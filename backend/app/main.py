"""FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_base_url, "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(tts.router)
    app.include_router(ai_video.router)
    app.include_router(uploads.router)

    @app.on_event("startup")
    async def _startup() -> None:
        # Create tables on first boot for SQLite / dev use. Use Alembic in prod.
        if settings.database_url.startswith("sqlite"):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    return app


app = create_app()
