from __future__ import annotations
"""Transcript extraction for YouTube videos."""

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TranscriptResult:
    """Result of transcript extraction."""

    video_id: str
    title: str
    duration: int | None
    transcript: str
    language: str | None
    has_manual_subtitles: bool
    extraction_method: str
    timestamp: datetime
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "duration": self.duration,
            "transcript": self.transcript,
            "language": self.language,
            "has_manual_subtitles": self.has_manual_subtitles,
            "extraction_method": self.extraction_method,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
        }


class TranscriptExtractor:
    """
    Extract transcripts from YouTube videos.

    Methods:
    1. Try YouTube Transcript API (fastest, for videos with captions)
    2. Fall back to yt-dlp --write-auto-sub
    3. Fall back to audio download + Whisper transcription
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        whisper_model: str = "base",
    ):
        self.cache_dir = cache_dir or self._get_default_cache_dir()
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.whisper_model = whisper_model

    def _get_default_cache_dir(self) -> Path:
        """Get default cache directory."""
        base = Path.home() / ".win11-omniagent" / "youtube_cache"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL."""
        import re

        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"(?:embed\/)([0-9A-Za-z_-]{11})",
            r"^([0-9A-Za-z_-]{11})$",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract video ID from: {url}")

    async def extract(self, url: str, force_refresh: bool = False) -> TranscriptResult:
        """Extract transcript from a YouTube video."""
        video_id = self._extract_video_id(url)

        if not force_refresh:
            cached = self._load_from_cache(video_id)
            if cached:
                return cached

        # Method 1: Try YouTube Transcript API
        try:
            result = await self._try_youtube_transcript_api(video_id, url)
            if result:
                self._save_to_cache(result)
                return result
        except Exception:
            pass

        # Method 2: Try yt-dlp
        try:
            result = await self._try_yt_dlp(video_id, url)
            if result:
                self._save_to_cache(result)
                return result
        except Exception:
            pass

        # Method 3: Fall back to Whisper
        try:
            result = await self._try_whisper(video_id, url)
            self._save_to_cache(result)
            return result
        except Exception as e:
            return TranscriptResult(
                video_id=video_id,
                title="Unknown",
                duration=None,
                transcript="",
                language=None,
                has_manual_subtitles=False,
                extraction_method="failed",
                timestamp=datetime.now(),
                confidence=0.0,
            )

    async def _try_youtube_transcript_api(self, video_id: str, url: str) -> TranscriptResult | None:
        """Try using youtube-transcript-api."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None
            language = None

            try:
                transcript = transcript_list.find_manually_created_transcript(["en"])
                language = "en"
            except Exception:
                pass

            if not transcript:
                try:
                    transcript = transcript_list.find_generated_transcript(["en"])
                    language = "en"
                except Exception:
                    pass

            if not transcript:
                for t in transcript_list:
                    transcript = t
                    language = t.language_code
                    break

            if transcript:
                transcript_data = transcript.fetch()
                text = " ".join([entry["text"] for entry in transcript_data])

                return TranscriptResult(
                    video_id=video_id,
                    title=url,
                    duration=None,
                    transcript=text,
                    language=language,
                    has_manual_subtitles=not transcript.is_generated,
                    extraction_method="youtube_transcript_api",
                    timestamp=datetime.now(),
                    confidence=0.95 if not transcript.is_generated else 0.85,
                )

        except Exception:
            pass

        return None

    async def _try_yt_dlp(self, video_id: str, url: str) -> TranscriptResult | None:
        """Try using yt-dlp to download subtitles."""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                cmd = [
                    "yt-dlp",
                    "--write-auto-sub",
                    "--skip-download",
                    "--output", f"{temp_dir}/%(id)s",
                    "--sub-langs", "en",
                    url,
                ]

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    subtitle_files = list(Path(temp_dir).glob(f"{video_id}*.vtt"))
                    if subtitle_files:
                        content = subtitle_files[0].read_text()
                        transcript = self._parse_vtt(content)

                        return TranscriptResult(
                            video_id=video_id,
                            title=url,
                            duration=None,
                            transcript=transcript,
                            language="en",
                            has_manual_subtitles=False,
                            extraction_method="yt_dlp",
                            timestamp=datetime.now(),
                            confidence=0.85,
                        )

            except FileNotFoundError:
                pass

        return None

    async def _try_whisper(self, video_id: str, url: str) -> TranscriptResult:
        """Transcribe using Whisper (audio download + transcription)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = f"{temp_dir}/audio.mp3"

            cmd_download = [
                "yt-dlp",
                "-x",
                "--audio-format", "mp3",
                "-o", audio_path,
                url,
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd_download,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()
            except FileNotFoundError:
                raise Exception("yt-dlp not installed")

            if not os.path.exists(audio_path):
                raise Exception("Audio download failed")

            try:
                import whisper

                model = whisper.load_model(self.whisper_model)
                result = model.transcribe(audio_path)

                return TranscriptResult(
                    video_id=video_id,
                    title=result.get("text", "")[:50],
                    duration=result.get("duration"),
                    transcript=result["text"],
                    language=result.get("language"),
                    has_manual_subtitles=False,
                    extraction_method="whisper",
                    timestamp=datetime.now(),
                    confidence=0.80,
                )

            except ImportError:
                raise Exception("OpenAI Whisper not installed")

    def _parse_vtt(self, vtt_content: str) -> str:
        """Parse VTT subtitle format to plain text."""
        lines = vtt_content.split("\n")
        text_parts = []

        for line in lines:
            line = line.strip()
            if "-->" in line or line.startswith("WEBVTT") or line.startswith("NOTE"):
                continue
            if not line or line.isdigit():
                continue
            text_parts.append(line)

        return " ".join(text_parts)

    def _load_from_cache(self, video_id: str) -> TranscriptResult | None:
        """Load transcript from cache."""
        cache_file = self.cache_dir / f"{video_id}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                return TranscriptResult(**data)
            except Exception:
                pass
        return None

    def _save_to_cache(self, result: TranscriptResult) -> None:
        """Save transcript to cache."""
        cache_file = self.cache_dir / f"{result.video_id}.json"
        cache_file.write_text(json.dumps(result.to_dict(), indent=2))

    def clear_cache(self, video_id: str | None = None) -> None:
        """Clear cache for a specific video or all."""
        if video_id:
            cache_file = self.cache_dir / f"{video_id}.json"
            if cache_file.exists():
                cache_file.unlink()
        else:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()
