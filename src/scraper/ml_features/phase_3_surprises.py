"""Phase 3 – Earning Surprises (metrics 1-5).

Sources (tried in order)
------------------------
1. Investing.com earnings tab (Scrapling)  — EPS and revenue actual vs forecast.
2. yfinance ``earnings_history``           — EPS only when Investing.com fails.
3. i3investor KLSE scrape                  — last resort.

Metrics computed
----------------
1. revenue_beat_rate_8q             — fraction of last 8 quarters with revenue beat
2. eps_beat_rate_8q                 — fraction of last 8 quarters with EPS beat
3. avg_revenue_surprise_pct         — mean (actual-estimate)/|estimate| revenue surprise
4. avg_eps_surprise_pct             — mean (actual-estimate)/|estimate| EPS surprise
5. consecutive_double_beat_quarters — # consecutive most-recent quarters with both beats
"""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import FeaturePayload, FeatureTarget

logger = logging.getLogger(__name__)
I3INVESTOR_BASE = "https://klse.i3investor.com"


# ── Data fetchers ────────────────────────────────────────────────────────────

def _to_float(val: Any) -> float | None:
    """Convert to float, returning None for NaN / None / non-numeric values."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _fetch_yfinance_earnings(yf_symbol: str, limit: int = 8) -> list[dict[str, Any]]:
    """Fetch EPS actual vs estimate from yfinance earnings_history.

    Revenue estimates are not available via yfinance; revenue columns will be
    None, so only EPS-based metrics (2, 4, 5) will be computed from this source.
    """
    try:
        import yfinance as yf

        t = yf.Ticker(yf_symbol)
        eh = t.earnings_history
        if eh is None or (hasattr(eh, "empty") and eh.empty):
            return []

        records: list[dict[str, Any]] = []
        for _, row in list(eh.iterrows())[:limit]:
            # Column names vary across yfinance versions; current API returns epsEstimate/epsActual
            eps_est = _to_float(
                row.get("epsEstimate") or row.get("EPS Estimate") or row.get("eps_estimate")
            )
            eps_act = _to_float(
                row.get("epsActual") or row.get("Reported EPS") or row.get("reportedEPS") or row.get("reported_eps")
            )
            if eps_est is None or eps_act is None:
                continue
            records.append({
                "date": str(getattr(row, "name", "")),
                "actualRevenue": None,       # not available from yfinance
                "estimatedRevenue": None,
                "actualEarningsPerShare": eps_act,
                "estimatedEarningsPerShare": eps_est,
            })
        return records
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase 3: yfinance earnings_history failed for %s: %s", yf_symbol, exc)
        return []


def _fetch_i3investor_surprises(ticker: str, numeric_code: str | None, limit: int = 8) -> list[dict[str, Any]]:
    """Scrape i3investor quarterly results table (last-resort fallback)."""
    try:
        import requests
        from bs4 import BeautifulSoup

        # Try with the Bursa numeric code first (more reliable), then the name
        codes_to_try = [c for c in [numeric_code, ticker] if c]
        for code in codes_to_try:
            url = f"{I3INVESTOR_BASE}/web/stock/analyst-earnings.ajax.php?code={code}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("table tbody tr")
            if not rows:
                # Try alternate selectors in case HTML structure changed
                rows = soup.select("tbody tr")
            records = []
            for row in rows[:limit]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 5:
                    try:
                        records.append({
                            "date": cells[0],
                            "actualRevenue": _to_float(cells[1]),
                            "estimatedRevenue": _to_float(cells[2]),
                            "actualEarningsPerShare": _to_float(cells[3]),
                            "estimatedEarningsPerShare": _to_float(cells[4]),
                        })
                    except Exception:  # noqa: BLE001
                        continue
            if records:
                return records
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase 3: i3investor scrape failed for %s: %s", ticker, exc)
        return []


# ── Metric computation ───────────────────────────────────────────────────────

def _compute_surprise_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive the five surprise metrics from a list of earn-surprise dicts."""
    rev_beats, eps_beats = 0, 0
    rev_surprises, eps_surprises = [], []
    total = len(records)

    for r in records:
        act_rev = r.get("actualRevenue")
        est_rev = r.get("estimatedRevenue")
        act_eps = r.get("actualEarningsPerShare")
        est_eps = r.get("estimatedEarningsPerShare")

        if act_rev is not None and est_rev is not None and est_rev != 0:
            rev_surprises.append((act_rev - est_rev) / abs(est_rev) * 100.0)
            if act_rev >= est_rev:
                rev_beats += 1

        if act_eps is not None and est_eps is not None and est_eps != 0:
            eps_surprises.append((act_eps - est_eps) / abs(est_eps) * 100.0)
            if act_eps >= est_eps:
                eps_beats += 1

    # Consecutive double-beats from most-recent record (index 0)
    consecutive = 0
    for r in records:
        act_rev = r.get("actualRevenue")
        est_rev = r.get("estimatedRevenue")
        act_eps = r.get("actualEarningsPerShare")
        est_eps = r.get("estimatedEarningsPerShare")
        rev_beat = act_rev is not None and est_rev is not None and act_rev >= est_rev
        eps_beat = act_eps is not None and est_eps is not None and act_eps >= est_eps
        if rev_beat and eps_beat:
            consecutive += 1
        else:
            break

    # Revenue-based metrics are None when no revenue estimate data available
    rev_total = sum(1 for r in records if r.get("estimatedRevenue") is not None)
    return {
        "revenue_beat_rate_8q": (rev_beats / rev_total) if rev_total else None,
        "eps_beat_rate_8q": (eps_beats / total) if total else None,
        "avg_revenue_surprise_pct": (sum(rev_surprises) / len(rev_surprises)) if rev_surprises else None,
        "avg_eps_surprise_pct": (sum(eps_surprises) / len(eps_surprises)) if eps_surprises else None,
        "consecutive_double_beat_quarters": consecutive,
    }


# ── Phase entry point ─────────────────────────────────────────────────────────

def run(
    target: "FeatureTarget",
    payload: "FeaturePayload",
    *,
    allow_investing: bool = True,
    description: str | None = None,
) -> None:
    """Fetch earnings surprise data and compute metrics 1-5.

    *description* is the TradingView company name (from ``PeerRef.description``)
    used for dynamic Investing.com slug resolution when no static mapping exists.
    """
    logger.info("Phase 3 – fetching earning surprises for %s", target.ticker)

    # Import the numeric code map to pass to i3investor fallback
    try:
        from .types import _KLSE_YFINANCE_CODES
        numeric_code = _KLSE_YFINANCE_CODES.get(target.ticker.upper())
    except Exception:  # noqa: BLE001
        numeric_code = None

    records: list[dict[str, Any]] = []
    source = "none"

    # 1. Investing.com (revenue + EPS; Scrapling loads __NEXT_DATA__ earnings JSON)
    if allow_investing:
        try:
            from .investing_com import fetch_earnings_surprises

            records = fetch_earnings_surprises(target.ticker, limit=8, description=description)
            if records:
                source = "investing.com"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Phase 3: Investing.com failed for %s: %s", target.ticker, exc)

    # 2. yfinance earnings_history (EPS only; revenue surprise will be null)
    if not records:
        logger.info("Phase 3: trying yfinance earnings_history for %s", target.ticker)
        records = _fetch_yfinance_earnings(target.yf_symbol, limit=8)
        if records:
            source = "yfinance"

    # 3. i3investor (last resort)
    if not records:
        logger.info("Phase 3: trying i3investor for %s", target.ticker)
        records = _fetch_i3investor_surprises(target.ticker, numeric_code, limit=8)
        if records:
            source = "i3investor"

    if not records:
        logger.warning("Phase 3: no earning surprise data found for %s", target.ticker)
        for k in ("revenue_beat_rate_8q", "eps_beat_rate_8q", "avg_revenue_surprise_pct",
                  "avg_eps_surprise_pct", "consecutive_double_beat_quarters"):
            payload.set_metric(k, None)
        payload.set_metadata("phase_3_source", "none")
        return

    payload.set_metadata("phase_3_source", source)
    payload.set_metadata("phase_3_records_used", len(records))

    metrics = _compute_surprise_metrics(records)
    for key, value in metrics.items():
        payload.set_metric(key, value)
