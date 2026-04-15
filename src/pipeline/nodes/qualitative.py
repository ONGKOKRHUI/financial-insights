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
            "Extract qualitative insights from the annual report excerpt below. "
            "Be concise, factual, and use information only from the provided text — do not hallucinate.",
        ),
        (
            "human",
            "Company: {ticker}\nFiscal Year: {fiscal_year}\nReport Period: {report_period}\n\n"
            "--- Report Excerpt ---\n{content}\n--- End of Excerpt ---\n\n"
            "Extract the future outlook summary and key strategic events as a JSON array.",
        ),
    ]
)

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=6000,
    chunk_overlap=400,
    separators=["\n## ", "\n### ", "\n\n", "\n", " "],
)


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

    # Use the first chunk that fits within the context window
    chunks = _SPLITTER.split_text(narrative_markdown)
    primary_chunk = "\n\n".join(chunks[:3])  # up to ~18 k chars

    try:
        result = chain.invoke(
            {
                "ticker": metadata.get("ticker", "UNKNOWN"),
                "fiscal_year": metadata.get("fiscal_year", "UNKNOWN"),
                "report_period": metadata.get("report_period", "UNKNOWN"),
                "content": primary_chunk[:10000],
            },
            config={"callbacks": callbacks},
        )
        qualitative_data: dict = result.model_dump() if result else {}
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
