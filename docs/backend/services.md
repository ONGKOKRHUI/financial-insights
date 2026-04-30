# Services

!!! success "Phase 4 — Live"
    The services layer includes the Jarvis voice assistant with modular ASR,
    intent classification, and TTS engines.  Financial data services are
    implemented directly in the routers (no separate service class layer).

---

## Service Layer Design

The backend uses a **thin router, inline service** pattern for financial data —
business logic (queries, formatting) lives directly in the router functions
with SQLAlchemy ORM queries.  The Jarvis voice assistant uses a dedicated
service layer because it requires multi-engine orchestration.

---

## Jarvis Voice Assistant Services

The Jarvis voice assistant is composed of three pluggable service modules,
each configurable via environment variables.

### ASR Service (`services/asr.py`)

Converts audio to text using one of two engines:

| Engine | Env Value | Dependencies | Notes |
|--------|-----------|--------------|-------|
| Whisper | `JARVIS_ASR_ENGINE=whisper` | `faster-whisper`, `ctranslate2` | Runs locally, ~1.5 GB RAM, ideal for Docker dev |
| Gemini | `JARVIS_ASR_ENGINE=gemini` | `google-generativeai` | Uses `GOOGLE_API_KEY`, ideal for production |

```python
from services.asr import transcribe_audio

text = transcribe_audio(audio_bytes, content_type="audio/webm")
```

### Intent Classification Service (`services/jarvis_intent.py`)

Maps user transcripts to navigation routes and structured responses:

| Engine | Env Value | Dependencies | Notes |
|--------|-----------|--------------|-------|
| Keyword | `JARVIS_INTENT_ENGINE=keyword` | None | Regex-based, handles all 8 KLSE companies, no external deps |
| LangGraph | `JARVIS_INTENT_ENGINE=langgraph` | `langchain`, `langgraph`, `langchain-google-genai` | Full NLU pipeline with transcript refinement, intent classification, entity extraction |
| Dify | `JARVIS_INTENT_ENGINE=dify` | `requests` | Legacy Dify workflow API (not recommended) |

The keyword engine always runs as a fallback if the primary engine fails.

### TTS Service (`services/tts.py`)

Synthesizes text responses into audio:

| Engine | Env Value | Dependencies | Notes |
|--------|-----------|--------------|-------|
| Edge TTS | `JARVIS_TTS_ENGINE=edge` | `edge-tts` | Microsoft edge-tts, free, no API key needed |
| Google Cloud | `JARVIS_TTS_ENGINE=google` | `google-cloud-texttospeech` | Requires `GOOGLE_TTS_API_KEY` |

### LangGraph Intent Pipeline (`services/langgraph_intent.py`)

When `JARVIS_INTENT_ENGINE=langgraph`, a 6-node LangGraph state machine handles
structured NLU:

```
refine_transcript → classify_intent → [conditional router]
                                        ├── handle_navigation
                                        ├── handle_financial_query
                                        ├── handle_company_info
                                        ├── handle_documentation
                                        ├── handle_small_talk
                                        └── handle_sensitive_topic
```

Each node uses Gemini with structured output (Pydantic models) and Langfuse
callbacks for observability.

---

## Financial Data Access

Financial data is accessed directly via SQLAlchemy queries in the routers:

- **Companies Router** — `db.query(models.Company)` for listing and detail
- **Financials Router** — `db.query(models.IncomeStatement)` etc. with ticker filter
- **Search Router** — Unified query across all statement types via payload-based request

There is no separate `FinancialService` or `CompanyService` class — the router
functions serve as the service layer for these simple CRUD operations.

---

## Planned Services

!!! info "Future Phases"

    | Service | Phase | Description |
    |---------|-------|-------------|
    | SearchService (hybrid) | Phase 5 | pgvector + semantic search |
    | AIAnalysisService | Phase 5 | LLM-powered financial analysis |
    | CacheService | Phase 6 | Redis caching layer |
