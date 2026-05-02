"""Weekly scrape-to-ETL orchestration for FinSight.

This module is the deployable bridge between the Playwright scrapers and the
LLM extraction/database pipeline:

    scraper latest check -> unprocessed PDF scan -> LlamaParse/Gemini pipeline
    -> PostgreSQL UPSERT -> pipeline_runs status tracking

It can be run directly:

    python -m jobs.weekly_ingestion --latest-only

Use --dry-run to inspect what would be processed without calling the LLM or DB
UPSERT stages.

Deployment note:
    This is the primary orchestration path intended for deployed environments
    (for example Render cron scheduling).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SRC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SRC_DIR.parent
SCRAPER_DIR = SRC_DIR / "scraper"
DEFAULT_RAW_DIR = SCRAPER_DIR / "data" / "raw"

for path in (SRC_DIR, SCRAPER_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@dataclass
class ProcessedPdf:
    pdf_path: str
    status: str
    ticker: str | None = None
    fiscal_year: int | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class IngestionSummary:
    scraped: bool
    raw_dir: str
    discovered: int
    processed: list[ProcessedPdf] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.processed if item.status == "success")

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.processed if item.status == "error")

    def as_dict(self) -> dict[str, Any]:
        return {
            "scraped": self.scraped,
            "raw_dir": self.raw_dir,
            "discovered": self.discovered,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "processed": [item.__dict__ for item in self.processed],
        }


async def _run_scraper(latest_only: bool) -> None:
    from main import main as run_scraper

    await run_scraper(latest_only=latest_only)


def run_pipeline(
    *,
    latest_only: bool = True,
    raw_dir: str | os.PathLike[str] | None = None,
    skip_scrape: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> IngestionSummary:
    """Run the complete scraper -> parser -> database ingestion workflow."""
    started_at = datetime.now(timezone.utc)
    start_perf = time.perf_counter()
    logger.info("Pipeline run started at %s", started_at.isoformat())

    resolved_raw_dir = Path(raw_dir or os.getenv("FINSIGHT_RAW_DIR", DEFAULT_RAW_DIR)).resolve()

    if not skip_scrape:
        logger.info("Running scraper latest_only=%s", latest_only)
        asyncio.run(_run_scraper(latest_only=latest_only))
    else:
        logger.info("Skipping scraper stage")

    from db.loader import get_unprocessed_pdfs, mark_processed, upsert_report
    from pipeline.graph import run_pipeline

    unprocessed = get_unprocessed_pdfs(str(resolved_raw_dir))
    if limit is not None:
        unprocessed = unprocessed[:limit]

    summary = IngestionSummary(
        scraped=not skip_scrape,
        raw_dir=str(resolved_raw_dir),
        discovered=len(unprocessed),
    )

    if dry_run:
        summary.processed = [
            ProcessedPdf(pdf_path=pdf_path, status="dry_run") for pdf_path in unprocessed
        ]
        logger.info("Dry run: %d PDFs would be processed", len(unprocessed))
        return summary

    for pdf_path in unprocessed:
        logger.info("Processing PDF: %s", pdf_path)
        mark_processed(pdf_path, status="processing")

        try:
            result = run_pipeline(pdf_path)
            payload = result.get("validated_payload", {})
            errors = list(result.get("errors", []))

            if not payload or not payload.get("ticker"):
                raise ValueError(f"Pipeline returned an empty payload. Errors: {errors}")

            upsert_report(payload)
            mark_processed(
                pdf_path,
                status="success",
                ticker=payload.get("ticker"),
                fiscal_year=payload.get("fiscal_year"),
            )
            summary.processed.append(
                ProcessedPdf(
                    pdf_path=pdf_path,
                    status="success",
                    ticker=payload.get("ticker"),
                    fiscal_year=payload.get("fiscal_year"),
                    errors=errors,
                )
            )
        except Exception as exc:
            logger.exception("Failed to ingest %s", pdf_path)
            mark_processed(pdf_path, status="error", error_msg=str(exc))
            summary.processed.append(
                ProcessedPdf(pdf_path=pdf_path, status="error", errors=[str(exc)])
            )

    completed_at = datetime.now(timezone.utc)
    duration_seconds = time.perf_counter() - start_perf
    if summary.error_count > 0:
        logger.warning(
            "Pipeline run completed with failures. start=%s end=%s duration=%.2fs success=%d errors=%d",
            started_at.isoformat(),
            completed_at.isoformat(),
            duration_seconds,
            summary.success_count,
            summary.error_count,
        )
    else:
        logger.info(
            "Pipeline run completed successfully. start=%s end=%s duration=%.2fs success=%d errors=%d",
            started_at.isoformat(),
            completed_at.isoformat(),
            duration_seconds,
            summary.success_count,
            summary.error_count,
        )
    return summary


def run_weekly_ingestion(
    *,
    latest_only: bool = True,
    raw_dir: str | os.PathLike[str] | None = None,
    skip_scrape: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> IngestionSummary:
    """Backward-compatible alias for legacy callers."""
    return run_pipeline(
        latest_only=latest_only,
        raw_dir=raw_dir,
        skip_scrape=skip_scrape,
        dry_run=dry_run,
        limit=limit,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FinSight weekly ingestion job")
    parser.add_argument("--latest-only", action="store_true", default=True)
    parser.add_argument("--full-backfill", action="store_true", help="Scrape all missing reports")
    parser.add_argument("--skip-scrape", action="store_true", help="Only process existing raw PDFs")
    parser.add_argument("--dry-run", action="store_true", help="List unprocessed PDFs without loading")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N PDFs")
    parser.add_argument("--raw-dir", default=None, help="Override FINSIGHT_RAW_DIR")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    args = _parse_args()
    summary = run_pipeline(
        latest_only=not args.full_backfill,
        raw_dir=args.raw_dir,
        skip_scrape=args.skip_scrape,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    print(summary.as_dict())


if __name__ == "__main__":
    main()
