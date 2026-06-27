from __future__ import annotations
"""Complete YouTube intelligence pipeline."""

from .transcriber import TranscriptExtractor, TranscriptResult
from .summarizer import YouTubeSummarizer, VideoSummary
from .cache import YouTubeCache
from .monitor import ChannelMonitor, ChannelVideo, ChannelMonitorConfig


class YouTubePipeline:
    """
    Complete YouTube intelligence pipeline.

    Combines transcript extraction, summarization, caching, and channel monitoring
    into a single easy-to-use interface.
    """

    def __init__(
        self,
        cache_dir: str | None = None,
        whisper_model: str = "base",
        llm_client=None,
    ):
        self.cache = YouTubeCache(cache_dir=cache_dir)
        self.transcriber = TranscriptExtractor(
            cache_dir=cache_dir,
            whisper_model=whisper_model,
        )
        self.summarizer = YouTubeSummarizer(llm_client=llm_client)
        self.monitor = ChannelMonitor(cache=self.cache)

    async def process_video(self, url: str, summarize: bool = True, force_refresh: bool = False) -> dict:
        """
        Process a YouTube video: extract transcript and optionally summarize.

        Args:
            url: YouTube video URL
            summarize: Whether to generate a summary
            force_refresh: Force re-extraction even if cached

        Returns:
            Dictionary with transcript and optionally summary
        """
        result = {
            "url": url,
            "transcript": None,
            "summary": None,
            "cached": False,
        }

        # Check cache first
        video_id = self._extract_video_id(url)
        cached_transcript = self.cache.get_transcript(video_id)

        if cached_transcript and not force_refresh:
            result["transcript"] = cached_transcript
            result["cached"] = True
        else:
            # Extract transcript
            transcript = await self.transcriber.extract(url, force_refresh=force_refresh)
            result["transcript"] = transcript
            self.cache.store_transcript(transcript)

        # Summarize if requested
        if summarize and result["transcript"]:
            cached_summary = self.cache.get_summary(video_id)

            if cached_summary and not force_refresh:
                result["summary"] = cached_summary
            else:
                summary = await self.summarizer.summarize(result["transcript"])
                result["summary"] = summary
                self.cache.store_summary(summary)

        return result

    async def summarize_video(self, url: str) -> VideoSummary:
        """Get or generate summary for a video."""
        video_id = self._extract_video_id(url)

        # Try cache first
        cached = self.cache.get_summary(video_id)
        if cached:
            return cached

        # Process video to get transcript
        result = await self.process_video(url, summarize=True)
        return result["summary"]

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from URL."""
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

    # Channel monitoring methods

    def add_channel(self, channel_id: str, name: str = "") -> None:
        """Add a channel to monitor."""
        self.monitor.add_channel(channel_id, name)

    def remove_channel(self, channel_id: str) -> None:
        """Remove a channel from monitoring."""
        self.monitor.remove_channel(channel_id)

    def get_monitored_channels(self) -> list[dict]:
        """Get list of monitored channels."""
        return self.monitor.get_monitored_channels()

    async def check_new_videos(self) -> dict[str, list[ChannelVideo]]:
        """Check all channels for new videos."""
        return await self.monitor.check_all_channels()

    async def start_monitoring(self) -> None:
        """Start background channel monitoring."""
        await self.monitor.start_monitoring()

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        await self.monitor.stop_monitoring()

    def on_new_video(self, callback) -> None:
        """Register callback for new video detection."""
        self.monitor.add_callback(callback)

    # Cache management

    def clear_cache(self, video_id: str | None = None) -> int:
        """Clear cache for a video or all."""
        return self.cache.clear_cache(video_id)

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()

    def search_videos(self, query: str, limit: int = 10) -> list[dict]:
        """Search cached transcripts."""
        return self.cache.search_transcripts(query, limit)
