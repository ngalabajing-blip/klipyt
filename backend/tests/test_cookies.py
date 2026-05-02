"""Tests for the YouTube cookie auth helpers + refresher utilities."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from app.auth import cookies as cookies_mod
from scripts.refresh_youtube_cookies import _playwright_cookies_to_netscape


@pytest.fixture(autouse=True)
def _clear_state(monkeypatch):
    """Cookie module caches a path globally; reset before every test."""
    cookies_mod._invalidate_cache()
    monkeypatch.delenv("YOUTUBE_COOKIES", raising=False)
    yield
    cookies_mod._invalidate_cache()


def test_get_cookie_file_returns_none_when_unconfigured():
    assert cookies_mod.get_cookie_file() is None


def test_get_cookie_file_falls_back_to_env_var(monkeypatch):
    raw = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\txyz\n"
    monkeypatch.setenv("YOUTUBE_COOKIES", base64.b64encode(raw).decode())

    path = cookies_mod.get_cookie_file()

    assert path is not None
    assert Path(path).read_bytes() == raw


def test_get_cookie_file_caches_within_ttl(monkeypatch):
    raw = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n"
    monkeypatch.setenv("YOUTUBE_COOKIES", base64.b64encode(raw).decode())

    first = cookies_mod.get_cookie_file()
    # Different env var value, but cache should keep returning the same path
    monkeypatch.setenv("YOUTUBE_COOKIES", base64.b64encode(b"changed").decode())
    second = cookies_mod.get_cookie_file()

    assert first == second


def test_get_cookie_file_handles_garbage_base64(monkeypatch):
    monkeypatch.setenv("YOUTUBE_COOKIES", "not-actually-base64!!@@##")
    assert cookies_mod.get_cookie_file() is None


def test_netscape_export_basic_shape():
    cookies = [
        {
            "name": "SID",
            "value": "g.a000xyz",
            "domain": ".youtube.com",
            "path": "/",
            "secure": True,
            "expires": 1798765432.0,
        },
        {
            # session-only cookie => expires column should be 0
            "name": "PLAY_TOKEN",
            "value": "abc",
            "domain": "www.youtube.com",
            "path": "/",
            "secure": False,
            "expires": -1,
        },
    ]

    out = _playwright_cookies_to_netscape(cookies)

    assert out.startswith("# Netscape HTTP Cookie File")
    # Subdomain-style domains use TRUE in column 2 ("include subdomains")
    assert ".youtube.com\tTRUE\t/\tTRUE\t1798765432\tSID\tg.a000xyz" in out
    # Host-only domains use FALSE
    assert "www.youtube.com\tFALSE\t/\tFALSE\t0\tPLAY_TOKEN\tabc" in out


def test_netscape_export_empty_cookies():
    out = _playwright_cookies_to_netscape([])
    assert out.startswith("# Netscape HTTP Cookie File")
    # Header + blank separator + final newline; no cookie rows.
    assert "youtube.com" not in out
