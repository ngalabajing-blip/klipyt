"""RQ task entrypoints — these run in a worker process."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Clip, Job
from app.pipeline.clip import CutOptions, cut_clip, make_thumbnail
from app.pipeline.ingest import download_video
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


def _ai_clip_windows(
    subtitle_path: Path | None,
    *,
    target_count: int,
) -> list[dict] | None:
    """Run MiMo highlight detection on captions and return clip windows.

    Returns ``None`` if there are no usable captions, MiMo isn't configured,
    or the API call fails — caller should fall back to even-split.
    """
    if subtitle_path is None or not Path(subtitle_path).exists():
        return None
    if not settings.mimo_api_key:
        logger.info("MIMO_API_KEY not set; skipping AI highlights")
        return None

    from app.mimo.client import MiMoClient
    from app.pipeline.captions import parse_vtt
    from app.pipeline.highlight import detect_highlights

    transcript = parse_vtt(subtitle_path)
    if transcript is None or not transcript.segments:
        logger.info("No usable captions in %s", subtitle_path)
        return None

    logger.info(
        "Captions parsed: %d segments, %.1fs, lang=%s",
        len(transcript.segments), transcript.duration, transcript.language,
    )

    client = MiMoClient()
    try:
        candidates = asyncio.run(
            detect_highlights(transcript, client=client, target_count=target_count)
        )
    except Exception:
        logger.exception("MiMo highlight detection failed")
        return None

    if not candidates:
        return None

    return [
        {
            "start": float(c.start),
            "end": float(c.end),
            "title": c.title or f"Clip {i + 1}",
            "caption": c.caption or "",
            "score": float(c.score),
            "reason": c.reason or "",
            "hashtags": list(c.hashtags or []),
        }
        for i, c in enumerate(candidates)
    ]


def _even_split_windows(duration: float, target_count: int) -> list[dict]:
    """Fallback strategy when AI highlights aren't available."""
    clip_duration = (
        min(60.0, max(15.0, duration / target_count)) if duration > 0 else 30.0
    )
    if duration > 0:
        segment_len = duration / max(1, target_count)
        starts = [i * segment_len + 2.0 for i in range(target_count)]
        starts = [s for s in starts if s + 5.0 < duration]
    else:
        starts = [0.0]
    if not starts:
        starts = [0.0]
    windows: list[dict] = []
    for idx, start in enumerate(starts):
        end = (
            min(start + clip_duration, duration) if duration > 0 else start + 30.0
        )
        windows.append({
            "start": start,
            "end": end,
            "title": f"Clip {idx + 1}",
            "caption": "",
            "score": 0.0,
            "reason": "Auto-generated",
            "hashtags": [],
        })
    return windows


def process_auto_clip_job(
    job_id: str,
    *,
    source_url: str | None = None,
    source_object_key: str | None = None,
    enable_voice_hook: bool = False,
    target_clip_count: int = 6,
) -> str:
    """Run the clip pipeline — download + cut + upload.

    Pipeline:
        download (with auto-captions) → MiMo highlight detection if captions
        available → cut clips with stream copy → upload.  Falls back to
        even-split when captions are missing or MiMo fails — keeps the worker
        within Railway's 512 MB limit by *never* loading Whisper.
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
            subtitle_path: Path | None = None
            if source_path is None:
                logger.info("Downloading %s", source_url)
                result = download_video(source_url, out_dir=work_dir / "src")
                video_path = result.path
                title = result.title
                duration = result.duration
                subtitle_path = result.subtitle_path
            else:
                video_path = source_path
                title = video_path.stem
                duration = 0.0

            _update_job(session, job_id, status="downloading", progress=40,
                        source_title=title, source_duration=duration)

            # ---- Pick clip windows (AI if captions available, else even-split) ----
            _update_job(session, job_id, status="analyzing", progress=45)
            ai_windows = _ai_clip_windows(subtitle_path, target_count=target_clip_count)
            if ai_windows:
                logger.info("Using %d AI-selected clips", len(ai_windows))
                windows = ai_windows
            else:
                logger.info("Falling back to even-split clip windows")
                windows = _even_split_windows(duration, target_clip_count)

            # ---- Cut clips ----
            _update_job(session, job_id, status="clipping", progress=50)
            artifacts = []

            for idx, w in enumerate(windows):
                start = float(w["start"])
                end = float(w["end"])
                if duration > 0:
                    end = min(end, duration)
                if end - start < 5.0:  # skip degenerate windows
                    logger.warning("Skipping clip %d: too short (%.1fs)", idx, end - start)
                    continue

                clip_dir = work_dir / "clips" / f"{idx:02d}"
                clip_path = clip_dir / "clip.mp4"
                thumb_path = clip_dir / "thumb.jpg"

                logger.info("Cutting clip %d: %.1f-%.1f (%s)", idx, start, end, w.get("title"))
                cut_clip(video_path, CutOptions(start=start, end=end, out_path=clip_path))
                make_thumbnail(clip_path, thumb_path)

                artifacts.append({
                    "index": idx,
                    "title": w.get("title") or f"Clip {idx + 1}",
                    "caption": w.get("caption") or f"Auto-generated clip from {title}",
                    "reason": w.get("reason") or "",
                    "score": float(w.get("score") or 0.0),
                    "hashtags": list(w.get("hashtags") or []),
                    "start": start,
                    "end": end,
                    "duration": end - start,
                    "clip_path": clip_path,
                    "thumb_path": thumb_path,
                })

                pct = 50 + int(40 * (idx + 1) / max(1, len(windows)))
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
                    hashtags_json=art["hashtags"],
                    score=art["score"],
                    reason=art["reason"] or "Auto-generated",
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
