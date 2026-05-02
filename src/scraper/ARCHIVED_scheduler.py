"""
ARCHIVED!!!: FinSight Scheduler (DISABLED INTERNAL SCHEDULER)
This file is intentionally kept for historical reference only.
Internal scheduling is disabled for cloud deployments.
Current orchestration model:
    GitHub Actions cron -> POST /run-pipeline -> jobs.weekly_ingestion.run_pipeline()
Important:
    - Do not re-enable looping/daemon scheduling here.
    - Do not add schedule/APScheduler/time.sleep while-loop logic here.
    
==================
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

import logging
import os
import sys
import time
from datetime import datetime

try:
    import schedule
except ImportError:
    raise SystemExit(
        "The 'schedule' package is required.\nRun: pip install schedule"
    )

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from jobs.weekly_ingestion import run_weekly_ingestion

logging.basicConfig(
    filename="scheduler.log",
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(levelname)s: %(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s [SCHEDULER] %(message)s"))
logging.getLogger("").addHandler(console)


def job(latest_only: bool = True):
    """Trigger scrape -> parse -> load. Set latest_only=False for a full backfill."""
    logging.info(f"Scheduler triggered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        summary = run_weekly_ingestion(latest_only=latest_only)
        logging.info("Ingestion run completed: %s", summary.as_dict())
    except Exception as e:
        logging.error(f"Ingestion run failed: {e}")


if __name__ == "__main__":
    logging.info("FinSight Scheduler started.")
    logging.info("Schedule: every Monday at 09:00 AM + immediate startup check.")

    # Run once on startup (latest only - quick check)
    job(latest_only=True)

    # Recurring: every Monday at 09:00 for a latest-quarter check
    schedule.every().monday.at("09:00").do(job, latest_only=True)

    # Optional: full backfill every Sunday night (catches any gaps)
    # schedule.every().sunday.at("02:00").do(job, latest_only=False)

    logging.info("Scheduler is running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)
