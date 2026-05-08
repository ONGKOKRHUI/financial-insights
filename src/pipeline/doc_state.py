"""LangGraph TypedDict state for the FinSight documentation ingestion pipeline."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ParsedSection(TypedDict):
    """One logical section from a Markdown document."""

    source_path: str
    title: str
    heading_path: list[str]  # e.g. ["README", "API", "Authentication"]
    heading_level: int
    content: str             # raw Markdown for this section
    tags: list[str]
    doc_type: str
    domain: str
    ticker: str | None
    source_line_start: int
    source_line_end: int


class DocumentChunk(TypedDict):
    """A single indexable chunk derived from a ParsedSection."""

    chunk_id: str           # stable hash-based ID
    doc_id: str             # per-source-file ID
    source_path: str
    source_uri: str
    repo: str
    branch: str
    content_hash: str
    last_modified: str      # ISO-8601
    ingested_at: str        # ISO-8601
    title: str
    heading_path: list[str]
    heading_level: int
    chunk_index: int
    section_id: str
    previous_chunk_id: str | None
    next_chunk_id: str | None
    source_line_start: int
    source_line_end: int
    tags: list[str]
    doc_type: str
    domain: str
    ticker: str | None
    visibility: str
    content: str            # text sent to the index
    content_vector: list[float] | None
    embedding_model: str
    embedding_dim: int
    ingestion_version: str


class DocPipelineState(TypedDict):
    """Shared state passed between nodes in the documentation ingestion graph."""

    # Input
    doc_roots: list[str]       # directories or individual .md file paths
    dry_run: bool              # if True, skip actual ES writes
    embed: bool                # if False, skip embedding step

    # After discover_files
    file_paths: list[str]

    # After parse_markdown
    sections: list[ParsedSection]

    # After chunk_sections
    chunks: list[DocumentChunk]

    # After embed_chunks — chunks with content_vector filled in
    embedded_chunks: list[DocumentChunk]

    # After upsert_elasticsearch
    indexed_count: int
    skipped_count: int

    # Cross-cutting
    errors: Annotated[list[str], operator.add]
