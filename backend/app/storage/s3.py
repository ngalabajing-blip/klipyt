"""S3-compatible object storage adapter (works with MinIO and Cloudflare R2)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.client import Config

from app.config import settings

logger = logging.getLogger(__name__)


class Storage:
    """Lightweight wrapper over a boto3 S3 client."""

    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self.public_base = settings.s3_public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if it does not yet exist (idempotent)."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket)
                logger.info("Created bucket %s", self.bucket)
            except Exception as exc:
                logger.warning("Could not ensure bucket %s: %s", self.bucket, exc)

    def upload_file(
        self,
        path: str | Path,
        key: str,
        *,
        content_type: str | None = None,
    ) -> str:
        extra: dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type
        self.client.upload_file(str(path), self.bucket, key, ExtraArgs=extra)
        return self.public_url(key)

    def upload_bytes(
        self,
        data: bytes | BinaryIO,
        key: str,
        *,
        content_type: str | None = None,
    ) -> str:
        if isinstance(data, (bytes, bytearray)):
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=bytes(data),
                **({"ContentType": content_type} if content_type else {}),
            )
        else:
            extra: dict[str, str] = {}
            if content_type:
                extra["ContentType"] = content_type
            self.client.upload_fileobj(data, self.bucket, key, ExtraArgs=extra)
        return self.public_url(key)

    def download_to(self, key: str, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(path))
        return path

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )

    def presigned_put(
        self, key: str, *, content_type: str = "application/octet-stream", expires: int = 3600
    ) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
        )

    def public_url(self, key: str) -> str:
        return f"{self.public_base}/{key.lstrip('/')}"


@lru_cache
def get_storage() -> Storage:
    return Storage()
