# Mager Klip

Open-source clone of [klip.mageran.ai](https://klip.mageran.ai/) — turn one long video into dozens of viral short clips, powered by **Xiaomi MiMo**.

## What it does

- Paste a YouTube/TikTok link or upload a video → get 5–15 vertical (9:16) clips ready for TikTok / Reels / Shorts.
- Karaoke-style word-level subtitles, auto-reframe with face tracking, AI-generated titles & captions per platform.
- AI Voice Hook: clone the speaker's voice (`MiMo-V2.5-TTS-VoiceClone`) and prepend a 3-second engagement hook in *their own voice*.
- Multi-language dubbing: translate (`MiMo-V2.5-Pro`) + voice-clone the original speaker → 1 video → N languages.
- AI Video generators: Educational, History, Satisfying, Short Movie, Character (image+TTS pipeline).
- Direct publish to TikTok / YouTube Shorts / Instagram Reels.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui |
| Backend  | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| Queue    | Redis + RQ |
| DB       | PostgreSQL (SQLite for local-only dev) |
| Storage  | S3-compatible (MinIO local, Cloudflare R2 prod) |
| Video    | ffmpeg, yt-dlp, MediaPipe (face tracking), faster-whisper |
| AI       | Xiaomi MiMo (V2.5-Pro / V2-Omni / V2.5-TTS / VoiceClone / VoiceDesign) |
| Deploy   | Vercel (frontend) + Fly.io (backend+worker) + Neon (DB) + R2 (storage) |

## Repo layout

```
mager-klip/
├── backend/                FastAPI app + worker
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db/             SQLAlchemy models + session
│   │   ├── api/            HTTP routes (auth, jobs, clips, ai-videos, social)
│   │   ├── mimo/           MiMo API client (chat, omni, TTS, voice clone/design)
│   │   ├── pipeline/       Video processing (ingest, transcribe, highlight, clip, render, hook, dub)
│   │   ├── storage/        S3-compatible adapter
│   │   └── worker.py       RQ worker entrypoint
│   ├── pyproject.toml
│   └── tests/
├── frontend/               Next.js app
│   ├── src/app/
│   ├── src/components/
│   └── package.json
├── docker-compose.yml      Local dev: postgres + redis + minio
├── .env.example
└── README.md
```

## Quick start (local dev)

### 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for postgres / redis / minio)
- ffmpeg (`apt install ffmpeg` or `brew install ffmpeg`)

### 2. Setup env

```bash
cp .env.example .env
# Fill in MIMO_API_KEY, MIMO_BASE_URL, etc.
```

### 3. Boot infra

```bash
docker compose up -d        # postgres, redis, minio
```

### 4. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head        # run migrations
uvicorn app.main:app --reload --port 8000

# In another terminal — start the worker
rq worker -u redis://localhost:6379 default
```

### 5. Frontend

```bash
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

Open http://localhost:3000, paste a YouTube link, watch clips appear in the dashboard.

## MiMo API reference (verified working)

| Model | Use case | Format |
|---|---|---|
| `mimo-v2.5-pro` | Highlight scoring, title/caption generation, translation | Standard `/v1/chat/completions` |
| `mimo-v2-omni` | Visual scene understanding (frames or full video as data URL) | Multimodal `image_url` / `video_url` content parts |
| `mimo-v2.5-tts` | Default narration | `messages: [{role:"assistant", content:text}]` → `message.audio.data` (base64 WAV 24 kHz) |
| `mimo-v2.5-tts-voiceclone` | Clone speaker for hook / dubbing | + `audio: {voice: "data:audio/wav;base64,..."}` reference |
| `mimo-v2.5-tts-voicedesign` | Custom-persona voiceover | `[{role:"user", content: voice_description}, {role:"assistant", content: text}]` |

Auth: `api-key: <key>` header. Base URL: `https://token-plan-sgp.xiaomimimo.com/v1`.

## CI

A GitHub Actions workflow template lives at [`docs/ci-template.yml`](docs/ci-template.yml).
To enable CI, copy it to `.github/workflows/ci.yml` (requires a token with
`workflow` scope, or use the GitHub web UI: Actions → New workflow → set up a
workflow yourself → paste).

## License

MIT
