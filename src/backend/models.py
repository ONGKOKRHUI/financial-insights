from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, UniqueConstraint
from database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    sector = Column(String(100))
    industry = Column(String(100))
    description = Column(Text)
    market_cap_bln = Column(Float)
    employees = Column(Integer)
    founded = Column(Integer)
    headquarters = Column(String(200))
    website = Column(String(300))
    currency = Column(String(10), default="MYR")
    exchange = Column(String(50), default="KLSE")


class KPISummary(Base):
    __tablename__ = "kpi_summaries"
    __table_args__ = (UniqueConstraint("ticker", "fiscal_year"),)

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), ForeignKey("companies.ticker"), index=True, nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    revenue_bln = Column(Float)
    net_income_bln = Column(Float)
    eps = Column(Float)
    pe_ratio = Column(Float, nullable=True)
    roe_pct = Column(Float)
    roace_pct = Column(Float, nullable=True)
    debt_to_equity = Column(Float)
    dividend_yield_pct = Column(Float, nullable=True)


class IncomeStatement(Base):
    __tablename__ = "income_statements"
    __table_args__ = (UniqueConstraint("ticker", "fiscal_year"),)

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), ForeignKey("companies.ticker"), index=True, nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    revenue_bln = Column(Float)
    gross_profit_bln = Column(Float)
    operating_income_bln = Column(Float)
    net_income_bln = Column(Float)
    eps = Column(Float)
    gross_margin_pct = Column(Float)
    operating_margin_pct = Column(Float)
    net_margin_pct = Column(Float)


class BalanceSheet(Base):
    __tablename__ = "balance_sheets"
    __table_args__ = (UniqueConstraint("ticker", "fiscal_year"),)

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), ForeignKey("companies.ticker"), index=True, nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    total_assets_bln = Column(Float)
    total_liabilities_bln = Column(Float)
    total_equity_bln = Column(Float)
    cash_and_equivalents_bln = Column(Float)
    total_debt_bln = Column(Float)


class CashFlow(Base):
    __tablename__ = "cash_flows"
    __table_args__ = (UniqueConstraint("ticker", "fiscal_year"),)

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), ForeignKey("companies.ticker"), index=True, nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    operating_cash_flow_bln = Column(Float)
    capital_expenditure_bln = Column(Float)
    free_cash_flow_bln = Column(Float)
    dividends_paid_bln = Column(Float)


class QualitativeInsight(Base):
    __tablename__ = "qualitative_insights"
    __table_args__ = (UniqueConstraint("ticker", "fiscal_year"),)

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), ForeignKey("companies.ticker"), index=True, nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    future_outlook = Column(Text)
    key_strategic_events = Column(Text)  # stored as JSON string
