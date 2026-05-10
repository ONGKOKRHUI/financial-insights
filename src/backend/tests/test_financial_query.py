"""Tests for Intent 2 — financial_query service.

Coverage:
    - MetricSpec catalog completeness checks
    - resolve_ticker: exact tickers, aliases, partial matches, unknown companies
    - resolve_metric: exact aliases, partial aliases, unknown metrics
    - parse_fiscal_year: explicit years, FY prefix, relative terms, None
    - lookup_financial_metric: found, missing row, null value (mocked DB)
    - query_financial_intent: full path, missing company, missing metric
    - handle_financial: Jarvis output shape (mocked query_financial_intent)
    - Future-data adaptation: adding new catalog entry does not break existing logic
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_income_row(ticker="MAYBANK", fiscal_year=2024, revenue_bln=30.2,
                     net_income_bln=9.1, eps=0.86, gross_profit_bln=22.8,
                     operating_income_bln=12.4, gross_margin_pct=75.5,
                     operating_margin_pct=41.1, net_margin_pct=30.1):
    row = MagicMock()
    row.ticker = ticker
    row.fiscal_year = fiscal_year
    row.revenue_bln = revenue_bln
    row.net_income_bln = net_income_bln
    row.eps = eps
    row.gross_profit_bln = gross_profit_bln
    row.operating_income_bln = operating_income_bln
    row.gross_margin_pct = gross_margin_pct
    row.operating_margin_pct = operating_margin_pct
    row.net_margin_pct = net_margin_pct
    return row


def _make_kpi_row(ticker="MAYBANK", fiscal_year=2024, pe_ratio=12.4,
                  roe_pct=10.8, roace_pct=8.2, debt_to_equity=0.92,
                  dividend_yield_pct=5.8, revenue_bln=30.2,
                  net_income_bln=9.1, eps=0.86):
    row = MagicMock()
    row.ticker = ticker
    row.fiscal_year = fiscal_year
    row.pe_ratio = pe_ratio
    row.roe_pct = roe_pct
    row.roace_pct = roace_pct
    row.debt_to_equity = debt_to_equity
    row.dividend_yield_pct = dividend_yield_pct
    row.revenue_bln = revenue_bln
    row.net_income_bln = net_income_bln
    row.eps = eps
    return row


# ── MetricSpec catalog ─────────────────────────────────────────────────────────


class TestMetricCatalog:
    def test_catalog_is_non_empty(self):
        from services.financial_query import METRIC_CATALOG
        assert len(METRIC_CATALOG) > 0

    def test_every_spec_has_required_fields(self):
        from services.financial_query import METRIC_CATALOG
        for spec in METRIC_CATALOG:
            assert spec.canonical_name, f"Empty canonical_name in {spec}"
            assert spec.aliases, f"No aliases for {spec.canonical_name}"
            assert spec.statement_type in (
                "income_statement", "balance_sheet", "cash_flow", "kpi", "qualitative"
            ), f"Unknown statement_type '{spec.statement_type}' in {spec.canonical_name}"
            assert spec.field_name, f"Empty field_name in {spec.canonical_name}"
            assert spec.unit, f"Empty unit in {spec.canonical_name}"
            assert spec.source_type in (
                "financial_report", "derived", "external_market"
            ), f"Unknown source_type '{spec.source_type}' in {spec.canonical_name}"

    def test_all_aliases_are_lowercase(self):
        from services.financial_query import METRIC_CATALOG
        for spec in METRIC_CATALOG:
            for alias in spec.aliases:
                assert alias == alias.lower(), (
                    f"Alias '{alias}' in {spec.canonical_name} is not lowercase"
                )

    def test_key_metrics_present(self):
        """Core financial metrics that Jarvis must always support."""
        from services.financial_query import resolve_metric
        required = [
            "revenue", "net income", "eps", "p/e ratio",
            "roe", "free cash flow", "operating income",
            "gross margin", "net margin", "total assets",
            "debt to equity", "dividend yield",
        ]
        for metric_text in required:
            spec = resolve_metric(metric_text)
            assert spec is not None, f"Core metric '{metric_text}' not found in catalog"

    def test_adding_new_catalog_entry_does_not_break_existing(self):
        """Simulate adding a hypothetical new metric; existing lookups unaffected.

        The production workflow for a new metric is:
          1. Append to METRIC_CATALOG.
          2. Add the aliases to _ALIAS_TO_METRIC so resolve_metric picks them up.
          3. The test verifies that existing metrics still resolve correctly.
        """
        from services.financial_query import METRIC_CATALOG, MetricSpec, _ALIAS_TO_METRIC, resolve_metric

        new_spec = MetricSpec(
            canonical_name="test_new_metric",
            aliases=["test metric placeholder xyz"],
            statement_type="kpi",
            field_name="pe_ratio",
            unit="x",
            source_type="external_market",
        )
        original_count = len(METRIC_CATALOG)
        METRIC_CATALOG.append(new_spec)
        _ALIAS_TO_METRIC["test metric placeholder xyz"] = new_spec

        try:
            assert resolve_metric("revenue") is not None
            assert resolve_metric("test metric placeholder xyz") is not None
        finally:
            METRIC_CATALOG.pop()
            _ALIAS_TO_METRIC.pop("test metric placeholder xyz", None)
            assert len(METRIC_CATALOG) == original_count


# ── resolve_ticker ────────────────────────────────────────────────────────────


class TestResolveTicker:
    def test_exact_uppercase_ticker(self):
        from services.financial_query import resolve_ticker
        assert resolve_ticker("MAYBANK") == "MAYBANK"
        assert resolve_ticker("CIMB") == "CIMB"
        assert resolve_ticker("TNB") == "TNB"
        assert resolve_ticker("PETRONAS") == "PETRONAS"
        assert resolve_ticker("MAXIS") == "MAXIS"
        assert resolve_ticker("TM") == "TM"
        assert resolve_ticker("GENTING") == "GENTING"
        assert resolve_ticker("SUNWAY") == "SUNWAY"

    def test_lowercase_alias(self):
        from services.financial_query import resolve_ticker
        assert resolve_ticker("maybank") == "MAYBANK"
        assert resolve_ticker("tenaga nasional") == "TNB"
        assert resolve_ticker("telekom malaysia") == "TM"

    def test_full_legal_name(self):
        from services.financial_query import resolve_ticker
        assert resolve_ticker("Malayan Banking Berhad") == "MAYBANK"
        assert resolve_ticker("Tenaga Nasional Berhad") == "TNB"
        assert resolve_ticker("CIMB Group Holdings Berhad") == "CIMB"

    def test_partial_match(self):
        from services.financial_query import resolve_ticker
        assert resolve_ticker("genting group") == "GENTING"
        assert resolve_ticker("petronas") == "PETRONAS"

    def test_unknown_company_returns_none(self):
        from services.financial_query import resolve_ticker
        assert resolve_ticker("XYZ Unknown Corp") is None
        assert resolve_ticker("") is None
        assert resolve_ticker(None) is None  # type: ignore[arg-type]


# ── resolve_metric ────────────────────────────────────────────────────────────


class TestResolveMetric:
    def test_exact_alias_matches(self):
        from services.financial_query import resolve_metric
        spec = resolve_metric("revenue")
        assert spec is not None
        assert spec.canonical_name == "revenue"

    def test_case_insensitive(self):
        from services.financial_query import resolve_metric
        spec = resolve_metric("Revenue")
        assert spec is not None
        assert spec.canonical_name == "revenue"

    def test_pe_ratio_variants(self):
        from services.financial_query import resolve_metric
        for phrase in ("p/e ratio", "PE ratio", "price to earnings", "pe", "p/e"):
            spec = resolve_metric(phrase)
            assert spec is not None, f"'{phrase}' should resolve to pe_ratio"
            assert spec.canonical_name == "pe_ratio"

    def test_earnings_and_profit_resolve_to_net_income(self):
        from services.financial_query import resolve_metric
        spec = resolve_metric("net profit")
        assert spec is not None
        assert spec.canonical_name == "net_income"

    def test_free_cash_flow(self):
        from services.financial_query import resolve_metric
        spec = resolve_metric("FCF")
        assert spec is not None
        assert spec.canonical_name == "free_cash_flow"

    def test_unknown_metric_returns_none(self):
        from services.financial_query import resolve_metric
        assert resolve_metric("galactic flux density") is None
        assert resolve_metric("") is None
        assert resolve_metric(None) is None  # type: ignore[arg-type]

    def test_partial_metric_match(self):
        from services.financial_query import resolve_metric
        spec = resolve_metric("operating cash flow statement")
        assert spec is not None
        assert spec.canonical_name == "operating_cash_flow"


# ── parse_fiscal_year ─────────────────────────────────────────────────────────


class TestParseFiscalYear:
    def test_none_returns_none(self):
        from services.financial_query import parse_fiscal_year
        assert parse_fiscal_year(None) is None

    def test_explicit_year(self):
        from services.financial_query import parse_fiscal_year
        assert parse_fiscal_year("2024") == 2024
        assert parse_fiscal_year("2020") == 2020

    def test_fy_prefix(self):
        from services.financial_query import parse_fiscal_year
        assert parse_fiscal_year("FY2024") == 2024
        assert parse_fiscal_year("fy 2023") == 2023

    def test_last_year(self):
        from services.financial_query import parse_fiscal_year
        expected = date.today().year - 1
        assert parse_fiscal_year("last year") == expected
        assert parse_fiscal_year("previous year") == expected

    def test_this_year(self):
        from services.financial_query import parse_fiscal_year
        expected = date.today().year
        assert parse_fiscal_year("this year") == expected

    def test_years_ago(self):
        from services.financial_query import parse_fiscal_year
        expected = date.today().year - 2
        assert parse_fiscal_year("2 years ago") == expected

    def test_quarterly_period_extracts_year(self):
        from services.financial_query import parse_fiscal_year
        assert parse_fiscal_year("Q3 2024") == 2024
        assert parse_fiscal_year("q1 2022") == 2022

    def test_latest_returns_none(self):
        from services.financial_query import parse_fiscal_year
        assert parse_fiscal_year("latest") is None
        assert parse_fiscal_year("most recent") is None
        assert parse_fiscal_year("") is None


# ── lookup_financial_metric ───────────────────────────────────────────────────


class TestLookupFinancialMetric:
    """All DB calls are mocked — no live database required."""

    def _get_revenue_spec(self):
        from services.financial_query import resolve_metric
        return resolve_metric("revenue")

    def _get_pe_spec(self):
        from services.financial_query import resolve_metric
        return resolve_metric("p/e ratio")

    @patch("database.SessionLocal")
    def test_found_income_statement_metric(self, mock_session_cls):
        from services.financial_query import lookup_financial_metric

        db = MagicMock()
        mock_session_cls.return_value = db

        company_mock = MagicMock()
        company_mock.name = "Malayan Banking Berhad"
        row = _make_income_row()

        db.query.return_value.filter.return_value.first.return_value = company_mock
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row

        spec = self._get_revenue_spec()
        result = lookup_financial_metric("MAYBANK", spec, None)

        assert result.found is True
        assert result.ticker == "MAYBANK"
        assert result.value == 30.2
        assert "30.2" in result.message
        assert "FY2024" in result.message
        assert len(result.sources) == 1
        assert result.sources[0]["metadata"]["ticker"] == "MAYBANK"
        assert result.sources[0]["metadata"]["source_type"] == "financial_report"

    @patch("database.SessionLocal")
    def test_no_row_returns_not_found(self, mock_session_cls):
        from services.financial_query import lookup_financial_metric

        db = MagicMock()
        mock_session_cls.return_value = db

        company_mock = MagicMock()
        company_mock.name = "Malayan Banking Berhad"
        db.query.return_value.filter.return_value.first.return_value = company_mock
        # No row found for any fiscal year
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        spec = self._get_revenue_spec()
        result = lookup_financial_metric("MAYBANK", spec, None)

        assert result.found is False
        assert result.value is None
        assert "couldn't find" in result.message.lower() or "not available" in result.message.lower()

    @patch("database.SessionLocal")
    def test_null_field_returns_not_found(self, mock_session_cls):
        from services.financial_query import lookup_financial_metric

        db = MagicMock()
        mock_session_cls.return_value = db

        company_mock = MagicMock()
        company_mock.name = "Petroliam Nasional Berhad"

        row = MagicMock()
        row.fiscal_year = 2024
        row.pe_ratio = None  # PETRONAS has no P/E

        db.query.return_value.filter.return_value.first.return_value = company_mock
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row

        spec = self._get_pe_spec()
        result = lookup_financial_metric("PETRONAS", spec, None)

        assert result.found is False
        assert "not available" in result.message.lower()

    @patch("database.SessionLocal")
    def test_external_market_note_in_message(self, mock_session_cls):
        from services.financial_query import lookup_financial_metric

        db = MagicMock()
        mock_session_cls.return_value = db

        company_mock = MagicMock()
        company_mock.name = "Malayan Banking Berhad"
        row = _make_kpi_row()

        db.query.return_value.filter.return_value.first.return_value = company_mock
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row

        spec = self._get_pe_spec()
        result = lookup_financial_metric("MAYBANK", spec, None)

        assert result.found is True
        assert "market" in result.message.lower() or "externally" in result.message.lower()

    @patch("database.SessionLocal")
    def test_db_error_returns_graceful_fallback(self, mock_session_cls):
        from services.financial_query import lookup_financial_metric

        mock_session_cls.side_effect = Exception("DB connection refused")

        spec = self._get_revenue_spec()
        result = lookup_financial_metric("MAYBANK", spec, 2024)

        assert result.found is False
        assert result.message != ""


# ── query_financial_intent ────────────────────────────────────────────────────


class TestQueryFinancialIntent:
    @patch("services.financial_query.lookup_financial_metric")
    @patch("services.financial_query.resolve_ticker", return_value="MAYBANK")
    @patch("services.financial_query.resolve_metric")
    def test_happy_path(self, mock_metric, mock_ticker, mock_lookup):
        from services.financial_query import MetricSpec, query_financial_intent

        spec = MetricSpec("revenue", ["revenue"], "income_statement", "revenue_bln", "MYR billion", "financial_report")
        mock_metric.return_value = spec

        lookup_result = MagicMock()
        lookup_result.found = True
        lookup_result.message = "Malayan Banking Berhad's revenue for FY2024 was MYR 30.20 billion."
        lookup_result.voice = lookup_result.message
        lookup_result.sources = [{"title": "test", "source_path": "/search", "snippet": "...", "rank": 1}]
        lookup_result.ticker = "MAYBANK"
        lookup_result.fiscal_year = 2024
        mock_lookup.return_value = lookup_result

        result = query_financial_intent("Maybank", "revenue", "2024")

        assert result["found"] is True
        assert result["ticker"] == "MAYBANK"
        assert result["fiscal_year"] == 2024
        assert "30.20" in result["message"]
        assert len(result["sources"]) == 1

    def test_unknown_company(self):
        from services.financial_query import query_financial_intent
        result = query_financial_intent("XYZ Unknown Bank", "revenue", None)
        assert result["found"] is False
        assert result["ticker"] is None
        assert "couldn't identify" in result["message"].lower()

    @patch("services.financial_query.resolve_ticker", return_value="CIMB")
    def test_unknown_metric(self, _mock_ticker):
        from services.financial_query import query_financial_intent
        result = query_financial_intent("CIMB", "galactic flux density", None)
        assert result["found"] is False
        assert result["ticker"] == "CIMB"
        assert "couldn't map" in result["message"].lower()

    def test_no_company_no_metric(self):
        from services.financial_query import query_financial_intent
        result = query_financial_intent(None, None, None)
        assert result["found"] is False


# ── handle_financial (Jarvis output shape) ────────────────────────────────────


class TestHandleFinancial:
    """Verify handle_financial returns a valid Jarvis output shape.

    The financial_query service is mocked so these tests do not need a DB.
    """

    def _make_state(self, company="MAYBANK", metric="revenue", time_period="2024"):
        return {
            "raw_transcript": f"what is {company}'s {metric}",
            "session_id": "test-session",
            "refined_text": f"What is {company}'s {metric} for {time_period}?",
            "intent_id": 2,
            "intent_name": "FinancialInfo",
            "confidence": 0.99,
            "entities": {
                "company": company,
                "metric": metric,
                "time_period": time_period,
                "navigation_target": None,
            },
            "reasoning": "Financial metric requested.",
            "output": {},
        }

    @patch("services.financial_query.query_financial_intent")
    def test_output_shape_on_success(self, mock_query):
        from services.langgraph_intent import handle_financial

        mock_query.return_value = {
            "found": True,
            "message": "MAYBANK's revenue for FY2024 was MYR 30.20 billion.",
            "voice": "MAYBANK's revenue for FY2024 was MYR 30.20 billion.",
            "sources": [{"title": "test", "source_path": "/search", "snippet": "x", "rank": 1}],
            "ticker": "MAYBANK",
            "fiscal_year": 2024,
        }

        state = self._make_state()
        result = handle_financial(state)

        output = result["output"]
        assert output["action"] == "respond"
        assert output["target"] is None
        assert output["intent_id"] == 2
        assert output["engine"] == "langgraph"
        assert isinstance(output["sources"], list)
        assert output["confidence"] == 0.99
        assert "revenue" in output["message"].lower() or "30.20" in output["message"]

    @patch("services.financial_query.query_financial_intent")
    def test_output_shape_on_failure(self, mock_query):
        from services.langgraph_intent import handle_financial

        mock_query.return_value = {
            "found": False,
            "message": "I couldn't identify 'XYZ' as a company.",
            "voice": "I couldn't identify that company.",
            "sources": [],
            "ticker": None,
            "fiscal_year": None,
        }

        state = self._make_state(company="XYZ")
        result = handle_financial(state)

        output = result["output"]
        assert output["action"] == "respond"
        assert output["intent_id"] == 2
        assert output["sources"] == []
        assert output["message"] != ""

    @patch("services.financial_query.query_financial_intent")
    def test_voice_field_present(self, mock_query):
        from services.langgraph_intent import handle_financial

        mock_query.return_value = {
            "found": True,
            "message": "Some message.",
            "voice": "Voice version.",
            "sources": [],
            "ticker": "TNB",
            "fiscal_year": 2024,
        }

        state = self._make_state(company="TNB")
        result = handle_financial(state)
        assert "voice" in result["output"]
        assert result["output"]["voice"] == "Voice version."
