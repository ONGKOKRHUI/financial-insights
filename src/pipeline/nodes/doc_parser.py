"""Node: parse Markdown/Obsidian files into structured sections.

Handles:
  - YAML / TOML frontmatter (via PyYAML)
  - ATX headings (#, ##, ...) to build a breadcrumb path
  - Obsidian [[Wiki Links]] and aliases → plain text
  - Obsidian tags (#tag, frontmatter tags:)
  - Code fences, callouts, tables kept as-is within section content
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_OBSIDIAN_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_/-]*)")
_CALLOUT_RE = re.compile(r"^>\s*\[!(\w+)\]", re.MULTILINE)

_DEFAULT_DOC_TYPE = "project_doc"
_DEFAULT_DOMAIN = "platform"
_DEFAULT_VISIBILITY = "internal"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and return (meta, body_without_frontmatter)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        import yaml  # type: ignore

        meta = yaml.safe_load(match.group(1)) or {}
    except Exception as exc:
        logger.warning("YAML frontmatter parse error: %s", exc)
        meta = {}
    body = text[match.end():]
    return meta, body


def _normalise_wikilinks(text: str) -> str:
    """Replace [[Link|Alias]] with Alias and [[Link]] with Link."""
    return _WIKI_LINK_RE.sub(lambda m: m.group(2) or m.group(1), text)


def _extract_inline_tags(text: str) -> list[str]:
    """Extract Obsidian #tags from body text."""
    return list(dict.fromkeys(_OBSIDIAN_TAG_RE.findall(text)))


def _infer_doc_type(path: str, meta: dict) -> str:
    p = Path(path)
    if meta.get("doc_type"):
        return str(meta["doc_type"])
    parts = {part.lower() for part in p.parts}
    if "api" in parts or "api-reference" in parts:
        return "api_doc"
    if "runbook" in parts or "runbooks" in parts:
        return "runbook"
    if "architecture" in parts or "arch" in parts:
        return "architecture_note"
    if "companies" in parts or "company" in parts:
        return "company_profile"
    return _DEFAULT_DOC_TYPE


def _infer_domain(path: str, meta: dict) -> str:
    if meta.get("domain"):
        return str(meta["domain"])
    p = Path(path)
    parts = {part.lower() for part in p.parts}
    if "pipeline" in parts:
        return "pipeline"
    if "api" in parts or "api-reference" in parts:
        return "api"
    if "companies" in parts or "company" in parts:
        return "company"
    return _DEFAULT_DOMAIN


def _infer_ticker(path: str, meta: dict) -> Optional[str]:
    if meta.get("ticker"):
        return str(meta["ticker"]).upper()
    # Cheap heuristic: check if a known ticker appears in the path
    known = {"MAYBANK", "CIMB", "TNB", "PETRONAS", "MAXIS", "TM", "GENTING", "SUNWAY"}
    upper_path = path.upper()
    for t in known:
        if t in upper_path:
            return t
    return None


def _split_by_headings(body: str) -> list[tuple[int, str, str, int, int]]:
    """Split body into (level, heading_text, section_body, start_line, end_line).

    The implicit top-level section before the first heading gets level 0 and
    heading_text = "".
    """
    lines = body.splitlines(keepends=True)
    sections: list[tuple[int, str, str, int, int]] = []
    current_level = 0
    current_heading = ""
    current_lines: list[str] = []
    current_start = 0

    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line.rstrip("\n"))
        if m:
            # Flush current section
            section_body = "".join(current_lines).strip()
            if section_body or current_heading:
                sections.append(
                    (current_level, current_heading, section_body, current_start, i - 1)
                )
            current_level = len(m.group(1))
            current_heading = m.group(2).strip()
            current_lines = []
            current_start = i
        else:
            current_lines.append(line)

    # Flush last section
    section_body = "".join(current_lines).strip()
    if section_body or current_heading:
        sections.append(
            (current_level, current_heading, section_body, current_start, len(lines) - 1)
        )

    return sections


def _parse_tsx_apidocs(path: str, text: str) -> list[dict]:
    """Extract documentation sections from ``frontend/src/app/api-docs/page.tsx``.

    Produces one ``ParsedSection`` per API endpoint (from the ENDPOINTS constant)
    plus sections for Authentication and HTTP Error Codes.  These are given
    ``domain="api"`` so they are matched by ``scope="documentation"`` in the
    retriever's filter map.
    """
    file_title = "FinSight API Documentation"
    tags = ["api", "finsight", "documentation"]
    sections: list[dict] = []

    # ── Authentication section ────────────────────────────────────────────────
    sections.append(
        {
            "source_path": path,
            "title": "Authentication",
            "heading_path": [file_title, "Authentication"],
            "heading_level": 1,
            "content": (
                "Phase 3 — Open API. No authentication is required. "
                "All endpoints are publicly accessible.\n\n"
                "API key gating (per-user rate limits, paid-tier access) is planned for Phase 4. "
                "Keys will be passed via an X-API-Key header. "
                "No changes to endpoint paths or response shapes are planned."
            ),
            "tags": tags + ["authentication"],
            "doc_type": "api_doc",
            "domain": "api",
            "ticker": None,
            "source_line_start": 0,
            "source_line_end": 0,
        }
    )

    # ── ENDPOINTS array ───────────────────────────────────────────────────────
    # Each entry follows this pattern (description may wrap to the next line):
    #   id: "...",
    #   method: "GET|POST",
    #   path: "/...",
    #   summary: "...",
    #   description:\n?      "..."
    ep_re = re.compile(
        r'id:\s*"([^"]+)",\s*\n\s*method:\s*"(GET|POST)",\s*\n\s*path:\s*"([^"]+)",\s*\n'
        r'\s*summary:\s*"([^"]+)",\s*\n\s*description:\s*\n?\s*"((?:[^"\\]|\\.)*)"',
        re.DOTALL,
    )
    param_re = re.compile(
        r'name:\s*"([^"]+)",\s*type:\s*"([^"]+)",\s*required:\s*(true|false),\s*'
        r'description:\s*"([^"]+)"'
    )

    for m in ep_re.finditer(text):
        _id, method, ep_path, summary, description = m.groups()
        content_lines = [
            f"{method} {ep_path}",
            f"{summary}",
            "",
            description.strip(),
        ]

        # Pull params from the window immediately following this match
        window = text[m.end(): m.end() + 800]
        for pm in param_re.finditer(window):
            pname, ptype, preq, pdesc = pm.groups()
            req_label = "required" if preq == "true" else "optional"
            content_lines.append(f"Parameter: {pname} ({ptype}, {req_label}) — {pdesc}")

        sections.append(
            {
                "source_path": path,
                "title": f"{method} {ep_path}",
                "heading_path": [file_title, "Endpoints", f"{method} {ep_path}"],
                "heading_level": 2,
                "content": "\n".join(content_lines),
                "tags": tags + ["endpoint"],
                "doc_type": "api_doc",
                "domain": "api",
                "ticker": None,
                "source_line_start": 0,
                "source_line_end": 0,
            }
        )

    # ── ERRORS array ─────────────────────────────────────────────────────────
    error_re = re.compile(
        r'status:\s*"(\d+)",\s*name:\s*"([^"]+)",\s*description:\s*"([^"]+)"'
    )
    error_lines = ["HTTP status codes returned by the FinSight API:"]
    for em in error_re.finditer(text):
        status, name, desc = em.groups()
        error_lines.append(f"- {status} {name}: {desc}")

    if len(error_lines) > 1:
        sections.append(
            {
                "source_path": path,
                "title": "Error Reference",
                "heading_path": [file_title, "Error Reference"],
                "heading_level": 1,
                "content": "\n".join(error_lines),
                "tags": tags + ["errors"],
                "doc_type": "api_doc",
                "domain": "api",
                "ticker": None,
                "source_line_start": 0,
                "source_line_end": 0,
            }
        )

    logger.info("Extracted %d sections from TSX api-docs: %s", len(sections), path)
    return sections


def parse_markdown(state: dict) -> dict:
    """Parse every discovered documentation file into structured sections.

    Handles:
    - ``.md`` files: full Markdown + Obsidian frontmatter / wikilinks parsing.
    - ``.tsx`` files matching ``*/api-docs/page.tsx``: delegates to
      ``_parse_tsx_apidocs`` which extracts endpoint and auth documentation
      from the FinSight API reference page.

    Input state keys: file_paths (list[str])
    Output state keys: sections (list[ParsedSection])
    """
    file_paths: list[str] = state.get("file_paths", [])
    sections = []
    errors: list[str] = []

    for path in file_paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            errors.append(f"doc_parser: cannot read {path}: {exc}")
            logger.warning("Cannot read %s: %s", path, exc)
            continue

        # Dispatch TSX api-docs page to its own extractor
        if path.endswith(".tsx"):
            tsx_sections = _parse_tsx_apidocs(path, text)
            sections.extend(tsx_sections)
            continue

        meta, body = _parse_frontmatter(text)
        body = _normalise_wikilinks(body)

        fm_tags: list[str] = []
        if isinstance(meta.get("tags"), list):
            fm_tags = [str(t) for t in meta["tags"]]
        elif isinstance(meta.get("tags"), str):
            fm_tags = [meta["tags"]]

        inline_tags = _extract_inline_tags(body)
        all_tags = list(dict.fromkeys(fm_tags + inline_tags))

        doc_type = _infer_doc_type(path, meta)
        domain = _infer_domain(path, meta)
        ticker = _infer_ticker(path, meta)

        # Title: prefer frontmatter title, else filename stem
        file_title = meta.get("title") or Path(path).stem.replace("-", " ").replace("_", " ")

        heading_stack: list[tuple[int, str]] = []

        raw_sections = _split_by_headings(body)
        for level, heading_text, section_body, start_line, end_line in raw_sections:
            # Maintain heading breadcrumb stack
            if heading_text:
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading_text))
                crumb_path = [file_title] + [h for _, h in heading_stack]
            else:
                crumb_path = [file_title]

            if not section_body:
                continue  # skip empty heading-only sections

            sections.append(
                {
                    "source_path": path,
                    "title": heading_text or str(file_title),
                    "heading_path": crumb_path,
                    "heading_level": level,
                    "content": section_body,
                    "tags": all_tags,
                    "doc_type": doc_type,
                    "domain": domain,
                    "ticker": ticker,
                    "source_line_start": start_line,
                    "source_line_end": end_line,
                }
            )

    logger.info("Parsed %d sections from %d files", len(sections), len(file_paths))
    return {"sections": sections, "errors": errors}
