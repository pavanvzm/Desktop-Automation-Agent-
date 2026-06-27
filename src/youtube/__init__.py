from __future__ import annotations
"""
Win11-OmniAgent YouTube Intelligence Package

Provides:
- Transcript extraction (yt-dlp + Whisper)
- Summarization chain (LLM-based)
- Caching layer (vector DB)
- Channel monitoring (RSS feeds)
"""

from .pipeline import YouTubePipeline
from .transcriber import TranscriptExtractor
from .summarizer import YouTubeSummarizer, VideoSummary
from .cache import YouTubeCache
from .monitor import ChannelMonitor

__all__ = [
    "YouTubePipeline",
    "TranscriptExtractor",
    "YouTubeSummarizer",
    "VideoSummary",
    "YouTubeCache",
    "ChannelMonitor",
]
