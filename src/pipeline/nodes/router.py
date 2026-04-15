"""Node: route_content

Splits the parsed Markdown into two sub-strings:
  - table_markdown   → lines that contain financial tables
  - narrative_markdown → all remaining narrative text

Uses a regex heuristic first; optionally uses a Gemini call for ambiguous
sections to improve accuracy.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# Markdown table row pattern: starts with '|' and has at least two '|'
_TABLE_LINE_RE = re.compile(r"^\s*\|.+\|")

# Section headers that typically precede financial tables
_TABLE_SECTION_HEADERS = re.compile(
    r"(income\s+statement|profit\s+(or\s+)?loss|balance\s+sheet|financial\s+position"
    r"|cash\s+flow|statement\s+of\s+cash|revenue|expenses|liabilities|assets|equity"
    r"|earnings|ebitda|operating\s+results)",
    re.IGNORECASE,
)

_NARRATIVE_SECTION_HEADERS = re.compile(
    r"(management.{0,20}discussion|chairman.{0,20}statement|outlook"
    r"|strategic|operating\s+environment|risks?\s+and|key\s+highlights"
    r"|business\s+review|group\s+performance|segment\s+review)",
    re.IGNORECASE,
)


def _split_by_regex(markdown: str) -> tuple[str, str]:
    """Heuristic split: paragraphs containing tables vs narrative prose."""
    lines = markdown.splitlines(keepends=True)
    table_lines: list[str] = []
    narrative_lines: list[str] = []

    in_table_block = False
    for line in lines:
        if _TABLE_LINE_RE.match(line):
            in_table_block = True
            table_lines.append(line)
        elif in_table_block and line.strip() == "":
            # Keep blank lines inside table blocks
            table_lines.append(line)
            in_table_block = False
        elif _TABLE_SECTION_HEADERS.search(line):
            table_lines.append(line)
        else:
            narrative_lines.append(line)

    return "".join(table_lines), "".join(narrative_lines)


def route_content(state: dict) -> dict:
    """LangGraph node: split markdown_text into table and narrative sub-strings."""
    markdown_text: str = state.get("markdown_text", "")
    errors: list = list(state.get("errors", []))

    if not markdown_text:
        errors.append("route_content: empty markdown_text — skipping split")
        return {
            **state,
            "table_markdown": "",
            "narrative_markdown": "",
            "errors": errors,
        }

    table_md, narrative_md = _split_by_regex(markdown_text)

    # If the regex produced an empty table section, pass the full text to both
    # branches so downstream LLM extraction still has material to work with.
    if not table_md.strip():
        logger.warning("No table content detected — passing full text to quantitative branch")
        table_md = markdown_text

    if not narrative_md.strip():
        logger.warning("No narrative content detected — passing full text to qualitative branch")
        narrative_md = markdown_text

    logger.info(
        "Routing complete: table=%d chars, narrative=%d chars",
        len(table_md),
        len(narrative_md),
    )

    return {
        **state,
        "table_markdown": table_md,
        "narrative_markdown": narrative_md,
        "errors": errors,
    }
