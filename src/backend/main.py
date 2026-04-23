import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, SessionLocal
from models import Base
from seed import seed_if_empty
from routers import companies, financials, jarvis


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
        "Provides company details, KPI summaries, income statements, "
        "balance sheets, cash flows, and qualitative insights."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- CORS ----------------------------------------------------------------
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],   # POST needed for /api/jarvis/voice
    allow_headers=["*"],
)

# --- Routers -------------------------------------------------------------
app.include_router(companies.router)
app.include_router(financials.router)
app.include_router(jarvis.router)


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "FinSight API", "version": "0.2.0"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
