"""FinSight FastAPI application entry point.

Registers all routers and middleware.  The lifespan handler runs
database table creation and seeds demo data on first startup.

Phase 4 additions
-----------------
- Auth router  — ``/auth/**``           (register, login, refresh, logout)
- Users router — ``/users/**``          (profile, API key management)
- Admin router — ``/admin/**``          (admin user management dashboard)
- Webhooks     — ``/webhooks/stripe``   (Stripe subscription lifecycle)
- CORS updated to allow credentials (required for HttpOnly cookie auth)
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal, engine
from models import Base
from routers import admin, companies, financials, jarvis, pipeline_trigger, search
from routers import auth as auth_router
from routers import users as users_router
from routers import webhooks
from routers import rag as rag_router
from seed import seed_if_empty

logger = logging.getLogger(__name__)

TAGS_METADATA = [
    {
        "name": "health",
        "description": "Liveness and readiness probes.",
    },
    {
        "name": "auth",
        "description": (
            "Registration, login, token refresh, and logout. "
            "Tokens are delivered as HttpOnly cookies — no body parsing needed."
        ),
    },
    {
        "name": "users",
        "description": "Authenticated user profile and developer API key management.",
    },
    {
        "name": "admin",
        "description": "Admin-only user management dashboard (requires ``admin`` role).",
    },
    {
        "name": "companies",
        "description": (
            "Company profiles, KPI summaries, and qualitative insights for the 8 "
            "covered Malaysian Blue-Chip companies."
        ),
    },
    {
        "name": "financials",
        "description": (
            "Annual financial statement history — income statements, balance sheets, "
            "and cash flow statements. Five years of data per company."
        ),
    },
    {
        "name": "search",
        "description": (
            "Financial data query and live search endpoints.  "
            "``POST /search`` — unified payload-based query: POST a ticker, statement type, "
            "and optional fiscal year to retrieve any financial record in one call.  "
            "``GET /search/live?q=...`` — search-as-you-type Elasticsearch suggestions "
            "returning the top 5 most relevant docs/page results for partial input.  "
            "Both endpoints require a valid session cookie or X-API-Key header."
        ),
    },
    {
        "name": "webhooks",
        "description": "Stripe webhook receiver — not for direct client use.",
    },
    {
        "name": "pipeline",
        "description": (
            "Externally triggered weekly ingestion endpoint for cloud deployment. "
            "Protected by x-api-key and designed for GitHub Actions cron calls."
        ),
    },
    {
        "name": "rag",
        "description": (
            "Phase 5 RAG — natural-language question answering over ingested "
            "Markdown documentation using Elasticsearch hybrid search (BM25 + KNN) "
            "and Gemini-grounded answers."
        ),
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables and seed demo data on startup."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    # RAG: ensure ES docs index + alias exist (idempotent; fresh Docker ES has none)
    if os.getenv("RAG_BOOTSTRAP_ES_INDEX", "1") not in ("0", "false", "False"):
        try:
            from services.es_client import get_es_client
            from services.es_docs_index import ensure_docs_index

            ensure_docs_index(get_es_client())
        except Exception as exc:
            logger.warning("Elasticsearch docs index bootstrap skipped: %s", exc)
    yield


app = FastAPI(
    title="FinSight API",
    description=(
        "Financial data and analytics API for Malaysian Blue-Chip companies. "
        "Provides company profiles, KPI summaries, income statements, balance sheets, "
        "cash flows, qualitative insights, and a unified search endpoint. "
        "Phase 4: JWT HttpOnly cookie authentication, RBAC (free/paid/admin roles), "
        "and Stripe subscription integration."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow_credentials must be True for HttpOnly cookies to work
# ---------------------------------------------------------------------------
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,           # required for cookie-based auth
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(admin.router)
app.include_router(webhooks.router)
app.include_router(companies.router)
app.include_router(financials.router)
app.include_router(search.router)
app.include_router(jarvis.router)
app.include_router(pipeline_trigger.router)
app.include_router(rag_router.router)


@app.get("/", tags=["health"])
def root():
    """Root health check — returns service name and version."""
    return {"status": "ok", "service": "FinSight API", "version": "2.0.0"}


@app.get("/health", tags=["health"])
def health():
    """Liveness probe used by Render and CI pipelines."""
    from services.es_client import es_health

    return {"status": "ok", "elasticsearch": es_health()}
