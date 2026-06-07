"""Airflow DAG: ml_features_etl

Weekly pipeline that computes and stores ML predictive features for each
configured KLSE ticker into the ``predictive_features`` PostgreSQL table.

The schema defines 21 metric columns; the current five-phase pipeline
populates 19 (metrics 19–20 are reserved for future PDF-based extraction).

Data sources: yfinance, TradingView sector screener, Investing.com earnings,
i3investor KLSE HTML, Malaysia Warrants IV.  No FMP API key required.

Task graph
----------
    discover_feature_targets >> run_feature_pipeline >> load_feature_payloads

Schedule: every Monday at 09:00 MYT (01:00 UTC)
Retry policy: 3 retries with a 5-minute delay (consistent with finsight_etl).

Environment variables
---------------------
    DATABASE_URL              SQLAlchemy URL (default: localhost finsight)
    ML_FEATURE_TICKERS        Comma-separated KLSE tickers (optional override)
    ML_FEATURE_YEAR           Fiscal year to process (optional; defaults to latest completed quarter)
    ML_FEATURE_QUARTER        Fiscal quarter to process (optional; defaults to latest completed quarter)
    ML_FEATURE_LIMIT          Process at most N tickers per run (optional cap; 0 = unlimited)
    INVESTING_SOLVE_CLOUDFLARE  Scrapling CF solver for Investing.com fallback (default: false)
    SCRAPLING_REAL_CHROME     Use system Chrome for Scrapling (optional)
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG

try:
    from airflow.providers.standard.operators.python import PythonOperator  # Airflow 3.x
except ImportError:
    from airflow.operators.python import PythonOperator  # Airflow 2.x fallback

logger = logging.getLogger(__name__)

# ── Path bootstrap ───────────────────────────────────────────────────────────
# Mirror the bootstrap used in finsight_etl_dag.py so that src/* is importable.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
_SCRAPER_DIR = os.path.join(_SRC_DIR, "scraper")
_BACKEND_DIR = os.path.join(_SRC_DIR, "backend")

for _p in (_SRC_DIR, _SCRAPER_DIR, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Default args ─────────────────────────────────────────────────────────────
DEFAULT_ARGS = {
    "owner": "finsight",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

# ── Configuration ─────────────────────────────────────────────────────────────
_DEFAULT_TICKERS = "MAYBANK,CIMB,SUNWAY,GENTING,TELEKOM,MAXIS,TNB"
_ML_TICKERS = os.getenv("ML_FEATURE_TICKERS", _DEFAULT_TICKERS)
_ML_LIMIT = int(os.getenv("ML_FEATURE_LIMIT", "0"))


def _current_completed_quarter() -> tuple[int, str]:
    """Return the most recently completed fiscal (year, quarter) pair.

    Uses the same conservative 45-day lag from quarter-end that the scraper
    already applies.
    """
    today = datetime.utcnow()
    if today.month <= 3:
        return today.year - 1, "Q4"
    elif today.month <= 6:
        return today.year, "Q1"
    elif today.month <= 9:
        return today.year, "Q2"
    else:
        return today.year, "Q3"


# ── Task callables ────────────────────────────────────────────────────────────


def discover_feature_targets(**context) -> None:
    """Build the list of (ticker, fiscal_year, fiscal_quarter) targets.

    Reads ML_FEATURE_TICKERS / ML_FEATURE_YEAR / ML_FEATURE_QUARTER from the
    environment, falling back to sensible defaults.  Pushes a serialisable
    list of dicts via XCom key ``feature_targets``.
    """
    from ml_pipeline_runner import discover_targets

    raw_tickers = [t.strip() for t in _ML_TICKERS.split(",") if t.strip()]
    if _ML_LIMIT > 0:
        raw_tickers = raw_tickers[:_ML_LIMIT]
        logger.info("discover_feature_targets: limited to %d tickers", _ML_LIMIT)

    default_year, default_quarter = _current_completed_quarter()
    fiscal_year = int(os.getenv("ML_FEATURE_YEAR", str(default_year)))
    fiscal_quarter = os.getenv("ML_FEATURE_QUARTER", default_quarter)

    targets = discover_targets(raw_tickers, fiscal_year, fiscal_quarter)
    target_dicts = [
        {"ticker": t.ticker, "fiscal_year": t.fiscal_year, "fiscal_quarter": t.fiscal_quarter}
        for t in targets
    ]

    logger.info(
        "discover_feature_targets: %d targets for FY%s %s",
        len(target_dicts), fiscal_year, fiscal_quarter,
    )
    context["ti"].xcom_push(key="feature_targets", value=target_dicts)


def run_feature_pipeline(**context) -> None:
    """Execute the five-phase ML feature pipeline for each target.

    Reads ``feature_targets`` from XCom, runs the pipeline with
    ``persist=False`` so DB writes are handled by the dedicated load task,
    and pushes serialisable payload dicts via XCom key ``feature_payloads``.
    """
    from ml_features.types import FeatureTarget
    from ml_pipeline_runner import run_pipeline

    target_dicts: list[dict] = context["ti"].xcom_pull(
        task_ids="discover_feature_targets", key="feature_targets"
    ) or []

    if not target_dicts:
        logger.info("run_feature_pipeline: no targets received")
        context["ti"].xcom_push(key="feature_payloads", value=[])
        return

    targets = [
        FeatureTarget(
            ticker=d["ticker"],
            fiscal_year=d["fiscal_year"],
            fiscal_quarter=d["fiscal_quarter"],
        )
        for d in target_dicts
    ]

    payloads = run_pipeline(targets, persist=False)
    logger.info("run_feature_pipeline: produced %d payload(s)", len(payloads))
    context["ti"].xcom_push(key="feature_payloads", value=payloads)


def load_feature_payloads(**context) -> None:
    """UPSERT all feature payloads to PostgreSQL via the batch loader.

    Reads ``feature_payloads`` from XCom and calls
    ``upsert_predictive_feature_batch``.  Individual row failures are logged
    but do not abort the task — the loader records which rows succeeded.
    """
    from db.loader import ensure_predictive_features_table, upsert_predictive_feature_batch

    payloads: list[dict] = context["ti"].xcom_pull(
        task_ids="run_feature_pipeline", key="feature_payloads"
    ) or []

    if not payloads:
        logger.info("load_feature_payloads: nothing to load")
        return

    # Ensure table exists (handles first-run before Alembic is applied)
    ensure_predictive_features_table()

    logger.info("load_feature_payloads: loading %d payload(s)", len(payloads))
    upsert_predictive_feature_batch(payloads)
    logger.info("load_feature_payloads: batch load complete")


# ── DAG definition ────────────────────────────────────────────────────────────

with DAG(
    dag_id="ml_features_etl",
    description="Weekly ML feature ingestion → 5-phase pipeline → predictive_features PostgreSQL table",
    schedule="0 1 * * MON",  # 09:00 MYT = 01:00 UTC every Monday
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["finsight", "ml", "features", "etl", "predictive"],
    doc_md=__doc__,
) as dag:

    t1 = PythonOperator(
        task_id="discover_feature_targets",
        python_callable=discover_feature_targets,
    )

    t2 = PythonOperator(
        task_id="run_feature_pipeline",
        python_callable=run_feature_pipeline,
    )

    t3 = PythonOperator(
        task_id="load_feature_payloads",
        python_callable=load_feature_payloads,
    )

    t1 >> t2 >> t3
