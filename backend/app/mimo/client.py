"""High-level MiMo API client.

The MiMo platform exposes an OpenAI-compatible ``/v1/chat/completions`` endpoint.
Model behaviour depends on the ``model`` ID:

* ``mimo-v2.5-pro`` / ``mimo-v2.5`` / ``mimo-v2-pro`` — text reasoning
* ``mimo-v2-omni`` — multimodal (image + video as ``data:`` URLs)
* ``mimo-v2.5-tts`` / ``mimo-v2-tts`` — TTS, expects an ``assistant`` message
* ``mimo-v2.5-tts-voiceclone`` — TTS + ``audio.voice`` reference (data URL)
* ``mimo-v2.5-tts-voicedesign`` — TTS with a ``user`` voice description message
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from app.config import Settings
from app.config import settings as default_settings
from app.mimo.types import ChatMessage, ChatResponse, TTSResult

logger = logging.getLogger(__name__)


class MiMoError(RuntimeError):
    """Raised when the MiMo API returns a non-2xx response."""


class MiMoClient:
    """Thin async client around MiMo's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or default_settings
        self.api_key = api_key or cfg.mimo_api_key
        self.base_url = (base_url or cfg.mimo_base_url).rstrip("/")
        self.timeout = timeout
        self.cfg = cfg
        if not self.api_key:
            logger.warning("MiMo client created without an API key set.")

    # ------------------------------------------------------------------ helpers

    def _headers(self) -> dict[str, str]:
        return {
            "api-key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _data_url(blob: bytes, mime: str) -> str:
        return f"data:{mime};base64,{base64.b64encode(blob).decode()}"

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        try:
            return payload["choices"][0]["message"].get("content", "") or ""
        except (KeyError, IndexError, TypeError):
            return ""

    @staticmethod
    def _extract_reasoning(payload: dict[str, Any]) -> str:
        try:
            return payload["choices"][0]["message"].get("reasoning_content", "") or ""
        except (KeyError, IndexError, TypeError):
            return ""

    @staticmethod
    def _extract_audio_b64(payload: dict[str, Any]) -> str | None:
        try:
            audio = payload["choices"][0]["message"].get("audio")
            if isinstance(audio, dict):
                return audio.get("data")
        except (KeyError, IndexError, TypeError):
            return None
        return None

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
        if response.status_code >= 400:
            raise MiMoError(
                f"MiMo API {response.status_code} on {path}: {response.text[:1000]}"
            )
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise MiMoError(f"Non-JSON response from MiMo: {response.text[:500]}") from exc

    # ------------------------------------------------------------------- chat

    async def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.95,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Send a generic chat request — used for V2.5-Pro / V2.5 / V2-Pro / V2-Omni."""
        payload: dict[str, Any] = {
            "model": model or self.cfg.mimo_model_pro,
            "messages": [
                m.model_dump(exclude_none=True) if isinstance(m, ChatMessage) else m
                for m in messages
            ],
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
        if extra:
            payload.update(extra)

        raw = await self._post("/chat/completions", payload)
        return ChatResponse(
            id=raw.get("id", ""),
            model=raw.get("model", payload["model"]),
            text=self._extract_text(raw),
            reasoning=self._extract_reasoning(raw),
            audio_b64=self._extract_audio_b64(raw),
            raw=raw,
        )

    # -------------------------------------------------- omni: image / video

    async def omni_image(
        self,
        prompt: str,
        image_bytes: bytes,
        *,
        mime: str = "image/jpeg",
        max_tokens: int = 1024,
        model: str | None = None,
    ) -> str:
        """Run a single-image multimodal query against ``mimo-v2-omni``."""
        msg: dict[str, Any] = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": self._data_url(image_bytes, mime)}},
            ],
        }
        response = await self.chat(
            [msg], model=model or self.cfg.mimo_model_omni, max_tokens=max_tokens
        )
        return response.text

    async def omni_video(
        self,
        prompt: str,
        video_bytes: bytes,
        *,
        mime: str = "video/mp4",
        max_tokens: int = 2048,
        response_format: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        """Run a video query against ``mimo-v2-omni``.

        The MiMo platform accepts the video as a ``data:video/mp4;base64,...`` URL
        in a ``video_url`` content part. Keep clips reasonably short (~ < 25 MB)
        for a snappy round-trip.
        """
        msg: dict[str, Any] = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "video_url", "video_url": {"url": self._data_url(video_bytes, mime)}},
            ],
        }
        return await self.chat(
            [msg],
            model=model or self.cfg.mimo_model_omni,
            max_tokens=max_tokens,
            response_format=response_format,
        )

    # --------------------------------------------------------------- TTS

    async def tts(self, text: str, *, model: str | None = None) -> TTSResult:
        """Default TTS — uses ``mimo-v2.5-tts``.

        MiMo TTS expects the text in an ``assistant`` message and returns the
        synthesised audio as base64 WAV (16-bit PCM, 24 kHz mono).
        """
        payload = {
            "model": model or self.cfg.mimo_model_tts,
            "messages": [{"role": "assistant", "content": text}],
        }
        raw = await self._post("/chat/completions", payload)
        audio_b64 = self._extract_audio_b64(raw) or ""
        if not audio_b64:
            raise MiMoError(f"MiMo TTS returned no audio data: {json.dumps(raw)[:500]}")
        wav = base64.b64decode(audio_b64)
        return TTSResult(audio_wav=wav, sample_rate=24_000, transcript=text)

    async def tts_voice_clone(
        self,
        text: str,
        reference_wav: bytes,
        *,
        model: str | None = None,
    ) -> TTSResult:
        """Synthesise speech that mimics ``reference_wav``."""
        payload = {
            "model": model or self.cfg.mimo_model_tts_clone,
            "audio": {"voice": self._data_url(reference_wav, "audio/wav")},
            "messages": [{"role": "assistant", "content": text}],
        }
        raw = await self._post("/chat/completions", payload)
        audio_b64 = self._extract_audio_b64(raw) or ""
        if not audio_b64:
            raise MiMoError(
                f"MiMo voice clone returned no audio data: {json.dumps(raw)[:500]}"
            )
        return TTSResult(
            audio_wav=base64.b64decode(audio_b64),
            sample_rate=24_000,
            transcript=text,
        )

    async def tts_voice_design(
        self,
        text: str,
        voice_description: str,
        *,
        model: str | None = None,
    ) -> TTSResult:
        """Generate speech with a custom-designed voice persona."""
        payload = {
            "model": model or self.cfg.mimo_model_tts_design,
            "messages": [
                {"role": "user", "content": voice_description},
                {"role": "assistant", "content": text},
            ],
        }
        raw = await self._post("/chat/completions", payload)
        audio_b64 = self._extract_audio_b64(raw) or ""
        if not audio_b64:
            raise MiMoError(
                f"MiMo voice design returned no audio data: {json.dumps(raw)[:500]}"
            )
        return TTSResult(
            audio_wav=base64.b64decode(audio_b64),
            sample_rate=24_000,
            transcript=text,
        )
