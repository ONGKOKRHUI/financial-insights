# FinSight API

FinSight API is an automated platform that scrapes, parses, and analyzes financial reports from Malaysian Blue-Chip companies, transforming unstructured PDFs into structured JSON and actionable intelligence. It bridges the gap between raw financial disclosures and actionable developer tooling, surfacing data through a developer API, an interactive dashboard, and an AI-powered analysis layer.

## 🚀 Features

### For Investors & Analysts (Free Tier)
- **General Dashboard**: High-level visualizations and basic company metrics of Malaysian Blue-Chip companies (e.g., Maybank, CIMB, TNB).
- **Automated Data Pipeline**: Continuous monitoring and parsing of quarterly and yearly financial reports.
- **Cleaned Financial Data**: Structured extraction of complex financial tables from raw PDFs.

### For Algorithmic Traders & Pro Users (Paid Tier)
- **Deep Financial Analysis**: Access to a detailed dashboard with advanced visualizations and historical trends.
- **AI Chatbot Interface**: Custom queries over company financials using advanced RAG and autonomous agent workflows.
- **Developer API**: Direct access to parsed structured JSON and LLM summaries for model training and integration into trading models.
- **Multi-Agent Reasoning**: Dynamic agent skills (via MCP) to fetch from vector stores or write SQL queries against financial data.

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | Next.js 16 + React 19 + TypeScript |
| **Styling** | Tailwind CSS v4 + Recharts |
| **State Management** | Zustand + TanStack Query |
| **Backend** | Python 3.12 + FastAPI + Uvicorn |
| **Database** | PostgreSQL (Supabase) + SQLAlchemy |
| **Data Engineering** | Playwright / Selenium, PyMuPDF |
| **AI / ML** | RAG Pipelines, LangGraph, MCP Tools, Langfuse, MLflow |
| **Infrastructure** | Docker Compose (local dev), GitHub Actions (CI/CD) |
| **Hosting** | Vercel (frontend) · Render (backend) · Supabase (database) |

## 📂 Project Structure

```
financial-insights/
├── src/
│   ├── backend/            # FastAPI application
│   │   ├── main.py         # App entry point, CORS, lifespan
│   │   ├── database.py     # SQLAlchemy engine + session
│   │   ├── models.py       # ORM models
│   │   ├── schemas.py      # Pydantic schemas
│   │   ├── seed.py         # Idempotent DB seed from mock data
│   │   ├── routers/        # companies.py, financials.py
│   │   ├── data/           # mock_data.py (seed source)
│   │   ├── requirements.txt
│   │   ├── render.yaml     # Render IaC (web service config)
│   │   └── Dockerfile      # Local development only
│   └── scraper/            # Data ingestion pipelines
├── frontend/               # Next.js web application
│   ├── src/
│   │   ├── app/api/        # Route Handlers (BFF proxy to FastAPI)
│   │   ├── components/     # UI components
│   │   ├── hooks/          # TanStack Query hooks
│   │   └── lib/api.ts      # Typed API client
│   ├── vercel.json
│   └── .env.local.example
├── docs/                   # MkDocs technical documentation
├── dev-documentation/      # Project plans and notes
├── docker-compose.yml      # Local development only
└── .env.example            # Local env var template
```

## 🔑 Environment Variables

### Backend (set in Render dashboard for production)

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Supabase PostgreSQL connection string | `postgresql://postgres.[ref]:[pwd]@aws-0-[region].pooler.supabase.com:6543/postgres` |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | `https://your-app.vercel.app` |

### Frontend (set in Vercel dashboard for production)

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Public Render backend URL | `https://finsight-api.onrender.com` |

### GitHub Actions secrets (for CI/CD)

| Secret | Description |
|--------|-------------|
| `RENDER_BACKEND_URL` | Your Render backend URL (no trailing slash) |
| `RENDER_DEPLOY_HOOK_URL` | Render deploy hook URL for backend |
| `VERCEL_TOKEN` | Vercel personal access token |
| `VERCEL_ORG_ID` | Vercel organization ID |
| `VERCEL_PROJECT_ID` | Vercel project ID |

## ⚡ Quick Start (Local Development)

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop
- Git

### Local Setup with Docker Compose

1. **Clone the repository**:
```bash
git clone https://github.com/ONGKOKRHUI/financial-insights.git
cd financial-insights
```

2. **Configure environment**:
```bash
# Root .env (used by Docker Compose)
cp .env.example .env

# Frontend .env.local
cp frontend/.env.local.example frontend/.env.local
```

3. **Start all services** (PostgreSQL + backend + frontend):
```bash
docker compose up
```

4. **Access the app**:

| Service | URL |
|---------|-----|
| Frontend Dashboard | http://localhost:3000 |
| Backend API Docs | http://localhost:8000/docs |
| Backend Health | http://localhost:8000/health |

### Local Setup without Docker (backend only)

```bash
cd src/backend
pip install -r requirements.txt
# Set DATABASE_URL to a running PostgreSQL instance
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finsight
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🚢 Production Deployment

The project is deployed across three independent services. Docker is **not** used in production.

```
Vercel (frontend)  →  Render (backend API)  →  Supabase (PostgreSQL)
```

### Step 1 — Supabase (Database)

1. Create a new Supabase project at [supabase.com](https://supabase.com).
2. Go to **Project Settings → Database → Connection string → URI** (enable **Connection pooling** → Session mode).
3. Copy the URI — it looks like:
   ```
   postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
4. The database schema and seed data are applied automatically on first backend startup via `Base.metadata.create_all()` and `seed_if_empty()`.

> **Manual step**: No migrations to run — the backend creates tables on startup.

### Step 2 — Render (Backend)

1. Connect your GitHub repo to [render.com](https://render.com).
2. Render auto-detects `src/backend/render.yaml` and creates the **finsight-api** web service.
3. In the Render dashboard → **Environment**, add:
   - `DATABASE_URL` → your Supabase connection string (from Step 1)
   - `ALLOWED_ORIGINS` → your Vercel frontend URL, e.g. `https://your-app.vercel.app`
4. Deploy. The start command is:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
5. Note your backend URL (e.g. `https://finsight-api.onrender.com`).

> **Manual step**: Set `DATABASE_URL` and `ALLOWED_ORIGINS` in Render → Environment.

### Step 3 — Vercel (Frontend)

1. Import the GitHub repo at [vercel.com](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. In the Vercel dashboard → **Settings → Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL` → your Render backend URL, e.g. `https://finsight-api.onrender.com`
4. Deploy. Vercel auto-detects Next.js from `frontend/vercel.json`.

> **Manual step**: Set `NEXT_PUBLIC_API_URL` in Vercel → Environment Variables.

### Step 4 — GitHub Actions (CI/CD)

Add the following secrets in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `RENDER_BACKEND_URL` | `https://finsight-api.onrender.com` |
| `RENDER_DEPLOY_HOOK_URL` | From Render dashboard → Settings → Deploy Hook |
| `VERCEL_TOKEN` | From Vercel → Account Settings → Tokens |
| `VERCEL_ORG_ID` | From Vercel project settings |
| `VERCEL_PROJECT_ID` | From Vercel project settings |

CI/CD pipelines run automatically on push to `main`:
- `deploy-backend.yml` — validates Python imports, triggers Render deploy hook
- `deploy-frontend.yml` — type-checks, builds, and deploys to Vercel

## 🏗 Architecture

FinSight follows a modern, decoupled architecture where each service is independently deployed:

- **Web Scraper & ETL**: Automated data ingestion using Playwright and PyMuPDF to extract tables from Malaysian company reports.
- **Database**: PostgreSQL on Supabase with SQLAlchemy ORM. Schema is managed via `Base.metadata.create_all()`.
- **Backend**: FastAPI on Render — orchestrates data retrieval and exposes REST endpoints. CORS is configured via `ALLOWED_ORIGINS` env var.
- **Frontend**: Next.js on Vercel — uses Route Handlers as a BFF (Backend-For-Frontend) proxy to the FastAPI backend. Backend URL is injected via `NEXT_PUBLIC_API_URL`.
- **AI Engine** *(planned)*: Multi-agent system powered by LangGraph with MCP tools for reasoning over financial metrics.

For deep-dive documentation, run `mkdocs serve` in the project root or view the [Documentation site](https://ONGKOKRHUI.github.io/financial-insights).

## 🧪 Testing

```bash
# Backend — validate imports and syntax
cd src/backend && python -m compileall .

# Frontend — type check
cd frontend && npx tsc --noEmit
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
