"""Shared embedding client for the FinSight RAG pipeline (Phase 5).

Wraps the Google Generative AI embedding API with caching, batching, and
retry logic. Used by both the ingestion pipeline and query-time retrieval.
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "models/gemini-embedding-001")
_GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
_MAX_RETRIES = 3
_RETRY_DELAY = 1.5
_RESOLVED_EMBEDDING_MODEL: str | None = None


def _candidate_embedding_models() -> list[str]:
    configured = _EMBEDDING_MODEL.strip()
    raw_candidates = [
        configured,
        "models/gemini-embedding-001",
        "gemini-embedding-001",
        "models/text-embedding-004",
        "models/embedding-001",
        "text-embedding-004",
        "embedding-001",
    ]
    candidates: list[str] = []
    seen: set[str] = set()
    for model in raw_candidates:
        if not model:
            continue
        if model in seen:
            continue
        seen.add(model)
        candidates.append(model)
    return candidates


def _resolve_embedding_model(genai) -> str:
    """Pick the first model that supports embedContent for this API key."""
    global _RESOLVED_EMBEDDING_MODEL
    if _RESOLVED_EMBEDDING_MODEL:
        return _RESOLVED_EMBEDDING_MODEL

    candidates = _candidate_embedding_models()
    configured = _EMBEDDING_MODEL.strip()
    try:
        supported = {
            m.name
            for m in genai.list_models()
            if "embedContent" in getattr(m, "supported_generation_methods", [])
        }
    except Exception as exc:
        logger.warning(
            "Could not list embedding-capable models (%s); using configured fallback %s",
            exc,
            candidates[0],
        )
        _RESOLVED_EMBEDDING_MODEL = candidates[0]
        return _RESOLVED_EMBEDDING_MODEL

    for candidate in candidates:
        if candidate in supported:
            _RESOLVED_EMBEDDING_MODEL = candidate
            logger.info("Resolved embedding model: %s", _RESOLVED_EMBEDDING_MODEL)
            return _RESOLVED_EMBEDDING_MODEL

    supported_preview = sorted(supported)[:5]
    raise RuntimeError(
        "No embedding model available for embedContent. "
        f"Configured={configured!r}, Supported(sample)={supported_preview}"
    )


def embed_query(text: str) -> list[float]:
    """Embed a single query string for retrieval (task_type=retrieval_query).

    Raises:
        RuntimeError: if the google-generativeai package is missing.
        Exception: propagated from the API on failure.
    """
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai not installed. Add it to requirements.txt."
        ) from exc

    if not _GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set — cannot embed query.")

    genai.configure(api_key=_GOOGLE_API_KEY)
    model_name = _resolve_embedding_model(genai)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = genai.embed_content(
                model=model_name,
                content=text,
                task_type="retrieval_query",
            )
            embedding = response.get("embedding")
            if embedding is None:
                raise ValueError(f"Unexpected response keys: {list(response.keys())}")
            return embedding
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                raise
            wait = _RETRY_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "embed_query attempt %d/%d failed: %s — retrying in %.1fs",
                attempt, _MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)

    raise RuntimeError("embed_query exhausted retries without success")
