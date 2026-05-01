"""Node: route_content

Passes the full parsed Markdown to both the quantitative (table) and
qualitative (narrative) branches unchanged.  Gemini 2.0 Flash's 1-million
token context window makes heuristic splitting unnecessary and harmful — the
LLM finds the tables it needs from the full document.
"""

import logging

logger = logging.getLogger(__name__)


def route_content(state: dict) -> dict:
    """LangGraph node: pass markdown_text to both table and narrative branches."""
    markdown_text: str = state.get("markdown_text", "")
    new_errors: list = []

    if not markdown_text:
        new_errors.append("route_content: empty markdown_text — skipping split")
        return {
            "table_markdown": "",
            "narrative_markdown": "",
            "errors": new_errors,
        }

    logger.info(
        "route_content: passing full document (%d chars) to both branches",
        len(markdown_text),
    )

    return {
        "table_markdown": markdown_text,
        "narrative_markdown": markdown_text,
        "errors": new_errors,
    }
