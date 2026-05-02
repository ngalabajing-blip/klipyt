"""Refresh the YouTube cookie file by simulating a real browser session.

Designed to run on a Railway scheduled-job service every ~6 hours. Pulls
the current Playwright storage state from object storage, opens a
headless Chromium, browses YouTube long enough to refresh session
tokens, exports cookies in Netscape ``cookies.txt`` format, and writes
the result back to object storage so the backend's ``_get_cookiefile``
picks up the new copy on the next download.

Why Playwright (and not just an httpx GET)?
  - Cookie *expiry* (``Set-Cookie`` headers) is just one piece. YouTube
    also tracks behavioral signals — page dwell time, video playback
    events, click-through patterns — to score whether a session looks
    automated. A real browser navigation gives those signals a healthy
    update; a bare HTTP GET does not.

This script is intentionally fault-tolerant: any failure logs at WARN
and exits 0 so a transient network blip doesn't page on-call. The next
run will retry.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("refresh_youtube_cookies")

# Where Playwright's persisted login state lives. The file is created by
# ``setup_youtube_cookies.py`` (interactive, run once on the operator's
# machine).
STATE_OBJECT_KEY = os.environ.get("YOUTUBE_STATE_KEY", "auth/youtube-storage-state.json")

# Trending feed gives us a populated home that's safe to dwell on without
# touching account-specific endpoints. Subscriptions would also work but
# can 404 on accounts that follow no channels.
TRENDING_URL = "https://www.youtube.com/feed/trending"

# Match yt-dlp's UA so YouTube fingerprints both the same.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _playwright_cookies_to_netscape(cookies: list[dict]) -> str:
    """Convert Playwright cookie dicts to Netscape ``cookies.txt`` format.

    Netscape format columns (tab-separated):
        domain  flag(domain_init)  path  secure  expires  name  value
    """
    lines = ["# Netscape HTTP Cookie File", "# Refreshed by klipyt cookie-refresher", ""]
    for c in cookies:
        domain = c.get("domain") or ""
        # Domains starting with "." apply to subdomains. Playwright already
        # normalises, but the "include subdomains" flag in column 2 must be
        # ``TRUE`` whenever the domain has a leading dot.
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path") or "/"
        secure = "TRUE" if c.get("secure") else "FALSE"
        # Playwright reports ``expires`` as Unix seconds (float). ``-1``
        # means session-only — encode as ``0`` so curl / yt-dlp don't
        # reject the row.
        expires_raw = c.get("expires", -1)
        expires = int(expires_raw) if expires_raw and expires_raw > 0 else 0
        name = c.get("name") or ""
        value = c.get("value") or ""
        lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
    return "\n".join(lines) + "\n"


async def _refresh_once(state_path: Path, output_path: Path) -> bool:
    """Open YouTube in headless Chromium, dwell briefly, export cookies.

    Returns True if a usable cookie file was written to ``output_path``.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "playwright not installed. Run: pip install playwright && "
            "playwright install --with-deps chromium"
        )
        return False

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                # Reduce memory pressure on the Railway 512 MB plan.
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ],
        )
        try:
            context = await browser.new_context(
                storage_state=str(state_path) if state_path.exists() else None,
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720},
            )
            page = await context.new_page()
            try:
                await page.goto(TRENDING_URL, wait_until="domcontentloaded", timeout=45_000)
                # Dwell. YouTube fires several background xhrs for trust
                # signals + session refresh during the first ~15s after
                # initial paint.
                await page.wait_for_timeout(15_000)
                # Scroll once to fire scroll telemetry.
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(5_000)
            except Exception as exc:
                logger.warning("Page navigation hit an error (continuing to export): %s", exc)

            cookies = await context.cookies()
            netscape = _playwright_cookies_to_netscape(cookies)
            output_path.write_text(netscape, encoding="utf-8")

            # Save the freshly-rotated storage state too so the next run
            # picks up any session changes (CSRF tokens, etc.).
            await context.storage_state(path=str(state_path))
        finally:
            await browser.close()

    sanity = "youtube.com" in netscape and len(netscape) > 200
    if not sanity:
        logger.warning("Exported cookies look empty/invalid: %d bytes", len(netscape))
    return sanity


def _download_state(dest: Path) -> bool:
    try:
        from app.storage.s3 import get_storage as get_s3
        store = get_s3()
        store.download_to(STATE_OBJECT_KEY, dest)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as exc:
        logger.info("No prior storage state at %s: %s", STATE_OBJECT_KEY, exc)
        return False


def _upload_state(src: Path) -> None:
    from app.storage.s3 import get_storage as get_s3
    store = get_s3()
    store.upload_file(src, STATE_OBJECT_KEY, content_type="application/json")
    logger.info("Storage state uploaded -> %s", STATE_OBJECT_KEY)


def main() -> int:
    _setup_logging()
    logger.info("Starting YouTube cookie refresh")

    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        state_path = td / "storage_state.json"
        cookies_path = td / "cookies.txt"

        had_state = _download_state(state_path)
        if not had_state:
            logger.error(
                "No storage_state.json in object storage at %s. "
                "Run scripts/setup_youtube_cookies.py once on a workstation "
                "to seed it.",
                STATE_OBJECT_KEY,
            )
            return 0  # exit 0 so cron doesn't page until seeded

        try:
            ok = asyncio.run(_refresh_once(state_path, cookies_path))
        except Exception:
            logger.exception("Cookie refresh raised")
            return 0

        if not ok:
            logger.warning("Refresh produced an empty/invalid cookie file; skipping upload")
            return 0

        from app.auth.cookies import save_cookie_file

        try:
            save_cookie_file(cookies_path)
            _upload_state(state_path)
        except Exception:
            logger.exception("Failed to upload refreshed cookies")
            return 0

    logger.info("YouTube cookie refresh complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
