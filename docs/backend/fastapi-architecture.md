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
├── schemas.py            # Pydantic request/response schemas
├── seed.py               # Idempotent seeder — populates all tables from mock_data on startup
├── requirements.txt      # Runtime + test dependencies
├── Dockerfile            # Production container image
├── render.yaml           # Render deployment manifest
├── data/
│   └── mock_data.py      # Static mock data for 8 companies, 5 fiscal years each
├── routers/
│   ├── companies.py      # GET /companies, /companies/{ticker}, /companies/{ticker}/summary, /companies/{ticker}/qualitative
│   ├── financials.py     # GET /financials/{ticker}/income-statement|balance-sheet|cash-flow
│   └── search.py         # POST /search (unified query endpoint)
└── tests/
    ├── conftest.py       # SQLite fixtures, dependency override, session-scoped TestClient
    └── test_api.py       # 13 tests covering all endpoints
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

| Router         | Prefix        | Methods   | Endpoints                                                      |
|----------------|---------------|-----------|----------------------------------------------------------------|
| `companies`    | `/companies`  | GET       | list, detail, KPI summary, qualitative insight                 |
| `financials`   | `/financials` | GET       | income statement, balance sheet, cash flow (per ticker)        |
| `search`       | `/search`     | POST      | unified payload-based query across all statement types         |

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

| Variable           | Default                                | Description                             |
|--------------------|----------------------------------------|-----------------------------------------|
| `DATABASE_URL`     | `postgresql://postgres:postgres@localhost:5432/finsight` | PostgreSQL connection string |
| `ALLOWED_ORIGINS`  | `*`                                    | Comma-separated CORS allowed origins    |

Production values are set in the Render dashboard. Local development values live
in `.env` (see `.env.example`).

---

## Error Handling

FastAPI's default exception handlers are used:

- **`RequestValidationError`** → HTTP 422 with a `detail` array of field-level errors
- **`HTTPException`** → HTTP status as raised, with a `detail` string
- Unhandled exceptions → HTTP 500

No custom global exception handler is registered in Phase 3.
