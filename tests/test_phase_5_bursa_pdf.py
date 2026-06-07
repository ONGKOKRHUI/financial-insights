"""Unit tests for Phase 5 sector peer earnings sentiment."""

from __future__ import annotations

import os
import sys

_SCRAPER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "scraper")
)
if _SCRAPER_DIR not in sys.path:
    sys.path.insert(0, _SCRAPER_DIR)

from ml_features.phase_5_forward_looking import _sector_peer_sentiment, run  # noqa: E402
from ml_features.types import FeaturePayload, FeatureTarget  # noqa: E402


def test_sector_peer_sentiment_averages_rates():
    p = FeaturePayload(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
    p.set_metadata("peer_beat_rates", [0.5, 0.75, 1.0])
    assert abs(_sector_peer_sentiment(p) - 0.75) < 1e-9


def test_sector_peer_sentiment_ignores_none():
    p = FeaturePayload(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
    p.set_metadata("peer_beat_rates", [0.5, None, 1.0])
    assert abs(_sector_peer_sentiment(p) - 0.75) < 1e-9


def test_sector_peer_sentiment_returns_none_when_empty():
    p = FeaturePayload(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
    p.set_metadata("peer_beat_rates", [])
    assert _sector_peer_sentiment(p) is None


def test_sector_peer_sentiment_returns_none_when_missing():
    p = FeaturePayload(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
    assert _sector_peer_sentiment(p) is None


def test_run_sets_sentiment_metric():
    t = FeatureTarget(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
    p = FeaturePayload(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
    p.set_metadata("peer_beat_rates", [0.625, 0.875])
    run(t, p)
    assert abs(p.metrics["sector_peer_earnings_sentiment"] - 0.75) < 1e-9


def test_run_sets_none_without_peer_rates():
    t = FeatureTarget(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
    p = FeaturePayload(ticker="TNB", fiscal_year=2025, fiscal_quarter="Q4")
    run(t, p)
    assert p.metrics["sector_peer_earnings_sentiment"] is None
