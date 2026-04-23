# Jarvis — Implementation Roadmap

## Phase Status

| Phase | Name | Status | Duration |
|-------|------|--------|---------|
| **Phase 1** | Speed Quick Wins + Multi-Intent | ✅ **Complete** | Weeks 1–2 |
| **Phase 2** | Live Streaming Transcription | 🔲 Planned | Weeks 3–4 |
| **Phase 3** | Financial Data + Elasticsearch | 🔲 Planned | Weeks 5–7 |
| **Phase 4** | Production Hardening | 🔲 Planned | Weeks 8–10 |

---

## ✅ Phase 1 — Speed Quick Wins + Multi-Intent (Complete)

### What was built

#### Backend

- [x] **`services/tts.py`** — TTS service (`edge-tts` local / Google Cloud TTS production)

- [x] **`routers/jarvis.py`** upgraded to V2.1
  - `POST /api/jarvis/intent/stream` — **🏆 PRIMARY: text-only SSE endpoint**
    - Accepts transcript text from browser Web Speech API
    - **Zero ASR cost** — skips audio upload entirely
    - Returns intent result in ~100ms (keyword) or ~1.5s (Dify)
  - `POST /api/jarvis/voice/stream` — Audio fallback SSE (for Firefox)
    - Pushes `event: transcript` immediately after ASR
    - Pushes `event: response` after intent classification
  - `POST /api/jarvis/speak` — TTS endpoint (returns MP3)
  - `GET /api/jarvis/health` — V2.1, shows `primary_path` and `fallback_path`

- [x] **`requirements.txt`** — Added: `edge-tts`, `httpx`, `silero-vad`

#### Frontend

- [x] **`JarvisButton.tsx`** upgraded to V2.1 with **Web Speech API**
  - `window.SpeechRecognition` / `window.webkitSpeechRecognition` — **zero latency**
  - **Interim results**: dim words stream live as user speaks (character by character)
  - **Final results**: bright white committed words accumulate in panel
  - **Blinking cursor** while listening
  - **2s silence auto-stop**: stops recognition automatically when user pauses
  - On `recognition.onend` → POSTs final text to `/intent/stream` (no audio, no wait)
  - TTS auto-playback of `voice` field in response
  - Graceful detection: checks `window.SpeechRecognition` availability; shows warning if unsupported

#### Documentation

- [x] `docs/ai-systems/jarvis-overview.md`
- [x] `docs/ai-systems/jarvis-architecture.md` — Updated with two-path design + latency tables
- [x] `docs/ai-systems/jarvis-intent-classifier.md`
- [x] `docs/ai-systems/jarvis-api-reference.md` — `/intent/stream` added as primary endpoint
- [x] `docs/ai-systems/jarvis-deployment.md`
- [x] `docs/ai-systems/jarvis-roadmap.md`
- [x] `mkdocs.yml` — Jarvis section added


---

## 🔲 Phase 2 — Live Streaming Transcription (Planned)

> **Goal**: Words appear on screen *while* the user is still speaking.

### Tasks

- [ ] Add **WhisperLive** Docker service to `docker-compose.yml`
  ```yaml
  whisper-live:
    image: collabora/whisperlive:latest
    ports: ["9090:9090"]
    volumes: [whisper_cache:/root/.cache/whisper]
    environment: [WHISPER_MODEL_TYPE=large-v3]
  ```
- [ ] Add WebSocket endpoint `ws://backend/ws/jarvis` to FastAPI
- [ ] Bridge FastAPI WS → WhisperLive WS → stream partial transcripts to browser
- [ ] Add server-side `silero-vad` for WASM stream finalization after 5s silence
- [ ] Frontend: replace SSE `EventSource` with persistent WebSocket connection
- [ ] Frontend: dim partial transcripts, solid when final

**Environment variables to add:**
```bash
JARVIS_WHISPERLIVE_URL=ws://whisper-live:9090
JARVIS_ENABLE_STREAMING=true
```

---

## 🔲 Phase 3 — Financial Data + Elasticsearch (Planned)

> **Goal**: Answer financial questions and company queries from real data.

### Infrastructure

- [ ] Add Elasticsearch 8.x to `docker-compose.yml`:
  ```yaml
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - ES_JAVA_OPTS=-Xms1g -Xmx1g
    ports: ["9200:9200"]
    volumes: [es_data:/usr/share/elasticsearch/data]
  ```
- [ ] Create index schemas: `financial_data`, `docs`
- [ ] Write data indexing scripts for financial records and MkDocs pages

### Dify Intent 2 — Financial Information

- [ ] Design `financial_data` ES index (company, metric, period, value)
- [ ] Build Dify **HTTP Request node** for ES queries
- [ ] Answer synthesis prompt with financial data context
- [ ] Test all metrics: P/E ratio, revenue, EPS, market cap

### Dify Intent 3 — Company Information (PDF RAG)

- [ ] Upload company PDFs to Dify Cloud Knowledge Base
- [ ] Chunking: 512 tokens, 50 overlap
- [ ] Synthesis prompt for background answers with citations

### Dify Intent 4 — Documentation (ES BM25)

- [ ] Index MkDocs pages into `docs` ES index
- [ ] BM25 keyword search (no vector — exact technical terms)
- [ ] Citation-aware response format with doc page links

---

## 🔲 Phase 4 — Production Hardening (Planned)

> **Goal**: Session memory, observability, rate limiting, graceful degradation.

### Tasks

- [ ] **Session context** — keep last 3 turns in memory per session for follow-up questions
- [ ] **Rate limiting** — 10 req/min per user on `/api/jarvis/` endpoints
- [ ] **Dify timeout fallback** — if Dify > 10s → keyword engine + Gemini direct call
- [ ] **Jarvis logs table** in PostgreSQL:
  ```sql
  CREATE TABLE jarvis_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT,
    raw_transcript TEXT,
    refined_transcript TEXT,
    intent_id INTEGER,
    action TEXT,
    latency_ms INTEGER,
    asr_engine TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );
  ```
- [ ] Analytics view: top intents, avg latency per intent, error rate
- [ ] Jarvis dashboard page in FinSight frontend

---

## Architecture Evolution

```
V1 (before Phase 1)          V2 (Phase 1 ✅)            V3 (Phase 2+)
─────────────────────        ──────────────────────       ──────────────────────────
Button press                 Button/VAD auto-stop         VAD streaming (live words)
↓                            ↓                            ↓
MediaRecorder blob    →      MediaRecorder/WAV blob →     PCM audio chunks (100ms)
↓                            ↓                            ↓
POST /voice (block)          POST /voice/stream (SSE) →   WebSocket /ws/jarvis
↓                            ↓                            ↓
Wait 3–8s total              Transcript in ~600ms         Partial words in ~100ms
↓                            ↓                            ↓
Single JSON result           event:transcript             live partial → final →
                             event:response               event:response
                             event:done
```
