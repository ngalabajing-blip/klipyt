"""Highlight JSON-block parsing should be tolerant to fenced / unfenced output."""

import json

import pytest

from app.pipeline.highlight import _parse_json_block


def test_parse_plain_json():
    text = '{"clips": [{"start": 1, "end": 2}]}'
    assert _parse_json_block(text)["clips"][0]["start"] == 1


def test_parse_fenced_json():
    text = """```json
    {"clips": [{"start": 5, "end": 6, "title": "ok"}]}
    ```"""
    parsed = _parse_json_block(text)
    assert parsed["clips"][0]["title"] == "ok"


def test_parse_with_preamble():
    text = "Here is the result:\n{\"clips\": []}\nThanks!"
    assert _parse_json_block(text) == {"clips": []}


def test_parse_invalid_raises():
    with pytest.raises((ValueError, json.JSONDecodeError)):
        _parse_json_block("no json here")
