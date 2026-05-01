"""Unit tests for MiMo client payload shapes (no real network calls)."""

import base64

import pytest

from app.mimo.client import MiMoClient


@pytest.fixture
def client(monkeypatch):
    captured: dict = {}

    async def fake_post(self, path, payload):
        captured["path"] = path
        captured["payload"] = payload
        # mimic a TTS response with base64 WAV
        wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
        return {
            "id": "test",
            "model": payload["model"],
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "ok",
                        "audio": {"data": base64.b64encode(wav).decode()},
                    }
                }
            ],
        }

    monkeypatch.setattr(MiMoClient, "_post", fake_post)
    c = MiMoClient(api_key="test")
    c._captured = captured  # type: ignore[attr-defined]
    return c


@pytest.mark.asyncio
async def test_tts_payload_uses_assistant_role(client):
    await client.tts("Halo dunia")
    payload = client._captured["payload"]
    assert payload["model"].startswith("mimo-v2.5-tts")
    assert payload["messages"][0]["role"] == "assistant"
    assert payload["messages"][0]["content"] == "Halo dunia"


@pytest.mark.asyncio
async def test_voice_clone_uses_audio_voice_dataurl(client):
    await client.tts_voice_clone("Halo", b"\x00\x01\x02")
    payload = client._captured["payload"]
    assert payload["model"] == "mimo-v2.5-tts-voiceclone"
    assert payload["audio"]["voice"].startswith("data:audio/wav;base64,")
    assert payload["messages"][0]["role"] == "assistant"


@pytest.mark.asyncio
async def test_voice_design_includes_user_description(client):
    await client.tts_voice_design("Halo", "young female, cheerful")
    payload = client._captured["payload"]
    assert payload["model"] == "mimo-v2.5-tts-voicedesign"
    assert payload["messages"][0]["role"] == "user"
    assert "cheerful" in payload["messages"][0]["content"]
    assert payload["messages"][1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_omni_image_data_url(client):
    await client.omni_image("describe", b"\xff\xd8\xff\xd9", mime="image/jpeg")
    payload = client._captured["payload"]
    assert payload["model"] == "mimo-v2-omni"
    parts = payload["messages"][0]["content"]
    img_part = next(p for p in parts if p["type"] == "image_url")
    assert img_part["image_url"]["url"].startswith("data:image/jpeg;base64,")
