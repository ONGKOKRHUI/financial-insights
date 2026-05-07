# FastAPI Architecture

!!! success "Phase 3 — Live"
    The FastAPI application is deployed on Render and accessible at
    `https://finsight-api.onrender.com`.

---

## Project Structure

```
src/backend/
├── main.py               # App factory: FastAPI instance, CORS, router registration, lifespan
├── database.py           # SQLAlchemy engine, SessionLocal, get_db dependency
├── models.py             # ORM models (Company, KPISummary, IncomeStatement, BalanceSheet, CashFlow, QualitativeInsight)
├── schemas/              # Pydantic request/response schemas (modular by domain)
│   ├── __init__.py       # Re-exports legacy schemas for backwards compatibility
│   └── rag.py            # RAG-specific request/response schemas
├── seed.py               # Idempotent seeder — populates all tables from mock_data on startup
├── requirements.txt      # Runtime + test dependencies
├── Dockerfile            # Production container image
├── render.yaml           # Render deployment manifest
├── data/
│   └── mock_data.py      # Static mock data for 8 companies, 5 fiscal years each
├── routers/
│   ├── companies.py      # GET /companies, /companies/{ticker}, /companies/{ticker}/summary, /companies/{ticker}/qualitative
│   ├── financials.py     # GET /financials/{ticker}/income-statement|balance-sheet|cash-flow
│   ├── search.py         # POST /search (unified query endpoint — developer API)
│   ├── jarvis.py         # POST /api/jarvis/intent/stream, /voice/stream, /tts
│   └── rag.py            # POST /rag/ask, GET /rag/health (Elasticsearch RAG)
├── services/
│   ├── jarvis_intent.py      # Intent engine dispatcher (keyword / langgraph)
│   ├── langgraph_intent.py   # Full LangGraph pipeline: 6 intent nodes
│   ├── financial_query.py    # Intent 2: metric catalog + PostgreSQL lookup
│   ├── rag_retriever.py      # Intent 4: Elasticsearch BM25 + KNN retrieval
│   ├── rag_answer.py         # Intent 4: Gemini grounded answer generation
│   ├── es_client.py          # Shared Elasticsearch client
│   ├── es_docs_index.py      # Elasticsearch index + alias bootstrap
│   ├── embeddings.py         # Shared embedding client (Gemini)
│   ├── asr.py                # ASR engine (faster-whisper / Gemini Audio)
│   └── tts.py                # Text-to-speech (edge-tts / Google Cloud TTS)
└── tests/
    ├── conftest.py              # SQLite fixtures, dependency override, session-scoped TestClient
    ├── test_api.py              # Core API endpoint tests
    ├── test_rag.py              # RAG endpoint tests (mocked ES + LLM)
    └── test_financial_query.py  # Intent 2 unit + integration tests
```

---

## Application Lifecycle

The app uses FastAPI's `lifespan` context manager (replacing the deprecated `@app.on_event`):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # create tables if not present
    db = SessionLocal()
    try:
        seed_if_empty(db)                   # seed from mock_data if tables are empty
    finally:
        db.close()
    yield                                   # app runs here
```

On first deploy (or after a database reset), this seeds all 8 companies and their
5 years of financial data. Subsequent restarts skip seeding because `seed_if_empty`
checks for an existing row before inserting.

---

## Middleware Stack

| Middleware | Configuration                                      |
|------------|----------------------------------------------------|
| CORS       | Origins from `ALLOWED_ORIGINS` env var (default `*`); methods `GET`, `POST` |

Additional middleware (rate limiter, request logger, auth) is planned for Phase 4+.

---

## Routers

| Router         | Prefix           | Methods      | Endpoints                                                                 |
|----------------|------------------|--------------|---------------------------------------------------------------------------|
| `companies`    | `/companies`     | GET          | list, detail, KPI summary, qualitative insight                            |
| `financials`   | `/financials`    | GET          | income statement, balance sheet, cash flow (per ticker)                   |
| `search`       | `/search`        | POST         | unified payload-based query across all statement types (developer API)    |
| `jarvis`       | `/api/jarvis`    | POST         | `/intent/stream`, `/voice/stream`, `/tts` — Jarvis voice assistant        |
| `rag`          | `/rag`           | POST / GET   | `/ask` (NL question answering), `/health` — Elasticsearch RAG             |

Routers that query the database use `Depends(get_db)` for session injection.

### financial_query service

`services/financial_query.py` is an internal service used by the Jarvis `handle_financial` node. It is **not a router** — it is called directly from `langgraph_intent.py` without going through an HTTP endpoint.

Its responsibilities:

| Function | Description |
|---|---|
| `resolve_ticker(company)` | Normalises a company name to a canonical KLSE ticker using a static alias map + DB fallback |
| `resolve_metric(metric_text)` | Maps natural-language metric phrases to a `MetricSpec` in the metric catalog |
| `parse_fiscal_year(time_period)` | Parses relative/absolute time references to an integer year or `None` (latest) |
| `lookup_financial_metric(ticker, spec, fy)` | Queries the correct SQLAlchemy model using `MetricSpec.statement_type` and returns a `FinancialQueryResult` |
| `query_financial_intent(company, metric, time_period)` | Top-level entry point for `handle_financial` — orchestrates the four functions above |

**Adding a new company** only requires updating `COMPANY_ALIASES` and inserting matching rows into the database. No handler code changes.

**Adding a new metric** requires appending one `MetricSpec` to `METRIC_CATALOG` (and adding the aliases to `_ALIAS_TO_METRIC`) plus an Alembic migration if a new column is needed.

All routers use `Depends(get_db)` for database session injection.

---

## Dependency Injection

**`get_db`** (in `database.py`) — yields a `SessionLocal` session and closes it
after the request completes:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Tests override this dependency with a session bound to an in-memory SQLite engine
(see `tests/conftest.py`).

---

## Database

| Setting          | Value                                                     |
|------------------|-----------------------------------------------------------|
| Production DB    | PostgreSQL on Supabase (connection string via `DATABASE_URL` env var) |
| ORM              | SQLAlchemy 2.x (sync, declarative)                        |
| Migrations       | None — `create_all` at startup; schema is stable          |
| Test DB          | In-memory SQLite with `StaticPool`                        |

The `DATABASE_URL` env var is read in `database.py`. Render's `postgres://` prefix is
automatically converted to `postgresql://` for SQLAlchemy compatibility.

---

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/finsight` | PostgreSQL connection string |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS allowed origins |
| `GOOGLE_API_KEY` | — | Required for LangGraph intent engine (Gemini) |
| `JARVIS_INTENT_ENGINE` | `keyword` | `keyword` or `langgraph` or `dify` |
| `JARVIS_GEMINI_MODEL` | — | Override Gemini model for Jarvis (fallback: `GEMINI_MODEL`) |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch host for RAG |
| `ELASTICSEARCH_DOCS_INDEX` | `finsight_docs_current` | Elasticsearch alias for RAG docs index |
| `RAG_EMBEDDING_MODEL` | `models/gemini-embedding-001` | Gemini embedding model for RAG |

Production values are set in the Render dashboard. Local development values live
in `.env` (see `.env.example`).

---

## Error Handling

FastAPI's default exception handlers are used:

- **`RequestValidationError`** → HTTP 422 with a `detail` array of field-level errors
- **`HTTPException`** → HTTP status as raised, with a `detail` string
- Unhandled exceptions → HTTP 500

The `financial_query` service and LangGraph intent handlers never raise HTTP exceptions — they return graceful fallback responses so Jarvis always returns a user-facing message even when data is unavailable.
