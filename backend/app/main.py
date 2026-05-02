"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import ai_video, health, jobs, tts, uploads
from app.config import settings
from app.db.models import Base
from app.db.session import engine

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mager Klip API",
        description="Auto-clip generator powered by Xiaomi MiMo.",
        version=__version__,
    )
    # Support comma-separated origins via FRONTEND_BASE_URL env var
    origins = [o.strip() for o in settings.frontend_base_url.split(",") if o.strip()]
    origins.extend(["http://localhost:3000", "http://localhost:5173"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(tts.router)
    app.include_router(ai_video.router)
    app.include_router(uploads.router)

    # Serve locally-stored clips/files
    storage_dir = Path("./storage")
    storage_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(storage_dir)), name="files")

    @app.get("/")
    async def root():
        return {"name": "Mager Klip API", "version": __version__, "docs": "/docs"}

    @app.on_event("startup")
    async def _startup() -> None:
        if os.environ.get("SKIP_DB_INIT") == "1":
            return
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    return app


app = create_app()
