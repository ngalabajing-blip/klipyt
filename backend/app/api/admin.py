"""Admin routes — queue management, stuck job cleanup."""

from __future__ import annotations

import logging
import os

import sqlalchemy as sa
from fastapi import APIRouter
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _sync_engine():
    db_url = os.environ.get("DATABASE_URL", settings.database_url)
    db_url = (
        db_url
        .replace("+aiosqlite", "")
        .replace("+asyncpg", "+psycopg")
        .replace("sqlite+", "sqlite:")
    )
    if "sqlite" in db_url:
        return create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    return create_engine(db_url, future=True)


@router.post("/flush-queue")
async def flush_queue():
    """Flush all pending jobs from the RQ queue."""
    from app.workers.queue import default_queue
    q = default_queue()
    count = 0
    while q.jobs:
        job = q.dequeue()
        if job:
            count += 1
        else:
            break
    return {"flushed": count}


@router.post("/fail-stuck")
async def fail_stuck_jobs():
    """Mark all non-terminal jobs as failed (cleanup stale jobs)."""
    engine = _sync_engine()
    with Session(engine) as session:
        # Raw SQL to avoid enum issues
        result = session.execute(
            text("UPDATE jobs SET status = 'failed', error_message = 'Cleaned up stale job' WHERE status NOT IN ('completed', 'failed', 'cancelled')")
        )
        session.commit()
        count = result.rowcount
    return {"failed_count": count}
