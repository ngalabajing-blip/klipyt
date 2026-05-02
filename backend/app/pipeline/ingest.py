"""Video ingest — download from URL (YouTube/TikTok/etc.) via yt-dlp."""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)


def _ensure_deno() -> None:
    """Install deno if not available and add to PATH."""
    deno_path = Path("/root/.deno/bin/deno")
    if not deno_path.exists():
        try:
            subprocess.run(
                ["sh", "-c", "curl -fsSL https://deno.land/install.sh | sh"],
                check=True, capture_output=True, timeout=120,
            )
        except Exception:
            logger.warning("Failed to install deno", exc_info=True)
    # Symlink to /usr/local/bin so yt-dlp subprocess can find it
    if deno_path.exists() and not Path("/usr/local/bin/deno").exists():
        try:
            Path("/usr/local/bin/deno").symlink_to(deno_path)
        except Exception:
            pass
    deno_bin = "/root/.deno/bin"
    if deno_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = deno_bin + ":" + os.environ.get("PATH", "")


def _get_cookiefile() -> str | None:
    """Return path to a cookie file from YOUTUBE_COOKIES env var (base64-encoded Netscape format)."""
    b64 = os.environ.get("YOUTUBE_COOKIES")
    if not b64:
        return None
    try:
        data = base64.b64decode(b64)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb")
        tmp.write(data)
        tmp.close()
        return tmp.name
    except Exception:
        logger.warning("Failed to decode YOUTUBE_COOKIES env var", exc_info=True)
        return None


@dataclass(slots=True)
class IngestResult:
    """Metadata + local path of an ingested video."""

    path: Path
    title: str
    duration: float
    thumbnail: str | None
    language: str | None
    extractor: str
    info: dict[str, Any]


def download_video(
    url: str,
    *,
    out_dir: str | Path,
    max_height: int = 1080,
    cookiefile: str | None = None,
) -> IngestResult:
    """Download a video to ``out_dir`` and return its local path + metadata."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_deno()
    # Verify deno is accessible
    try:
        r = subprocess.run(["deno", "--version"], capture_output=True, text=True, timeout=10)
        logger.info("Deno check: %s", r.stdout.strip().split("\n")[0] if r.returncode == 0 else "NOT FOUND")
    except Exception as e:
        logger.warning("Deno not accessible: %s", e)

    ydl_opts: dict[str, Any] = {
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "format": "best[height<=1080]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
        "verbose": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "writethumbnail": True,
        "convert_thumbnails": "jpg",
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        },
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
        ],
    }
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile
    else:
        auto_cookie = _get_cookiefile()
        if auto_cookie:
            ydl_opts["cookiefile"] = auto_cookie

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if info is None:
        raise RuntimeError(f"Failed to extract info for {url}")

    file_id = info["id"]
    candidates = list(out_dir.glob(f"{file_id}.*"))
    video_files = [c for c in candidates if c.suffix.lower() in {".mp4", ".mkv", ".webm"}]
    if not video_files:
        raise RuntimeError(f"yt-dlp downloaded no video file for {url}")
    video_path = video_files[0]

    thumb_files = [c for c in candidates if c.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    thumb_path = str(thumb_files[0]) if thumb_files else info.get("thumbnail")

    return IngestResult(
        path=video_path,
        title=info.get("title") or url,
        duration=float(info.get("duration") or 0.0),
        thumbnail=thumb_path,
        language=info.get("language"),
        extractor=info.get("extractor", "unknown"),
        info=info,
    )
