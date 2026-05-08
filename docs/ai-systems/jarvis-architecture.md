# Jarvis — Architecture & Pipeline

## Two-Path Design

Jarvis uses **two paths** depending on browser support:

| Path | Trigger | Transcription | Latency |
|------|---------|---------------|---------|
| **Primary** | Web Speech API available (Chrome/Edge) | Browser-native, live word-by-word | **~50ms** live + ~1–2s intent |
| **Fallback** | Web Speech API unavailable (Firefox) | faster-whisper or Gemini ASR | ~1–3s ASR + ~1–2s intent |

---

## System Architecture

```mermaid
flowchart TD
    subgraph Browser ["Browser (Next.js)"]
        BTN["JarvisButton.tsx"]
        WSA["Web Speech API\nwindow.SpeechRecognition\n(native browser, zero latency)"]
        PANEL["Status Panel\nLive words appear here\nwhile user is still speaking"]
        TTS_PLAY["TTS Playback\nHTML Audio"]
    end

    subgraph Backend ["FastAPI Backend"]
        INTENT_EP["POST /api/jarvis/intent/stream\nPRIMARY — text only, no ASR\n~1–2s total latency"]
        VOICE_EP["POST /api/jarvis/voice/stream\nFALLBACK — audio upload + ASR\n~3–6s total latency"]
        INTENT["Intent Service\njarvis_intent.py\n(keyword regex or LangGraph)"]
        TTS_SVC["TTS Service\ntts.py"]
    end

    subgraph ASR_Engines ["ASR Engines (fallback path only)"]
        WHISPER["faster-whisper\nlarge-v3 int8\n(local/Docker)"]
        GEMINI_ASR["Gemini Audio API\n(production)"]
    end

    subgraph Intent_Engines ["Intent Engines"]
        KW["Keyword Regex\n(instant, default)"]
        LG["LangGraph Pipeline\nRefine → Classify → Route → Handle"]
    end

    BTN -->|"PRIMARY: final transcript text"| WSA
    WSA -->|"Interim words shown live"| PANEL
    WSA -->|"Final text on silence"| INTENT_EP
    INTENT_EP --> INTENT
    INTENT --> KW & LG
    KW & LG -->|"event: response"| BTN
    BTN -->|"FALLBACK: audio blob"| VOICE_EP
    VOICE_EP --> WHISPER & GEMINI_ASR
    WHISPER & GEMINI_ASR -->|"event: transcript"| PANEL
    VOICE_EP --> INTENT
    BTN --> TTS_SVC
    TTS_SVC -->|"MP3 bytes"| TTS_PLAY
```

---

## Request / Response Lifecycle

### Primary Path — Web Speech API (Chrome/Edge)

```
1. User clicks mic → window.SpeechRecognition.start()
2. Browser streams words to panel in real-time as user speaks:
   interim: "naviga"              → dim text, blinking cursor
   interim: "navigate to May"     → updating live
   final:   "navigate to Maybank" → committed bright text
3. User pauses → 2s silence timer → recognition.stop()
4. POST /api/jarvis/intent/stream (FormData: text="navigate to Maybank")
   ↳ NO audio upload, NO ASR — just the text string
5. Backend: keyword regex match → instant result
   OR LangGraph: ~1–2s for intent classification
6. SSE event: response → { action: "navigate", target: "/companies/MAYBANK" }
7. Frontend navigates + plays TTS

Total time from 'stop speaking' to navigation:
  ~200ms (keyword engine) or ~1.5s (LangGraph)
```

### Fallback Path — Audio Upload (Firefox / mobile)

```
1. User clicks mic → MediaRecorder.start()
2. User clicks stop → Blob(chunks, audio/webm)
3. POST /api/jarvis/voice/stream (FormData: file, stop_reason)
4. Backend runs ASR (1–3s)
5. SSE event: transcript → { text: "navigate to Maybank" }  ← shown in panel
6. Backend runs intent classifier
7. SSE event: response → { action: "navigate", ... }

Total time from 'stop speaking' to navigation: ~3–6s
```

---

## Component Map

### Backend

| File | Purpose |
|------|---------|
| `routers/jarvis.py` | FastAPI router — `/intent/stream` (primary) + `/voice/stream` (fallback) + TTS |
| `services/asr.py` | Dual ASR engine: faster-whisper (local) / Gemini (cloud) — fallback path only |
| `services/jarvis_intent.py` | Intent routing: keyword regex (instant) + LangGraph pipeline |
| `services/langgraph_intent.py` | Full LangGraph pipeline: refine → classify → route → 6 handler nodes |
| `services/financial_query.py` | **Intent 2** retrieval: metric catalog, company alias map, PostgreSQL lookup |
| `services/rag_retriever.py` | **Intent 4** retrieval: Elasticsearch hybrid BM25 + KNN search with RRF fusion |
| `services/rag_answer.py` | **Intent 4** answer generation: Gemini grounded answer with source citations |
| `services/tts.py` | Text-to-speech: edge-tts (local) / Google Cloud TTS |

### Frontend

| File | Purpose |
|------|---------|
| `components/ui/JarvisButton.tsx` | Full Jarvis UI — Web Speech API live transcription, SSE intent, TTS playback |

---

## Intent 2 Retrieval Lane (FinancialInfo)

When `intent_id = 2`, the LangGraph node `handle_financial` delegates to `financial_query.query_financial_intent`. No LLM-generated SQL is executed — the service uses a predefined metric catalog and deterministic database queries.

```mermaid
flowchart TD
    userPrompt["User Prompt"] --> refine[refine_transcript]
    refine --> classify[classify_intent]
    classify --> financial[handle_financial]
    financial --> resolveTicker["resolve_ticker(company)"]
    financial --> resolveMetric["resolve_metric(metric_text)"]
    financial --> parseYear["parse_fiscal_year(time_period)"]
    resolveTicker --> lookup["lookup_financial_metric(ticker, spec, fy)"]
    resolveMetric --> lookup
    parseYear --> lookup
    lookup --> postgres[(PostgreSQL)]
    postgres --> response["Grounded Answer + Sources"]
```

### Retrieval lane comparison

| Intent | Handler | Data source | Characteristics |
|---|---|---|---|
| 2 — FinancialInfo | `handle_financial` → `financial_query` | PostgreSQL structured tables | Exact metric/year, deterministic, no LLM SQL |
| 3 — CompanyInfo | `handle_company_info` → `_get_company_profile` | PostgreSQL `companies`, `kpi_summaries`, `qualitative_insights` | Company background, profile lookup |
| 4 — Documentation | `handle_documentation` → `_call_rag` | Elasticsearch hybrid BM25 + KNN | Platform how-to, API questions, text search |

---

## Latency Budget

### Primary Path (Web Speech API — Chrome/Edge)

| Stage | Latency | Notes |
|-------|---------|-------|
| First word appears in panel | **~50ms** | Browser-native, real-time |
| User stops speaking | 0ms | Auto-detected via 2s silence |
| POST text to `/intent/stream` | ~20ms | Just a text string |
| Keyword intent (local regex) | **~5ms** | Pure regex, no network |
| LangGraph intent (cloud) | ~1–2s | 2 LLM calls (refine + classify) |
| Intent 2 PostgreSQL lookup | ~5–20ms | Deterministic DB query, no LLM |
| TTS synthesis + playback | ~400ms | edge-tts |
| **Total (keyword engine)** | **~100ms** | Effectively instant |
| **Total (LangGraph engine)** | **~1.5–3s** | |

### Fallback Path (Audio Upload — Firefox / mobile)

| Stage | Latency | Notes |
|-------|---------|-------|
| Audio upload | 50–200ms | |
| ASR faster-whisper CPU | 1–3s | large-v3 + int8 |
| ASR Gemini Audio API | 300–800ms | Cloud |
| Transcript shown in panel | **~1–3s** | SSE `event: transcript` |
| Keyword intent | ~5ms | |
| LangGraph intent | ~1–2s | |
| **Total (keyword)** | **~1–3s** | |
| **Total (LangGraph)** | **~3–6s** | |

---

## Browser Compatibility

| Browser | Web Speech API | Path Used |
|---------|---------------|-----------|
| Chrome 33+ | Yes | Primary (live transcription) |
| Edge 79+ | Yes | Primary (live transcription) |
| Safari 14.1+ | Partial | Primary (may need prefix) |
| Firefox | No | Fallback (audio upload) |
| Mobile Chrome | Yes | Primary |
| Mobile Safari | Partial | Primary |

---

## Intent Classification

Jarvis uses a **native LangGraph pipeline** (engine: `langgraph`):

1. **Transcript Refinement** — Gemini 2.0 Flash fixes STT artifacts (`"navigate the Maybank"` → `"navigate to Maybank"`)
2. **Intent Classifier** — Gemini 2.0 Flash outputs a `IntentOutput` Pydantic model via `with_structured_output`; no separate JSON parser node required
3. **Conditional Router** — routes `intent_id` 1–6 to the appropriate handler node
4. **Handler nodes** — each intent has a dedicated node; Intent 2 uses `financial_query`, Intent 4 uses Elasticsearch RAG

A legacy `keyword` engine (regex-based, instant) is still supported as a fallback when `GOOGLE_API_KEY` is absent.

See the [Intent Classifier Prompt](./jarvis-intent-classifier.md) for the full system prompt and few-shot examples.
