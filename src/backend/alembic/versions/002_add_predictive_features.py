"""Add predictive_features table for ML training metrics

Revision ID: 002
Revises: 001
Create Date: 2026-05-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create predictive_features table with all 21 ML metric columns."""
    op.create_table(
        "predictive_features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.String(length=2), nullable=False),

        # Phase 3: Earning surprises — metrics 1-5
        sa.Column("revenue_beat_rate_8q", sa.Float(), nullable=True),
        sa.Column("eps_beat_rate_8q", sa.Float(), nullable=True),
        sa.Column("avg_revenue_surprise_pct", sa.Float(), nullable=True),
        sa.Column("avg_eps_surprise_pct", sa.Float(), nullable=True),
        sa.Column("consecutive_double_beat_quarters", sa.Integer(), nullable=True),

        # Phase 4: Money flow — metrics 6-9
        sa.Column("net_institutional_cash_flow_myr", sa.Float(), nullable=True),
        sa.Column("institutional_flow_to_market_cap_ratio", sa.Float(), nullable=True),
        sa.Column("net_insider_trading_value_myr", sa.Float(), nullable=True),
        sa.Column("options_iv_rank_pct", sa.Float(), nullable=True),

        # Phase 1: Fundamentals — metrics 10-14
        sa.Column("revenue_yoy_growth_pct", sa.Float(), nullable=True),
        sa.Column("net_income_yoy_growth_pct", sa.Float(), nullable=True),
        sa.Column("gross_margin_delta_qoq_pct", sa.Float(), nullable=True),
        sa.Column("operating_margin_delta_qoq_pct", sa.Float(), nullable=True),
        sa.Column("fcf_yield_pct", sa.Float(), nullable=True),

        # Phase 2: Valuation — metrics 15-18
        sa.Column("forward_pe_peer_zscore", sa.Float(), nullable=True),
        sa.Column("forward_pe_peer_discount_pct", sa.Float(), nullable=True),
        sa.Column("forward_ps_ratio", sa.Float(), nullable=True),
        sa.Column("peg_ratio", sa.Float(), nullable=True),

        # Phase 5: Forward-looking — metrics 19-21
        sa.Column("guidance_beat_indicator", sa.Boolean(), nullable=True),
        sa.Column("backlog_order_book_yoy_growth_pct", sa.Float(), nullable=True),
        sa.Column("sector_peer_earnings_sentiment", sa.Float(), nullable=True),

        # Audit columns
        sa.Column("source_metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),

        sa.ForeignKeyConstraint(["ticker"], ["companies.ticker"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker", "fiscal_year", "fiscal_quarter",
            name="uq_predictive_features_ticker_period",
        ),
    )
    op.create_index("ix_predictive_features_id", "predictive_features", ["id"])
    op.create_index("ix_predictive_features_ticker", "predictive_features", ["ticker"])


def downgrade() -> None:
    """Drop the predictive_features table."""
    op.drop_index("ix_predictive_features_ticker", table_name="predictive_features")
    op.drop_index("ix_predictive_features_id", table_name="predictive_features")
    op.drop_table("predictive_features")
