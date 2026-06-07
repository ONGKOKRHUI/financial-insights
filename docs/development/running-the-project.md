# Running the Project

## Local modes

Use one of these two local execution modes:

1. **App stack mode (no Airflow):**
   - `docker compose up -d` for backend/frontend/postgres only
   - Run ingestion manually when needed via `src/jobs/weekly_ingestion.py`
2. **Airflow mode (Docker):**
   - Uses `docker-compose.airflow.yml` + `dags/finsight_etl_dag.py`
   - Intended for local orchestration testing and DAG debugging.

Cloud deployment does **not** use internal Python scheduling.  
For production trigger operations, see `docs/development/pipeline-trigger-runbook.md`.

---

## Start core app stack

```bash
docker compose up -d
```

This starts:
- `postgres` (finsight DB) on `localhost:5432`
- `backend` on `localhost:8000`
- `frontend` on `localhost:3000`

---

## Weekly ingestion path (manual local run)

Run one full weekly ingestion pass manually:

```bash
PYTHONPATH=src python -m jobs.weekly_ingestion --latest-only
```

Useful flags:

```bash
PYTHONPATH=src python -m jobs.weekly_ingestion --skip-scrape --dry-run
PYTHONPATH=src python -m jobs.weekly_ingestion --full-backfill --limit 5
```

---

## Airflow local mode (Docker)

1. Ensure `.env` is configured (see `docs/data-engineering/etl-pipeline.md` for required keys).
   - For Docker Airflow, set `AIRFLOW_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/finsight`.
2. Start Airflow stack:

```bash
docker compose -f docker-compose.airflow.yml up -d --build
```

3. Open Airflow UI: `http://localhost:8080` (`admin` / `admin`).
4. Trigger DAG:

```bash
docker compose -f docker-compose.airflow.yml exec -T airflow-webserver \
  airflow dags trigger finsight_etl
```

5. Smoke-test DAG end-to-end:

```bash
python tests/test_phase4_airflow_pipeline_local.py
```

Fast local check (recommended default):

```bash
# Process only 1 unprocessed PDF
python tests/test_phase4_airflow_pipeline_local.py --max-pdfs 1

# Process up to 3 PDFs
python tests/test_phase4_airflow_pipeline_local.py --max-pdfs 3
```

---

## Switch pipelines locally (LangGraph vs Dify)

Set `PIPELINE_ENGINE` in `.env`:

- `PIPELINE_ENGINE=langgraph` (default)
- `PIPELINE_ENGINE=dify`

Then restart Airflow containers:

```bash
docker compose -f docker-compose.airflow.yml down
docker compose -f docker-compose.airflow.yml up -d --build
```

Run validation harnesses with explicit overrides if needed:

```bash
python tests/test_phase4_airflow_pipeline_local.py --pipeline-engine langgraph
python tests/test_phase4_airflow_pipeline_local.py --pipeline-engine dify
```

---

## ML Features pipeline (manual local run)

Compute predictive metrics into `predictive_features` (19 of 21 columns populated today):

```bash
cd src/scraper
pip install -r requirements.txt

# Dry run — inspect payloads without DB writes
python ml_pipeline_runner.py --tickers MAYBANK --dry-run

# Full run for one quarter
python ml_pipeline_runner.py \
  --tickers MAYBANK,CIMB,MAXIS \
  --fiscal-year 2025 \
  --fiscal-quarter Q4
```

Required env var: `DATABASE_URL`. Optional overrides: `ML_FEATURE_TICKERS`,
`ML_FEATURE_YEAR`, `ML_FEATURE_QUARTER`.

Apply the database migration first:

```bash
cd src/backend && alembic upgrade head
```

See [ML Features ETL](../data-engineering/ml-features-etl.md) for the full
reference.

Trigger via Airflow (local Docker):

```bash
docker compose -f docker-compose.airflow.yml exec -T airflow-webserver \
  airflow dags trigger ml_features_etl
```

---

## Validation check

```bash
PYTHONPATH=src python -m validation.validate_extraction_accuracy \
  --ground-truth ground_truth/mock_ground_truth.json \
  --output validation_report.json
```

---

## Build and lint

```bash
# Frontend
cd frontend
npm run lint
npm run build

# Backend/Python tests from repo root
cd ..
python -m pytest tests/test_phase4_run_pdf_pipeline_validation.py -q
```
