"""Command-line interface for streamfetch."""

from __future__ import annotations

import argparse
import sys

from . import __version__, core


def _human_bytes(n: float | None) -> str:
    if not n:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _human_duration(seconds: float | None) -> str:
    if not seconds:
        return "?"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _progress_line(state: dict) -> None:
    status = state.get("status")
    if status == "downloading":
        percent = state.get("percent")
        pct = f"{percent:5.1f}%" if percent is not None else "  ?  "
        speed = state.get("speed")
        speed_txt = f"{_human_bytes(speed)}/s" if speed else "?"
        eta = state.get("eta")
        eta_txt = _human_duration(eta) if eta else "?"
        total = _human_bytes(state.get("total_bytes"))
        sys.stdout.write(
            f"\r  [download] {pct} of {total}  {speed_txt}  ETA {eta_txt}   "
        )
        sys.stdout.flush()
    elif status == "processing":
        sys.stdout.write("\r  [download] 100.0% — post-processing...            \n")
        sys.stdout.flush()


def _cmd_info(args: argparse.Namespace) -> int:
    info = core.fetch_metadata(args.urls[0], cookies_from_browser=args.cookies_from_browser)
    print(f"Title:     {info.title}")
    print(f"Source:    {info.extractor}")
    print(f"Uploader:  {info.uploader or '-'}")
    print(f"Duration:  {_human_duration(info.duration)}")
    print(f"Views:     {info.view_count if info.view_count is not None else '-'}")
    if info.is_playlist:
        print(f"Playlist:  yes ({info.entry_count} items)")
    print(f"URL:       {info.webpage_url}")
    return 0


def _cmd_formats(args: argparse.Namespace) -> int:
    formats = core.list_formats(args.urls[0], cookies_from_browser=args.cookies_from_browser)
    print(f"{'ID':<12}{'EXT':<7}{'RESOLUTION':<13}{'VCODEC':<12}{'ACODEC':<12}{'SIZE':<10}")
    print("-" * 66)
    for f in formats:
        print(
            f"{str(f['format_id']):<12}"
            f"{str(f['ext']):<7}"
            f"{str(f['resolution'] or '-'):<13}"
            f"{str(f['vcodec'] or '-'):<12}"
            f"{str(f['acodec'] or '-'):<12}"
            f"{_human_bytes(f['filesize']):<10}"
        )
    return 0


def _cmd_download(args: argparse.Namespace) -> int:
    if args.audio and not core.ffmpeg_available():
        print(
            "warning: ffmpeg was not found on PATH. Audio extraction may fail.\n"
            "         Install ffmpeg: https://ffmpeg.org/download.html\n",
            file=sys.stderr,
        )

    exit_code = 0
    for i, url in enumerate(args.urls):
        if len(args.urls) > 1:
            print(f"\n=== [{i + 1}/{len(args.urls)}] {url}")
        try:
            results = core.download(
                url,
                output_dir=args.output,
                quality=args.quality,
                audio_only=args.audio,
                progress=None if args.quiet else _progress_line,
                cookies_from_browser=args.cookies_from_browser,
            )
        except Exception as exc:  # noqa: BLE001 - surface a clean message to the user
            print(f"  error: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        for res in results:
            size = _human_bytes(res.filesize)
            print(f"  saved: {res.filepath}  ({size})")

    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="streamfetch",
        description="Download videos from YouTube, TikTok, and many other platforms.",
    )
    parser.add_argument("urls", nargs="+", metavar="URL", help="one or more media URLs")
    parser.add_argument(
        "-o",
        "--output",
        default=str(core.DEFAULT_OUTPUT_DIR),
        help="output directory (default: ./downloads)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="best",
        choices=list(core.QUALITY_PRESETS.keys()),
        help="video quality preset (default: best)",
    )
    parser.add_argument(
        "-a",
        "--audio",
        action="store_true",
        help="download audio only and convert to mp3 (needs ffmpeg)",
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="list available formats and exit",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="print metadata only, do not download",
    )
    parser.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        choices=["chrome", "firefox", "edge", "brave", "opera", "vivaldi", "safari"],
        help="use cookies from a browser (for private/age-restricted videos)",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress progress output")
    parser.add_argument("--version", action="version", version=f"streamfetch {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_formats:
        return _cmd_formats(args)
    if args.info:
        return _cmd_info(args)
    return _cmd_download(args)


if __name__ == "__main__":
    raise SystemExit(main())
