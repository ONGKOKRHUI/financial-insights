"""ML Feature Pipeline Runner.

Executes the five-phase ML feature ingestion pipeline for one or more
(ticker, fiscal_year, fiscal_quarter) targets and optionally persists the
results to the ``predictive_features`` PostgreSQL table.

Usage
-----
    # Run against the latest completed quarter for all default tickers:
    python ml_pipeline_runner.py

    # Specific tickers / period:
    python ml_pipeline_runner.py \\
        --tickers MAYBANK,CIMB,MAXIS \\
        --fiscal-year 2025 \\
        --fiscal-quarter Q4

    # Inspect payloads without writing to the database:
    python ml_pipeline_runner.py --dry-run

Environment variables
---------------------
    DATABASE_URL         SQLAlchemy URL (default: localhost finsight)
    ML_FEATURE_TICKERS   Comma-separated list of KLSE tickers
    ML_FEATURE_YEAR      Fiscal year (default: 2025)
    ML_FEATURE_QUARTER   Fiscal quarter (default: Q4)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

# ── Path bootstrap ──────────────────────────────────────────────────────────
SCRAPER_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRAPER_DIR.parent
REPO_DIR = SRC_DIR.parent
BACKEND_DIR = SRC_DIR / "backend"

# Load .env from repo root so FINSIGHT_RAW_DIR and other vars are available
# when running the script directly (outside Docker / direnv).
try:
    from dotenv import load_dotenv
    _env_file = REPO_DIR / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
except ImportError:
    pass

for _path in (SRC_DIR, SCRAPER_DIR, BACKEND_DIR):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

# ── Deferred imports (after sys.path is set) ────────────────────────────────
from db.loader import upsert_predictive_features  # noqa: E402
from ml_features.phase_1_fundamentals import run as run_fundamentals  # noqa: E402
from ml_features.phase_2_valuation import run as run_valuation  # noqa: E402
from ml_features.phase_3_surprises import run as run_surprises  # noqa: E402
from ml_features.phase_4_money_flow import run as run_money_flow  # noqa: E402
from ml_features.phase_5_forward_looking import run as run_forward_looking  # noqa: E402
from ml_features.types import FeaturePayload, FeatureTarget, PeerRef  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_TICKERS = (
    "MAYBANK", "CIMB", "SUNWAY", "GENTING", "TELEKOM", "MAXIS", "TNB",
)
DEFAULT_PEER_SENTIMENT_SAMPLE_LIMIT = 10
DEFAULT_PEER_SENTIMENT_MIN_RATES = 1
DEFAULT_PEER_SENTIMENT_FALLBACK_LIMIT = 2


def _positive_int_env(name: str, default: int) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid %s=%r; using default %d",
            name,
            raw,
            default,
        )
        return default
    return value if value > 0 else None


def _peer_sentiment_sample_limit() -> int | None:
    return _positive_int_env(
        "ML_PEER_SENTIMENT_SAMPLE_LIMIT",
        DEFAULT_PEER_SENTIMENT_SAMPLE_LIMIT,
    )


def _peer_sentiment_min_rates() -> int | None:
    return _positive_int_env(
        "ML_PEER_SENTIMENT_MIN_RATES",
        DEFAULT_PEER_SENTIMENT_MIN_RATES,
    )


def _peer_sentiment_fallback_limit() -> int | None:
    return _positive_int_env(
        "ML_PEER_SENTIMENT_FALLBACK_LIMIT",
        DEFAULT_PEER_SENTIMENT_FALLBACK_LIMIT,
    )

# ── Public API ──────────────────────────────────────────────────────────────

def discover_targets(
    tickers: Iterable[str],
    fiscal_year: int,
    fiscal_quarter: str,
) -> list[FeatureTarget]:
    """Build a ``FeatureTarget`` list from raw ticker strings."""
    return [
        FeatureTarget(
            ticker=ticker.strip().upper(),
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter.upper(),
        )
        for ticker in tickers
        if ticker.strip()
    ]


class PipelineContext:
    """Cross-target cache for Phase 3 earnings data and sector peer rates.

    Ensures each peer ticker is scraped at most once, and multiple targets
    sharing a sector reuse the same peer beat-rate list.
    """

    def __init__(self) -> None:
        self._phase3_cache: dict[tuple[str, int, str, bool], FeaturePayload] = {}
        self._sector_rate_cache: dict[tuple[str, int, str], list[float]] = {}

    def get_surprise_payload(
        self,
        target: FeatureTarget,
        *,
        description: str | None = None,
        allow_investing_fallback: bool = True,
    ) -> FeaturePayload:
        """Run Phase 3 for *target* (cached; at most one network fetch per ticker/period).

        *description* is forwarded to Investing.com for dynamic slug resolution
        when the ticker lacks a static slug mapping.
        """
        key = (
            target.ticker,
            target.fiscal_year,
            target.fiscal_quarter,
            allow_investing_fallback,
        )
        if key not in self._phase3_cache:
            payload = FeaturePayload(
                ticker=target.ticker,
                fiscal_year=target.fiscal_year,
                fiscal_quarter=target.fiscal_quarter,
            )
            run_surprises(
                target,
                payload,
                allow_investing=True,
                allow_investing_fallback=allow_investing_fallback,
                allow_fallback_sources=allow_investing_fallback,
                description=description,
            )
            self._phase3_cache[key] = payload
        return self._phase3_cache[key]

    def peer_beat_rates(
        self,
        target: FeatureTarget,
        peers: list[PeerRef],
    ) -> list[float]:
        """Return best available earnings beat rates for sector peers.

        Results are cached by (sector, year, quarter) so targets in the same
        sector share a single set of peer fetches.
        """
        if not peers:
            return []
        sector = peers[0].sector
        sector_key = (sector, target.fiscal_year, target.fiscal_quarter)
        if sector_key in self._sector_rate_cache:
            return self._sector_rate_cache[sector_key]

        sample_limit = _peer_sentiment_sample_limit()
        min_rates = _peer_sentiment_min_rates()
        fallback_limit = _peer_sentiment_fallback_limit()
        rates: list[float] = []
        peers_without_fast_rate: list[PeerRef] = []

        for peer in peers:
            peer_target = FeatureTarget(
                ticker=peer.ticker,
                fiscal_year=target.fiscal_year,
                fiscal_quarter=target.fiscal_quarter,
            )
            try:
                payload = self.get_surprise_payload(
                    peer_target,
                    description=peer.description,
                    allow_investing_fallback=False,
                )
                rate = _peer_sentiment_rate(payload)
                if rate is not None:
                    rates.append(rate)
                    if sample_limit is not None and len(rates) >= sample_limit:
                        logger.info(
                            "Phase 3 peer sentiment: reached sample limit of %d for %s",
                            sample_limit,
                            sector,
                        )
                        break
                else:
                    peers_without_fast_rate.append(peer)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Phase 3 failed for peer %s: %s", peer.ticker, exc,
                )
                peers_without_fast_rate.append(peer)

        needs_more_rates = min_rates is not None and len(rates) < min_rates
        if needs_more_rates and peers_without_fast_rate and fallback_limit != 0:
            max_fallbacks = (
                len(peers_without_fast_rate)
                if fallback_limit is None
                else min(fallback_limit, len(peers_without_fast_rate))
            )
            logger.info(
                "Phase 3 peer sentiment: fast pass produced %d rate(s) for %s; "
                "trying full fallback for up to %d peer(s)",
                len(rates),
                sector,
                max_fallbacks,
            )
            for peer in peers_without_fast_rate[:max_fallbacks]:
                peer_target = FeatureTarget(
                    ticker=peer.ticker,
                    fiscal_year=target.fiscal_year,
                    fiscal_quarter=target.fiscal_quarter,
                )
                try:
                    payload = self.get_surprise_payload(
                        peer_target,
                        description=peer.description,
                        allow_investing_fallback=True,
                    )
                    rate = _peer_sentiment_rate(payload)
                    if rate is not None:
                        rates.append(rate)
                        if min_rates is not None and len(rates) >= min_rates:
                            break
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Phase 3 fallback failed for peer %s: %s", peer.ticker, exc,
                    )

        self._sector_rate_cache[sector_key] = rates
        return rates


def _apply_prefetched_phase3(payload: FeaturePayload, prefetched: FeaturePayload) -> None:
    """Copy Phase 3 metrics and provenance from an earlier batch pass."""
    for key, value in prefetched.metrics.items():
        payload.set_metric(key, value)
    for key, value in prefetched.source_metadata.items():
        if key.startswith("phase_3"):
            payload.set_metadata(key, value)


def _peer_sentiment_rate(payload: FeaturePayload) -> float | None:
    """Use revenue beat rate when available, otherwise EPS beat rate."""
    for metric in ("revenue_beat_rate_8q", "eps_beat_rate_8q"):
        rate = payload.metrics.get(metric)
        if rate is not None:
            return float(rate)
    return None


def run_for_target(
    target: FeatureTarget,
    *,
    context: PipelineContext,
    persist: bool = True,
) -> dict:
    """Run all five phases for a single target and return the payload dict.

    After Phase 2, the runner reads the dynamically discovered sector peers
    from metadata and fetches their earnings via the shared ``context``,
    populating ``peer_beat_rates`` before Phase 5 computes sentiment.
    """
    payload = FeaturePayload(
        ticker=target.ticker,
        fiscal_year=target.fiscal_year,
        fiscal_quarter=target.fiscal_quarter,
    )

    def _safe(name: str, fn, *args) -> None:
        try:
            fn(*args)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Phase %s failed for %s FY%s %s: %s",
                name, target.ticker, target.fiscal_year, target.fiscal_quarter, exc,
            )
            payload.set_metadata(f"{name}_fatal_error", str(exc))

    _safe("fundamentals", run_fundamentals, target, payload)
    _safe("valuation", run_valuation, target, payload)

    # Bridge Phase 2 peer discovery -> Phase 3 earnings for sector sentiment.
    peers = [
        PeerRef.from_dict(d)
        for d in payload.source_metadata.get("phase_2_peer_refs", [])
    ]
    peer_rates = context.peer_beat_rates(target, peers)
    payload.set_metadata("peer_beat_rates", peer_rates)
    payload.set_metadata(
        "peer_beat_rate_source",
        "TradingView sector peers + Phase 3 cache (revenue beat, EPS fallback)",
    )
    payload.set_metadata("peer_beat_rate_count", len(peer_rates))

    # Phase 3 for the target itself (cached; may already exist from a peer run).
    try:
        own_phase3 = context.get_surprise_payload(target)
        _apply_prefetched_phase3(payload, own_phase3)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Phase surprises failed for %s FY%s %s: %s",
            target.ticker, target.fiscal_year, target.fiscal_quarter, exc,
        )
        payload.set_metadata("surprises_fatal_error", str(exc))

    _safe("money_flow", run_money_flow, target, payload)
    _safe("forward_looking", run_forward_looking, target, payload)

    result = payload.as_loader_payload()

    if persist:
        try:
            upsert_predictive_features(result)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "DB upsert failed for %s FY%s %s: %s",
                target.ticker, target.fiscal_year, target.fiscal_quarter, exc,
            )
            raise

    return result


def run_pipeline(
    targets: Iterable[FeatureTarget],
    *,
    persist: bool = True,
) -> list[dict]:
    """Run the full pipeline for every target and return a list of payload dicts.

    A shared ``PipelineContext`` caches Phase 3 earnings data across targets
    so that dynamically discovered sector peers (from Phase 2's TradingView
    screener) are fetched at most once.
    """
    target_list = list(targets)
    if not target_list:
        logger.info("run_pipeline: no targets to process")
        return []

    context = PipelineContext()
    results: list[dict] = []
    for target in target_list:
        logger.info(
            "ML pipeline: processing %s FY%s %s",
            target.ticker, target.fiscal_year, target.fiscal_quarter,
        )
        result = run_for_target(target, context=context, persist=persist)
        results.append(result)

    logger.info("run_pipeline: completed %d target(s)", len(results))
    return results


# ── CLI entry point ─────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the predictive ML feature ingestion pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tickers",
        default=os.getenv("ML_FEATURE_TICKERS", ",".join(DEFAULT_TICKERS)),
        help="Comma-separated KLSE tickers",
    )
    parser.add_argument(
        "--fiscal-year",
        type=int,
        default=int(os.getenv("ML_FEATURE_YEAR", "2025")),
        help="Fiscal year to process",
    )
    parser.add_argument(
        "--fiscal-quarter",
        default=os.getenv("ML_FEATURE_QUARTER", "Q4"),
        help="Fiscal quarter (Q1-Q4)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all phases but skip the database UPSERT",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    args = _parse_args()
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    targets = discover_targets(tickers, args.fiscal_year, args.fiscal_quarter)
    results = run_pipeline(targets, persist=not args.dry_run)
    logger.info("Completed: %d payload(s) processed", len(results))
    if args.dry_run:
        import json
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
