"""Pydantic v2 request/response schemas for the FinSight RAG endpoint (Phase 5)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class RagFilters(BaseModel):
    """Optional pre-retrieval metadata filters."""

    doc_type: Optional[list[str]] = Field(
        None,
        description="Restrict to specific doc types e.g. ['api_doc', 'runbook']",
    )
    tags: Optional[list[str]] = Field(
        None,
        description="Restrict to chunks with any of these Obsidian/frontmatter tags",
    )
    source_path_prefix: Optional[str] = Field(
        None,
        description="Restrict to chunks whose source_path starts with this prefix",
    )
    updated_after: Optional[datetime] = Field(
        None,
        description="Restrict to chunks last modified after this timestamp",
    )


class RagAskRequest(BaseModel):
    """Request body for POST /rag/ask."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural-language question to answer from indexed documentation",
    )
    scope: Literal["documentation", "company", "all"] = Field(
        "all",
        description=(
            "'documentation' — platform/API/pipeline docs only; "
            "'company' — company profile docs only; "
            "'all' — search all indexed content"
        ),
    )
    ticker: Optional[str] = Field(
        None,
        max_length=20,
        description="Restrict retrieval to documents about a specific KLSE ticker",
    )
    filters: Optional[RagFilters] = Field(
        None,
        description="Optional metadata pre-filters applied before retrieval",
    )
    top_k: int = Field(
        default=6,
        ge=1,
        le=12,
        description="Maximum number of source chunks to retrieve and include",
    )
    include_sources: bool = Field(
        True,
        description="Whether to include source snippets in the response",
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional session identifier (reserved for future conversational memory)",
    )


class RagSource(BaseModel):
    """A single retrieved source chunk included in the response."""

    chunk_id: str
    title: str
    source_path: str
    heading_path: list[str]
    snippet: str = Field(description="Short excerpt from the chunk content")
    score: Optional[float] = Field(None, description="RRF fusion score")
    rank: int = Field(description="1-based rank in the fused result list")
    metadata: dict = Field(default_factory=dict)


class RagRetrievalInfo(BaseModel):
    """Retrieval diagnostics included in every response."""

    strategy: Literal["hybrid_rrf"] = "hybrid_rrf"
    lexical_hits: int = Field(description="Number of BM25 candidate hits")
    vector_hits: int = Field(description="Number of KNN vector candidate hits")
    fused_hits: int = Field(description="Number of chunks after RRF fusion")
    embedding_model: str = Field(description="Model used to embed the query")


class RagAskResponse(BaseModel):
    """Response body for POST /rag/ask."""

    answer: str = Field(description="Grounded answer generated from retrieved sources")
    question: str = Field(description="Original question as received")
    scope: str
    sources: list[RagSource] = Field(
        description="Retrieved source chunks (empty when include_sources=False)"
    )
    retrieval: RagRetrievalInfo
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "high — ≥3 sources found; "
            "medium — 1-2 sources found; "
            "low — no reliable sources or abstained"
        )
    )
    abstained: bool = Field(
        False,
        description="True when the LLM determined the context was insufficient to answer",
    )
