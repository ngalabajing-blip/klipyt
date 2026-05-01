"""Subtitle ASS generation should produce a valid header + dialogue lines."""

from app.pipeline.subtitle import SubtitleStyle, _build_ass
from app.pipeline.transcribe import Segment, Transcript, Word


def _sample_transcript() -> Transcript:
    words = [
        Word(text="Hello", start=0.0, end=0.4),
        Word(text="world", start=0.4, end=0.8),
        Word(text="this", start=0.8, end=1.0),
        Word(text="is", start=1.0, end=1.1),
        Word(text="MiMo", start=1.1, end=1.5),
    ]
    seg = Segment(start=0.0, end=1.5, text="Hello world this is MiMo", words=words)
    return Transcript(language="en", duration=1.5, segments=[seg])


def test_build_ass_emits_header_and_dialogue():
    transcript = _sample_transcript()
    ass = _build_ass(transcript, SubtitleStyle())
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass
    assert "Dialogue:" in ass
    # Karaoke tag should appear for at least one word.
    assert "\\kf" in ass


def test_build_ass_handles_empty_transcript():
    transcript = Transcript(language="en", duration=0.0, segments=[])
    ass = _build_ass(transcript, SubtitleStyle())
    assert "Dialogue:" not in ass
    assert "[V4+ Styles]" in ass
