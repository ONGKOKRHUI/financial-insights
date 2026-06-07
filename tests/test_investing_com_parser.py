"""Offline tests for Investing.com embedded earnings JSON parsing."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "scraper"))

from ml_features.investing_com import (  # noqa: E402
    _fetch_earnings_api,
    _get_instrument_id,
    _instrument_search_queries,
    _jwt_exp,
    _records_from_html,
    _row_from_api_obj,
    _slug_candidates,
)
from ml_features.scrapling_utils import _extract_bearer_from_html  # noqa: E402
from ml_features.types import _INVESTING_EQUITY_SLUGS  # noqa: E402

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


def test_get_instrument_id_cbhb_uses_slug_fallback_query():
    from ml_features.investing_com import _instrument_id_cache

    _instrument_id_cache.pop("CBHB", None)
    iid = _get_instrument_id(
        "CBHB",
        description="CBH Engineering Holding Berhad",
    )
    assert iid == 1225495


if __name__ == "__main__":
    test_records_from_next_data()
    print("all tests passed")
