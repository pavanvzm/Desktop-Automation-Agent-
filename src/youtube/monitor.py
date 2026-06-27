"""YouTube channel monitoring using RSS feeds."""

import asyncio
import feedparser
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from .cache import YouTubeCache


@dataclass
class ChannelVideo:
    """Represents a video from a YouTube channel."""

    video_id: str
    title: str
    published_at: datetime
    url: str
    description: str = ""


@dataclass
class ChannelMonitorConfig:
    """Configuration for channel monitoring."""

    check_interval_minutes: int = 30
    max_videos_per_check: int = 10
    include_description: bool = False


class ChannelMonitor:
    """
    Monitor YouTube channels for new videos using RSS feeds.

    Features:
    - RSS feed polling for channel updates
    - Detection of new videos since last check
    - Optional automatic summarization of new videos
    - Configurable alert callbacks
    """

    def __init__(
        self,
        cache: YouTubeCache | None = None,
        config: ChannelMonitorConfig | None = None,
    ):
        self.cache = cache or YouTubeCache()
        self.config = config or ChannelMonitorConfig()
        self._running = False
        self._task: asyncio.Task | None = None
        self._callbacks: list[Callable[[list[ChannelVideo]], Any]] = []
        self._channel_configs: dict[str, dict] = {}

    def add_callback(self, callback: Callable[[list[ChannelVideo]], Any]) -> None:
        """Add a callback to be called when new videos are detected."""
        self._callbacks.append(callback)

    def add_channel(self, channel_id: str, name: str = "", tags: list[str] | None = None) -> None:
        """Add a channel to monitor."""
        self._channel_configs[channel_id] = {
            "name": name or channel_id,
            "tags": tags or [],
            "last_check": None,
        }

    def remove_channel(self, channel_id: str) -> None:
        """Remove a channel from monitoring."""
        if channel_id in self._channel_configs:
            del self._channel_configs[channel_id]

    def get_rss_url(self, channel_id: str) -> str:
        """Get the RSS feed URL for a channel."""
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    async def check_channel(self, channel_id: str) -> list[ChannelVideo]:
        """Check a single channel for new videos."""
        rss_url = self.get_rss_url(channel_id)

        try:
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, rss_url)
        except Exception:
            return []

        if not feed.entries:
            return []

        new_videos = []
        config = self._channel_configs.get(channel_id, {})
        last_check = config.get("last_check")

        for entry in feed.entries[:self.config.max_videos_per_check]:
            video = self._parse_entry(entry)

            # Check if this is a new video
            if last_check and video.published_at <= last_check:
                continue

            # Store in cache
            self.cache.store_channel_video(
                channel_id=channel_id,
                video_id=video.video_id,
                title=video.title,
                published_at=video.published_at.isoformat(),
            )

            new_videos.append(video)

        # Update last check time
        self._channel_configs[channel_id]["last_check"] = datetime.now()

        return new_videos

    def _parse_entry(self, entry: Any) -> ChannelVideo:
        """Parse an RSS entry into a ChannelVideo."""
        # Extract video ID from yt:videoId or media_content
        video_id = None

        if hasattr(entry, "yt_videoid"):
            video_id = entry.yt_videoid
        elif hasattr(entry, "media_content") and entry.media_content:
            url = entry.media_content[0].get("url", "")
            match = re.search(r"/vi/([^/]+)/", url)
            if match:
                video_id = match.group(1)

        if not video_id:
            # Try to extract from link
            match = re.search(r"watch\?v=([^&]+)", entry.get("link", ""))
            if match:
                video_id = match.group(1)
            else:
                video_id = entry.get("id", "").split(":")[-1]

        # Parse published date
        published_at = datetime.now()
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6])

        # Get description
        description = ""
        if self.config.include_description:
            if hasattr(entry, "summary"):
                description = entry.summary
            elif hasattr(entry, "content") and entry.content:
                description = entry.content[0].get("value", "")

        return ChannelVideo(
            video_id=video_id,
            title=entry.get("title", "Unknown"),
            published_at=published_at,
            url=entry.get("link", f"https://youtube.com/watch?v={video_id}"),
            description=description,
        )

    async def check_all_channels(self) -> dict[str, list[ChannelVideo]]:
        """Check all monitored channels for new videos."""
        results = {}

        for channel_id in self._channel_configs:
            videos = await self.check_channel(channel_id)
            if videos:
                results[channel_id] = videos

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(videos)
                        else:
                            callback(videos)
                    except Exception:
                        pass

        return results

    async def start_monitoring(self) -> None:
        """Start background monitoring."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        interval = self.config.check_interval_minutes * 60

        while self._running:
            try:
                await self.check_all_channels()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(60)  # Wait 1 minute on error

    def get_monitored_channels(self) -> list[dict]:
        """Get list of monitored channels."""
        return [
            {
                "channel_id": channel_id,
                **config,
            }
            for channel_id, config in self._channel_configs.items()
        ]

    def get_recent_videos(self, channel_id: str, hours: int = 24) -> list[dict]:
        """Get recent videos from a channel."""
        since = datetime.now() - timedelta(hours=hours)
        return self.cache.get_channel_videos(channel_id, since=since)