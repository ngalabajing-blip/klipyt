"""Local-disk fallback storage for tests / local-only development.

Drop-in replacement for :class:`Storage` when no S3 endpoint is available.
Files are served via FastAPI's /files static mount.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO


def _get_base_url() -> str:
    """Determine the public base URL for file access."""
    # Explicit env var takes priority
    base = os.environ.get("APP_BASE_URL", "")
    if base:
        return base.rstrip("/")
    # Railway auto-detected domain
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if domain:
        return f"https://{domain}"
    return "http://localhost:8000"


class LocalStorage:
    def __init__(self, root: str = "./storage") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base = _get_base_url()

    def _abs(self, key: str) -> Path:
        return self.root / key.lstrip("/")

    def ensure_bucket(self) -> None:
        return None

    def upload_file(
        self, path: str | Path, key: str, *, content_type: str | None = None
    ) -> str:
        dst = self._abs(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)
        return self.public_url(key)

    def upload_bytes(
        self, data: BinaryIO | bytes, key: str, *, content_type: str | None = None
    ) -> str:
        dst = self._abs(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, (bytes, bytearray)):
            dst.write_bytes(bytes(data))
        else:
            with dst.open("wb") as f:
                shutil.copyfileobj(data, f)
        return self.public_url(key)

    def download_to(self, key: str, path: str | Path) -> Path:
        src = self._abs(key)
        dst = Path(path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return dst

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        return self.public_url(key)

    def presigned_put(self, key: str, **_: object) -> str:
        return self.public_url(key)

    def public_url(self, key: str) -> str:
        return f"{self.public_base}/files/{key.lstrip('/')}"
