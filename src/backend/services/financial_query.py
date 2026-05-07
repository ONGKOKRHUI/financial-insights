"""Financial metric lookup service for Jarvis Intent 2 (FinancialInfo).

Architecture
------------
This service is the *only* place in the Jarvis pipeline that touches financial
database tables.  It owns three concerns:

1.  MetricSpec catalog  — maps natural-language metric aliases to the correct
    SQLAlchemy model, column, unit, and source-provenance type.
2.  Company alias map   — normalises free-text company references to canonical
    KLSE tickers without running an LLM.
3.  Postgres lookup     — queries the correct table + column deterministically;
    no LLM-generated SQL is ever executed.

Adding new companies
--------------------
Add the canonical ticker to _COMPANY_ALIASES (and any common short names / full
legal names the user might speak).  Then insert matching rows into the relevant
financial tables via Alembic migration + seed/import script.  No handler code
needs to change.

Adding new metrics
------------------
1.  Decide which table owns the value (income_statement, balance_sheet,
    cash_flow, kpi, or a future dedicated table).
2.  Add the column via an Alembic migration and update the seed/import script.
3.  Add one MetricSpec entry below with its aliases, unit, and source_type.
4.  Add tests in test_financial_query.py.

Public API
----------
    query_financial_intent(company, metric, time_period) -> FinancialQueryResult
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


# ── MetricSpec ────────────────────────────────────────────────────────────────


@dataclass
class MetricSpec:
    """Describes a single financial metric and how to retrieve it.

    Attributes
    ----------
    canonical_name:   machine-readable key, used in messages and source labels.
    aliases:          lower-cased phrases that resolve to this metric.
    statement_type:   matches the /search endpoint statement_type values.
                      One of: "income_statement", "balance_sheet", "cash_flow",
                      "kpi", "qualitative".
    field_name:       SQLAlchemy model attribute name to read.
    unit:             display unit appended to the formatted value.
    source_type:      provenance of the value — one of:
                        "financial_report"  extracted directly from annual report
                        "derived"           computed ratio (e.g. gross profit / revenue)
                        "external_market"   requires live market price (e.g. P/E, yield)
    display_precision: decimal places used when formatting the value.
    """

    canonical_name: str
    aliases: list[str]
    statement_type: str
    field_name: str
    unit: str
    source_type: str
    display_precision: int = 2


# ── Metric catalog ─────────────────────────────────────────────────────────────
#
# Ordering matters for partial-alias matching: put more-specific entries before
# generic ones so "net margin" matches before "margin".
#
# To add a new metric:
#   1. Append a MetricSpec here.
#   2. Add an Alembic migration if the column is new.
#   3. Add tests in test_financial_query.py.

METRIC_CATALOG: list[MetricSpec] = [
    # ── Income Statement ──────────────────────────────────────────────────────
    MetricSpec(
        canonical_name="revenue",
        aliases=["revenue", "sales", "turnover", "total revenue", "total sales", "net revenue", "total income"],
        statement_type="income_statement",
        field_name="revenue_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="gross_profit",
        aliases=["gross profit", "gross income", "gross earnings"],
        statement_type="income_statement",
        field_name="gross_profit_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="operating_income",
        aliases=["operating income", "operating profit", "ebit", "operating earnings", "profit from operations", "operating result"],
        statement_type="income_statement",
        field_name="operating_income_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="net_income",
        aliases=["net income", "net profit", "net earnings", "profit after tax", "pat",
                 "bottom line", "net profit after tax", "earnings", "profit"],
        statement_type="income_statement",
        field_name="net_income_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="eps",
        aliases=["eps", "earnings per share", "earning per share", "basic eps"],
        statement_type="income_statement",
        field_name="eps",
        unit="MYR",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="gross_margin",
        aliases=["gross margin", "gross profit margin"],
        statement_type="income_statement",
        field_name="gross_margin_pct",
        unit="%",
        source_type="derived",
    ),
    MetricSpec(
        canonical_name="operating_margin",
        aliases=["operating margin", "operating profit margin", "ebit margin"],
        statement_type="income_statement",
        field_name="operating_margin_pct",
        unit="%",
        source_type="derived",
    ),
    MetricSpec(
        canonical_name="net_margin",
        aliases=["net margin", "net profit margin", "profit margin", "return on sales", "net income margin"],
        statement_type="income_statement",
        field_name="net_margin_pct",
        unit="%",
        source_type="derived",
    ),

    # ── Balance Sheet ─────────────────────────────────────────────────────────
    MetricSpec(
        canonical_name="total_assets",
        aliases=["total assets", "assets", "asset base"],
        statement_type="balance_sheet",
        field_name="total_assets_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="total_liabilities",
        aliases=["total liabilities", "liabilities", "total obligations"],
        statement_type="balance_sheet",
        field_name="total_liabilities_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="total_equity",
        aliases=["total equity", "equity", "shareholders equity", "shareholder equity",
                 "book value", "net assets"],
        statement_type="balance_sheet",
        field_name="total_equity_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="cash",
        aliases=["cash", "cash and equivalents", "cash equivalents",
                 "cash and cash equivalents", "liquid assets", "cash position"],
        statement_type="balance_sheet",
        field_name="cash_and_equivalents_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="total_debt",
        aliases=["total debt", "debt", "borrowings", "total borrowings", "long term debt"],
        statement_type="balance_sheet",
        field_name="total_debt_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),

    # ── Cash Flow ─────────────────────────────────────────────────────────────
    MetricSpec(
        canonical_name="operating_cash_flow",
        aliases=["operating cash flow", "cash flow from operations", "operating cashflow",
                 "cash from operations", "cffo", "cash flow operations"],
        statement_type="cash_flow",
        field_name="operating_cash_flow_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="capital_expenditure",
        aliases=["capital expenditure", "capex", "capital expenditures",
                 "capital spending", "capex spending"],
        statement_type="cash_flow",
        field_name="capital_expenditure_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="free_cash_flow",
        aliases=["free cash flow", "fcf", "free cashflow"],
        statement_type="cash_flow",
        field_name="free_cash_flow_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),
    MetricSpec(
        canonical_name="dividends_paid",
        aliases=["dividends paid", "dividend payment", "total dividends paid"],
        statement_type="cash_flow",
        field_name="dividends_paid_bln",
        unit="MYR billion",
        source_type="financial_report",
    ),

    # ── KPI Summaries ─────────────────────────────────────────────────────────
    MetricSpec(
        canonical_name="pe_ratio",
        aliases=["pe ratio", "p/e ratio", "price to earnings", "price earnings ratio",
                 "pe", "p/e", "price earnings", "p e ratio"],
        statement_type="kpi",
        field_name="pe_ratio",
        unit="x",
        source_type="external_market",
    ),
    MetricSpec(
        canonical_name="roe",
        aliases=["roe", "return on equity", "return on equity percentage", "return on equity ratio"],
        statement_type="kpi",
        field_name="roe_pct",
        unit="%",
        source_type="derived",
    ),
    MetricSpec(
        canonical_name="roace",
        aliases=["roace", "return on average capital employed",
                 "return on capital employed", "roce", "return on capital"],
        statement_type="kpi",
        field_name="roace_pct",
        unit="%",
        source_type="derived",
    ),
    MetricSpec(
        canonical_name="debt_to_equity",
        aliases=["debt to equity", "debt equity ratio", "d/e ratio", "leverage ratio",
                 "gearing ratio", "debt equity", "d/e"],
        statement_type="kpi",
        field_name="debt_to_equity",
        unit="x",
        source_type="derived",
    ),
    MetricSpec(
        canonical_name="dividend_yield",
        aliases=["dividend yield", "yield", "dividend yield percentage", "dividend rate"],
        statement_type="kpi",
        field_name="dividend_yield_pct",
        unit="%",
        source_type="external_market",
    ),
    MetricSpec(
        canonical_name="dividends",
        aliases=["dividends", "dividend"],
        statement_type="kpi",
        field_name="dividend_yield_pct",
        unit="%",
        source_type="external_market",
    ),
]

# Build flat alias → MetricSpec lookup
_ALIAS_TO_METRIC: dict[str, MetricSpec] = {}
for _spec in METRIC_CATALOG:
    for _alias in _spec.aliases:
        _ALIAS_TO_METRIC[_alias.lower()] = _spec


# ── Company aliases ────────────────────────────────────────────────────────────
#
# Keys are lower-cased spoken/written forms; values are canonical KLSE tickers.
# The LLM already normalises company names to uppercase in entities["company"],
# so most inputs will match the direct-ticker check before reaching this map.
#
# To add a new company:
#   1. Add its canonical ticker and common aliases here.
#   2. Insert the company profile and financial rows into the database.
#   3. No Jarvis handler code needs to change.

COMPANY_ALIASES: dict[str, str] = {
    # MAYBANK
    "maybank": "MAYBANK",
    "malayan banking": "MAYBANK",
    "malayan banking berhad": "MAYBANK",
    "mbb": "MAYBANK",
    "m2u": "MAYBANK",

    # CIMB
    "cimb": "CIMB",
    "cimb group": "CIMB",
    "cimb bank": "CIMB",
    "cimb group holdings": "CIMB",
    "cimb group holdings berhad": "CIMB",

    # TNB
    "tnb": "TNB",
    "tenaga": "TNB",
    "tenaga nasional": "TNB",
    "tenaga nasional berhad": "TNB",
    "national energy": "TNB",

    # PETRONAS
    "petronas": "PETRONAS",
    "petroliam nasional": "PETRONAS",
    "petroliam nasional berhad": "PETRONAS",

    # MAXIS
    "maxis": "MAXIS",
    "maxis berhad": "MAXIS",
    "maxis communications": "MAXIS",

    # TM
    "tm": "TM",
    "telekom malaysia": "TM",
    "telekom malaysia berhad": "TM",

    # GENTING
    "genting": "GENTING",
    "genting berhad": "GENTING",
    "genting group": "GENTING",
    "rwg": "GENTING",

    # SUNWAY
    "sunway": "SUNWAY",
    "sunway berhad": "SUNWAY",
    "sunway group": "SUNWAY",
}

# Set of all canonical tickers (for fast direct-match check)
_KNOWN_TICKERS: frozenset[str] = frozenset(COMPANY_ALIASES.values())


# ── Public resolver functions ──────────────────────────────────────────────────


def resolve_ticker(company_name: str) -> Optional[str]:
    """Normalise a company reference to a canonical KLSE ticker.

    Resolution order:
    1.  Direct uppercase match against known tickers (e.g. "MAYBANK").
    2.  Case-insensitive alias lookup.
    3.  Partial substring match (longest alias wins).
    4.  PostgreSQL name search fallback.

    Returns the canonical ticker or None if unresolvable.
    """
    if not company_name:
        return None

    upper = company_name.strip().upper()
    if upper in _KNOWN_TICKERS:
        return upper

    normalized = company_name.strip().lower()
    if normalized in COMPANY_ALIASES:
        return COMPANY_ALIASES[normalized]

    # Partial match: longest alias that is a substring of the input or vice versa
    best_ticker: Optional[str] = None
    best_len = 0
    for alias, ticker in COMPANY_ALIASES.items():
        if alias in normalized or normalized in alias:
            if len(alias) > best_len:
                best_ticker = ticker
                best_len = len(alias)
    if best_ticker:
        return best_ticker

    # Database fallback
    try:
        from database import SessionLocal
        from models import Company

        db = SessionLocal()
        try:
            row = db.query(Company).filter(Company.ticker == upper).first()
            if row:
                return row.ticker
            row = db.query(Company).filter(Company.name.ilike(f"%{company_name}%")).first()
            if row:
                return row.ticker
        finally:
            db.close()
    except Exception as exc:
        logger.warning("resolve_ticker DB fallback failed for %r: %s", company_name, exc)

    return None


def resolve_metric(metric_text: str) -> Optional[MetricSpec]:
    """Map a natural-language metric string to a MetricSpec.

    Tries exact alias match first, then longest-substring partial match.
    Returns None if no catalog entry matches.
    """
    if not metric_text:
        return None

    normalized = metric_text.strip().lower()

    if normalized in _ALIAS_TO_METRIC:
        return _ALIAS_TO_METRIC[normalized]

    best: Optional[MetricSpec] = None
    best_len = 0
    for alias, spec in _ALIAS_TO_METRIC.items():
        if alias in normalized or normalized in alias:
            if len(alias) > best_len:
                best = spec
                best_len = len(alias)

    return best


def parse_fiscal_year(time_period: Optional[str]) -> Optional[int]:
    """Parse a natural-language time period to an integer fiscal year.

    Returns:
        int   — specific fiscal year (e.g. 2024)
        None  — caller should use the latest available row
    """
    if time_period is None:
        return None

    text = time_period.strip().lower()

    if not text or text in ("latest", "most recent", "current", "recent", "now"):
        return None

    if text in ("last year", "previous year", "prior year", "last fiscal year"):
        return date.today().year - 1

    if text in ("this year", "current year", "present year"):
        return date.today().year

    m = re.match(r"(\d+)\s+years?\s+ago", text)
    if m:
        return date.today().year - int(m.group(1))

    m = re.match(r"fy\s*(\d{4})", text)
    if m:
        return int(m.group(1))

    # "Q1 2024" — quarterly period; we only have annual data so extract the year
    m = re.match(r"q[1-4]\s*(\d{4})", text)
    if m:
        return int(m.group(1))

    m = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    if m:
        return int(m.group(1))

    return None


# ── Result type ────────────────────────────────────────────────────────────────


@dataclass
class FinancialQueryResult:
    """Structured result returned by lookup_financial_metric."""

    ticker: str
    company_name: str
    metric: MetricSpec
    fiscal_year: int
    value: Optional[float]
    found: bool
    message: str        # user-facing prose (chatbot message)
    voice: str          # TTS-optimised (≤300 chars)
    sources: list[dict] = field(default_factory=list)


# ── Value formatter ────────────────────────────────────────────────────────────


def _format_value(value: float, unit: str, precision: int) -> str:
    if unit == "MYR billion":
        return f"MYR {value:.{precision}f} billion"
    if unit == "%":
        return f"{value:.{precision}f}%"
    if unit == "x":
        return f"{value:.{precision}f}x"
    if unit == "MYR":
        return f"MYR {value:.{precision}f}"
    return f"{value:.{precision}f} {unit}"


# ── Main entry point ───────────────────────────────────────────────────────────


def lookup_financial_metric(
    ticker: str,
    metric: MetricSpec,
    fiscal_year: Optional[int],
) -> FinancialQueryResult:
    """Query PostgreSQL for a specific metric for a company and fiscal year.

    If fiscal_year is None the most recent available row is returned.

    This function never generates SQL dynamically; it dispatches to a
    predefined model using the statement_type from the MetricSpec.
    """
    from database import SessionLocal
    from models import BalanceSheet, CashFlow, Company, IncomeStatement, KPISummary

    _MODEL_MAP = {
        "income_statement": IncomeStatement,
        "balance_sheet": BalanceSheet,
        "cash_flow": CashFlow,
        "kpi": KPISummary,
    }

    try:
        db = SessionLocal()
    except Exception as exc:
        logger.warning("lookup_financial_metric could not open DB session: %s", exc)
        msg = f"I encountered an error retrieving {metric.canonical_name.replace('_', ' ')} data for {ticker}."
        return FinancialQueryResult(
            ticker=ticker, company_name=ticker, metric=metric,
            fiscal_year=fiscal_year or 0, value=None, found=False,
            message=msg, voice="I encountered an error looking up that financial data.",
        )

    try:
        company_row = db.query(Company).filter(Company.ticker == ticker).first()
        company_name = company_row.name if company_row else ticker

        model = _MODEL_MAP.get(metric.statement_type)
        if model is None:
            msg = f"I don't have a data source for {metric.canonical_name.replace('_', ' ')} yet."
            return FinancialQueryResult(
                ticker=ticker, company_name=company_name, metric=metric,
                fiscal_year=fiscal_year or 0, value=None, found=False,
                message=msg, voice=msg,
            )

        q = db.query(model).filter(model.ticker == ticker)
        if fiscal_year:
            q = q.filter(model.fiscal_year == fiscal_year)
        else:
            q = q.order_by(model.fiscal_year.desc())
        row = q.first()

        if not row:
            year_desc = f"FY{fiscal_year}" if fiscal_year else "the most recent year"
            msg = (
                f"I couldn't find {metric.canonical_name.replace('_', ' ')} data "
                f"for {company_name} in {year_desc}."
            )
            return FinancialQueryResult(
                ticker=ticker, company_name=company_name, metric=metric,
                fiscal_year=fiscal_year or 0, value=None, found=False,
                message=msg, voice=msg,
            )

        value = getattr(row, metric.field_name, None)
        actual_fy = row.fiscal_year

        if value is None:
            msg = (
                f"{company_name}'s {metric.canonical_name.replace('_', ' ')} "
                f"for FY{actual_fy} is not available."
            )
            return FinancialQueryResult(
                ticker=ticker, company_name=company_name, metric=metric,
                fiscal_year=actual_fy, value=None, found=False,
                message=msg, voice=msg,
            )

        formatted = _format_value(value, metric.unit, metric.display_precision)
        source_label = {
            "financial_report": "Annual Report",
            "derived": "Derived from Annual Report",
            "external_market": "Market Data (externally derived)",
        }.get(metric.source_type, metric.source_type)

        display_name = metric.canonical_name.replace("_", " ")
        msg = f"{company_name}'s {display_name} for FY{actual_fy} was {formatted}."
        note = (
            f" (Note: this figure is based on {source_label} and may not reflect live market data.)"
            if metric.source_type == "external_market"
            else ""
        )
        message = msg + note
        voice = msg  # keep voice short

        sources = [
            {
                "title": (
                    f"{company_name} ({ticker}) — "
                    f"{metric.statement_type.replace('_', ' ').title()} FY{actual_fy}"
                ),
                "source_path": "/search",
                "snippet": (
                    f"{display_name.title()}: {formatted} "
                    f"({source_label})"
                ),
                "rank": 1,
                "metadata": {
                    "ticker": ticker,
                    "fiscal_year": actual_fy,
                    "statement_type": metric.statement_type,
                    "field": metric.field_name,
                    "unit": metric.unit,
                    "source_type": metric.source_type,
                },
            }
        ]

        return FinancialQueryResult(
            ticker=ticker, company_name=company_name, metric=metric,
            fiscal_year=actual_fy, value=value, found=True,
            message=message, voice=voice, sources=sources,
        )

    except Exception as exc:
        logger.warning(
            "lookup_financial_metric DB error for %s / %s: %s",
            ticker, metric.canonical_name, exc,
        )
        msg = f"I encountered an error retrieving {metric.canonical_name.replace('_', ' ')} data for {ticker}."
        return FinancialQueryResult(
            ticker=ticker, company_name=ticker, metric=metric,
            fiscal_year=fiscal_year or 0, value=None, found=False,
            message=msg, voice="I encountered an error looking up that financial data.",
        )
    finally:
        db.close()


# ── Main entry point for Jarvis handle_financial ──────────────────────────────


def query_financial_intent(
    company: Optional[str],
    metric_text: Optional[str],
    time_period: Optional[str],
) -> dict:
    """Resolve entities from the Jarvis intent and return a Jarvis output dict.

    This is the single function called by handle_financial.

    Returns a dict with keys: found, message, voice, sources, ticker, fiscal_year.
    The caller (handle_financial) wraps this into the standard Jarvis output shape.
    """
    # 1. Resolve company → ticker
    ticker = resolve_ticker(company or "") if company else None
    if not ticker:
        company_label = company or "the requested company"
        msg = (
            f"I couldn't identify '{company_label}' as a company in my database. "
            "Please specify a company by its full name or ticker, for example MAYBANK or Tenaga."
        )
        return {"found": False, "message": msg, "voice": msg, "sources": [], "ticker": None, "fiscal_year": None}

    # 2. Resolve metric
    metric_spec = resolve_metric(metric_text or "") if metric_text else None
    if not metric_spec:
        metric_label = metric_text or "a financial metric"
        msg = (
            f"I understood you're asking about {ticker}, but I couldn't map "
            f"'{metric_label}' to a supported financial metric. "
            "Try asking for revenue, net income, P/E ratio, EPS, ROE, free cash flow, "
            "or another standard financial figure."
        )
        return {"found": False, "message": msg, "voice": msg, "sources": [], "ticker": ticker, "fiscal_year": None}

    # 3. Parse fiscal year
    fiscal_year = parse_fiscal_year(time_period)

    # 4. Lookup
    result = lookup_financial_metric(ticker, metric_spec, fiscal_year)

    return {
        "found": result.found,
        "message": result.message,
        "voice": result.voice,
        "sources": result.sources,
        "ticker": result.ticker,
        "fiscal_year": result.fiscal_year,
    }
