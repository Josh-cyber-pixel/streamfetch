"""Core download engine.

This module is a thin, typed wrapper around ``yt-dlp``. Everything else in the
project (CLI and web app) builds on top of it, so that behaviour stays identical
across interfaces.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yt_dlp

DEFAULT_OUTPUT_DIR = Path("downloads")

#: Player clients that can be forced for YouTube. ``""`` lets yt-dlp pick.
#: Some clients (``tv``/``android``/``ios``/``mweb``) can bypass YouTube's
#: "confirm you're not a bot" check on datacenter IPs.
YOUTUBE_CLIENTS = ["", "web", "tv", "android", "ios", "mweb", "web_safari"]

QUALITY_PRESETS: dict[str, int | None] = {
    "best": None,
    "2160p": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "worst": -1,
}

ProgressCallback = Callable[[dict], None]


@dataclass
class MediaInfo:
    """Normalised metadata about a single media item."""

    id: str
    title: str
    webpage_url: str
    extractor: str
    uploader: str | None = None
    duration: float | None = None
    thumbnail: str | None = None
    view_count: int | None = None
    is_playlist: bool = False
    entry_count: int = 1

    @classmethod
    def from_ytdlp(cls, info: dict) -> MediaInfo:
        entries = info.get("entries") or []
        is_playlist = info.get("_type") == "playlist" or bool(entries)
        return cls(
            id=str(info.get("id") or ""),
            title=info.get("title") or "Untitled",
            webpage_url=info.get("webpage_url") or info.get("original_url") or "",
            extractor=info.get("extractor_key") or info.get("extractor") or "unknown",
            uploader=info.get("uploader") or info.get("channel") or info.get("creator"),
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            view_count=info.get("view_count"),
            is_playlist=is_playlist,
            entry_count=len(entries) if entries else 1,
        )


@dataclass
class DownloadResult:
    """The outcome of downloading a single media item."""

    title: str
    filepath: str
    ext: str
    extractor: str
    webpage_url: str
    duration: float | None = None
    filesize: int | None = None
    info: dict = field(default_factory=dict, repr=False)


def ffmpeg_available() -> bool:
    """Return ``True`` when an ``ffmpeg`` binary is reachable on ``PATH``.

    ffmpeg is required for muxing separate video/audio streams and for audio
    extraction. Downloads of pre-muxed formats still work without it.
    """
    return shutil.which("ffmpeg") is not None


def build_format_selector(quality: str = "best", audio_only: bool = False) -> str:
    """Translate a quality preset into a yt-dlp format selector string."""
    if audio_only:
        return "bestaudio/best"

    if quality not in QUALITY_PRESETS:
        valid = ", ".join(QUALITY_PRESETS)
        raise ValueError(f"Unknown quality {quality!r}. Valid options: {valid}")

    height = QUALITY_PRESETS[quality]
    if height is None:
        return "bestvideo*+bestaudio/best"
    if height < 0:
        return "worstvideo*+worstaudio/worst"
    return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"


def _base_opts(
    output_dir: str | Path,
    *,
    cookies_from_browser: str | None = None,
    player_client: str | None = None,
) -> dict:
    out = Path(output_dir).expanduser()
    opts: dict[str, Any] = {
        "outtmpl": str(out / "%(title).150B [%(id)s].%(ext)s"),
        "windowsfilenames": True,
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "continuedl": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "ignoreerrors": False,
        "postprocessors": [],
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if player_client:
        opts["extractor_args"] = {"youtube": {"player_client": [player_client]}}
    return opts


def _progress_hook(callback: ProgressCallback | None):
    if callback is None:
        return None

    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            percent = (downloaded / total * 100.0) if total else None
            callback(
                {
                    "status": "downloading",
                    "percent": percent,
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    "filename": d.get("filename"),
                }
            )
        elif status == "finished":
            callback({"status": "processing", "filename": d.get("filename")})
        elif status == "error":
            callback({"status": "error", "filename": d.get("filename")})

    return hook


def extract_info(
    url: str,
    *,
    cookies_from_browser: str | None = None,
    player_client: str | None = None,
    flat: bool = False,
) -> dict:
    """Fetch raw metadata for ``url`` without downloading anything."""
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    if flat:
        opts["extract_flat"] = "in_playlist"
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if player_client:
        opts["extractor_args"] = {"youtube": {"player_client": [player_client]}}

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def fetch_metadata(
    url: str,
    *,
    cookies_from_browser: str | None = None,
    player_client: str | None = None,
) -> MediaInfo:
    """Return a :class:`MediaInfo` for ``url``."""
    return MediaInfo.from_ytdlp(
        extract_info(url, cookies_from_browser=cookies_from_browser, player_client=player_client)
    )


def list_formats(
    url: str,
    *,
    cookies_from_browser: str | None = None,
    player_client: str | None = None,
) -> list[dict]:
    """Return a simplified, display-friendly list of available formats."""
    info = extract_info(url, cookies_from_browser=cookies_from_browser, player_client=player_client)
    formats = []
    for f in info.get("formats") or []:
        formats.append(
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution")
                or (f"{f.get('width')}x{f.get('height')}" if f.get("height") else None),
                "fps": f.get("fps"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "abr": f.get("abr"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "note": f.get("format_note"),
            }
        )
    return formats


def _result_from_entry(entry: dict) -> DownloadResult:
    requested = entry.get("requested_downloads") or []
    filepath = ""
    filesize = None
    if requested:
        filepath = requested[0].get("filepath") or requested[0].get("_filename") or ""
        filesize = requested[0].get("filesize") or requested[0].get("total_bytes")
    if not filepath:
        filepath = entry.get("filepath") or entry.get("_filename") or ""

    if not filesize and filepath:
        try:
            filesize = Path(filepath).stat().st_size
        except OSError:
            pass

    return DownloadResult(
        title=entry.get("title") or "Untitled",
        filepath=filepath,
        ext=entry.get("ext") or Path(filepath).suffix.lstrip("."),
        extractor=entry.get("extractor_key") or entry.get("extractor") or "unknown",
        webpage_url=entry.get("webpage_url") or "",
        duration=entry.get("duration"),
        filesize=filesize,
        info=entry,
    )


def download(
    url: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    quality: str = "best",
    audio_only: bool = False,
    progress: ProgressCallback | None = None,
    cookies_from_browser: str | None = None,
    player_client: str | None = None,
) -> list[DownloadResult]:
    """Download ``url`` and return one :class:`DownloadResult` per media item.

    Handles playlists too: a playlist URL yields one result per entry. Raises
    ``yt_dlp.utils.DownloadError`` on failure (e.g. a private or deleted video).
    """
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    opts = _base_opts(out, cookies_from_browser=cookies_from_browser, player_client=player_client)
    opts["format"] = build_format_selector(quality, audio_only)
    hook = _progress_hook(progress)
    if hook is not None:
        opts["progress_hooks"] = [hook]

    if audio_only:
        opts["postprocessors"].append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        )

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    entries = info.get("entries") if info.get("_type") == "playlist" else None
    if entries:
        return [_result_from_entry(e) for e in entries if e]
    return [_result_from_entry(info)]
