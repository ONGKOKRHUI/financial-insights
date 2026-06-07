"""Unit tests for i3investor embedded-json parsers (offline fixtures)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRAPER = REPO / "src" / "scraper"
sys.path.insert(0, str(SCRAPER))

from ml_features import i3investor  # noqa: E402


FINANCIAL_FIXTURE = """
<html><body><script>
var dtdata = [
  ["31-Dec-2025","26-Feb-2026","31-Dec-2025","4","10,000","2,000","1,500","1,400"],
  ["31-Dec-2025","21-Nov-2025","30-Sep-2025","3","9,000","1,800","1,350","1,300"]
];
</script></body></html>
"""

DIRECTOR_FIXTURE = """
<html><body><script>
var dtdata_holder = [
  ["29-May-2026","DIRECTOR A","28-May-2026","Acquired","10,000","10.00","0","0","0"],
  ["29-May-2026","DIRECTOR B","28-May-2026","Disposed","5,000","10.00","0","0","0"],
  ["01-Jan-2020","OLD","01-Jan-2020","Acquired","1,000","1.00","0","0","0"]
];
</script></body></html>
"""

SUBSTANTIAL_FIXTURE = """
<html><body><script>
var dtdata_holder = [
  ["29-May-2026","EMPLOYEES PROVIDENT FUND BOARD","28-May-2026","Acquired","1,000,000","0.000","0","0","0"],
  ["29-May-2026","EMPLOYEES PROVIDENT FUND BOARD","28-May-2026","Disposed","200,000","0.000","0","0","0"],
  ["29-May-2026","PRIVATE SUBSTANTIAL HOLDER","28-May-2026","Acquired","50,000","0.000","0","0","0"],
  ["01-Jan-2020","EMPLOYEES PROVIDENT FUND BOARD","01-Jan-2020","Acquired","1,000","1.00","0","0","0"]
];
</script></body></html>
"""


def test_extract_embedded_json_financial():
    rows = i3investor._extract_embedded_json(FINANCIAL_FIXTURE, preferred_names=("dtdata",))
    assert rows is not None
    assert len(rows) == 2


def test_compute_margin_deltas_qoq():
    quarters = [
        {"quarter_end": i3investor._parse_i3_date("31-Dec-2025"), "revenue": 10000.0, "pbt": 2000.0, "net_profit": 1500.0},
        {"quarter_end": i3investor._parse_i3_date("30-Sep-2025"), "revenue": 9000.0, "pbt": 1800.0, "net_profit": 1350.0},
    ]
    pbt_delta, np_delta = i3investor.compute_margin_deltas_qoq(quarters)
    assert abs(pbt_delta) < 1e-9
    assert abs(np_delta) < 1e-9


def _patch_today(monkeypatch):
    from datetime import date as real_date

    class _FixedDate(real_date):
        @classmethod
        def today(cls):
            return real_date(2026, 5, 31)

    monkeypatch.setattr(i3investor, "date", _FixedDate)


def test_fetch_director_net_flow_from_fixture(monkeypatch):
    monkeypatch.setattr(i3investor, "_fetch_page", lambda url: DIRECTOR_FIXTURE)
    _patch_today(monkeypatch)
    net, counted = i3investor.fetch_director_net_flow_myr("1155", days_lookback=90)
    assert counted == 2
    assert abs(net - 50_000.0) < 1e-6


def test_fetch_institutional_net_flow_filters_and_uses_fallback_price(monkeypatch):
    monkeypatch.setattr(i3investor, "_fetch_page", lambda url: SUBSTANTIAL_FIXTURE)
    _patch_today(monkeypatch)
    net, counted = i3investor.fetch_institutional_net_flow_myr(
        "1155",
        days_lookback=90,
        fallback_price=10.0,
    )
    # EPF only: acquired 1,000,000 - disposed 200,000 at fallback 10.0
    assert counted == 2
    assert abs(net - 8_000_000.0) < 1e-6


def test_fetch_insider_net_flow_alias(monkeypatch):
    monkeypatch.setattr(i3investor, "_fetch_page", lambda url: DIRECTOR_FIXTURE)
    _patch_today(monkeypatch)
    net = i3investor.fetch_insider_net_flow_myr("1155", days_lookback=90)
    assert abs(net - 50_000.0) < 1e-6


def test_fetch_financial_quarter_rows_parsing(monkeypatch):
    monkeypatch.setattr(i3investor, "_fetch_page", lambda url: FINANCIAL_FIXTURE)
    rows = i3investor.fetch_financial_quarter_rows("1155")
    assert len(rows) == 2
    assert rows[0]["revenue"] == 10000.0
    assert rows[0]["pbt"] == 2000.0


class _MonkeyPatch:
    def setattr(self, target, name, value):
        setattr(target, name, value)


if __name__ == "__main__":
    patch = _MonkeyPatch()
    test_extract_embedded_json_financial()
    test_compute_margin_deltas_qoq()
    test_fetch_director_net_flow_from_fixture(patch)
    test_fetch_institutional_net_flow_filters_and_uses_fallback_price(patch)
    test_fetch_insider_net_flow_alias(patch)
    test_fetch_financial_quarter_rows_parsing(patch)
    print("all tests passed")
