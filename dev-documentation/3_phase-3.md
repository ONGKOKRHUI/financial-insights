### Phase 3: Backend API Hardening, Testing & Documentation (Weeks 8-11) (Monash W8-11)

**Focus:** Production-quality REST API, automated test coverage, and developer-facing documentation.

---

## What Was Built

### 1. Backend API Hardening (`src/backend/`)

- Bumped FastAPI app version to `1.0.0`
- Added `openapi_tags` metadata for a richer Swagger UI experience
- Added new **`POST /search`** unified query endpoint (`src/backend/routers/search.py`) — accepts `{ ticker, statement_type, fiscal_year }` and dispatches to the correct DB table, returning a consistent JSON envelope
- Added `httpx`, `pytest`, and `pytest-asyncio` to `requirements.txt` for CI-compatible test execution

### 2. Automated Test Suite (`tests/`)

- **`tests/conftest.py`** — pytest fixtures: in-memory SQLite engine, seeded test DB session, `TestClient` with dependency-overridden DB (no live PostgreSQL required)
- **`tests/test_api.py`** — 13 test cases covering all 7 existing GET endpoints plus the new `POST /search` endpoint

| Test | Endpoint | Scenario |
|---|---|---|
| `test_health` | `GET /health` | Returns `{"status": "ok"}` |
| `test_list_companies` | `GET /companies` | 8 companies, correct schema |
| `test_get_company_valid` | `GET /companies/MAYBANK` | Full `CompanyDetail` returned |
| `test_get_company_invalid` | `GET /companies/INVALID` | 404 + detail message |
| `test_kpi_summary` | `GET /companies/MAYBANK/summary` | KPI fields present, fiscal_year correct |
| `test_income_statement` | `GET /financials/MAYBANK/income-statement` | 5-year array returned |
| `test_balance_sheet` | `GET /financials/CIMB/balance-sheet` | Correct schema |
| `test_cash_flow` | `GET /financials/TNB/cash-flow` | Correct schema |
| `test_qualitative` | `GET /companies/MAYBANK/qualitative` | `key_strategic_events` is a list |
| `test_search_income` | `POST /search` | `MAYBANK` income_statement returns correct data |
| `test_search_kpi` | `POST /search` | `CIMB` kpi returns latest year |
| `test_search_invalid_ticker` | `POST /search` | 404 for unknown ticker |
| `test_search_invalid_type` | `POST /search` | 422 validation error for bad `statement_type` |

### 3. Frontend `/api-docs` Page (`frontend/src/app/api-docs/page.tsx`)

Interactive, developer-facing API documentation page hosted within the Next.js app:
- Sticky sidebar navigation
- Endpoint cards with `curl` / Python / JavaScript code tabs
- Real JSON response excerpts from the live API
- HTTP error reference table
- Live "Try It" widget — enter a ticker, select an endpoint, fires a real `fetch()`, displays the JSON response inline
- Navbar updated with "API Docs" link
- Homepage hero CTA updated: second button "View API Docs →" added; badge updated to `Phase 3 — API Now Live`

### 4. MkDocs Documentation (`docs/api-reference/`)

- `overview.md` — real base URL, REST design principles, rate limits table, actual response envelope format, versioning note
- `endpoints.md` — full documentation for all 7 GET endpoints + `POST /search`
- `examples.md` — working `curl`/Python/JS examples using the live Render URL; `POST /search` examples added
- `authentication.md` — documents current open-API state; API key auth planned for Phase 4
- `fastapi-architecture.md` — accurate router structure, CORS config, and seeding logic

---

## Design Decisions

**Why a unified `POST /search` endpoint?**
External developers (algorithmic traders, data consumers) often prefer a single parameterized endpoint over memorizing 5+ GET paths. `POST /search` accepts `{ ticker, statement_type, fiscal_year }` and returns consistent JSON regardless of which table was queried. The existing GET endpoints remain live for direct browser/curl use.

**Why SQLite for tests?**
Tests must run in CI without a live Supabase/PostgreSQL connection. All SQLAlchemy queries use standard ORM syntax compatible with both dialects. The in-memory SQLite fixture seeds the same data shape as production, giving high confidence in correctness without infrastructure cost.

**pgvector and Elasticsearch are NOT in Phase 3.**
Advanced vector/keyword search infrastructure is deferred to Phase 5, where it will power the AI chatbot's RAG pipeline. Phase 3's MVP milestone is: *a robust, tested, documented REST API for financial data retrieval* — no embedding or search engine needed for that.

---

## How to Run Tests

```bash
# From the project root, with the venv active:
cd src/backend
pip install pytest httpx pytest-asyncio

pytest tests/ -v
# Expected: 13 passed, 0 failed
```

---

## Milestone

> **A robust FastAPI backend capable of querying precise financial metrics, with tests proving it works, and documentation explaining how to use it.**

***Builds the API product.***
