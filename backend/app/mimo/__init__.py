"""MiMo (Xiaomi) API client wrapper.

Verified against base URL ``https://token-plan-sgp.xiaomimimo.com/v1``.
All endpoints share the OpenAI-compatible ``/chat/completions`` route — model
behaviour is differentiated by the ``model`` ID and message shape.
"""

from app.mimo.client import MiMoClient
from app.mimo.types import (
    ChatMessage,
    ChatResponse,
    HighlightCandidate,
    TTSResult,
)

__all__ = [
    "MiMoClient",
    "ChatMessage",
    "ChatResponse",
    "HighlightCandidate",
    "TTSResult",
]
