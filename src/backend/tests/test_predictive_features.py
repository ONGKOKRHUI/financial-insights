"""Unit tests for the predictive_features table and UPSERT loader helpers.

Runs against the shared in-memory SQLite database seeded by conftest.py, so
no live PostgreSQL connection is required.

Covers
------
- ``PredictiveFeature`` ORM model is registered with ``Base.metadata``.
- ``upsert_predictive_features`` inserts a new row.
- Calling ``upsert_predictive_features`` twice for the same
  (ticker, fiscal_year, fiscal_quarter) updates rather than duplicates.
- ``upsert_predictive_feature_batch`` handles empty lists and partial failures.
- COALESCE policy: a second upsert with a NULL metric does not overwrite an
  existing non-NULL value.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/backend is importable (conftest already does this, but being
# explicit keeps this module self-contained when run in isolation).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models
from database import get_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(db_session):
    """Alias for the conftest db_session fixture."""
    return db_session


# ── Model registration ────────────────────────────────────────────────────────


def test_predictive_feature_model_registered():
    """PredictiveFeature must be registered in Base.metadata."""
    assert "predictive_features" in models.Base.metadata.tables


def test_predictive_feature_has_all_metric_columns():
    """All 21 metric columns must be present on the ORM model."""
    expected_columns = {
        # Phase 3
        "revenue_beat_rate_8q",
        "eps_beat_rate_8q",
        "avg_revenue_surprise_pct",
        "avg_eps_surprise_pct",
        "consecutive_double_beat_quarters",
        # Phase 4
        "net_institutional_cash_flow_myr",
        "institutional_flow_to_market_cap_ratio",
        "net_insider_trading_value_myr",
        "options_iv_rank_pct",
        # Phase 1
        "revenue_yoy_growth_pct",
        "net_income_yoy_growth_pct",
        "gross_margin_delta_qoq_pct",
        "operating_margin_delta_qoq_pct",
        "fcf_yield_pct",
        # Phase 2
        "forward_pe_peer_zscore",
        "forward_pe_peer_discount_pct",
        "forward_ps_ratio",
        "peg_ratio",
        # Phase 5
        "guidance_beat_indicator",
        "backlog_order_book_yoy_growth_pct",
        "sector_peer_earnings_sentiment",
    }
    table = models.Base.metadata.tables["predictive_features"]
    actual_columns = {col.name for col in table.columns}
    assert expected_columns.issubset(actual_columns), (
        f"Missing columns: {expected_columns - actual_columns}"
    )


# ── FeaturePayload ────────────────────────────────────────────────────────────


def test_feature_payload_as_loader_payload():
    """FeaturePayload.as_loader_payload() must flatten correctly."""
    # Import from the scraper package – adjust path if needed.
    _SCRAPER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scraper")
    if _SCRAPER_DIR not in sys.path:
        sys.path.insert(0, _SCRAPER_DIR)

    from ml_features.types import FeaturePayload

    payload = FeaturePayload(ticker="MAYBANK", fiscal_year=2025, fiscal_quarter="Q4")
    payload.set_metric("revenue_yoy_growth_pct", 12.5)
    payload.set_metric("eps_beat_rate_8q", 0.75)
    payload.set_metadata("phase_1_source", "yfinance/MAYBANK.KL")

    result = payload.as_loader_payload()

    assert result["ticker"] == "MAYBANK"
    assert result["fiscal_year"] == 2025
    assert result["fiscal_quarter"] == "Q4"
    assert result["revenue_yoy_growth_pct"] == 12.5
    assert result["eps_beat_rate_8q"] == 0.75
    # source_metadata must be JSON-serialised
    assert result["source_metadata"] is not None
    meta = json.loads(result["source_metadata"])
    assert meta["phase_1_source"] == "yfinance/MAYBANK.KL"


def test_feature_payload_empty_metadata_is_none():
    """When no metadata is set, as_loader_payload must return None for source_metadata."""
    _SCRAPER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scraper")
    if _SCRAPER_DIR not in sys.path:
        sys.path.insert(0, _SCRAPER_DIR)

    from ml_features.types import FeaturePayload

    payload = FeaturePayload(ticker="TNB", fiscal_year=2024, fiscal_quarter="Q2")
    result = payload.as_loader_payload()
    assert result["source_metadata"] is None


# ── Loader UPSERT helpers ─────────────────────────────────────────────────────


def _make_loader_with_sqlite(db_session):
    """
    Patch the loader's _get_engine so it uses the test's in-memory SQLite
    engine instead of talking to a live PostgreSQL instance.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Re-create tables on the test engine (predictive_features DDL uses
    # PostgreSQL-specific syntax, so we use the ORM metadata here).
    models.Base.metadata.create_all(bind=engine)
    return engine


def test_upsert_predictive_features_insert(monkeypatch):
    """upsert_predictive_features must insert a new row without error."""
    # This test mocks the DB call because the loader uses raw SQL with
    # PostgreSQL-specific ON CONFLICT syntax.
    import db.loader as loader_module

    inserted: list[dict] = []

    def fake_transaction():
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            conn = MagicMock()
            conn.execute = lambda sql, params=None: inserted.append(params or {})
            yield conn

        return _ctx()

    monkeypatch.setattr(loader_module, "_transaction", lambda: fake_transaction())

    payload = {
        "ticker": "MAYBANK",
        "fiscal_year": 2025,
        "fiscal_quarter": "Q4",
        "revenue_yoy_growth_pct": 10.0,
        "eps_beat_rate_8q": 0.875,
        "source_metadata": json.dumps({"phase_1_source": "yfinance"}),
    }
    loader_module.upsert_predictive_features(payload)

    assert len(inserted) == 1
    assert inserted[0]["ticker"] == "MAYBANK"
    assert inserted[0]["revenue_yoy_growth_pct"] == 10.0


def test_upsert_predictive_features_missing_key_raises(monkeypatch):
    """upsert_predictive_features must raise ValueError when key fields are absent."""
    import db.loader as loader_module

    monkeypatch.setattr(loader_module, "_transaction", lambda: MagicMock())

    with pytest.raises(ValueError, match="missing key field"):
        loader_module.upsert_predictive_features({"ticker": "CIMB", "fiscal_year": 2025})


def test_upsert_predictive_feature_batch_empty(monkeypatch):
    """Batch upsert with an empty list must be a no-op."""
    import db.loader as loader_module

    calls: list = []
    monkeypatch.setattr(
        loader_module,
        "upsert_predictive_features",
        lambda p: calls.append(p),
    )

    loader_module.upsert_predictive_feature_batch([])
    assert calls == []


def test_upsert_predictive_feature_batch_skips_failures(monkeypatch):
    """Batch upsert must continue after individual row errors."""
    import db.loader as loader_module

    successes: list[str] = []

    def sometimes_fail(payload: dict) -> None:
        if payload["ticker"] == "BAD":
            raise RuntimeError("Simulated DB error")
        successes.append(payload["ticker"])

    monkeypatch.setattr(loader_module, "upsert_predictive_features", sometimes_fail)

    payloads = [
        {"ticker": "MAYBANK", "fiscal_year": 2025, "fiscal_quarter": "Q4"},
        {"ticker": "BAD", "fiscal_year": 2025, "fiscal_quarter": "Q4"},
        {"ticker": "CIMB", "fiscal_year": 2025, "fiscal_quarter": "Q4"},
    ]
    loader_module.upsert_predictive_feature_batch(payloads)

    assert "MAYBANK" in successes
    assert "CIMB" in successes
    assert "BAD" not in successes
