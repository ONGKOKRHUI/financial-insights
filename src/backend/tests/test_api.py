"""
End-to-end API test suite — 13 tests covering all endpoints.

Uses the session-scoped TestClient from conftest.py which injects an
in-memory SQLite database; no live PostgreSQL connection is required.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import models


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    # Phase 5: /health now includes ES diagnostics; key must be present
    assert "elasticsearch" in body


def test_health_db(client: TestClient):
    res = client.get("/health/db")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["company_count"] >= 1


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

def test_list_companies(client: TestClient):
    res = client.get("/companies")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 8
    first = data[0]
    assert "ticker" in first
    assert "name" in first
    assert "sector" in first
    assert "market_cap_bln" in first


def test_get_company_valid(client: TestClient):
    res = client.get("/companies/MAYBANK")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "MAYBANK"
    assert data["name"] == "Malayan Banking Berhad"
    assert "industry" in data
    assert "description" in data
    assert "exchange" in data


def test_get_company_invalid(client: TestClient):
    res = client.get("/companies/INVALID")
    assert res.status_code == 404
    assert "detail" in res.json()


def test_kpi_summary(client: TestClient):
    res = client.get("/companies/MAYBANK/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "MAYBANK"
    assert data["fiscal_year"] == 2024
    assert "revenue_bln" in data
    assert "net_income_bln" in data
    assert "roe_pct" in data


# ---------------------------------------------------------------------------
# Financials
# ---------------------------------------------------------------------------

def test_income_statement(client: TestClient):
    res = client.get("/financials/MAYBANK/income-statement")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "MAYBANK"
    assert data["currency"] == "MYR"
    assert len(data["data"]) == 5
    entry = data["data"][0]
    assert "fiscal_year" in entry
    assert "revenue_bln" in entry
    assert "net_income_bln" in entry


def test_income_statement_allows_null_metrics(client: TestClient, db_session: Session):
    db_session.query(models.IncomeStatement).filter(
        models.IncomeStatement.ticker == "MAYBANK",
        models.IncomeStatement.fiscal_year == 2099,
    ).delete()
    db_session.add(
        models.IncomeStatement(
            ticker="MAYBANK",
            fiscal_year=2099,
            revenue_bln=32.5,
            gross_profit_bln=30.3,
            operating_income_bln=14.1,
            net_income_bln=10.8,
            eps=0.87,
            gross_margin_pct=None,
            operating_margin_pct=None,
            net_margin_pct=None,
        )
    )
    db_session.commit()

    res = client.get("/financials/MAYBANK/income-statement")
    assert res.status_code == 200
    row = next(item for item in res.json()["data"] if item["fiscal_year"] == 2099)
    assert row["gross_margin_pct"] is None
    assert row["operating_margin_pct"] is None
    assert row["net_margin_pct"] is None


def test_balance_sheet(client: TestClient):
    res = client.get("/financials/CIMB/balance-sheet")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "CIMB"
    assert len(data["data"]) > 0
    entry = data["data"][0]
    assert "total_assets_bln" in entry
    assert "total_liabilities_bln" in entry
    assert "total_equity_bln" in entry


def test_cash_flow(client: TestClient):
    res = client.get("/financials/TNB/cash-flow")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "TNB"
    assert len(data["data"]) > 0
    entry = data["data"][0]
    assert "operating_cash_flow_bln" in entry
    assert "free_cash_flow_bln" in entry


def test_qualitative(client: TestClient):
    res = client.get("/companies/MAYBANK/qualitative")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "MAYBANK"
    assert isinstance(data["key_strategic_events"], list)
    assert len(data["key_strategic_events"]) > 0
    assert "future_outlook" in data


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------

def test_search_income(client: TestClient):
    res = client.post("/search", json={"ticker": "MAYBANK", "statement_type": "income_statement"})
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "MAYBANK"
    assert data["statement_type"] == "income_statement"
    assert data["fiscal_year"] is not None
    assert "revenue_bln" in data["data"]
    assert "net_income_bln" in data["data"]


def test_search_kpi(client: TestClient):
    res = client.post("/search", json={"ticker": "CIMB", "statement_type": "kpi"})
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "CIMB"
    assert data["statement_type"] == "kpi"
    assert data["fiscal_year"] is not None
    assert "revenue_bln" in data["data"]
    assert "roe_pct" in data["data"]


def test_search_invalid_ticker(client: TestClient):
    res = client.post(
        "/search",
        json={"ticker": "DOESNOTEXIST", "statement_type": "income_statement"},
    )
    assert res.status_code == 404
    assert "detail" in res.json()


def test_search_invalid_type(client: TestClient):
    res = client.post(
        "/search",
        json={"ticker": "MAYBANK", "statement_type": "not_a_valid_type"},
    )
    assert res.status_code == 422
