# I Debug Jarvis

This file lists common Jarvis debugging issues seen in this project and how to solve them quickly.

## Quick Start Debug Flow

1. Start infra first:
   - `docker compose up --build`
2. Check containers are healthy (`postgres`, `elasticsearch`, `backend`, `frontend`).
3. If running backend locally, make sure Elasticsearch is still up in Docker.
4. Re-test Jarvis API:
   - `POST /api/jarvis/intent/stream`

## Known Errors and Fixes

### 1) Elasticsearch Connection Refused

Error pattern:
- `Elasticsearch docs index bootstrap skipped ... Failed to establish a new connection: [Errno 61] Connection refused`
- `RAG service call failed ... Connection refused`

Why it happens:
- Backend is running, but Elasticsearch container is not running (or not ready yet).

How to solve:
1. Start services:
   - `docker compose up -d elasticsearch postgres`
2. Wait for health:
   - `docker compose ps`
   - status should be `healthy` for `elasticsearch` and `postgres`.
3. Restart backend (local or container).
4. Retry Jarvis intent request.

Notes:
- This is the main Docker-related runtime issue seen in current logs.

### 2) LangGraph Intent Fallback Triggered

Error pattern:
- `LangGraph intent error: 3. Falling back to keyword engine.`

Why it happens:
- LangGraph classifier/handler throws an internal error and system falls back by design.

How to solve:
1. Check backend logs around this line for stack trace.
2. Verify model/API keys are loaded from `.env`.
3. Confirm dependencies are installed and backend restarted.
4. If issue repeats, test with a simpler transcript to isolate the failing intent.

### 3) Unauthorized on User Endpoint

Error pattern:
- `GET /users/me HTTP/1.1" 401 Unauthorized`

Why it happens:
- Missing or invalid auth token/session.

How to solve:
1. Login again from frontend.
2. Confirm token is attached in request headers.
3. Check backend auth config/env values.

### 4) `uvicorn --reload` Missing APP

Error pattern:
- `Error: Missing argument 'APP'.`

How to solve:
- Run with app target:
  - `uvicorn main:app --reload --port 8000`

### 5) Gemini Package Future Warning

Warning pattern:
- `All support for the google.generativeai package has ended... switch to google.genai`

Impact:
- Not an immediate crash, but should be migrated soon.

How to solve:
1. Plan migration from `google.generativeai` to `google.genai`.
2. Update imports and client initialization in embeddings/LLM service files.
3. Re-test intent and RAG flows.

## Docker Error Troubleshooting (Detailed)

If Jarvis fails while Docker setup is involved, run this exact sequence:

1. Stop old stack:
   - `docker compose down`
2. Start fresh build:
   - `docker compose up --build`
3. Check service health:
   - `docker compose ps`
4. Inspect Elasticsearch logs if not healthy:
   - `docker compose logs elasticsearch`
5. Inspect backend logs:
   - `docker compose logs backend`
6. Verify endpoints:
   - frontend: `http://localhost:3000`
   - backend: `http://localhost:8000/docs`
7. Re-run Jarvis request.

Important:
- `exited with code 137` can appear during manual shutdown (`Ctrl+C`) and is often not a bug by itself.
- Treat it as an error only if container exits unexpectedly without manual stop.

## Current Practical Recommendation

For stable Jarvis testing:
- Keep `elasticsearch` and `postgres` running in Docker.
- Run backend either in Docker or locally, but always with reachable Elasticsearch.
- Validate with one known intent request before broader testing.
