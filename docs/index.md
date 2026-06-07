# FinSight API

> An automated platform that scrapes, parses, and analyzes financial reports from Malaysian public companies — transforming unstructured PDFs into structured data and AI-powered intelligence.

---

## What is FinSight API?

FinSight API bridges the gap between raw financial disclosures and actionable developer tooling. It ingests quarterly and annual reports from Malaysian Blue-Chip companies, extracts structured financial tables, and surfaces the data through a developer API, interactive dashboard, and AI-powered analysis layer.

---

## Quick Navigation

| Section | Description | Status |
|---|---|---|
| [Platform Overview](platform-overview/overview.md) | Goals, monetization, and roadmap | ✅ Current |
| [Architecture](architecture/system-architecture.md) | System design and component map | ✅ Current |
| [Data Engineering](data-engineering/scraping-system.md) | Scraping, PDF ETL, and ML features pipeline | ✅ Current |
| [Backend](backend/fastapi-architecture.md) | FastAPI services, auth, RBAC, and database schema | ✅ Current |
| [API Reference](api-reference/overview.md) | Endpoints, auth, and usage examples | ✅ Current |
| [Frontend](frontend/architecture.md) | Next.js dashboard, routing, and state management | ✅ Current |
| [AI Systems](ai-systems/jarvis-overview.md) | Jarvis voice assistant, intent classification | ✅ Current |
| [RAG Pipeline](ai-systems/rag-pipeline.md) | RAG, LLM analysis, and agents | ✅ Current |
| [MLOps](mlops/model-training.md) | Feature store (19/21 metrics), model training, tracking, deployment | 🚧 In Progress |
| [System Design](system-design/scaling.md) | Scaling, reliability, and data quality | 🚧 Planned |
| [Development](development/environment-setup.md) | Local setup and contribution guide | ✅ Current |

---

## Development Phases

```
Phase 1 ── MVP & Data Acquisition          ← Weeks 1–3   ✅ Complete
Phase 2 ── ETL Pipeline & Database         ← Weeks 4–7   ✅ Complete
Phase 3 ── Backend API & Frontend          ← Weeks 8–11  ✅ Complete
Phase 4 ── Auth, RBAC, Stripe & Dashboard  ← Weeks 12–16 ✅ Complete
Phase 5 ── Agentic Workflows & RAG         ← Weeks 17–19 🚧 Planned
Phase 6 ── ML Models & Production CI/CD    ← Weeks 21–24 🚧 Feature ETL done; training next
```

---

## Tech Stack at a Glance

=== "Frontend"
    - **Next.js 15** — React 19 framework for the web dashboard
    - **Zustand** — Lightweight client-side state management
    - **TanStack Query** — Server state and data fetching
    - **Recharts** — Financial data visualizations
    - **TailwindCSS v4** — Utility-first CSS framework

=== "Backend"
    - **FastAPI** — High-performance Python API framework
    - **PostgreSQL** — Relational database (Supabase-hosted)
    - **SQLAlchemy 2.x** — ORM with declarative models
    - **Alembic** — Database migrations
    - **python-jose + bcrypt** — JWT auth and password hashing
    - **Stripe** — Payment processing and subscription management
    - **Elasticsearch** — Hybrid keyword + semantic search
    - **Redis** — Caching and rate-limiting

=== "Data Engineering"
    - **Playwright** — Stealth web scraping with WAF bypass
    - **LlamaParse** — AI-powered PDF → Markdown conversion
    - **PyMuPDF** — Fallback PDF text extraction
    - **Apache Airflow** — Pipeline orchestration (LocalExecutor)
    - **Docker Compose** — Containerized local development

=== "AI Systems"
    - **RAG Pipelines** — Retrieval-Augmented Generation over financial docs
    - **LangGraph** — Multi-agent orchestration and routing
    - **MCP Tools** — Model Context Protocol for agent tool-use
    - **Langfuse** — AI observability, cost, and latency tracking
    - **Google Gemini** — LLM for structured data extraction and intent classification

=== "MLOps"
    - **predictive_features** — PostgreSQL feature store (19/21 metrics populated weekly)
    - **MLflow** — Experiment tracking and model registry
    - **PyTorch / XGBoost** — Model training
    - **GitHub Actions** — CI/CD pipeline
    - **Docker** — Reproducible build and deployment

=== "Voice AI"
    - **Edge TTS / Google Cloud TTS** — Text-to-speech for Jarvis
    - **Faster-Whisper / Gemini Audio** — Speech-to-text for Jarvis

=== "Infrastructure"
    - **Vercel** — Frontend hosting with edge middleware
    - **Render** — Backend API hosting
    - **Supabase** — Managed PostgreSQL database
    - **GitHub Actions** — CI/CD pipelines
    - **Docker Compose** — Local dev orchestration