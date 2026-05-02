"""Local-disk fallback storage for tests / local-only development.

Drop-in replacement for :class:`Storage` when no S3 endpoint is available.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO


class LocalStorage:
    def __init__(self, root: str = "./storage") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base = ""

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
        return str(dst)

    def upload_bytes(
        self, data: bytes | BinaryIO, key: str, *, content_type: str | None = None
    ) -> str:
        dst = self._abs(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, (bytes, bytearray)):
            dst.write_bytes(bytes(data))
        else:
            with dst.open("wb") as f:
                shutil.copyfileobj(data, f)
        return str(dst)

    def download_to(self, key: str, path: str | Path) -> Path:
        src = self._abs(key)
        dst = Path(path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return dst

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        return str(self._abs(key))

    def presigned_put(self, key: str, **_: object) -> str:
        return str(self._abs(key))

    def public_url(self, key: str) -> str:
        return str(self._abs(key))
