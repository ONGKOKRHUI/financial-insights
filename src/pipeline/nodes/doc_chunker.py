"""Node: split ParsedSections into size-bounded DocumentChunks.

Strategy:
  - If a section fits within MAX_CHUNK_TOKENS, it becomes one chunk.
  - Larger sections are split on blank lines (paragraph boundaries) with
    OVERLAP_TOKENS of text carried forward to preserve context.
  - Code fences and tables are kept intact — never split mid-block.
  - Each chunk gets a stable deterministic chunk_id based on source path,
    heading path, chunk index, and content hash.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pipeline.doc_state import DocumentChunk, ParsedSection

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = int(os.getenv("RAG_MAX_CHUNK_CHARS", "3600"))   # ≈900 tokens
OVERLAP_CHARS = int(os.getenv("RAG_OVERLAP_CHARS", "400"))        # ≈100 tokens
EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "models/gemini-embedding-001")
EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "3072"))
INGESTION_VERSION = "1.0.0"

_REPO = os.getenv("RAG_REPO", "finsight")
_BRANCH = os.getenv("RAG_BRANCH", "main")
_VISIBILITY = os.getenv("RAG_VISIBILITY", "internal")
# When set, prepend this base URL to the relative source path to build a
# clickable source_uri (e.g. "https://github.com/org/repo/blob/main").
# Leave unset for local-only ingestion so source_uri is stored as None.
_DOCS_BASE_URI = os.getenv("RAG_DOCS_BASE_URI", "").rstrip("/")

_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_TABLE_ROW_RE = re.compile(r"^\|.*\|$", re.MULTILINE)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _make_chunk_id(source_path: str, heading_path: list[str], chunk_index: int, content: str) -> str:
    raw = f"{source_path}|{'|'.join(heading_path)}|{chunk_index}|{_content_hash(content)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _make_doc_id(source_path: str) -> str:
    return hashlib.sha256(source_path.encode()).hexdigest()[:16]


def _make_source_uri(source_path: str) -> Optional[str]:
    """Build a navigable source_uri, or None for local-only ingestion."""
    if not _DOCS_BASE_URI:
        return None
    # Strip any leading path components up to and including the repo root so
    # we get a clean relative path like "docs/architecture/rag-architecture.md".
    p = Path(source_path)
    try:
        # Try to find "docs/" as an anchor — works for the standard project layout
        parts = p.parts
        for i, part in enumerate(parts):
            if part == "docs":
                rel = "/".join(parts[i:])
                return f"{_DOCS_BASE_URI}/{rel}"
    except Exception:
        pass
    return f"{_DOCS_BASE_URI}/{p.name}"


def _prefix_context(section: ParsedSection, content: str) -> str:
    """Prefix chunk with lightweight context for better embedding."""
    crumb = " > ".join(section["heading_path"])
    tags = ", ".join(section["tags"]) if section["tags"] else ""
    parts = [
        f"Title: {section['title']}",
        f"Section: {crumb}",
    ]
    if tags:
        parts.append(f"Tags: {tags}")
    parts.append(f"Content:\n{content}")
    return "\n".join(parts)


def _split_preserving_blocks(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Split text into chunks while keeping code fences and tables intact."""
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)

        if para_len > max_chars:
            # Oversized single paragraph (e.g. a giant table): keep as-is
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                # Carry overlap
                overlap_text = " ".join(current_parts)[-overlap_chars:]
                current_parts = [overlap_text] if overlap_text else []
                current_len = len(overlap_text)
            chunks.append(para)
            current_parts = []
            current_len = 0
        elif current_len + para_len + 2 > max_chars and current_parts:
            # Would overflow — flush current chunk
            chunks.append("\n\n".join(current_parts))
            # Carry overlap into next chunk
            overlap_text = " ".join(current_parts)[-overlap_chars:]
            current_parts = [overlap_text, para] if overlap_text else [para]
            current_len = len(overlap_text) + para_len + 2
        else:
            current_parts.append(para)
            current_len += para_len + 2

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return [c.strip() for c in chunks if c.strip()]


def _chunk_section(section: ParsedSection) -> list[DocumentChunk]:
    content = section["content"]
    source_path = section["source_path"]
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        mtime = Path(source_path).stat().st_mtime
        last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except Exception:
        last_modified = now_iso

    if len(content) <= MAX_CHUNK_CHARS:
        raw_chunks = [content]
    else:
        raw_chunks = _split_preserving_blocks(content, MAX_CHUNK_CHARS, OVERLAP_CHARS)

    doc_id = _make_doc_id(source_path)
    section_id = _make_chunk_id(source_path, section["heading_path"], 0, content)
    chunks: list[DocumentChunk] = []

    for idx, raw in enumerate(raw_chunks):
        prefixed = _prefix_context(section, raw)
        chunk_id = _make_chunk_id(source_path, section["heading_path"], idx, raw)

        chunk: DocumentChunk = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "source_path": source_path,
            "source_uri": _make_source_uri(source_path),
            "repo": _REPO,
            "branch": _BRANCH,
            "content_hash": _content_hash(raw),
            "last_modified": last_modified,
            "ingested_at": now_iso,
            "title": section["title"],
            "heading_path": section["heading_path"],
            "heading_level": section["heading_level"],
            "chunk_index": idx,
            "section_id": section_id,
            "previous_chunk_id": None,
            "next_chunk_id": None,
            "source_line_start": section["source_line_start"],
            "source_line_end": section["source_line_end"],
            "tags": section["tags"],
            "doc_type": section["doc_type"],
            "domain": section["domain"],
            "ticker": section["ticker"],
            "visibility": _VISIBILITY,
            "content": prefixed,
            "content_vector": None,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "ingestion_version": INGESTION_VERSION,
        }
        chunks.append(chunk)

    # Wire previous/next pointers
    for i, chunk in enumerate(chunks):
        if i > 0:
            chunk["previous_chunk_id"] = chunks[i - 1]["chunk_id"]
        if i < len(chunks) - 1:
            chunk["next_chunk_id"] = chunks[i + 1]["chunk_id"]

    return chunks


def chunk_sections(state: dict) -> dict:
    """Convert sections into size-bounded chunks with stable IDs.

    Input state keys: sections (list[ParsedSection])
    Output state keys: chunks (list[DocumentChunk])
    """
    sections: list[ParsedSection] = state.get("sections", [])
    all_chunks: list[DocumentChunk] = []
    errors: list[str] = []

    for section in sections:
        try:
            all_chunks.extend(_chunk_section(section))
        except Exception as exc:
            msg = f"doc_chunker: error chunking section '{section.get('title')}' in {section.get('source_path')}: {exc}"
            errors.append(msg)
            logger.error(msg)

    logger.info("Produced %d chunks from %d sections", len(all_chunks), len(sections))
    return {"chunks": all_chunks, "errors": errors}
