"""Node: generate dense vector embeddings for each DocumentChunk.

Uses the Google Generative AI embedding API (same key as the rest of the
pipeline). Batches requests to stay within API limits and handles retries
with exponential backoff.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "models/gemini-embedding-001")
_GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
_BATCH_SIZE = int(os.getenv("RAG_EMBED_BATCH_SIZE", "20"))
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0
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
        f"Configured={_EMBEDDING_MODEL!r}, Supported(sample)={supported_preview}"
    )


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the Google Generative AI API.

    Returns a list of float vectors in the same order as the input.
    """
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai not installed. Add it to requirements.txt."
        ) from exc

    genai.configure(api_key=_GOOGLE_API_KEY)
    model_name = _resolve_embedding_model(genai)

    results: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = genai.embed_content(
                    model=model_name,
                    content=batch,
                    task_type="retrieval_document",
                )
                embeddings = response.get("embedding") or response.get("embeddings")
                if embeddings is None:
                    raise ValueError(f"Unexpected embedding response shape: {list(response.keys())}")
                # embed_content returns a single vector for a single string input,
                # or a list of vectors for a list input.
                if isinstance(embeddings[0], float):
                    # Single string was passed — wrap
                    results.append(embeddings)
                else:
                    results.extend(embeddings)
                logger.debug("Embedded batch %d/%d (%d texts)", i // _BATCH_SIZE + 1, -(-len(texts) // _BATCH_SIZE), len(batch))
                break
            except Exception as exc:
                if attempt == _MAX_RETRIES:
                    raise
                wait = _RETRY_DELAY * (2 ** (attempt - 1))
                logger.warning("Embedding attempt %d/%d failed: %s — retrying in %.1fs", attempt, _MAX_RETRIES, exc, wait)
                time.sleep(wait)

    return results


def embed_chunks(state: dict) -> dict:
    """Add content_vector to each chunk.

    Input state keys: chunks (list[DocumentChunk])
    Output state keys: embedded_chunks (list[DocumentChunk])
    """
    chunks: list = state.get("chunks", [])
    errors: list[str] = []

    if not chunks:
        return {"embedded_chunks": [], "errors": []}

    if not state.get("embed", True):
        logger.info("Embedding skipped (embed=False)")
        return {"embedded_chunks": chunks, "errors": []}

    if not _GOOGLE_API_KEY:
        errors.append("embed_chunks: GOOGLE_API_KEY is not set — skipping embeddings")
        logger.error("GOOGLE_API_KEY not set; embedding skipped")
        # Return chunks with None vectors so dry-run still works
        return {"embedded_chunks": chunks, "errors": errors}

    texts = [c["content"] for c in chunks]
    logger.info("Embedding %d chunks with model %s", len(texts), _EMBEDDING_MODEL)

    try:
        vectors = _embed_texts(texts)
    except Exception as exc:
        errors.append(f"embed_chunks: embedding failed: {exc}")
        logger.error("Embedding failed: %s", exc)
        return {"embedded_chunks": chunks, "errors": errors}

    embedded = []
    for chunk, vec in zip(chunks, vectors):
        updated = dict(chunk)
        updated["content_vector"] = vec
        embedded.append(updated)

    logger.info("Embedded %d chunks successfully", len(embedded))
    return {"embedded_chunks": embedded, "errors": errors}
