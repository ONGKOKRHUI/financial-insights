Listed directory financial-insights
Listed directory src
Listed directory frontend
Listed directory dags
Listed directory .github
Listed directory backend
Listed directory db
Listed directory pipeline
Listed directory workflows
Viewed docker-compose.yml:1-47
Viewed docker-compose.airflow.yml:1-136
Viewed render.yaml:1-35
Viewed vercel.json:1-6
Viewed deploy-backend.yml:1-40
Viewed deploy-frontend.yml:1-56
Viewed database.py:1-29
Listed directory src
Viewed Dockerfile:1-42
Viewed Dockerfile:1-13
Viewed .env.example:1-7
Viewed .env.local.example:1-13
Viewed .env.example:1-94
Viewed main.py:1-141
Listed directory alembic
Listed directory routers
Viewed .env.example:1-13

Now I have a comprehensive picture of the entire repository. Here's the breakdown:

---

## 🗺️ Cloud vs. Local — Code Map

This project has a **clear dual-target architecture**. The same application code runs in both environments, but completely different *infrastructure files* control how it gets deployed.

---

### ☁️ Cloud Deployment (Vercel + Render + Supabase)

These files exist purely for cloud hosting:

| File | Platform | Purpose |
|---|---|---|
| [`frontend/vercel.json`](file:///c:\Users\HP\Documents\repos\financial-insights\frontend\vercel.json) | **Vercel** | Tells Vercel the framework is Next.js, sets build/output commands |
| [`frontend/.vercel/`](file:///c:\Users\HP\Documents\repos\financial-insights\frontend\.vercel) | **Vercel** | Vercel project config generated after `vercel link` (stores project/org IDs) |
| [`src/backend/render.yaml`](file:///c:\Users\HP\Documents\repos\financial-insights\src\backend\render.yaml) | **Render** | Infrastructure-as-code for Render — declares the Python web service, build command (`pip install`), and start command (`uvicorn main:app --port $PORT`) |
| [`.github/workflows/deploy-frontend.yml`](file:///c:\Users\HP\Documents\repos\financial-insights\.github\workflows\deploy-frontend.yml) | **Vercel** | CI/CD — on push to `main`, builds Next.js and calls `vercel --prod` |
| [`.github/workflows/deploy-backend.yml`](file:///c:\Users\HP\Documents\repos\financial-insights\.github\workflows\deploy-backend.yml) | **Render** | CI/CD — on push to `main`, validates backend imports then triggers Render's deploy hook via `curl` |

**Supabase** isn't a file — it's the **database**. The connection is wired in via the `DATABASE_URL` environment variable set in the Render dashboard. The `render.yaml` even has a comment saying: *"This project uses Supabase for PostgreSQL (not Render's built-in DB)."*

**The application code itself** (`src/backend/main.py`, `src/backend/database.py`, etc.) is cloud-agnostic — it just reads `DATABASE_URL` and `ALLOWED_ORIGINS` from env vars. The comment in `database.py` even has a specific fix for cloud:
```python
# Render's free PostgreSQL provides "postgres://" but SQLAlchemy needs "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
```

---

### 🐳 Local Development & Hosting (Docker)

| File | Purpose |
|---|---|
| [`docker-compose.yml`](file:///c:\Users\HP\Documents\repos\financial-insights\docker-compose.yml) | **Main local stack** — spins up 3 containers: `postgres` (port 5432), `backend` FastAPI (port 8000), and `frontend` Next.js (port 3000) all wired together on an internal Docker network |
| [`docker-compose.airflow.yml`](file:///c:\Users\HP\Documents\repos\financial-insights\docker-compose.airflow.yml) | **ETL pipeline stack** — spins up a full Apache Airflow environment (webserver on :8080, scheduler, init) with its own isolated Postgres (port 5433), so it doesn't conflict with the main DB |
| [`src/backend/Dockerfile`](file:///c:\Users\HP\Documents\repos\financial-insights\src\backend\Dockerfile) | Builds the FastAPI image (Python 3.12, installs deps, runs `uvicorn` on port 8000) |
| [`frontend/Dockerfile`](file:///c:\Users\HP\Documents\repos\financial-insights\frontend\Dockerfile) | Multi-stage build for Next.js (deps → build → production runner on port 3000) |
| [`.env.example`](file:///c:\Users\HP\Documents\repos\financial-insights\.env.example) | **Root-level env template for Docker** — has all the `localhost` URLs, Airflow keys, and ETL pipeline secrets. The file header explicitly says *"for LOCAL DEVELOPMENT only"* |
| [`frontend/.env.local.example`](file:///c:\Users\HP\Documents\repos\financial-insights\frontend\.env.local.example) | Frontend-specific local env — points `NEXT_PUBLIC_API_URL` to `localhost:8000` and notes that `INTERNAL_API_URL=http://backend:8000` is only needed inside Docker Compose |
| [`dags/finsight_etl_dag.py`](file:///c:\Users\HP\Documents\repos\financial-insights\dags\finsight_etl_dag.py) | The Airflow DAG definition — only used locally via `docker-compose.airflow.yml` |

---

### 🧠 How It All Connects

```
LOCAL                               CLOUD
──────────────────────────          ──────────────────────────
docker-compose.yml                  GitHub Actions (push to main)
  ├── postgres (Docker)               ├── deploy-frontend.yml → Vercel
  ├── backend (Docker)                └── deploy-backend.yml → Render
  └── frontend (Docker)
                                    Render (Backend API)
docker-compose.airflow.yml            └── reads DATABASE_URL from Supabase
  └── Airflow + postgres-airflow
      └── dags/finsight_etl_dag.py  Vercel (Frontend Next.js)
                                      └── calls Render backend URL
```

**The key insight**: The actual application code in `src/backend/` and `frontend/src/` is **environment-agnostic**. Cloud vs. local is purely decided by which *infrastructure layer* you activate — Docker Compose files for local, and the Render/Vercel config + GitHub Actions for cloud.