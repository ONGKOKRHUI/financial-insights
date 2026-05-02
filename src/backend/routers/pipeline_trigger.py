"""External pipeline trigger endpoint.

This router intentionally exposes a stateless HTTP-triggered entrypoint for
weekly ingestion. Scheduling is handled outside the app (for example, GitHub
Actions cron), and this service only runs ingestion when explicitly called.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, status

# Ensure repo `src/` is importable when backend runs from `src/backend`.
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobs.weekly_ingestion import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pipeline"])

_pipeline_lock = threading.Lock()
_pipeline_running = False


@router.post("/run-pipeline", status_code=status.HTTP_200_OK)
def trigger_pipeline(x_api_key: str | None = Header(default=None, alias="x-api-key")) -> dict:
    """Run weekly ingestion via authenticated external trigger."""
    expected_api_key = os.getenv("API_SECRET_KEY")
    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_SECRET_KEY is not configured.",
        )

    if x_api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized.",
        )

    global _pipeline_running
    with _pipeline_lock:
        if _pipeline_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Pipeline is already running.",
            )
        _pipeline_running = True

    try:
        summary = run_pipeline()
        logger.info("External trigger pipeline finished: %s", summary.as_dict())
    finally:
        with _pipeline_lock:
            _pipeline_running = False

    return {"status": "success"}
