"""Phase 1 – Fundamentals (metrics 10-14).

Source: yfinance ``yf.Ticker("<TICKER>.KL")`` quarterly financial APIs.

Metrics computed
----------------
10. revenue_yoy_growth_pct         — Revenue Q_n vs Q_{n-4} YoY (%)
11. net_income_yoy_growth_pct      — Net Income Q_n vs Q_{n-4} YoY (%)
12. gross_margin_delta_qoq_pct     — PBT / Revenue margin QoQ change (pp); i3investor
13. operating_margin_delta_qoq_pct — Net profit / Revenue margin QoQ change (pp); i3investor
14. fcf_yield_pct                  — FCF TTM / Market Cap (%)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import FeaturePayload, FeatureTarget

logger = logging.getLogger(__name__)


def _safe_pct_change(new: float | None, old: float | None) -> float | None:
    """Return (new - old) / |old| * 100 or None when inputs are unavailable."""
    if new is None or old is None or old == 0:
        return None
    return (new - old) / abs(old) * 100.0


def _safe_margin(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator * 100.0


def run(target: "FeatureTarget", payload: "FeaturePayload") -> None:
    """Fetch quarterly statements from yfinance and compute metrics 10-14."""
    try:
        import yfinance as yf
    except ImportError as exc:
        logger.error("yfinance is not installed: %s", exc)
        return

    symbol = target.yf_symbol
    logger.info("Phase 1 – fetching fundamentals for %s", symbol)

    try:
        ticker_obj = yf.Ticker(symbol)
        income_q = ticker_obj.quarterly_income_stmt
        cashflow_q = ticker_obj.quarterly_cashflow
        info = ticker_obj.info
    except Exception as exc:  # noqa: BLE001
        logger.error("Phase 1 yfinance fetch failed for %s: %s", symbol, exc)
        payload.set_metadata("phase_1_error", str(exc))
        return

    payload.set_metadata("phase_1_source", f"yfinance/{symbol}")

    # ── Revenue & Net Income YoY ────────────────────────────────────────────
    try:
        if income_q is not None and not income_q.empty:
            cols = list(income_q.columns)  # newest-first
            if len(cols) >= 5:
                rev_row = income_q.loc["Total Revenue"] if "Total Revenue" in income_q.index else None
                ni_row = income_q.loc["Net Income"] if "Net Income" in income_q.index else None
                rev_latest = float(rev_row.iloc[0]) if rev_row is not None else None
                rev_yoy_ago = float(rev_row.iloc[4]) if rev_row is not None else None
                ni_latest = float(ni_row.iloc[0]) if ni_row is not None else None
                ni_yoy_ago = float(ni_row.iloc[4]) if ni_row is not None else None

                payload.set_metric("revenue_yoy_growth_pct", _safe_pct_change(rev_latest, rev_yoy_ago))
                payload.set_metric("net_income_yoy_growth_pct", _safe_pct_change(ni_latest, ni_yoy_ago))

                # Margin QoQ: yfinance gross/operating lines are absent for banks; filled via i3 below.
                gp_row = income_q.loc["Gross Profit"] if "Gross Profit" in income_q.index else None
                oi_row = income_q.loc["Operating Income"] if "Operating Income" in income_q.index else None
                if gp_row is not None and oi_row is not None:
                    gp_latest = float(gp_row.iloc[0])
                    gp_prev = float(gp_row.iloc[1])
                    oi_latest = float(oi_row.iloc[0])
                    oi_prev = float(oi_row.iloc[1])
                    gm_latest = _safe_margin(gp_latest, rev_latest)
                    gm_prev = _safe_margin(gp_prev, float(rev_row.iloc[1]) if rev_row is not None else None)
                    om_latest = _safe_margin(oi_latest, rev_latest)
                    om_prev = _safe_margin(oi_prev, float(rev_row.iloc[1]) if rev_row is not None else None)
                    payload.set_metric(
                        "gross_margin_delta_qoq_pct",
                        (gm_latest - gm_prev) if (gm_latest is not None and gm_prev is not None) else None,
                    )
                    payload.set_metric(
                        "operating_margin_delta_qoq_pct",
                        (om_latest - om_prev) if (om_latest is not None and om_prev is not None) else None,
                    )
                    payload.set_metadata("phase_1_margin_source", f"yfinance/{symbol}")
            else:
                logger.warning("Phase 1: insufficient quarterly income history for %s (%d cols)", symbol, len(cols))
                for key in ("revenue_yoy_growth_pct", "net_income_yoy_growth_pct", "gross_margin_delta_qoq_pct", "operating_margin_delta_qoq_pct"):
                    payload.set_metric(key, None)
        else:
            logger.warning("Phase 1: quarterly_income_stmt empty for %s", symbol)
            for key in ("revenue_yoy_growth_pct", "net_income_yoy_growth_pct", "gross_margin_delta_qoq_pct", "operating_margin_delta_qoq_pct"):
                payload.set_metric(key, None)
    except Exception as exc:  # noqa: BLE001
        logger.error("Phase 1 income statement parsing failed for %s: %s", symbol, exc)
        for key in ("revenue_yoy_growth_pct", "net_income_yoy_growth_pct", "gross_margin_delta_qoq_pct", "operating_margin_delta_qoq_pct"):
            payload.set_metric(key, None)

    # ── FCF Yield ───────────────────────────────────────────────────────────
    try:
        market_cap = info.get("marketCap") if info else None
        fcf_ttm: float | None = None
        if cashflow_q is not None and not cashflow_q.empty:
            cols = list(cashflow_q.columns)
            fcf_row = cashflow_q.loc["Free Cash Flow"] if "Free Cash Flow" in cashflow_q.index else None
            if fcf_row is not None and len(cols) >= 4:
                fcf_ttm = float(sum(fcf_row.iloc[:4]))

        if fcf_ttm is not None and market_cap and market_cap > 0:
            payload.set_metric("fcf_yield_pct", fcf_ttm / market_cap * 100.0)
        else:
            payload.set_metric("fcf_yield_pct", None)
    except Exception as exc:  # noqa: BLE001
        logger.error("Phase 1 FCF yield calculation failed for %s: %s", symbol, exc)
        payload.set_metric("fcf_yield_pct", None)

    # ── Bank-friendly margin QoQ (i3investor financial-quarter) ─────────────
    if payload.metrics.get("gross_margin_delta_qoq_pct") is None:
        try:
            from . import i3investor as i3

            code = i3.numeric_code(target.ticker)
            if code:
                quarters = i3.fetch_financial_quarter_rows(code)
                pbt_delta, np_delta = i3.compute_margin_deltas_qoq(quarters)
                payload.set_metric("gross_margin_delta_qoq_pct", pbt_delta)
                payload.set_metric("operating_margin_delta_qoq_pct", np_delta)
                if quarters:
                    payload.set_metadata("phase_1_margin_source", f"i3investor/financial-quarter/{code}")
                    payload.set_metadata("phase_1_i3_quarters_used", len(quarters))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Phase 1 i3investor margins failed for %s: %s", target.ticker, exc)
