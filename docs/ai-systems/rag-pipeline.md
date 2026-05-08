# RAG Pipeline

!!! success "Current status"
    This pipeline is implemented and wired into the backend via `/rag/ask` and `/rag/health`.

---

## Overview

FinSight uses an Elasticsearch-backed hybrid RAG flow for documentation and company knowledge queries:

1. Ingest Markdown/Obsidian (and API docs TSX) into a chunked, embedded index.
2. Retrieve with BM25 + vector KNN.
3. Fuse rankings with Reciprocal Rank Fusion (RRF).
4. Generate grounded Gemini answers with optional source snippets.

---

## Indexing (Implemented)

### LangGraph ingestion graph

`src/pipeline/doc_graph.py` runs:

`discover_files -> parse_markdown -> chunk_sections -> embed_chunks -> upsert_elasticsearch`

Supported inputs:
- `.md` docs (including frontmatter, headings, tags, wikilinks)
- `frontend/src/app/api-docs/page.tsx` (endpoint/auth/error extraction)

### Chunking strategy

Implemented in `src/pipeline/nodes/doc_chunker.py`:
- Size cap via `RAG_MAX_CHUNK_CHARS` (default `3600`)
- Overlap via `RAG_OVERLAP_CHARS` (default `400`)
- Preserves paragraph boundaries and avoids splitting code/table blocks
- Adds contextual prefix (`Title`, `Section`, `Tags`, `Content`) before embedding
- Generates stable `chunk_id`/`doc_id` and previous/next chunk links

### Embeddings and upsert

- Embeddings use Gemini embedding models (`RAG_EMBEDDING_MODEL`, default `models/gemini-embedding-001`)
- Batch embedding with retries/exponential backoff
- ES bulk upsert by `chunk_id`; unchanged chunks are skipped using `content_hash`
- Index alias defaults to `finsight_docs_current`

---

## Retrieval (Implemented)

Implemented in `src/backend/services/rag_retriever.py`.

### Hybrid retrieval

- BM25 `multi_match` over `title`, `heading_path`, `tags`, `content`
- KNN search over `content_vector`
- Pre-filters for `scope`, `ticker`, and metadata filters (`doc_type`, `tags`, `source_path_prefix`, `updated_after`)
- Visibility guard: only `visibility=internal`

### Rank fusion

Lexical and vector rankings are merged with RRF (`RAG_RRF_RANK_CONSTANT`, default `60`), returning top-k chunks with retrieval diagnostics.

---

## Answer Generation (Implemented)

Implemented in `src/backend/services/rag_answer.py`.

- Model: `RAG_ANSWER_MODEL` (default `gemini-2.5-flash`)
- Grounding rule: answer only from provided context
- Abstention rule: explicit abstain string when context is insufficient
- Confidence output:
  - `high`: at least 3 supporting chunks
  - `medium`: 1-2 chunks
  - `low`: abstained or no support

---

## API Surface

- `POST /rag/ask`
  - Auth: session cookie or `X-API-Key`
  - Returns `answer`, `sources`, retrieval stats, `confidence`, `abstained`
- `GET /rag/health`
  - Returns RAG health, ES connectivity, embedding model, and answer model

---

## Operational Notes

- On backend startup, the app can bootstrap the docs index/alias (`RAG_BOOTSTRAP_ES_INDEX=1` by default).
- If retrieval or answer generation backends are unavailable, `/rag/ask` returns `503`.
- For re-indexing docs, run:

```bash
python -m pipeline.doc_graph --docs ./docs
```
