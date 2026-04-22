import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, SessionLocal
from models import Base
from seed import seed_if_empty
from routers import companies, financials
from routers import search

TAGS_METADATA = [
    {
        "name": "health",
        "description": "Liveness and readiness probes.",
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
            "Unified payload-based query endpoint. POST a ticker, statement type, "
            "and optional fiscal year to retrieve any financial record in one call."
        ),
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="FinSight API",
    description=(
        "Financial data API for Malaysian Blue-Chip companies. "
        "Provides company profiles, KPI summaries, income statements, "
        "balance sheets, cash flows, qualitative insights, and a unified "
        "search endpoint — all without authentication in Phase 3."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

# --- CORS ----------------------------------------------------------------
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- Routers -------------------------------------------------------------
app.include_router(companies.router)
app.include_router(financials.router)
app.include_router(search.router)


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "FinSight API", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
