# Jarvis — Deployment Guide

## Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

### Minimum variables for Jarvis (production - Gemini ASR + LangGraph intent)

```bash
GOOGLE_API_KEY=AIzaSy...         # Gemini API key — also used for ASR
JARVIS_ASR_ENGINE=gemini
JARVIS_GEMINI_MODEL=gemini-2.0-flash
JARVIS_INTENT_ENGINE=langgraph
JARVIS_TTS_ENGINE=edge
JARVIS_TTS_VOICE=en-US-AriaNeural
```

### Minimum variables for Jarvis (local Docker - Whisper ASR)

```bash
JARVIS_ASR_ENGINE=whisper
JARVIS_WHISPER_MODEL=large-v3
JARVIS_INTENT_ENGINE=langgraph   # Uses Gemini API; falls back to keyword if key is invalid
JARVIS_TTS_ENGINE=edge
```

---

## Local Docker Compose

### Start Full Stack

```bash
docker compose up --build
```

Services started:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Jarvis Health | http://localhost:8000/api/jarvis/health |

### First-Run Whisper Download

The first time you run with `JARVIS_ASR_ENGINE=whisper`, the `large-v3` model (~1.5 GB) downloads automatically from HuggingFace. Subsequent restarts are instant because the model is cached in the `whisper_cache` Docker volume.

To pre-bake the model into the image layer (eliminate cold start):

```dockerfile
# In src/backend/Dockerfile — add after pip install:
RUN python -c "
from faster_whisper import WhisperModel
WhisperModel('large-v3', device='cpu', compute_type='int8', download_root='/models')
"
```

---

## Local Machine (No Docker)

### Backend

```bash
cd src/backend

# Core dependencies
pip install -r requirements.txt

# Local Whisper ASR (optional)
pip install setuptools
pip install -r requirements-whisper.txt --no-build-isolation

# Run
env $(grep -v '^#' ../../.env | grep -v '^$' | xargs) \
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

# Install VAD library (for browser-side silence detection)
npm install @ricky0123/vad-web

# Run
npm run dev
```

---

## Production — Render (Backend) + Vercel (Frontend)

### Backend on Render

1. Create a **Web Service** pointed at `src/backend/`
2. Build command: `pip install -r requirements.txt`  
   *(Do NOT install requirements-whisper.txt on Render — use Gemini ASR instead)*
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set environment variables in the Render dashboard:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Supabase connection string |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` |
| `GOOGLE_API_KEY` | Your Gemini API key |
| `JARVIS_ASR_ENGINE` | `gemini` |
| `JARVIS_GEMINI_MODEL` | `gemini-2.0-flash` |
| `JARVIS_INTENT_ENGINE` | `langgraph` |
| `JARVIS_TTS_ENGINE` | `edge` |

### Frontend on Vercel

1. Import `frontend/` directory on Vercel
2. Set environment variable:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://your-backend.onrender.com` |

---

## Dify Cloud — Workflow Setup (Legacy)

!!! important "Manual setup required"
    The Dify workflow cannot be provisioned automatically. You must create it once in the Dify Cloud dashboard.

### Step 1 — Create Workflow

1. Go to [https://cloud.dify.ai](https://cloud.dify.ai)
2. Click **Studio → Create → Workflow**
3. Name it `jarvis-intent-classifier`

### Step 2 — Add Nodes

Add these nodes in order:

| # | Node Type | Name | Config |
|---|-----------|------|--------|
| 1 | Start | Input | Variable: `raw_transcript` (string) |
| 2 | LLM | Transcript Refinement | Model: `gemini-2.0-flash`, temp: 0.1 |
| 3 | LLM | Intent Classifier | Model: `gemini-1.5-pro`, JSON mode: ON, temp: 0 |
| 4 | Code | JSON Parser | Python — see [Intent Classifier docs](./jarvis-intent-classifier.md#node-3--json-parser-code-python) |
| 5 | IF/ELSE | Intent Router | Conditions on `intent_id` (1–6) |
| 6+ | Various | Branches 1–6 | See [architecture docs](./jarvis-architecture.md) for branch designs |

### Step 3 — Get API Key

1. In your workflow → click **API Access**
2. Copy the API URL and API key
3. Paste into your `.env`:
   ```bash
   JARVIS_DIFY_API_URL=https://api.dify.ai/v1/workflows/run
   JARVIS_DIFY_API_KEY=app-...
   JARVIS_INTENT_ENGINE=dify
   ```

### Step 4 — Test

```bash
curl http://localhost:8000/api/jarvis/health
# Expected: { "status": "ok", "intent_engine": "dify", ... }
```

---

## Verifying Jarvis is Working

```bash
# 1. Health check
curl http://localhost:8000/api/jarvis/health

# 2. Test transcription + intent (upload a .wav or .webm file)
curl -X POST http://localhost:8000/api/jarvis/voice \
  -F "file=@test_audio.webm;type=audio/webm"

# 3. Test TTS
curl -X POST http://localhost:8000/api/jarvis/speak \
  -F "text=Hello, I am Jarvis" \
  --output test_tts.mp3 && open test_tts.mp3

# 4. Test SSE streaming (watch events appear)
curl -X POST http://localhost:8000/api/jarvis/voice/stream \
  -F "file=@test_audio.webm;type=audio/webm" \
  --no-buffer
```

---

## Troubleshooting

### `faster-whisper` not loading

```bash
# Ensure setuptools is installed first (Python 3.12 compatibility)
pip install setuptools
pip install -r requirements-whisper.txt --no-build-isolation
```

### LangGraph falls back to keyword unexpectedly

Check that `GOOGLE_API_KEY` is valid for the Generative Language API. If invalid, Jarvis logs an API key warning and falls back to the keyword engine.

### Dify returning 401 (legacy engine only)

Check that `JARVIS_DIFY_API_KEY` starts with `app-` (not `user-`). Use the **Workflow** API key, not a user key.

### CORS errors on `/voice/stream`

The backend `main.py` already allows `POST`. If you see CORS errors, check that `ALLOWED_ORIGINS` in your `.env` matches the frontend URL exactly (no trailing slash, correct protocol).

### VAD not stopping automatically

If `@ricky0123/vad-web` is not installed, Jarvis silently falls back to manual button mode. Install it:

```bash
cd frontend && npm install @ricky0123/vad-web
```

### TTS produces no audio

Check browser autoplay policy. Some browsers block autoplay until the user has interacted with the page. The Jarvis button click counts as user interaction — TTS should work after at least one button click.
