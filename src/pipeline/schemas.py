"""Pydantic v2 schemas for the FinSight ETL pipeline.

These mirror (and extend) the SQLAlchemy ORM models in src/backend/models.py
so that LLM-extracted data is validated before reaching the database.
"""

from typing import Optional
from pydantic import BaseModel, Field


class IncomeStatementSchema(BaseModel):
    ticker: str
    fiscal_year: int
    revenue_bln: Optional[float] = None
    gross_profit_bln: Optional[float] = None
    operating_income_bln: Optional[float] = None
    net_income_bln: Optional[float] = None
    eps: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    net_margin_pct: Optional[float] = None


class BalanceSheetSchema(BaseModel):
    ticker: str
    fiscal_year: int
    total_assets_bln: Optional[float] = None
    total_liabilities_bln: Optional[float] = None
    total_equity_bln: Optional[float] = None
    cash_and_equivalents_bln: Optional[float] = None
    total_debt_bln: Optional[float] = None


class CashFlowSchema(BaseModel):
    ticker: str
    fiscal_year: int
    operating_cash_flow_bln: Optional[float] = None
    capital_expenditure_bln: Optional[float] = None
    free_cash_flow_bln: Optional[float] = None
    dividends_paid_bln: Optional[float] = None


class QualitativeInsightSchema(BaseModel):
    ticker: str
    fiscal_year: int
    future_outlook: Optional[str] = None
    key_strategic_events: Optional[str] = None  # JSON-serialised list


class KPISummarySchema(BaseModel):
    ticker: str
    fiscal_year: int
    revenue_bln: Optional[float] = None
    net_income_bln: Optional[float] = None
    eps: Optional[float] = None
    pe_ratio: Optional[float] = None
    roe_pct: Optional[float] = None
    roace_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    dividend_yield_pct: Optional[float] = None


class FinancialReportPayload(BaseModel):
    """Top-level validated envelope produced by the pipeline for one PDF."""

    ticker: str = Field(..., description="Company ticker symbol, e.g. MAYBANK")
    fiscal_year: int = Field(..., description="Fiscal year, e.g. 2024")
    report_period: str = Field(..., description="Quarter/period, e.g. Q3")
    source_pdf: str = Field(..., description="Absolute path to the source PDF")

    income_statement: Optional[IncomeStatementSchema] = None
    balance_sheet: Optional[BalanceSheetSchema] = None
    cash_flow: Optional[CashFlowSchema] = None
    qualitative_insight: Optional[QualitativeInsightSchema] = None
    kpi_summary: Optional[KPISummarySchema] = None
