"""YouTube cookie persistence + retrieval.

The cookie file is stored in object storage so a separate refresher service
can rotate it without redeploying the backend. The lookup order is:

1. Object storage (R2/S3) at the configured key — refreshed on schedule.
2. ``YOUTUBE_COOKIES`` env var (base64 of a Netscape ``cookies.txt``) —
   bootstrap fallback used until the refresher writes its first copy.

Both paths return a path to a temp file on local disk that yt-dlp can
``--cookies`` with. The caller owns deletion.
"""

from __future__ import annotations

import base64
import logging
import os
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Where the refresher writes the canonical cookie file. Kept short so it
# also reads cleanly in the R2 dashboard.
COOKIE_OBJECT_KEY = os.environ.get("YOUTUBE_COOKIES_KEY", "auth/youtube-cookies.txt")

# In-process cache so a worker handling many jobs back-to-back doesn't pull
# from R2 on every download. TTL is short — the refresher runs hourly at
# most so a 5-min staleness budget is fine.
_CACHE_TTL_SECONDS = 300

_cache_path: str | None = None
_cache_loaded_at: float = 0.0


def _load_from_object_storage(dest: Path) -> bool:
    """Try to download cookies from object storage to ``dest``.

    Returns True on success, False otherwise. We only attempt this if the
    storage backend is actually S3 (no point hitting the local fallback
    when there's nothing to fetch).
    """
    try:
        from app.config import settings

        # Only S3-backed storage carries cross-process state; local disk
        # would just reflect this same machine's writes.
        if "localhost" in (settings.s3_endpoint_url or "") or not settings.s3_endpoint_url:
            return False
        from app.storage.s3 import get_storage as get_s3
        store = get_s3()
        store.download_to(COOKIE_OBJECT_KEY, dest)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as exc:  # boto/network errors, key missing, etc.
        logger.info("YouTube cookies not in object storage (%s): %s", COOKIE_OBJECT_KEY, exc)
        return False


def _load_from_env(dest: Path) -> bool:
    """Decode the ``YOUTUBE_COOKIES`` env var into ``dest``."""
    b64 = os.environ.get("YOUTUBE_COOKIES")
    if not b64:
        return False
    try:
        dest.write_bytes(base64.b64decode(b64))
        return dest.stat().st_size > 0
    except Exception:
        logger.warning("Failed to decode YOUTUBE_COOKIES env var", exc_info=True)
        return False


def get_cookie_file() -> str | None:
    """Materialize the current YouTube cookie file on local disk.

    Caches the path for ``_CACHE_TTL_SECONDS`` so concurrent downloads
    inside the same worker don't all pay the storage roundtrip.
    """
    global _cache_path, _cache_loaded_at
    now = time.time()
    if _cache_path and (now - _cache_loaded_at) < _CACHE_TTL_SECONDS:
        if Path(_cache_path).exists():
            return _cache_path
        # Cached path was deleted (e.g. /tmp cleanup) — fall through and
        # repopulate.

    tmp = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name)
    if _load_from_object_storage(tmp) or _load_from_env(tmp):
        _cache_path = str(tmp)
        _cache_loaded_at = now
        logger.info("YouTube cookies loaded (%d bytes) -> %s", tmp.stat().st_size, tmp)
        return _cache_path

    try:
        tmp.unlink()
    except OSError:
        pass
    return None


def save_cookie_file(path: str | Path) -> None:
    """Upload a Netscape ``cookies.txt`` from disk to object storage.

    Used by the refresher service. Bumps the in-process cache so the next
    ``get_cookie_file`` call re-pulls.
    """
    from app.storage.s3 import get_storage as get_s3
    store = get_s3()
    store.upload_file(path, COOKIE_OBJECT_KEY, content_type="text/plain")
    logger.info("YouTube cookies uploaded -> %s", COOKIE_OBJECT_KEY)
    _invalidate_cache()


def _invalidate_cache() -> None:
    global _cache_path, _cache_loaded_at
    _cache_path = None
    _cache_loaded_at = 0.0
