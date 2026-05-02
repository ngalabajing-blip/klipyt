# scripts/

Operator scripts that aren't part of the API/worker hot path.

## YouTube cookie auto-refresh

The deployed worker pulls YouTube videos with `yt-dlp`. Without an
authenticated cookie, YouTube starts challenging the request with
"Sign in to confirm you're not a bot" — which blocks every download.
A static `YOUTUBE_COOKIES` env var works for ~1-2 weeks, but YouTube
will eventually flag the cookie+IP combo. The two scripts below close
the loop.

### Architecture

```
   ┌──────────────────────┐         ┌──────────────────────┐
   │  setup_youtube_      │ once    │ Cloudflare R2        │
   │  cookies.py          │────────▶│ auth/                │
   │ (operator's laptop)  │         │   youtube-storage-   │
   └──────────────────────┘         │   state.json         │
                                    │   youtube-cookies.txt│
   ┌──────────────────────┐         └──────────────────────┘
   │ refresh_youtube_     │ every     ▲             │
   │ cookies.py           │ ~6 h      │ rotate      │ read
   │ (Railway cron)       │───────────┘             ▼
   └──────────────────────┘                ┌──────────────────────┐
                                           │ klipyt API/worker    │
                                           │ ingest.py            │
                                           │ → app.auth.cookies   │
                                           └──────────────────────┘
```

The backend reads cookies via `app.auth.cookies.get_cookie_file()`,
which prefers the rotating R2 copy and falls back to the
`YOUTUBE_COOKIES` env var when R2 is empty (bootstrap).

### One-time setup (operator)

```bash
cd backend
pip install -e ".[refresher]"
playwright install chromium

# Make sure S3_* env vars are set to point at the same R2 bucket
# Railway uses (you can copy them from Railway → service → Variables).
python -m scripts.setup_youtube_cookies
```

A Chromium window opens on `accounts.google.com`. Log in to a
**secondary YouTube account** (do not use your personal one — this
session will be replayed from a Railway IP, and Google will
occasionally challenge it). When the YouTube home feed loads,
return to the terminal and press Enter.

The script uploads:
- `auth/youtube-storage-state.json` — Playwright session state.
- `auth/youtube-cookies.txt` — Netscape cookie file consumed by
  `yt-dlp`.

### Recurring refresh (Railway)

Add a new Railway **scheduled service** in the existing project:

| Setting              | Value                                              |
|----------------------|----------------------------------------------------|
| Source               | Same git repo, root path `backend/`                |
| Dockerfile           | `Dockerfile.refresher`                             |
| Schedule             | `0 */6 * * *` (every 6 hours)                      |
| Start command        | `python -m scripts.refresh_youtube_cookies`        |
| Env vars             | `S3_*` (same as backend), `YOUTUBE_COOKIES_KEY` (optional override) |

The service is short-lived: ~30s per run, then exits. Memory peaks
around 200 MB during the headless Chromium session.

### Failure modes & escalation

- **No storage state in R2** → script logs an error and exits 0
  (won't page). Re-run `setup_youtube_cookies.py` to seed.
- **Login challenged** (Google "Verify it's you") → refresh keeps
  running but cookies don't pick up new tokens; eventually
  `yt-dlp` starts erroring with bot-detection. Re-run
  `setup_youtube_cookies.py` from a fresh laptop session.
- **Object storage unreachable** → backend falls back to the
  `YOUTUBE_COOKIES` env var, so jobs keep working until the next
  refresher run.
