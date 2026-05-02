"""RQ task entrypoints — these run in a worker process."""

from __future__ import annotations

import logging
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Clip, Job, JobStatus
from app.pipeline.ingest import download_video
from app.pipeline.clip import CutOptions, cut_clip, make_thumbnail
from app.storage.s3 import get_storage

logger = logging.getLogger(__name__)


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
    """Run the clip pipeline — download + cut + upload.

    Lightweight pipeline: download video → cut clips with stream copy → upload.
    Skips transcription/highlight detection for now to stay within Railway's
    512 MB memory limit.
    """
    engine = _sync_engine()
    storage = get_storage()
    storage.ensure_bucket()

    work_dir = Path("./storage/work") / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

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
        _update_job(session, job_id, status="downloading", progress=5)

        try:
            # ---- Download ----
            if source_path is None:
                logger.info("Downloading %s", source_url)
                result = download_video(source_url, out_dir=work_dir / "src")
                video_path = result.path
                title = result.title
                duration = result.duration
            else:
                video_path = source_path
                title = video_path.stem
                duration = 0.0

            _update_job(session, job_id, status="downloading", progress=40,
                        source_title=title, source_duration=duration)

            # ---- Determine clip windows ----
            # Simple strategy: divide video into N equal segments, take first 30-60s of each
            clip_duration = min(60.0, max(15.0, duration / target_clip_count)) if duration > 0 else 30.0
            if duration > 0:
                # Spread clips evenly across the video
                segment_len = duration / max(1, target_clip_count)
                clip_starts = [i * segment_len + 2.0 for i in range(target_clip_count)]
                # Don't start too close to the end
                clip_starts = [s for s in clip_starts if s + 5.0 < duration]
            else:
                clip_starts = [0.0]
                clip_duration = 30.0

            if not clip_starts:
                clip_starts = [0.0]

            # ---- Cut clips ----
            _update_job(session, job_id, status="clipping", progress=50)
            artifacts = []

            for idx, start in enumerate(clip_starts):
                end = min(start + clip_duration, duration) if duration > 0 else start + 30.0
                clip_dir = work_dir / "clips" / f"{idx:02d}"
                clip_path = clip_dir / "clip.mp4"
                thumb_path = clip_dir / "thumb.jpg"

                logger.info("Cutting clip %d: %.1f-%.1f", idx, start, end)
                cut_clip(video_path, CutOptions(start=start, end=end, out_path=clip_path))
                make_thumbnail(clip_path, thumb_path)

                artifacts.append({
                    "index": idx,
                    "title": f"Clip {idx + 1}",
                    "caption": f"Auto-generated clip from {title}",
                    "start": start,
                    "end": end,
                    "duration": end - start,
                    "clip_path": clip_path,
                    "thumb_path": thumb_path,
                })

                pct = 50 + int(40 * (idx + 1) / len(clip_starts))
                _update_job(session, job_id, progress=pct)

            # ---- Upload ----
            _update_job(session, job_id, progress=92)
            for art in artifacts:
                video_key = f"jobs/{job_id}/clips/{art['index']:02d}.mp4"
                thumb_key = f"jobs/{job_id}/clips/{art['index']:02d}.jpg"
                storage.upload_file(art["clip_path"], video_key, content_type="video/mp4")
                storage.upload_file(art["thumb_path"], thumb_key, content_type="image/jpeg")

                session.add(Clip(
                    job_id=job_id,
                    index=art["index"],
                    title=art["title"],
                    caption=art["caption"],
                    hashtags_json=[],
                    score=0.0,
                    reason="Auto-generated",
                    start=art["start"],
                    end=art["end"],
                    duration=art["duration"],
                    object_key=video_key,
                    thumbnail_object_key=thumb_key,
                    has_voice_hook=False,
                ))

            session.execute(
                sa.update(Job)
                .where(Job.id == job_id)
                .values(
                    source_title=title,
                    source_duration=duration,
                    status="completed",
                    progress=100,
                )
            )
            session.commit()
            logger.info("Job %s completed — %d clips", job_id, len(artifacts))

        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            with Session(engine) as s:
                s.execute(
                    sa.update(Job)
                    .where(Job.id == job_id)
                    .values(status="failed", error_message=str(exc)[:2000])
                )
                s.commit()
            raise

    return job_id
