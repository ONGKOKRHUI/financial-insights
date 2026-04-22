"""Node: extract_qualitative

Uses Google Gemini to summarise narrative sections of annual reports:
  - Management Discussion & Analysis (MD&A)
  - Strategic outlook and key events

Splits long documents with RecursiveCharacterTextSplitter before
summarising to avoid hitting the model's context window.
Each LLM call is wrapped with a Langfuse callback.
"""

import json
import logging
import os
import re

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)


class _QualitativeExtraction(BaseModel):
    future_outlook: Optional[str] = Field(
        None,
        description=(
            "2-3 sentences summarising management's forward-looking statements, "
            "guidance, and strategic priorities for the next 12-24 months."
        ),
    )
    key_strategic_events: Optional[str] = Field(
        None,
        description=(
            "JSON array of strings — each string is one significant event, "
            "acquisition, divestment, restructuring, or regulatory change "
            "mentioned in this report period. Example: "
            '["Acquired XYZ Bank for MYR 2.1 bln", "Launched digital wallet product"]'
        ),
    )


def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        temperature=0.2,
    )


def _build_langfuse_callback():
    try:
        try:
            from langfuse.langchain import CallbackHandler  # langfuse >= 2.x
        except ImportError:
            from langfuse.callback import CallbackHandler  # langfuse < 2.x

        # Reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST from env
        return CallbackHandler()
    except Exception as exc:
        logger.warning("Langfuse callback unavailable: %s", exc)
        return None


_QUALITATIVE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior equity research analyst specialising in Malaysian public companies (Bursa Malaysia). "
            "Your task is to extract two specific qualitative fields from the annual report excerpt below.\n\n"
            "FIELD DEFINITIONS:\n"
            "  1. future_outlook — Write 2-3 sentences summarising management's forward-looking statements. "
            "Look for sections titled 'Outlook', 'Prospects', 'Strategy', 'Guidance', 'Going Forward', "
            "'Management Discussion', or 'Chairman's Statement'. Capture specific targets, projections, "
            "or strategic priorities for the next 12-24 months.\n"
            "  2. key_strategic_events — Return a JSON array of strings. Each string is ONE significant "
            "event from this report period: acquisitions, divestments, new product launches, regulatory "
            "changes, restructuring, major contracts, or JVs. "
            'Example: ["Acquired XYZ Bank for MYR 2.1 bln", "Launched digital wallet in Q2 2024"]\n\n'
            "RULES:\n"
            "  • Use ONLY information present in the excerpt — do not invent or infer details\n"
            "  • If the excerpt contains no forward-looking language, return null for future_outlook\n"
            "  • If no significant events are mentioned, return an empty JSON array [] for key_strategic_events\n"
            "  • Return key_strategic_events as a JSON-formatted string (not a Python list)",
        ),
        (
            "human",
            "Company: {ticker}\nFiscal Year: {fiscal_year}\nReport Period: {report_period}\n\n"
            "--- Report Excerpt ---\n{content}\n--- End of Excerpt ---\n\n"
            "Extract future_outlook and key_strategic_events from the excerpt above.",
        ),
    ]
)

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=6000,
    chunk_overlap=400,
    separators=["\n## ", "\n### ", "\n\n", "\n", " "],
)

# Section-header patterns for narrative sections, ordered by priority.
_NARRATIVE_SECTION_PATTERNS = [
    r"(management.{0,25}discussion|MD&A|MD\s+&\s+A)",
    r"(chairman.{0,20}(?:statement|message|letter)|group\s+(?:chief\s+executives?|ceo).{0,20}(?:statement|message))",
    r"(outlook|prospects?|looking\s+ahead|going\s+forward|future\s+strategy)",
    r"(operating\s+review|group\s+(?:performance|overview)|business\s+review)",
    r"(key\s+highlights?|financial\s+highlights?|corporate\s+highlights?)",
]

_NARRATIVE_WINDOW_CHARS = 14_000


def _find_narrative_window(content: str) -> str:
    """Find the most relevant narrative section(s) and return a combined window.

    Searches for up to 3 distinct section-header matches across the document
    and stitches their windows together, capped at ~18K chars total so we stay
    well within the LLM's context budget.
    """
    found_windows: list[str] = []
    covered: set[tuple[int, int]] = set()  # (start, end) ranges already captured

    for pattern in _NARRATIVE_SECTION_PATTERNS:
        if len(found_windows) >= 3:
            break
        m = re.search(pattern, content, re.IGNORECASE)
        if not m:
            continue
        start = max(0, m.start() - 100)
        end = min(len(content), start + _NARRATIVE_WINDOW_CHARS)
        # Skip if this window heavily overlaps one we already have
        overlap = any(abs(start - s) < 2000 for s, _ in covered)
        if not overlap:
            found_windows.append(content[start:end])
            covered.add((start, end))
            logger.debug(
                "[Qualitative] Narrative section found at char %d (pattern=%r). Window [%d:%d].",
                m.start(), pattern, start, end,
            )

    if found_windows:
        combined = "\n\n[...section break...]\n\n".join(found_windows)
        return combined[:20000]

    # Fallback: first chunk of the document
    logger.warning(
        "[Qualitative] No narrative section headers found in %d-char document. "
        "Falling back to first %d chars.",
        len(content), _NARRATIVE_WINDOW_CHARS,
    )
    return content[:_NARRATIVE_WINDOW_CHARS]


def extract_qualitative(state: dict) -> dict:
    """LangGraph node: extract narrative summaries from the qualitative section."""
    narrative_markdown: str = state.get("narrative_markdown", "")
    metadata: dict = state.get("metadata", {})
    errors: list = list(state.get("errors", []))

    if not narrative_markdown.strip():
        errors.append("extract_qualitative: no narrative content to process")
        return {"qualitative_data": {}, "errors": errors}

    llm = _build_llm()
    cb = _build_langfuse_callback()
    callbacks = [cb] if cb else []

    structured_llm = llm.with_structured_output(_QualitativeExtraction)
    chain = _QUALITATIVE_PROMPT | structured_llm

    # Smart narrative targeting: find Outlook / MD&A / Chairman sections
    primary_chunk = _find_narrative_window(narrative_markdown)

    try:
        result = chain.invoke(
            {
                "ticker": metadata.get("ticker", "UNKNOWN"),
                "fiscal_year": metadata.get("fiscal_year", "UNKNOWN"),
                "report_period": metadata.get("report_period", "UNKNOWN"),
                "content": primary_chunk,
            },
            config={"callbacks": callbacks},
        )
        qualitative_data: dict = result.model_dump() if result else {}

        none_fields = [k for k, v in qualitative_data.items() if v is None]
        populated_fields = [k for k, v in qualitative_data.items() if v is not None]
        logger.debug(
            "[QualitativeExtraction] populated: %s | null: %s",
            populated_fields, none_fields,
        )
    except Exception as exc:
        logger.error("Qualitative extraction failed: %s", exc)
        errors.append(f"Qualitative extraction failed: {exc}")
        qualitative_data = {}

    # Ensure key_strategic_events is a valid JSON string if it's a list
    if isinstance(qualitative_data.get("key_strategic_events"), list):
        qualitative_data["key_strategic_events"] = json.dumps(
            qualitative_data["key_strategic_events"]
        )

    logger.info("Qualitative data extracted: %s", qualitative_data)

    return {
        "qualitative_data": qualitative_data,
        "errors": errors,
    }
