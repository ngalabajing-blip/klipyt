"""Multi-language dubbing — translate the transcript and re-voice with VoiceClone.

Workflow:
1. Translate transcript text → target language with MiMo V2.5-Pro.
2. Extract a voice sample from the source.
3. Synthesise the translated text with ``mimo-v2.5-tts-voiceclone``.
4. Replace the original audio track on the clip and re-mux.

Note: lip-sync is NOT performed in this MVP. Future iteration can use Wav2Lip.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.mimo.client import MiMoClient
from app.mimo.types import ChatMessage

logger = logging.getLogger(__name__)


TRANSLATION_PROMPT = """You translate transcripts for short-form video dubbing.

Rules:
- Translate to {target_language}.
- Preserve the speaker's voice, tone, and informal register.
- The translated text should take roughly the SAME time to speak as the source.
- Return ONLY the translated text — no commentary, no quotes, no labels.
"""


async def translate(
    text: str,
    *,
    target_language: str,
    client: MiMoClient,
) -> str:
    """Translate ``text`` into ``target_language`` using V2.5-Pro."""
    response = await client.chat(
        [
            ChatMessage(role="system", content=TRANSLATION_PROMPT.format(target_language=target_language)),
            ChatMessage(role="user", content=text),
        ],
        model=client.cfg.mimo_model_pro,
        max_tokens=2048,
        temperature=0.5,
    )
    return (response.text or "").strip()


def replace_audio(
    video_path: str | Path,
    audio_wav: str | Path,
    out_path: str | Path,
) -> Path:
    """Replace the audio track of ``video_path`` with ``audio_wav``."""
    video_path = Path(video_path)
    audio_wav = Path(audio_wav)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_wav),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path
