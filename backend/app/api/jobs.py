"""Job management routes — submit a video, track status, list clips."""

from __future__ import annotations

import logging
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import ClipOut, JobCreateRequest, JobOut
from app.db.models import Job, JobKind, JobStatus
from app.db.session import get_session
from app.storage.s3 import get_storage
from app.workers.queue import default_queue
from app.workers.tasks import process_auto_clip_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(payload: JobCreateRequest, session: SessionDep) -> JobOut:
    if not payload.source_url and not payload.source_object_key:
        raise HTTPException(
            status_code=400, detail="Provide source_url or source_object_key"
        )
    job = Job(
        kind=JobKind.AUTO_CLIP,
        status=JobStatus.PENDING,
        source_url=payload.source_url,
        source_object_key=payload.source_object_key,
    )
    session.add(job)
    await session.flush()
    job_id = job.id

    queue = default_queue()
    # `job_id` is a reserved RQ kwarg, so pass our task arguments via `kwargs=`.
    queue.enqueue_call(
        func=process_auto_clip_job,
        kwargs={
            "job_id": job_id,
            "source_url": payload.source_url,
            "source_object_key": payload.source_object_key,
            "enable_voice_hook": payload.enable_voice_hook,
            "target_clip_count": payload.target_clip_count,
        },
        timeout=60 * 60,
    )
    await session.refresh(job, attribute_names=["clips"])
    return _job_out(job)


@router.get("", response_model=list[JobOut])
async def list_jobs(session: SessionDep, limit: int = 50) -> list[JobOut]:
    stmt = (
        sa.select(Job)
        .options(selectinload(Job.clips))
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    jobs = result.scalars().all()
    return [_job_out(j) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, session: SessionDep) -> JobOut:
    stmt = (
        sa.select(Job).options(selectinload(Job.clips)).where(Job.id == job_id)
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(job)


def _job_out(job: Job) -> JobOut:
    storage = get_storage()
    clips: list[ClipOut] = []
    for c in sorted(job.clips, key=lambda c: c.index):
        clips.append(
            ClipOut.model_validate(
                {
                    "id": c.id,
                    "index": c.index,
                    "title": c.title,
                    "caption": c.caption,
                    "hashtags_json": c.hashtags_json,
                    "score": c.score,
                    "reason": c.reason,
                    "start": c.start,
                    "end": c.end,
                    "duration": c.duration,
                    "object_key": (
                        storage.public_url(c.object_key) if c.object_key else None
                    ),
                    "thumbnail_object_key": (
                        storage.public_url(c.thumbnail_object_key)
                        if c.thumbnail_object_key
                        else None
                    ),
                    "aspect_ratio": c.aspect_ratio,
                    "has_voice_hook": c.has_voice_hook,
                    "created_at": c.created_at,
                }
            )
        )
    return JobOut.model_validate(
        {
            "id": job.id,
            "kind": job.kind.value if hasattr(job.kind, "value") else str(job.kind),
            "status": (
                job.status.value if hasattr(job.status, "value") else str(job.status)
            ),
            "progress": job.progress,
            "source_url": job.source_url,
            "source_title": job.source_title,
            "source_thumbnail": job.source_thumbnail,
            "source_duration": job.source_duration,
            "source_language": job.source_language,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "clips": clips,
        }
    )
