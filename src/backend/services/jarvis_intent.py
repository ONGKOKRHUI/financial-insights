"""Jarvis intent mapping service.

Converts a text transcript into a structured navigation command.

Supports three engines, toggled via JARVIS_INTENT_ENGINE env var:
  - "keyword"   → regex/keyword matching (default, no external deps, always works)
  - "langgraph" → LangChain + LangGraph pipeline (full NLU, requires GOOGLE_API_KEY)
  - "dify"      → Dify Workflow API (legacy, not recommended)

The keyword engine is always used as fallback if the selected engine fails.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_INTENT_ENGINE = os.getenv("JARVIS_INTENT_ENGINE", "keyword").lower()

# ── Route map ─────────────────────────────────────────────────────────────────
# Maps (regex pattern) → Next.js route
# Patterns are checked in order; first match wins.

_ROUTE_PATTERNS: list[tuple[str, str]] = [
    # Company pages — match ticker or common name
    (r"\b(maybank|malayan banking|mbb)\b",         "/companies/MAYBANK"),
    (r"\b(cimb|commerce)\b",                        "/companies/CIMB"),
    (r"\b(tnb|tenaga|national(?:al)? energy)\b",   "/companies/TNB"),
    (r"\b(petronas|petroliam|petroleum)\b",         "/companies/PETRONAS"),
    (r"\b(maxis)\b",                                "/companies/MAXIS"),
    (r"\b(tm|telekom|telco)\b",                     "/companies/TM"),
    (r"\b(genting|resort|casino)\b",                "/companies/GENTING"),
    (r"\b(sunway|property)\b",                      "/companies/SUNWAY"),
    # Section pages
    (r"\b(all\s+compan|list\s+compan|companies|browse)\b", "/companies"),
    (r"\b(home|main|start|landing)\b",              "/"),
    # API docs / health
    (r"\b(docs?|swagger|api)\b",                    "/"),
]

# Friendly display names for transcript echo
_TICKER_NAMES = {
    "/companies/MAYBANK":  "Maybank",
    "/companies/CIMB":     "CIMB Group",
    "/companies/TNB":      "Tenaga Nasional",
    "/companies/PETRONAS": "Petronas",
    "/companies/MAXIS":    "Maxis",
    "/companies/TM":       "Telekom Malaysia",
    "/companies/GENTING":  "Genting",
    "/companies/SUNWAY":   "Sunway",
    "/companies":          "Companies List",
    "/":                   "Home",
}


# ── Keyword engine (primary) ──────────────────────────────────────────────────

def _map_keyword(transcript: str) -> dict:
    """Match transcript against known patterns and return a navigation command."""
    cleaned = transcript.lower().strip()

    for pattern, route in _ROUTE_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            friendly = _TICKER_NAMES.get(route, route)
            logger.info("Keyword match: %r → %s", pattern, route)
            return {
                "action": "navigate",
                "target": route,
                "label": friendly,
                "engine": "keyword",
            }

    logger.info("No keyword match found for transcript: %r", transcript)
    return {
        "action": "unknown",
        "message": f"Could not understand: \"{transcript}\". Try saying a company name like \"Maybank\" or \"Petronas\".",
        "engine": "keyword",
    }


# ── LangGraph engine ──────────────────────────────────────────────────────────

def _map_langgraph(transcript: str, session_id: str = "anonymous") -> dict:
    """Run the full Jarvis LangGraph pipeline for intent classification.

    Falls back to the keyword engine if GOOGLE_API_KEY is not set or the
    graph raises an unexpected exception.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        logger.warning(
            "JARVIS_INTENT_ENGINE=langgraph but GOOGLE_API_KEY is not set. "
            "Falling back to keyword engine."
        )
        return _map_keyword(transcript)

    try:
        from services.langgraph_intent import run_jarvis_graph  # lazy import

        logger.info("LangGraph intent pipeline: %r", transcript[:80])
        result = run_jarvis_graph(transcript, session_id=session_id)
        # Add backward-compat "label" field used by older frontend code
        if result.get("action") == "navigate" and result.get("target"):
            result.setdefault("label", _TICKER_NAMES.get(result["target"], result["target"]))
        return result
    except Exception as exc:
        exc_str = str(exc)
        if "API_KEY_INVALID" in exc_str or "API key not valid" in exc_str:
            logger.warning(
                "LangGraph intent failed: Google API key invalid. "
                "Set `GOOGLE_API_KEY` to a valid Gemini/Generative Language API key "
                "or switch JARVIS_INTENT_ENGINE=keyword."
            )
        else:
            logger.warning("LangGraph intent error: %s. Falling back to keyword engine.", exc)
        return _map_keyword(transcript)


# ── Dify engine (legacy) ───────────────────────────────────────────────────────

_DIFY_API_URL = os.getenv("JARVIS_DIFY_API_URL", "")
_DIFY_API_KEY = os.getenv("JARVIS_DIFY_API_KEY", "")
_DIFY_TIMEOUT = int(os.getenv("JARVIS_DIFY_TIMEOUT", "15"))


def _map_dify(transcript: str) -> dict:
    """Send transcript to Dify workflow for intent classification.

    Expected Dify output format:
        { "action": "navigate", "target": "/companies/MAYBANK" }
    or:
        { "action": "unknown", "message": "Could not determine intent" }

    Falls back to the keyword engine on any error.
    """
    if not _DIFY_API_URL or not _DIFY_API_KEY:
        logger.warning(
            "JARVIS_INTENT_ENGINE=dify but JARVIS_DIFY_API_URL/JARVIS_DIFY_API_KEY are not set. "
            "Falling back to keyword engine."
        )
        return _map_keyword(transcript)

    headers = {
        "Authorization": f"Bearer {_DIFY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": {"transcript": transcript},
        "response_mode": "blocking",
        "user": "jarvis-voice-assistant",
    }

    try:
        logger.info("Calling Dify intent workflow for transcript: %r", transcript)
        response = requests.post(
            _DIFY_API_URL,
            json=payload,
            headers=headers,
            timeout=_DIFY_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        # Dify blocking response: { "data": { "outputs": {...} } }
        outputs = data.get("data", {}).get("outputs", data)
        action = outputs.get("action", "unknown")
        target = outputs.get("target", "")

        if action == "navigate" and target:
            friendly = _TICKER_NAMES.get(target, target)
            logger.info("Dify intent: navigate → %s", target)
            return {
                "action": "navigate",
                "target": target,
                "label": friendly,
                "engine": "dify",
            }

        # Dify responded but intent unknown — try keyword as graceful fallback
        logger.info("Dify returned unknown intent; falling back to keyword engine.")
        return _map_keyword(transcript)

    except requests.Timeout:
        logger.warning("Dify intent request timed out. Falling back to keyword engine.")
        return _map_keyword(transcript)
    except Exception as exc:
        logger.warning("Dify intent error: %s. Falling back to keyword engine.", exc)
        return _map_keyword(transcript)


# ── Public API ────────────────────────────────────────────────────────────────

def map_intent(transcript: str) -> dict:
    """Map a voice transcript to a navigation command.

    Args:
        transcript: Raw text from the ASR engine.

    Returns:
        Dict with one of:
            { "action": "navigate", "target": "/companies/MAYBANK", "label": "Maybank", "engine": "..." }
            { "action": "unknown",  "message": "...",                                   "engine": "..." }
    """
    if not transcript or not transcript.strip():
        return {
            "action": "unknown",
            "message": "No speech detected. Please try again.",
            "engine": _INTENT_ENGINE,
        }

    if _INTENT_ENGINE == "langgraph":
        return _map_langgraph(transcript)
    elif _INTENT_ENGINE == "dify":
        return _map_dify(transcript)
    else:
        return _map_keyword(transcript)
