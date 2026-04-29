"""Automatic Speech Recognition (ASR) service for Jarvis.

Supports two engines, toggled via JARVIS_ASR_ENGINE env var:
  - "whisper"  → openai-whisper Large V3 (local, Docker-friendly, best for dev)
  - "gemini"   → Gemini Audio API       (zero extra deps, best for production)

The Whisper model is lazy-loaded on the first request to avoid blocking startup.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

_ASR_ENGINE = os.getenv("JARVIS_ASR_ENGINE", "gemini").lower()
_WHISPER_MODEL_NAME = os.getenv("JARVIS_WHISPER_MODEL", "large-v3")

# Lazy-loaded Whisper model (only instantiated if engine == "whisper")
_whisper_model = None


class ASRError(Exception):
    """Raised when speech-to-text conversion fails."""


# ── faster-whisper (local) ────────────────────────────────────────────────────

def _load_whisper():
    """Load faster-whisper model once and cache it."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            logger.info(
                "Loading faster-whisper model '%s' — this may take a moment on first run...",
                _WHISPER_MODEL_NAME,
            )
            # Use CPU with int8 quantization for broad compatibility (no GPU required)
            _whisper_model = WhisperModel(_WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
            logger.info("faster-whisper model '%s' loaded successfully.", _WHISPER_MODEL_NAME)
        except ImportError as exc:
            raise ASRError(
                "faster-whisper is not installed. "
                "Add 'faster-whisper' to requirements-whisper.txt or switch to JARVIS_ASR_ENGINE=gemini."
            ) from exc
    return _whisper_model


def _transcribe_whisper(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio using local faster-whisper model."""
    model = _load_whisper()

    ext_map = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mp4": ".mp4",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
    }
    ext = ext_map.get(mime_type, ".webm")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        logger.debug("Running faster-whisper inference on %s (%d bytes)", tmp_path, len(audio_bytes))
        segments, info = model.transcribe(tmp_path, beam_size=5)
        transcript = " ".join(seg.text for seg in segments).strip()
        logger.info("faster-whisper transcript: %r (lang=%s)", transcript, info.language)
        return transcript
    except Exception as exc:
        raise ASRError(f"faster-whisper transcription failed: {exc}") from exc
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except OSError:
            pass


# ── Gemini Audio API ───────────────────────────────────────────────────────────

def _transcribe_gemini(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio using the Google Gemini Audio API."""
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise ASRError("GOOGLE_API_KEY is not set. Cannot use JARVIS_ASR_ENGINE=gemini.")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ASRError(
            "google-generativeai is not installed. "
            "Add it to requirements.txt or switch to JARVIS_ASR_ENGINE=whisper."
        ) from exc

    genai.configure(api_key=api_key)
    model_name = os.getenv("JARVIS_GEMINI_MODEL", "gemini-1.5-flash")
    model = genai.GenerativeModel(model_name)

    logger.debug("Sending %d bytes of audio to Gemini (%s)...", len(audio_bytes), mime_type)

    prompt = (
        "Transcribe the following audio clip accurately. "
        "Return only the spoken words with no commentary, metadata, or punctuation added. "
        "If the audio is silent or unintelligible, return an empty string."
    )

    # Gemini accepts inline audio blobs
    audio_part = {"mime_type": mime_type, "data": audio_bytes}

    try:
        response = model.generate_content([prompt, audio_part])
        transcript = response.text.strip()
        logger.info("Gemini ASR transcript: %r", transcript)
        return transcript
    except Exception as exc:
        raise ASRError(f"Gemini ASR failed: {exc}") from exc


# ── Public API ─────────────────────────────────────────────────────────────────

def transcribe(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio bytes to text using the configured ASR engine.

    Args:
        audio_bytes: Raw audio file bytes (webm, wav, mp4, etc.)
        mime_type:   MIME type of the audio (default: audio/webm from MediaRecorder)

    Returns:
        Transcript string (may be empty if audio was silent).

    Raises:
        ASRError: If transcription fails.
    """
    if not audio_bytes:
        raise ASRError("No audio data received.")

    logger.info("ASR engine: %s | audio size: %d bytes | mime: %s", _ASR_ENGINE, len(audio_bytes), mime_type)

    if _ASR_ENGINE == "whisper":
        return _transcribe_whisper(audio_bytes, mime_type)
    elif _ASR_ENGINE == "gemini":
        return _transcribe_gemini(audio_bytes, mime_type)
    else:
        raise ASRError(
            f"Unknown JARVIS_ASR_ENGINE value: '{_ASR_ENGINE}'. "
            "Must be 'whisper' or 'gemini'."
        )
