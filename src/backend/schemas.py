from pydantic import BaseModel
from typing import Optional


class CompanySummary(BaseModel):
    ticker: str
    name: str
    sector: str
    market_cap_bln: float
    currency: str = "MYR"


class CompanyDetail(BaseModel):
    ticker: str
    name: str
    sector: str
    industry: str
    description: str
    market_cap_bln: float
    employees: int
    founded: int
    headquarters: str
    website: str
    currency: str = "MYR"
    exchange: str = "KLSE"


class KPISummary(BaseModel):
    ticker: str
    revenue_bln: float
    net_income_bln: float
    eps: float
    pe_ratio: Optional[float]
    roe_pct: float
    roace_pct: Optional[float]
    debt_to_equity: float
    dividend_yield_pct: Optional[float]
    fiscal_year: int


class IncomeStatementEntry(BaseModel):
    fiscal_year: int
    revenue_bln: Optional[float] = None
    gross_profit_bln: Optional[float] = None
    operating_income_bln: Optional[float] = None
    net_income_bln: Optional[float] = None
    eps: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    net_margin_pct: Optional[float] = None


class IncomeStatementResponse(BaseModel):
    ticker: str
    name: str
    currency: str
    data: list[IncomeStatementEntry]


class BalanceSheetEntry(BaseModel):
    fiscal_year: int
    total_assets_bln: float
    total_liabilities_bln: float
    total_equity_bln: float
    cash_and_equivalents_bln: float
    total_debt_bln: float


class BalanceSheetResponse(BaseModel):
    ticker: str
    name: str
    currency: str
    data: list[BalanceSheetEntry]


class CashFlowEntry(BaseModel):
    fiscal_year: int
    operating_cash_flow_bln: float
    capital_expenditure_bln: float
    free_cash_flow_bln: float
    dividends_paid_bln: float


class CashFlowResponse(BaseModel):
    ticker: str
    name: str
    currency: str
    data: list[CashFlowEntry]


class QualitativeInsight(BaseModel):
    ticker: str
    fiscal_year: int
    future_outlook: str
    key_strategic_events: list[str]
