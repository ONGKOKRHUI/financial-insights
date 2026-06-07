"""i3investor KLSE scrapers for financial quarters and shareholding trades."""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Callable

import requests

from .types import _KLSE_YFINANCE_CODES

logger = logging.getLogger(__name__)

I3_BASE = "https://klse.i3investor.com"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# dtdata column indices on /web/stock/financial-quarter/{code}
_FQ_COL_QTR_END = 2
_FQ_COL_REVENUE = 4
_FQ_COL_PBT = 5
_FQ_COL_NP = 6

# dtdata_holder on /web/stock/holder/{code} and substantial-shareholder/{code}
_TRADE_COL_DATE = 0
_TRADE_COL_NAME = 1
_TRADE_COL_TYPE = 3
_TRADE_COL_SHARES = 4
_TRADE_COL_PRICE = 5

# Form 29C — Changes in Director's Interest
DIRECTOR_TRADES_PATH = "holder"
# Form 29B — Changes in Substantial Shareholder's Interest
SUBSTANTIAL_TRADES_PATH = "substantial-shareholder"

_INSTITUTIONAL_KEYWORDS = (
    "employees provident fund",
    "epf",
    "kwsp",
    "permodalan nasional",
    "pnb",
    "amanah saham",
    "kumpulan wang persaraan",
    "kwap",
    "retirement fund",
    "lembaga tabung haji",
    "tabung haji",
    "tabung angkatan tentera",
    "ltat",
    "socso",
    "perkeso",
    "khazanah",
    "valuecap",
    "great eastern",
    "employees provident",
)

_DTDATE_RE = re.compile(
    r"var\s+(dtdata(?:_\w+)?)\s*=\s*(\[.*?\]);",
    re.DOTALL,
)


def numeric_code(ticker: str) -> str | None:
    return _KLSE_YFINANCE_CODES.get(ticker.upper())


def _fetch_page(url: str, *, max_retries: int = 3) -> str | None:
    import time

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
            resp.raise_for_status()
            return resp.text
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "i3investor GET attempt %d/%d failed for %s: %s. Retrying in %ds...",
                    attempt, max_retries, url, exc, wait,
                )
                time.sleep(wait)
            else:
                logger.warning("i3investor GET failed after %d attempts for %s: %s", max_retries, url, exc)
                return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("i3investor GET failed for %s: %s", url, exc)
            return None
    return None


def _extract_embedded_json(html: str, preferred_names: tuple[str, ...] = ("dtdata",)) -> list[Any] | None:
    """Parse the first matching ``var dtdata* = [...]`` assignment."""
    matches = list(_DTDATE_RE.finditer(html))
    if not matches:
        return None

    for pref in preferred_names:
        for m in matches:
            if m.group(1) == pref:
                try:
                    return json.loads(m.group(2))
                except json.JSONDecodeError:
                    continue

    for m in matches:
        try:
            return json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
    return None


def _parse_number(raw: Any) -> float | None:
    if raw is None:
        return None
    text = re.sub(r"<[^>]+>", "", str(raw)).strip()
    if not text or text in {"-", "N/A", "n/a", " - "}:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _parse_i3_date(text: str) -> date | None:
    for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _trade_page_url(code: str, page_path: str) -> str:
    return f"{I3_BASE}/web/stock/{page_path}/{code}"


def _is_institutional_name(name: str) -> bool:
    normalized = html_lib.unescape(name).lower()
    return any(keyword in normalized for keyword in _INSTITUTIONAL_KEYWORDS)


def _effective_price(raw_price: Any, fallback_price: float | None) -> float | None:
    price = _parse_number(raw_price)
    if price is not None and price > 0:
        return price
    if fallback_price is not None and fallback_price > 0:
        return fallback_price
    return None


def fetch_trade_rows(code: str, page_path: str) -> list[dict[str, Any]]:
    """Return normalized trade rows from an i3investor holder table page."""
    url = _trade_page_url(code, page_path)
    html = _fetch_page(url)
    if not html:
        return []

    raw_rows = _extract_embedded_json(html, preferred_names=("dtdata_holder", "dtdata"))
    if not raw_rows:
        logger.warning("i3investor: no trade dtdata on %s for %s", page_path, code)
        return []

    trades: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, list) or len(row) <= _TRADE_COL_PRICE:
            continue
        trade_type = str(row[_TRADE_COL_TYPE]).strip()
        if trade_type not in {"Acquired", "Disposed"}:
            continue
        trade_date = _parse_i3_date(str(row[_TRADE_COL_DATE]))
        shares = _parse_number(row[_TRADE_COL_SHARES])
        if trade_date is None or shares is None:
            continue
        trades.append({
            "date": trade_date,
            "name": html_lib.unescape(str(row[_TRADE_COL_NAME]).strip()),
            "type": trade_type,
            "shares": shares,
            "price_raw": row[_TRADE_COL_PRICE],
        })
    return trades


def compute_net_flow_myr(
    trades: list[dict[str, Any]],
    *,
    days_lookback: int = 90,
    fallback_price: float | None = None,
    name_filter: Callable[[str], bool] | None = None,
) -> tuple[float, int]:
    """Sum signed MYR value for trades within the lookback window."""
    cutoff = date.today() - timedelta(days=days_lookback)
    net = 0.0
    counted = 0

    for trade in trades:
        if trade["date"] < cutoff:
            continue
        if name_filter is not None and not name_filter(trade["name"]):
            continue

        price = _effective_price(trade.get("price_raw"), fallback_price)
        if price is None:
            continue

        value = trade["shares"] * price
        if trade["type"] == "Acquired":
            net += value
        else:
            net -= value
        counted += 1

    return net, counted


def fetch_director_net_flow_myr(
    code: str,
    *,
    days_lookback: int = 90,
    fallback_price: float | None = None,
) -> tuple[float | None, int]:
    """
    Net director trading (Form 29C) from /web/stock/holder/{code}.

    Positive for net Acquired, negative for net Disposed.
    """
    trades = fetch_trade_rows(code, DIRECTOR_TRADES_PATH)
    net, counted = compute_net_flow_myr(
        trades,
        days_lookback=days_lookback,
        fallback_price=fallback_price,
    )
    if counted == 0:
        return 0.0, 0
    return net, counted


def fetch_institutional_net_flow_myr(
    code: str,
    *,
    days_lookback: int = 90,
    fallback_price: float | None = None,
) -> tuple[float | None, int]:
    """
    Net institutional substantial-shareholder flow (Form 29B subset).

    Uses /web/stock/substantial-shareholder/{code} and keeps rows whose holder
    name matches known Malaysian institutional investors (EPF, KWAP, PNB, etc.).
    """
    trades = fetch_trade_rows(code, SUBSTANTIAL_TRADES_PATH)
    net, counted = compute_net_flow_myr(
        trades,
        days_lookback=days_lookback,
        fallback_price=fallback_price,
        name_filter=_is_institutional_name,
    )
    if counted == 0:
        return None, 0
    return net, counted


def fetch_insider_net_flow_myr(code: str, days_lookback: int = 90) -> float | None:
    """Backward-compatible alias for director net flow without price fallback."""
    net, counted = fetch_director_net_flow_myr(code, days_lookback=days_lookback)
    if counted == 0:
        return 0.0
    return net


def fetch_financial_quarter_rows(code: str) -> list[dict[str, Any]]:
    """Return quarterly rows with revenue, PBT, and net profit from i3investor."""
    url = f"{I3_BASE}/web/stock/financial-quarter/{code}"
    html = _fetch_page(url)
    if not html:
        return []

    raw_rows = _extract_embedded_json(html, preferred_names=("dtdata",))
    if not raw_rows:
        logger.warning("i3investor: no dtdata on financial-quarter page for %s", code)
        return []

    quarters: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, list) or len(row) <= _FQ_COL_NP:
            continue
        revenue = _parse_number(row[_FQ_COL_REVENUE])
        pbt = _parse_number(row[_FQ_COL_PBT])
        net_profit = _parse_number(row[_FQ_COL_NP])
        qtr_end = _parse_i3_date(str(row[_FQ_COL_QTR_END]))
        if revenue is None or qtr_end is None:
            continue
        quarters.append({
            "quarter_end": qtr_end,
            "revenue": revenue,
            "pbt": pbt,
            "net_profit": net_profit,
        })

    quarters.sort(key=lambda r: r["quarter_end"], reverse=True)
    return quarters


def compute_margin_deltas_qoq(quarters: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    """
    Map legacy metric slots to bank-friendly margins:
    - gross_margin_delta_qoq_pct  → PBT / Revenue margin QoQ (pp)
    - operating_margin_delta_qoq_pct → Net Profit / Revenue margin QoQ (pp)
    """
    if len(quarters) < 2:
        return None, None

    def _margins(row: dict[str, Any]) -> tuple[float | None, float | None]:
        rev = row.get("revenue")
        if not rev or rev == 0:
            return None, None
        pbt_m = (row["pbt"] / rev * 100.0) if row.get("pbt") is not None else None
        np_m = (row["net_profit"] / rev * 100.0) if row.get("net_profit") is not None else None
        return pbt_m, np_m

    pbt_latest, np_latest = _margins(quarters[0])
    pbt_prev, np_prev = _margins(quarters[1])

    pbt_delta = (pbt_latest - pbt_prev) if (pbt_latest is not None and pbt_prev is not None) else None
    np_delta = (np_latest - np_prev) if (np_latest is not None and np_prev is not None) else None
    return pbt_delta, np_delta
