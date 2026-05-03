"""Node: discover documentation files (.md and api-docs page.tsx) from configured doc roots."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Set RAG_INCLUDE_TSX=0 to opt-out of api-docs page.tsx discovery
_INCLUDE_TSX = os.getenv("RAG_INCLUDE_TSX", "1") not in ("0", "false", "False")


def discover_files(state: dict) -> dict:
    """Recursively find every .md file and api-docs page.tsx under each root.

    When RAG_INCLUDE_TSX=1 (default), also discovers any
    ``*/api-docs/page.tsx`` files found under directory roots so that the
    FinSight API documentation page is ingested alongside the Markdown docs.

    Input state keys: doc_roots (list[str])
    Output state keys: file_paths (list[str])
    """
    roots: list[str] = state.get("doc_roots", [])
    found: list[str] = []
    errors: list[str] = []

    for root in roots:
        p = Path(root)
        if not p.exists():
            errors.append(f"doc_loader: path does not exist — {root}")
            logger.warning("Path does not exist: %s", root)
            continue

        if p.is_file():
            if p.suffix.lower() == ".md":
                found.append(str(p.resolve()))
            elif p.suffix.lower() == ".tsx" and _INCLUDE_TSX:
                found.append(str(p.resolve()))
            else:
                logger.warning("Skipping unsupported file: %s", root)
        else:
            # Directory — recurse for Markdown files
            md_files = sorted(p.rglob("*.md"))
            resolved = [str(f.resolve()) for f in md_files if f.is_file()]
            found.extend(resolved)
            logger.info("Discovered %d .md files under %s", len(resolved), root)

            # Also pick up api-docs page.tsx (the frontend API documentation page)
            if _INCLUDE_TSX:
                tsx_files = sorted(p.rglob("*/api-docs/page.tsx"))
                tsx_resolved = [str(f.resolve()) for f in tsx_files if f.is_file()]
                if tsx_resolved:
                    found.extend(tsx_resolved)
                    logger.info(
                        "Discovered %d api-docs page.tsx file(s) under %s",
                        len(tsx_resolved),
                        root,
                    )

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for path in found:
        if path not in seen:
            seen.add(path)
            unique.append(path)

    logger.info("Total unique documentation files: %d", len(unique))
    return {"file_paths": unique, "errors": errors}
