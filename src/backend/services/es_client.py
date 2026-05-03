"""Shared Elasticsearch client for the FinSight backend (Phase 5 RAG).

Usage:
    from services.es_client import get_es_client, es_health

The client is lazy-initialised on first access so the backend starts normally
even when Elasticsearch is unavailable (retrieval will raise at call time).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
_ES_TIMEOUT = int(os.getenv("RAG_ES_TIMEOUT", "10"))

_client: Optional["Elasticsearch"] = None  # noqa: F821


def get_es_client():
    """Return a cached Elasticsearch client instance."""
    global _client
    if _client is None:
        try:
            from elasticsearch import Elasticsearch  # type: ignore

            _client = Elasticsearch(
                _ES_URL,
                request_timeout=_ES_TIMEOUT,
                retry_on_timeout=True,
                max_retries=2,
            )
            logger.info("Elasticsearch client initialised — %s", _ES_URL)
        except ImportError as exc:
            raise RuntimeError(
                "elasticsearch package not installed. "
                "Add elasticsearch>=8.13.0 to requirements.txt."
            ) from exc
    return _client


def es_health() -> dict:
    """Return a concise ES cluster health dict for the /health endpoint.

    Returns a dict with ``status`` and ``url``; never raises so the root health
    check stays green even if ES is down.
    """
    try:
        client = get_es_client()
        info = client.cluster.health(timeout="3s")
        return {
            "status": info.get("status", "unknown"),
            "url": _ES_URL,
            "available": True,
        }
    except Exception as exc:
        logger.warning("Elasticsearch health check failed: %s", exc)
        return {"status": "unavailable", "url": _ES_URL, "available": False}
