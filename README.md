# streamfetch

Download videos from **YouTube, TikTok, and many other platforms** — from your
terminal or from a browser on your phone.

`streamfetch` is a small, friendly wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp).
It ships two front-ends backed by the same engine:

- **CLI** — a fast one-liner for your machine.
- **Web app** — a mobile-friendly page you can host yourself and open from any device.

> [!IMPORTANT]
> Only download content you have the right to download. Respect each platform's
> Terms of Service and applicable copyright law. This tool is provided for
> personal, legitimate use.

---

## Features

- Works with anything yt-dlp supports: YouTube, TikTok, Vimeo, Twitter/X,
  Instagram, Facebook, Reddit, Twitch VODs, and 1000+ more sites.
- Quality presets: `best`, `2160p`, `1440p`, `1080p`, `720p`, `480p`, `360p`, `worst`.
- Audio-only mode (extract to MP3).
- Playlist support (downloads every entry).
- Progress reporting in both the CLI and the web UI.
- Optional browser-cookie import for age-restricted / private videos.
- Web app: paste a link, preview metadata, watch live progress, tap to save.
- Dockerfile for one-command deployment.

## Requirements

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/download.html) on your `PATH` — **recommended**.
  Needed to merge separate video/audio streams (most 1080p+ downloads) and for
  audio extraction. Pre-muxed formats still download without it.

---

## Install

```bash
git clone https://github.com/Josh-cyber-pixel/streamfetch.git
cd streamfetch

python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -e .
```

This installs the `streamfetch` command.

## CLI usage

```bash
# Download best quality into ./downloads
streamfetch "https://www.youtube.com/watch?v=..."

# Pick a quality and output folder
streamfetch "https://youtu.be/..." -q 1080p -o "D:\Videos"

# Audio only (MP3)
streamfetch "https://www.tiktok.com/@user/video/..." -a

# Several links at once
streamfetch "<url1>" "<url2>" "<url3>"

# Just look at metadata, or list the available formats
streamfetch "<url>" --info
streamfetch "<url>" --list-formats

# Age-restricted video: borrow cookies from your browser
streamfetch "<url>" --cookies-from-browser firefox
```

Run `streamfetch --help` for all options.

## Web app

Start the server:

```bash
python -m streamfetch.web.app
# → http://localhost:8000
```

Then open it on your phone. To reach it over your local network, find your
computer's LAN IP (`ipconfig` on Windows, `ip addr` on Linux) and browse to
`http://<that-ip>:8000` from the phone (both must be on the same Wi-Fi).

Configuration via environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `STREAMFETCH_HOST` | `0.0.0.0` | Interface to bind |
| `STREAMFETCH_PORT` | `8000` | Port to listen on |
| `STREAMFETCH_DOWNLOAD_DIR` | `~/streamfetch_downloads` | Where files are stored |

### HTTP API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Status + whether ffmpeg was found |
| `POST` | `/api/info` | `{"url": "..."}` → metadata |
| `POST` | `/api/download` | `{"url", "quality", "audio_only"}` → `{"job_id"}` |
| `GET` | `/api/jobs/{job_id}` | Job status + progress |
| `GET` | `/api/jobs/{job_id}/file?filename=...` | Download the finished file |

## Docker

```bash
docker build -t streamfetch .
docker run --rm -p 8000:8000 -v streamfetch_data:/data streamfetch
```

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

## Project layout

```
streamfetch/
├─ streamfetch/
│  ├─ core.py            # yt-dlp wrapper (shared engine)
│  ├─ cli.py             # command-line interface
│  └─ web/
│     ├─ app.py          # FastAPI app + JSON API
│     └─ static/index.html
├─ tests/
├─ pyproject.toml
└─ Dockerfile
```

## License

MIT — see [LICENSE](LICENSE).

`streamfetch` is an independent project and is not affiliated with YouTube,
TikTok, or any other platform. Underlying downloading is powered by yt-dlp.
