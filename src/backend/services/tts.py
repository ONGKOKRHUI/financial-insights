"""Text-to-Speech (TTS) service for Jarvis.

Supports two engines, toggled via JARVIS_TTS_ENGINE env var:
  - "edge"   → edge-tts (Microsoft Edge TTS, free, no API key, local-friendly)
  - "google" → Google Cloud Text-to-Speech (production, requires GOOGLE_TTS_API_KEY)

Returns raw MP3 audio bytes ready to stream back to the frontend.
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_TTS_ENGINE = os.getenv("JARVIS_TTS_ENGINE", "edge").lower()
_TTS_VOICE = os.getenv("JARVIS_TTS_VOICE", "en-US-AriaNeural")


class TTSError(Exception):
    """Raised when TTS synthesis fails."""


# ── edge-tts (local, free) ────────────────────────────────────────────────────

async def _synthesize_edge(text: str) -> bytes:
    """Synthesize speech using Microsoft edge-tts (no API key required)."""
    try:
        import edge_tts  # pip install edge-tts
    except ImportError as exc:
        raise TTSError(
            "edge-tts is not installed. Run: pip install edge-tts"
        ) from exc

    communicate = edge_tts.Communicate(text, voice=_TTS_VOICE)
    audio_chunks: list[bytes] = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    if not audio_chunks:
        raise TTSError("edge-tts returned no audio data.")

    logger.info("edge-tts synthesized %d bytes for text: %r", sum(len(c) for c in audio_chunks), text[:60])
    return b"".join(audio_chunks)


# ── Google Cloud TTS (production) ─────────────────────────────────────────────

async def _synthesize_google(text: str) -> bytes:
    """Synthesize speech using Google Cloud Text-to-Speech API."""
    api_key = os.getenv("GOOGLE_TTS_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    if not api_key:
        raise TTSError("GOOGLE_TTS_API_KEY is not set. Cannot use JARVIS_TTS_ENGINE=google.")

    try:
        import httpx  # Already available via fastapi ecosystem
    except ImportError as exc:
        raise TTSError("httpx is not installed. Run: pip install httpx") from exc

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": "en-US",
            "name": os.getenv("JARVIS_TTS_VOICE", "en-US-Neural2-F"),
            "ssmlGender": "FEMALE",
        },
        "audioConfig": {"audioEncoding": "MP3"},
    }

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    import base64
    audio_bytes = base64.b64decode(data["audioContent"])
    logger.info("Google TTS synthesized %d bytes.", len(audio_bytes))
    return audio_bytes


# ── Public API ────────────────────────────────────────────────────────────────

async def synthesize(text: str) -> bytes:
    """Convert text to MP3 audio bytes using the configured TTS engine.

    Args:
        text: The text to speak. Keep to 1–2 sentences for voice output.

    Returns:
        Raw MP3 bytes.

    Raises:
        TTSError: If synthesis fails.
    """
    if not text or not text.strip():
        raise TTSError("No text provided for TTS synthesis.")

    logger.info("TTS engine: %s | text length: %d chars", _TTS_ENGINE, len(text))

    if _TTS_ENGINE == "edge":
        return await _synthesize_edge(text)
    elif _TTS_ENGINE == "google":
        return await _synthesize_google(text)
    else:
        raise TTSError(
            f"Unknown JARVIS_TTS_ENGINE value: '{_TTS_ENGINE}'. Must be 'edge' or 'google'."
        )
