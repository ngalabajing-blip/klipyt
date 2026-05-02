"""WebVTT caption parser → :class:`Transcript`.

Used as a *zero-memory* alternative to running Whisper locally on Railway's
512 MB worker.  yt-dlp is asked to also pull YouTube's auto-generated captions
(``--write-auto-subs --sub-langs en,id``) at download time; we then parse the
``.vtt`` and feed the resulting :class:`Transcript` to the existing
MiMo-driven highlight pipeline.

Word-level timing isn't available in YouTube's VTT — only segment-level (one
caption cue ≈ one segment).  ``Transcript.words`` is left empty; the highlight
pipeline already tolerates that and just skips the word-snap step.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.pipeline.transcribe import Segment, Transcript

logger = logging.getLogger(__name__)


_TIMESTAMP_RE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})(?:[.,](?P<ms>\d{1,3}))?"
)
_CUE_HEADER_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s+-->\s+(?P<end>\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})"
)
_TAG_RE = re.compile(r"<[^>]+>")


def _parse_ts(s: str) -> float:
    m = _TIMESTAMP_RE.match(s)
    if not m:
        return 0.0
    h = int(m.group("h"))
    mm = int(m.group("m"))
    ss = int(m.group("s"))
    ms = int((m.group("ms") or "0").ljust(3, "0")[:3])
    return h * 3600 + mm * 60 + ss + ms / 1000.0


def _strip(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def parse_vtt(path: str | Path) -> Transcript | None:
    """Parse a WebVTT file and return a :class:`Transcript`.

    Returns ``None`` if the file is empty / contains no cues — caller should
    treat that as "no captions available" and fall back to the even-split
    strategy.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Failed to read VTT %s: %s", path, exc)
        return None

    raw_cues: list[tuple[float, float, str]] = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = _CUE_HEADER_RE.match(line)
        if not m:
            i += 1
            continue
        start = _parse_ts(m.group("start"))
        end = _parse_ts(m.group("end"))
        i += 1
        text_parts: list[str] = []
        while i < len(lines) and lines[i].strip():
            text_parts.append(_strip(lines[i]))
            i += 1
        text = " ".join(t for t in text_parts if t).strip()
        if not text:
            continue
        if end <= start:
            end = start + 0.1
        raw_cues.append((start, end, text))

    # YouTube auto-captions are usually emitted as a "roll-up": each cue
    # contains the prior cue's text plus a few new words.  Two patterns:
    #
    #   1. Short transition cue (< 0.5s) then full cue — the short one is a
    #      duplicate of the previous one's tail and adds no information.
    #   2. Adjacent cues where the next cue's text *starts with* the previous
    #      cue's text — keep only the longer one.
    #
    # We collapse both into a single forward pass that keeps the *latest*
    # full version of each rolling group.
    segments: list[Segment] = []
    for start, end, text in raw_cues:
        if end - start < 0.5:
            continue
        if segments:
            prev = segments[-1]
            # If this cue's text starts with the previous cue's text, replace
            # the previous cue (it's the rolled-up extension).
            if text.startswith(prev.text):
                prev.end = end
                prev.text = text
                continue
            # If this cue's text is wholly contained in the previous one, drop.
            if text in prev.text:
                continue
        segments.append(Segment(start=start, end=end, text=text, words=[]))

    if not segments:
        return None

    duration = max(s.end for s in segments)
    # Cheap language guess from filename: foo.en.vtt → en, foo.id.vtt → id,
    # foo.en-orig.vtt → en, foo.en-de-DE.vtt → en (translated to German but
    # source language is what matters for the LLM).
    lang = "und"
    name_parts = path.stem.split(".")
    if len(name_parts) >= 2:
        suffix = name_parts[-1].lower()
        # Take the leading 2-letter ISO code if possible.
        if "-" in suffix:
            lang = suffix.split("-", 1)[0]
        elif 2 <= len(suffix) <= 5:
            lang = suffix
    return Transcript(language=lang, duration=duration, segments=segments)


def find_subtitles_for(video_path: str | Path) -> Path | None:
    """Return the best available ``.vtt`` next to ``video_path``.

    yt-dlp writes captions as ``<video-stem>.<lang>.vtt``.  We prefer the
    original-language track of the video over auto-translations:

    * ``.en.vtt`` / ``.id.vtt`` — original captions
    * ``.en-orig.vtt`` / ``.id-orig.vtt`` — original captions with timing
    * any ``.en-*.vtt`` / ``.id-*.vtt`` — last resort, may be a machine
      translation INTO some language but still has the source timestamps.
    """
    video_path = Path(video_path)
    candidates = sorted(video_path.parent.glob(f"{video_path.stem}.*.vtt"))
    if not candidates:
        return None

    def _rank(p: Path) -> tuple[int, str]:
        # Suffix between the video stem and ``.vtt``.
        lang = p.stem[len(video_path.stem) + 1 :].lower()
        if lang in ("en",):
            return (0, lang)
        if lang in ("id",):
            return (1, lang)
        if lang in ("en-orig", "en-en"):
            return (2, lang)
        if lang in ("id-orig", "id-id"):
            return (3, lang)
        if lang.startswith("en"):
            return (4, lang)
        if lang.startswith("id"):
            return (5, lang)
        return (6, lang)

    candidates.sort(key=_rank)
    return candidates[0]
