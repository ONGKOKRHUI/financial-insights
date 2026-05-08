# FastAPI Architecture

!!! success "Phase 4 — Live"
    The FastAPI application is deployed on Render and accessible at
    `https://finsight-api.onrender.com`.  Phase 4 adds authentication,
    RBAC, Stripe integration, the Jarvis voice assistant, and admin
    management endpoints.

---

## Project Structure

```
src/backend/
├── main.py               # App factory: FastAPI instance, CORS, router registration, lifespan
├── database.py           # SQLAlchemy engine, SessionLocal, get_db dependency
├── models.py             # ORM models (Company, KPISummary, IncomeStatement, BalanceSheet,
│                         #   CashFlow, QualitativeInsight, User, RefreshToken, APIKey)
├── schemas/              # Pydantic request/response schemas (modular by domain)
│   ├── __init__.py       # Re-exports legacy schemas for backwards compatibility
│   └── rag.py            # RAG-specific request/response schemas
├── seed.py               # Idempotent seeder — populates all tables from mock_data on startup
├── requirements.txt      # Runtime dependencies
├── requirements-whisper.txt  # Optional Whisper ASR dependencies
├── Dockerfile            # Local development container image
├── render.yaml           # Render deployment manifest
├── alembic.ini           # Alembic migration configuration
├── alembic/
│   ├── env.py            # Migration environment
│   └── versions/
│       └── 001_add_auth_tables.py  # Phase 4 auth migration
├── auth/
│   ├── __init__.py       # Auth package exports
│   ├── jwt.py            # JWT creation (access/refresh) and validation
│   ├── password.py       # bcrypt hashing, API key generation (SHA-256)
│   └── dependencies.py   # FastAPI deps: get_current_user, require_role, get_api_key_user
├── data/
│   └── mock_data.py      # Static mock data for 8 companies, 5 fiscal years each
├── routers/
│   ├── auth.py           # POST /auth/register|login|refresh|logout
│   ├── users.py          # GET /users/me, GET /users/me/api-key, POST /users/me/api-key/rotate
│   ├── admin.py          # GET/PATCH/DELETE /admin/users (admin-only)
│   ├── companies.py      # GET /companies, /companies/{ticker}, /companies/{ticker}/summary|qualitative
│   ├── financials.py     # GET /financials/{ticker}/income-statement|balance-sheet|cash-flow
│   ├── search.py         # GET /search/live, POST /search (unified query, requires paid/admin)
│   ├── jarvis.py         # Jarvis voice endpoints: /intent/stream, /voice/stream, /tts, /health
│   ├── rag.py            # POST /rag/ask, GET /rag/health (Elasticsearch RAG)
│   └── webhooks.py       # POST /webhooks/stripe (Stripe subscription lifecycle)
├── services/
│   ├── jarvis_intent.py      # Intent engine dispatcher (keyword / langgraph)
│   ├── langgraph_intent.py   # Full LangGraph pipeline: 6 intent nodes
│   ├── financial_query.py    # Intent 2: metric catalog + PostgreSQL lookup
│   ├── rag_retriever.py      # Intent 4: Elasticsearch BM25 + KNN retrieval
│   ├── rag_answer.py         # Intent 4: Gemini grounded answer generation
│   ├── es_client.py          # Shared Elasticsearch client
│   ├── es_docs_index.py      # Elasticsearch index + alias bootstrap (v2 adds autocomplete fields)
│   ├── live_search.py        # Search-as-you-type: lightweight BM25 over autocomplete sub-fields
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
|------------|-----------------------------------------------------|
| CORS       | Origins from `ALLOWED_ORIGINS` env var; `allow_credentials=True`; all methods and headers allowed |

Authentication is enforced at the dependency level (not middleware) via `get_current_user`,
`require_role`, and `require_api_key_or_session` callables injected into route handlers.

---

## Routers

| Router         | Prefix           | Methods            | Auth Required    | Endpoints                                                                 |
|----------------|------------------|--------------------|------------------|---------------------------------------------------------------------------|
| `auth`         | `/auth`          | POST               | No (public)      | register, login, refresh, logout                                          |
| `users`        | `/users`         | GET, POST          | Session cookie   | profile (`GET /me`), API key info (`GET /me/api-key`), rotate (`POST /me/api-key/rotate`) |
| `admin`        | `/admin`         | GET, PATCH, DELETE | Admin role       | user list, update role/status, delete user                                |
| `companies`    | `/companies`     | GET                | No (public)      | list, detail, KPI summary, qualitative insight                            |
| `financials`   | `/financials`    | GET                | No (public)      | income statement, balance sheet, cash flow (per ticker)                   |
| `search`       | `/search`        | GET / POST         | Paid/Admin       | `GET /search/live?q=` — live Elasticsearch suggestions (top 5); `POST /search` — unified payload-based query |
| `jarvis`       | `/api/jarvis`    | POST, GET          | No               | `/intent/stream`, `/voice/stream`, `/tts`, `health`                       |
| `rag`          | `/rag`           | POST / GET         | No               | `/ask` (NL question answering), `/health` — Elasticsearch RAG             |
| `webhooks`     | `/webhooks`      | POST               | Stripe signature | Stripe subscription lifecycle events                                      |

Routers that query the database use `Depends(get_db)` for session injection.
Protected routers additionally use `Depends(get_current_user)` and/or `Depends(require_role(...))`.

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

All data routers use `Depends(get_db)` for database session injection.
Protected routers additionally use `Depends(get_current_user)` and/or `Depends(require_role(...))`.

---

## Authentication & RBAC

Phase 4 implements a cookie-based JWT authentication system:

- **Access Token** — 15-minute JWT stored in `access_token` HttpOnly cookie
- **Refresh Token** — 7-day JWT stored in `refresh_token` HttpOnly cookie, hash persisted in DB
- **API Keys** — `fsk_`-prefixed keys for programmatic access (paid/admin tier), SHA-256 hashed in DB

Role hierarchy: `free` < `paid` < `admin`

See [Authentication](authentication.md) and [RBAC](rbac.md) for details.

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

**`get_current_user`** (in `auth/dependencies.py`) — reads the `access_token`
cookie, decodes the JWT, and returns the `User` ORM object.

**`require_role(*roles)`** (in `auth/dependencies.py`) — factory that returns a
dependency checking `current_user.role in roles`.

**`require_api_key_or_session`** (in `auth/dependencies.py`) — dual-auth dependency
that accepts either a session cookie or an `X-API-Key` header.

Tests override `get_db` with a session bound to an in-memory SQLite engine
(see `tests/conftest.py`).

---

## Database

| Setting          | Value                                                     |
|------------------|-----------------------------------------------------------|
| Production DB    | PostgreSQL on Supabase (connection string via `DATABASE_URL` env var) |
| ORM              | SQLAlchemy 2.x (sync, declarative)                        |
| Migrations       | Alembic — `001_add_auth_tables.py` for Phase 4 auth tables |
| Test DB          | In-memory SQLite with `StaticPool`                        |

The `DATABASE_URL` env var is read in `database.py`. Render's `postgres://` prefix is
automatically converted to `postgresql://` for SQLAlchemy compatibility.

---

## Configuration

All configuration is via environment variables:

| Variable                          | Default                                                    | Description                                               |
|-----------------------------------|------------------------------------------------------------|-----------------------------------------------------------|
| `DATABASE_URL`                    | `postgresql://postgres:postgres@localhost:5432/finsight`   | PostgreSQL connection string                              |
| `ALLOWED_ORIGINS`                 | `http://localhost:3000`                                    | Comma-separated CORS allowed origins                      |
| `SECRET_KEY`                      | *(required)*                                               | JWT signing secret (HS256)                                |
| `ALGORITHM`                       | `HS256`                                                    | JWT algorithm                                             |
| `COOKIE_SECURE`                   | `true`                                                     | Set to `false` for local HTTP dev                         |
| `STRIPE_SECRET_KEY`               | *(required for payments)*                                  | Stripe API secret key                                     |
| `STRIPE_WEBHOOK_SECRET`           | *(required for webhooks)*                                  | Stripe webhook signing secret                             |
| `STRIPE_PRO_PRICE_ID`             | *(required for checkout)*                                  | Stripe Price ID for Pro plan                              |
| `GOOGLE_API_KEY`                  | *(required for Gemini)*                                    | Google AI API key — required for LangGraph + Gemini ASR   |
| `JARVIS_ASR_ENGINE`               | `whisper`                                                  | ASR engine: `whisper` or `gemini`                         |
| `JARVIS_INTENT_ENGINE`            | `langgraph`                                                | Intent engine: `keyword`, `langgraph`, or `dify`          |
| `JARVIS_GEMINI_MODEL`             | `gemini-2.0-flash`                                         | Override Gemini model for Jarvis (fallback: `GEMINI_MODEL`) |
| `JARVIS_TTS_ENGINE`               | `edge`                                                     | TTS engine: `edge` or `google`                            |
| `ELASTICSEARCH_URL`               | `http://localhost:9200`                                    | Elasticsearch host for RAG and live search                |
| `ELASTICSEARCH_DOCS_INDEX`        | `finsight_docs_current`                                    | Elasticsearch alias for RAG docs index and live search    |
| `ELASTICSEARCH_DOCS_INDEX_VERSION`| `v2`                                                       | Physical index version (`v2` adds autocomplete sub-fields) |
| `RAG_EMBEDDING_MODEL`             | `models/gemini-embedding-001`                              | Gemini embedding model for RAG                            |
| `LIVE_SEARCH_SNIPPET_CHARS`       | `160`                                                      | Maximum characters per result snippet in `GET /search/live` |

Production values are set in the Render dashboard. Local development values live
in `.env` (see `.env.example`).

---

## Error Handling

FastAPI's default exception handlers are used:

- **`RequestValidationError`** → HTTP 422 with a `detail` array of field-level errors
- **`HTTPException`** → HTTP status as raised, with a `detail` string
- Unhandled exceptions → HTTP 500

Auth endpoints return descriptive error messages via `HTTPException(status_code=401, detail="...")`.

The `financial_query` service and LangGraph intent handlers never raise HTTP exceptions — they return graceful fallback responses so Jarvis always returns a user-facing message even when data is unavailable.
