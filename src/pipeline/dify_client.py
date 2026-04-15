"""Dify Workflow API client (used when PIPELINE_ENGINE=dify).

Sends the LlamaParse Markdown as a payload to a Dify workflow endpoint
and awaits the structured JSON response, which is passed directly to
the database loader — bypassing the LangGraph nodes entirely.
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

_DIFY_API_URL = os.getenv("DIFY_API_URL", "")           # e.g. https://api.dify.ai/v1/workflows/run
_DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
_DIFY_TIMEOUT = int(os.getenv("DIFY_TIMEOUT_SECONDS", "120"))
_DIFY_MAX_RETRIES = int(os.getenv("DIFY_MAX_RETRIES", "3"))


class DifyClientError(Exception):
    """Raised when the Dify API returns an error or times out."""


def run_dify_workflow(markdown_text: str, metadata: dict) -> dict:
    """Send markdown to the Dify workflow and return the validated payload dict.

    Args:
        markdown_text: Full parsed Markdown from LlamaParse/PyMuPDF.
        metadata: Dict with ticker, fiscal_year, report_period, source_pdf.

    Returns:
        Dict that matches FinancialReportPayload structure.

    Raises:
        DifyClientError: if the workflow call fails after retries.
    """
    if not _DIFY_API_URL or not _DIFY_API_KEY:
        raise DifyClientError(
            "DIFY_API_URL and DIFY_API_KEY must be set when PIPELINE_ENGINE=dify"
        )

    headers = {
        "Authorization": f"Bearer {_DIFY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": {
            "markdown_text": markdown_text[:50000],   # guard against very large documents
            "ticker": metadata.get("ticker", ""),
            "fiscal_year": str(metadata.get("fiscal_year", "")),
            "report_period": metadata.get("report_period", ""),
        },
        "response_mode": "blocking",
        "user": "finsight-etl-pipeline",
    }

    last_exc: Exception = Exception("No attempt made")
    for attempt in range(1, _DIFY_MAX_RETRIES + 1):
        try:
            logger.info(
                "Calling Dify workflow (attempt %d/%d) for %s FY%s",
                attempt, _DIFY_MAX_RETRIES,
                metadata.get("ticker"), metadata.get("fiscal_year"),
            )
            response = requests.post(
                _DIFY_API_URL,
                json=payload,
                headers=headers,
                timeout=_DIFY_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            # Dify blocking response: {"data": {"outputs": {...}}}
            outputs = data.get("data", {}).get("outputs", data)
            logger.info("Dify workflow succeeded: %s", list(outputs.keys()))
            return _normalise_dify_output(outputs, metadata)

        except requests.HTTPError as exc:
            logger.warning("Dify HTTP error on attempt %d: %s", attempt, exc)
            last_exc = exc
        except requests.Timeout as exc:
            logger.warning("Dify timeout on attempt %d", attempt)
            last_exc = exc
        except Exception as exc:
            logger.warning("Dify unexpected error on attempt %d: %s", attempt, exc)
            last_exc = exc

        if attempt < _DIFY_MAX_RETRIES:
            time.sleep(5 * attempt)

    raise DifyClientError(f"Dify workflow failed after {_DIFY_MAX_RETRIES} attempts: {last_exc}") from last_exc


def _normalise_dify_output(outputs: dict, metadata: dict) -> dict:
    """Ensure the Dify response conforms to FinancialReportPayload structure.

    Dify workflows can return arbitrary keys depending on how the workflow
    is designed. This function maps common patterns to the expected schema.
    """
    return {
        "ticker": metadata.get("ticker", outputs.get("ticker", "UNKNOWN")),
        "fiscal_year": metadata.get("fiscal_year", outputs.get("fiscal_year")),
        "report_period": metadata.get("report_period", outputs.get("report_period", "")),
        "source_pdf": metadata.get("source_pdf", ""),
        "income_statement": outputs.get("income_statement"),
        "balance_sheet": outputs.get("balance_sheet"),
        "cash_flow": outputs.get("cash_flow"),
        "qualitative_insight": outputs.get("qualitative_insight"),
        "kpi_summary": outputs.get("kpi_summary"),
    }
