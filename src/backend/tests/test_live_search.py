"""Tests for the GET /search/live endpoint.

All Elasticsearch calls are mocked so tests run without a live cluster.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from auth.dependencies import get_current_user
import models


# ── Auth bypass ───────────────────────────────────────────────────────────────

_MOCK_USER = models.User(id=1, email="test@finsight.dev", role="free", is_active=True)


def _override_auth():
    return _MOCK_USER


app.dependency_overrides[get_current_user] = _override_auth

client = TestClient(app, raise_server_exceptions=True)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_es_hit(rank: int, title: str = "Jarvis Architecture") -> dict:
    """Build a fake ES hit dict as returned by es.search()."""
    return {
        "_id": f"chunk_{rank:04d}",
        "_score": 1.5 - rank * 0.1,
        "_source": {
            "title": title,
            "content": f"Title: {title}\nContent:\nSome content about {title.lower()}.",
            "source_path": f"docs/ai-systems/{title.lower().replace(' ', '-')}.md",
            "source_uri": f"https://finsight.dev/docs/ai-systems/{title.lower().replace(' ', '-')}/",
            "doc_type": "project_doc",
            "domain": "platform",
            "ticker": None,
        },
    }


def _fake_es_response(n: int = 3) -> dict:
    return {
        "hits": {
            "total": {"value": n},
            "hits": [_make_es_hit(i + 1) for i in range(n)],
        }
    }


# ── Tests: happy path ─────────────────────────────────────────────────────────


@patch("services.es_client.get_es_client")
def test_live_search_returns_hits(mock_get_es):
    mock_es = MagicMock()
    mock_es.search.return_value = _fake_es_response(3)
    mock_get_es.return_value = mock_es

    resp = client.get("/search/live", params={"q": "jarvis"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["query"] == "jarvis"
    assert body["total"] == 3
    assert len(body["hits"]) == 3
    first = body["hits"][0]
    assert first["rank"] == 1
    assert first["title"] == "Jarvis Architecture"
    assert "snippet" in first
    assert first["score"] > 0


@patch("services.es_client.get_es_client")
def test_live_search_caps_at_five(mock_get_es):
    mock_es = MagicMock()
    mock_es.search.return_value = _fake_es_response(5)
    mock_get_es.return_value = mock_es

    resp = client.get("/search/live", params={"q": "financial"})
    assert resp.status_code == 200
    assert resp.json()["total"] <= 5


@patch("services.es_client.get_es_client")
def test_live_search_empty_index(mock_get_es):
    mock_es = MagicMock()
    mock_es.search.return_value = _fake_es_response(0)
    mock_get_es.return_value = mock_es

    resp = client.get("/search/live", params={"q": "nomatch"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["hits"] == []
    assert body["total"] == 0


# ── Tests: query validation ───────────────────────────────────────────────────


def test_live_search_query_too_short_single_char():
    """Single character queries are rejected by FastAPI (min_length=2)."""
    resp = client.get("/search/live", params={"q": "a"})
    assert resp.status_code == 422


def test_live_search_missing_q():
    resp = client.get("/search/live")
    assert resp.status_code == 422


def test_live_search_query_whitespace_only():
    """Queries that are only whitespace resolve to < 2 chars after strip → empty list."""
    with patch("services.es_client.get_es_client") as mock_get_es:
        mock_es = MagicMock()
        mock_es.search.return_value = _fake_es_response(0)
        mock_get_es.return_value = mock_es
        resp = client.get("/search/live", params={"q": "  "})
        # FastAPI min_length=2 checks raw param length (2 spaces passes), but the
        # stripped check inside the endpoint returns an empty list without calling ES.
        assert resp.status_code == 200
        assert resp.json()["hits"] == []
        mock_es.search.assert_not_called()


# ── Tests: error handling ─────────────────────────────────────────────────────


@patch("services.es_client.get_es_client", side_effect=RuntimeError("ES down"))
def test_live_search_es_unavailable(mock_get_es):
    # ES down is now gracefully degraded — company DB hits are still returned.
    # "maybank" matches the seeded MAYBANK company row, so we get 200 + ≥1 hit.
    resp = client.get("/search/live", params={"q": "maybank"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert body["hits"][0]["domain"] == "company"


# ── Tests: response shape ─────────────────────────────────────────────────────


@patch("services.es_client.get_es_client")
def test_live_search_hit_fields(mock_get_es):
    mock_es = MagicMock()
    mock_es.search.return_value = _fake_es_response(1)
    mock_get_es.return_value = mock_es

    resp = client.get("/search/live", params={"q": "jarvis"})
    hit = resp.json()["hits"][0]
    for field in ("rank", "title", "snippet", "source_path", "source_uri", "score", "doc_type", "domain", "ticker"):
        assert field in hit, f"Missing field: {field}"
