"""Transcribe the video audio with faster-whisper, returning word-level timestamps."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(slots=True)
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass(slots=True)
class Transcript:
    language: str
    duration: float
    segments: list[Segment]

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments).strip()

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "duration": self.duration,
            "segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "words": [{"text": w.text, "start": w.start, "end": w.end} for w in s.words],
                }
                for s in self.segments
            ],
        }


def extract_audio(video_path: str | Path, out_path: str | Path) -> Path:
    """Strip audio to mono 16 kHz WAV — what whisper-style models expect."""
    video_path = Path(video_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def transcribe(
    audio_path: str | Path,
    *,
    language: str | None = None,
    beam_size: int = 1,
) -> Transcript:
    """Run faster-whisper and return a :class:`Transcript`."""
    from faster_whisper import WhisperModel  # imported lazily — heavy import

    audio_path = Path(audio_path)
    model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=beam_size,
        word_timestamps=True,
        vad_filter=True,
    )
    segments: list[Segment] = []
    for seg in segments_iter:
        words = [
            Word(text=w.word.strip(), start=float(w.start), end=float(w.end))
            for w in (seg.words or [])
            if w.start is not None and w.end is not None
        ]
        segments.append(
            Segment(
                start=float(seg.start),
                end=float(seg.end),
                text=seg.text.strip(),
                words=words,
            )
        )
    return Transcript(
        language=info.language,
        duration=float(info.duration or 0.0),
        segments=segments,
    )
