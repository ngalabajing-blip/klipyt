"""Direct upload helper — returns a presigned PUT URL or accepts raw bytes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, UploadFile

from app.storage.s3 import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_VIDEO_MIME = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}
ALLOWED_AUDIO_MIME = {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4"}


@router.get("/presign")
async def presigned_put(filename: str, content_type: str = "video/mp4") -> dict:
    if content_type not in ALLOWED_VIDEO_MIME | ALLOWED_AUDIO_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported content type {content_type}")
    storage = get_storage()
    storage.ensure_bucket()
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    key = f"uploads/{uuid.uuid4().hex}/{safe}"
    url = storage.presigned_put(key, content_type=content_type, expires=3600)
    return {"key": key, "upload_url": url, "public_url": storage.public_url(key)}


@router.post("/direct")
async def direct_upload(file: UploadFile) -> dict:
    if file.content_type not in ALLOWED_VIDEO_MIME | ALLOWED_AUDIO_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported content type {file.content_type}")
    storage = get_storage()
    storage.ensure_bucket()
    safe = "".join(
        c if c.isalnum() or c in "._-" else "_" for c in (file.filename or "upload.mp4")
    )
    key = f"uploads/{uuid.uuid4().hex}/{safe}"
    body = await file.read()
    storage.upload_bytes(body, key, content_type=file.content_type)
    return {"key": key, "public_url": storage.public_url(key)}
