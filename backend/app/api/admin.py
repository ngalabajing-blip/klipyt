"""Admin routes — queue management, stuck job cleanup."""

from __future__ import annotations

import logging
import os
import traceback

import sqlalchemy as sa
from fastapi import APIRouter
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _get_db_url():
    db_url = os.environ.get("DATABASE_URL", settings.database_url)
    db_url = (
        db_url
        .replace("+aiosqlite", "")
        .replace("+asyncpg", "+psycopg")
        .replace("sqlite+", "sqlite:")
    )
    return db_url


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
    try:
        db_url = _get_db_url()
        engine = create_engine(db_url, future=True)
        with engine.connect() as conn:
            result = conn.execute(
                text("UPDATE jobs SET status = 'failed', error_message = 'Cleaned up stale job' WHERE status NOT IN ('completed', 'failed', 'cancelled')")
            )
            conn.commit()
            count = result.rowcount
        return {"failed_count": count, "db": db_url.split("@")[-1] if "@" in db_url else "local"}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()[-500:]}
