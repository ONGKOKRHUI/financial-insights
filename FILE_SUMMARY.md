# FinSight — Complete File Summary

> Auto-generated repository audit · 2026-04-30

---

## Root Directory

| File | Purpose |
|---|---|
| `README.md` | Project overview, tech stack, quick-start guide, production deployment instructions (Vercel/Render/Supabase), CI/CD secrets reference |
| `.env.example` | Comprehensive env-var template covering DB, CORS, auth (Phase 4), Stripe, Gemini, LlamaParse, Langfuse, Jarvis ASR/TTS/Intent, Airflow, and pipeline engine toggles |
| `.gitignore` | Git ignore rules for Python/Node artifacts |
| `Makefile` | Minimal makefile (currently only contains a placeholder target) |
| `mkdocs.yml` | MkDocs Material configuration — theme, nav tree, markdown extensions, plugins for the project documentation site |
| `docker-compose.yml` | Local dev stack: PostgreSQL 16, FastAPI backend, Next.js frontend — three-service orchestration |
| `docker-compose.airflow.yml` | Standalone Airflow stack (LocalExecutor) with separate metadata DB on port 5433, webserver, scheduler, and init container that installs pipeline deps |
| `package.json` | Root-level Node package (only dependency: `concurrently` for running frontend+backend together) |
| `requirements.txt` | Root-level Python requirements (mkdocs + plugins for documentation) |
| `readme_jarvis.md` | Standalone Jarvis voice assistant documentation (architecture, endpoints, setup) |
| `results_sunway_2021_q1.json` | Sample pipeline output JSON for Sunway 2021 Q1 — used for manual validation |

---

## `src/backend/` — FastAPI Backend

| File | Purpose |
|---|---|
| `main.py` | FastAPI app factory — registers all 8 routers (auth, users, admin, webhooks, companies, financials, search, jarvis), configures CORS with credentials, lifespan handler creates tables and seeds mock data |
| `database.py` | SQLAlchemy engine creation from `DATABASE_URL`, `SessionLocal` factory, `get_db` dependency generator; auto-converts Render's `postgres://` to `postgresql://` |
| `models.py` | 9 ORM models: `Company`, `KPISummary`, `IncomeStatement`, `BalanceSheet`, `CashFlow`, `QualitativeInsight` (Phase 2), `User`, `RefreshToken`, `APIKey` (Phase 4) |
| `schemas.py` | Pydantic response schemas for company data, KPIs, financial statements, qualitative insights |
| `seed.py` | Idempotent seeder — populates all 6 financial tables from `mock_data.py` if `companies` table is empty |
| `Dockerfile` | Python 3.12-slim image with ffmpeg (for Whisper), installs base + whisper requirements, runs uvicorn |
| `render.yaml` | Render IaC manifest for the `finsight-api` web service (build/start commands, env vars, health check) |
| `alembic.ini` | Alembic migration config pointing to `alembic/` directory |
| `runtime.txt` | Python version pin (`python-3.12`) for Render |
| `requirements.txt` | Backend Python deps: FastAPI, SQLAlchemy, psycopg2, python-jose, bcrypt, stripe, pydantic, etc. |
| `requirements-whisper.txt` | Optional deps for local Whisper ASR: faster-whisper, CTranslate2 |
| `.env.example` | Backend-specific env template (subset of root `.env.example`) |
| `.python-version` | Python version file (`3.12`) |
| `__init__.py` | Package marker |

### `src/backend/routers/`

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `auth.py` | Auth router (`/auth/**`) — register (system-generated password), login (sets HttpOnly JWT cookies), refresh (rotates access token), logout (revokes refresh token). Cookie config is env-driven (`COOKIE_SECURE`) |
| `users.py` | User router (`/users/**`) — GET profile, GET API key info, POST rotate API key. Requires `paid`/`admin` role for key operations |
| `admin.py` | Admin router (`/admin/**`) — paginated user list, PATCH role/active status, DELETE user. All endpoints require `admin` role |
| `companies.py` | Companies router (`/companies/**`) — list all, get detail by ticker, get KPI summary, get qualitative insight. Parses `key_strategic_events` from JSON string |
| `financials.py` | Financials router (`/financials/**`) — income statement, balance sheet, cash flow history per ticker. Uses `_get_company_or_404` helper |
| `search.py` | Search router (`POST /search`) — unified payload-based query across all 5 statement types. Requires `paid`/`admin` via `require_api_key_or_session` |
| `jarvis.py` | Jarvis voice assistant router (`/api/jarvis/**`) — text intent stream (SSE), audio voice stream (SSE), legacy blocking endpoint, TTS synthesis, health check |
| `webhooks.py` | Stripe webhook handler (`/webhooks/stripe`) — verifies signature, handles `checkout.session.completed` (upgrade to paid), `customer.subscription.deleted` (downgrade to free), `invoice.payment_failed` (downgrade) |

### `src/backend/auth/`

| File | Purpose |
|---|---|
| `__init__.py` | Package docstring listing exports |
| `jwt.py` | JWT utilities — create access token (15min), create refresh token (7d), decode/verify, type checkers (`is_access_token`, `is_refresh_token`). Uses `python-jose` with HS256 |
| `password.py` | Password utilities — bcrypt hash/verify, `generate_secure_password` (20-byte `secrets.token_urlsafe`), SHA-256 API key hashing, `generate_api_key` (returns `fsk_` prefixed key) |
| `dependencies.py` | FastAPI dependency callables — `get_current_user` (cookie-based), `require_role(*roles)` (RBAC decorator), `get_api_key_user` (X-API-Key header), `require_api_key_or_session` (dual-auth for search) |

### `src/backend/services/`

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `asr.py` | ASR service — supports `whisper` (local faster-whisper) and `gemini` (Google Gemini Audio API) engines. Lazy-loads Whisper model. Configurable via `JARVIS_ASR_ENGINE` |
| `jarvis_intent.py` | Intent mapping service — supports `keyword` (regex patterns for 8 KLSE companies + sections), `langgraph` (full NLU pipeline), and `dify` (legacy workflow API) engines. Always falls back to keyword |
| `langgraph_intent.py` | Full LangGraph intent pipeline — 6-node graph: refine_transcript → classify_intent → conditional router to handle_navigation/financial/company_info/documentation/small_talk/sensitive. Uses Gemini with structured output |
| `tts.py` | TTS service — supports `edge` (Microsoft edge-tts, free) and `google` (Google Cloud TTS API) engines. Returns raw MP3 bytes |

### `src/backend/data/`

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `mock_data.py` | ~45KB of static mock data for 8 Malaysian companies (Maybank, CIMB, TNB, Petronas, Maxis, TM, Genting, Sunway) — company profiles, KPIs, 5 years of income statements, balance sheets, cash flows, qualitative insights |

### `src/backend/alembic/`

| File | Purpose |
|---|---|
| `env.py` | Alembic environment config — reads `DATABASE_URL`, imports `Base.metadata` for autogenerate |
| `script.py.mako` | Alembic migration template |
| `versions/001_add_auth_tables.py` | Initial migration adding `users`, `refresh_tokens`, `api_keys` tables (Phase 4) |

### `src/backend/tests/`

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `conftest.py` | Test fixtures — in-memory SQLite with StaticPool, seeds mock data, overrides `get_db`, session-scoped TestClient (no lifespan to avoid PG connection) |
| `test_api.py` | 13 unit tests covering companies list/detail, KPI summary, qualitative insights, financials (income/balance/cash), search endpoint, health checks |

---

## `src/pipeline/` — ETL Pipeline (LangGraph)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker with module docstring |
| `graph.py` | LangGraph state machine — supports `langgraph` (native nodes) and `dify` (Dify workflow) engines. CLI entry point (`--pdf`, `--output`). Builds sequential graph: parse_pdf → route_content → [extract_quantitative ∥ extract_qualitative] → merge_and_validate |
| `state.py` | `PipelineState` TypedDict — shared state with `errors` as an Annotated reducer for safe parallel writes |
| `schemas.py` | Pydantic v2 schemas for pipeline output — `FinancialReportPayload` envelope with optional sub-schemas for each financial statement type |
| `dify_client.py` | Dify Workflow API client — sends parsed markdown to Dify, retries up to 3 times, normalises output to `FinancialReportPayload` structure |
| `requirements.txt` | Pipeline-specific deps: langchain, langgraph, langfuse, llama-cloud, pymupdf, etc. |

### `src/pipeline/nodes/`

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `parser.py` | `parse_pdf` node — LlamaParse (async API) primary, PyMuPDF fallback. Extracts metadata (ticker, year, quarter) from filename convention `{TICKER}_{YEAR}_{QUARTER}.pdf` |
| `router.py` | `route_content` node — passes full markdown to both quantitative and qualitative branches unchanged (relies on Gemini's 1M-token context window) |
| `quantitative.py` | `extract_quantitative` node — 4 structured LLM extraction calls (income statement, balance sheet, cash flow, KPI) using Gemini with Langfuse callbacks. Includes `FinancialValue` two-stage container and `normalize_financial_data` post-processor for unit conversion to MYR billions |
| `qualitative.py` | `extract_qualitative` node — finds narrative sections (MD&A, Chairman's Statement, Outlook) via regex, extracts `future_outlook` and `key_strategic_events` using structured LLM output |
| `merger.py` | `merge_and_validate` node — assembles `FinancialReportPayload` from both branches, validates with Pydantic, handles partial failures gracefully |

---

## `src/db/` — Database Loader

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `loader.py` | PostgreSQL UPSERT loader — `upsert_report(payload)` writes to all 5 financial tables with ON CONFLICT DO UPDATE. `mark_processed` tracks pipeline runs. `get_unprocessed_pdfs` scans for new PDFs. `ensure_pipeline_runs_table` creates tracking DDL |

---

## `src/scraper/` — Web Scraper

| File | Purpose |
|---|---|
| `main.py` | Scraper orchestrator — configures 8 companies (Maybank, Sunway, Genting, TM, Maxis, Petronas, TNB, CIMB) with date ranges 2020-2025. Supports backfill mode and `--latest` for new-release checks. Uses Playwright with stealth and WebGL spoofing |
| `scheduler.py` | APScheduler wrapper — runs `main.py --latest` every Monday at 09:00 AM (KL time) + once on startup |
| `README.md` | Scraper documentation |
| `requirements.txt` | Scraper deps: playwright, playwright-stealth, schedule |
| `scraper.log` | Runtime log file (~165KB) |

### `src/scraper/scrapers/`

| File | Purpose |
|---|---|
| `__init__.py` | Package marker importing all 8 scraper modules |
| `maybank.py` | Maybank IR scraper — navigates quarterly announcements page, handles Imperva WAF with scroll simulation, retry logic, and PDF validation |
| `cimb.py` | CIMB Group quarterly report scraper |
| `tnb.py` | Tenaga Nasional quarterly report scraper |
| `petronas.py` | Petronas Chemicals quarterly report scraper |
| `maxis.py` | Maxis quarterly report scraper |
| `telekom.py` | Telekom Malaysia quarterly report scraper |
| `genting.py` | Genting Berhad quarterly report scraper |
| `sunway.py` | Sunway Group quarterly report scraper |
| `maybank_test.py` | Standalone test script for Maybank scraper |

---

## `dags/` — Airflow DAGs

| File | Purpose |
|---|---|
| `finsight_etl_dag.py` | Daily ETL DAG: `check_new_pdfs` → `trigger_parse_pipeline` → `load_to_postgres`. Scans scraper output dir, runs pipeline for each unprocessed PDF, upserts results to PostgreSQL. 3 retries with 5-min delay |

---

## `frontend/` — Next.js Web Application

| File | Purpose |
|---|---|
| `package.json` | Next.js 15 + React 19 + TypeScript, TailwindCSS v4, TanStack Query, Zustand, Recharts |
| `next.config.ts` | Next.js config with `output: "standalone"` for Docker, image domain whitelist |
| `tsconfig.json` | TypeScript config with `@/` path alias |
| `vercel.json` | Vercel deployment config with rewrite rules |
| `Dockerfile` | Multi-stage Docker build (deps → build → standalone runner) |
| `.env.example` | Frontend env template (`NEXT_PUBLIC_API_URL`) |
| `.env.local.example` | Local dev env template (includes `INTERNAL_API_URL`, Stripe keys) |
| `eslint.config.mjs` | ESLint flat config for Next.js |
| `postcss.config.mjs` | PostCSS config for TailwindCSS |

### `frontend/src/`

| File | Purpose |
|---|---|
| `middleware.ts` | Edge middleware — route-level access control. Decodes JWT (no signature verification) for role-based redirects. Public: `/companies/**`. Protected: `/dashboard` (paid/admin), `/admin` (admin only) |

### `frontend/src/app/` — Pages

| File | Purpose |
|---|---|
| `layout.tsx` | Root layout — Inter font, Providers wrapper, Header, Footer, JarvisButton |
| `globals.css` | Global CSS with TailwindCSS imports |
| `page.tsx` | Authenticated home hub — role-differentiated company grid (free: locked cards, paid: analytics links, admin: admin dashboard link) |
| `not-found.tsx` | Custom 404 page |
| `auth/login/page.tsx` | Login page with email/password form |
| `auth/register/page.tsx` | Registration page — displays system-generated password |
| `companies/page.tsx` | Public company list page |
| `companies/[id]/page.tsx` | Company detail page with KPIs, financials, qualitative insights |
| `dashboard/page.tsx` | Pro dashboard hub (paid/admin) |
| `dashboard/[ticker]/page.tsx` | Per-company analytics dashboard with charts |
| `admin/dashboard/page.tsx` | Admin user management dashboard |
| `account/page.tsx` | User account/profile page |
| `upgrade/page.tsx` | Stripe upgrade/pricing page |
| `api-docs/page.tsx` | API documentation viewer page |

### `frontend/src/app/api/` — BFF Route Handlers

| File | Purpose |
|---|---|
| `auth/login/route.ts` | Proxies POST to backend `/auth/login`, forwards Set-Cookie headers |
| `auth/register/route.ts` | Proxies POST to backend `/auth/register` |
| `auth/me/route.ts` | Proxies GET to backend `/users/me` with cookie forwarding |
| `auth/logout/route.ts` | Proxies POST to backend `/auth/logout` |
| `companies/route.ts` | Proxies GET to backend `/companies` |
| `companies/[id]/route.ts` | Proxies GET to backend `/companies/{id}` (detail + summary + qualitative) |
| `financials/[id]/route.ts` | Proxies GET to backend `/financials/{id}/income-statement` |
| `admin/users/route.ts` | Proxies GET to backend `/admin/users` |
| `admin/users/[id]/route.ts` | Proxies PATCH/DELETE to backend `/admin/users/{id}` |
| `users/api-key/route.ts` | Proxies to backend `/users/me/api-key` and `/users/me/api-key/rotate` |
| `stripe/checkout/route.ts` | Creates Stripe Checkout session and returns `checkout_url` |

### `frontend/src/components/`

| File | Purpose |
|---|---|
| `layout/Header.tsx` | Top navigation bar with auth state, role badge, nav links |
| `layout/Footer.tsx` | Footer with links and copyright |
| `charts/IncomeBarChart.tsx` | Revenue/net income bar chart (Recharts) |
| `charts/MarginChart.tsx` | Margin trend line chart |
| `charts/PeerRadarChart.tsx` | Peer comparison radar chart |
| `charts/RevenueTrendChart.tsx` | Revenue trend line chart |
| `charts/SentimentOverlayChart.tsx` | AI sentiment overlay chart |
| `charts/WaterfallChart.tsx` | Revenue waterfall chart |
| `tables/FinancialsTable.tsx` | Sortable financial data table |
| `ui/Badge.tsx` | Role/status badge component |
| `ui/CompanyCard.tsx` | Company card for grid layouts |
| `ui/JarvisButton.tsx` | Floating Jarvis voice assistant button with Web Speech API integration |
| `ui/KPICard.tsx` | KPI metric card component |
| `ui/Skeleton.tsx` | Loading skeleton component |

### `frontend/src/lib/`

| File | Purpose |
|---|---|
| `api.ts` | Centralised API client — `fetchJSON` (GET with ISR), `mutateJSON` (POST/PATCH/DELETE). Namespaced: `api.companies`, `api.financials`, `api.auth`, `api.user`, `api.stripe` |
| `providers.tsx` | React context providers — QueryClientProvider (TanStack Query), SessionHydrator (auto-refreshes auth on mount) |
| `utils.ts` | Utility functions — number formatting, currency display, date formatting |

### `frontend/src/hooks/`

| File | Purpose |
|---|---|
| `useAuth.ts` | TanStack Query hooks — `useCurrentUser`, `useLogin`, `useRegister`, `useLogout`. Syncs with Zustand store, handles redirects |
| `useCompanies.ts` | TanStack Query hooks for company list and detail |
| `useFinancials.ts` | TanStack Query hooks for financial data |

### `frontend/src/stores/`

| File | Purpose |
|---|---|
| `authStore.ts` | Zustand store — holds `AuthUser` (id, email, role, has_api_key), `isHydrating` flag, `setUser`/`clearUser`/`setHydrated` actions |
| `searchStore.ts` | Zustand store for search state |

### `frontend/src/types/`

| File | Purpose |
|---|---|
| `index.ts` | TypeScript interfaces — `CompanySummary`, `CompanyDetail`, `KPISummary`, `IncomeStatementEntry`, `IncomeStatementResponse` |

---

## `tests/` — Root-Level Integration Tests

| File | Purpose |
|---|---|
| `conftest.py` | Root pytest config — documents that these are live HTTP integration tests (not unit tests) |
| `test_phase2_extraction.py` | Phase 2 ETL pipeline extraction tests — validates LLM output quality |
| `test_phase3_api_integration.py` | Phase 3 API integration tests — hits live backend, tests all endpoints |
| `test_phase4_auth_integration.py` | Phase 4 auth integration tests — register, login, refresh, logout, RBAC |
| `test_phase4_full_stack.py` | Phase 4 full-stack tests — end-to-end auth + data + Stripe flows |
| `test_pipeline.py` | Pipeline unit tests — parser, router, extractor, merger nodes |
| `test_2081_api.py` | Specific API test |
| `test_gemini_api.py` | Gemini API connectivity test |
| `test_llama_parse.py` | LlamaParse connectivity test |
| `debug_extraction.py` | Debug script for extraction pipeline |
| `debug_extraction_results.txt` | Debug output |
| `test_phase2_extraction_result.txt` | Phase 2 extraction test results |

---

## `docs/` — MkDocs Documentation

| Directory | Contents |
|---|---|
| `index.md` | Documentation home — quick navigation table, development phases, tech stack tabs |
| `platform-overview/` | Platform overview and goals |
| `architecture/` | System architecture, data pipeline, RAG architecture, agentic workflow diagrams |
| `data-engineering/` | Scraping system, PDF parsing, ETL pipeline docs |
| `backend/` | FastAPI architecture, services, database schema, authentication, RBAC, Stripe integration |
| `api-reference/` | API overview, authentication, endpoints, usage examples |
| `frontend/` | Frontend architecture, routing, state management, dashboard |
| `ai-systems/` | RAG pipeline, LLM analysis, agentic system, Jarvis voice assistant (overview, architecture, intent classifier, API reference, deployment, roadmap) |
| `mlops/` | Model training, experiment tracking, deployment (planned) |
| `system-design/` | Scaling, reliability, data quality (planned) |
| `development/` | Environment setup, running the project, contributing |

---

## `dev-documentation/` — Internal Planning

| File | Purpose |
|---|---|
| `0_project-plan.md` | Master project plan and roadmap |
| `1_phase-1.md` | Phase 1 plan (MVP & data acquisition) |
| `2_phase-2.md` | Phase 2 plan (ETL pipeline & database) |
| `2.1_pipeline_runbook.md.resolved` | Pipeline runbook (resolved version) |
| `3_phase-3.md` | Phase 3 plan (RAG & backend API) |
| `3.1_implementation.md` | Phase 3 implementation details |
| `4_phase-4.md` | Phase 4 plan (full-stack dashboard & auth) |
| `4.1_plan.md` | Phase 4 detailed plan |
| `4.2_implementation.md` | Phase 4 implementation tracker |
| `4.3_usage_and_setup.md` | Phase 4 usage and setup guide |
| `5_phase-5.md` | Phase 5 plan (agentic workflows) |
| `EEYANG.md` | Team member notes |
| `VINCENT.md` | Team member notes |
| `local_vs_cloud.md` | Local vs cloud architecture comparison |
| `knowledge/` | Internal knowledge base |

---

## `.github/workflows/` — CI/CD

| File | Purpose |
|---|---|
| `deploy-backend.yml` | Backend CI — validates Python imports, triggers Render deploy hook on push to `main` |
| `deploy-frontend.yml` | Frontend CI — TypeScript check, build, deploy to Vercel on push to `main` |
| `deploy-docs-on-main.yml` | Docs CI — builds MkDocs site and deploys to GitHub Pages |
