"""End-to-end pipeline orchestration for the auto-clip workflow."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.mimo.client import MiMoClient
from app.mimo.types import HighlightCandidate
from app.pipeline import clip as clipmod
from app.pipeline import highlight as hl
from app.pipeline import ingest, subtitle, transcribe, voice_hook
from app.pipeline.transcribe import Transcript

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClipArtifact:
    candidate: HighlightCandidate
    raw_clip: Path
    final_clip: Path
    thumbnail: Path
    has_voice_hook: bool = False


@dataclass(slots=True)
class AutoClipResult:
    source_path: Path
    title: str
    duration: float
    language: str
    transcript: Transcript
    candidates: list[HighlightCandidate]
    clips: list[ClipArtifact] = field(default_factory=list)


ProgressCb = Callable[[str, int], None]


async def run_auto_clip(
    *,
    source_url: str | None = None,
    source_path: str | Path | None = None,
    work_dir: str | Path,
    target_clip_count: int = 6,
    enable_voice_hook: bool = False,
    enable_subtitles: bool = True,
    progress: ProgressCb | None = None,
    client: MiMoClient | None = None,
) -> AutoClipResult:
    """Run the full pipeline and return all generated artifacts."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    client = client or MiMoClient()

    def _p(stage: str, pct: int) -> None:
        logger.info("[%s] %d%%", stage, pct)
        if progress:
            try:
                progress(stage, pct)
            except Exception as exc:
                logger.warning("Progress callback raised: %s", exc)

    # ------------------------------------------------------------------ ingest
    _p("downloading", 5)
    if source_path is None:
        if not source_url:
            raise ValueError("Provide either source_url or source_path")
        ingested = ingest.download_video(source_url, out_dir=work_dir / "src")
        video_path = ingested.path
        title = ingested.title
        duration_meta = ingested.duration
        lang_meta = ingested.language
    else:
        video_path = Path(source_path)
        title = video_path.stem
        duration_meta = clipmod.estimate_duration(video_path)
        lang_meta = None

    # ----------------------------------------------------------- transcribe
    _p("transcribing", 20)
    audio_wav = work_dir / "src" / "audio.wav"
    transcribe.extract_audio(video_path, audio_wav)
    transcript = transcribe.transcribe(audio_wav, language=lang_meta)
    duration_meta = duration_meta or transcript.duration

    # ----------------------------------------------------------- highlight
    _p("detecting_highlights", 40)
    candidates = await hl.detect_highlights(
        transcript, client=client, target_count=target_clip_count
    )
    candidates = candidates[:target_clip_count]
    if not candidates:
        logger.warning("No highlights detected; falling back to first %ds", min(60, int(duration_meta)))
        candidates = [
            HighlightCandidate(
                start=0.0,
                end=min(60.0, max(15.0, duration_meta)),
                score=5.0,
                title=title,
                caption="Auto-generated fallback clip.",
                reason="No highlight candidates returned by the model.",
                hashtags=[],
            )
        ]

    # ----------------------------------------------------------- clip + render
    artifacts: list[ClipArtifact] = []
    total = max(1, len(candidates))
    voice_sample_path: Path | None = None
    if enable_voice_hook:
        try:
            voice_sample_path = voice_hook.extract_voice_sample(
                video_path, work_dir / "voice_sample.wav", start=0.0, duration=8.0
            )
        except Exception as exc:
            logger.warning("Could not extract voice sample for hook: %s", exc)

    for idx, cand in enumerate(candidates):
        stage_pct = 50 + int(45 * idx / total)
        _p(f"clipping_{idx}", stage_pct)
        clip_dir = work_dir / "clips" / f"{idx:02d}"
        raw_clip = clipmod.cut_clip(
            video_path,
            clipmod.CutOptions(
                start=cand.start, end=cand.end, out_path=clip_dir / "raw.mp4"
            ),
        )
        # Subtitle burn
        final = raw_clip
        if enable_subtitles:
            ass = subtitle.write_ass_for_clip(
                transcript,
                out_path=clip_dir / "captions.ass",
                clip_start=cand.start,
                clip_end=cand.end,
            )
            final = subtitle.burn_subtitles(
                raw_clip, ass, clip_dir / "with_subs.mp4"
            )
        # Voice hook
        has_hook = False
        if enable_voice_hook and voice_sample_path is not None:
            try:
                hook_text = await voice_hook.generate_hook_text(
                    client=client,
                    clip_text=" ".join(
                        s.text
                        for s in transcript.segments
                        if s.start <= cand.end and s.end >= cand.start
                    )[:600],
                    title=cand.title,
                    language=transcript.language,
                )
                tts = await client.tts_voice_clone(
                    hook_text, voice_sample_path.read_bytes()
                )
                hook_audio = clip_dir / "hook.wav"
                hook_audio.write_bytes(tts.audio_wav)
                final = voice_hook.prepend_audio_freezeframe(
                    final, hook_audio, clip_dir / "with_hook.mp4"
                )
                has_hook = True
            except Exception as exc:
                logger.warning("Voice hook generation failed for clip %d: %s", idx, exc)

        thumb = clipmod.make_thumbnail(final, clip_dir / "thumb.jpg")
        artifacts.append(
            ClipArtifact(
                candidate=cand,
                raw_clip=raw_clip,
                final_clip=final,
                thumbnail=thumb,
                has_voice_hook=has_hook,
            )
        )

    _p("completed", 100)
    return AutoClipResult(
        source_path=video_path,
        title=title,
        duration=duration_meta,
        language=transcript.language,
        transcript=transcript,
        candidates=candidates,
        clips=artifacts,
    )


def run_auto_clip_sync(**kwargs) -> AutoClipResult:
    """Sync wrapper for use inside RQ worker tasks."""
    return asyncio.run(run_auto_clip(**kwargs))
