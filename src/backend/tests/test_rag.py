"""Tests for the Phase 5 RAG endpoint (POST /rag/ask).

All ES and LLM calls are mocked so these tests run without live services.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from auth.dependencies import require_api_key_or_session
import models


# ── Auth bypass ───────────────────────────────────────────────────────────────

_MOCK_USER = models.User(id=1, email="test@finsight.dev", role="paid", is_active=True)


def _override_auth():
    return _MOCK_USER


app.dependency_overrides[require_api_key_or_session] = _override_auth

client = TestClient(app, raise_server_exceptions=True)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_chunk(rank: int = 1, ticker: str | None = None):
    from services.rag_retriever import RetrievedChunk

    return RetrievedChunk(
        chunk_id=f"chunk_{rank:04d}",
        title="Jarvis Voice Assistant",
        source_path="/docs/readme_jarvis.md",
        heading_path=["readme_jarvis", "Jarvis Voice Assistant Features"],
        snippet="Hands-free navigation by voice using Gemini ASR.",
        content="Title: Jarvis Voice Assistant\nContent:\nHands-free navigation by voice.",
        doc_type="project_doc",
        domain="platform",
        ticker=ticker,
        tags=["voice", "jarvis"],
        rrf_score=1.0 / (60 + rank),
        rank=rank,
    )


def _make_retrieval_result(n_chunks: int = 3):
    from services.rag_retriever import RetrievalResult

    return RetrievalResult(
        chunks=[_make_chunk(rank=i + 1) for i in range(n_chunks)],
        lexical_hits=10,
        vector_hits=10,
        fused_hits=n_chunks,
        embedding_model="models/embedding-001",
    )


# ── Test: happy path ─────────────────────────────────────────────────────────

@patch("services.rag_retriever.retrieve")
@patch("services.rag_answer.generate_answer")
def test_rag_ask_happy_path(mock_answer, mock_retrieve):
    mock_retrieve.return_value = _make_retrieval_result(3)
    mock_answer.return_value = ("Jarvis supports voice navigation.", False, "high")

    resp = client.post(
        "/rag/ask",
        json={"question": "How does Jarvis voice navigation work?"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == "Jarvis supports voice navigation."
    assert body["confidence"] == "high"
    assert body["abstained"] is False
    assert len(body["sources"]) == 3
    assert body["retrieval"]["strategy"] == "hybrid_rrf"
    assert body["retrieval"]["lexical_hits"] == 10


# ── Test: abstention ─────────────────────────────────────────────────────────

@patch("services.rag_retriever.retrieve")
@patch("services.rag_answer.generate_answer")
def test_rag_ask_abstention(mock_answer, mock_retrieve):
    mock_retrieve.return_value = _make_retrieval_result(0)
    mock_answer.return_value = (
        "I could not find relevant documentation.",
        True,
        "low",
    )

    resp = client.post(
        "/rag/ask",
        json={"question": "What is the airspeed velocity of an unladen swallow?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["abstained"] is True
    assert body["confidence"] == "low"


# ── Test: sources excluded when include_sources=False ────────────────────────

@patch("services.rag_retriever.retrieve")
@patch("services.rag_answer.generate_answer")
def test_rag_ask_no_sources(mock_answer, mock_retrieve):
    mock_retrieve.return_value = _make_retrieval_result(2)
    mock_answer.return_value = ("Short answer.", False, "medium")

    resp = client.post(
        "/rag/ask",
        json={"question": "How do I use the API?", "include_sources": False},
    )
    assert resp.status_code == 200
    assert resp.json()["sources"] == []


# ── Test: scope and ticker forwarded to retriever ────────────────────────────

@patch("services.rag_retriever.retrieve")
@patch("services.rag_answer.generate_answer")
def test_rag_ask_scope_and_ticker_passed(mock_answer, mock_retrieve):
    mock_retrieve.return_value = _make_retrieval_result(1)
    mock_answer.return_value = ("Maybank info.", False, "medium")

    resp = client.post(
        "/rag/ask",
        json={
            "question": "Tell me about Maybank",
            "scope": "company",
            "ticker": "MAYBANK",
        },
    )
    assert resp.status_code == 200
    mock_retrieve.assert_called_once()
    call_kwargs = mock_retrieve.call_args.kwargs
    assert call_kwargs["scope"] == "company"
    assert call_kwargs["ticker"] == "MAYBANK"


# ── Test: top_k validation ────────────────────────────────────────────────────

def test_rag_ask_top_k_too_large():
    resp = client.post(
        "/rag/ask",
        json={"question": "test", "top_k": 99},
    )
    assert resp.status_code == 422


def test_rag_ask_question_too_short():
    resp = client.post(
        "/rag/ask",
        json={"question": "hi"},
    )
    assert resp.status_code == 422


# ── Test: retrieval service unavailable ──────────────────────────────────────

@patch("services.rag_retriever.retrieve", side_effect=ConnectionError("ES is down"))
def test_rag_ask_retrieval_failure(mock_retrieve):
    resp = client.post(
        "/rag/ask",
        json={"question": "What is the Jarvis ASR engine?"},
    )
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


# ── Test: RAG health endpoint ─────────────────────────────────────────────────

@patch("services.es_client.es_health")
def test_rag_health_with_es_up(mock_health):
    mock_health.return_value = {"status": "green", "url": "http://localhost:9200", "available": True}
    resp = client.get("/rag/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["elasticsearch"]["available"] is True


@patch("services.es_client.es_health")
def test_rag_health_with_es_down(mock_health):
    mock_health.return_value = {"status": "unavailable", "url": "http://localhost:9200", "available": False}
    resp = client.get("/rag/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"
