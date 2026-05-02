"""
FinSight Scheduler
Runs the full scraper + ETL ingestion job automatically so new quarterly
reports are downloaded, parsed, extracted, and saved to the database.

Default schedule
----------------
  • Every Monday at 09:00 AM (KL time)  → full check (catches new releases)
  • Also runs once immediately on startup for a quick sanity check.

Usage
-----
    # Start the scheduler (runs in the foreground; use tmux or nohup for background)
    python scheduler.py

    # Run in the background with logs
    nohup python scheduler.py > scheduler_output.log 2>&1 &

Dependencies
------------
    pip install schedule

The scheduler calls `jobs.weekly_ingestion.run_weekly_ingestion()` with
latest_only=True by default.  If you want a full backfill run every week,
change `latest_only=True` to `latest_only=False` in the job() function below.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """No-op entrypoint kept to make archival intent explicit."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info(
        "scheduler.py is archived and intentionally disabled. "
        "Use external trigger POST /run-pipeline instead."
    )


if __name__ == "__main__":
    main()
