"""Pydantic types for MiMo API requests/responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """A single chat message — content may be a string or a list of multimodal parts."""

    model_config = ConfigDict(extra="allow")

    role: Literal["system", "developer", "user", "assistant", "tool", "function"]
    content: str | list[dict[str, Any]]


class ChatResponse(BaseModel):
    """Subset of the MiMo chat-completion response we care about."""

    model_config = ConfigDict(extra="allow")

    id: str
    model: str
    text: str = ""
    reasoning: str = ""
    audio_b64: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class TTSResult(BaseModel):
    """Result of a TTS / voice-clone / voice-design synthesis call."""

    audio_wav: bytes
    sample_rate: int = 24_000
    duration_seconds: float = 0.0
    transcript: str | None = None


class HighlightCandidate(BaseModel):
    """A candidate clip identified by the highlight detector."""

    start: float = Field(ge=0)
    end: float = Field(gt=0)
    score: float = Field(ge=0, le=10)
    title: str
    caption: str
    reason: str = ""
    hashtags: list[str] = Field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)
