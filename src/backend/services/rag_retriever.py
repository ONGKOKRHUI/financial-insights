"""Hybrid Elasticsearch retrieval with Reciprocal Rank Fusion (Phase 5).

Search strategy:
  1. Run a BM25 multi_match query over content, title, heading_path, tags.
  2. Run a KNN approximate nearest-neighbour query over content_vector.
  3. Fuse the two ranked lists using RRF (Reciprocal Rank Fusion).
  4. Apply any caller-supplied metadata filters as pre-retrieval filters.
  5. Return top-k fused results with retrieval diagnostics.

Public API:
    retrieve(question, scope, ticker, filters, top_k) -> RetrievalResult
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_ALIAS = os.getenv("ELASTICSEARCH_DOCS_INDEX", "finsight_docs_current")
_CANDIDATE_POOL = int(os.getenv("RAG_CANDIDATE_POOL", "50"))
_RRF_K = int(os.getenv("RAG_RRF_RANK_CONSTANT", "60"))
_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "models/gemini-embedding-001")


# ── Data classes for retrieval results ───────────────────────────────────────


@dataclass
class RetrievedChunk:
    chunk_id: str
    title: str
    source_path: str
    heading_path: list[str]
    snippet: str          # raw content (without context prefix)
    content: str          # full indexed content (with prefix)
    doc_type: str
    domain: str
    ticker: Optional[str]
    tags: list[str]
    rrf_score: float
    rank: int
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    lexical_hits: int
    vector_hits: int
    fused_hits: int
    embedding_model: str


# ── Metadata filter builder ───────────────────────────────────────────────────


def _build_filter_clauses(
    scope: Optional[str] = None,
    ticker: Optional[str] = None,
    filters: Optional[dict] = None,
) -> list[dict]:
    """Build ES bool filter clauses from caller-supplied constraints."""
    clauses: list[dict] = []

    if scope and scope != "all":
        scope_domain_map = {
            "documentation": ["platform", "api", "pipeline"],
            "company": ["company"],
        }
        domains = scope_domain_map.get(scope)
        if domains:
            clauses.append({"terms": {"domain": domains}})

    if ticker:
        clauses.append({"term": {"ticker": ticker.upper()}})

    if filters:
        if filters.get("doc_type"):
            clauses.append({"terms": {"doc_type": filters["doc_type"]}})
        if filters.get("tags"):
            clauses.append({"terms": {"tags": filters["tags"]}})
        if filters.get("source_path_prefix"):
            clauses.append(
                {"prefix": {"source_path": filters["source_path_prefix"]}}
            )
        if filters.get("updated_after"):
            clauses.append(
                {"range": {"last_modified": {"gte": filters["updated_after"]}}}
            )

    # Always restrict to internally visible docs
    clauses.append({"term": {"visibility": "internal"}})

    return clauses


# ── BM25 lexical search ───────────────────────────────────────────────────────


def _bm25_search(
    es,
    question: str,
    filter_clauses: list[dict],
    pool_size: int,
) -> list[dict]:
    """Run a boosted multi_match BM25 query."""
    query: dict = {
        "bool": {
            "must": [
                {
                    "multi_match": {
                        "query": question,
                        "fields": [
                            "title^3",
                            "heading_path^2",
                            "tags^1.5",
                            "content^1",
                        ],
                        "type": "best_fields",
                        "tie_breaker": 0.3,
                    }
                }
            ],
            "filter": filter_clauses,
        }
    }

    resp = es.search(
        index=_ALIAS,
        query=query,
        size=pool_size,
        _source=[
            "chunk_id", "title", "source_path", "heading_path",
            "content", "doc_type", "domain", "ticker", "tags",
        ],
    )
    return resp.get("hits", {}).get("hits", [])


# ── KNN vector search ─────────────────────────────────────────────────────────


def _knn_search(
    es,
    query_vector: list[float],
    filter_clauses: list[dict],
    pool_size: int,
) -> list[dict]:
    """Run approximate KNN query over content_vector."""
    knn: dict = {
        "field": "content_vector",
        "query_vector": query_vector,
        "k": pool_size,
        "num_candidates": pool_size * 3,
    }
    if filter_clauses:
        knn["filter"] = {"bool": {"filter": filter_clauses}}

    resp = es.search(
        index=_ALIAS,
        knn=knn,
        size=pool_size,
        _source=[
            "chunk_id", "title", "source_path", "heading_path",
            "content", "doc_type", "domain", "ticker", "tags",
        ],
    )
    return resp.get("hits", {}).get("hits", [])


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────


def _rrf_fuse(
    lexical_hits: list[dict],
    vector_hits: list[dict],
    k: int = 60,
    top_n: int = 10,
) -> list[tuple[str, float, dict]]:
    """Combine two ranked lists using RRF.

    Returns a list of (chunk_id, rrf_score, source_doc) sorted descending.
    """
    scores: dict[str, float] = {}
    sources: dict[str, dict] = {}

    for rank, hit in enumerate(lexical_hits, start=1):
        cid = hit["_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in sources:
            sources[cid] = hit["_source"]

    for rank, hit in enumerate(vector_hits, start=1):
        cid = hit["_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in sources:
            sources[cid] = hit["_source"]

    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    return [(cid, scores[cid], sources[cid]) for cid in sorted_ids[:top_n]]


# ── Main retrieval entry point ────────────────────────────────────────────────


def _extract_snippet(content: str, max_chars: int = 400) -> str:
    """Extract a readable snippet from the prefixed chunk content."""
    marker = "Content:\n"
    idx = content.find(marker)
    raw = content[idx + len(marker):] if idx != -1 else content
    return raw[:max_chars].strip()


def retrieve(
    question: str,
    scope: str = "all",
    ticker: Optional[str] = None,
    filters: Optional[dict] = None,
    top_k: int = 6,
) -> RetrievalResult:
    """Perform hybrid BM25 + KNN retrieval with RRF fusion.

    Args:
        question: Natural-language question from the user.
        scope:    "documentation" | "company" | "all"
        ticker:   Optional KLSE ticker to restrict results.
        filters:  Optional dict with keys doc_type, tags, source_path_prefix, updated_after.
        top_k:    Number of chunks to return after fusion.

    Returns:
        RetrievalResult with ranked chunks and retrieval diagnostics.
    """
    from services.es_client import get_es_client
    from services.embeddings import embed_query

    es = get_es_client()
    filter_clauses = _build_filter_clauses(scope=scope, ticker=ticker, filters=filters)

    # Embed the query
    query_vector = embed_query(question)

    # Run both searches
    pool = _CANDIDATE_POOL
    lexical_hits = _bm25_search(es, question, filter_clauses, pool)
    vector_hits = _knn_search(es, query_vector, filter_clauses, pool)

    logger.info(
        "Retrieval: BM25=%d hits, KNN=%d hits for question=%r",
        len(lexical_hits), len(vector_hits), question[:60],
    )

    # Fuse rankings
    fused = _rrf_fuse(lexical_hits, vector_hits, k=_RRF_K, top_n=top_k)

    chunks: list[RetrievedChunk] = []
    for rank, (chunk_id, rrf_score, src) in enumerate(fused, start=1):
        content = src.get("content", "")
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                title=src.get("title", ""),
                source_path=src.get("source_path", ""),
                heading_path=src.get("heading_path", []),
                snippet=_extract_snippet(content),
                content=content,
                doc_type=src.get("doc_type", ""),
                domain=src.get("domain", ""),
                ticker=src.get("ticker"),
                tags=src.get("tags", []),
                rrf_score=rrf_score,
                rank=rank,
                metadata={
                    "doc_type": src.get("doc_type"),
                    "domain": src.get("domain"),
                    "ticker": src.get("ticker"),
                    "tags": src.get("tags", []),
                },
            )
        )

    return RetrievalResult(
        chunks=chunks,
        lexical_hits=len(lexical_hits),
        vector_hits=len(vector_hits),
        fused_hits=len(fused),
        embedding_model=_EMBEDDING_MODEL,
    )
