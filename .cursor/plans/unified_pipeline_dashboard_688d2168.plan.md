---
name: unified pipeline dashboard
overview: Unify the company browsing and advanced analytics experience under `/companies`, wire the scraper and LLM extraction into an automated weekly ingestion path, and add a replaceable mocked ground-truth validation framework for retrieval accuracy.
todos:
  - id: frontend-routes
    content: Unify company routes and move paid analytics to `/companies/[ticker]/advanced`.
    status: completed
  - id: auth-navigation
    content: Update middleware, header, logout, and legacy redirects for the new access rules.
    status: completed
  - id: pipeline-orchestration
    content: Add weekly scrape-to-ETL orchestration that processes unprocessed PDFs and upserts database rows.
    status: completed
  - id: mock-data-runtime
    content: Keep mock data for tests/demo only and remove production visualisation dependence on it.
    status: completed
  - id: ground-truth-validation
    content: Add mocked ground-truth files plus an accuracy validation script and tests.
    status: completed
  - id: verification
    content: Run lint/tests/build or document any environment-limited checks.
    status: completed
  - id: todo-1777682492551-x8qg5kibc
    content: "look at the docs folder (project documentation) and update the relevant markdown files "
    status: completed
  - id: todo-1777682587111-xcd41afe9
    content: explain what are the changes made how use the updated pipeline (for example is there a file for the pipeline etc)
    status: completed
isProject: false
---

# Unified Companies, Pipeline, and Validation Plan

## Current Findings
- Frontend already has public company list/detail routes at [`frontend/src/app/companies/page.tsx`](frontend/src/app/companies/page.tsx) and [`frontend/src/app/companies/[id]/page.tsx`](frontend/src/app/companies/[id]/page.tsx). The detail page already renders the free KPI, revenue, income, margin, and income-statement visualisations from backend data.
- Paid analytics currently live at [`frontend/src/app/dashboard/[ticker]/page.tsx`](frontend/src/app/dashboard/[ticker]/page.tsx), while [`frontend/src/app/dashboard/page.tsx`](frontend/src/app/dashboard/page.tsx) redirects to `/`. The authenticated home page [`frontend/src/app/page.tsx`](frontend/src/app/page.tsx) still has a separate hard-coded 8-company grid that does not match the scraper/database company set.
- Middleware [`frontend/src/middleware.ts`](frontend/src/middleware.ts) currently makes `/companies/**` public and gates `/dashboard/**` to paid/admin. This needs to change so `/companies/[ticker]` stays public but `/companies/[ticker]/advanced` is paid/admin only.
- Backend data APIs already expose companies, summaries, and financial statements through [`src/backend/routers/companies.py`](src/backend/routers/companies.py) and [`src/backend/routers/financials.py`](src/backend/routers/financials.py). The paid dashboard currently calls a missing BFF path `/api/companies/[ticker]/summary`, so that needs to be added or the component needs to use the existing API client consistently.
- Scrapers and weekly scheduling exist in [`src/scraper/main.py`](src/scraper/main.py) and [`src/scraper/scheduler.py`](src/scraper/scheduler.py), but the scheduler only downloads PDFs. The ETL graph exists in [`src/pipeline/graph.py`](src/pipeline/graph.py), and DB loading/tracking exists in [`src/db/loader.py`](src/db/loader.py), but they are not automatically chained after a scrape.
- `mock_data.py` is imported by [`src/backend/seed.py`](src/backend/seed.py) and backend tests, but no tracked `mock_data.py` was found. I will preserve the concept of mock data while removing it from production visualisation/data flow.

## Implementation Approach

1. Unify company navigation under `/companies`.
- Keep [`frontend/src/app/companies/page.tsx`](frontend/src/app/companies/page.tsx) as the only company-card grid for all users.
- Remove the hard-coded company grid from [`frontend/src/app/page.tsx`](frontend/src/app/page.tsx); make the logged-in home page a lightweight hub that links to `/companies`, account/API docs, upgrade, and admin tools as appropriate.
- Ensure all company card data comes from `/companies` backend data, not hard-coded constants.

2. Move paid analytics to `/companies/[ticker]/advanced`.
- Create `frontend/src/app/companies/[id]/advanced/page.tsx` by adapting the existing paid charts from [`frontend/src/app/dashboard/[ticker]/page.tsx`](frontend/src/app/dashboard/[ticker]/page.tsx).
- Add an “Advanced analytics” CTA on [`frontend/src/app/companies/[id]/page.tsx`](frontend/src/app/companies/[id]/page.tsx): visible to all users, clickable for paid/admin, and visually locked/upgrade-oriented for guests/free users.
- Add redirects from old `/dashboard/[ticker]` URLs to `/companies/[ticker]/advanced`; keep `/dashboard` as a redirect to `/companies` or `/` to avoid stale entry points.
- Add/adjust BFF routes so advanced charts fetch only currently available database fields: income statement history, KPI summary, and derived chart data from those fields.

3. Enforce route and navigation rules.
- Update [`frontend/src/middleware.ts`](frontend/src/middleware.ts) so:
  - `/companies` and `/companies/[ticker]` remain public.
  - `/companies/[ticker]/advanced` requires paid/admin.
  - signed-out users attempting advanced URLs go to `/auth/login?redirect=...`.
  - logged-in free users attempting advanced URLs go to `/upgrade`.
  - admin routes remain admin-only.
- Harden logout/back-button behavior by ensuring logout clears auth query cache, navigates with `router.replace`, and protected pages rely on middleware plus session hydration rather than stale client state.
- Update header/navigation text so there is one “Companies” entry point and no separate dashboard company-card entry.

4. Wire scraper to processing pipeline.
- Add a deployment-friendly orchestration entry point, likely `src/jobs/weekly_ingestion.py`, that runs:
  - scraper latest check for the 8 configured companies from [`src/scraper/main.py`](src/scraper/main.py),
  - `get_unprocessed_pdfs(raw_dir)` from [`src/db/loader.py`](src/db/loader.py),
  - `run_pipeline(pdf_path)` from [`src/pipeline/graph.py`](src/pipeline/graph.py),
  - `upsert_report(payload)` and `mark_processed(...)` from [`src/db/loader.py`](src/db/loader.py).
- Update [`src/scraper/scheduler.py`](src/scraper/scheduler.py) or add a sibling scheduler so Monday 09:00 KL runs the full scrape-and-process job, not just PDF download.
- Keep idempotency through `pipeline_runs` and existing database UPSERT constraints.

5. Stop production reliance on `mock_data.py` while preserving it.
- Keep any mock-data module for tests/demo seeding, but change production startup so it does not seed visualisation data from mock data unless explicitly enabled by an environment flag.
- Ensure frontend visualisations use backend/API data only.
- Update backend tests to keep using mock fixtures where useful, but separate that from deployed runtime behavior.

6. Add mocked ground-truth validation.
- Create a ground-truth folder, for example `ground_truth/`, with a replaceable JSON/CSV schema covering ticker, fiscal year, report period, statement, field, expected value, unit, and tolerance.
- Generate mocked ground-truth records for the current 8 companies and available report periods so the validator works immediately and can be replaced later with real values.
- Add a validation script, likely `src/validation/validate_extraction_accuracy.py`, that compares database values to ground truth and reports field-level accuracy, missing values, mismatches, and tolerance-based pass/fail counts.
- Add focused tests for the comparison logic using a small fixture so the metric calculation remains stable when real ground truth replaces the mock data.

## Verification Plan
- Run backend tests around company/financial APIs and any new validation utilities.
- Run frontend lint/build checks for the route and middleware changes.
- Smoke-test route access manually or with focused tests for guest, free, paid, and admin paths:
  - `/companies`
  - `/companies/MAYBANK`
  - `/companies/MAYBANK/advanced`
  - legacy `/dashboard/MAYBANK`
  - logout then browser back to protected pages.
- Run the ingestion orchestrator in a dry-run or one-PDF mode if API keys/database are available; otherwise verify it with mocks around scraper, pipeline, and loader calls.