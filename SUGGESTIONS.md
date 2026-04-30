# FinSight — Bug Report & Technical Suggestions

> Auto-generated repository audit · 2026-04-30

---

## 🐛 Hidden Bugs (Functional Issues)

### BUG-1 · `parser.py` — `asyncio.run()` inside LangGraph node will crash in async contexts

**File:** `src/pipeline/nodes/parser.py` L98  
**Severity:** 🔴 Critical  
**Impact:** Pipeline fails when invoked from any async context (e.g., Airflow's `PythonOperator` running in an async event loop, or direct `await` calls).

`parse_pdf()` calls `asyncio.run(_llamaparse(pdf_path))` which creates a new event loop. If the caller is already inside an event loop (common in Airflow 2.9+ and FastAPI), this raises `RuntimeError: This event loop is already running`.

**Fix:** Use `asyncio.get_event_loop().run_until_complete()` or, better, refactor `parse_pdf` to be `async` and `await _llamaparse()` directly. Alternatively, use `nest_asyncio` as a quick patch.

---

### BUG-2 · `parser.py` — LlamaParse failure raises RuntimeError but also appends to errors list (dead code)

**File:** `src/pipeline/nodes/parser.py` L101-103  
**Severity:** 🟡 Medium  
**Impact:** Line 101 appends the error to `errors`, but line 103 immediately raises `RuntimeError`, so the appended error is never returned to the caller — the errors list is lost.

**Fix:** Either raise the exception (and don't append to errors), or append to errors and return gracefully (don't raise). Currently the behavior is contradictory.

---

### BUG-3 · `merger.py` — Returns `{**state, ...}` which conflicts with LangGraph's parallel reducer

**File:** `src/pipeline/nodes/merger.py` L97-101  
**Severity:** 🟡 Medium  
**Impact:** The `merge_and_validate` node returns `{**state, "validated_payload": ..., "errors": errors}` which spreads the entire state back. In a LangGraph parallel fan-in, this could overwrite keys from the other branch's output. The `errors` key uses an `operator.add` reducer, so returning the full accumulated `errors` list (which includes errors from both branches) causes **duplicate errors** because LangGraph will `add` the returned list to the already-accumulated list.

**Fix:** Return only the keys this node writes: `{"validated_payload": validated_payload, "errors": []}` (only append *new* errors from this node, not re-return existing ones).

---

### BUG-4 · `quantitative.py` — Extraction does NOT call `normalize_financial_data` 

**File:** `src/pipeline/nodes/quantitative.py` L202-232  
**Severity:** 🔴 Critical  
**Impact:** The `extract_quantitative` node extracts data as `FinancialValue` dicts (with `raw_value` and `unit_header`), but never calls `normalize_financial_data()` before returning. This means the `quantitative_data` dict contains nested `FinancialValue` objects, not floats. Downstream, `merger.py` passes these dicts directly to Pydantic schemas that expect `Optional[float]` — causing **ValidationError** on every field.

The `normalize_financial_data` function exists at L283 but is never invoked in the pipeline. The merger's `_build_statement` will silently strip all invalid fields, resulting in **all quantitative data being lost** (all `None` values in the database).

**Fix:** Call `quantitative_data = normalize_financial_data(quantitative_data)` before returning from `extract_quantitative`.

---

### BUG-5 · `router.py` — Returns `{**state, ...}` which duplicates errors via the reducer

**File:** `src/pipeline/nodes/router.py` L33-38  
**Severity:** 🟡 Medium  
**Impact:** Same issue as BUG-3. The `route_content` node spreads `**state` back, which includes the `errors` list from `parse_pdf`. Since `errors` uses an `operator.add` reducer, LangGraph will add the returned errors to the accumulated state, duplicating all prior errors.

**Fix:** Return only the keys this node writes: `{"table_markdown": ..., "narrative_markdown": ..., "errors": []}`.

---

### BUG-6 · `auth/dependencies.py` — Refresh token accepted as access token

**File:** `src/backend/auth/dependencies.py` (in `get_current_user`)  
**Severity:** 🟡 Medium  
**Impact:** The `get_current_user` dependency decodes the `access_token` cookie but does not verify that the token is actually an access token (not a refresh token). If a refresh token were accidentally placed in the `access_token` cookie, it would be accepted as valid authentication. The JWT payload contains a `type` field (`"access"` or `"refresh"`) but `get_current_user` does not check it.

**Fix:** Add `if payload.get("type") != "access": raise HTTPException(401)` after decoding.

---

### BUG-7 · `webhooks.py` — Stripe customer lookup by email has a race condition

**File:** `src/backend/routers/webhooks.py`  
**Severity:** 🟡 Medium  
**Impact:** The webhook handler looks up users by `email` from the Stripe event. If a user changes their email between checkout creation and webhook delivery, the lookup fails silently (`user` is `None`), and the subscription upgrade is lost.

**Fix:** Store `stripe_customer_id` on the user record at checkout creation time, and look up by `stripe_customer_id` in the webhook handler instead of email.

---

### BUG-8 · `loader.py` — `_clean()` strips `ticker` and `fiscal_year` but UPSERT helpers inject them separately — **OK if data has no extra keys, but** `None` values cause SQL parameter errors

**File:** `src/db/loader.py` L204-226  
**Severity:** 🟡 Medium  
**Impact:** If the pipeline produces a statement dict with `None` values for numeric columns (e.g., `{"revenue_bln": None, "eps": None}`), these `None` values are passed directly into the `INSERT` SQL as parameters. PostgreSQL accepts `NULL` for nullable columns, so this isn't a crash — but it means **the UPSERT will overwrite existing good data with NULLs** if a re-run produces partial extraction results.

**Fix:** Either skip `None` values in the UPSERT, or use `COALESCE(EXCLUDED.col, col)` in the ON CONFLICT clause to preserve existing data.

---

### BUG-9 · `middleware.ts` — JWT expiry not checked in middleware

**File:** `frontend/src/middleware.ts` L46-54  
**Severity:** 🟢 Low (UX issue, not security — backend verifies)  
**Impact:** The middleware decodes the JWT but doesn't check the `exp` claim. An expired access token will still pass the middleware's `isAuthenticated` check, causing the user to see the protected page briefly before the backend rejects the API call. This creates a flicker/flash of content.

**Fix:** Add `if (payload.exp && Date.now() / 1000 > payload.exp) return null;` in `decodeJwtPayload`.

---

### BUG-10 · `api.ts` — `apiKeyInfo` and `rotateApiKey` use identical HTTP method and path

**File:** `frontend/src/lib/api.ts` L140-147  
**Severity:** 🟢 Low  
**Impact:** Both `apiKeyInfo()` and `rotateApiKey()` POST to `/users/api-key`. They cannot be distinguished — the user will always rotate the key when trying to fetch info. The backend's `/users/me/api-key` is a GET endpoint, but the BFF calls it with POST.

**Fix:** `apiKeyInfo` should use `fetchJSON("/users/api-key")` (GET) instead of `mutateJSON`.

---

## ⚠️ Architecture & Design Suggestions

### SUGGEST-1 · Add rate limiting to auth endpoints

**Files:** `src/backend/routers/auth.py`  
**Priority:** 🔴 High  
**Rationale:** The `/auth/login` and `/auth/register` endpoints have no rate limiting. An attacker can brute-force passwords or spam registrations. Since passwords are system-generated (20 bytes), brute-forcing is unlikely, but the registration endpoint creates database records.

**Recommendation:** Add `slowapi` or a custom middleware with per-IP rate limits: 5 attempts/min for login, 3 registrations/hour.

---

### SUGGEST-2 · Add request/response logging middleware

**Files:** `src/backend/main.py`  
**Priority:** 🟡 Medium  
**Rationale:** There is no structured request logging. Failed API calls, slow queries, and error patterns are invisible in production.

**Recommendation:** Add a middleware that logs method, path, status code, duration, and user ID (if authenticated). Use `structlog` for JSON formatting. Integrate with a log aggregation service.

---

### SUGGEST-3 · The `search.py` router does N+1 query patterns

**File:** `src/backend/routers/search.py` L50-169  
**Priority:** 🟡 Medium  
**Rationale:** The unified search endpoint makes separate DB queries for each requested data type (income, balance, cashflow, kpi, qualitative). For a single-company request this is fine, but for multi-company searches this creates N queries per type.

**Recommendation:** Use SQLAlchemy `joinedload` or batch queries with `IN` clauses to reduce round-trips.

---

### SUGGEST-4 · Add database connection pool monitoring

**File:** `src/backend/database.py`  
**Priority:** 🟡 Medium  
**Rationale:** The SQLAlchemy engine uses default pool settings. Under load, connection exhaustion will crash the app silently. There's no monitoring of pool utilization.

**Recommendation:** Set explicit `pool_size`, `max_overflow`, `pool_timeout`, and `pool_recycle` values. Add a `/health/db` endpoint that reports pool stats.

---

### SUGGEST-5 · Frontend BFF routes have repetitive proxy boilerplate

**Files:** `frontend/src/app/api/**/*.ts`  
**Priority:** 🟢 Low  
**Rationale:** Each BFF route handler manually constructs the backend URL, forwards cookies, and proxies responses. This is ~30 lines of nearly identical code per file.

**Recommendation:** Create a `proxyToBackend(req, backendPath, options?)` utility and reuse it across all BFF routes to reduce boilerplate and ensure consistent error handling.

---

### SUGGEST-6 · Add TypeScript strict mode

**File:** `frontend/tsconfig.json`  
**Priority:** 🟢 Low  
**Rationale:** TypeScript strict mode (`"strict": true`) catches common errors at compile time. The current config doesn't enforce `noUncheckedIndexedAccess`, `strictNullChecks`, or `noImplicitAny`.

**Recommendation:** Enable strict mode and fix any resulting type errors. This will prevent runtime `undefined` crashes in the frontend.

---

### SUGGEST-7 · Scraper modules lack timeout configuration for per-company pages

**Files:** `src/scraper/scrapers/*.py`  
**Priority:** 🟢 Low  
**Rationale:** Only Maybank has robust retry/timeout logic. Other scraper modules may have simpler error handling and can hang indefinitely on unresponsive IR pages.

**Recommendation:** Apply the same retry + timeout pattern from `maybank.py` as a base class or shared utility for all scrapers.

---

### SUGGEST-8 · Add health check endpoint for pipeline/DB loader

**File:** `src/db/loader.py`  
**Priority:** 🟢 Low  
**Rationale:** There's no way to verify that the pipeline's DB connection is working without running a full pipeline. The Airflow DAG will fail silently if `DATABASE_URL` is misconfigured.

**Recommendation:** Add a `check_connection()` function that runs a simple `SELECT 1` and is called at DAG startup.

---

### SUGGEST-9 · `_unit_multiplier` regex is too greedy

**File:** `src/pipeline/nodes/quantitative.py` L268-280  
**Priority:** 🟡 Medium  
**Rationale:** The regex `(thousand|'000|000)` will match any string containing "000" — including "RM 1,000,000" or "200,000". This could misidentify the unit multiplier for edge-case unit headers. The regex for billions `(billion|'bil|b$)` would match any header ending in "b".

**Recommendation:** Use more specific patterns: `r"('000|rm\s*'?000|thousands?)"` and `r"(billions?|rm\s*'?bil)"` with word boundaries.

---

### SUGGEST-10 · Add graceful degradation for Langfuse unavailability

**Files:** `src/pipeline/nodes/quantitative.py`, `src/pipeline/nodes/qualitative.py`  
**Priority:** 🟢 Low  
**Rationale:** Both nodes already handle Langfuse being unavailable (returning `None` and using an empty callbacks list). However, the warning is logged once per node call. In a high-volume pipeline run, this generates excessive log noise.

**Recommendation:** Cache the Langfuse availability check (e.g., module-level flag) so the warning is logged only once per process.

---

## 📊 Documentation Gaps Found

| Doc File | Issue | Status |
|---|---|---|
| `docs/backend/fastapi-architecture.md` | Lists only 3 routers (companies, financials, search) — missing auth, users, admin, webhooks, jarvis (5 routers added in Phase 4) | ⚠️ Outdated |
| `docs/backend/fastapi-architecture.md` | Middleware table says "Additional middleware (rate limiter, request logger, auth) is planned for Phase 4+" but Phase 4 auth is now implemented | ⚠️ Outdated |
| `docs/backend/fastapi-architecture.md` | Config table lists only 2 env vars — missing SECRET_KEY, COOKIE_SECURE, STRIPE_*, JARVIS_* | ⚠️ Outdated |
| `docs/backend/services.md` | Entirely placeholder — HTML comments instead of content, references non-existent class-based service layer | ⚠️ Outdated |
| `docs/architecture/system-architecture.md` | Component table marks pgvector as "✅ Current" but it's not implemented | ⚠️ Incorrect |
| `docs/architecture/system-architecture.md` | Service Boundaries, Infrastructure, Security sections are empty HTML comments | ⚠️ Incomplete |
| `docs/index.md` | Tech stack mentions Elasticsearch, Redis, pgvector — none are implemented | ⚠️ Misleading |
| `README.md` | Project structure section doesn't list auth/, services/, alembic/ directories | ⚠️ Outdated |
| `README.md` | Env variables table missing Phase 4 vars (SECRET_KEY, STRIPE_*, COOKIE_SECURE) | ⚠️ Outdated |
| `README.md` | AI Engine listed as "planned" — Jarvis voice assistant is fully implemented | ⚠️ Outdated |

---

## 🔒 Security Recommendations

| # | Issue | Priority |
|---|---|---|
| SEC-1 | No rate limiting on `/auth/login` — vulnerable to credential stuffing | 🔴 High |
| SEC-2 | API keys are returned in full once and never stored — good practice, but no key rotation notification mechanism | 🟡 Medium |
| SEC-3 | Stripe webhook endpoint doesn't validate that the event hasn't been processed before (replay protection) | 🟡 Medium |
| SEC-4 | `COOKIE_SECURE` defaults to `true` but `.env.example` sets it to `false` — easy to deploy insecurely | 🟢 Low |
| SEC-5 | Admin user creation requires manual DB access — no admin bootstrap endpoint or CLI command | 🟢 Low |

---

## 🧪 Testing Recommendations

| # | Suggestion | Priority |
|---|---|---|
| TEST-1 | Backend unit tests don't cover auth routers, admin routers, or webhook handlers | 🔴 High |
| TEST-2 | No pipeline node unit tests in `src/backend/tests/` — pipeline tests are only integration-level | 🟡 Medium |
| TEST-3 | Frontend has no test setup (no Jest/Vitest config, no component tests) | 🟡 Medium |
| TEST-4 | Integration tests require live backend — add a CI-compatible mock server or use `httpx` AsyncClient | 🟢 Low |
