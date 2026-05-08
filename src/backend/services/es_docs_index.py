"""Elasticsearch docs index: versioned index + alias for RAG and live search.

``ensure_docs_index`` is idempotent and safe to call on every API startup.

v2 additions (live search)
--------------------------
- ``autocomplete_filter``: edge n-gram filter (min_gram=2, max_gram=20)
- ``autocomplete_index`` analyzer: used at index time on title, heading_path, content sub-fields
- ``autocomplete_search`` analyzer: used at query time (standard tokenize + lowercase, no n-gram expansion)
- Sub-fields: ``title.autocomplete``, ``heading_path.autocomplete``, ``content.autocomplete``

Upgrading from v1 → v2
-----------------------
The new analyzers require a new physical index.  Set ``ELASTICSEARCH_DOCS_INDEX_VERSION=v2``
(or leave unset, the default is now v2) and either delete the old index manually or let
``ensure_docs_index(es, reset=True)`` rebuild it.  Re-run the pipeline ingestion to
re-populate the index with the new sub-fields.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_INDEX_VERSION = os.getenv("ELASTICSEARCH_DOCS_INDEX_VERSION", "v2")
INDEX_NAME = f"finsight_docs_{_INDEX_VERSION}"

INDEX_SETTINGS: dict[str, Any] = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "filter": {
            "autocomplete_filter": {
                "type": "edge_ngram",
                "min_gram": 2,
                "max_gram": 20,
            },
        },
        "analyzer": {
            "english_analyzer": {
                "type": "english",
            },
            # Used at *index* time: tokenise → lowercase → edge n-gram expansion
            "autocomplete_index": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "autocomplete_filter"],
            },
            # Used at *query* time: tokenise → lowercase only (no n-gram expansion)
            "autocomplete_search": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase"],
            },
        },
    },
}


def _alias_name() -> str:
    return os.getenv("ELASTICSEARCH_DOCS_INDEX", "finsight_docs_current")


def _embedding_dim() -> int:
    return int(os.getenv("RAG_EMBEDDING_DIM", "3072"))


def _index_mappings() -> dict[str, Any]:
    dim = _embedding_dim()
    return {
        "dynamic": "strict",
        "properties": {
            "content": {
                "type": "text",
                "analyzer": "english_analyzer",
                "fields": {
                    "raw": {"type": "keyword"},
                    # autocomplete sub-field: edge n-gram at index time, plain at query time
                    "autocomplete": {
                        "type": "text",
                        "analyzer": "autocomplete_index",
                        "search_analyzer": "autocomplete_search",
                    },
                },
            },
            "title": {
                "type": "text",
                "analyzer": "english_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "autocomplete": {
                        "type": "text",
                        "analyzer": "autocomplete_index",
                        "search_analyzer": "autocomplete_search",
                    },
                },
            },
            "heading_path": {
                "type": "text",
                "analyzer": "english_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "autocomplete": {
                        "type": "text",
                        "analyzer": "autocomplete_index",
                        "search_analyzer": "autocomplete_search",
                    },
                },
            },
            "tags": {
                "type": "keyword",
            },
            "content_vector": {
                "type": "dense_vector",
                "dims": dim,
                "index": True,
                "similarity": "cosine",
            },
            "doc_type": {"type": "keyword"},
            "domain": {"type": "keyword"},
            "ticker": {"type": "keyword"},
            "visibility": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
            "source_path": {"type": "keyword"},
            "source_uri": {"type": "keyword"},
            "repo": {"type": "keyword"},
            "branch": {"type": "keyword"},
            "content_hash": {"type": "keyword"},
            "last_modified": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
            },
            "ingested_at": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
            },
            "heading_level": {"type": "integer"},
            "chunk_index": {"type": "integer"},
            "section_id": {"type": "keyword"},
            "previous_chunk_id": {"type": "keyword"},
            "next_chunk_id": {"type": "keyword"},
            "source_line_start": {"type": "integer"},
            "source_line_end": {"type": "integer"},
            "embedding_model": {"type": "keyword"},
            "embedding_dim": {"type": "integer"},
            "ingestion_version": {"type": "keyword"},
        },
    }


def ensure_docs_index(es, *, reset: bool = False) -> None:
    """Create the versioned index and alias if missing (same behaviour as the CLI script)."""
    alias = _alias_name()
    dim = _embedding_dim()

    if reset and es.indices.exists(index=INDEX_NAME):
        logger.warning("reset: deleting existing index %s", INDEX_NAME)
        es.indices.delete(index=INDEX_NAME)

    if es.indices.exists(index=INDEX_NAME):
        logger.debug("Index %s already exists — skipping creation", INDEX_NAME)
    else:
        es.indices.create(
            index=INDEX_NAME,
            body={
                "settings": INDEX_SETTINGS,
                "mappings": _index_mappings(),
            },
        )
        logger.info("Created Elasticsearch index %s (embedding_dim=%d)", INDEX_NAME, dim)

    if not es.indices.exists_alias(name=alias):
        es.indices.put_alias(index=INDEX_NAME, name=alias)
        logger.info("Elasticsearch alias %s → %s created", alias, INDEX_NAME)
    else:
        logger.debug("Elasticsearch alias %s already exists", alias)


def check_index(es) -> bool:
    """Return True if versioned index and configured alias exist."""
    alias = _alias_name()
    idx_ok = bool(es.indices.exists(index=INDEX_NAME))
    alias_ok = bool(es.indices.exists_alias(name=alias))
    logger.info("Index %s exists: %s", INDEX_NAME, idx_ok)
    logger.info("Alias %s exists: %s", alias, alias_ok)
    if idx_ok:
        doc_count = es.count(index=INDEX_NAME).get("count", 0)
        logger.info("Document count in %s: %d", INDEX_NAME, doc_count)
    return idx_ok and alias_ok
