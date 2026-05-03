"""FastAPI router for the FinSight RAG endpoint (Phase 5).

Endpoint:
    POST /rag/ask
        Natural-language question answering over Elasticsearch-indexed
        documentation using hybrid BM25 + KNN retrieval and Gemini answers.

Authentication: same session cookie / X-API-Key as /search (requires valid login).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import require_api_key_or_session
from models import User
from schemas.rag import RagAskRequest, RagAskResponse, RagRetrievalInfo, RagSource

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger(__name__)


@router.post(
    "/ask",
    response_model=RagAskResponse,
    summary="Natural-language question answering over indexed documentation",
    description=(
        "Performs hybrid BM25 + dense-vector retrieval (Reciprocal Rank Fusion) over "
        "Elasticsearch-indexed Markdown/Obsidian documentation, then generates a "
        "grounded Gemini answer with source citations.\n\n"
        "Use `scope` to restrict to platform documentation, company profiles, or all content. "
        "Optionally narrow results further with `ticker` or `filters`."
    ),
)
def ask(
    payload: RagAskRequest,
    _current_user: User = Depends(require_api_key_or_session),
) -> RagAskResponse:
    """Handle a documentation question via hybrid RAG."""
    logger.info(
        "RAG ask | user=%s scope=%s ticker=%s question=%r",
        getattr(_current_user, "email", "unknown"),
        payload.scope,
        payload.ticker,
        payload.question[:80],
    )

    # ── Retrieval ─────────────────────────────────────────────────────────────
    try:
        from services.rag_retriever import retrieve

        filters_dict = None
        if payload.filters:
            filters_dict = payload.filters.model_dump(exclude_none=True)
            if "updated_after" in filters_dict and filters_dict["updated_after"]:
                filters_dict["updated_after"] = filters_dict["updated_after"].isoformat()

        result = retrieve(
            question=payload.question,
            scope=payload.scope,
            ticker=payload.ticker,
            filters=filters_dict,
            top_k=payload.top_k,
        )
    except Exception as exc:
        logger.exception("Retrieval failed")
        raise HTTPException(
            status_code=503,
            detail=f"Retrieval service unavailable: {exc}",
        )

    # ── Answer generation ─────────────────────────────────────────────────────
    try:
        from services.rag_answer import generate_answer

        answer_text, abstained, confidence = generate_answer(
            question=payload.question,
            chunks=result.chunks,
            session_id=payload.session_id,
        )
    except Exception as exc:
        logger.exception("Answer generation failed")
        raise HTTPException(
            status_code=503,
            detail=f"Answer generation service unavailable: {exc}",
        )

    # ── Build response ────────────────────────────────────────────────────────
    sources: list[RagSource] = []
    if payload.include_sources:
        for chunk in result.chunks:
            sources.append(
                RagSource(
                    chunk_id=chunk.chunk_id,
                    title=chunk.title,
                    source_path=chunk.source_path,
                    heading_path=chunk.heading_path,
                    snippet=chunk.snippet,
                    score=round(chunk.rrf_score, 6),
                    rank=chunk.rank,
                    metadata=chunk.metadata,
                )
            )

    retrieval_info = RagRetrievalInfo(
        strategy="hybrid_rrf",
        lexical_hits=result.lexical_hits,
        vector_hits=result.vector_hits,
        fused_hits=result.fused_hits,
        embedding_model=result.embedding_model,
    )

    return RagAskResponse(
        answer=answer_text,
        question=payload.question,
        scope=payload.scope,
        sources=sources,
        retrieval=retrieval_info,
        confidence=confidence,
        abstained=abstained,
    )


@router.get(
    "/health",
    summary="Check RAG service and Elasticsearch connectivity",
    tags=["rag"],
)
def rag_health() -> dict:
    """Liveness check for the RAG subsystem."""
    from services.es_client import es_health

    es = es_health()
    return {
        "status": "ok" if es["available"] else "degraded",
        "elasticsearch": es,
        "embedding_model": __import__("os").getenv("RAG_EMBEDDING_MODEL", "models/gemini-embedding-001"),
        "answer_model": __import__("os").getenv("RAG_ANSWER_MODEL", "gemini-2.5-flash"),
    }
