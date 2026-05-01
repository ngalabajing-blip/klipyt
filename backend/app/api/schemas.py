"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobCreateRequest(BaseModel):
    source_url: str | None = None
    source_object_key: str | None = None
    target_clip_count: int = Field(default=6, ge=1, le=20)
    enable_voice_hook: bool = False
    enable_subtitles: bool = True


class ClipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    index: int
    title: str
    caption: str
    hashtags_json: list[str] | None = None
    score: float
    reason: str
    start: float
    end: float
    duration: float
    object_key: str | None
    thumbnail_object_key: str | None
    aspect_ratio: str
    has_voice_hook: bool
    created_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    status: str
    progress: int
    source_url: str | None
    source_title: str | None
    source_thumbnail: str | None
    source_duration: float | None
    source_language: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    clips: list[ClipOut] = []


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice_description: str | None = None  # for voice-design


class TTSResponse(BaseModel):
    audio_b64: str
    sample_rate: int = 24_000


class VoiceCloneRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    reference_audio_b64: str  # WAV base64


class AIVideoRequest(BaseModel):
    kind: str = Field(pattern="^(educational|history|satisfying|short_movie|character)$")
    prompt: str
    language: str = "id"
    voice_description: str | None = None


class HealthOut(BaseModel):
    ok: bool = True
    version: str
    mimo_models: list[str] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)
