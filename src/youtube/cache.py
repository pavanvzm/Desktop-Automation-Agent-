"""YouTube caching layer using vector database."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .transcriber import TranscriptResult
from .summarizer import VideoSummary


class YouTubeCache:
    """
    Cache for YouTube transcripts and summaries.

    Uses SQLite for metadata and can optionally use vector DB for semantic search.
    """

    def __init__(self, cache_dir: str | Path | None = None):
        self.cache_dir = cache_dir or self._get_default_cache_dir()
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_default_cache_dir(self) -> Path:
        """Get default cache directory."""
        base = Path.home() / ".win11-omniagent" / "youtube_cache"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        db_path = self.cache_dir / "cache.db"
        self.conn = sqlite3.connect(str(db_path))
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                duration INTEGER,
                transcript TEXT,
                language TEXT,
                has_manual_subtitles INTEGER,
                extraction_method TEXT,
                timestamp TEXT,
                confidence REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                duration INTEGER,
                summary_data TEXT,
                processed_at TEXT,
                FOREIGN KEY (video_id) REFERENCES transcripts(video_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                video_id TEXT,
                title TEXT,
                published_at TEXT,
                cached_at TEXT,
                UNIQUE(channel_id, video_id)
            )
        """)

        self.conn.commit()

    def store_transcript(self, result: TranscriptResult) -> None:
        """Store a transcript in the cache."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO transcripts
            (video_id, title, duration, transcript, language, has_manual_subtitles,
             extraction_method, timestamp, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.video_id,
            result.title,
            result.duration,
            result.transcript,
            result.language,
            1 if result.has_manual_subtitles else 0,
            result.extraction_method,
            result.timestamp.isoformat(),
            result.confidence,
        ))
        self.conn.commit()

    def get_transcript(self, video_id: str) -> TranscriptResult | None:
        """Retrieve a transcript from cache."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM transcripts WHERE video_id = ?",
            (video_id,)
        )
        row = cursor.fetchone()

        if row:
            return TranscriptResult(
                video_id=row[0],
                title=row[1],
                duration=row[2],
                transcript=row[3],
                language=row[4],
                has_manual_subtitles=bool(row[5]),
                extraction_method=row[6],
                timestamp=datetime.fromisoformat(row[7]),
                confidence=row[8],
            )
        return None

    def has_transcript(self, video_id: str) -> bool:
        """Check if transcript is cached."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM transcripts WHERE video_id = ?",
            (video_id,)
        )
        return cursor.fetchone() is not None

    def store_summary(self, summary: VideoSummary) -> None:
        """Store a summary in the cache."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO summaries
            (video_id, title, duration, summary_data, processed_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            summary.video_id,
            summary.title,
            summary.duration,
            json.dumps(summary.to_dict()),
            summary.processed_at.isoformat(),
        ))
        self.conn.commit()

    def get_summary(self, video_id: str) -> VideoSummary | None:
        """Retrieve a summary from cache."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT summary_data FROM summaries WHERE video_id = ?",
            (video_id,)
        )
        row = cursor.fetchone()

        if row:
            data = json.loads(row[0])
            data["processed_at"] = datetime.fromisoformat(data["processed_at"])
            return VideoSummary(**{k: v for k, v in data.items() if k in VideoSummary.__dataclass_fields__})
        return None

    def store_channel_video(self, channel_id: str, video_id: str, title: str, published_at: str) -> None:
        """Store a video entry from channel monitoring."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO channel_videos
            (channel_id, video_id, title, published_at, cached_at)
            VALUES (?, ?, ?, ?, ?)
        """, (channel_id, video_id, title, published_at, datetime.now().isoformat()))
        self.conn.commit()

    def get_channel_videos(
        self,
        channel_id: str,
        since: datetime | None = None
    ) -> list[dict]:
        """Get videos from a channel since a certain date."""
        cursor = self.conn.cursor()

        if since:
            cursor.execute(
                """SELECT video_id, title, published_at FROM channel_videos
                   WHERE channel_id = ? AND published_at >= ?
                   ORDER BY published_at DESC""",
                (channel_id, since.isoformat())
            )
        else:
            cursor.execute(
                """SELECT video_id, title, published_at FROM channel_videos
                   WHERE channel_id = ?
                   ORDER BY published_at DESC""",
                (channel_id,)
            )

        return [
            {"video_id": row[0], "title": row[1], "published_at": row[2]}
            for row in cursor.fetchall()
        ]

    def search_transcripts(self, query: str, limit: int = 10) -> list[dict]:
        """Search cached transcripts by keyword (simple text search)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT video_id, title, transcript FROM transcripts
               WHERE transcript LIKE ? OR title LIKE ?
               LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit)
        )

        return [
            {"video_id": row[0], "title": row[1], "transcript_preview": row[2][:500]}
            for row in cursor.fetchall()
        ]

    def clear_cache(self, video_id: str | None = None) -> int:
        """Clear cache for a video or all."""
        cursor = self.conn.cursor()

        if video_id:
            cursor.execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))
            cursor.execute("DELETE FROM summaries WHERE video_id = ?", (video_id,))
        else:
            cursor.execute("DELETE FROM transcripts")
            cursor.execute("DELETE FROM summaries")

        self.conn.commit()
        return cursor.rowcount

    def get_stats(self) -> dict:
        """Get cache statistics."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM transcripts")
        transcript_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM summaries")
        summary_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT channel_id) FROM channel_videos")
        channel_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(LENGTH(transcript)) FROM transcripts")
        total_size = cursor.fetchone()[0] or 0

        return {
            "transcript_count": transcript_count,
            "summary_count": summary_count,
            "channel_count": channel_count,
            "total_transcript_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
        }

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self, 'conn'):
            self.conn.close()