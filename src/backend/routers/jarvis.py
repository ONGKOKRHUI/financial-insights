"""FastAPI router for the Jarvis voice assistant — V2.

Endpoints:
    POST /api/jarvis/intent/stream  ← PRIMARY (Phase 1)
        Accepts plain TEXT (already transcribed by browser Web Speech API).
        Runs intent classification only — NO audio upload, NO ASR wait.
        Returns SSE: event:response → intent JSON, event:done.
        Latency: ~1–3s (just the intent classifier, no ASR bottleneck).

    POST /api/jarvis/voice/stream   ← AUDIO FALLBACK
        Accepts audio file → ASR → intent → SSE.
        Used when Web Speech API is unavailable (Firefox, some mobile browsers).
        Shows transcript via event:transcript after ASR, then event:response.

    POST /api/jarvis/voice          ← LEGACY V1 (kept for testing)
        Blocking single-response endpoint. Not used by the V2 frontend.

    POST /api/jarvis/speak
        Text → MP3 audio bytes (edge-tts or Google Cloud TTS).

    GET  /api/jarvis/health
        Engine status check.

SSE event format:
    event: transcript   data: {"text": "navigate to Maybank"}
    event: response     data: {"action": "navigate", "target": "/companies/MAYBANK", ...}
    event: error        data: {"message": "..."}
    event: done         data: {}
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse

from services.asr import ASRError, transcribe
from services.jarvis_intent import map_intent
from services.tts import TTSError, synthesize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jarvis", tags=["jarvis"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    """Format a single SSE frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── PRIMARY: Text-only intent endpoint (Web Speech API path) ─────────────────

@router.post("/intent/stream")
async def intent_stream(text: str = Form(...)) -> StreamingResponse:
    """Classify intent from a pre-transcribed text string via SSE.

    This is the **fastest path**: the browser's Web Speech API has already
    converted audio to text in real-time, so we skip ASR entirely.

    Args:
        text: Final transcript from the browser's SpeechRecognition API.

    SSE events:
        response  → intent JSON
        error     → on failure
        done      → always last
    """
    logger.info("Intent stream request | text: %r", text[:80] if text else "")

    async def event_generator():
        if not text or not text.strip():
            yield _sse("error", {"message": "No text received."})
            yield _sse("done", {})
            return

        try:
            intent = map_intent(text.strip())
            logger.info("Intent result: %s", intent)
            yield _sse("response", {**intent, "transcript": text.strip()})
        except Exception as exc:
            logger.exception("Intent mapping error")
            yield _sse("error", {"message": "Could not process your request."})

        yield _sse("done", {})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── AUDIO FALLBACK: SSE streaming with ASR ────────────────────────────────────

@router.post("/voice/stream")
async def voice_stream(
    file: UploadFile = File(...),
    stop_reason: str = Form(default="button"),
) -> StreamingResponse:
    """Audio upload → ASR → intent SSE (fallback when Web Speech API unavailable).

    Pushes event:transcript immediately after ASR completes, then event:response
    after intent classification, so the UI shows something within ASR time (~1–3s).

    Args:
        file: Audio blob (audio/webm from MediaRecorder or audio/wav from VAD).
        stop_reason: "vad" | "button" — analytics only.
    """
    try:
        audio_bytes = await file.read()
        mime_type = file.content_type or "audio/webm"
        logger.info("Audio stream | size=%d bytes | mime=%s | stop=%s", len(audio_bytes), mime_type, stop_reason)
    except Exception:
        async def err():
            yield _sse("error", {"message": "Could not read audio file."})
            yield _sse("done", {})
        return StreamingResponse(err(), media_type="text/event-stream")

    async def event_generator():
        # Stage 1: ASR
        transcript = ""
        try:
            transcript = transcribe(audio_bytes, mime_type=mime_type)
            logger.info("ASR transcript: %r", transcript)
            yield _sse("transcript", {"text": transcript})
        except ASRError as exc:
            yield _sse("error", {"message": f"Speech recognition failed: {exc}"})
            yield _sse("done", {})
            return
        except Exception:
            logger.exception("Unexpected ASR error")
            yield _sse("error", {"message": "Internal ASR error."})
            yield _sse("done", {})
            return

        # Stage 2: Intent
        try:
            intent = map_intent(transcript)
            logger.info("Intent: %s", intent)
            yield _sse("response", {**intent, "transcript": transcript})
        except Exception:
            logger.exception("Intent mapping error")
            yield _sse("error", {"message": "Could not process your request."})

        yield _sse("done", {})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── LEGACY V1: Blocking endpoint ──────────────────────────────────────────────

@router.post("/voice")
async def voice_command(file: UploadFile = File(...)) -> JSONResponse:
    """Legacy blocking endpoint. Use /intent/stream or /voice/stream instead."""
    try:
        audio_bytes = await file.read()
        mime_type = file.content_type or "audio/webm"
    except Exception:
        return JSONResponse(status_code=400, content={"action": "error", "message": "Could not read audio.", "transcript": ""})

    try:
        transcript = transcribe(audio_bytes, mime_type=mime_type)
    except ASRError as exc:
        return JSONResponse(status_code=503, content={"action": "error", "message": str(exc), "transcript": ""})
    except Exception:
        return JSONResponse(status_code=500, content={"action": "error", "message": "Internal ASR error.", "transcript": ""})

    try:
        intent = map_intent(transcript)
    except Exception:
        return JSONResponse(status_code=500, content={"action": "error", "message": "Could not process request.", "transcript": transcript})

    return JSONResponse(status_code=200, content={**intent, "transcript": transcript})


# ── TTS ───────────────────────────────────────────────────────────────────────

@router.post("/speak")
async def speak(text: str = Form(...)) -> Response:
    """Convert text to MP3 audio bytes via configured TTS engine."""
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    try:
        audio_bytes = await synthesize(text.strip())
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=jarvis-response.mp3"},
        )
    except TTSError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("TTS error")
        raise HTTPException(status_code=500, detail="TTS synthesis failed.")


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def jarvis_health() -> dict:
    """Liveness check — returns engine config."""
    import os
    return {
        "status": "ok",
        "version": "2.1.0",
        "asr_engine": os.getenv("JARVIS_ASR_ENGINE", "gemini"),
        "intent_engine": os.getenv("JARVIS_INTENT_ENGINE", "keyword"),
        "tts_engine": os.getenv("JARVIS_TTS_ENGINE", "edge"),
        "primary_path": "web-speech-api → /intent/stream",
        "fallback_path": "audio-upload → /voice/stream",
    }
