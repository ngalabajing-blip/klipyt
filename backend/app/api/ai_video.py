"""AI video generator endpoint (synchronous for MVP)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AIVideoRequest
from app.db.models import Job, JobKind, JobStatus
from app.db.session import get_session
from app.mimo.client import MiMoClient
from app.pipeline import ai_video as aiv
from app.storage.s3 import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-videos", tags=["ai-videos"])


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/generate")
async def generate_ai_video(req: AIVideoRequest, session: SessionDep) -> dict:
    job_id = uuid.uuid4().hex
    work_dir = Path("./storage/work") / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    client = MiMoClient()

    job = Job(
        id=job_id,
        kind=JobKind.AI_VIDEO,
        status=JobStatus.RENDERING,
        progress=10,
        ai_video_kind=req.kind,
        ai_video_prompt=req.prompt,
    )
    session.add(job)
    await session.flush()

    try:
        script = await aiv.generate_script(
            client=client, kind=req.kind, prompt=req.prompt, language=req.language
        )
        # Synthesise narration: prefer voice-design if a description is given.
        if req.voice_description or script.voice_description:
            tts = await client.tts_voice_design(
                script.text,
                req.voice_description or script.voice_description,
            )
        else:
            tts = await client.tts(script.text)
        audio_path = work_dir / "narration.wav"
        audio_path.write_bytes(tts.audio_wav)

        # Run the heavy ffmpeg work in a thread to avoid blocking.
        loop = asyncio.get_running_loop()

        def _render() -> Path:
            images = aiv.render_visuals(script.beats, work_dir / "frames")
            duration = max(2.0, len(tts.audio_wav) / (24_000 * 2))  # 16-bit mono samples
            return aiv.assemble_video(
                images, audio_path, work_dir / "out.mp4", audio_duration=duration
            )

        out_video = await loop.run_in_executor(None, _render)
        storage = get_storage()
        storage.ensure_bucket()
        key = f"ai_videos/{job_id}/out.mp4"
        storage.upload_file(out_video, key, content_type="video/mp4")

        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.source_title = script.title
        await session.flush()
        return {
            "job_id": job_id,
            "title": script.title,
            "video_url": storage.public_url(key),
            "beats": script.beats,
            "voice_description": script.voice_description,
        }
    except Exception as exc:
        logger.exception("AI video generation failed")
        job.status = JobStatus.FAILED
        job.error_message = str(exc)[:2000]
        await session.flush()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
