"""Node: parse_pdf

Uses the LlamaCloud async API to convert a PDF into structured Markdown.
Falls back to PyMuPDF (fitz) if LlamaParse fails or the API key is absent.
"""

import asyncio
import logging
import os
import re

logger = logging.getLogger(__name__)

_LLAMA_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY", "")


def _extract_metadata_from_path(pdf_path: str) -> dict:
    """Derive ticker, fiscal_year, report_period from the scraper filename convention.

    Expected filename: {TICKER}_{YEAR}_{QUARTER}.pdf
    e.g. MAYBANK_2024_Q3.pdf
    """
    filename = os.path.basename(pdf_path)
    stem = os.path.splitext(filename)[0]
    parts = stem.split("_")
    metadata: dict = {"source_pdf": pdf_path}

    if len(parts) >= 3:
        metadata["ticker"] = parts[0]
        try:
            metadata["fiscal_year"] = int(parts[1])
        except ValueError:
            metadata["fiscal_year"] = None
        metadata["report_period"] = "_".join(parts[2:])
    elif len(parts) == 2:
        metadata["ticker"] = parts[0]
        try:
            metadata["fiscal_year"] = int(parts[1])
        except ValueError:
            metadata["fiscal_year"] = None
        metadata["report_period"] = "ANNUAL"
    else:
        metadata["ticker"] = stem
        metadata["fiscal_year"] = None
        metadata["report_period"] = "UNKNOWN"

    return metadata


async def _llamaparse(pdf_path: str) -> str:
    """Call LlamaCloud async API and return full Markdown."""
    from llama_cloud import AsyncLlamaCloud  # type: ignore

    client = AsyncLlamaCloud(api_key=_LLAMA_API_KEY)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    file_obj = await client.files.create(file=(os.path.basename(pdf_path), pdf_bytes, "application/pdf"), purpose="parse")
    result = await client.parsing.parse(
        file_id=file_obj.id,
        version="latest",
        tier="agentic",
        expand=["markdown_full"],
    )
    return result.markdown_full or ""


def _pymupdf_fallback(pdf_path: str) -> str:
    """Extract plain text from a PDF using PyMuPDF (fitz)."""
    try:
        import fitz  # type: ignore  # pymupdf

        doc = fitz.open(pdf_path)
        pages = [page.get_text("text") for page in doc]
        doc.close()
        return "\n\n".join(pages)
    except Exception as exc:
        logger.error("PyMuPDF fallback also failed for %s: %s", pdf_path, exc)
        return ""


def parse_pdf(state: dict) -> dict:
    """LangGraph node: parse PDF → markdown_text + metadata."""
    pdf_path: str = state["pdf_path"]
    errors: list = list(state.get("errors", []))
    metadata: dict = dict(state.get("metadata", {}))

    # Always derive metadata from the filename regardless of parse outcome
    file_meta = _extract_metadata_from_path(pdf_path)
    metadata.update({k: v for k, v in file_meta.items() if v is not None})

    markdown_text = ""

    if _LLAMA_API_KEY:
        try:
            logger.info("Parsing %s with LlamaParse …", pdf_path)
            markdown_text = asyncio.run(_llamaparse(pdf_path))
            logger.info("LlamaParse succeeded (%d chars)", len(markdown_text))
        except Exception as exc:
            logger.warning("LlamaParse failed, falling back to PyMuPDF: %s", exc)
            errors.append(f"LlamaParse failed: {exc}")

    if not markdown_text:
        logger.info("Using PyMuPDF fallback for %s", pdf_path)
        markdown_text = _pymupdf_fallback(pdf_path)

    if not markdown_text:
        errors.append(f"Could not extract text from {pdf_path}")
        logger.error("All extraction methods failed for %s", pdf_path)

    return {
        **state,
        "markdown_text": markdown_text,
        "metadata": metadata,
        "errors": errors,
    }
