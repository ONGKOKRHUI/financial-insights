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
| [Data Engineering](data-engineering/scraping-system.md) | Scraping, parsing, and ETL pipeline | ✅ Current |
| [Backend](backend/fastapi-architecture.md) | FastAPI services and database schema | ✅ Current |
| [API Reference](api-reference/overview.md) | Endpoints, auth, and usage examples | ✅ Current |
| [Frontend](frontend/architecture.md) | Next.js dashboard and state management | ✅ Current |
| [AI Systems](ai-systems/rag-pipeline.md) | RAG, LLM analysis, and agents | ✅ Current |
| [MLOps](mlops/model-training.md) | Model training, tracking, and deployment | 🚧 Planned |
| [System Design](system-design/scaling.md) | Scaling, reliability, and data quality | 🚧 Planned |
| [Development](development/environment-setup.md) | Local setup and contribution guide | ✅ Current |

---

## Development Phases

```
Phase 1 ── MVP & Data Acquisition          ← Weeks 1–3
Phase 2 ── ETL Pipeline & Database         ← Weeks 4–7
Phase 3 ── RAG & Backend API               ← Weeks 8–11
Phase 4 ── Full-Stack Dashboard & Auth     ← Weeks 12–16
Phase 5 ── Agentic Workflows               ← Weeks 17–19
Phase 6 ── ML Models & Production CI/CD   ← Weeks 21–24
```

---

## Tech Stack at a Glance

=== "Frontend"
    - **Next.js** — React framework for the web dashboard
    - **Zustand** — Lightweight client-side state management
    - **TanStack Query** — Server state and data fetching
    - **Recharts / Chart.js** — Financial data visualizations

=== "Backend"
    - **FastAPI** — High-performance Python API framework
    - **PostgreSQL + pgvector** — Relational store + vector embeddings
    - **Elasticsearch** — Hybrid keyword + semantic search
    - **Redis** — Caching and rate-limiting

=== "Data Engineering"
    - **Playwright / Selenium** — Dynamic web scraping
    - **PyMuPDF** — PDF parsing and table extraction
    - **Airflow / Prefect** — Pipeline orchestration
    - **Docker** — Containerized pipeline execution

=== "AI Systems"
    - **RAG Pipelines** — Retrieval-Augmented Generation over financial docs
    - **LangGraph** — Multi-agent orchestration and routing
    - **MCP Tools** — Model Context Protocol for agent tool-use
    - **Langfuse** — AI observability, cost, and latency tracking

=== "MLOps"
    - **MLflow** — Experiment tracking and model registry
    - **PyTorch / XGBoost** — Model training
    - **GitHub Actions** — CI/CD pipeline
    - **Docker** — Reproducible build and deployment
