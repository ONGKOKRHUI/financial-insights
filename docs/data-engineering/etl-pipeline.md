# ETL Pipeline

!!! success "Phase 2 — Implemented"
    The full automated ETL pipeline — scraper check → PDF ingestion → AI-driven parsing → PostgreSQL UPSERT — is live.  
    Orchestrated by **Apache Airflow** (LocalExecutor), powered by **LangGraph + Google Gemini 
    2.0 Flash**, and traced end-to-end with **Langfuse**.
    It can run through the deployable weekly job in `src/jobs/weekly_ingestion.py` or through the Airflow DAG.

---

## Overview

The FinSight ETL pipeline converts raw quarterly/annual report PDFs downloaded by the Phase 1 scraper into structured financial data stored in PostgreSQL.

```
Weekly job / Airflow
────────────────────────────────────────────────────────────────────────────────
Playwright scraper latest check
  src/scraper/data/raw/<TICKER>/*.pdf
    └── scan unprocessed PDFs via pipeline_runs
        └── LangGraph state machine
            parse_pdf → route_content
              ├── extract_quantitative  (Gemini)
              └── extract_qualitative   (Gemini)
                    └── merge_and_validate
                        └── PostgreSQL UPSERT + status tracking
```

---

## Pipeline Diagram

```mermaid
flowchart LR
    A[PDF Files\nsrc/scraper/data/raw/] --> B[LlamaParse\nwith Markdown\nparsing_instruction]
    B --> B2[PyMuPDF fallback\nif API key absent]
    B --> C[route_content\nPass-through: full\nMarkdown → both branches]
    B2 --> C
    C --> D[extract_quantitative\nGemini — raw string\nextraction via FinancialValue]
    C --> E[extract_qualitative\nGemini — narrative\nsummarisation]
    D --> F[merge_and_validate\nPydantic FinancialReportPayload]
    E --> F
    F --> G[normalize_financial_data\nPython string→float\nconversion]
    G --> H{Valid?}
    H -- Yes --> I[PostgreSQL UPSERT\nincome_statements\nbalance_sheets\ncash_flows\nqualitative_insights\nkpi_summaries]
    H -- Partial --> I
    H -- Error --> J[pipeline_runs\nstatus = error]
    I --> K[(finsight DB)]
```

---

## Orchestration

### Weekly Ingestion Job — `src/jobs/weekly_ingestion.py`

This is the simplest deployment entry point when you want one scheduled
process to do everything every Monday:

```bash
PYTHONPATH=src python -m jobs.weekly_ingestion --latest-only
```

The job performs:

1. `src/scraper/main.py` latest-quarter scrape for the configured companies.
2. `db.loader.get_unprocessed_pdfs(FINSIGHT_RAW_DIR)` to find raw PDFs not
   already marked `success`.
3. `pipeline.graph.run_pipeline(pdf_path)` for LlamaParse/Gemini extraction.
4. `db.loader.upsert_report(payload)` and `mark_processed(...)` for database
   persistence and idempotent run tracking.

Useful options:

| Option | Purpose |
|---|---|
| `--skip-scrape` | Process PDFs already in the raw folder without running Playwright. |
| `--dry-run` | List PDFs that would be processed without LLM or DB writes. |
| `--limit N` | Process only the first N unprocessed PDFs for smoke testing. |
| `--full-backfill` | Run scraper backfill mode instead of latest-only mode. |

`src/scraper/scheduler.py` is archived/disabled and kept only for historical
reference. Cloud runs are triggered externally via `POST /run-pipeline`.

### Airflow DAG — `dags/finsight_etl_dag.py`

| Property | Value |
|---|---|
| DAG ID | `finsight_etl` |
| Schedule | `@daily` |
| Executor | `LocalExecutor` |
| Retries | 3 × 5-minute delay |
| Start date | 2025-01-01 (catchup=False) |

**Task graph:**

```
check_new_pdfs >> trigger_parse_pipeline >> load_to_postgres
```

| Task | Operator | What it does |
|---|---|---|
| `check_new_pdfs` | `PythonOperator` | Scans `FINSIGHT_RAW_DIR` for PDFs not yet in `pipeline_runs` with `status='success'`. Pushes list via XCom. |
| `trigger_parse_pipeline` | `PythonOperator` | Runs `pipeline.graph.run_pipeline(pdf_path)` for each unprocessed PDF. Calls `normalize_financial_data()` on the result. Pushes validated JSON payloads via XCom. |
| `load_to_postgres` | `PythonOperator` | Calls `db.loader.upsert_report(payload)` for each payload; marks files as `success` or `error` in `pipeline_runs`. |

---

## Transform Logic

### LangGraph State Machine — `src/pipeline/`

The pipeline uses a **LangGraph StateGraph** (engine toggle: `PIPELINE_ENGINE=langgraph|dify`).

```python
# graph.py
parse_pdf → route_content → [extract_quantitative, extract_qualitative] → merge_and_validate
```

| Node | File | Description |
|---|---|---|
| `parse_pdf` | `nodes/parser.py` | Calls LlamaCloud async API (`tier=agentic`) with a strict Markdown `parsing_instruction` → clean Markdown. Falls back to PyMuPDF if API key absent. Derives ticker/year/period from filename. |
| `route_content` | `nodes/router.py` | **Pass-through node.** Assigns the full `markdown_text` to both `table_markdown` and `narrative_markdown`. No regex splitting — Gemini 2.0 Flash's 1M-token context window locates tables itself. |
| `extract_quantitative` | `nodes/quantitative.py` | Gemini `with_structured_output()` extracts Income Statement, Balance Sheet, Cash Flow, KPI Summary as **raw strings** (`FinancialValue`). Receives the full document. Langfuse callback attached. |
| `extract_qualitative` | `nodes/qualitative.py` | Pattern-matching locates MD&A / Outlook / Chairman sections, then Gemini summarises → `future_outlook` string + `key_strategic_events` JSON array. Langfuse callback attached. |
| `merge_and_validate` | `nodes/merger.py` | Assembles `FinancialReportPayload` Pydantic model from both branches. On validation error, appends to `errors` and returns partial payload. |

### Two-Stage Financial Data Extraction

Quantitative extraction is now a **two-stage pipeline** to eliminate LLM arithmetic errors:

**Stage 1 — LLM extracts raw strings (zero arithmetic)**

The LLM is given the full document and asked to return values exactly as printed, alongside the unit header from the table:

```python
class FinancialValue(BaseModel):
    raw_value: Optional[str]    # e.g. "(1,350,348)" or "12,345.00"
    unit_header: Optional[str]  # e.g. "RM 000", "MYR Millions", "sen"
```

Each field in `_IncomeStatementExtraction`, `_BalanceSheetExtraction`, `_CashFlowExtraction`, and `_KPIExtraction` is typed as `Optional[FinancialValue]`.

**Stage 2 — Python normalises to MYR billions (deterministic)**

`normalize_financial_data(extracted_data)` recursively walks the LLM JSON and converts every `FinancialValue` dict to a float:

| Step | Logic |
|---|---|
| Strip commas | `"12,345.00"` → `12345.0` |
| Parentheses → negative | `"(1,350,348)"` → `-1350348.0` |
| Unit multiplier | `RM '000` → ÷ 1,000,000 · `MYR Millions` → ÷ 1,000 · `Billions` → ÷ 1 |

### Financial Data Normalisation

- All monetary values reach the DB as **MYR billions** floats (e.g., 12,345 RM'000 → 0.012345)
- Fiscal year derived from filename `{TICKER}_{YEAR}_{QUARTER}.pdf`
- Percentages stored as 0–100 (not 0–1)
- `key_strategic_events` stored as a JSON-serialised string in PostgreSQL

### Deduplication / Idempotency

All financial tables use `ON CONFLICT (ticker, fiscal_year) DO UPDATE` so re-running the pipeline never creates duplicates.

The `pipeline_runs` tracking table records:

```sql
CREATE TABLE pipeline_runs (
    id          SERIAL PRIMARY KEY,
    pdf_path    TEXT        NOT NULL UNIQUE,
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | processing | success | error
    ticker      VARCHAR(20),
    fiscal_year INTEGER,
    run_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_msg   TEXT
);
```

### Incremental Loading

Only PDFs absent from `pipeline_runs WHERE status='success'` are processed each job/DAG run.

---

## Ground-Truth Accuracy Validation

Mock ground truth lives at `ground_truth/mock_ground_truth.json`. Replace the
records in this file with manually verified financial values when the real
ground-truth dataset is ready.

Run the validator against the configured database:

```bash
PYTHONPATH=src python -m validation.validate_extraction_accuracy \
  --ground-truth ground_truth/mock_ground_truth.json \
  --output validation_report.json
```

The report includes total records, passed records, missing database values, and
overall tolerance-based accuracy. Ground-truth records are field-level entries
with `ticker`, `fiscal_year`, `statement`, `field`, `expected_value`, and
`tolerance_abs`.

---

## Engine Toggle — LangGraph vs Dify

Set `PIPELINE_ENGINE` in `.env`:

| Value | Behaviour |
|---|---|
| `langgraph` (default) | Full LangGraph state machine: Parser → Pass-through Router → Quant/Qual → Merge → Normalise |
| `dify` | Skips LangGraph nodes; sends parsed Markdown to a Dify Workflow API endpoint (`DIFY_API_URL`) and maps the JSON response to the DB loader |

Dify client lives at `src/pipeline/dify_client.py`.

---

## Docker Setup

Airflow runs in a **separate** `docker-compose.airflow.yml` so it never interferes with the main `docker-compose.yml` (postgres + backend + frontend).

```
docker compose up -d                                 # main stack (postgres:5432, backend, frontend)
docker compose -f docker-compose.airflow.yml up --build   # Airflow (postgres-airflow:5433, UI:8080)
```

### Intended usage split

- **Deployment (Render):** use external trigger path (`POST /run-pipeline` -> `src/jobs/weekly_ingestion.py`).
- **Local development/testing:** use Airflow in Docker with `dags/finsight_etl_dag.py`.

For production operations and validation steps, see:
`docs/development/pipeline-trigger-runbook.md`.

### Required `.env` keys for local Airflow ETL

Minimum keys for **LangGraph + Gemini + LlamaParse + Langfuse**:

| Key | Required | Example |
|---|---|---|
| `AIRFLOW_DATABASE_URL` | Recommended | `postgresql://postgres:postgres@postgres:5432/finsight` |
| `DATABASE_URL` | Yes (fallback) | `postgresql://postgres:postgres@localhost:5432/finsight` |
| `FINSIGHT_RAW_DIR` | Yes | `/app/src/scraper/data/raw` (container path is set by compose) |
| `PIPELINE_ENGINE` | Yes | `langgraph` |
| `GOOGLE_API_KEY` | Yes (`langgraph`) | `AIza...` |
| `GEMINI_MODEL` | Optional | `gemini-2.5-flash` |
| `LLAMA_CLOUD_API_KEY` | Optional but recommended | `llx-...` |
| `LANGFUSE_PUBLIC_KEY` | Optional (enable tracing) | `pk-lf-...` |
| `LANGFUSE_SECRET_KEY` | Optional (enable tracing) | `sk-lf-...` |
| `LANGFUSE_HOST` | Optional | `https://cloud.langfuse.com` |
| `AIRFLOW_FERNET_KEY` | Yes | `HnvohNQlq8zydPYxPVvA6x0f0l4CYwSqNMOYfTRtFjY=` |
| `AIRFLOW_SECRET_KEY` | Yes | `finsight-airflow-dev-secret` |

Additional keys only when `PIPELINE_ENGINE=dify`:

| Key | Required (`dify`) | Example |
|---|---|---|
| `DIFY_API_URL` | Yes | `https://api.dify.ai/v1/workflows/run` |
| `DIFY_API_KEY` | Yes | `app-...` |

Airflow services:

| Service | Port | Notes |
|---|---|---|
| `postgres-airflow` | 5433 | Airflow metadata DB — isolated from finsight DB |
| `airflow-init` | — | One-shot: runs `airflow db migrate` + creates admin user |
| `airflow-webserver` | 8080 | UI at http://localhost:8080 (admin/admin) |
| `airflow-scheduler` | — | Picks up and executes DAG runs |

The Airflow containers mount `./dags` and `./src` as volumes and set `PYTHONPATH=/app/src` so `pipeline.*` and `db.*` imports work transparently.

---

## Monitoring and Alerting

- **Langfuse** traces every LLM call (model, prompt, tokens, latency) at https://cloud.langfuse.com
- **Airflow UI** (http://localhost:8080) shows per-task status, logs, XCom values, and retry history
- **`pipeline_runs` table** provides SQL-queryable run history:
  ```sql
  SELECT * FROM pipeline_runs ORDER BY run_at DESC LIMIT 20;
  ```
- Set `email_on_failure=True` in `DEFAULT_ARGS` (DAG file) and configure Airflow SMTP for alerts

---

## Data Lineage

Every DB row is traceable via:

1. `pipeline_runs.pdf_path` → source PDF
2. `pipeline_runs.run_at` → ingestion timestamp
3. Langfuse trace → full LLM prompt/response for that PDF

---

## Local Development Quickstart

```bash
# 1. Install pipeline deps
pip install -r src/pipeline/requirements.txt

# 2. Copy and fill in .env
cp .env.example .env

# 3. Smoke test (no DB or LLM needed)
python tests/test_pipeline.py --smoke

# 4. Run pipeline on a single PDF (requires GOOGLE_API_KEY + DATABASE_URL)
python -m pipeline.graph --pdf src/scraper/data/raw/MAYBANK/MAYBANK_2024_Q3.pdf

# 5. Integration test (DB + LLM + real PDF)
python tests/test_pipeline.py --integration --pdf src/scraper/data/raw/MAYBANK/MAYBANK_2024_Q3.pdf

# 6. Watch mode: auto-run when any new PDF appears
python tests/test_pipeline.py --watch

# 7. Start Airflow locally
docker compose -f docker-compose.airflow.yml up --build

# 8. Trigger Airflow DAG manually
docker compose -f docker-compose.airflow.yml exec -T airflow-webserver \
  airflow dags trigger finsight_etl

# 9. Smoke-test DAG end-to-end (recommended)
python scripts/test_airflow_pipeline_local.py --max-pdfs 1
```

## Switching pipeline engines locally

You can switch the extraction pipeline used by Airflow via `PIPELINE_ENGINE`:

1. Set in `.env`:
   - `PIPELINE_ENGINE=langgraph` (default)
   - `PIPELINE_ENGINE=dify`
2. Restart Airflow stack so containers pick up the new env:
   ```bash
   docker compose -f docker-compose.airflow.yml down
   docker compose -f docker-compose.airflow.yml up -d --build
   ```
3. Run a test:
   ```bash
   python scripts/test_airflow_pipeline_local.py --pipeline-engine langgraph --max-pdfs 1
   # or
   python scripts/test_airflow_pipeline_local.py --pipeline-engine dify --max-pdfs 1
   ```

For direct DAG runs, set this env var for quick validation:

```bash
FINSIGHT_MAX_PDFS_PER_RUN=1
```

When `FINSIGHT_MAX_PDFS_PER_RUN` is greater than `0`, `check_new_pdfs` limits
the number of files sent to downstream tasks in the same DAG run.
