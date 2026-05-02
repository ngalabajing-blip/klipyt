"""Object storage abstraction (S3-compatible with local fallback)."""

import logging
import os

logger = logging.getLogger(__name__)


def get_storage():
    """Return S3 storage if configured, otherwise fall back to local disk."""
    s3_endpoint = os.environ.get("S3_ENDPOINT_URL", "")
    s3_bucket = os.environ.get("S3_BUCKET", "")
    s3_key = os.environ.get("S3_ACCESS_KEY_ID", "")

    # Only use S3 if explicitly configured (not default localhost)
    if s3_endpoint and s3_bucket and s3_key and "localhost" not in s3_endpoint:
        from app.storage.s3 import Storage
        return Storage()

    logger.info("S3 not configured — using local storage fallback")
    from app.storage.local import LocalStorage
    return LocalStorage()


__all__ = ["get_storage"]
