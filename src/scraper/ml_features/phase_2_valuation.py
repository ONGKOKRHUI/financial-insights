"""Phase 2 – Valuation (metrics 15-18).

Sources
-------
- yfinance: market cap, trailing/forward PE, TTM revenue, PEG ratio.
- TradingView Screener API: dynamic sector peer discovery for PE comparison.

Peer discovery (dynamic via TradingView)
-----------------------------------------
1. Convert the pipeline ticker to a TradingView stock name (e.g. TNB -> TENAGA).
2. Query the TradingView Malaysia screener for that stock's sector.
3. Fetch all liquid KLSE stocks (market cap > 1 B MYR) in that sector with a
   valid trailing PE in (0, 100].  Results are cached by sector for the
   process lifetime, so CIMB reuses MAYBANK's Finance sector response.
4. Exclude the target itself and compute z-score / discount vs the peer group.

Because TradingView does not expose forward PE for most KLSE stocks, the peer
comparison uses *trailing PE* (``price_earnings_ttm``) consistently for both
target and peers.  Metadata records ``phase_2_pe_type = "trailing/TTM"``
so callers know which P/E was used.

Metrics computed
----------------
15. forward_pe_peer_zscore       — z-score of trailing PE vs sector peers
16. forward_pe_peer_discount_pct — % discount of trailing PE vs sector mean
17. forward_ps_ratio             — Market Cap / TTM Revenue
18. peg_ratio                    — yfinance pegRatio
"""
from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING, NamedTuple

from .types import PeerRef

if TYPE_CHECKING:
    from .types import FeaturePayload, FeatureTarget

logger = logging.getLogger(__name__)

# ── TradingView screener ─────────────────────────────────────────────────────
_TV_SCAN_URL = "https://scanner.tradingview.com/malaysia/scan"
_TV_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}

# Pipeline canonical ticker → TradingView stock name, only where they differ.
# Most pipeline tickers match TradingView names exactly; these are the exceptions.
_TV_NAME_OVERRIDES: dict[str, str] = {
    "TNB": "TENAGA",
    "TELEKOM": "TM",
}

class _SectorStock(NamedTuple):
    tv_name: str
    pe_ttm: float
    description: str | None = None


_TV_NAME_REVERSE: dict[str, str] = {v: k for k, v in _TV_NAME_OVERRIDES.items()}

# Process-lifetime caches.
_tv_sector_cache: dict[str, list[_SectorStock]] = {}
_tv_stock_sector_cache: dict[str, str | None] = {}


def _to_tv_name(pipeline_ticker: str) -> str:
    """Return the TradingView KLSE stock name for a pipeline ticker."""
    return _TV_NAME_OVERRIDES.get(pipeline_ticker.upper(), pipeline_ticker.upper())


def _from_tv_name(tv_name: str) -> str:
    """Return the pipeline ticker for a TradingView stock name."""
    return _TV_NAME_REVERSE.get(tv_name, tv_name)


def _tv_post(payload: dict) -> dict:
    """POST to the TradingView Malaysia screener and return parsed JSON."""
    import requests

    resp = requests.post(_TV_SCAN_URL, json=payload, headers=_TV_HEADERS, timeout=12)
    resp.raise_for_status()
    return resp.json()


def _tv_get_sector(tv_name: str) -> str | None:
    """Return the TradingView sector for a KLSE stock (cached per stock)."""
    if tv_name in _tv_stock_sector_cache:
        return _tv_stock_sector_cache[tv_name]

    sector: str | None = None
    try:
        data = _tv_post({
            "filter": [{"left": "name", "operation": "equal", "right": tv_name}],
            "options": {"lang": "en"},
            "columns": ["name", "sector"],
            "range": [0, 1],
        })
        rows = data.get("data") or []
        if rows:
            sector = rows[0]["d"][1]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase 2: TradingView sector lookup failed for %s: %s", tv_name, exc)

    _tv_stock_sector_cache[tv_name] = sector
    return sector


def _tv_fetch_sector_pes(
    sector: str,
    min_mcap: float = 1_000_000_000,
    max_pe: float = 100.0,
) -> list[_SectorStock]:
    """
    Fetch sector stocks with PE and description for all liquid KLSE stocks in *sector*.

    Cached by sector name so multiple tickers in the same sector share one API call.
    Filters applied:
    - market_cap_basic > min_mcap  (default 1 B MYR -- excludes illiquid small caps)
    - 0 < price_earnings_ttm < max_pe  (excludes loss-making stocks and outliers)
    """
    if sector in _tv_sector_cache:
        return _tv_sector_cache[sector]

    result: list[_SectorStock] = []
    try:
        data = _tv_post({
            "filter": [
                {"left": "sector",             "operation": "equal",   "right": sector},
                {"left": "market_cap_basic",   "operation": "greater", "right": min_mcap},
                {"left": "price_earnings_ttm", "operation": "greater", "right": 0},
                {"left": "price_earnings_ttm", "operation": "less",    "right": max_pe},
            ],
            "options": {"lang": "en"},
            "columns": ["name", "price_earnings_ttm", "description"],
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
            "range": [0, 50],
        })
        rows = data.get("data") or []
        result = [
            _SectorStock(
                tv_name=str(row["d"][0]),
                pe_ttm=float(row["d"][1]),
                description=str(row["d"][2]) if len(row["d"]) > 2 and row["d"][2] else None,
            )
            for row in rows
            if row["d"][1] is not None
        ]
        logger.info(
            "Phase 2: TradingView sector '%s' → %d stocks with PE",
            sector,
            len(result),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Phase 2: TradingView sector peers failed for '%s': %s", sector, exc
        )

    _tv_sector_cache[sector] = result
    return result


def _tv_peer_pes(tv_name: str, sector: str | None) -> list[float]:
    """Return trailing PE values for same-sector peers, excluding the target."""
    if not sector:
        return []
    return [s.pe_ttm for s in _tv_fetch_sector_pes(sector) if s.tv_name != tv_name]


def discover_sector_peers(target: "FeatureTarget") -> list[PeerRef]:
    """Return identity-rich peer references for same-sector KLSE stocks.

    Reuses the cached TradingView sector screener data so no extra API calls
    are made if ``run()`` has already fetched PE peers for the same sector.
    """
    tv_name = _to_tv_name(target.ticker)
    sector = _tv_get_sector(tv_name)
    if not sector:
        return []

    return [
        PeerRef(
            ticker=_from_tv_name(stock.tv_name),
            tv_name=stock.tv_name,
            description=stock.description,
            sector=sector,
        )
        for stock in _tv_fetch_sector_pes(sector)
        if stock.tv_name != tv_name
    ]


# ── z-score / discount helper ─────────────────────────────────────────────────

def _zscore_and_discount(value: float | None, peers: list[float]) -> tuple[float | None, float | None]:
    """Return (z-score, pct_discount) of *value* relative to the peer list."""
    if not peers or value is None:
        return None, None
    mean = statistics.mean(peers)
    stdev = statistics.stdev(peers) if len(peers) > 1 else None
    z = ((value - mean) / stdev) if stdev else None
    discount = ((mean - value) / mean * 100.0) if mean else None
    return z, discount


# ── Phase entry point ─────────────────────────────────────────────────────────

def run(target: "FeatureTarget", payload: "FeaturePayload") -> None:
    """Fetch valuation data and compute metrics 15-18."""
    try:
        import yfinance as yf
    except ImportError as exc:
        logger.error("yfinance is not installed: %s", exc)
        for k in ("forward_pe_peer_zscore", "forward_pe_peer_discount_pct",
                  "forward_ps_ratio", "peg_ratio"):
            payload.set_metric(k, None)
        return

    symbol = target.yf_symbol
    logger.info("Phase 2 – fetching valuation for %s", symbol)

    try:
        ticker_obj = yf.Ticker(symbol)
        info = ticker_obj.info or {}
        income_q = ticker_obj.quarterly_income_stmt
    except Exception as exc:  # noqa: BLE001
        logger.error("Phase 2 yfinance fetch failed for %s: %s", symbol, exc)
        payload.set_metadata("phase_2_error", str(exc))
        for k in ("forward_pe_peer_zscore", "forward_pe_peer_discount_pct",
                  "forward_ps_ratio", "peg_ratio"):
            payload.set_metric(k, None)
        return

    payload.set_metadata("phase_2_source", f"yfinance/{symbol}")

    market_cap: float | None = info.get("marketCap")
    trailing_pe: float | None = info.get("trailingPE")

    # ── Forward P/S (yfinance) ───────────────────────────────────────────────
    try:
        ttm_revenue: float | None = None
        if income_q is not None and not income_q.empty and "Total Revenue" in income_q.index:
            rev_row = income_q.loc["Total Revenue"]
            if len(rev_row) >= 4:
                ttm_revenue = float(sum(rev_row.iloc[:4]))
        payload.set_metric(
            "forward_ps_ratio",
            (market_cap / ttm_revenue) if (market_cap and ttm_revenue and ttm_revenue > 0) else None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Phase 2 P/S ratio failed for %s: %s", symbol, exc)
        payload.set_metric("forward_ps_ratio", None)

    # ── PEG ratio (yfinance only) ───────────────────────────────────────────
    payload.set_metric("peg_ratio", info.get("pegRatio"))

    # ── Trailing PE vs dynamic TradingView sector peers ──────────────────────
    try:
        tv_name = _to_tv_name(target.ticker)
        tv_sector = _tv_get_sector(tv_name)
        peer_pe_values = _tv_peer_pes(tv_name, tv_sector)

        logger.info(
            "Phase 2: %s TV-sector='%s' → %d same-sector peers (trailing PE)",
            target.ticker,
            tv_sector,
            len(peer_pe_values),
        )

        z, discount = _zscore_and_discount(trailing_pe, peer_pe_values)
        payload.set_metric("forward_pe_peer_zscore", z)
        payload.set_metric("forward_pe_peer_discount_pct", discount)

        peers = discover_sector_peers(target)
        payload.set_metadata("phase_2_peer_refs", [p.to_dict() for p in peers])
        payload.set_metadata("phase_2_peer_count", len(peer_pe_values))
        payload.set_metadata("phase_2_peer_sector", tv_sector)
        payload.set_metadata("phase_2_peer_source", "TradingView/dynamic-sector")
        payload.set_metadata("phase_2_pe_type", "trailing/TTM")
    except Exception as exc:  # noqa: BLE001
        logger.error("Phase 2 peer PE failed for %s: %s", symbol, exc)
        payload.set_metric("forward_pe_peer_zscore", None)
        payload.set_metric("forward_pe_peer_discount_pct", None)
