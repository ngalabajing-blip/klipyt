"""Admin routes — queue management, stuck job cleanup."""

from __future__ import annotations

import logging

import sqlalchemy as sa
from fastapi import APIRouter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Job, JobStatus
from app.workers.queue import default_queue, redis_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _sync_engine():
    sync_url = (
        settings.database_url
        .replace("+aiosqlite", "")
        .replace("+asyncpg", "+psycopg")
        .replace("sqlite+", "sqlite:")
    )
    if sync_url.startswith("postgresql+psycopg"):
        return create_engine(sync_url, future=True)
    if sync_url.startswith("sqlite"):
        return create_engine(sync_url, future=True, connect_args={"check_same_thread": False})
    return create_engine(sync_url, future=True)


@router.post("/flush-queue")
async def flush_queue():
    """Flush all pending jobs from the RQ queue."""
    q = default_queue()
    count = 0
    while q.jobs:
        job = q.dequeue()
        if job:
            count += 1
        else:
            break
    # Also clean up started_job_registry
    registry = q.started_job_registry
    for job_id in registry.get_job_ids():
        registry.remove(job_id)
        count += 1
    return {"flushed": count}


@router.post("/fail-stuck")
async def fail_stuck_jobs():
    """Mark all non-terminal jobs as failed (cleanup stale jobs)."""
    engine = _sync_engine()
    terminal = {"completed", "failed", "cancelled"}
    with Session(engine) as session:
        stuck = session.execute(
            sa.select(Job).where(Job.status.notin_(terminal))
        ).scalars().all()
        for job in stuck:
            session.execute(
                sa.update(Job)
                .where(Job.id == job.id)
                .values(status="failed", error_message="Manually marked as stuck — cleaned up")
            )
        session.commit()
        ids = [j.id for j in stuck]
    return {"failed_count": len(ids), "job_ids": ids}
