"""Phase 5 – Forward-Looking (metric 21).

Metric computed
---------------
21. sector_peer_earnings_sentiment — Avg beat rate of sector peers (0-1)

The pipeline runner populates ``payload.source_metadata["peer_beat_rates"]``
with revenue beat rates from dynamically discovered TradingView sector peers
(via Phase 2) before calling this phase.
"""
from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import FeaturePayload, FeatureTarget

logger = logging.getLogger(__name__)


def _sector_peer_sentiment(payload: "FeaturePayload") -> float | None:
    """Average the peer beat rates supplied by the runner."""
    peer_rates = payload.source_metadata.get("peer_beat_rates")
    if peer_rates and isinstance(peer_rates, list) and len(peer_rates) > 0:
        try:
            return statistics.mean([r for r in peer_rates if r is not None])
        except statistics.StatisticsError:
            return None
    return None


def run(target: "FeatureTarget", payload: "FeaturePayload") -> None:
    """Compute metric 21 (sector peer earnings sentiment)."""
    logger.info("Phase 5 – computing sector peer sentiment for %s", target.ticker)
    payload.set_metric("sector_peer_earnings_sentiment", _sector_peer_sentiment(payload))
