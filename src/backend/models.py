from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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


# ---------------------------------------------------------------------------
# Auth & RBAC models (Phase 4)
# ---------------------------------------------------------------------------


class User(Base):
    """Registered user account.

    Roles
    -----
    - ``free``  — basic public data, no API key
    - ``paid``  — full dashboard + 1 API key (granted via Stripe webhook)
    - ``admin`` — all resources + user management dashboard
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="free")
    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RefreshToken(Base):
    """Long-lived refresh token stored as a bcrypt hash.

    Storing only the hash means a database compromise does not expose
    live tokens.  Tokens are single-use: on rotation the old row is
    revoked and a new one is inserted.
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)


class APIKey(Base):
    """Developer API key for programmatic access (paid tier and above).

    Only the SHA-256 hash is persisted; the raw key is returned to the
    user exactly once at creation time and never stored in plain text.
    The ``key_prefix`` (first 8 chars) is stored so users can identify
    their key in the dashboard without revealing the full secret.
    """

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)  # SHA-256 hex digest
    key_prefix = Column(String(10), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked = Column(Boolean, nullable=False, default=False)
