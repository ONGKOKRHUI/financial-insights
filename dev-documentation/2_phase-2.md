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

#### Next steps (full ETL pipeline)

- Set up Airflow or Prefect for orchestration
- Build PyMuPDF / Unstructured PDF parser for financial report ingestion
- Replace seed data with pipeline-generated records in PostgreSQL
