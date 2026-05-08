"""Node: upsert DocumentChunks into Elasticsearch.

Uses the chunk_id as the document _id so re-ingestion is idempotent.
Skips chunks that already exist with the same content_hash.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
_ALIAS = os.getenv("ELASTICSEARCH_DOCS_INDEX", "finsight_docs_current")
_BATCH_SIZE = int(os.getenv("RAG_INDEX_BATCH_SIZE", "50"))


def _get_existing_hashes(es, chunk_ids: list[str]) -> dict[str, str]:
    """Fetch content_hash for existing chunk_ids via mget."""
    if not chunk_ids:
        return {}
    try:
        resp = es.mget(
            index=_ALIAS,
            body={"ids": chunk_ids},
            _source=["content_hash"],
        )
        return {
            doc["_id"]: doc["_source"]["content_hash"]
            for doc in resp.get("docs", [])
            if doc.get("found") and doc.get("_source")
        }
    except Exception as exc:
        logger.warning("mget for existing hashes failed: %s — will upsert all", exc)
        return {}


def upsert_elasticsearch(state: dict) -> dict:
    """Bulk upsert chunks into ES, skipping unchanged documents.

    Input state keys: embedded_chunks (list[DocumentChunk]), dry_run (bool)
    Output state keys: indexed_count (int), skipped_count (int)
    """
    embedded_chunks: list = state.get("embedded_chunks", [])
    dry_run: bool = state.get("dry_run", False)
    errors: list[str] = []
    indexed_count = 0
    skipped_count = 0

    if not embedded_chunks:
        return {"indexed_count": 0, "skipped_count": 0, "errors": []}

    if dry_run:
        logger.info("DRY RUN: would index %d chunks", len(embedded_chunks))
        return {"indexed_count": 0, "skipped_count": len(embedded_chunks), "errors": []}

    try:
        from elasticsearch import Elasticsearch, helpers  # type: ignore
    except ImportError as exc:
        errors.append(f"doc_indexer: elasticsearch not installed: {exc}")
        return {"indexed_count": 0, "skipped_count": 0, "errors": errors}

    es = Elasticsearch(_ES_URL, request_timeout=30)

    for batch_start in range(0, len(embedded_chunks), _BATCH_SIZE):
        batch = embedded_chunks[batch_start : batch_start + _BATCH_SIZE]
        ids = [c["chunk_id"] for c in batch]

        existing_hashes = _get_existing_hashes(es, ids)

        actions = []
        for chunk in batch:
            cid = chunk["chunk_id"]
            chash = chunk.get("content_hash", "")

            if existing_hashes.get(cid) == chash:
                skipped_count += 1
                continue

            # Strip internal None values from the doc to avoid ES mapping errors
            doc = {k: v for k, v in chunk.items() if v is not None and k != "chunk_id"}

            actions.append(
                {
                    "_op_type": "index",
                    "_index": _ALIAS,
                    "_id": cid,
                    "_source": doc,
                }
            )

        if actions:
            try:
                success, failed = helpers.bulk(
                    es, actions, raise_on_error=False, stats_only=True
                )
                indexed_count += success
                if failed:
                    errors.append(
                        f"doc_indexer: {failed} docs failed in batch starting at {batch_start}"
                    )
                    logger.warning("%d docs failed to index in batch %d", failed, batch_start)
            except Exception as exc:
                errors.append(f"doc_indexer: bulk error at batch {batch_start}: {exc}")
                logger.error("Bulk indexing error: %s", exc)

    logger.info(
        "Indexing complete: %d indexed, %d skipped (unchanged)", indexed_count, skipped_count
    )
    return {"indexed_count": indexed_count, "skipped_count": skipped_count, "errors": errors}
