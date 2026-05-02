"""Airflow DAG: finsight_etl

Local orchestration pipeline for FinSight ETL.

Purpose
-------
- Intended for local Docker/Airflow development and DAG testing.
- Deployment path uses weekly scheduler -> jobs.weekly_ingestion by default.

Task graph:
    check_new_pdfs >> trigger_parse_pipeline >> load_to_postgres

Schedule: @daily (catches any new PDFs downloaded by the Phase 1 scraper)
Retry policy: 3 retries with a 5-minute delay.
"""

import logging
import os
import sys

from datetime import datetime, timedelta

from airflow import DAG
try:
    from airflow.providers.standard.operators.python import PythonOperator  # Airflow 3.x
except ImportError:
    from airflow.operators.python import PythonOperator  # Airflow 2.x fallback

logger = logging.getLogger(__name__)

# ── Path bootstrap ─────────────────────────────────────────────────────────────
# Add src/ to PYTHONPATH so pipeline.* and db.* can be imported inside tasks.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Raw PDF directory — default to scraper's actual output path; override via env
RAW_DIR = os.getenv(
    "FINSIGHT_RAW_DIR",
    os.path.join(_REPO_ROOT, "src", "scraper", "data", "raw"),
)

# Optional cap for quick local validation runs.
# Example: FINSIGHT_MAX_PDFS_PER_RUN=1
MAX_PDFS_PER_RUN = int(os.getenv("FINSIGHT_MAX_PDFS_PER_RUN", "0"))

# ── Default args ───────────────────────────────────────────────────────────────

DEFAULT_ARGS = {
    "owner": "finsight",
    "depends_on_past": False,
    "email_on_failure": False,   # set to True and provide email list for alerts
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

# ── Task callables ─────────────────────────────────────────────────────────────


def check_new_pdfs(**context) -> None:
    """Scan RAW_DIR for PDFs not yet successfully processed.

    Pushes a list of absolute PDF paths via XCom key 'unprocessed_pdfs'.
    """
    from db.loader import get_unprocessed_pdfs

    unprocessed = get_unprocessed_pdfs(RAW_DIR)
    if MAX_PDFS_PER_RUN > 0:
        unprocessed = unprocessed[:MAX_PDFS_PER_RUN]
        logger.info(
            "check_new_pdfs: limiting to %d PDF(s) for this run",
            MAX_PDFS_PER_RUN,
        )
    logger.info("check_new_pdfs: found %d unprocessed PDFs", len(unprocessed))
    context["ti"].xcom_push(key="unprocessed_pdfs", value=unprocessed)


def trigger_parse_pipeline(**context) -> None:
    """Run the ETL pipeline for each unprocessed PDF.

    Pushes validated JSON payloads via XCom key 'validated_payloads'.
    """
    from db.loader import mark_processed
    from pipeline.graph import run_pipeline

    unprocessed: list[str] = context["ti"].xcom_pull(
        task_ids="check_new_pdfs", key="unprocessed_pdfs"
    ) or []

    if not unprocessed:
        logger.info("trigger_parse_pipeline: no new PDFs to process")
        context["ti"].xcom_push(key="validated_payloads", value=[])
        return

    results = []
    for pdf_path in unprocessed:
        logger.info("Processing: %s", pdf_path)
        mark_processed(pdf_path, status="processing")
        try:
            result = run_pipeline(pdf_path)
            if result.get("errors"):
                logger.warning("Pipeline completed with errors for %s: %s", pdf_path, result["errors"])
            results.append(
                {
                    "pdf_path": pdf_path,
                    "payload": result.get("validated_payload", {}),
                    "errors": result.get("errors", []),
                    "metadata": result.get("metadata", {}),
                }
            )
        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", pdf_path, exc)
            mark_processed(pdf_path, status="error", error_msg=str(exc))
            results.append(
                {
                    "pdf_path": pdf_path,
                    "payload": {},
                    "errors": [str(exc)],
                    "metadata": {},
                }
            )

    context["ti"].xcom_push(key="validated_payloads", value=results)
    logger.info("trigger_parse_pipeline: processed %d PDFs", len(results))


def load_to_postgres(**context) -> None:
    """UPSERT validated payloads to PostgreSQL and mark each PDF as processed."""
    from db.loader import mark_processed, upsert_report

    results: list[dict] = context["ti"].xcom_pull(
        task_ids="trigger_parse_pipeline", key="validated_payloads"
    ) or []

    if not results:
        logger.info("load_to_postgres: nothing to load")
        return

    for item in results:
        pdf_path: str = item.get("pdf_path", "")
        payload: dict = item.get("payload", {})
        errors: list = item.get("errors", [])
        metadata: dict = item.get("metadata", {})

        if not payload or not payload.get("ticker"):
            logger.warning("Skipping load for %s — empty or invalid payload", pdf_path)
            mark_processed(
                pdf_path,
                status="error",
                error_msg=f"Empty payload. Pipeline errors: {errors}",
            )
            continue

        try:
            upsert_report(payload)
            mark_processed(
                pdf_path,
                status="success",
                ticker=payload.get("ticker"),
                fiscal_year=payload.get("fiscal_year"),
            )
            logger.info("Loaded %s FY%s from %s", payload["ticker"], payload.get("fiscal_year"), pdf_path)
        except Exception as exc:
            logger.error("DB load failed for %s: %s", pdf_path, exc)
            mark_processed(pdf_path, status="error", error_msg=str(exc))
            raise  # re-raise so Airflow marks the task as failed


# ── DAG definition ─────────────────────────────────────────────────────────────

with DAG(
    dag_id="finsight_etl",
    description="Daily PDF ingestion → parse → load to PostgreSQL",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["finsight", "etl", "pdf", "pipeline"],
    doc_md=__doc__,
) as dag:

    t1 = PythonOperator(
        task_id="check_new_pdfs",
        python_callable=check_new_pdfs,
    )

    t2 = PythonOperator(
        task_id="trigger_parse_pipeline",
        python_callable=trigger_parse_pipeline,
    )

    t3 = PythonOperator(
        task_id="load_to_postgres",
        python_callable=load_to_postgres,
    )

    t1 >> t2 >> t3
