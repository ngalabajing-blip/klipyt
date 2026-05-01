"""Health-check + diagnostics."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.api.schemas import HealthOut
from app.config import settings

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(
        ok=True,
        version=__version__,
        mimo_models=[
            settings.mimo_model_pro,
            settings.mimo_model_fast,
            settings.mimo_model_omni,
            settings.mimo_model_tts,
            settings.mimo_model_tts_clone,
            settings.mimo_model_tts_design,
        ],
        extras={"app_env": settings.app_env, "redis": settings.redis_url},
    )
