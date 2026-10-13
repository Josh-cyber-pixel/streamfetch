"""FastAPI web app for streamfetch.

Serves a small mobile-friendly UI plus a JSON API. Downloads run in background
threads; clients poll ``/api/jobs/{id}`` for progress and then fetch the file
from ``/api/jobs/{id}/file``.

Run with::

    python -m streamfetch.web.app
    # or
    uvicorn streamfetch.web.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__, core

STATIC_DIR = Path(__file__).parent / "static"
DOWNLOAD_ROOT = Path(
    os.environ.get("STREAMFETCH_DOWNLOAD_DIR", Path.home() / "streamfetch_downloads")
).resolve()

JOB_TTL_SECONDS = 60 * 60  # keep finished jobs around for one hour
MAX_JOBS = 200

app = FastAPI(
    title="streamfetch",
    version=__version__,
    description="Download videos from YouTube, TikTok, and many other platforms.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class InfoRequest(BaseModel):
    url: str
    cookies_from_browser: str | None = None


class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"
    audio_only: bool = False
    cookies_from_browser: str | None = None


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    return url


def _purge_old_jobs() -> None:
    now = time.time()
    stale = [
        jid
        for jid, job in _jobs.items()
        if job.get("finished_at") and now - job["finished_at"] > JOB_TTL_SECONDS
    ]
    for jid in stale:
        _jobs.pop(jid, None)

    if len(_jobs) > MAX_JOBS:
        ordered = sorted(_jobs.items(), key=lambda kv: kv[1].get("created_at", 0))
        for jid, _ in ordered[: len(_jobs) - MAX_JOBS]:
            _jobs.pop(jid, None)


def _run_job(job_id: str, request: DownloadRequest) -> None:
    job_dir = DOWNLOAD_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def on_progress(state: dict) -> None:
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is None:
                return
            job["progress"] = state
            if state.get("status") == "processing":
                job["stage"] = "processing"

    try:
        results = core.download(
            request.url,
            output_dir=job_dir,
            quality=request.quality,
            audio_only=request.audio_only,
            progress=on_progress,
            cookies_from_browser=request.cookies_from_browser,
        )
        files = []
        for res in results:
            files.append(
                {
                    "title": res.title,
                    "filename": Path(res.filepath).name,
                    "filesize": res.filesize,
                    "ext": res.ext,
                }
            )
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job["status"] = "done"
                job["files"] = files
                job["finished_at"] = time.time()
    except Exception as exc:  # noqa: BLE001 - report any failure to the client
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job["status"] = "error"
                job["error"] = str(exc)
                job["finished_at"] = time.time()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "ffmpeg": core.ffmpeg_available(),
    }


@app.post("/api/info")
def info(request: InfoRequest) -> dict:
    url = _validate_url(request.url)
    try:
        meta = core.fetch_metadata(url, cookies_from_browser=request.cookies_from_browser)
    except yt_dlp.utils.DownloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": meta.id,
        "title": meta.title,
        "extractor": meta.extractor,
        "uploader": meta.uploader,
        "duration": meta.duration,
        "thumbnail": meta.thumbnail,
        "view_count": meta.view_count,
        "webpage_url": meta.webpage_url,
        "is_playlist": meta.is_playlist,
        "entry_count": meta.entry_count,
    }


@app.post("/api/download")
def start_download(request: DownloadRequest) -> dict:
    url = _validate_url(request.url)
    if request.quality not in core.QUALITY_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown quality {request.quality!r}")

    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _purge_old_jobs()
        _jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "stage": "queued",
            "url": url,
            "quality": request.quality,
            "audio_only": request.audio_only,
            "progress": None,
            "files": [],
            "error": None,
            "created_at": time.time(),
            "finished_at": None,
        }

    thread = threading.Thread(target=_run_job, args=(job_id, request), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(job)


@app.get("/api/jobs/{job_id}/file")
def job_file(job_id: str, filename: str | None = None) -> FileResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["status"] != "done":
            raise HTTPException(status_code=409, detail="Job is not finished")
        files = list(job.get("files") or [])

    if not files:
        raise HTTPException(status_code=404, detail="No files produced")

    target = None
    job_dir = DOWNLOAD_ROOT / job_id
    if filename:
        candidate = job_dir / filename
        if candidate.is_file():
            target = candidate
    if target is None:
        target = job_dir / files[0]["filename"]

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File missing on disk")

    return FileResponse(path=str(target), filename=target.name)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


def main() -> None:
    import uvicorn

    host = os.environ.get("STREAMFETCH_HOST", "0.0.0.0")
    # Render and friends inject $PORT; fall back to STREAMFETCH_PORT, then 8000.
    port = int(os.environ.get("PORT") or os.environ.get("STREAMFETCH_PORT") or "8000")
    uvicorn.run("streamfetch.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
