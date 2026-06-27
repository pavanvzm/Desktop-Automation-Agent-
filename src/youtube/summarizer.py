"""YouTube video summarization using LLM."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .transcriber import TranscriptResult


@dataclass
class VideoSummary:
    """Structured summary of a YouTube video."""

    video_id: str
    title: str
    duration: int | None

    key_points: list[str] = field(default_factory=list)
    main_themes: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    timestamps: list[dict[str, Any]] = field(default_factory=list)

    summary: str = ""
    sentiment: str = "neutral"
    sentiment_score: float = 0.5

    confidence: float = 1.0
    processed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "duration": self.duration,
            "key_points": self.key_points,
            "main_themes": self.main_themes,
            "action_items": self.action_items,
            "timestamps": self.timestamps,
            "summary": self.summary,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "confidence": self.confidence,
            "processed_at": self.processed_at.isoformat(),
        }

    def format_for_display(self) -> str:
        """Format summary for human-readable display."""
        lines = [f"# Summary: {self.title}\n"]

        if self.duration:
            minutes = self.duration // 60
            lines.append(f"**Duration**: {minutes} minutes\n")

        lines.append(f"**Sentiment**: {self.sentiment.title()} ({self.sentiment_score:.0%})\n")

        if self.summary:
            lines.append(f"\n## Overview\n{self.summary}\n")

        if self.key_points:
            lines.append("\n## Key Points\n")
            for i, point in enumerate(self.key_points, 1):
                lines.append(f"{i}. {point}\n")

        if self.main_themes:
            lines.append("\n## Main Themes\n")
            for theme in self.main_themes:
                lines.append(f"- {theme}\n")

        if self.action_items:
            lines.append("\n## Action Items\n")
            for item in self.action_items:
                lines.append(f"- [ ] {item}\n")

        if self.timestamps:
            lines.append("\n## Chapters\n")
            for ts in self.timestamps[:10]:
                lines.append(f"- [{ts['timestamp']}] {ts['description']}\n")

        return "".join(lines)


class YouTubeSummarizer:
    """
    Summarize YouTube videos using LLM.

    Uses map-reduce pattern:
    1. Chunk the transcript
    2. Summarize each chunk (map)
    3. Combine summaries (reduce)
    4. Extract structured information
    """

    def __init__(
        self,
        llm_client: Any = None,
        chunk_size: int = 2000,
        overlap: int = 200,
    ):
        self.llm_client = llm_client
        self.chunk_size = chunk_size
        self.overlap = overlap

    def _chunk_transcript(self, transcript: str) -> list[dict]:
        """Split transcript into overlapping chunks."""
        chunks = []
        start = 0

        while start < len(transcript):
            end = start + self.chunk_size
            chunk_text = transcript[start:end]

            if end < len(transcript):
                last_period = chunk_text.rfind(".")
                last_newline = chunk_text.rfind("\n")
                break_point = max(last_period, last_newline)

                if break_point > start + self.chunk_size // 2:
                    chunk_text = chunk_text[:break_point + 1]
                    end = start + break_point + 1

            chunks.append({
                "text": chunk_text.strip(),
                "start_char": start,
                "end_char": end,
                "word_count": len(chunk_text.split()),
            })

            start = end - self.overlap

        return chunks

    async def summarize(self, transcript_result: TranscriptResult) -> VideoSummary:
        """Generate a structured summary of a video."""
        if not self.llm_client:
            return self._fallback_summary(transcript_result)

        chunks = self._chunk_transcript(transcript_result.transcript)
        chunk_summaries = []

        for i, chunk in enumerate(chunks):
            summary = await self._summarize_chunk(chunk["text"], i + 1, len(chunks))
            chunk_summaries.append(summary)

        combined_summary = await self._combine_summaries(chunk_summaries)
        structured = await self._extract_structured_info(
            transcript_result.transcript,
            combined_summary
        )

        return VideoSummary(
            video_id=transcript_result.video_id,
            title=transcript_result.title,
            duration=transcript_result.duration,
            summary=combined_summary,
            **structured,
        )

    async def _summarize_chunk(self, text: str, chunk_num: int, total_chunks: int) -> str:
        """Summarize a single chunk of transcript."""
        prompt = f"""Summarize the following section of a video transcript.
Focus on the main points and key information.

Section {chunk_num} of {total_chunks}:

{text}

Provide a concise summary (2-3 sentences):"""

        try:
            response = await self.llm_client.chat([
                {"role": "user", "content": prompt}
            ])
            return response.strip()
        except Exception:
            return text[:200] + "..."

    async def _combine_summaries(self, summaries: list[str]) -> str:
        """Combine multiple chunk summaries into one coherent summary."""
        if len(summaries) == 1:
            return summaries[0]

        prompt = f"""Combine the following section summaries into a coherent video summary.
Remove redundancies and organize the information logically.

Summaries:
{chr(10).join(f"{i+1}. {s}" for i, s in enumerate(summaries))}

Provide a comprehensive summary (3-5 sentences):"""

        try:
            response = await self.llm_client.chat([
                {"role": "user", "content": prompt}
            ])
            return response.strip()
        except Exception:
            return " ".join(summaries[:3])

    async def _extract_structured_info(
        self,
        transcript: str,
        summary: str
    ) -> dict:
        """Extract structured information from the transcript."""
        prompt = f"""Analyze this video transcript and extract structured information.
Return a JSON object with the following fields:
- key_points: Array of 3-5 main takeaways
- main_themes: Array of 2-4 main themes/topics
- action_items: Array of any actionable items mentioned
- sentiment: "positive", "negative", or "neutral"
- sentiment_score: A number from 0.0 to 1.0

Transcript/Summary:
{summary[:2000]}

Return only valid JSON:"""

        try:
            response = await self.llm_client.chat([
                {"role": "user", "content": prompt}
            ])

            import json
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass

        return {
            "key_points": [],
            "main_themes": [],
            "action_items": [],
            "sentiment": "neutral",
            "sentiment_score": 0.5,
        }

    def _fallback_summary(self, transcript_result: TranscriptResult) -> VideoSummary:
        """Generate a basic summary without LLM."""
        text = transcript_result.transcript
        sentences = text.split(".")[:5]
        summary = ". ".join(s.strip() for s in sentences if s.strip()) + "."

        words = text.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 5:
                word_freq[word] = word_freq.get(word, 0) + 1

        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        key_points = [f"Topic discussed: {word}" for word, _ in top_words[:5]]

        return VideoSummary(
            video_id=transcript_result.video_id,
            title=transcript_result.title,
            duration=transcript_result.duration,
            summary=summary,
            key_points=key_points,
            main_themes=["See key points above"],
            action_items=[],
            sentiment="neutral",
            sentiment_score=0.5,
            confidence=0.5,
        )

    async def summarize_batch(
        self,
        transcripts: list[TranscriptResult]
    ) -> list[VideoSummary]:
        """Summarize multiple videos in parallel."""
        tasks = [self.summarize(t) for t in transcripts]
        return await asyncio.gather(*tasks)