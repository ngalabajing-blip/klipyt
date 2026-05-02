"""RQ task entrypoints — these run in a worker process."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Clip, Job, JobStatus
from app.pipeline.runner import run_auto_clip
from app.storage.s3 import get_storage

logger = logging.getLogger(__name__)


def _sync_engine():
    sync_url = settings.database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg").replace("sqlite+", "sqlite:")
    if sync_url.startswith("postgresql+psycopg"):
        return create_engine(sync_url, future=True)
    if sync_url.startswith("sqlite"):
        return create_engine(sync_url, future=True, connect_args={"check_same_thread": False})
    return create_engine(sync_url, future=True)


def _update_job(session: Session, job_id: str, **fields) -> None:
    session.execute(sa.update(Job).where(Job.id == job_id).values(**fields))
    session.commit()


def process_auto_clip_job(
    job_id: str,
    *,
    source_url: str | None = None,
    source_object_key: str | None = None,
    enable_voice_hook: bool = False,
    target_clip_count: int = 6,
) -> str:
    """Run the auto-clip pipeline end-to-end and persist artifacts."""
    engine = _sync_engine()
    storage = get_storage()
    storage.ensure_bucket()

    work_dir = Path("./storage/work") / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # If the source is already in our storage, fetch to a local file so the
    # pipeline can read it directly (yt-dlp is bypassed).
    source_path: Path | None = None
    if source_object_key:
        src_dir = work_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        source_path = src_dir / Path(source_object_key).name
        storage.download_to(source_object_key, source_path)

    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        _update_job(session, job_id, status=JobStatus.DOWNLOADING, progress=5)

        def progress(stage: str, pct: int) -> None:
            status_map = {
                "downloading": JobStatus.DOWNLOADING,
                "transcribing": JobStatus.TRANSCRIBING,
                "detecting_highlights": JobStatus.DETECTING,
                "completed": JobStatus.COMPLETED,
            }
            status = status_map.get(stage)
            if stage.startswith("clipping_"):
                status = JobStatus.CLIPPING
            with Session(engine) as s:
                values: dict = {"progress": pct}
                if status is not None:
                    values["status"] = status
                s.execute(sa.update(Job).where(Job.id == job_id).values(**values))
                s.commit()

        try:
            result = asyncio.run(
                run_auto_clip(
                    source_url=source_url or job.source_url if source_path is None else None,
                    source_path=source_path,
                    work_dir=work_dir,
                    target_clip_count=target_clip_count,
                    enable_voice_hook=enable_voice_hook,
                    progress=progress,
                )
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("Job %s failed", job_id)
            with Session(engine) as s:
                s.execute(
                    sa.update(Job)
                    .where(Job.id == job_id)
                    .values(status=JobStatus.FAILED, error_message=str(exc)[:2000])
                )
                s.commit()
            raise

        # Upload clips
        for idx, art in enumerate(result.clips):
            video_key = f"jobs/{job_id}/clips/{idx:02d}.mp4"
            thumb_key = f"jobs/{job_id}/clips/{idx:02d}.jpg"
            storage.upload_file(art.final_clip, video_key, content_type="video/mp4")
            storage.upload_file(art.thumbnail, thumb_key, content_type="image/jpeg")
            session.add(
                Clip(
                    job_id=job_id,
                    index=idx,
                    title=art.candidate.title,
                    caption=art.candidate.caption,
                    hashtags_json=art.candidate.hashtags,
                    score=art.candidate.score,
                    reason=art.candidate.reason,
                    start=art.candidate.start,
                    end=art.candidate.end,
                    duration=art.candidate.duration,
                    object_key=video_key,
                    thumbnail_object_key=thumb_key,
                    has_voice_hook=art.has_voice_hook,
                )
            )
        # Persist transcript + source meta
        session.execute(
            sa.update(Job)
            .where(Job.id == job_id)
            .values(
                source_title=result.title,
                source_duration=result.duration,
                source_language=result.language,
                highlights_json={"candidates": [c.model_dump() for c in result.candidates]},
                status=JobStatus.COMPLETED,
                progress=100,
            )
        )
        session.commit()
    return job_id
