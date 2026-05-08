"""Live (search-as-you-type) Elasticsearch service for FinSight.

Provides a lightweight BM25-only search over the docs/RAG index using the
autocomplete sub-fields added in finsight_docs_v2.  Intentionally avoids
KNN / embedding so the endpoint stays fast enough for per-keystroke calls.

Public API
----------
    live_search(query: str, top_k: int = 5) -> list[LiveSearchHit]
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_ALIAS = os.getenv("ELASTICSEARCH_DOCS_INDEX", "finsight_docs_current")
_SNIPPET_CHARS = int(os.getenv("LIVE_SEARCH_SNIPPET_CHARS", "160"))

# Minimum query length before hitting Elasticsearch (avoids expensive wildcard-like
# queries on a single character).
MIN_QUERY_LEN = 2


@dataclass
class LiveSearchHit:
    rank: int
    title: str
    snippet: str
    source_path: str
    source_uri: Optional[str]
    score: float
    doc_type: str
    domain: str
    ticker: Optional[str]


def _extract_snippet(content: str, max_chars: int = _SNIPPET_CHARS) -> str:
    """Return a short readable excerpt from prefixed chunk content."""
    marker = "Content:\n"
    idx = content.find(marker)
    raw = content[idx + len(marker) :] if idx != -1 else content
    return raw[:max_chars].strip()


def live_search(query: str, top_k: int = 5) -> list[LiveSearchHit]:
    """Run a fast autocomplete BM25 search against the docs index.

    Args:
        query: Raw user input string (already validated by the router).
        top_k: Maximum number of hits to return (always ≤ 5).

    Returns:
        A ranked list of ``LiveSearchHit`` objects, possibly empty.
    """
    from services.es_client import get_es_client

    es = get_es_client()

    # Boost title autocomplete highest so page-title prefix matches surface first,
    # then heading sub-sections, then raw content.
    query_body = {
        "bool": {
            "must": [
                {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "title.autocomplete^4",
                            "heading_path.autocomplete^2",
                            "content.autocomplete^1",
                        ],
                        "type": "best_fields",
                        "tie_breaker": 0.3,
                    }
                }
            ],
            # Only surface API-reference docs in user-facing search.
            # Platform/architecture/pipeline docs are developer-only.
            "filter": [
                {"term": {"visibility": "internal"}},
                {"terms": {"domain": ["api"]}},
            ],
        }
    }

    try:
        resp = es.search(
            index=_ALIAS,
            query=query_body,
            size=min(top_k, 5),
            _source=[
                "title",
                "content",
                "source_path",
                "source_uri",
                "doc_type",
                "domain",
                "ticker",
            ],
        )
    except Exception as exc:
        logger.warning("live_search ES error for query %r: %s", query, exc)
        raise

    hits = resp.get("hits", {}).get("hits", [])
    results: list[LiveSearchHit] = []
    for rank, hit in enumerate(hits, start=1):
        src = hit.get("_source", {})
        results.append(
            LiveSearchHit(
                rank=rank,
                title=src.get("title", ""),
                snippet=_extract_snippet(src.get("content", "")),
                source_path=src.get("source_path", ""),
                source_uri=src.get("source_uri") or None,
                score=round(hit.get("_score", 0.0), 6),
                doc_type=src.get("doc_type", ""),
                domain=src.get("domain", ""),
                ticker=src.get("ticker") or None,
            )
        )

    logger.info(
        "live_search: query=%r hits=%d", query[:60], len(results)
    )
    return results
