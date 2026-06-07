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
            revenue_bln            = COALESCE(EXCLUDED.revenue_bln,          income_statements.revenue_bln),
            gross_profit_bln       = COALESCE(EXCLUDED.gross_profit_bln,     income_statements.gross_profit_bln),
            operating_income_bln   = COALESCE(EXCLUDED.operating_income_bln, income_statements.operating_income_bln),
            net_income_bln         = COALESCE(EXCLUDED.net_income_bln,       income_statements.net_income_bln),
            eps                    = COALESCE(EXCLUDED.eps,                  income_statements.eps),
            gross_margin_pct       = COALESCE(EXCLUDED.gross_margin_pct,     income_statements.gross_margin_pct),
            operating_margin_pct   = COALESCE(EXCLUDED.operating_margin_pct, income_statements.operating_margin_pct),
            net_margin_pct         = COALESCE(EXCLUDED.net_margin_pct,       income_statements.net_margin_pct)
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
            total_assets_bln         = COALESCE(EXCLUDED.total_assets_bln,         balance_sheets.total_assets_bln),
            total_liabilities_bln    = COALESCE(EXCLUDED.total_liabilities_bln,    balance_sheets.total_liabilities_bln),
            total_equity_bln         = COALESCE(EXCLUDED.total_equity_bln,         balance_sheets.total_equity_bln),
            cash_and_equivalents_bln = COALESCE(EXCLUDED.cash_and_equivalents_bln, balance_sheets.cash_and_equivalents_bln),
            total_debt_bln           = COALESCE(EXCLUDED.total_debt_bln,           balance_sheets.total_debt_bln)
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
            operating_cash_flow_bln  = COALESCE(EXCLUDED.operating_cash_flow_bln,  cash_flows.operating_cash_flow_bln),
            capital_expenditure_bln  = COALESCE(EXCLUDED.capital_expenditure_bln,  cash_flows.capital_expenditure_bln),
            free_cash_flow_bln       = COALESCE(EXCLUDED.free_cash_flow_bln,       cash_flows.free_cash_flow_bln),
            dividends_paid_bln       = COALESCE(EXCLUDED.dividends_paid_bln,       cash_flows.dividends_paid_bln)
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
            revenue_bln        = COALESCE(EXCLUDED.revenue_bln,        kpi_summaries.revenue_bln),
            net_income_bln     = COALESCE(EXCLUDED.net_income_bln,     kpi_summaries.net_income_bln),
            eps                = COALESCE(EXCLUDED.eps,                kpi_summaries.eps),
            pe_ratio           = COALESCE(EXCLUDED.pe_ratio,           kpi_summaries.pe_ratio),
            roe_pct            = COALESCE(EXCLUDED.roe_pct,            kpi_summaries.roe_pct),
            roace_pct          = COALESCE(EXCLUDED.roace_pct,          kpi_summaries.roace_pct),
            debt_to_equity     = COALESCE(EXCLUDED.debt_to_equity,     kpi_summaries.debt_to_equity),
            dividend_yield_pct = COALESCE(EXCLUDED.dividend_yield_pct, kpi_summaries.dividend_yield_pct)
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


# ── Predictive Features (ML training data) ─────────────────────────────────

# All 21 metric columns in insertion order (matches the ORM model).
_PREDICTIVE_FEATURE_METRIC_COLS = [
    # Phase 3 – earning surprises
    "revenue_beat_rate_8q",
    "eps_beat_rate_8q",
    "avg_revenue_surprise_pct",
    "avg_eps_surprise_pct",
    "consecutive_double_beat_quarters",
    # Phase 4 – money flow
    "net_institutional_cash_flow_myr",
    "institutional_flow_to_market_cap_ratio",
    "net_insider_trading_value_myr",
    "options_iv_rank_pct",
    # Phase 1 – fundamentals
    "revenue_yoy_growth_pct",
    "net_income_yoy_growth_pct",
    "gross_margin_delta_qoq_pct",
    "operating_margin_delta_qoq_pct",
    "fcf_yield_pct",
    # Phase 2 – valuation
    "forward_pe_peer_zscore",
    "forward_pe_peer_discount_pct",
    "forward_ps_ratio",
    "peg_ratio",
    # Phase 5 – forward-looking
    "guidance_beat_indicator",
    "backlog_order_book_yoy_growth_pct",
    "sector_peer_earnings_sentiment",
]

_ALL_COLS = ["ticker", "fiscal_year", "fiscal_quarter"] + _PREDICTIVE_FEATURE_METRIC_COLS + ["source_metadata"]


def _build_predictive_features_upsert_sql() -> str:
    """Build the UPSERT SQL for ``predictive_features`` at import time."""
    col_list = ", ".join(_ALL_COLS)
    placeholder_list = ", ".join(f":{col}" for col in _ALL_COLS)
    # Metric columns: prefer incoming value but fall back to existing (partial phase runs)
    metric_updates = "\n            ".join(
        f"{col} = COALESCE(EXCLUDED.{col}, predictive_features.{col}),"
        for col in _PREDICTIVE_FEATURE_METRIC_COLS
    )
    return f"""
        INSERT INTO predictive_features ({col_list})
        VALUES ({placeholder_list})
        ON CONFLICT ON CONSTRAINT uq_predictive_features_ticker_period DO UPDATE SET
            {metric_updates}
            source_metadata = COALESCE(EXCLUDED.source_metadata, predictive_features.source_metadata),
            updated_at = NOW()
    """


_PREDICTIVE_FEATURES_UPSERT_SQL = _build_predictive_features_upsert_sql()

PREDICTIVE_FEATURES_DDL = """
CREATE TABLE IF NOT EXISTS predictive_features (
    id                                   SERIAL PRIMARY KEY,
    ticker                               VARCHAR(20) NOT NULL REFERENCES companies(ticker),
    fiscal_year                          INTEGER     NOT NULL,
    fiscal_quarter                       VARCHAR(2)  NOT NULL,

    revenue_beat_rate_8q                 FLOAT,
    eps_beat_rate_8q                     FLOAT,
    avg_revenue_surprise_pct             FLOAT,
    avg_eps_surprise_pct                 FLOAT,
    consecutive_double_beat_quarters     INTEGER,

    net_institutional_cash_flow_myr      FLOAT,
    institutional_flow_to_market_cap_ratio FLOAT,
    net_insider_trading_value_myr        FLOAT,
    options_iv_rank_pct                  FLOAT,

    revenue_yoy_growth_pct               FLOAT,
    net_income_yoy_growth_pct            FLOAT,
    gross_margin_delta_qoq_pct           FLOAT,
    operating_margin_delta_qoq_pct       FLOAT,
    fcf_yield_pct                        FLOAT,

    forward_pe_peer_zscore               FLOAT,
    forward_pe_peer_discount_pct         FLOAT,
    forward_ps_ratio                     FLOAT,
    peg_ratio                            FLOAT,

    guidance_beat_indicator              BOOLEAN,
    backlog_order_book_yoy_growth_pct    FLOAT,
    sector_peer_earnings_sentiment       FLOAT,

    source_metadata                      TEXT,
    created_at                           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_predictive_features_ticker_period
        UNIQUE (ticker, fiscal_year, fiscal_quarter)
);
CREATE INDEX IF NOT EXISTS ix_predictive_features_ticker ON predictive_features (ticker);
"""


def ensure_predictive_features_table() -> None:
    """Idempotent DDL: create ``predictive_features`` if absent (local dev/Airflow)."""
    with _transaction() as conn:
        conn.execute(text(PREDICTIVE_FEATURES_DDL))
    logger.info("predictive_features table ensured")


def _normalise_payload(payload: dict) -> dict:
    """Return a copy of *payload* with only the columns we insert, defaulting to None."""
    return {col: payload.get(col) for col in _ALL_COLS}


def upsert_predictive_features(payload: dict) -> None:
    """UPSERT a single (ticker, fiscal_year, fiscal_quarter) feature row.

    Missing metric keys are treated as None so a partial phase run does not
    overwrite existing values thanks to the COALESCE update policy.

    Args:
        payload: Dict from ``FeaturePayload.as_loader_payload()`` or equivalent.

    Raises:
        ValueError: If ``ticker``, ``fiscal_year``, or ``fiscal_quarter`` is absent.
        Exception: Re-raises database exceptions after logging.
    """
    ticker = payload.get("ticker", "")
    fiscal_year = payload.get("fiscal_year")
    fiscal_quarter = payload.get("fiscal_quarter", "")

    if not ticker or not fiscal_year or not fiscal_quarter:
        raise ValueError(
            f"predictive_features payload missing key field: "
            f"ticker={ticker!r} fiscal_year={fiscal_year!r} fiscal_quarter={fiscal_quarter!r}"
        )

    params = _normalise_payload(payload)

    try:
        with _transaction() as conn:
            conn.execute(text(_PREDICTIVE_FEATURES_UPSERT_SQL), params)
        logger.info("Upserted predictive_features: %s FY%s %s", ticker, fiscal_year, fiscal_quarter)
    except Exception as exc:
        logger.error(
            "DB upsert failed for predictive_features %s FY%s %s: %s",
            ticker, fiscal_year, fiscal_quarter, exc,
        )
        raise


def upsert_predictive_feature_batch(payloads: list[dict]) -> None:
    """UPSERT a list of feature payloads within a single transaction.

    Errors in individual rows are logged and do not abort the entire batch;
    the failing row is skipped and processing continues.

    Args:
        payloads: List of dicts from ``FeaturePayload.as_loader_payload()``.
    """
    if not payloads:
        logger.info("upsert_predictive_feature_batch: empty batch, nothing to do")
        return

    success, failed = 0, 0
    for payload in payloads:
        try:
            upsert_predictive_features(payload)
            success += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.error(
                "Batch upsert skipped row %s/%s/%s: %s",
                payload.get("ticker"), payload.get("fiscal_year"), payload.get("fiscal_quarter"), exc,
            )

    logger.info(
        "upsert_predictive_feature_batch: %d succeeded, %d failed out of %d total",
        success, failed, len(payloads),
    )
