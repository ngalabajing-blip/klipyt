"""TTS / VoiceClone / VoiceDesign passthrough routes."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import TTSRequest, TTSResponse, VoiceCloneRequest
from app.mimo.client import MiMoClient, MiMoError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("/standard", response_model=TTSResponse)
async def standard_tts(req: TTSRequest) -> TTSResponse:
    client = MiMoClient()
    try:
        result = await client.tts(req.text)
    except MiMoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TTSResponse(audio_b64=base64.b64encode(result.audio_wav).decode())


@router.post("/voice-design", response_model=TTSResponse)
async def voice_design_tts(req: TTSRequest) -> TTSResponse:
    if not req.voice_description:
        raise HTTPException(status_code=400, detail="voice_description required")
    client = MiMoClient()
    try:
        result = await client.tts_voice_design(req.text, req.voice_description)
    except MiMoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TTSResponse(audio_b64=base64.b64encode(result.audio_wav).decode())


@router.post("/voice-clone", response_model=TTSResponse)
async def voice_clone_tts(req: VoiceCloneRequest) -> TTSResponse:
    try:
        ref = base64.b64decode(req.reference_audio_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {exc}") from exc
    client = MiMoClient()
    try:
        result = await client.tts_voice_clone(req.text, ref)
    except MiMoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TTSResponse(audio_b64=base64.b64encode(result.audio_wav).decode())
