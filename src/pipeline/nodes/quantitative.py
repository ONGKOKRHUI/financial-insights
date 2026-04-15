"""Node: extract_quantitative

Uses Google Gemini (via LangChain) with structured output to extract
financial tables from the table_markdown section.

Each LLM call is wrapped with a Langfuse callback for full observability.
"""

import json
import logging
import os
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Structured-output schemas (for LLM extraction, not DB validation) ─────────

class _IncomeStatementExtraction(BaseModel):
    revenue_bln: Optional[float] = Field(None, description="Total revenue in MYR billions")
    gross_profit_bln: Optional[float] = Field(None, description="Gross profit in MYR billions")
    operating_income_bln: Optional[float] = Field(None, description="Operating income / EBIT in MYR billions")
    net_income_bln: Optional[float] = Field(None, description="Net income / profit after tax in MYR billions")
    eps: Optional[float] = Field(None, description="Basic earnings per share in MYR")
    gross_margin_pct: Optional[float] = Field(None, description="Gross margin as percentage 0-100")
    operating_margin_pct: Optional[float] = Field(None, description="Operating margin as percentage 0-100")
    net_margin_pct: Optional[float] = Field(None, description="Net margin as percentage 0-100")


class _BalanceSheetExtraction(BaseModel):
    total_assets_bln: Optional[float] = Field(None, description="Total assets in MYR billions")
    total_liabilities_bln: Optional[float] = Field(None, description="Total liabilities in MYR billions")
    total_equity_bln: Optional[float] = Field(None, description="Total equity / shareholders' funds in MYR billions")
    cash_and_equivalents_bln: Optional[float] = Field(None, description="Cash and cash equivalents in MYR billions")
    total_debt_bln: Optional[float] = Field(None, description="Total borrowings / debt in MYR billions")


class _CashFlowExtraction(BaseModel):
    operating_cash_flow_bln: Optional[float] = Field(None, description="Net cash from operating activities in MYR billions")
    capital_expenditure_bln: Optional[float] = Field(None, description="Capital expenditure (capex) in MYR billions — use positive value")
    free_cash_flow_bln: Optional[float] = Field(None, description="Free cash flow = operating CF – capex in MYR billions")
    dividends_paid_bln: Optional[float] = Field(None, description="Dividends paid in MYR billions — use positive value")


class _KPIExtraction(BaseModel):
    revenue_bln: Optional[float] = Field(None, description="Revenue in MYR billions")
    net_income_bln: Optional[float] = Field(None, description="Net income in MYR billions")
    eps: Optional[float] = Field(None, description="EPS in MYR")
    pe_ratio: Optional[float] = Field(None, description="Price-to-earnings ratio")
    roe_pct: Optional[float] = Field(None, description="Return on equity as percentage 0-100")
    roace_pct: Optional[float] = Field(None, description="Return on average capital employed as percentage 0-100")
    debt_to_equity: Optional[float] = Field(None, description="Debt-to-equity ratio")
    dividend_yield_pct: Optional[float] = Field(None, description="Dividend yield as percentage 0-100")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        temperature=0,
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


_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a financial data extraction specialist for Malaysian public companies (Bursa Malaysia / KLSE). "
            "Extract numerical values accurately from the provided financial report excerpt. "
            "All monetary values must be in MYR billions (e.g., 1,234 MYR million → 1.234). "
            "Return null for any field you cannot find. Do not invent numbers.",
        ),
        (
            "human",
            "Company: {ticker}\nFiscal Year: {fiscal_year}\nReport Period: {report_period}\n\n"
            "--- Financial Report Excerpt ---\n{content}\n--- End of Excerpt ---\n\n"
            "Extract the {statement_type} figures.",
        ),
    ]
)


def _extract_statement(llm, schema, statement_type: str, content: str, metadata: dict, callbacks: list) -> dict:
    """Run one structured extraction and return a dict (empty on failure)."""
    try:
        structured_llm = llm.with_structured_output(schema)
        chain = _EXTRACTION_PROMPT | structured_llm
        result = chain.invoke(
            {
                "ticker": metadata.get("ticker", "UNKNOWN"),
                "fiscal_year": metadata.get("fiscal_year", "UNKNOWN"),
                "report_period": metadata.get("report_period", "UNKNOWN"),
                "content": content[:8000],  # token guard
                "statement_type": statement_type,
            },
            config={"callbacks": callbacks},
        )
        return result.model_dump() if result else {}
    except Exception as exc:
        logger.error("Structured extraction failed for %s: %s", statement_type, exc)
        return {}


# ── LangGraph node ─────────────────────────────────────────────────────────────

def extract_quantitative(state: dict) -> dict:
    """LangGraph node: extract income statement, balance sheet, cash flow, KPIs."""
    table_markdown: str = state.get("table_markdown", "")
    metadata: dict = state.get("metadata", {})
    errors: list = list(state.get("errors", []))

    if not table_markdown.strip():
        errors.append("extract_quantitative: no table content to process")
        return {"quantitative_data": {}, "errors": errors}

    llm = _build_llm()
    cb = _build_langfuse_callback()
    callbacks = [cb] if cb else []

    quantitative_data: dict = {}

    for statement_type, schema in [
        ("Income Statement", _IncomeStatementExtraction),
        ("Balance Sheet", _BalanceSheetExtraction),
        ("Cash Flow Statement", _CashFlowExtraction),
        ("KPI Summary", _KPIExtraction),
    ]:
        extracted = _extract_statement(llm, schema, statement_type, table_markdown, metadata, callbacks)
        key = statement_type.lower().replace(" ", "_")
        quantitative_data[key] = extracted
        logger.info("Extracted %s: %s", statement_type, extracted)

    return {
        "quantitative_data": quantitative_data,
        "errors": errors,
    }
