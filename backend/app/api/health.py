"""Health-check + diagnostics."""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health():
    import shutil
    import subprocess
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


@router.get("/debug/ytdlp")
async def debug_ytdlp(url: str = "https://youtu.be/dQw4w9WgXcQ"):
    """Debug endpoint: run yt-dlp --list-formats and return output."""
    import subprocess

    from app.pipeline.ingest import _get_cookiefile
    cmd = ["yt-dlp", "--list-formats", "--no-check-certificates"]
    cookiefile = _get_cookiefile()
    if cookiefile:
        cmd.extend(["--cookies", cookiefile])
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {
            "returncode": r.returncode,
            "stdout": r.stdout[-3000:],
            "stderr": r.stderr[-3000:],
            "cookiefile": cookiefile,
        }
    except Exception as e:
        return {"error": str(e)}
