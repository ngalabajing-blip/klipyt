"""Health-check + diagnostics."""

from __future__ import annotations

import os

from fastapi import APIRouter

from app import __version__
from app.api.schemas import HealthOut
from app.config import settings

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health():
    import subprocess, shutil
    deno = shutil.which("deno")
    ytdlp = shutil.which("yt-dlp")
    deno_ver = ""
    if deno:
        try:
            r = subprocess.run(["deno", "--version"], capture_output=True, text=True, timeout=5)
            deno_ver = r.stdout.strip().split("\n")[0]
        except Exception:
            deno_ver = "error"
    ytdlp_ver = ""
    if ytdlp:
        try:
            r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=5)
            ytdlp_ver = r.stdout.strip()
        except Exception:
            ytdlp_ver = "error"
    return {
        "ok": True,
        "deno_path": deno,
        "deno_version": deno_ver,
        "ytdlp_path": ytdlp,
        "ytdlp_version": ytdlp_ver,
        "path": os.environ.get("PATH", ""),
    }
