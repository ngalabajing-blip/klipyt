"""One-time interactive YouTube login for the cookie-refresher service.

Run this on a workstation (NOT on Railway) to seed the storage state
that the headless refresher will rotate. It opens a real Chromium
window, lets you log in by hand (so 2FA/captcha works), then uploads
both ``storage_state.json`` and the resulting ``cookies.txt`` to object
storage.

Prerequisites:
  - ``S3_*`` env vars pointing at the same bucket Railway uses (R2).
  - ``pip install playwright`` and ``playwright install chromium``.

Usage:
  python -m scripts.setup_youtube_cookies

After the login window opens, log in to YouTube (use a *secondary*
account, not your primary). When the home feed renders, return to the
terminal and press Enter. The script handles the rest.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("setup_youtube_cookies")

LOGIN_URL = "https://accounts.google.com/ServiceLogin?service=youtube"


async def _interactive_login(state_path: Path, cookies_path: Path) -> bool:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "Playwright not installed. Run:\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr,
        )
        return False

    print("Opening Chromium. Log in to YouTube, then return here and press Enter.")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        await page.goto(LOGIN_URL)

        # Block on the operator. ``input`` is sync — wrap so the asyncio
        # loop isn't held; for a one-shot CLI script that's fine.
        await asyncio.get_event_loop().run_in_executor(
            None, input, "After successful login + a YouTube page loads, press Enter to continue: "
        )

        # Sanity-check we have YouTube auth cookies before saving.
        cookies = await context.cookies()
        names = {c.get("name") for c in cookies if "youtube.com" in (c.get("domain") or "")}
        if not (names & {"SID", "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO"}):
            print(
                "Couldn't see any YouTube auth cookies. Make sure you finished login "
                "(home feed visible) before pressing Enter. Aborting.",
                file=sys.stderr,
            )
            await browser.close()
            return False

        await context.storage_state(path=str(state_path))
        from scripts.refresh_youtube_cookies import _playwright_cookies_to_netscape  # noqa: PLC0415

        cookies_path.write_text(_playwright_cookies_to_netscape(cookies), encoding="utf-8")
        await browser.close()

    print(f"Wrote storage state ({state_path.stat().st_size} bytes) and cookies "
          f"({cookies_path.stat().st_size} bytes).")
    return True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        state_path = td / "storage_state.json"
        cookies_path = td / "cookies.txt"

        try:
            ok = asyncio.run(_interactive_login(state_path, cookies_path))
        except KeyboardInterrupt:
            print("\nAborted.", file=sys.stderr)
            return 130

        if not ok:
            return 1

        from app.auth.cookies import save_cookie_file
        from scripts.refresh_youtube_cookies import _upload_state

        save_cookie_file(cookies_path)
        _upload_state(state_path)

    print("Done. The Railway cookie-refresher service will rotate from here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
