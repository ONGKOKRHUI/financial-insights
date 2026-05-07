# FinSight Full Project Audit Report

Date: 2026-05-07  
Auditor: Codex  
Scope reviewed: root configs, `src`, `frontend`, `tests`, `docs`, `dev-documentation`, and listed deployment/manifests.

---

## 1) Executive Summary

The project is functional and reasonably modular, with clear domain separation across scraper, pipeline, backend API, and frontend dashboard. The biggest risks are not feature gaps but production hardening and consistency gaps: auth/session security assumptions, configuration defaults, non-hermetic integration tests, stale docs, and mixed orchestration patterns.

High-impact documentation mismatches were corrected in this pass (API auth behavior, route naming, run commands, and scraper orchestration guidance).

---

## 2) Best-Practice Findings (Prioritized)

## Critical

- `src/backend/auth/jwt.py`: hardcoded fallback `SECRET_KEY` path is unsafe; startup should fail when `SECRET_KEY` is missing in non-test modes.
- `src/backend/services/tts.py`: Google API key sent via query-string; this can leak in intermediary logs.
- `src/backend/auth/dependencies.py`: potential null dereference in API key owner lookup can produce 500 instead of 401/403.

## High

- `src/pipeline/graph.py`: `load_dotenv(override=True)` at import time can override container/runtime-provided env unexpectedly.
- `src/backend/main.py`: `Base.metadata.create_all()` in app lifespan can drift from Alembic migration discipline.
- `src/backend/routers/pipeline_trigger.py`: in-process lock is not distributed-safe across multiple workers/instances.
- Broad `except Exception` usage in pipeline/scraper/Jarvis paths reduces observability and recovery precision.

## Medium

- Repeated `sys.path` bootstrapping in DAG/jobs/tests indicates packaging/import boundary fragility.
- Archived/runtime files coexist with active paths without strong archival markers (for example scheduler/testing variants).
- Integration test suite is largely live-environment dependent; deterministic fast unit coverage for failure cases is relatively thin.
- Frontend auth typing and fallback behavior is inconsistent in login flow (`frontend/src/app/api/auth/login/route.ts`, `frontend/src/hooks/useAuth.ts`).
- Direct backend calls still exist alongside BFF pattern in multiple frontend pages/components.

## Low

- Mixed naming semantics (`[id]` often represents ticker) reduce readability.
- Some operational scripts still rely on ad-hoc `print` logs and script-style conventions.

---

## 3) Documentation / Implementation Drift (Detected)

- `docs/api-reference/overview.md` and `docs/api-reference/endpoints.md` previously claimed all endpoints were open; `POST /search` is paid/admin-gated.
- `docs/backend/fastapi-architecture.md` had stale Jarvis endpoint names and API key route wording.
- `docs/development/running-the-project.md` referenced non-existent `scripts/test_airflow_pipeline_local.py` and outdated test filenames.
- `docs/data-engineering/scraping-system.md` described active scheduler automation inconsistent with current archived scheduler approach.
- `docs/development/environment-setup.md` referenced frontend env copy flow that did not match existing files.
- `dev-documentation/FILE_SUMMARY.md` contained stale entries and path mismatches.

---

## 4) Changes Applied In This Cleanup

- Updated `docs/api-reference/overview.md`:
  - Clarified tier-aware access model.
  - Removed claim that all endpoints are unauthenticated.
- Updated `docs/api-reference/endpoints.md`:
  - Added auth requirements and 401/403 behavior for `POST /search`.
  - Corrected ticker table to `TELEKOM`.
- Updated `docs/backend/fastapi-architecture.md`:
  - Corrected users API-key route descriptions.
  - Corrected Jarvis endpoint naming.
  - Corrected default `ALLOWED_ORIGINS` value.
- Updated `docs/development/environment-setup.md`:
  - Corrected local env creation instructions for frontend.
- Updated `docs/development/running-the-project.md`:
  - Replaced non-existent script commands with existing pytest harnesses.
  - Fixed stale validation test reference.
- Updated `docs/data-engineering/scraping-system.md`:
  - Marked scheduler as archived path and aligned to current orchestration model.
- Updated `docs/development/contributing.md`:
  - Corrected frontend validation checklist command.
- Replaced `dev-documentation/FILE_SUMMARY.md` with a maintained, current index format.

---

## 5) Code File Documentation Index

This section documents what each core code file does (grouped by area).

### Backend (`src/backend`)

- `main.py`: FastAPI app entry, router registration, CORS, health, startup DB/seed flow.
- `database.py`: SQLAlchemy engine/session and dependency provider.
- `models.py`: ORM entities for companies, statements, qualitative insights, users, tokens, API keys.
- `schemas.py`: Pydantic response/request schemas.
- `seed.py`: idempotent DB seeding from mock data.
- `routers/auth.py`: register/login/refresh/logout cookie auth flow.
- `routers/users.py`: profile retrieval and API key info/rotation.
- `routers/admin.py`: admin user listing/update/delete.
- `routers/companies.py`: company listing/detail/summary/qualitative endpoints.
- `routers/financials.py`: financial statement endpoints by ticker.
- `routers/search.py`: paid/admin unified search endpoint.
- `routers/jarvis.py`: Jarvis text/voice stream and TTS endpoints.
- `routers/webhooks.py`: Stripe subscription lifecycle webhook handling.
- `routers/pipeline_trigger.py`: protected external trigger for ingestion run.
- `auth/jwt.py`: JWT issue/decode utilities.
- `auth/password.py`: password/API key hashing + generation helpers.
- `auth/dependencies.py`: FastAPI auth dependencies and RBAC checks.
- `services/asr.py`: ASR abstraction for Whisper/Gemini.
- `services/jarvis_intent.py`: keyword/LangGraph/Dify intent mapping logic.
- `services/langgraph_intent.py`: multi-step LangGraph intent pipeline.
- `services/tts.py`: TTS abstraction for Edge/Google.
- `alembic/env.py` and `alembic/versions/*`: migration environment and versioned schema deltas.
- `tests/conftest.py`: backend test DB setup/fixtures.
- `tests/test_api.py`: backend route tests.

### Pipeline / Data (`src/pipeline`, `src/db`, `src/jobs`, `dags`)

- `pipeline/graph.py`: orchestrates parse → route → extraction → merge/validate flow.
- `pipeline/state.py`: shared typed pipeline state.
- `pipeline/schemas.py`: typed extraction payload models.
- `pipeline/dify_client.py`: Dify workflow bridge client.
- `pipeline/nodes/parser.py`: PDF text extraction + metadata parsing.
- `pipeline/nodes/router.py`: branch routing for content.
- `pipeline/nodes/quantitative.py`: financial metrics extraction + normalization.
- `pipeline/nodes/qualitative.py`: narrative/strategic events extraction.
- `pipeline/nodes/merger.py`: branch merge + final validation.
- `db/loader.py`: upsert/report ingestion and processed-file bookkeeping.
- `jobs/weekly_ingestion.py`: runbook entrypoint for scrape+pipeline+load orchestration.
- `dags/finsight_etl_dag.py`: Airflow DAG for local orchestration/testing path.

### Scraper (`src/scraper`)

- `main.py`: orchestrates company scrapers by period mode/backfill.
- `scheduler.py`: archived scheduler compatibility stub.
- `scrapers/*.py`: company-specific IR scraping/download logic.
- `scrapers/maybank_test.py`, `ARCHIVED_scheduler.py`: historical/experimental paths to archive-hardening.

### Frontend (`frontend/src`)

- `middleware.ts`: route-level auth/role redirect middleware.
- `app/layout.tsx`, `app/globals.css`: root shell + global styles.
- `app/page.tsx`, `app/companies/*`, `app/account/page.tsx`, `app/upgrade/page.tsx`, `app/admin/dashboard/page.tsx`: primary UI pages and role-aware experiences.
- `app/api/**/route.ts`: BFF route handlers proxying backend auth/data/admin/stripe operations.
- `components/layout/*`: app header/footer shell.
- `components/ui/*`: reusable UI blocks including `JarvisButton`.
- `components/charts/*`, `components/tables/*`: visual analytics presentation layer.
- `hooks/useAuth.ts`, `useCompanies.ts`, `useFinancials.ts`: data-fetching/mutation hooks.
- `stores/authStore.ts`, `searchStore.ts`: Zustand local state.
- `lib/api.ts`, `providers.tsx`, `utils.ts`: API helpers, provider wiring, and shared formatting helpers.
- `types/index.ts`: domain interfaces.

### Tests (`tests`)

- `test_phase2_extraction.py`: extraction diagnostics.
- `test_phase3_api_integration.py`: live API integration checks.
- `test_phase4_auth_integration.py`: auth/RBAC integration checks.
- `test_phase4_full_stack.py`: full-stack integration checks.
- `test_phase4_airflow_pipeline_local.py`: Airflow-local pipeline smoke harness.
- `test_phase4_run_pdf_pipeline_validation.py`: PDF-run validation against ground truth.
- `test_bugs.py`: regression-oriented bug tests.
- `test_gemini_api.py`, `test_llama_parse.py`, `debug_extraction.py`: utility/debug scripts (recommend move under a clearly named `scripts/` area).

---

## 6) Structural Improvement Suggestions

- Enforce strict runtime config policy:
  - fail fast on missing `SECRET_KEY` outside test mode;
  - remove unsafe fallback DB credentials in production paths.
- Harden auth/session perimeter:
  - avoid trusting unverified JWT claims in frontend middleware for privileged gating;
  - add explicit CSRF defense pattern for cookie-authenticated mutating operations.
- Standardize architecture boundaries:
  - route all frontend data access through BFF consistently;
  - avoid mixed direct backend URL usage.
- Improve orchestration robustness:
  - replace in-process pipeline trigger lock with distributed lock/job queue.
- Upgrade testing strategy:
  - keep current integration suite, but add fast deterministic unit tests for edge/error/security cases;
  - reclassify utility scripts from `test_*.py` to `scripts/` to avoid intent confusion.
- Reduce archival noise:
  - move historical files into an explicit `archive/` namespace and add top-of-file banners.
- Documentation governance:
  - enforce “last verified date + verified against code paths” on operational docs;
  - keep one canonical runbook per area, link historical notes rather than duplicating instructions.

---

## 7) Proposed Next Pass (Optional)

If you want, the next implementation-focused pass should directly fix code risks (not only docs):

1. Security hardening PR (JWT secret enforcement, API-key null safety, safer TTS auth).
2. Frontend auth consistency PR (typed login response contract, BFF-only access, middleware policy).
3. Reliability PR (distributed-safe trigger lock + stronger retry/error taxonomy).
4. Test architecture PR (separate scripts/integration/unit lanes and update CI matrix).
