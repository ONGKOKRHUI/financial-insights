"""
FinSight API — Phase 3 Integration Test
========================================
This script demonstrates how an **external user** interacts with the
FinSight REST API over HTTP.  It is the single, self-contained reference
for every endpoint shipped in Phase 3:

    GET  /health
    GET  /companies
    GET  /companies/{ticker}
    GET  /companies/{ticker}/summary
    GET  /companies/{ticker}/qualitative
    GET  /financials/{ticker}/income-statement
    GET  /financials/{ticker}/balance-sheet
    GET  /financials/{ticker}/cash-flow
    POST /search   ← unified payload-based query endpoint

Usage
-----
1.  Make sure the backend is running.
    Local:      docker compose up   (or uvicorn in src/backend/)
    Production: uses FINSIGHT_BASE_URL env-var (defaults to Render URL)

2.  Run:
        python -m pytest tests/test_phase3_api_integration.py -v

    Or execute directly for a human-readable walkthrough:
        python tests/test_phase3_api_integration.py

Environment variables
---------------------
FINSIGHT_BASE_URL   Base URL of the FinSight backend.
                    Default: https://finsight-api.onrender.com
"""

import json
import os
import sys

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = os.getenv(
    "FINSIGHT_BASE_URL",
    "https://financial-insights-grit.onrender.com",
).rstrip("/")

TIMEOUT = 60  # seconds per request

# Tickers available in the seeded database
ALL_TICKERS = ["MAYBANK", "CIMB", "TNB", "PETRONAS", "MAXIS", "TM", "GENTING", "SUNWAY"]

# ---------------------------------------------------------------------------
# API availability check — skip entire module if the backend is not reachable
# ---------------------------------------------------------------------------

def _api_is_available() -> tuple[bool, str]:
    """Return (True, "") if the API is up, or (False, reason) if not."""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=60)
        if r.status_code == 200:
            try:
                if r.json().get("status") == "ok":
                    return True, ""
            except Exception:
                pass
        return False, f"HTTP {r.status_code} — {r.text[:120].strip()}"
    except requests.exceptions.ConnectionError as exc:
        return False, f"Connection error: {exc}"
    except requests.exceptions.Timeout:
        return False, "Timed out after 60 s"


_API_UP, _API_SKIP_REASON = _api_is_available()

pytestmark = pytest.mark.skipif(
    not _API_UP,
    reason=f"FinSight backend not reachable at {BASE_URL} — {_API_SKIP_REASON}",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(path: str, **kwargs) -> requests.Response:
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, timeout=TIMEOUT, **kwargs)
    return resp


def _post(path: str, payload: dict, **kwargs) -> requests.Response:
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, json=payload, timeout=TIMEOUT, **kwargs)
    return resp


def _safe_json(resp: requests.Response):
    """Return parsed JSON or the raw text if the body is not JSON."""
    try:
        return resp.json()
    except Exception:
        return resp.text


def _print_result(label: str, resp: requests.Response) -> None:
    """Print a compact summary when running as a standalone script."""
    status = "✅ PASS" if resp.ok else f"❌ FAIL ({resp.status_code})"
    body = _safe_json(resp)
    body_str = json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    print(f"\n{status}  {label}")
    print(f"  → {resp.request.method} {resp.url}")
    print(f"  ← {body_str[:200]}")


# ===========================================================================
# Test: Health
# ===========================================================================

def test_health():
    """
    GET /health

    Expected: {"status": "ok"}

    The simplest possible check — confirms the backend is reachable and
    the web process is alive.
    """
    resp = _get("/health")
    _print_result("Health check", resp)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.json()
    assert body.get("status") == "ok", f"Unexpected body: {body}"


# ===========================================================================
# Test: List Companies
# ===========================================================================

def test_list_companies():
    """
    GET /companies

    Expected: array of 8 company summary objects, each with
    ticker / name / sector / market_cap_bln / currency.
    """
    resp = _get("/companies")
    _print_result("List all companies", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list), "Expected a JSON array"
    assert len(data) == 8, f"Expected 8 companies, got {len(data)}"

    # Validate schema of the first item
    first = data[0]
    for field in ("ticker", "name", "sector", "market_cap_bln", "currency"):
        assert field in first, f"Field '{field}' missing from company summary"

    # Confirm all expected tickers are present
    returned_tickers = {c["ticker"] for c in data}
    for ticker in ALL_TICKERS:
        assert ticker in returned_tickers, f"Ticker '{ticker}' missing from /companies"


# ===========================================================================
# Test: Get Single Company (valid)
# ===========================================================================

def test_get_company_maybank():
    """
    GET /companies/MAYBANK

    Expected: full CompanyDetail object including description, industry,
    employees, exchange, etc.
    """
    resp = _get("/companies/MAYBANK")
    _print_result("Get MAYBANK company detail", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "MAYBANK"
    assert data["name"] == "Malayan Banking Berhad"
    for field in ("industry", "description", "market_cap_bln",
                  "employees", "founded", "headquarters", "website",
                  "currency", "exchange"):
        assert field in data, f"Field '{field}' missing from company detail"


# ===========================================================================
# Test: Get Single Company (not found)
# ===========================================================================

def test_get_company_not_found():
    """
    GET /companies/INVALID

    Expected: 404 with a 'detail' error message — not a server crash.
    """
    resp = _get("/companies/INVALID_TICKER_XYZ")
    _print_result("Get unknown company → expect 404", resp)

    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    body = resp.json()
    assert "detail" in body, "404 response must contain a 'detail' key"


# ===========================================================================
# Test: KPI Summary
# ===========================================================================

def test_kpi_summary():
    """
    GET /companies/MAYBANK/summary

    Expected: latest KPI summary (FY2024) with revenue_bln, net_income_bln,
    EPS, PE ratio, ROE, debt-to-equity, and dividend yield.
    """
    resp = _get("/companies/MAYBANK/summary")
    _print_result("MAYBANK KPI summary", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "MAYBANK"
    assert data["fiscal_year"] == 2024, "KPI summary should return the latest fiscal year (2024)"
    for field in ("revenue_bln", "net_income_bln", "eps", "roe_pct", "debt_to_equity"):
        assert field in data, f"KPI field '{field}' missing"
    # Sanity-check values are non-negative for a profitable bank
    assert data["revenue_bln"] > 0
    assert data["net_income_bln"] > 0


# ===========================================================================
# Test: Qualitative Insights
# ===========================================================================

def test_qualitative_insights():
    """
    GET /companies/CIMB/qualitative

    Expected: free-text future_outlook string and a list of
    key_strategic_events (not empty).
    """
    resp = _get("/companies/CIMB/qualitative")
    _print_result("CIMB qualitative insights", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "CIMB"
    assert isinstance(data["future_outlook"], str) and len(data["future_outlook"]) > 0
    assert isinstance(data["key_strategic_events"], list)
    assert len(data["key_strategic_events"]) > 0, "key_strategic_events must not be empty"


# ===========================================================================
# Test: Income Statement
# ===========================================================================

def test_income_statement():
    """
    GET /financials/MAYBANK/income-statement

    Expected: 5 years of income statement history (FY2020–FY2024),
    each with revenue, gross profit, net income, EPS, and margin percentages.
    """
    resp = _get("/financials/MAYBANK/income-statement")
    _print_result("MAYBANK income statement (5 years)", resp)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "MAYBANK"
    assert body["currency"] == "MYR"
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 5, f"Expected 5 years of data, got {len(body['data'])}"

    # Validate schema of one entry
    entry = body["data"][0]
    for field in ("fiscal_year", "revenue_bln", "gross_profit_bln",
                  "operating_income_bln", "net_income_bln", "eps",
                  "gross_margin_pct", "operating_margin_pct", "net_margin_pct"):
        assert field in entry, f"Income statement field '{field}' missing"

    # Years should be sorted ascending
    years = [e["fiscal_year"] for e in body["data"]]
    assert years == sorted(years), f"Years not sorted ascending: {years}"


# ===========================================================================
# Test: Balance Sheet
# ===========================================================================

def test_balance_sheet():
    """
    GET /financials/TNB/balance-sheet

    Expected: annual balance sheets with total assets, liabilities, equity,
    cash, and total debt.
    """
    resp = _get("/financials/TNB/balance-sheet")
    _print_result("TNB balance sheet", resp)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "TNB"
    assert len(body["data"]) > 0

    entry = body["data"][0]
    for field in ("fiscal_year", "total_assets_bln", "total_liabilities_bln",
                  "total_equity_bln", "cash_and_equivalents_bln", "total_debt_bln"):
        assert field in entry, f"Balance sheet field '{field}' missing"


# ===========================================================================
# Test: Cash Flow
# ===========================================================================

def test_cash_flow():
    """
    GET /financials/GENTING/cash-flow

    Expected: cash flow statements with operating CF, capex, free CF,
    and dividends paid.
    """
    resp = _get("/financials/GENTING/cash-flow")
    _print_result("GENTING cash flow", resp)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "GENTING"
    assert len(body["data"]) > 0

    entry = body["data"][0]
    for field in ("fiscal_year", "operating_cash_flow_bln", "capital_expenditure_bln",
                  "free_cash_flow_bln", "dividends_paid_bln"):
        assert field in entry, f"Cash flow field '{field}' missing"


# ===========================================================================
# Test: POST /search — Income Statement
# ===========================================================================

def test_search_income_statement():
    """
    POST /search

    Payload: { ticker, statement_type: "income_statement" }
    (no fiscal_year → should return most recent year)

    Expected: latest income statement record for PETRONAS in a unified
    SearchResponse envelope with ticker, statement_type, fiscal_year, data.
    """
    payload = {
        "ticker": "PETRONAS",
        "statement_type": "income_statement",
    }
    resp = _post("/search", payload)
    _print_result("POST /search — PETRONAS income_statement (latest)", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "PETRONAS"
    assert data["statement_type"] == "income_statement"
    assert data["fiscal_year"] is not None
    assert "revenue_bln" in data["data"]
    assert "net_income_bln" in data["data"]


# ===========================================================================
# Test: POST /search — Balance Sheet with fiscal_year filter
# ===========================================================================

def test_search_balance_sheet_specific_year():
    """
    POST /search

    Payload: { ticker, statement_type: "balance_sheet", fiscal_year: 2022 }

    Expected: exactly FY2022 balance sheet data — confirms the optional
    fiscal_year filter routes to the right row.
    """
    payload = {
        "ticker": "CIMB",
        "statement_type": "balance_sheet",
        "fiscal_year": 2022,
    }
    resp = _post("/search", payload)
    _print_result("POST /search — CIMB balance_sheet FY2022", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "CIMB"
    assert data["fiscal_year"] == 2022, f"Expected FY2022, got {data['fiscal_year']}"
    assert "total_assets_bln" in data["data"]


# ===========================================================================
# Test: POST /search — KPI
# ===========================================================================

def test_search_kpi():
    """
    POST /search

    Payload: { ticker, statement_type: "kpi" }

    Expected: KPI summary envelope with ROE, D/E, EPS, dividend yield, etc.
    """
    payload = {
        "ticker": "MAXIS",
        "statement_type": "kpi",
    }
    resp = _post("/search", payload)
    _print_result("POST /search — MAXIS kpi", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "MAXIS"
    assert data["statement_type"] == "kpi"
    kpi = data["data"]
    for field in ("revenue_bln", "net_income_bln", "eps", "roe_pct", "debt_to_equity"):
        assert field in kpi, f"KPI field '{field}' missing from /search response"


# ===========================================================================
# Test: POST /search — Cash Flow
# ===========================================================================

def test_search_cash_flow():
    """
    POST /search

    Payload: { ticker, statement_type: "cash_flow" }
    """
    payload = {
        "ticker": "TM",
        "statement_type": "cash_flow",
    }
    resp = _post("/search", payload)
    _print_result("POST /search — TM cash_flow", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "TM"
    assert "operating_cash_flow_bln" in data["data"]
    assert "free_cash_flow_bln" in data["data"]


# ===========================================================================
# Test: POST /search — Qualitative
# ===========================================================================

def test_search_qualitative():
    """
    POST /search

    Payload: { ticker, statement_type: "qualitative" }

    Expected: future_outlook and key_strategic_events list inside data.
    """
    payload = {
        "ticker": "SUNWAY",
        "statement_type": "qualitative",
    }
    resp = _post("/search", payload)
    _print_result("POST /search — SUNWAY qualitative", resp)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "SUNWAY"
    assert "future_outlook" in data["data"]
    assert isinstance(data["data"]["key_strategic_events"], list)


# ===========================================================================
# Test: POST /search — invalid ticker → 404
# ===========================================================================

def test_search_invalid_ticker():
    """
    POST /search — unknown ticker

    Expected: 404 with a meaningful detail message, NOT a 500.
    """
    payload = {
        "ticker": "DOESNOTEXIST",
        "statement_type": "income_statement",
    }
    resp = _post("/search", payload)
    _print_result("POST /search — unknown ticker → expect 404", resp)

    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    assert "detail" in resp.json()


# ===========================================================================
# Test: POST /search — invalid statement_type → 422
# ===========================================================================

def test_search_invalid_statement_type():
    """
    POST /search — bad statement_type value

    Expected: 422 Unprocessable Entity — FastAPI's Pydantic validation
    rejects the enum value before the handler is ever called.
    """
    payload = {
        "ticker": "MAYBANK",
        "statement_type": "not_a_real_type",
    }
    resp = _post("/search", payload)
    _print_result("POST /search — invalid statement_type → expect 422", resp)

    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


# ===========================================================================
# Standalone runner — human-readable walkthrough
# ===========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print(f"  FinSight API — Phase 3 Integration Test")
    print(f"  Base URL: {BASE_URL}")
    print("=" * 70)

    if not _API_UP:
        print(f"\n  ⚠  Backend not reachable — {_API_SKIP_REASON}")
        print("  Start the backend locally or set FINSIGHT_BASE_URL.")
        print("=" * 70)
        sys.exit(1)


    tests = [
        test_health,
        test_list_companies,
        test_get_company_maybank,
        test_get_company_not_found,
        test_kpi_summary,
        test_qualitative_insights,
        test_income_statement,
        test_balance_sheet,
        test_cash_flow,
        test_search_income_statement,
        test_search_balance_sheet_specific_year,
        test_search_kpi,
        test_search_cash_flow,
        test_search_qualitative,
        test_search_invalid_ticker,
        test_search_invalid_statement_type,
    ]

    passed = 0
    failed = 0
    errors = []

    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append((fn.__name__, str(exc)))
            print(f"  ⚠  Exception: {exc}")

    print("\n" + "=" * 70)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if errors:
        print("\n  Failed tests:")
        for name, msg in errors:
            print(f"    ✗ {name}: {msg}")
    print("=" * 70)

    sys.exit(1 if failed else 0)
