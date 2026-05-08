"""LangGraph documentation ingestion pipeline for FinSight Phase 5.

Separate from graph.py (the financial PDF pipeline). Handles Markdown/.md and
Obsidian-formatted notes: discovery → parsing → chunking → embedding → ES upsert.

CLI usage:
    python -m pipeline.doc_graph --docs ./docs --docs ./readme_jarvis.md
    python -m pipeline.doc_graph --docs ./docs --dry-run
    python -m pipeline.doc_graph --docs ./docs --no-embed
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _build_doc_graph(embed: bool = True):
    """Construct and compile the documentation ingestion StateGraph."""
    from langgraph.graph import END, START, StateGraph  # type: ignore

    from pipeline.doc_state import DocPipelineState
    from pipeline.nodes.doc_loader import discover_files
    from pipeline.nodes.doc_parser import parse_markdown
    from pipeline.nodes.doc_chunker import chunk_sections
    from pipeline.nodes.doc_embedder import embed_chunks
    from pipeline.nodes.doc_indexer import upsert_elasticsearch

    graph = StateGraph(DocPipelineState)

    graph.add_node("discover_files", discover_files)
    graph.add_node("parse_markdown", parse_markdown)
    graph.add_node("chunk_sections", chunk_sections)
    graph.add_node("embed_chunks", embed_chunks)
    graph.add_node("upsert_elasticsearch", upsert_elasticsearch)

    graph.add_edge(START, "discover_files")
    graph.add_edge("discover_files", "parse_markdown")
    graph.add_edge("parse_markdown", "chunk_sections")
    graph.add_edge("chunk_sections", "embed_chunks")
    graph.add_edge("embed_chunks", "upsert_elasticsearch")
    graph.add_edge("upsert_elasticsearch", END)

    return graph.compile()


def run_doc_pipeline(doc_roots: list[str], dry_run: bool = False, embed: bool = True) -> dict:
    """Run the full documentation ingestion pipeline.

    Args:
        doc_roots: List of directories or individual .md file paths.
        dry_run:   If True, skip ES writes (useful for verifying chunks).
        embed:     If False, skip embedding (chunks will have null vectors).

    Returns:
        dict with keys: indexed_count, skipped_count, errors, chunk_count.
    """
    logger.info(
        "Starting documentation ingestion [dry_run=%s, embed=%s] for: %s",
        dry_run,
        embed,
        doc_roots,
    )

    compiled = _build_doc_graph(embed=embed)

    initial_state = {
        "doc_roots": doc_roots,
        "dry_run": dry_run,
        "embed": embed,
        "file_paths": [],
        "sections": [],
        "chunks": [],
        "embedded_chunks": [],
        "indexed_count": 0,
        "skipped_count": 0,
        "errors": [],
    }

    final_state = compiled.invoke(initial_state)

    return {
        "indexed_count": final_state.get("indexed_count", 0),
        "skipped_count": final_state.get("skipped_count", 0),
        "chunk_count": len(final_state.get("embedded_chunks", [])),
        "file_count": len(final_state.get("file_paths", [])),
        "section_count": len(final_state.get("sections", [])),
        "errors": final_state.get("errors", []),
    }


# ── CLI entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="FinSight documentation ingestion pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m pipeline.doc_graph --docs ./docs
  python -m pipeline.doc_graph --docs ./docs --docs ./readme_jarvis.md --dry-run
  python -m pipeline.doc_graph --docs ./docs --no-embed --output chunks.json
""",
    )
    parser.add_argument(
        "--docs",
        action="append",
        dest="doc_roots",
        required=True,
        metavar="PATH",
        help="Directory or .md file to ingest (repeatable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and chunk without writing to Elasticsearch",
    )
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="Skip embedding step (chunks will have null vectors)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional file path to write chunk JSON output (default: stdout summary)",
    )
    args = parser.parse_args()

    result = run_doc_pipeline(
        doc_roots=args.doc_roots,
        dry_run=args.dry_run,
        embed=not args.no_embed,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Output written to {args.output}")
    else:
        print(json.dumps(result, indent=2, default=str))

    if result.get("errors"):
        logger.warning("%d error(s) during ingestion:", len(result["errors"]))
        for err in result["errors"]:
            logger.warning("  %s", err)
        sys.exit(1)
