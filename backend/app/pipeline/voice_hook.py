"""Generate a 3-second AI voice hook in the speaker's own voice and prepend to a clip.

Pipeline:

1. Take a 5-10s sample of the speaker's voice from the source video.
2. Ask MiMo V2.5-Pro to write a punchy hook based on the clip's transcript / title.
3. Send (hook_text, voice_sample) to ``mimo-v2.5-tts-voiceclone``.
4. Concatenate the hook audio + a still frame (or freeze frame) in front of the clip.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.mimo.client import MiMoClient
from app.mimo.types import ChatMessage

logger = logging.getLogger(__name__)


HOOK_PROMPT = """You are a viral short-form copywriter.\nWrite ONE single-sentence hook (8-15 words) for the clip below.\nThe hook must create curiosity or tension and lead naturally INTO the clip's first sentence.\nWrite it in the same language as the transcript.\nReply with ONLY the hook sentence — no quotes, no preamble."""


def extract_voice_sample(
    video_path: str | Path,
    out_path: str | Path,
    *,
    start: float,
    duration: float = 8.0,
) -> Path:
    """Extract a clean WAV voice sample for cloning."""
    video_path = Path(video_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{duration:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-acodec",
            "pcm_s16le",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path


async def generate_hook_text(
    *,
    client: MiMoClient,
    clip_text: str,
    title: str,
    language: str | None,
) -> str:
    """Ask MiMo V2.5-Pro for a punchy hook sentence."""
    user = (
        f"Clip title: {title}\n"
        f"Language: {language or 'auto'}\n"
        f"Opening transcript: {clip_text[:600]}"
    )
    response = await client.chat(
        [
            ChatMessage(role="system", content=HOOK_PROMPT),
            ChatMessage(role="user", content=user),
        ],
        model=client.cfg.mimo_model_pro,
        max_tokens=128,
        temperature=0.85,
    )
    text = (response.text or "").strip().strip('"').strip()
    return text or title


def prepend_audio_freezeframe(
    clip_video: str | Path,
    hook_audio: str | Path,
    out_path: str | Path,
    *,
    freeze_seconds: float = 2.5,
) -> Path:
    """Build a tiny freeze-frame intro from ``clip_video[0]`` + ``hook_audio`` and concat.

    Uses the first frame of the clip as a still backdrop, overlays the hook
    audio, then concatenates (hook | clip) with stream copy.
    """
    clip_video = Path(clip_video)
    hook_audio = Path(hook_audio)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = out_path.parent / f".hook_{out_path.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)

    intro_path = work_dir / "intro.mp4"
    # 1) Build the intro: still frame loop at 30 fps with hook audio.
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(clip_video),
            "-i",
            str(hook_audio),
            "-t",
            f"{freeze_seconds:.3f}",
            "-vf",
            "select=eq(n\\,0),scale=1080:1920:flags=lanczos,setsar=1,fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            str(intro_path),
        ],
        check=True,
        capture_output=True,
    )

    # 2) Concat intro + clip via the concat demuxer (re-encode to keep timestamps clean).
    list_file = work_dir / "concat.txt"
    list_file.write_text(
        f"file '{intro_path.resolve()}'\nfile '{clip_video.resolve()}'\n", encoding="utf-8"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path
