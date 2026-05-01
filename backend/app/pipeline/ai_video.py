"""AI video generators: Educational, History, Satisfying, Short Movie, Character.

For the MVP these all share the same architecture:

1. Generate a short script with **MiMo V2.5-Pro** (specialised system prompt per kind).
2. Synthesise narration with **MiMo TTS** (regular or voice-design).
3. Build a sequence of background images (placeholder for image-gen integration)
   and concatenate with the narration.

This module returns a final mp4. Image generation is currently a stub that draws
the script line on a coloured background — wire up your preferred image-gen API
(Flux, Stable Diffusion, etc.) inside ``render_visuals`` to upgrade.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from app.mimo.client import MiMoClient
from app.mimo.types import ChatMessage

logger = logging.getLogger(__name__)


AIVideoKind = Literal["educational", "history", "satisfying", "short_movie", "character"]


SYSTEM_PROMPTS: dict[AIVideoKind, str] = {
    "educational": (
        "You write 60-90 second educational explainer scripts for vertical short-form video. "
        "Open with a strong hook question, give 3-5 punchy beats, end with a memorable takeaway. "
        "Each beat is a single short sentence (<= 18 words)."
    ),
    "history": (
        "You write 60-90 second history retellings for vertical short-form video. "
        "Use vivid imagery, a tense narrative arc, and surprising facts. "
        "Each beat is a single short sentence (<= 18 words)."
    ),
    "satisfying": (
        "You write 30-60 second 'oddly satisfying' narration scripts. "
        "Soft observations about precise, repetitive, or aesthetic processes. "
        "Each beat is a single short sentence (<= 16 words)."
    ),
    "short_movie": (
        "You write 60-90 second cinematic short-movie scripts. "
        "Three-act mini-arc: setup, twist, payoff. Use sensory details. "
        "Each beat is a single short sentence (<= 18 words)."
    ),
    "character": (
        "You write 60-90 second character monologues from a unique persona. "
        "Speak in first person, distinctive voice, end on a hook. "
        "Each beat is a single short sentence (<= 18 words)."
    ),
}


@dataclass(slots=True)
class GeneratedScript:
    title: str
    beats: list[str] = field(default_factory=list)
    voice_description: str = ""

    @property
    def text(self) -> str:
        return " ".join(self.beats).strip()


async def generate_script(
    *,
    client: MiMoClient,
    kind: AIVideoKind,
    prompt: str,
    language: str = "en",
) -> GeneratedScript:
    """Ask MiMo V2.5-Pro for a JSON-structured script in ``language``."""
    system = (
        SYSTEM_PROMPTS[kind]
        + f"\nWrite the script in language: {language}.\n"
        "Return JSON: {\"title\": str, \"beats\": [str, ...], \"voice_description\": str}."
        " The voice_description should specify gender, age, mood, and pacing."
    )
    response = await client.chat(
        [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=prompt),
        ],
        model=client.cfg.mimo_model_pro,
        max_tokens=1024,
        temperature=0.85,
        response_format={"type": "json_object"},
    )
    import json
    import re

    text = (response.text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError:
        data = {"title": prompt[:80], "beats": [prompt], "voice_description": "neutral"}
    return GeneratedScript(
        title=str(data.get("title", prompt[:80])),
        beats=[str(b) for b in (data.get("beats") or []) if str(b).strip()],
        voice_description=str(data.get("voice_description", "neutral, calm")),
    )


def _draw_text_card(text: str, out_path: Path, *, size=(1080, 1920), bg=(15, 15, 24)) -> Path:
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64
        )
    except OSError:
        font = ImageFont.load_default()
    margin = 80
    max_w = size[0] - 2 * margin
    # Naive word wrap
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if (bbox[2] - bbox[0]) > max_w and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    y = (size[1] - len(lines) * 80) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (size[0] - w) // 2
        draw.text(
            (x, y),
            line,
            fill=(255, 255, 255),
            font=font,
            stroke_width=4,
            stroke_fill=(0, 0, 0),
        )
        y += 80
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=92)
    return out_path


def render_visuals(beats: list[str], out_dir: Path) -> list[Path]:
    """Render one background image per beat (placeholder — wire image gen here)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, beat in enumerate(beats):
        path = out_dir / f"beat_{i:03d}.jpg"
        _draw_text_card(beat, path)
        paths.append(path)
    return paths


def assemble_video(
    image_paths: list[Path],
    audio_path: Path,
    out_path: Path,
    *,
    audio_duration: float,
) -> Path:
    """Stitch images + audio into a final 1080x1920 mp4 with even pacing."""
    if not image_paths:
        raise ValueError("Need at least one image")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = out_path.parent / f".aivid_{out_path.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)

    per_image = max(1.5, audio_duration / len(image_paths))
    list_file = work_dir / "concat.txt"
    with list_file.open("w", encoding="utf-8") as fp:
        for img in image_paths:
            fp.write(f"file '{img.resolve()}'\nduration {per_image:.3f}\n")
        fp.write(f"file '{image_paths[-1].resolve()}'\n")

    silent_video = work_dir / "silent.mp4"
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
            "-vsync",
            "vfr",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=1080:1920:flags=lanczos,setsar=1,fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            str(silent_video),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path
