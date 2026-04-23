# Jarvis — API Reference

Base path: `/api/jarvis`

All endpoints are served by the FastAPI backend on port `8000` locally (`http://localhost:8000`).

---

## Endpoint Overview

| Endpoint | Method | Use Case | Latency |
|----------|--------|----------|---------|
| `/intent/stream` | POST | 🏆 **Primary** — text from Web Speech API → SSE | ~100ms–2s |
| `/voice/stream` | POST | Fallback — audio file → ASR → SSE | ~3–6s |
| `/voice` | POST | Legacy blocking (testing only) | ~3–8s |
| `/speak` | POST | Text → MP3 TTS audio | ~400ms |
| `/health` | GET | Engine status check | instant |

---

## Endpoints

### `POST /api/jarvis/intent/stream` — 🏆 Primary (Text → SSE)

**This is the fastest path.** Accepts plain text already transcribed by the browser's Web Speech API — no audio, no ASR wait. Returns intent result via SSE.

**Request**

```
Content-Type: multipart/form-data
Body:
  text (required)  — final transcript string from SpeechRecognition API
```

**SSE events**

| Event | Data | Timing |
|-------|------|--------|
| `response` | Full intent JSON | ~100ms (keyword) or ~1.5s (Dify) |
| `error` | `{ "message": "..." }` | On failure |
| `done` | `{}` | Always last |

**`response` payload**

```json
{
  "action": "navigate",
  "target": "/companies/MAYBANK",
  "label": "Maybank",
  "transcript": "navigate to Maybank",
  "engine": "keyword"
}
```

**Example — cURL**

```bash
curl -X POST http://localhost:8000/api/jarvis/intent/stream \
  -F "text=navigate to Maybank" \
  --no-buffer
```

**Example — JavaScript**

```javascript
const formData = new FormData();
formData.append('text', transcript);  // from SpeechRecognition.onresult

const response = await fetch('/api/jarvis/intent/stream', {
  method: 'POST',
  body: formData,
});
// Read SSE stream from response.body
```

---


### `POST /api/jarvis/voice` — V1 Blocking (Legacy)

Accepts an audio file, transcribes it, runs intent classification, and returns a JSON result **all in one response**. Use this for simple integrations or testing; prefer `/voice/stream` for production frontend use.

**Request**

```
Content-Type: multipart/form-data
Body:
  file (required)  — audio blob (audio/webm from MediaRecorder)
```

**Response**

=== "navigate"
    ```json
    {
      "action": "navigate",
      "target": "/companies/MAYBANK",
      "label": "Maybank",
      "transcript": "show me maybank",
      "engine": "keyword"
    }
    ```

=== "respond"
    ```json
    {
      "action": "respond",
      "message": "Maybank's P/E ratio for FY2023 was 14.2x.",
      "voice": "Maybank's P/E ratio for FY2023 was 14.2.",
      "intent_id": 2,
      "transcript": "what is maybank pe ratio"
    }
    ```

=== "unknown"
    ```json
    {
      "action": "unknown",
      "message": "Could not understand: \"...\".",
      "transcript": "..."
    }
    ```

=== "error"
    ```json
    {
      "action": "error",
      "message": "Speech recognition failed: ...",
      "transcript": ""
    }
    ```

**Status Codes**

| Code | Meaning |
|------|---------|
| 200 | Success (action may still be `unknown`) |
| 400 | Bad request (unreadable audio) |
| 503 | ASR engine unavailable |
| 500 | Internal server error |

---

### `POST /api/jarvis/voice/stream` — V2 SSE Streaming *(Recommended)*

The primary endpoint for the frontend. Pushes events via **Server-Sent Events (SSE)** so the transcript appears immediately, before intent classification is done.

**Request**

```
Content-Type: multipart/form-data
Body:
  file        (required) — audio blob (audio/webm or audio/wav)
  stop_reason (optional) — "button" | "vad" (default: "button")
```

**SSE Event Stream**

Events are pushed in this order:

| Event | Data | Timing |
|-------|------|--------|
| `transcript` | `{ "text": "..." }` | Immediately after ASR (~0.5–2s) |
| `response` | Full intent JSON (see below) | After Dify classification (~2–5s total) |
| `error` | `{ "message": "..." }` | On any failure |
| `done` | `{}` | Always last |

**`response` event payload**

```json
{
  "action": "navigate | respond | unknown | error",
  "target": "/companies/MAYBANK",
  "label": "Maybank",
  "message": "Navigating to Maybank…",
  "voice": "Navigating to Maybank",
  "intent_id": 1,
  "transcript": "navigate to maybank",
  "confidence": 0.97
}
```

**Example — cURL**

```bash
curl -X POST http://localhost:8000/api/jarvis/voice/stream \
  -F "file=@recording.webm;type=audio/webm" \
  -F "stop_reason=button" \
  --no-buffer
```

**Example — JavaScript (Frontend)**

```javascript
const formData = new FormData();
formData.append('file', audioBlob, 'recording.webm');
formData.append('stop_reason', 'vad');

const response = await fetch('/api/jarvis/voice/stream', {
  method: 'POST',
  body: formData,
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

// Parse SSE frames
let buffer = '';
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  // Split on double newlines → parse event/data pairs
}
```

---

### `POST /api/jarvis/speak` — Text-to-Speech

Synthesizes text to MP3 audio using the configured TTS engine.

**Request**

```
Content-Type: multipart/form-data
Body:
  text (required) — plain text to synthesize (keep to 1–2 sentences)
```

**Response**

```
Content-Type: audio/mpeg
Body: raw MP3 bytes
```

**Example — cURL**

```bash
curl -X POST http://localhost:8000/api/jarvis/speak \
  -F "text=Navigating to Maybank" \
  --output response.mp3
```

**Example — JavaScript**

```javascript
const formData = new FormData();
formData.append('text', 'Navigating to Maybank');

const res = await fetch('/api/jarvis/speak', { method: 'POST', body: formData });
const blob = await res.blob();
const audio = new Audio(URL.createObjectURL(blob));
audio.play();
```

---

### `GET /api/jarvis/health` — Liveness Check

Returns the current engine configuration for quick diagnostics.

**Response**

```json
{
  "status": "ok",
  "version": "2.0.0",
  "asr_engine": "gemini",
  "intent_engine": "dify",
  "tts_engine": "edge",
  "streaming": true
}
```

**Example — cURL**

```bash
curl http://localhost:8000/api/jarvis/health
```

---

## Response Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | `navigate`, `respond`, `unknown`, or `error` |
| `target` | string? | Next.js route (only for `navigate`) |
| `label` | string? | Human-readable page name |
| `message` | string? | Full response text (for `respond`/`unknown`/`error`) |
| `voice` | string? | Short 1–2 sentence version for TTS |
| `intent_id` | int? | 1–6 (see Intent Definitions) |
| `transcript` | string | What Jarvis heard |
| `confidence` | float? | Classifier confidence (0.0–1.0) |
| `engine` | string? | Which engine handled intent (`keyword` or `dify`) |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_ASR_ENGINE` | `gemini` | `whisper` or `gemini` |
| `JARVIS_WHISPER_MODEL` | `large-v3` | Whisper model size |
| `JARVIS_GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model for ASR |
| `JARVIS_INTENT_ENGINE` | `keyword` | `keyword` or `dify` |
| `JARVIS_DIFY_API_URL` | — | Dify Cloud workflow URL |
| `JARVIS_DIFY_API_KEY` | — | Dify Cloud API key (`app-...`) |
| `JARVIS_DIFY_TIMEOUT` | `15` | Seconds before Dify fallback |
| `JARVIS_TTS_ENGINE` | `edge` | `edge` or `google` |
| `JARVIS_TTS_VOICE` | `en-US-AriaNeural` | edge-tts voice name |
| `GOOGLE_TTS_API_KEY` | — | Only for `JARVIS_TTS_ENGINE=google` |
