"""Object storage abstraction (S3-compatible)."""

from app.storage.s3 import Storage, get_storage

__all__ = ["Storage", "get_storage"]
