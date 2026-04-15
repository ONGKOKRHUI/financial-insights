"""PostgreSQL UPSERT loader for the FinSight ETL pipeline.

Connects to the finsight database via DATABASE_URL and implements:
  - upsert_report(payload)  — UPSERT all financial tables from a validated payload
  - mark_processed(pdf_path, status, error_msg) — update pipeline_runs tracking
  - ensure_pipeline_runs_table() — idempotent DDL for the tracking table

All operations are wrapped in transactions that roll back on any exception.
"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/finsight")
        _engine = create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        logger.info("Database engine created: %s", db_url.split("@")[-1])
    return _engine


@contextmanager
def _transaction():
    """Yield a connected, auto-committing SQLAlchemy connection."""
    engine = _get_engine()
    with engine.connect() as conn:
        with conn.begin():
            yield conn


# ── DDL ────────────────────────────────────────────────────────────────────────

PIPELINE_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          SERIAL PRIMARY KEY,
    pdf_path    TEXT        NOT NULL UNIQUE,
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
    ticker      VARCHAR(20),
    fiscal_year INTEGER,
    run_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_msg   TEXT
);
"""


def ensure_pipeline_runs_table() -> None:
    """Create the pipeline_runs tracking table if it does not already exist."""
    with _transaction() as conn:
        conn.execute(text(PIPELINE_RUNS_DDL))
    logger.info("pipeline_runs table ensured")


# ── UPSERT helpers ─────────────────────────────────────────────────────────────

def _upsert_income_statement(conn, ticker: str, fiscal_year: int, data: dict) -> None:
    if not data:
        return
    conn.execute(
        text("""
        INSERT INTO income_statements
            (ticker, fiscal_year, revenue_bln, gross_profit_bln, operating_income_bln,
             net_income_bln, eps, gross_margin_pct, operating_margin_pct, net_margin_pct)
        VALUES
            (:ticker, :fiscal_year, :revenue_bln, :gross_profit_bln, :operating_income_bln,
             :net_income_bln, :eps, :gross_margin_pct, :operating_margin_pct, :net_margin_pct)
        ON CONFLICT (ticker, fiscal_year) DO UPDATE SET
            revenue_bln            = EXCLUDED.revenue_bln,
            gross_profit_bln       = EXCLUDED.gross_profit_bln,
            operating_income_bln   = EXCLUDED.operating_income_bln,
            net_income_bln         = EXCLUDED.net_income_bln,
            eps                    = EXCLUDED.eps,
            gross_margin_pct       = EXCLUDED.gross_margin_pct,
            operating_margin_pct   = EXCLUDED.operating_margin_pct,
            net_margin_pct         = EXCLUDED.net_margin_pct
        """),
        {"ticker": ticker, "fiscal_year": fiscal_year, **data},
    )


def _upsert_balance_sheet(conn, ticker: str, fiscal_year: int, data: dict) -> None:
    if not data:
        return
    conn.execute(
        text("""
        INSERT INTO balance_sheets
            (ticker, fiscal_year, total_assets_bln, total_liabilities_bln,
             total_equity_bln, cash_and_equivalents_bln, total_debt_bln)
        VALUES
            (:ticker, :fiscal_year, :total_assets_bln, :total_liabilities_bln,
             :total_equity_bln, :cash_and_equivalents_bln, :total_debt_bln)
        ON CONFLICT (ticker, fiscal_year) DO UPDATE SET
            total_assets_bln       = EXCLUDED.total_assets_bln,
            total_liabilities_bln  = EXCLUDED.total_liabilities_bln,
            total_equity_bln       = EXCLUDED.total_equity_bln,
            cash_and_equivalents_bln = EXCLUDED.cash_and_equivalents_bln,
            total_debt_bln         = EXCLUDED.total_debt_bln
        """),
        {"ticker": ticker, "fiscal_year": fiscal_year, **data},
    )


def _upsert_cash_flow(conn, ticker: str, fiscal_year: int, data: dict) -> None:
    if not data:
        return
    conn.execute(
        text("""
        INSERT INTO cash_flows
            (ticker, fiscal_year, operating_cash_flow_bln, capital_expenditure_bln,
             free_cash_flow_bln, dividends_paid_bln)
        VALUES
            (:ticker, :fiscal_year, :operating_cash_flow_bln, :capital_expenditure_bln,
             :free_cash_flow_bln, :dividends_paid_bln)
        ON CONFLICT (ticker, fiscal_year) DO UPDATE SET
            operating_cash_flow_bln  = EXCLUDED.operating_cash_flow_bln,
            capital_expenditure_bln  = EXCLUDED.capital_expenditure_bln,
            free_cash_flow_bln       = EXCLUDED.free_cash_flow_bln,
            dividends_paid_bln       = EXCLUDED.dividends_paid_bln
        """),
        {"ticker": ticker, "fiscal_year": fiscal_year, **data},
    )


def _upsert_qualitative_insight(conn, ticker: str, fiscal_year: int, data: dict) -> None:
    if not data:
        return
    key_events = data.get("key_strategic_events")
    if isinstance(key_events, list):
        key_events = json.dumps(key_events)

    conn.execute(
        text("""
        INSERT INTO qualitative_insights
            (ticker, fiscal_year, future_outlook, key_strategic_events)
        VALUES
            (:ticker, :fiscal_year, :future_outlook, :key_strategic_events)
        ON CONFLICT (ticker, fiscal_year) DO UPDATE SET
            future_outlook       = EXCLUDED.future_outlook,
            key_strategic_events = EXCLUDED.key_strategic_events
        """),
        {
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "future_outlook": data.get("future_outlook"),
            "key_strategic_events": key_events,
        },
    )


def _upsert_kpi_summary(conn, ticker: str, fiscal_year: int, data: dict) -> None:
    if not data:
        return
    conn.execute(
        text("""
        INSERT INTO kpi_summaries
            (ticker, fiscal_year, revenue_bln, net_income_bln, eps, pe_ratio,
             roe_pct, roace_pct, debt_to_equity, dividend_yield_pct)
        VALUES
            (:ticker, :fiscal_year, :revenue_bln, :net_income_bln, :eps, :pe_ratio,
             :roe_pct, :roace_pct, :debt_to_equity, :dividend_yield_pct)
        ON CONFLICT (ticker, fiscal_year) DO UPDATE SET
            revenue_bln       = EXCLUDED.revenue_bln,
            net_income_bln    = EXCLUDED.net_income_bln,
            eps               = EXCLUDED.eps,
            pe_ratio          = EXCLUDED.pe_ratio,
            roe_pct           = EXCLUDED.roe_pct,
            roace_pct         = EXCLUDED.roace_pct,
            debt_to_equity    = EXCLUDED.debt_to_equity,
            dividend_yield_pct = EXCLUDED.dividend_yield_pct
        """),
        {"ticker": ticker, "fiscal_year": fiscal_year, **data},
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def upsert_report(payload: dict) -> None:
    """UPSERT all financial tables from a FinancialReportPayload dict.

    Args:
        payload: Dict matching FinancialReportPayload structure.

    Raises:
        Exception: rolls back the transaction and re-raises on any DB error.
    """
    ticker: str = payload.get("ticker", "")
    fiscal_year: int = payload.get("fiscal_year") or 0

    if not ticker or not fiscal_year:
        raise ValueError(f"payload missing ticker or fiscal_year: {payload}")

    try:
        with _transaction() as conn:
            income_stmt = payload.get("income_statement") or {}
            balance_sheet = payload.get("balance_sheet") or {}
            cash_flow = payload.get("cash_flow") or {}
            qual_insight = payload.get("qualitative_insight") or {}
            kpi = payload.get("kpi_summary") or {}

            # Strip nested ticker/fiscal_year keys before passing to helpers
            def _clean(d: dict) -> dict:
                return {k: v for k, v in d.items() if k not in ("ticker", "fiscal_year", "id")}

            _upsert_income_statement(conn, ticker, fiscal_year, _clean(income_stmt))
            _upsert_balance_sheet(conn, ticker, fiscal_year, _clean(balance_sheet))
            _upsert_cash_flow(conn, ticker, fiscal_year, _clean(cash_flow))
            _upsert_qualitative_insight(conn, ticker, fiscal_year, _clean(qual_insight))
            _upsert_kpi_summary(conn, ticker, fiscal_year, _clean(kpi))

        logger.info("Upserted report: %s FY%s", ticker, fiscal_year)

    except Exception as exc:
        logger.error("DB upsert failed for %s FY%s: %s", ticker, fiscal_year, exc)
        raise


def mark_processed(
    pdf_path: str,
    status: str,
    ticker: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    error_msg: Optional[str] = None,
) -> None:
    """Insert or update a pipeline_runs row for the given PDF path.

    Args:
        pdf_path: Absolute or relative path to the PDF.
        status: One of 'pending', 'processing', 'success', 'error'.
        ticker: Ticker extracted from the filename.
        fiscal_year: Fiscal year extracted from the filename.
        error_msg: Error details if status == 'error'.
    """
    ensure_pipeline_runs_table()
    with _transaction() as conn:
        conn.execute(
            text("""
            INSERT INTO pipeline_runs (pdf_path, status, ticker, fiscal_year, run_at, error_msg)
            VALUES (:pdf_path, :status, :ticker, :fiscal_year, :run_at, :error_msg)
            ON CONFLICT (pdf_path) DO UPDATE SET
                status      = EXCLUDED.status,
                ticker      = EXCLUDED.ticker,
                fiscal_year = EXCLUDED.fiscal_year,
                run_at      = EXCLUDED.run_at,
                error_msg   = EXCLUDED.error_msg
            """),
            {
                "pdf_path": pdf_path,
                "status": status,
                "ticker": ticker,
                "fiscal_year": fiscal_year,
                "run_at": datetime.now(timezone.utc),
                "error_msg": error_msg,
            },
        )
    logger.info("Marked %s as %s in pipeline_runs", pdf_path, status)


def get_unprocessed_pdfs(raw_dir: str) -> list[str]:
    """Return PDF paths in raw_dir that are not yet in pipeline_runs with status='success'.

    Args:
        raw_dir: Root directory to scan recursively for *.pdf files.

    Returns:
        List of absolute PDF path strings not yet successfully processed.
    """
    import glob

    ensure_pipeline_runs_table()

    all_pdfs = set(
        os.path.abspath(p)
        for p in glob.glob(os.path.join(raw_dir, "**", "*.pdf"), recursive=True)
    )

    with _get_engine().connect() as conn:
        result = conn.execute(
            text("SELECT pdf_path FROM pipeline_runs WHERE status = 'success'")
        )
        processed = {row[0] for row in result}

    unprocessed = sorted(all_pdfs - processed)
    logger.info("Found %d/%d unprocessed PDFs", len(unprocessed), len(all_pdfs))
    return unprocessed
