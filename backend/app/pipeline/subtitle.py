"""Karaoke-style subtitle rendering via ffmpeg + ASS (Advanced SubStation Alpha)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.pipeline.transcribe import Transcript, Word

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SubtitleStyle:
    font_name: str = "Inter"
    font_size: int = 64
    primary_color: str = "&H00FFFFFF"   # white
    secondary_color: str = "&H00FFFF00" # yellow highlight (per-word karaoke)
    outline_color: str = "&H00000000"   # black outline
    back_color: str = "&H80000000"      # semi-transparent box
    outline: int = 4
    shadow: int = 0
    bold: int = -1                       # -1 = true in ASS
    margin_v: int = 220                  # distance from bottom
    align: int = 2                       # bottom-centre
    max_words_per_line: int = 4
    line_max_chars: int = 26


def _format_time(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _chunk_words(words: list[Word], style: SubtitleStyle) -> list[list[Word]]:
    """Group words into short subtitle phrases (max ``max_words_per_line``)."""
    chunks: list[list[Word]] = []
    current: list[Word] = []
    current_len = 0
    for w in words:
        text = w.text
        if (
            len(current) >= style.max_words_per_line
            or current_len + len(text) > style.line_max_chars
        ):
            if current:
                chunks.append(current)
            current = [w]
            current_len = len(text)
        else:
            current.append(w)
            current_len += len(text) + 1
    if current:
        chunks.append(current)
    return chunks


def _build_ass(transcript: Transcript, style: SubtitleStyle, *, time_offset: float = 0.0) -> str:
    """Render an ASS subtitle string with karaoke-style per-word colour transitions."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font_name},{style.font_size},{style.primary_color},{style.secondary_color},{style.outline_color},{style.back_color},{style.bold},0,0,0,100,100,0,0,1,{style.outline},{style.shadow},{style.align},80,80,{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    all_words: list[Word] = []
    for seg in transcript.segments:
        all_words.extend(seg.words)
    if not all_words:
        return header

    # Apply time offset (e.g., we cropped the video to start at clip.start).
    shifted = [
        Word(
            text=w.text,
            start=max(0.0, w.start - time_offset),
            end=max(0.0, w.end - time_offset),
        )
        for w in all_words
    ]
    chunks = _chunk_words(shifted, style)
    for chunk in chunks:
        if not chunk:
            continue
        start = chunk[0].start
        end = chunk[-1].end
        # Build karaoke text: each word becomes "{\kf<centiseconds>}word "
        # The \kf tag fills the highlight colour over the word's duration.
        parts: list[str] = []
        for w in chunk:
            cs = max(1, int(round((w.end - w.start) * 100)))
            text = w.text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
            parts.append(f"{{\\kf{cs}}}{text} ")
        line = "".join(parts).strip()
        events.append(
            f"Dialogue: 0,{_format_time(start)},{_format_time(end)},Default,,0,0,0,,{line}"
        )
    return header + "\n".join(events) + "\n"


def write_ass_for_clip(
    transcript: Transcript,
    *,
    out_path: str | Path,
    clip_start: float,
    clip_end: float,
    style: SubtitleStyle | None = None,
) -> Path:
    """Write an ``.ass`` subtitle file aligned to a clip starting at ``clip_start``."""
    style = style or SubtitleStyle()
    # Filter words to those overlapping the clip window, then offset.
    filtered_segments = []
    for seg in transcript.segments:
        words_in = [
            w for w in seg.words if w.end >= clip_start and w.start <= clip_end
        ]
        if words_in:
            filtered_segments.append(
                type(seg)(start=seg.start, end=seg.end, text=seg.text, words=words_in)
            )
    sub_transcript = Transcript(
        language=transcript.language, duration=clip_end - clip_start, segments=filtered_segments
    )
    ass = _build_ass(sub_transcript, style, time_offset=clip_start)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(ass, encoding="utf-8")
    return out_path


def burn_subtitles(
    video_path: str | Path, ass_path: str | Path, out_path: str | Path
) -> Path:
    """Burn an ``.ass`` file into ``video_path`` using ffmpeg's subtitle filter."""
    video_path = Path(video_path)
    ass_path = Path(ass_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # ffmpeg filter syntax requires escaping colons & backslashes inside the path.
    safe = str(ass_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"ass='{safe}'",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    logger.info("ffmpeg burn_subtitles: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path
