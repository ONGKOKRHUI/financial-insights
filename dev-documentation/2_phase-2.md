### Phase 2: Data Engineering & ETL Pipeline (Weeks 4-7) (Monash W5-7 + MSB)

**Focus:** Unstructured data parsing, cleaning, and database design.

- **What to Build:** Develop an automated Extract, Transform, Load (ETL) pipeline. The pipeline must ingest the downloaded PDFs, remove formatting syntax, and parse them into raw JSON while critically maintaining the structure of financial tables. Write Python scripts to clean this data, discarding noise and keeping only the relevant financial context. Append this cleaned JSON as new rows in a CSV and store it in a database.
- **What to Learn & Tools to Use:** Learn to orchestrate this workflow using **Apache Airflow** or **Prefect**. To handle complex layouts, explore advanced parsers like **Unstructured** or **PyMuPDF**. Containerize this pipeline using **Docker**.
- **Milestone:** An automated, containerized pipeline that turns raw PDFs into clean, structured data warehoused in a PostgreSQL database.
- IMPORTANT: Heavy studying and understanding of Financial reports of different companies and know which are important insights to retrieve. Use them in the post processing to get important data only. Build the full pipeline and stored in Postgres Database

---

### Phase 2 Progress — Completed (MVP PostgreSQL + Docker)

**Status:** Core database migration and containerisation delivered. Full PDF ETL pipeline is next.

#### What was done

1. **Data completion** — Manually researched and filled in `BALANCE_SHEETS`, `CASH_FLOWS`, and `QUALITATIVE_INSIGHTS` for all 8 KLSE companies (FY2020–FY2024). Values for balance sheets are derived consistently from the ROE and D/E ratios in `KPI_SUMMARIES`. Qualitative insights include future outlook and key strategic events sourced from annual reports.

2. **PostgreSQL via SQLAlchemy** — Backend now reads and writes from a PostgreSQL database instead of in-memory Python dicts:
   - `src/backend/database.py` — SQLAlchemy engine, `SessionLocal`, `get_db()` dependency
   - `src/backend/models.py` — ORM models: `companies`, `kpi_summaries`, `income_statements`, `balance_sheets`, `cash_flows`, `qualitative_insights`
   - `src/backend/seed.py` — Idempotent seed on first boot from `mock_data.py`
   - `src/backend/requirements.txt` — Added `sqlalchemy`, `psycopg2-binary`

3. **New API endpoints**:
   - `GET /financials/{ticker}/balance-sheet`
   - `GET /financials/{ticker}/cash-flow`
   - `GET /companies/{ticker}/qualitative`

4. **Dockerisation**:
   - Fixed `src/backend/Dockerfile` CMD (`backend.main:app` → `main:app`)
   - Created `frontend/Dockerfile` — multi-stage Node 22 Alpine build with `output: standalone`
   - Created `docker-compose.yml` at repo root — three services: `postgres`, `backend`, `frontend`

5. **Deployment (Render)** — Updated `src/backend/render.yaml` to declare a managed PostgreSQL database (`finsight-db`, free plan). `DATABASE_URL` is automatically injected by Render on startup. The seed runs automatically on first boot when tables are empty.

6. **GitHub workflows fixed**:
   - `deploy-backend.yml` — corrected path trigger (`src/backend/**`), `requirements.txt` path, and Python validation commands
   - `deploy-frontend.yml` — added `working-directory: ./frontend` to the type-check step

#### Local development with Docker Compose

```bash
# From repo root
docker compose up --build

# Services:
#   Frontend: http://localhost:3000
#   Backend:  http://localhost:8000/docs
#   Postgres: localhost:5432 (user: postgres, pass: postgres, db: finsight)
```

---

### Phase 2 Progress — ETL Pipeline Completed

**Status:** Full automated PDF → PostgreSQL ETL pipeline delivered.

#### What was built (ETL pipeline)

##### Folder structure added

```
financial-insights/
├── dags/
│   └── finsight_etl_dag.py      Airflow DAG (@daily, LocalExecutor)
├── src/
│   ├── pipeline/                LangGraph state machine
│   │   ├── __init__.py
│   │   ├── state.py             PipelineState TypedDict
│   │   ├── schemas.py           Pydantic v2 validated schemas
│   │   ├── graph.py             run_pipeline() + CLI entry point
│   │   ├── dify_client.py       Dify Workflow API client (PIPELINE_ENGINE=dify)
│   │   ├── requirements.txt     ETL-specific dependencies
│   │   └── nodes/
│   │       ├── parser.py        LlamaParse → Markdown (PyMuPDF fallback)
│   │       ├── router.py        Table vs narrative Markdown splitter
│   │       ├── quantitative.py  Gemini structured extraction (4 statements)
│   │       ├── qualitative.py   Gemini narrative summarisation
│   │       └── merger.py        Pydantic merge + validation
│   └── db/
│       ├── __init__.py
│       └── loader.py            PostgreSQL UPSERT + pipeline_runs tracker
├── tests/
│   └── test_pipeline.py         3-tier test suite (smoke + unit + integration)
├── docker-compose.airflow.yml   Separate Airflow stack (LocalExecutor)
└── .env.example                 Updated with all AI + Airflow keys
```

##### LangGraph state machine

```
parse_pdf → route_content → [extract_quantitative ‖ extract_qualitative] → merge_and_validate
```

- **Parser**: LlamaCloud async API (`tier=agentic`) → structured Markdown. Fallback: PyMuPDF
- **Router**: Regex heuristic splits into `table_markdown` and `narrative_markdown`
- **Quantitative**: Gemini `gemini-2.0-flash` with `with_structured_output()` extracts Income Statement, Balance Sheet, Cash Flow, KPI Summary — all in MYR billions
- **Qualitative**: Gemini summarises MD&A → `future_outlook` string + `key_strategic_events` JSON array
- **Merger**: Pydantic `FinancialReportPayload` validates final envelope; partial payloads stored on error

##### Engine toggle

Set `PIPELINE_ENGINE` in `.env`:

| Value | Behaviour |
|---|---|
| `langgraph` (default) | Full LangGraph state machine |
| `dify` | Parsed Markdown → Dify Workflow API → loader |

##### Airflow orchestration

- **DAG**: `finsight_etl` — `@daily`, 3 retries × 5-minute delay
- **Idempotency**: `pipeline_runs` table tracks each PDF path; only unprocessed PDFs are picked up each run
- **Airflow stack**: `docker-compose.airflow.yml` — isolated `postgres-airflow` (port 5433), webserver (port 8080), scheduler; never touches the main finsight DB

##### Database loader

- `db.loader.upsert_report(payload)` — `INSERT … ON CONFLICT (ticker, fiscal_year) DO UPDATE` for all 5 tables
- `db.loader.mark_processed(pdf_path, status, ...)` — idempotent tracking in `pipeline_runs`
- Full transaction with rollback on any DB exception

##### Langfuse observability

Every Gemini call in `extract_quantitative` and `extract_qualitative` attaches a `langfuse.callback.CallbackHandler`, capturing model, prompt, response, token usage, and latency at https://cloud.langfuse.com.

#### How to run the pipeline locally

```bash
# Install deps
pip install -r src/pipeline/requirements.txt

# Smoke test (no DB/LLM needed)
python tests/test_pipeline.py --smoke

# Run on a single PDF (requires GOOGLE_API_KEY + DATABASE_URL in .env)
python -m pipeline.graph --pdf src/scraper/data/raw/MAYBANK/MAYBANK_2024_Q3.pdf

# Full integration test (DB + LLM + real PDF)
python tests/test_pipeline.py --integration --pdf src/scraper/data/raw/MAYBANK/MAYBANK_2024_Q3.pdf

# Watch mode — auto-triggers pipeline when scraper drops a new PDF
python tests/test_pipeline.py --watch

# Start Airflow (after main stack is running)
docker compose -f docker-compose.airflow.yml up --build
# UI → http://localhost:8080  (admin/admin)
```

#### PDF directory convention

The scraper writes to `src/scraper/data/raw/{TICKER}/{TICKER}_{YEAR}_{QUARTER}.pdf`.  
The DAG reads `FINSIGHT_RAW_DIR` env var (defaults to `src/scraper/data/raw`) and derives `ticker`, `fiscal_year`, `report_period` from the filename automatically.

#### Dependencies added (ETL)

| Package | Version | Purpose |
|---|---|---|
| `langchain-google-genai` | ≥2.0 | Gemini LLM integration |
| `langchain` + `langchain-core` | ≥0.3 | Prompt templates, text splitter |
| `langgraph` | ≥0.2 | State machine orchestration |
| `langfuse` | ≥2.0 | LLM observability callbacks |
| `llama-cloud` | ≥0.1 | LlamaParse PDF parsing API |
| `pymupdf` | ≥1.24 | PyMuPDF fallback extraction |
| `pydantic` | ≥2.0 | Schema validation |
| `apache-airflow` | 2.9.3 | DAG orchestration |
| `sqlalchemy` + `psycopg2-binary` | — | PostgreSQL UPSERT loader |
| `requests` | ≥2.31 | Dify API client |
| `python-dotenv` | ≥1.0 | `.env` loading |
