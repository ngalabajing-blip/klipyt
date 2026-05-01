"""Video processing pipeline.

Each module is intentionally small and pure: it accepts file paths and returns
file paths or in-memory data. Orchestration lives in :mod:`app.pipeline.runner`.

Submodules are imported lazily so that tests / lightweight tooling that only
need a single helper (e.g. ``subtitle._build_ass``) don't pay the cost of
loading heavy ML dependencies (mediapipe, faster-whisper, Pillow, etc.).
"""

__all__ = [
    "ingest",
    "transcribe",
    "highlight",
    "clip",
    "subtitle",
    "voice_hook",
    "dub",
    "ai_video",
    "runner",
]
