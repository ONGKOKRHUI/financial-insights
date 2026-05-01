"""Node: extract_quantitative

Uses Google Gemini (via LangChain) with structured output to extract
financial tables from the full document markdown.

Each LLM call is wrapped with a Langfuse callback for full observability.
Post-processing normalises raw string values to MYR-billion floats.
"""

import logging
import os
import re
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Two-stage value container ──────────────────────────────────────────────────

class FinancialValue(BaseModel):
    raw_value: Optional[str] = Field(
        None,
        description=(
            "The exact string value from the table, "
            "e.g. '(1,350,348)' or '12,345.00'"
        ),
    )
    unit_header: Optional[str] = Field(
        None,
        description=(
            "The unit stated at the top of the table/column, "
            "e.g. 'RM 000', 'MYR Millions', or 'sen'"
        ),
    )


# ── Structured-output schemas (for LLM extraction, not DB validation) ─────────

class _IncomeStatementExtraction(BaseModel):
    revenue_bln: Optional[FinancialValue] = Field(None, description="Total revenue / turnover")
    gross_profit_bln: Optional[FinancialValue] = Field(None, description="Gross profit")
    operating_income_bln: Optional[FinancialValue] = Field(None, description="Operating income / EBIT")
    net_income_bln: Optional[FinancialValue] = Field(None, description="Net income / profit after tax")
    eps: Optional[FinancialValue] = Field(None, description="Basic earnings per share")
    gross_margin_pct: Optional[FinancialValue] = Field(None, description="Gross margin percentage")
    operating_margin_pct: Optional[FinancialValue] = Field(None, description="Operating margin percentage")
    net_margin_pct: Optional[FinancialValue] = Field(None, description="Net margin percentage")


class _BalanceSheetExtraction(BaseModel):
    total_assets_bln: Optional[FinancialValue] = Field(None, description="Total assets")
    total_liabilities_bln: Optional[FinancialValue] = Field(None, description="Total liabilities")
    total_equity_bln: Optional[FinancialValue] = Field(None, description="Total equity / shareholders' funds")
    cash_and_equivalents_bln: Optional[FinancialValue] = Field(None, description="Cash and cash equivalents")
    total_debt_bln: Optional[FinancialValue] = Field(None, description="Total borrowings / debt")


class _CashFlowExtraction(BaseModel):
    operating_cash_flow_bln: Optional[FinancialValue] = Field(None, description="Net cash from operating activities")
    capital_expenditure_bln: Optional[FinancialValue] = Field(None, description="Capital expenditure (capex)")
    free_cash_flow_bln: Optional[FinancialValue] = Field(None, description="Free cash flow = operating CF – capex")
    dividends_paid_bln: Optional[FinancialValue] = Field(None, description="Dividends paid")


class _KPIExtraction(BaseModel):
    revenue_bln: Optional[FinancialValue] = Field(None, description="Revenue / turnover")
    net_income_bln: Optional[FinancialValue] = Field(None, description="Net income / profit after tax")
    eps: Optional[FinancialValue] = Field(None, description="Earnings per share")
    pe_ratio: Optional[FinancialValue] = Field(None, description="Price-to-earnings ratio")
    roe_pct: Optional[FinancialValue] = Field(None, description="Return on equity percentage")
    roace_pct: Optional[FinancialValue] = Field(None, description="Return on average capital employed percentage")
    debt_to_equity: Optional[FinancialValue] = Field(None, description="Debt-to-equity ratio")
    dividend_yield_pct: Optional[FinancialValue] = Field(None, description="Dividend yield percentage")


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

        return CallbackHandler()
    except Exception as exc:
        logger.warning("Langfuse callback unavailable: %s", exc)
        return None


_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a financial data extraction specialist for Malaysian public companies (Bursa Malaysia / KLSE). "
            "Your task is to extract SPECIFIC values from structured financial tables in the document below.\n\n"
            "EXTRACTION RULES:\n"
            "  • Search the ENTIRE document — tables may appear anywhere\n"
            "  • Look for both Markdown tables (|...|) and plain-text tabular data\n"
            "  • Extract the EXACT string representation of the number as it appears in the text "
            "(including commas and parentheses), e.g. '(1,350,348)' or '12,345.00'\n"
            "  • Identify the unit stated at the top of the table or column header, "
            "e.g. 'RM 000', 'MYR Millions', 'sen'\n"
            "  • If a field is present in the table you MUST return it — do not return null if the number exists\n"
            "  • Return null ONLY if a field is genuinely absent from the document\n"
            "  • Do not invent, estimate, or convert numbers",
        ),
        (
            "human",
            "Company: {ticker}\nFiscal Year: {fiscal_year}\nReport Period: {report_period}\n\n"
            "--- Financial Report ---\n{content}\n--- End of Report ---\n\n"
            "Extract the {statement_type} figures from the document above.\n"
            "Look specifically for tables or rows labelled with these terms (or close equivalents):\n"
            "{field_hints}\n\n"
            "For each value, return the raw string exactly as printed and the unit header from the table. "
            "Return null for any field that is truly absent.",
        ),
    ]
)


_FIELD_HINTS: dict[str, str] = {
    "Income Statement": (
        "Revenue / Turnover / Total Income, Gross Profit, Operating Profit / EBIT, "
        "Net Profit / Profit After Tax / PAT, Earnings Per Share / EPS, "
        "Gross Margin %, Operating Margin %, Net Margin %"
    ),
    "Balance Sheet": (
        "Total Assets, Total Liabilities, Total Equity / Shareholders' Funds, "
        "Cash and Cash Equivalents / Bank Balances, Total Borrowings / Debt"
    ),
    "Cash Flow Statement": (
        "Net Cash from Operating Activities / Operating Cash Flow, "
        "Capital Expenditure / Purchase of PPE / Capex, "
        "Free Cash Flow (= Operating CF - Capex), "
        "Dividends Paid / Dividends to Shareholders"
    ),
    "KPI Summary": (
        "Revenue / Turnover, Net Income / Profit After Tax / PAT, "
        "Basic EPS / Earnings Per Share (sen or MYR), "
        "Price-to-Earnings (P/E) Ratio, Return on Equity (ROE) %, "
        "Return on Average Capital Employed (ROACE) %, "
        "Debt-to-Equity Ratio / Gearing Ratio, Dividend Yield %. "
        "Check financial highlights, key indicators, ratios, and statistics sections. "
        "Some of these may only appear in financial highlights tables, not the income statement."
    ),
}


def _extract_statement(llm, schema, statement_type: str, content: str, metadata: dict, callbacks: list) -> dict:
    """Run one structured extraction and return a dict (empty on failure)."""
    try:
        structured_llm = llm.with_structured_output(schema)
        chain = _EXTRACTION_PROMPT | structured_llm

        field_hints = _FIELD_HINTS.get(statement_type, "")

        logger.debug(
            "[%s] Sending %d chars to LLM.",
            statement_type, len(content),
        )

        result = chain.invoke(
            {
                "ticker": metadata.get("ticker", "UNKNOWN"),
                "fiscal_year": metadata.get("fiscal_year", "UNKNOWN"),
                "report_period": metadata.get("report_period", "UNKNOWN"),
                "content": content,
                "statement_type": statement_type,
                "field_hints": field_hints,
            },
            config={"callbacks": callbacks},
        )

        raw = result.model_dump() if result else {}
        none_fields = [k for k, v in raw.items() if v is None]
        populated_fields = [k for k, v in raw.items() if v is not None]
        logger.debug(
            "[%s] LLM result -- populated: %s | null: %s",
            statement_type, populated_fields, none_fields,
        )
        return raw
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

    quantitative_data = normalize_financial_data(quantitative_data)

    return {
        "quantitative_data": quantitative_data,
        "errors": errors,
    }


# ── Post-processing utility ────────────────────────────────────────────────────

def _parse_raw_value(raw_value: str) -> float:
    """Convert a raw financial string to a plain float.

    Handles:
      - Commas as thousands separators: '12,345.00' → 12345.0
      - Parentheses as negatives: '(1,350)' → -1350.0
      - Leading/trailing whitespace
    """
    s = raw_value.strip().replace(",", "").replace(" ", "")
    
    # Handle accounting dashes (which mean zero)
    if s == "-" or s == "–" or s == "": 
        return 0.0
        
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    return -float(s) if negative else float(s)


def _unit_multiplier(unit_header: str) -> float:
    """Return the divisor needed to convert a raw value to MYR billions.

    Examples:
      'RM 000' / 'RM\'000' / \"'000\" / 'thousands'  →  divide by 1,000,000
      'RM million' / 'MYR Millions'                  →  divide by 1,000
      'RM billion' / 'MYR Billions'                  →  divide by 1  (no-op)
      'sen'                                           →  1  (keep as-is; caller decides)
    """
    u = unit_header.lower()

    if re.search(r"(billion|'bil|b$)", u):
        return 1.0

    if re.search(r"(million|'mil|m$)", u):
        return 1_000.0

    # Thousands expressed as RM'000 / RM 000 / '000 / thousand
    if re.search(r"(thousand|'000|000)", u):
        return 1_000_000.0

    # Fallback: no recognised multiplier — return as-is
    logger.warning("Unrecognised unit header %r — no multiplier applied", unit_header)
    return 1.0


def normalize_financial_data(extracted_data: dict) -> dict:
    """Recursively convert FinancialValue dicts to normalised MYR-billion floats.

    Walks the nested dict produced by ``extract_quantitative``.  Whenever it
    encounters a dict with ``raw_value`` and ``unit_header`` keys it:

      1. Parses ``raw_value`` to a float (handling commas and parentheses).
      2. Divides by the appropriate multiplier derived from ``unit_header``.
      3. Replaces the nested dict with the resulting float.

    Dicts that do not have both keys are recursed into unchanged.
    """

    def _process(node: Any) -> Any:
        if not isinstance(node, dict):
            return node

        if "raw_value" in node and "unit_header" in node:
            raw = node.get("raw_value")
            unit = node.get("unit_header")

            if raw is None:
                return None

            try:
                value = _parse_raw_value(raw)
            except (ValueError, AttributeError) as exc:
                logger.warning("Could not parse raw_value %r: %s", raw, exc)
                return None

            if unit:
                divisor = _unit_multiplier(unit)
                value = value / divisor

            return value

        return {k: _process(v) for k, v in node.items()}

    return _process(extracted_data)
