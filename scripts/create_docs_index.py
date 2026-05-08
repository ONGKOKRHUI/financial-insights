#!/usr/bin/env python3
"""Create or update the FinSight documentation Elasticsearch index.

Creates a versioned index (finsight_docs_v1) and an alias
(finsight_docs_current) pointing to it. Safe to re-run: skips creation if the
index and alias already exist.

The API also runs the same logic on startup unless RAG_BOOTSTRAP_ES_INDEX=0.

Usage:
    PYTHONPATH=src/backend python scripts/create_docs_index.py
    PYTHONPATH=src/backend python scripts/create_docs_index.py --reset      # delete + recreate
    PYTHONPATH=src/backend python scripts/create_docs_index.py --check      # verify index exists
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "src" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.es_docs_index import (  # noqa: E402
    INDEX_NAME,
    check_index,
    ensure_docs_index,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("create_docs_index")

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage FinSight docs ES index")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the index")
    parser.add_argument("--check", action="store_true", help="Verify index exists and exit")
    args = parser.parse_args()

    try:
        from elasticsearch import Elasticsearch  # type: ignore
    except ImportError:
        logger.error("elasticsearch package not installed. Run: pip install elasticsearch>=8.13.0")
        sys.exit(1)

    logger.info("Connecting to Elasticsearch at %s", ES_URL)
    es = Elasticsearch(ES_URL, request_timeout=15)

    try:
        info = es.info()
        logger.info(
            "Connected: ES %s cluster '%s'",
            info["version"]["number"],
            info["cluster_name"],
        )
    except Exception as exc:
        logger.error("Cannot connect to Elasticsearch at %s: %s", ES_URL, exc)
        sys.exit(1)

    if args.check:
        ok = check_index(es)
        sys.exit(0 if ok else 1)

    ensure_docs_index(es, reset=args.reset)
    logger.info("Done. Mapping summary:")
    mapping = es.indices.get_mapping(index=INDEX_NAME)
    print(
        json.dumps(
            list(mapping[INDEX_NAME]["mappings"]["properties"].keys()),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
