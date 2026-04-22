# API Overview

!!! success "Phase 3 — Live"
    The FinSight REST API is live on Render. All endpoints documented here are
    functional and accessible without authentication.

---

## Base URL

```
https://finsight-api.onrender.com
```

Use this URL as the prefix for every request. There is no `/v1/` path prefix —
endpoints are mounted directly at the root (e.g. `/companies`, not `/v1/companies`).

---

## API Design Principles

- **Resource-based routing** — URLs identify resources, HTTP verbs identify actions.
  `GET /companies/MAYBANK` returns a company; `POST /search` queries across tables.
- **Ticker-keyed** — Every resource is addressed by its KLSE ticker symbol (uppercase
  string), not a numeric ID. Path parameters are case-insensitive; the API normalises
  to uppercase internally.
- **No pagination** — The dataset is small (8 companies × 5 years per statement).
  All list endpoints return the full result set.
- **No filtering or sorting query params** — Data volumes are low enough that filtering
  is done client-side. The `POST /search` endpoint accepts a `fiscal_year` to retrieve
  a specific year.
- **Bare JSON responses** — There is no outer `{ "success": true, "data": {} }`
  envelope. Responses are plain JSON objects or arrays matching the Pydantic schemas
  defined in `schemas.py`.

---

## Rate Limits

Rate limiting is **not enforced** in Phase 3. The values below are the planned limits
for Phase 4+ when Redis-backed throttling is added.

| Tier     | Requests / Minute | Requests / Day |
|----------|-------------------|----------------|
| Free     | 10                | 100            |
| Paid     | 300               | 50,000         |
| Internal | Unlimited         | Unlimited      |

---

## Response Format

Responses are bare JSON — no envelope wrapper. Example from `GET /companies/MAYBANK/summary`:

```json
{
  "ticker": "MAYBANK",
  "revenue_bln": 30.2,
  "net_income_bln": 9.1,
  "eps": 0.86,
  "pe_ratio": 12.4,
  "roe_pct": 10.8,
  "roace_pct": 8.2,
  "debt_to_equity": 0.92,
  "dividend_yield_pct": 5.8,
  "fiscal_year": 2024
}
```

Error responses include a `detail` field:

```json
{ "detail": "Company 'XYZ' not found." }
```

Validation errors (HTTP 422) include a `detail` array with field-level messages, as
produced by Pydantic and FastAPI's default exception handler.

---

## Versioning

The API is currently **unversioned** — paths like `/companies` are used directly
rather than `/v1/companies`. URL versioning will be introduced if a breaking change
is required; the existing paths will remain accessible during any deprecation window.

---

## OpenAPI / Swagger

FastAPI auto-generates interactive API documentation:

- **Swagger UI** — `https://finsight-api.onrender.com/docs`
- **ReDoc** — `https://finsight-api.onrender.com/redoc`
- **OpenAPI JSON** — `https://finsight-api.onrender.com/openapi.json`
