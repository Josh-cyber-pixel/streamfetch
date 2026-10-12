"""streamfetch — download videos from YouTube, TikTok, and many other platforms.

A small, friendly wrapper around yt-dlp with both a command-line interface and a
web app.
"""

__version__ = "0.1.0"

from .core import (
    DownloadResult,
    MediaInfo,
    download,
    extract_info,
    fetch_metadata,
    ffmpeg_available,
    list_formats,
)

__all__ = [
    "DownloadResult",
    "MediaInfo",
    "download",
    "extract_info",
    "fetch_metadata",
    "ffmpeg_available",
    "list_formats",
    "__version__",
]
