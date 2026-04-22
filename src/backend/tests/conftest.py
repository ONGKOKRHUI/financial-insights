"""
Test configuration: in-memory SQLite DB seeded with mock data.

All tests run without a live PostgreSQL connection.  The production
`get_db` dependency is overridden with a session bound to a StaticPool
SQLite engine so every test shares the same in-memory database.

The TestClient is created WITHOUT a context-manager (`with` statement)
to prevent the lifespan from firing — the lifespan would attempt a
PostgreSQL connection that is not available in the test environment.
"""
import json
import os
import sys

# Ensure `src/backend/` is importable before any backend module is loaded.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from data.mock_data import (
    BALANCE_SHEETS,
    CASH_FLOWS,
    COMPANIES,
    INCOME_STATEMENTS,
    KPI_SUMMARIES,
    QUALITATIVE_INSIGHTS,
)
from database import get_db
from main import app

# ---------------------------------------------------------------------------
# Shared in-memory SQLite engine
# StaticPool ensures all sessions share the same single connection so the
# data seeded here is visible to every subsequent request.
# ---------------------------------------------------------------------------
_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)

# Create tables once for the entire test session.
models.Base.metadata.create_all(bind=_ENGINE)


def _seed_test_db() -> None:
    db = _SessionLocal()
    try:
        if db.query(models.Company).first() is not None:
            return

        for data in COMPANIES.values():
            db.add(models.Company(**data))
        db.flush()

        for data in KPI_SUMMARIES.values():
            db.add(models.KPISummary(**data))

        for ticker, rows in INCOME_STATEMENTS.items():
            for row in rows:
                db.add(models.IncomeStatement(ticker=ticker, **row))

        for ticker, rows in BALANCE_SHEETS.items():
            for row in rows:
                db.add(models.BalanceSheet(ticker=ticker, **row))

        for ticker, rows in CASH_FLOWS.items():
            for row in rows:
                db.add(models.CashFlow(ticker=ticker, **row))

        for ticker, data in QUALITATIVE_INSIGHTS.items():
            db.add(
                models.QualitativeInsight(
                    ticker=ticker,
                    fiscal_year=data["fiscal_year"],
                    future_outlook=data["future_outlook"],
                    key_strategic_events=json.dumps(data["key_strategic_events"]),
                )
            )

        db.commit()
    finally:
        db.close()


_seed_test_db()


def _override_get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Session-scoped TestClient.

    Not used as a context manager so the app lifespan (startup/shutdown)
    does not fire — those events try to connect to the production
    PostgreSQL database which is not available during testing.
    """
    return TestClient(app, raise_server_exceptions=True)
