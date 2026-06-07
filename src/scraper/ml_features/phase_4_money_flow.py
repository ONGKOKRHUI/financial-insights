"""Phase 4 – Money Flow (metrics 6-9).

Sources
-------
- i3investor KLSE HTML tables (no browser required):
  - /web/stock/holder/{code}                 → Form 29C director trades
  - /web/stock/substantial-shareholder/{code} → Form 29B substantial-holder trades
- Malaysia Warrants ScreenerJSONServlet for implied volatility data.

Metrics computed
----------------
6. net_institutional_cash_flow_myr           — Net institutional buying (MYR)
7. institutional_flow_to_market_cap_ratio    — Metric 6 / market cap
8. net_insider_trading_value_myr             — Net director buying (MYR)
9. options_iv_rank_pct                       — IV percentile rank of KLSE warrants
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import FeaturePayload, FeatureTarget

logger = logging.getLogger(__name__)

WARRANT_SCREENER_URL = (
    "https://www.malaysiawarrants.com.my/apimqmy/ScreenerJSONServlet"
    "?underlying=mystocks&type=all&issuer=all&maturity=all&moneyness=all"
    "&moneynessPercent=all&effectiveGearing=all&expiry=all&indicator=all"
    "&sortBy=&sortOrder=asc"
)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _parse_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _fetch_warrant_iv(ticker: str, bursa_code: str) -> tuple[float | None, str | None]:
    """Fetch structured warrant implied volatility from Malaysia Warrants screener JSON."""
    import requests

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
        "Referer": "https://www.malaysiawarrants.com.my/tools/warrantsearch/",
    }
    try:
        resp = requests.get(WARRANT_SCREENER_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        raw_data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.info("Phase 4: warrant screener unavailable for %s: %s", ticker, exc)
        return None, None

    warrants = raw_data.get("data", []) if isinstance(raw_data, dict) else []
    ticker_upper = ticker.upper()
    matching = [
        w for w in warrants
        if str(w.get("ticker", "")).startswith(bursa_code)
        or str(w.get("dwSymbol", "")).upper().startswith(ticker_upper)
        or str(w.get("underlying", "")).upper() in {ticker_upper, bursa_code}
    ]
    if not matching:
        return None, None

    calls = [w for w in matching if str(w.get("type", "")).upper() in {"CALL", "C", "CW"}]
    candidates = calls or matching
    candidates.sort(key=lambda w: _parse_float(str(w.get("tradeVolume", 0))) or 0, reverse=True)
    best = candidates[0]
    iv_raw = best.get("impliedVolalitiy")  # API spelling is intentionally misspelled.
    iv = _parse_float(str(iv_raw)) if iv_raw is not None else None
    warrant_ticker = best.get("dwSymbol") or best.get("ticker")
    return (round(iv / 100.0, 4) if iv is not None else None), warrant_ticker


def _fetch_yfinance_market_data(yf_symbol: str) -> tuple[float | None, float | None]:
    """Return market cap and last price for flow ratio and missing trade prices."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(yf_symbol)
        fast_info = ticker.fast_info or {}
        market_cap = fast_info.get("marketCap") or fast_info.get("market_cap")
        last_price = fast_info.get("lastPrice") or fast_info.get("last_price")
        if market_cap is None:
            market_cap = (ticker.info or {}).get("marketCap")
        return market_cap, last_price
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase 4: yfinance market data lookup failed for %s: %s", yf_symbol, exc)
        return None, None


def run(target: "FeatureTarget", payload: "FeaturePayload") -> None:
    """Fetch i3investor shareholding trades and warrant IV, compute metrics 6-9."""
    from . import i3investor as i3

    logger.info("Phase 4 – fetching money flow for %s", target.ticker)

    bursa_code = target.yf_symbol.replace(".KL", "")
    code = i3.numeric_code(target.ticker) or bursa_code
    market_cap, fallback_price = _fetch_yfinance_market_data(target.yf_symbol)
    lookback_days = 90

    institutional_flow: float | None = None
    institutional_count = 0
    director_flow: float | None = None
    director_count = 0

    try:
        institutional_flow, institutional_count = i3.fetch_institutional_net_flow_myr(
            code,
            days_lookback=lookback_days,
            fallback_price=fallback_price,
        )
        logger.info(
            "Phase 4: i3investor institutional trades for %s (%s rows in 90d)",
            code,
            institutional_count,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase 4: i3investor institutional trades failed for %s: %s", target.ticker, exc)

    try:
        director_flow, director_count = i3.fetch_director_net_flow_myr(
            code,
            days_lookback=lookback_days,
            fallback_price=fallback_price,
        )
        logger.info(
            "Phase 4: i3investor director trades for %s (%s rows in 90d)",
            code,
            director_count,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase 4: i3investor director trades failed for %s: %s", target.ticker, exc)

    payload.set_metric(
        "net_institutional_cash_flow_myr",
        institutional_flow if institutional_count else None,
    )
    payload.set_metric(
        "net_insider_trading_value_myr",
        director_flow if director_count else (0.0 if director_flow == 0.0 else None),
    )
    payload.set_metadata(
        "phase_4_institutional_source",
        f"i3investor/stock/{i3.SUBSTANTIAL_TRADES_PATH}/{code}",
    )
    payload.set_metadata(
        "phase_4_insider_source",
        f"i3investor/stock/{i3.DIRECTOR_TRADES_PATH}/{code}",
    )
    payload.set_metadata("phase_4_institutional_trades_used", institutional_count)
    payload.set_metadata("phase_4_director_trades_used", director_count)
    payload.set_metadata("phase_4_filings_parsed", institutional_count + director_count)
    payload.set_metadata(
        "phase_4_source",
        "i3investor holder + substantial-shareholder (Form 29C/29B HTML tables)",
    )

    payload.set_metric(
        "institutional_flow_to_market_cap_ratio",
        (institutional_flow / market_cap)
        if (market_cap and market_cap > 0 and institutional_count)
        else None,
    )

    iv_rank, warrant_ticker = _fetch_warrant_iv(target.ticker, bursa_code)
    payload.set_metric("options_iv_rank_pct", iv_rank)
    payload.set_metadata("phase_4_iv_source", "Malaysia Warrants ScreenerJSONServlet")
    payload.set_metadata("phase_4_warrant_ticker", warrant_ticker)
