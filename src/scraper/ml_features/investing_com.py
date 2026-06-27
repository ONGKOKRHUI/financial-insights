"""Investing.com earnings scraper.

Primary path: direct JSON API via ``endpoints.investing.com`` (~350ms per ticker).
Fallback path: Scrapling headless-browser page load + embedded JSON parsing (~90s).

The fast API requires an Investing.com ``instrument_id`` for each ticker.  IDs are
resolved in order: static map → search API → Scrapling fallback (which also
caches the discovered ID for subsequent calls).
"""
from __future__ import annotations

import base64
import difflib
import json
import logging
import os
import re
import time
from typing import Any

import requests as _requests

from .types import InstrumentIdentity, _INVESTING_EQUITY_SLUGS, _INVESTING_INSTRUMENT_IDS

logger = logging.getLogger(__name__)

_INVESTING_BASE = "https://www.investing.com"
_EARNINGS_API_BASE = "https://endpoints.investing.com/earnings/v1/instruments"
_SEARCH_API = "https://api.investing.com/api/search/v2/search"
_EARNINGS_ARRAY_RE = re.compile(r'"earnings"\s*:\s*(\[[\s\S]*?\])\s*,\s*"[a-zA-Z_]+"\s*:', re.DOTALL)
_MIN_SEARCH_ACCEPT_SCORE = 150
_MIN_SEARCH_SCORE_GAP = 25

_API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://www.investing.com",
    "Referer": "https://www.investing.com/",
}

_instrument_id_cache: dict[str, int] = {}
_equity_slug_cache: dict[str, str] = {}


class _InvestingAuthSession:
    """Reuse a single guest JWT across many earnings API calls in one pipeline run."""

    _bearer: str | None = None
    _bearer_exp: float | None = None
    _bearer_unavailable_until: float | None = None

    @classmethod
    def get_bearer(cls) -> str | None:
        env_token = os.getenv("INVESTING_BEARER_TOKEN", "").strip()
        if env_token:
            return env_token

        now = time.time()
        if cls._bearer and cls._bearer_exp and now < cls._bearer_exp - 60:
            return cls._bearer
        if cls._bearer_unavailable_until and now < cls._bearer_unavailable_until:
            return None

        from .scrapling_utils import bootstrap_investing_bearer_token

        token = bootstrap_investing_bearer_token()
        if not token:
            try:
                retry_seconds = float(os.getenv("INVESTING_BEARER_RETRY_SECONDS", "300"))
            except ValueError:
                retry_seconds = 300.0
            cls._bearer_unavailable_until = now + max(retry_seconds, 0.0)
            return None

        cls._bearer = token
        cls._bearer_exp = _jwt_exp(token)
        cls._bearer_unavailable_until = None
        return cls._bearer

    @classmethod
    def reset(cls) -> None:
        cls._bearer = None
        cls._bearer_exp = None
        cls._bearer_unavailable_until = None


def _jwt_exp(token: str) -> float | None:
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        return float(exp) if exp is not None else None
    except Exception:  # noqa: BLE001
        return None


# ── Fast-path helpers ────────────────────────────────────────────────────────


def _extract_equity_slug_from_quote(quote: Any) -> str | None:
    """Pull the canonical ``/equities/{slug}`` path from a search result object."""
    if isinstance(quote, str):
        match = re.search(
            r"(?:https?://(?:(?:www|[a-z]{2})\.)?investing\.com)?/equities/([^/?#]+)",
            quote,
        )
        if not match:
            return None
        slug = match.group(1)
        if slug.endswith("-earnings"):
            slug = slug[: -len("-earnings")]
        return slug or None

    if isinstance(quote, dict):
        for value in quote.values():
            slug = _extract_equity_slug_from_quote(value)
            if slug:
                return slug
    elif isinstance(quote, list):
        for item in quote:
            slug = _extract_equity_slug_from_quote(item)
            if slug:
                return slug

    return None


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _first_text(result: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = result.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def _result_symbol(result: dict[str, Any]) -> str:
    return _first_text(result, "symbol", "ticker")


def _result_name(result: dict[str, Any]) -> str:
    return _first_text(result, "name", "title", "description", "pair_name", "pairName")


def _result_exchange(result: dict[str, Any]) -> str:
    return _first_text(result, "exchange", "exchange_name", "exchangeName", "market")


def _result_country(result: dict[str, Any]) -> str:
    return _first_text(result, "country", "country_name", "countryName", "flag")


def _result_currency(result: dict[str, Any]) -> str:
    return _first_text(result, "currency", "currency_code", "currencyCode")


def _same_exchange(left: Any, right: Any) -> bool:
    left_norm = _norm(left)
    right_norm = _norm(right)
    if not left_norm or not right_norm:
        return False
    aliases = {
        "kualalumpur": {"kualalumpur", "bursamalaysia", "xkls", "klse"},
        "bursamalaysia": {"kualalumpur", "bursamalaysia", "xkls", "klse"},
        "xkls": {"kualalumpur", "bursamalaysia", "xkls", "klse"},
    }
    return left_norm == right_norm or right_norm in aliases.get(left_norm, set())


def _same_country(left: Any, right: Any) -> bool:
    left_norm = _norm(left)
    right_norm = _norm(right)
    if not left_norm or not right_norm:
        return False
    aliases = {
        "my": {"my", "malaysia"},
        "malaysia": {"my", "malaysia"},
    }
    return left_norm == right_norm or right_norm in aliases.get(left_norm, set())


def _same_currency(left: Any, right: Any) -> bool:
    return bool(_norm(left)) and _norm(left) == _norm(right)


def _is_equity_result(result: dict[str, Any]) -> bool:
    slug = _extract_equity_slug_from_quote(result)
    if slug:
        return True
    blob = " ".join(str(result.get(key, "")) for key in ("type", "category", "instrument_type", "instrumentType"))
    return any(token in blob.lower() for token in ("equity", "stock", "share"))


def _name_similarity(left: str | None, right: str | None) -> int:
    left_norm = " ".join(re.findall(r"[a-z0-9]+", str(left or "").lower()))
    right_norm = " ".join(re.findall(r"[a-z0-9]+", str(right or "").lower()))
    if not left_norm or not right_norm:
        return 0
    return int(difflib.SequenceMatcher(None, left_norm, right_norm).ratio() * 100)


def _score_search_result(result: dict[str, Any], identity: InstrumentIdentity) -> int:
    score = 0

    result_iid = result.get("id")
    if identity.investing_instrument_id:
        if result_iid == identity.investing_instrument_id:
            score += 900
        elif isinstance(result_iid, int):
            score -= 900

    result_isin = _first_text(result, "isin", "ISIN")
    if result_isin and identity.isin:
        if _norm(result_isin) == _norm(identity.isin):
            score += 1000
        else:
            score -= 1000

    if _norm(_result_symbol(result)) == _norm(identity.ticker):
        score += 100

    exchange = _result_exchange(result)
    if _same_exchange(exchange, identity.exchange) or _same_exchange(exchange, identity.exchange_mic):
        score += 80

    if _same_country(_result_country(result), identity.country):
        score += 50

    if _same_currency(_result_currency(result), identity.currency):
        score += 30

    if _extract_equity_slug_from_quote(result):
        score += 25

    score += _name_similarity(_result_name(result), identity.name)
    return score


def _search_quotes(query: str) -> list[dict[str, Any]]:
    try:
        resp = _requests.get(
            _SEARCH_API,
            params={"q": query, "t": "Equities"},
            headers=_API_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Investing.com search API failed for '%s': %s", query, exc)
        return []

    quotes = data.get("quotes", [])
    return [q for q in quotes if isinstance(q, dict)]


def _rank_search_results(
    quotes: list[dict[str, Any]],
    identity: InstrumentIdentity,
) -> list[tuple[int, dict[str, Any]]]:
    scored = [
        (_score_search_result(q, identity), q)
        for q in quotes
        if _is_equity_result(q)
    ]
    return sorted(scored, key=lambda item: item[0], reverse=True)


def _resolve_equity_via_search(
    query: str,
    *,
    identity: InstrumentIdentity | None = None,
) -> tuple[int | None, str | None]:
    """Resolve an Investing.com equity by ranked identity match, not ticker alone."""
    quotes = _search_quotes(query)
    if not quotes:
        return None, None

    if identity is not None:
        ranked = _rank_search_results(quotes, identity)
        if not ranked:
            return None, None

        best_score, best = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else None
        if best_score < _MIN_SEARCH_ACCEPT_SCORE:
            logger.info(
                "Investing.com search: no confident match for %s via query='%s' (best_score=%d)",
                identity.cache_key, query, best_score,
            )
            return None, None
        if second_score is not None and best_score - second_score < _MIN_SEARCH_SCORE_GAP:
            logger.info(
                "Investing.com search: ambiguous match for %s via query='%s' "
                "(best_score=%d, second_score=%d)",
                identity.cache_key, query, best_score, second_score,
            )
            return None, None

        iid = best.get("id")
        valid_iid = iid if isinstance(iid, int) and iid > 0 else None
        return valid_iid, _extract_equity_slug_from_quote(best)

    # Compatibility path for older callers/tests that do not provide identity.
    fallback_iid: int | None = None
    fallback_slug: str | None = None
    for q in quotes:
        iid = q.get("id")
        valid_iid = iid if isinstance(iid, int) and iid > 0 else None
        slug = _extract_equity_slug_from_quote(q)
        if fallback_iid is None and valid_iid is not None:
            fallback_iid = valid_iid
            fallback_slug = slug
        elif fallback_slug is None and slug:
            fallback_slug = slug

        flag = str(q.get("flag", "")).upper()
        exchange = str(q.get("exchange", "")).lower()
        if (
            valid_iid is not None
            and (
            flag in {"MY", "MALAYSIA"}
            or "bursa" in exchange
            or "kuala" in exchange
            or "malaysia" in exchange
            )
        ):
            return valid_iid, slug

    return fallback_iid, fallback_slug


def _resolve_instrument_id_via_search(query: str) -> int | None:
    """Call the Investing.com search API and return the best-matching instrument ID."""
    iid, _ = _resolve_equity_via_search(query)
    return iid


def _instrument_search_queries(
    ticker: str,
    *,
    slug: str | None = None,
    description: str | None = None,
    identity: InstrumentIdentity | None = None,
) -> list[str]:
    """Build ordered, de-duplicated search queries for instrument ID lookup."""
    queries: list[str] = []
    if identity:
        if identity.isin:
            queries.append(identity.isin)
        if identity.investing_instrument_id:
            queries.append(str(identity.investing_instrument_id))
        if identity.exchange:
            queries.append(f"{ticker} {identity.exchange}")
        if identity.country:
            queries.append(f"{ticker} {identity.country}")
        if identity.currency:
            queries.append(f"{ticker} {identity.currency}")
    if description:
        queries.append(description)
    if slug:
        queries.extend(_slug_candidates(slug))
        queries.append(slug)
    if description:
        queries.extend(_slugs_from_description(description))
    queries.append(ticker)

    return list(dict.fromkeys(q for q in queries if q and q.strip()))


def _get_instrument_id(
    ticker: str,
    *,
    slug: str | None = None,
    description: str | None = None,
    identity: InstrumentIdentity | None = None,
) -> int | None:
    """Resolve an Investing.com instrument ID from cache, static map, or search API."""
    upper = ticker.upper()
    cache_key = identity.cache_key if identity else upper
    cached = _instrument_id_cache.get(cache_key)
    if isinstance(cached, int) and cached > 0:
        return cached

    if identity and identity.investing_instrument_id:
        _instrument_id_cache[cache_key] = identity.investing_instrument_id
        return identity.investing_instrument_id

    if upper in _INVESTING_INSTRUMENT_IDS:
        iid = _INVESTING_INSTRUMENT_IDS[upper]
        if iid > 0:
            _instrument_id_cache[cache_key] = iid
            return iid

    for search_term in _instrument_search_queries(
        ticker, slug=slug, description=description, identity=identity,
    ):
        iid, canonical_slug = _resolve_equity_via_search(search_term, identity=identity)
        if canonical_slug:
            _equity_slug_cache[cache_key] = canonical_slug
        if iid is not None and iid > 0:
            _instrument_id_cache[cache_key] = iid
            logger.info(
                "Investing.com: resolved instrument_id=%d for %s via search API (query='%s')",
                iid, ticker, search_term,
            )
            return iid

    return None


def _get_equity_slug(
    ticker: str,
    *,
    static_slug: str | None = None,
    description: str | None = None,
    identity: InstrumentIdentity | None = None,
) -> str | None:
    """Resolve the canonical Investing.com equity slug without relying on guesses."""
    upper = ticker.upper()
    cache_key = identity.cache_key if identity else upper
    cached = _equity_slug_cache.get(cache_key)
    if cached:
        return cached

    if static_slug and identity is None:
        _equity_slug_cache[cache_key] = static_slug
        return static_slug

    for search_term in _instrument_search_queries(
        ticker, slug=static_slug, description=description, identity=identity,
    ):
        _, canonical_slug = _resolve_equity_via_search(search_term, identity=identity)
        if canonical_slug:
            _equity_slug_cache[cache_key] = canonical_slug
            logger.info(
                "Investing.com: resolved equity slug=%s for %s via search API (query='%s')",
                canonical_slug, ticker, search_term,
            )
            return canonical_slug

    if static_slug:
        _equity_slug_cache[cache_key] = static_slug
        return static_slug

    return None


def _row_from_api_obj(obj: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one earnings API object to the canonical record format."""
    eps_act = obj.get("eps_actual")
    eps_est = obj.get("eps_forecast")
    rev_act = obj.get("revenue_actual")
    rev_est = obj.get("revenue_forecast")

    if eps_act is None and rev_act is None:
        return None

    return {
        "date": str(obj.get("date") or ""),
        "actualRevenue": float(rev_act) if rev_act is not None else None,
        "estimatedRevenue": float(rev_est) if rev_est is not None else None,
        "actualEarningsPerShare": float(eps_act) if eps_act is not None else None,
        "estimatedEarningsPerShare": float(eps_est) if eps_est is not None else None,
    }


def _fetch_earnings_api(
    instrument_id: int,
    limit: int = 10,
    *,
    bearer_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch historical earnings from the fast JSON endpoint (~350ms)."""
    if not bearer_token:
        return []

    url = f"{_EARNINGS_API_BASE}/{instrument_id}/earnings"
    headers = {
        **_API_HEADERS,
        "Accept": "*/*",
        "Authorization": f"Bearer {bearer_token}",
    }
    try:
        resp = _requests.get(
            url,
            params={"limit": limit},
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 401:
            logger.info("Investing.com earnings API: bearer token expired for id=%d", instrument_id)
            _InvestingAuthSession.reset()
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Investing.com earnings API failed for id=%d: %s",
            instrument_id,
            exc,
        )
        return []

    earnings = data.get("earnings", [])
    records: list[dict[str, Any]] = []
    for obj in earnings:
        if not isinstance(obj, dict):
            continue
        row = _row_from_api_obj(obj)
        if row is not None:
            records.append(row)
        if len(records) >= limit:
            break
    return records


# ── Scrapling fallback helpers (unchanged) ───────────────────────────────────


def _parse_amount(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(",", "")
    if not text or text in {"-", "N/A"}:
        return None
    mult = 1.0
    lower = text.lower()
    if lower.endswith("b"):
        mult = 1e9
        text = text[:-1]
    elif lower.endswith("m"):
        mult = 1e6
        text = text[:-1]
    elif lower.endswith("k"):
        mult = 1e3
        text = text[:-1]
    try:
        return float(text) * mult
    except ValueError:
        return None


def _parse_eps(raw: Any) -> float | None:
    return _parse_amount(raw)


def _row_from_investing_obj(obj: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one Investing.com earnings object to FMP-style keys."""
    eps_act = _parse_eps(obj.get("epsActual"))
    eps_est = _parse_eps(obj.get("epsForecast") or obj.get("epsEstimate"))
    rev_act = _parse_amount(obj.get("revenueActual"))
    rev_est = _parse_amount(obj.get("revenueForecast") or obj.get("revenueEstimate"))

    if eps_act is None and eps_est is None and rev_act is None and rev_est is None:
        return None

    return {
        "date": str(obj.get("date") or ""),
        "actualRevenue": rev_act,
        "estimatedRevenue": rev_est,
        "actualEarningsPerShare": eps_act,
        "estimatedEarningsPerShare": eps_est,
    }


def _records_from_earnings_array(html: str, limit: int) -> list[dict[str, Any]]:
    """Parse the ``"earnings":[...]`` JSON blob embedded in the page."""
    match = _EARNINGS_ARRAY_RE.search(html)
    if not match:
        return []

    try:
        items = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.debug("Investing.com: earnings JSON decode failed: %s", exc)
        return []

    records: list[dict[str, Any]] = []
    for obj in items:
        if not isinstance(obj, dict):
            continue
        row = _row_from_investing_obj(obj)
        if row is None:
            continue
        if row["actualEarningsPerShare"] is None and row["actualRevenue"] is None:
            continue
        records.append(row)
        if len(records) >= limit:
            break
    return records


def _records_from_next_data(html: str, limit: int) -> list[dict[str, Any]]:
    """Walk ``__NEXT_DATA__`` for ``earningsStore.earnings``."""
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    earnings = (
        data.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("earningsStore", {})
        .get("earnings")
    )
    if not isinstance(earnings, list):
        return []

    records: list[dict[str, Any]] = []
    for obj in earnings:
        if not isinstance(obj, dict):
            continue
        row = _row_from_investing_obj(obj)
        if row is None:
            continue
        if row["actualEarningsPerShare"] is None and row["actualRevenue"] is None:
            continue
        records.append(row)
        if len(records) >= limit:
            break
    return records


def _records_from_html_tables(html: str, limit: int) -> list[dict[str, Any]]:
    """Fallback: parse visible HTML tables if JSON is missing."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    records: list[dict[str, Any]] = []

    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not headers:
            continue
        header_blob = " ".join(headers)
        if "eps" not in header_blob and "earnings" not in header_blob:
            continue

        def _col_idx(*needles: str) -> int | None:
            for i, h in enumerate(headers):
                if any(n in h for n in needles):
                    return i
            return None

        idx_date = _col_idx("date", "release", "period")
        idx_eps_act = _col_idx("eps actual", "actual eps", "reported")
        idx_eps_est = _col_idx("eps forecast", "eps estimate", "forecast", "consensus")
        idx_rev_act = _col_idx("revenue actual", "actual revenue")
        idx_rev_est = _col_idx("revenue forecast", "revenue estimate")

        if idx_eps_act is None and idx_eps_est is None:
            continue

        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 3:
                continue

            def _cell(idx: int | None) -> str | None:
                if idx is None or idx >= len(cells):
                    return None
                return cells[idx]

            row = {
                "date": _cell(idx_date) or "",
                "actualRevenue": _parse_amount(_cell(idx_rev_act) or ""),
                "estimatedRevenue": _parse_amount(_cell(idx_rev_est) or ""),
                "actualEarningsPerShare": _parse_eps(_cell(idx_eps_act) or ""),
                "estimatedEarningsPerShare": _parse_eps(_cell(idx_eps_est) or ""),
            }
            if (
                row["actualEarningsPerShare"] is None
                and row["actualRevenue"] is None
            ):
                continue
            records.append(row)
            if len(records) >= limit:
                return records

        if records:
            return records

    return records


def _records_from_html(html: str, limit: int = 8) -> list[dict[str, Any]]:
    for parser in (
        _records_from_earnings_array,
        _records_from_next_data,
        _records_from_html_tables,
    ):
        records = parser(html, limit)
        if records:
            return records[:limit]
    return []


def _extract_instrument_id_from_html(html: str) -> int | None:
    """Try to pull the instrument_id from __NEXT_DATA__ or embedded analytics."""
    for pattern in (
        r'"instrument_id"\s*:\s*(\d+)',
        r'"pair_id"\s*:\s*(\d+)',
        r'"instrumentId"\s*:\s*(\d+)',
    ):
        for match in re.finditer(pattern, html):
            iid = int(match.group(1))
            if iid > 0:
                return iid
    return None


def _slug_candidates(slug: str) -> list[str]:
    """Return Investing.com equity slug variants to try (most specific first)."""
    candidates = [slug]
    if not slug.endswith("-bhd") and not slug.endswith("-holdings"):
        alt = f"{slug}-bhd"
        if alt not in candidates:
            candidates.append(alt)
    return candidates


def _slug_suffix_variants(slug: str) -> list[str]:
    candidates: list[str] = []
    if slug.endswith("-berhad"):
        candidates.append(slug[:-len("-berhad")] + "-bhd")
        candidates.append(slug)
        candidates.append(slug[:-len("-berhad")].rstrip("-"))
    elif slug.endswith("-bhd"):
        candidates.append(slug)
        candidates.append(slug[:-len("-bhd")].rstrip("-"))
    else:
        candidates.append(slug)
        candidates.append(f"{slug}-bhd")
    return candidates


def _abbreviated_slug_variants(slug: str) -> list[str]:
    """Add common Investing.com abbreviations seen in Bursa equity slugs."""
    variants = [slug]
    replacements = (
        ("real-estate-investment-trust", "real-estate-inv-trust"),
        ("development", "develop"),
        ("corporation", "corp"),
    )
    for source, target in replacements:
        if source in slug:
            variants.append(slug.replace(source, target))
    return list(dict.fromkeys(variants))


def _normalize_description_slug(description: str, *, keep_parentheses: bool) -> str:
    slug = description.lower().strip()
    if keep_parentheses:
        slug = re.sub(r'[.,\[\]\'"]', '', slug)
    else:
        slug = re.sub(r'[.,\(\)\[\]\'"]', '', slug)
    slug = slug.replace("&", "and")
    slug = re.sub(r"\s+", "-", slug).strip("-")
    return slug


def _slugs_from_description(description: str) -> list[str]:
    """Derive Investing.com slug candidates from a TradingView company name.

    E.g. "YTL Power International Bhd." -> ["ytl-power-international-bhd",
    "ytl-power-international"]
    """
    candidates: list[str] = []
    normalized = [
        _normalize_description_slug(description, keep_parentheses=True),
        _normalize_description_slug(description, keep_parentheses=False),
    ]
    for slug in dict.fromkeys(s for s in normalized if s):
        for variant in _abbreviated_slug_variants(slug):
            candidates.extend(_slug_suffix_variants(variant))

    return list(dict.fromkeys(candidates))


# ── Scrapling-based fallback ─────────────────────────────────────────────────


def _fetch_via_scrapling(
    ticker: str,
    limit: int,
    candidates: list[str],
    *,
    cache_key: str | None = None,
) -> list[dict[str, Any]]:
    """Slow path: load the full page with Scrapling headless browser."""
    from .scrapling_utils import fetch_html_stealth

    resolved_cache_key = cache_key or ticker.upper()
    last_html_len = 0
    for try_slug in candidates:
        url = f"{_INVESTING_BASE}/equities/{try_slug}-earnings"
        html = fetch_html_stealth(url, site="investing.com")
        if not html:
            continue
        last_html_len = len(html)

        iid = _extract_instrument_id_from_html(html)
        if iid is not None and iid > 0 and resolved_cache_key not in _instrument_id_cache:
            _instrument_id_cache[resolved_cache_key] = iid
            logger.info(
                "Investing.com: cached instrument_id=%d for %s from Scrapling page",
                iid, ticker,
            )

        records = _records_from_html(html, limit=limit)
        if records:
            logger.info(
                "Investing.com (Scrapling): parsed %d earnings row(s) for %s (slug: %s)",
                len(records), ticker, try_slug,
            )
            return records

    if last_html_len:
        logger.warning(
            "Investing.com: no earnings parsed for %s via Scrapling (html_len=%d)",
            ticker, last_html_len,
        )
    return []


# ── Public API ───────────────────────────────────────────────────────────────


def fetch_earnings_surprises(
    ticker: str,
    limit: int = 8,
    *,
    description: str | None = None,
    identity: InstrumentIdentity | None = None,
    allow_fallback: bool = True,
) -> list[dict[str, Any]]:
    """Fetch EPS/revenue actual vs forecast rows from Investing.com.

    Tries the fast JSON API first after resolving the Investing.com instrument
    with exchange-qualified identity metadata. Falls back to the full Scrapling
    page load only when the fast path cannot resolve an ID or returns no data.
    """
    upper = ticker.upper()
    slug = _INVESTING_EQUITY_SLUGS.get(upper)
    cache_key = identity.cache_key if identity else upper

    # ── Fast path: direct JSON API (requires guest Bearer JWT) ───────────
    instrument_id = _get_instrument_id(
        upper, slug=slug, description=description, identity=identity,
    )
    bearer = _InvestingAuthSession.get_bearer()
    if instrument_id is not None and bearer:
        records = _fetch_earnings_api(instrument_id, limit=limit, bearer_token=bearer)
        if records:
            logger.info(
                "Investing.com API: parsed %d earnings for %s (id=%d)",
                len(records), ticker, instrument_id,
            )
            return records
        logger.info(
            "Investing.com API: no earnings rows for %s (id=%d)",
            ticker, instrument_id,
        )
    elif instrument_id is not None and not bearer:
        logger.info(
            "Investing.com API: no bearer token available for %s",
            ticker,
        )

    if not allow_fallback:
        logger.info("Investing.com: skipping Scrapling fallback for %s", ticker)
        return []

    # ── Slow path: Scrapling page load ───────────────────────────────────
    resolved_slug = _get_equity_slug(
        upper, static_slug=slug, description=description, identity=identity,
    )
    if resolved_slug:
        candidates = _slug_candidates(resolved_slug)
    elif description:
        candidates = _slugs_from_description(description)
        logger.info(
            "Investing.com: no static slug for %s, trying dynamic slugs from description '%s'",
            ticker, description,
        )
    else:
        logger.info("Investing.com: no slug mapping for %s", ticker)
        return []

    return _fetch_via_scrapling(ticker, limit, candidates, cache_key=cache_key)
