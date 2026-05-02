"""Tests for the WebVTT caption parser."""

from __future__ import annotations

from pathlib import Path

from app.pipeline.captions import find_subtitles_for, parse_vtt

VTT_SAMPLE = """WEBVTT
Kind: captions
Language: en

00:00:00.500 --> 00:00:03.000
Hello and welcome to the show

00:00:03.000 --> 00:00:07.250
Today we're talking about three reasons<00:00:05.500><c> people fail</c>

00:00:08.000 --> 00:00:12.500
The first reason is procrastination
"""

# YouTube auto-captions repeat lines as new words roll in — the parser should
# collapse rolling extensions into a single cue, and skip transition cues
# (< 0.5s) entirely.
VTT_ROLLING = """WEBVTT

00:00:00.000 --> 00:00:01.000
hello world

00:00:01.000 --> 00:00:01.100
hello world

00:00:01.100 --> 00:00:03.000
hello world today
"""


def test_parse_vtt_basic(tmp_path: Path) -> None:
    p = tmp_path / "video.en.vtt"
    p.write_text(VTT_SAMPLE)
    t = parse_vtt(p)
    assert t is not None
    assert t.language == "en"
    assert len(t.segments) == 3
    assert t.segments[0].start == 0.5
    assert t.segments[0].end == 3.0
    assert t.segments[0].text == "Hello and welcome to the show"
    # Inline tags should be stripped.
    assert "<" not in t.segments[1].text
    assert "people fail" in t.segments[1].text
    assert t.duration == 12.5


def test_parse_vtt_dedupes_rolling_captions(tmp_path: Path) -> None:
    p = tmp_path / "video.en.vtt"
    p.write_text(VTT_ROLLING)
    t = parse_vtt(p)
    assert t is not None
    # Rolling cues collapse into the longest version, transition cue (< 0.5s)
    # is skipped entirely.
    texts = [s.text for s in t.segments]
    assert texts == ["hello world today"]
    # The collapsed cue should span from the original start to the latest end.
    assert t.segments[0].start == 0.0
    assert t.segments[0].end == 3.0


def test_parse_vtt_empty_file_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "empty.en.vtt"
    p.write_text("WEBVTT\n\n")
    assert parse_vtt(p) is None


def test_find_subtitles_prefers_english(tmp_path: Path) -> None:
    video = tmp_path / "abc123.mp4"
    video.touch()
    (tmp_path / "abc123.id.vtt").write_text(VTT_SAMPLE)
    (tmp_path / "abc123.en.vtt").write_text(VTT_SAMPLE)
    (tmp_path / "abc123.fr.vtt").write_text(VTT_SAMPLE)
    found = find_subtitles_for(video)
    assert found is not None
    assert found.name == "abc123.en.vtt"


def test_find_subtitles_returns_none_when_missing(tmp_path: Path) -> None:
    video = tmp_path / "abc123.mp4"
    video.touch()
    assert find_subtitles_for(video) is None
