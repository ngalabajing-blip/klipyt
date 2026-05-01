"""Highlight detection — find the most viral-worthy clips in a long video.

Strategy:

1. **Pass 1 (V2.5-Pro on transcript):** read the full transcript with timestamps and
   ask MiMo to score every potential clip on a 0–10 viral-potential scale, pick the
   top-K windows, and generate platform-ready titles/captions/hashtags.
2. **Pass 2 (V2-Omni on each candidate):** sample a few frames per candidate clip
   and let the multimodal model adjust the score / refine the title with visual cues
   (facial expression, on-screen text, etc.).

Output: a list of :class:`HighlightCandidate` ordered by descending score.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from app.mimo.client import MiMoClient
from app.mimo.types import ChatMessage, HighlightCandidate
from app.pipeline.transcribe import Transcript

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert short-form video editor for TikTok, Reels, and YouTube Shorts. \
You read transcripts of long-form content and extract the most viral-worthy 30-90 second clips.

Selection rules:
- Each clip must contain a complete idea, story beat, or quotable insight.
- Prefer hooks: contradictions, surprising claims, emotional peaks, list openings ("there are 3 reasons..."), or strong opinions.
- Avoid filler, repeated greetings, or off-topic tangents.
- Target duration: 30-75 seconds. Never below 15 or above 90 seconds.
- Return between 5 and 12 clips ordered by descending score.

For each clip you MUST return:
- start, end: seconds (float). Must align to nearby word boundaries from the transcript.
- score: 0-10 viral potential.
- title: <= 80 chars, hook-style, ALL-CAPS for the punch words.
- caption: 1-2 sentences for the post.
- reason: <= 140 chars why this clip works.
- hashtags: 3-7 relevant tags WITHOUT the leading #.

Respond ONLY with a JSON object: {"clips": [...]}"""


def _format_transcript(transcript: Transcript, max_chars: int = 60_000) -> str:
    """Render the transcript as ``[mm:ss] text`` lines for the LLM."""
    lines: list[str] = []
    used = 0
    for seg in transcript.segments:
        m, s = divmod(int(seg.start), 60)
        h, m = divmod(m, 60)
        ts = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        line = f"[{ts}] {seg.text}"
        if used + len(line) > max_chars:
            lines.append("[...transcript truncated...]")
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def _parse_json_block(text: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    return json.loads(text[start : end + 1])


def _snap_to_word_boundaries(
    transcript: Transcript, start: float, end: float
) -> tuple[float, float]:
    """Move boundaries to the nearest word so we don't cut mid-syllable."""
    all_words = [w for s in transcript.segments for w in s.words]
    if not all_words:
        return start, end
    snap_start = min(all_words, key=lambda w: abs(w.start - start)).start
    snap_end = min(all_words, key=lambda w: abs(w.end - end)).end
    if snap_end - snap_start < 8.0:  # too short, fall back
        return start, end
    return float(snap_start), float(snap_end)


async def detect_highlights(
    transcript: Transcript,
    *,
    client: MiMoClient,
    target_count: int = 8,
    min_duration: float = 15.0,
    max_duration: float = 90.0,
) -> list[HighlightCandidate]:
    """Run pass 1 of highlight detection (transcript-only) using MiMo V2.5-Pro."""
    if not transcript.segments:
        return []

    user_prompt = (
        f"Transcript language: {transcript.language}.\n"
        f"Total duration: {transcript.duration:.1f} seconds.\n"
        f"Aim to return {target_count} clips. Each between {min_duration:.0f}s and {max_duration:.0f}s.\n\n"
        f"Transcript:\n{_format_transcript(transcript)}"
    )
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]
    response = await client.chat(
        messages,
        model=client.cfg.mimo_model_pro,
        max_tokens=4096,
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    data = _parse_json_block(response.text or "{}")
    clips_raw = data.get("clips") or data.get("highlights") or []

    candidates: list[HighlightCandidate] = []
    for raw in clips_raw:
        try:
            start = float(raw["start"])
            end = float(raw["end"])
        except (KeyError, ValueError, TypeError):
            continue
        if end - start < min_duration or end - start > max_duration:
            continue
        start, end = _snap_to_word_boundaries(transcript, start, end)
        try:
            candidates.append(
                HighlightCandidate(
                    start=start,
                    end=end,
                    score=float(raw.get("score", 5.0)),
                    title=str(raw.get("title", "Untitled clip"))[:200],
                    caption=str(raw.get("caption", ""))[:1024],
                    reason=str(raw.get("reason", ""))[:300],
                    hashtags=[str(h).lstrip("#") for h in raw.get("hashtags", [])][:8],
                )
            )
        except Exception as exc:
            logger.warning("Skipping malformed highlight candidate: %s (%s)", raw, exc)

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def sample_frames(
    video_path: str | Path,
    *,
    start: float,
    end: float,
    out_dir: str | Path,
    n: int = 4,
) -> list[Path]:
    """Sample ``n`` frames evenly between ``start`` and ``end`` for omni re-scoring."""
    video_path = Path(video_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = max(0.1, end - start)
    paths: list[Path] = []
    for i in range(n):
        t = start + duration * (i + 0.5) / n
        out = out_dir / f"frame_{int(t * 1000):08d}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            paths.append(out)
        except subprocess.CalledProcessError as exc:
            logger.warning("Failed to sample frame at %.2fs: %s", t, exc)
    return paths


async def refine_with_omni(
    candidate: HighlightCandidate,
    *,
    video_path: str | Path,
    client: MiMoClient,
) -> HighlightCandidate:
    """Re-score and improve a candidate's title using visual frames via Omni."""
    from app.pipeline.highlight import sample_frames as _sample  # self-import for testability

    frames = _sample(video_path, start=candidate.start, end=candidate.end, out_dir="/tmp/mager_frames", n=3)
    if not frames:
        return candidate
    image_part = {
        "type": "image_url",
        "image_url": {"url": client._data_url(frames[0].read_bytes(), "image/jpeg")},
    }
    prompt = (
        "Look at this still from a candidate viral clip. "
        f"The current title is: \"{candidate.title}\". "
        "Suggest an improved title (<= 80 chars, hook-style) and rate the visual viral potential 0-10. "
        'Reply as JSON: {"title": "...", "visual_score": <0-10>}'
    )
    messages = [
        {"role": "user", "content": [{"type": "text", "text": prompt}, image_part]}
    ]
    try:
        resp = await client.chat(messages, model=client.cfg.mimo_model_omni, max_tokens=256)
        data = _parse_json_block(resp.text or "{}")
        new_title = str(data.get("title", candidate.title)).strip()[:200] or candidate.title
        visual_score = float(data.get("visual_score", candidate.score))
        candidate.title = new_title
        candidate.score = (candidate.score + visual_score) / 2.0
    except Exception as exc:
        logger.warning("Omni refinement failed for %s: %s", candidate.title, exc)
    return candidate
