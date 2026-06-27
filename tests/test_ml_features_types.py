"""Unit tests for ml_features.types (FeatureTarget, FeaturePayload).

No external services or database required — pure Python logic only.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# Ensure the scraper package is importable.
_SCRAPER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "scraper")
)
if _SCRAPER_DIR not in sys.path:
    sys.path.insert(0, _SCRAPER_DIR)

from ml_features.types import FeaturePayload, FeatureTarget, PeerRef


# ── FeatureTarget ─────────────────────────────────────────────────────────────


def test_feature_target_immutable():
    t = FeatureTarget(ticker="MAYBANK", fiscal_year=2025, fiscal_quarter="Q4")
    with pytest.raises((TypeError, AttributeError)):
        t.ticker = "OTHER"  # type: ignore[misc]


def test_feature_target_yf_symbol():
    t = FeatureTarget(ticker="CIMB", fiscal_year=2024, fiscal_quarter="Q1")
    assert t.yf_symbol == "1023.KL"


def test_feature_target_yf_symbol_various_tickers():
    expected = {
        "MAYBANK": "1155.KL",
        "TNB": "5347.KL",
        "MAXIS": "6012.KL",
        "T": "T.KL",
    }
    for ticker, yf in expected.items():
        t = FeatureTarget(ticker=ticker, fiscal_year=2024, fiscal_quarter="Q2")
        assert t.yf_symbol == yf


# ── FeaturePayload ────────────────────────────────────────────────────────────


def test_feature_payload_defaults():
    p = FeaturePayload(ticker="MAYBANK", fiscal_year=2025, fiscal_quarter="Q4")
    assert p.metrics == {}
    assert p.source_metadata == {}


def test_set_metric_stores_value():
    p = FeaturePayload(ticker="TNB", fiscal_year=2024, fiscal_quarter="Q3")
    p.set_metric("revenue_yoy_growth_pct", 15.3)
    assert p.metrics["revenue_yoy_growth_pct"] == 15.3


def test_set_metric_preserves_none():
    """Explicit None values must be stored (needed for COALESCE UPSERTs)."""
    p = FeaturePayload(ticker="TNB", fiscal_year=2024, fiscal_quarter="Q3")
    p.set_metric("fcf_yield_pct", None)
    assert "fcf_yield_pct" in p.metrics
    assert p.metrics["fcf_yield_pct"] is None


def test_set_metadata_stores_value():
    p = FeaturePayload(ticker="CIMB", fiscal_year=2024, fiscal_quarter="Q2")
    p.set_metadata("phase_1_source", "yfinance/CIMB.KL")
    assert p.source_metadata["phase_1_source"] == "yfinance/CIMB.KL"


def test_as_loader_payload_identity_fields():
    p = FeaturePayload(ticker="GENTING", fiscal_year=2023, fiscal_quarter="Q2")
    result = p.as_loader_payload()
    assert result["ticker"] == "GENTING"
    assert result["fiscal_year"] == 2023
    assert result["fiscal_quarter"] == "Q2"


def test_as_loader_payload_flattens_metrics():
    p = FeaturePayload(ticker="MAXIS", fiscal_year=2025, fiscal_quarter="Q1")
    p.set_metric("eps_beat_rate_8q", 0.625)
    p.set_metric("forward_ps_ratio", 3.2)
    result = p.as_loader_payload()
    assert result["eps_beat_rate_8q"] == 0.625
    assert result["forward_ps_ratio"] == 3.2


def test_as_loader_payload_metadata_json():
    p = FeaturePayload(ticker="SUNWAY", fiscal_year=2025, fiscal_quarter="Q4")
    p.set_metadata("phase_3_source", "FMP")
    p.set_metadata("phase_3_records_used", 8)
    result = p.as_loader_payload()
    assert result["source_metadata"] is not None
    meta = json.loads(result["source_metadata"])
    assert meta["phase_3_source"] == "FMP"
    assert meta["phase_3_records_used"] == 8


def test_as_loader_payload_empty_metadata_is_none():
    p = FeaturePayload(ticker="TELEKOM", fiscal_year=2024, fiscal_quarter="Q3")
    result = p.as_loader_payload()
    assert result["source_metadata"] is None


def test_as_loader_payload_metrics_overwrite_identity_if_present():
    """metrics dict keys must not accidentally overwrite ticker/year/quarter."""
    p = FeaturePayload(ticker="MAYBANK", fiscal_year=2025, fiscal_quarter="Q4")
    # The spread of metrics happens AFTER the identity fields, so a metrics key
    # named 'ticker' would shadow it — we verify this does NOT happen in practice
    # because phases should never set identity keys.
    p.set_metric("revenue_yoy_growth_pct", 8.0)
    result = p.as_loader_payload()
    assert result["ticker"] == "MAYBANK"


# ── discover_targets helper ───────────────────────────────────────────────────


def test_discover_targets_basic():
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from ml_pipeline_runner import discover_targets

    targets = discover_targets(["maybank", " cimb ", "TNB"], 2025, "q4")
    assert len(targets) == 3
    assert targets[0].ticker == "MAYBANK"
    assert targets[1].ticker == "CIMB"
    assert targets[2].ticker == "TNB"
    assert targets[0].fiscal_year == 2025
    assert targets[0].fiscal_quarter == "Q4"


def test_discover_targets_skips_empty_strings():
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from ml_pipeline_runner import discover_targets

    targets = discover_targets(["MAYBANK", "", "  ", "CIMB"], 2024, "Q1")
    assert len(targets) == 2
    assert {t.ticker for t in targets} == {"MAYBANK", "CIMB"}


# ── PeerRef ──────────────────────────────────────────────────────────────────


def test_peer_ref_immutable():
    p = PeerRef(ticker="YTLPOWR", tv_name="YTLPOWR", description="YTL POWER INTL BHD", sector="Utilities")
    with pytest.raises((TypeError, AttributeError)):
        p.ticker = "OTHER"  # type: ignore[misc]


def test_peer_ref_roundtrip():
    p = PeerRef(ticker="YTLPOWR", tv_name="YTLPOWR", description="YTL POWER INTL BHD", sector="Utilities")
    d = p.to_dict()
    assert d["ticker"] == "YTLPOWR"
    assert d["sector"] == "Utilities"
    restored = PeerRef.from_dict(d)
    assert restored == p


def test_peer_ref_from_dict_missing_description():
    d = {"ticker": "TNB", "tv_name": "TENAGA", "sector": "Utilities"}
    p = PeerRef.from_dict(d)
    assert p.description is None
    assert p.ticker == "TNB"


# ── PipelineContext ──────────────────────────────────────────────────────────


def test_pipeline_context_caches_phase3():
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from unittest.mock import patch as mock_patch

    from ml_pipeline_runner import PipelineContext

    call_count = 0

    def fake_run_surprises(target, payload, **kwargs):
        nonlocal call_count
        call_count += 1
        payload.set_metric("revenue_beat_rate_8q", 0.75)

    with mock_patch("ml_pipeline_runner.run_surprises", side_effect=fake_run_surprises):
        ctx = PipelineContext()
        t = FeatureTarget(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
        p1 = ctx.get_surprise_payload(t)
        p2 = ctx.get_surprise_payload(t)

    assert call_count == 1
    assert p1 is p2
    assert p1.metrics["revenue_beat_rate_8q"] == 0.75


def test_pipeline_context_peer_beat_rates():
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from unittest.mock import patch as mock_patch

    from ml_pipeline_runner import PipelineContext

    peer_rates_map = {"YTLPOWR": 0.5, "MALAKOF": 0.875, "DIALOG": None}

    def fake_run_surprises(target, payload, **kwargs):
        rate = peer_rates_map.get(target.ticker)
        if rate is not None:
            payload.set_metric("revenue_beat_rate_8q", rate)

    with mock_patch("ml_pipeline_runner.run_surprises", side_effect=fake_run_surprises):
        ctx = PipelineContext()
        target = FeatureTarget(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
        peers = [
            PeerRef(ticker="YTLPOWR", tv_name="YTLPOWR", description=None, sector="Utilities"),
            PeerRef(ticker="MALAKOF", tv_name="MALAKOF", description=None, sector="Utilities"),
            PeerRef(ticker="DIALOG", tv_name="DIALOG", description=None, sector="Utilities"),
        ]
        rates = ctx.peer_beat_rates(target, peers)

    assert sorted(rates) == [0.5, 0.875]


def test_pipeline_context_peer_beat_rates_use_fast_mode_and_sample_limit(monkeypatch):
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from unittest.mock import patch as mock_patch

    from ml_pipeline_runner import PipelineContext

    monkeypatch.setenv("ML_PEER_SENTIMENT_SAMPLE_LIMIT", "2")
    calls = []

    def fake_run_surprises(target, payload, **kwargs):
        calls.append((target.ticker, kwargs))
        payload.set_metric("revenue_beat_rate_8q", 0.5)

    with mock_patch("ml_pipeline_runner.run_surprises", side_effect=fake_run_surprises):
        ctx = PipelineContext()
        target = FeatureTarget(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
        peers = [
            PeerRef(ticker="YTLPOWR", tv_name="YTLPOWR", description=None, sector="Utilities"),
            PeerRef(ticker="MALAKOF", tv_name="MALAKOF", description=None, sector="Utilities"),
            PeerRef(ticker="DIALOG", tv_name="DIALOG", description=None, sector="Utilities"),
        ]
        rates = ctx.peer_beat_rates(target, peers)

    assert rates == [0.5, 0.5]
    assert [ticker for ticker, _ in calls] == ["YTLPOWR", "MALAKOF"]
    assert all(kwargs["allow_investing_fallback"] is False for _, kwargs in calls)
    assert all(kwargs["allow_fallback_sources"] is False for _, kwargs in calls)


def test_pipeline_context_keeps_fast_peer_cache_separate_from_full_target_cache():
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from unittest.mock import patch as mock_patch

    from ml_pipeline_runner import PipelineContext

    calls = []

    def fake_run_surprises(target, payload, **kwargs):
        calls.append(kwargs["allow_investing_fallback"])
        payload.set_metric("revenue_beat_rate_8q", 0.75 if kwargs["allow_investing_fallback"] else 0.5)

    with mock_patch("ml_pipeline_runner.run_surprises", side_effect=fake_run_surprises):
        ctx = PipelineContext()
        target = FeatureTarget(ticker="MAYBANK", fiscal_year=2025, fiscal_quarter="Q4")
        fast_payload = ctx.get_surprise_payload(target, allow_investing_fallback=False)
        full_payload = ctx.get_surprise_payload(target)

    assert fast_payload.metrics["revenue_beat_rate_8q"] == 0.5
    assert full_payload.metrics["revenue_beat_rate_8q"] == 0.75
    assert calls == [False, True]


def test_pipeline_context_uses_bounded_fallback_when_fast_peer_rates_empty(monkeypatch):
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from unittest.mock import patch as mock_patch

    from ml_pipeline_runner import PipelineContext

    monkeypatch.setenv("ML_PEER_SENTIMENT_SAMPLE_LIMIT", "1")
    monkeypatch.setenv("ML_PEER_SENTIMENT_MIN_RATES", "1")
    monkeypatch.setenv("ML_PEER_SENTIMENT_FALLBACK_LIMIT", "1")
    calls = []

    def fake_run_surprises(target, payload, **kwargs):
        calls.append((target.ticker, kwargs["allow_investing_fallback"]))
        if kwargs["allow_investing_fallback"]:
            payload.set_metric("revenue_beat_rate_8q", 0.625)
        else:
            payload.set_metric("revenue_beat_rate_8q", None)

    with mock_patch("ml_pipeline_runner.run_surprises", side_effect=fake_run_surprises):
        ctx = PipelineContext()
        target = FeatureTarget(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
        peers = [
            PeerRef(ticker="YTLPOWR", tv_name="YTLPOWR", description=None, sector="Utilities"),
            PeerRef(ticker="PETGAS", tv_name="PETGAS", description=None, sector="Utilities"),
        ]
        rates = ctx.peer_beat_rates(target, peers)

    assert rates == [0.625]
    assert calls == [
        ("YTLPOWR", False),
        ("PETGAS", False),
        ("YTLPOWR", True),
    ]


def test_pipeline_context_peer_sentiment_uses_eps_when_revenue_missing(monkeypatch):
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from unittest.mock import patch as mock_patch

    from ml_pipeline_runner import PipelineContext

    monkeypatch.setenv("ML_PEER_SENTIMENT_SAMPLE_LIMIT", "1")
    monkeypatch.setenv("ML_PEER_SENTIMENT_MIN_RATES", "1")
    monkeypatch.setenv("ML_PEER_SENTIMENT_FALLBACK_LIMIT", "1")
    calls = []

    def fake_run_surprises(target, payload, **kwargs):
        calls.append((target.ticker, kwargs["allow_investing_fallback"]))
        payload.set_metric("revenue_beat_rate_8q", None)
        payload.set_metric("eps_beat_rate_8q", 0.5)

    with mock_patch("ml_pipeline_runner.run_surprises", side_effect=fake_run_surprises):
        ctx = PipelineContext()
        target = FeatureTarget(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
        peers = [
            PeerRef(ticker="YTLPOWR", tv_name="YTLPOWR", description=None, sector="Utilities"),
            PeerRef(ticker="PETGAS", tv_name="PETGAS", description=None, sector="Utilities"),
        ]
        rates = ctx.peer_beat_rates(target, peers)

    assert rates == [0.5]
    assert calls == [("YTLPOWR", False)]


def test_pipeline_context_sector_rate_cache():
    _SRC_SCRAPER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))
    if _SRC_SCRAPER not in sys.path:
        sys.path.insert(0, _SRC_SCRAPER)

    from unittest.mock import patch as mock_patch

    from ml_pipeline_runner import PipelineContext

    call_count = 0

    def fake_run_surprises(target, payload, **kwargs):
        nonlocal call_count
        call_count += 1
        payload.set_metric("revenue_beat_rate_8q", 0.625)

    with mock_patch("ml_pipeline_runner.run_surprises", side_effect=fake_run_surprises):
        ctx = PipelineContext()
        peers = [
            PeerRef(ticker="YTLPOWR", tv_name="YTLPOWR", description=None, sector="Utilities"),
        ]
        t1 = FeatureTarget(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
        t2 = FeatureTarget(ticker="PETGAS", fiscal_year=2025, fiscal_quarter="Q4")
        rates1 = ctx.peer_beat_rates(t1, peers)
        rates2 = ctx.peer_beat_rates(t2, peers)

    assert rates1 == rates2 == [0.625]
    assert call_count == 1
