"""Offline tests for Investing.com embedded earnings JSON parsing."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "scraper"))

from ml_features.investing_com import (  # noqa: E402
    _extract_equity_slug_from_quote,
    _fetch_earnings_api,
    _get_equity_slug,
    _get_instrument_id,
    fetch_earnings_surprises,
    _equity_slug_cache,
    _instrument_search_queries,
    _jwt_exp,
    _records_from_html,
    _resolve_equity_via_search,
    _score_search_result,
    _row_from_api_obj,
    _slug_candidates,
    _slugs_from_description,
)
from ml_features.scrapling_utils import _extract_bearer_from_html  # noqa: E402
from ml_features.types import InstrumentIdentity, _INVESTING_EQUITY_SLUGS  # noqa: E402

SAMPLE = """
<html><body><script id="__NEXT_DATA__" type="application/json">{
  "props": {"pageProps": {"state": {"earningsStore": {"earnings": [
    {"date": "2026-05-28T00:00:00.000Z", "epsActual": 0.2053, "epsForecast": 0.2205,
     "revenueActual": 6940000000, "revenueForecast": 7880000000},
    {"date": "2026-02-26T00:00:00.000Z", "epsActual": 0.2215, "epsForecast": 0.1996,
     "revenueActual": 7860000000, "revenueForecast": 7630000000}
  ]}}}}
}</script></body></html>
"""


def test_records_from_next_data():
    records = _records_from_html(SAMPLE, limit=8)
    assert len(records) == 2
    assert records[0]["actualEarningsPerShare"] == 0.2053
    assert records[0]["estimatedRevenue"] == 7880000000.0


def test_investing_slug_mappings_use_bhd_suffix_for_klse_utilities():
    assert _INVESTING_EQUITY_SLUGS["TNB"] == "tenaga-nasional-bhd"
    assert _INVESTING_EQUITY_SLUGS["TELEKOM"] == "telekom-malaysia-bhd"


def test_slug_candidates_adds_bhd_fallback():
    assert _slug_candidates("tenaga-nasional") == [
        "tenaga-nasional",
        "tenaga-nasional-bhd",
    ]
    assert _slug_candidates("malayan-banking-bhd") == ["malayan-banking-bhd"]
    assert _slug_candidates("cimb-group-holdings") == ["cimb-group-holdings"]


def test_row_from_api_obj_maps_snake_case_fields():
    row = _row_from_api_obj({
        "date": "2024-08-21",
        "eps_actual": 0.0535,
        "eps_forecast": 0.05,
        "revenue_actual": 7530000000,
        "revenue_forecast": 7530000000,
    })
    assert row is not None
    assert row["actualEarningsPerShare"] == 0.0535
    assert row["estimatedRevenue"] == 7530000000.0


def test_jwt_exp_decodes_expiry():
    token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJleHAiOjE3ODA3NjQ0MjIsImlhdCI6MTc4MDc2MDgyMn0."
        "signature"
    )
    assert _jwt_exp(token) == 1780764422.0


def test_fetch_earnings_api_requires_bearer_token():
    assert _fetch_earnings_api(41640, limit=8, bearer_token=None) == []


def test_fetch_earnings_surprises_can_skip_scrapling_fallback(monkeypatch):
    monkeypatch.setattr("ml_features.investing_com._get_instrument_id", lambda *args, **kwargs: None)
    monkeypatch.setattr("ml_features.investing_com._InvestingAuthSession.get_bearer", lambda: None)

    def fail_fetch(*args, **kwargs):
        raise AssertionError("Scrapling fallback should not be called")

    monkeypatch.setattr("ml_features.investing_com._fetch_via_scrapling", fail_fetch)

    assert fetch_earnings_surprises(
        "SLOW",
        description="Slow Example Bhd.",
        allow_fallback=False,
    ) == []


def test_extract_bearer_from_html_finds_guest_jwt():
    html = '<script>window.__token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE5OTk5OTk5OTl9.sig";</script>'
    token = _extract_bearer_from_html(html)
    assert token is not None
    assert token.startswith("eyJ")


def test_instrument_search_queries_try_slug_after_description():
    queries = _instrument_search_queries(
        "CBHB",
        description="CBH Engineering Holding Berhad",
    )
    assert queries[0] == "CBH Engineering Holding Berhad"
    assert "cbh-engineering-holding-bhd" in queries
    assert queries[-1] == "CBHB"


def test_slugs_from_description_handles_investing_abbreviations_and_parentheses():
    assert "pavilion-real-estate-inv-trust" in _slugs_from_description(
        "Pavilion Real Estate Investment Trust"
    )
    assert "eco-world-develop-group" in _slugs_from_description(
        "Eco World Development Group Bhd."
    )
    assert "aeon-credit-service-(m)-bhd" in _slugs_from_description(
        "AEON Credit Service (M) Bhd."
    )


def test_extract_equity_slug_from_search_quote_handles_nested_urls():
    quote = {
        "id": 950185,
        "flag": "MY",
        "exchange": "Kuala Lumpur",
        "link": "https://www.investing.com/equities/aeon-credit-service-(m)-bhd-earnings",
    }
    assert _extract_equity_slug_from_quote(quote) == "aeon-credit-service-(m)-bhd"


def test_instrument_search_queries_include_identity_context():
    identity = InstrumentIdentity.from_yahoo_symbol(
        yahoo_symbol="5139.KL",
        ticker="AEONCR",
        name="AEON Credit Service (M) Bhd.",
        isin="MYL5139OO005",
        investing_instrument_id=950185,
    )
    queries = _instrument_search_queries(
        "AEONCR",
        description="AEON Credit Service (M) Bhd.",
        identity=identity,
    )

    assert queries[:5] == [
        "MYL5139OO005",
        "950185",
        "AEONCR Kuala Lumpur",
        "AEONCR Malaysia",
        "AEONCR MYR",
    ]


def test_get_equity_slug_uses_search_canonical_slug(monkeypatch):
    _equity_slug_cache.pop("DYNAMIC", None)
    identity = InstrumentIdentity.from_yahoo_symbol(
        yahoo_symbol="1234.KL",
        ticker="DYNAMIC",
        name="Dynamic Example Bhd.",
    )

    def fake_resolve(query: str, *, identity=None):
        assert query
        assert identity is not None
        return 123, "dynamic-canonical-slug"

    monkeypatch.setattr(
        "ml_features.investing_com._resolve_equity_via_search",
        fake_resolve,
    )

    assert _get_equity_slug(
        "DYNAMIC",
        description="Dynamic Example Bhd.",
        identity=identity,
    ) == "dynamic-canonical-slug"
    assert _equity_slug_cache[identity.cache_key] == "dynamic-canonical-slug"


def test_get_instrument_id_uses_identity_investing_id():
    from ml_features.investing_com import _instrument_id_cache

    identity = InstrumentIdentity.from_yahoo_symbol(
        yahoo_symbol="5139.KL",
        ticker="AEONCR",
        investing_instrument_id=950185,
    )
    _instrument_id_cache.pop(identity.cache_key, None)

    assert _get_instrument_id("AEONCR", identity=identity) == 950185
    assert _instrument_id_cache[identity.cache_key] == 950185


def test_score_search_result_prefers_exchange_qualified_identity():
    identity = InstrumentIdentity.from_yahoo_symbol(
        yahoo_symbol="5139.KL",
        ticker="AEONCR",
        name="AEON Credit Service (M) Bhd.",
    )
    malaysia_result = {
        "id": 950185,
        "symbol": "AEONCR",
        "name": "AEON Credit Service (M) Bhd.",
        "exchange": "Kuala Lumpur",
        "country": "Malaysia",
        "currency": "MYR",
        "url": "/equities/aeon-credit-service-(m)-bhd-earnings",
    }
    foreign_result = {
        "id": 111,
        "symbol": "AEONCR",
        "name": "AEON Credit Holdings",
        "exchange": "Tokyo",
        "country": "Japan",
        "currency": "JPY",
        "url": "/equities/aeon-credit-holdings-earnings",
    }

    assert _score_search_result(malaysia_result, identity) > _score_search_result(
        foreign_result, identity,
    )


def test_resolve_equity_via_search_rejects_ambiguous_identity_match(monkeypatch):
    identity = InstrumentIdentity.from_yahoo_symbol(
        yahoo_symbol="5139.KL",
        ticker="AEONCR",
        name="AEON Credit Service (M) Bhd.",
    )

    monkeypatch.setattr(
        "ml_features.investing_com._search_quotes",
        lambda query: [
            {
                "id": 1,
                "symbol": "AEONCR",
                "name": "AEON Credit Service (M) Bhd.",
                "exchange": "Kuala Lumpur",
                "country": "Malaysia",
                "currency": "MYR",
                "url": "/equities/aeon-credit-service-(m)-bhd-earnings",
            },
            {
                "id": 2,
                "symbol": "AEONCR",
                "name": "AEON Credit Service (M) Bhd.",
                "exchange": "Kuala Lumpur",
                "country": "Malaysia",
                "currency": "MYR",
                "url": "/equities/aeon-credit-service-alt-earnings",
            },
        ],
    )

    assert _resolve_equity_via_search("AEONCR", identity=identity) == (None, None)


def test_resolve_equity_via_search_returns_ranked_canonical_slug(monkeypatch):
    identity = InstrumentIdentity.from_yahoo_symbol(
        yahoo_symbol="5139.KL",
        ticker="AEONCR",
        name="AEON Credit Service (M) Bhd.",
    )

    monkeypatch.setattr(
        "ml_features.investing_com._search_quotes",
        lambda query: [
            {
                "id": 111,
                "symbol": "AEONCR",
                "name": "AEON Credit Holdings",
                "exchange": "Tokyo",
                "country": "Japan",
                "currency": "JPY",
                "url": "/equities/aeon-credit-holdings-earnings",
            },
            {
                "id": 950185,
                "symbol": "AEONCR",
                "name": "AEON Credit Service (M) Bhd.",
                "exchange": "Kuala Lumpur",
                "country": "Malaysia",
                "currency": "MYR",
                "url": "/equities/aeon-credit-service-(m)-bhd-earnings",
            },
        ],
    )

    assert _resolve_equity_via_search("AEONCR", identity=identity) == (
        950185,
        "aeon-credit-service-(m)-bhd",
    )


def test_get_instrument_id_cbhb_uses_slug_fallback_query(monkeypatch):
    from ml_features.investing_com import _instrument_id_cache

    _instrument_id_cache.pop("CBHB", None)

    def fake_resolve(query: str, *, identity=None):
        if query == "cbh-engineering-holding-bhd":
            return 1225495, "cbh-engineering-holding-bhd"
        return None, None

    monkeypatch.setattr(
        "ml_features.investing_com._resolve_equity_via_search",
        fake_resolve,
    )

    iid = _get_instrument_id(
        "CBHB",
        description="CBH Engineering Holding Berhad",
    )
    assert iid == 1225495


if __name__ == "__main__":
    test_records_from_next_data()
    print("all tests passed")
