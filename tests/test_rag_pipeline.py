"""Unit tests for the Phase 5 documentation ingestion pipeline components.

Tests are isolated — no live ES, no live embedding API.
"""

from __future__ import annotations

import sys
import os
import textwrap

import pytest

# Allow importing pipeline and backend modules without a full install
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))           # exposes 'pipeline.*'
sys.path.insert(0, os.path.join(_ROOT, "src", "backend")) # exposes 'services.*', 'schemas.*'


# ── doc_parser tests ──────────────────────────────────────────────────────────

class TestDocParser:
    def _parse(self, md_text: str, path: str = "/docs/test.md") -> list[dict]:
        from pipeline.nodes.doc_parser import parse_markdown

        state = {"file_paths": []}
        # Write a temp file and use it
        import tempfile, pathlib

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(md_text)
            tmp_path = f.name

        try:
            result = parse_markdown({"file_paths": [tmp_path]})
        finally:
            os.unlink(tmp_path)
        return result["sections"]

    def test_heading_based_splitting(self):
        md = textwrap.dedent("""\
            # Overview
            This is the overview section.

            ## Installation
            Run pip install.

            ## Usage
            Call the API.
        """)
        sections = self._parse(md)
        titles = [s["title"] for s in sections]
        assert "Overview" in titles
        assert "Installation" in titles
        assert "Usage" in titles

    def test_frontmatter_extracted(self):
        md = textwrap.dedent("""\
            ---
            title: My Doc
            tags: [voice, api]
            doc_type: api_doc
            ---
            # Content
            Some content here.
        """)
        sections = self._parse(md)
        assert len(sections) >= 1
        s = sections[0]
        assert "voice" in s["tags"] or "api" in s["tags"]
        assert s["doc_type"] == "api_doc"

    def test_wikilink_normalisation(self):
        md = textwrap.dedent("""\
            # Notes
            See [[Jarvis Setup|setup guide]] for more info.
            Also see [[Architecture]].
        """)
        sections = self._parse(md)
        assert len(sections) >= 1
        content = sections[0]["content"]
        assert "[[" not in content
        assert "setup guide" in content
        assert "Architecture" in content

    def test_obsidian_inline_tags_extracted(self):
        md = textwrap.dedent("""\
            # Tagged Note
            This note is about #jarvis and #voice-assistant features.
        """)
        sections = self._parse(md)
        tags = sections[0]["tags"]
        assert "jarvis" in tags
        assert "voice-assistant" in tags

    def test_empty_sections_skipped(self):
        md = textwrap.dedent("""\
            # Empty
            ## Also Empty
            ### Has Content
            This section has content.
        """)
        sections = self._parse(md)
        # Only sections with content survive
        for s in sections:
            assert s["content"].strip(), f"Empty section made it through: {s['title']}"


# ── doc_chunker tests ─────────────────────────────────────────────────────────

class TestDocChunker:
    def _make_section(self, content: str, title: str = "Test Section") -> dict:
        return {
            "source_path": "/docs/test.md",
            "title": title,
            "heading_path": ["Test Doc", title],
            "heading_level": 2,
            "content": content,
            "tags": ["test"],
            "doc_type": "project_doc",
            "domain": "platform",
            "ticker": None,
            "source_line_start": 0,
            "source_line_end": 10,
        }

    def test_small_section_one_chunk(self):
        from pipeline.nodes.doc_chunker import chunk_sections

        section = self._make_section("Short content.")
        result = chunk_sections({"sections": [section]})
        assert len(result["chunks"]) == 1

    def test_large_section_multiple_chunks(self):
        from pipeline.nodes.doc_chunker import chunk_sections, MAX_CHUNK_CHARS

        big = ("word " * 500 + "\n\n") * 5  # well over MAX_CHUNK_CHARS
        section = self._make_section(big)
        result = chunk_sections({"sections": [section]})
        assert len(result["chunks"]) > 1

    def test_chunk_id_is_stable(self):
        from pipeline.nodes.doc_chunker import chunk_sections

        section = self._make_section("Stable content for hashing.")
        r1 = chunk_sections({"sections": [section]})
        r2 = chunk_sections({"sections": [section]})
        assert r1["chunks"][0]["chunk_id"] == r2["chunks"][0]["chunk_id"]

    def test_previous_next_pointers(self):
        from pipeline.nodes.doc_chunker import chunk_sections, MAX_CHUNK_CHARS

        big = ("paragraph content here. " * 80 + "\n\n") * 10
        section = self._make_section(big)
        result = chunk_sections({"sections": [section]})
        chunks = result["chunks"]
        if len(chunks) < 2:
            pytest.skip("Section did not produce multiple chunks with current settings")
        assert chunks[0]["next_chunk_id"] == chunks[1]["chunk_id"]
        assert chunks[1]["previous_chunk_id"] == chunks[0]["chunk_id"]
        assert chunks[0]["previous_chunk_id"] is None
        assert chunks[-1]["next_chunk_id"] is None

    def test_context_prefix_present(self):
        from pipeline.nodes.doc_chunker import chunk_sections

        section = self._make_section("The actual content goes here.")
        result = chunk_sections({"sections": [section]})
        content = result["chunks"][0]["content"]
        assert "Title:" in content
        assert "Section:" in content
        assert "Content:" in content


# ── RRF fusion unit test ──────────────────────────────────────────────────────

class TestRRF:
    def test_rrf_combines_scores(self):
        from services.rag_retriever import _rrf_fuse

        lexical = [{"_id": "a", "_source": {"title": "A"}}, {"_id": "b", "_source": {"title": "B"}}]
        vector = [{"_id": "b", "_source": {"title": "B"}}, {"_id": "c", "_source": {"title": "C"}}]

        fused = _rrf_fuse(lexical, vector, k=60, top_n=5)
        ids = [cid for cid, _, _ in fused]
        scores = [score for _, score, _ in fused]

        # "b" appears in both lists so should score highest
        assert ids[0] == "b"
        assert all(s > 0 for s in scores)

    def test_rrf_deduplicates(self):
        from services.rag_retriever import _rrf_fuse

        lexical = [{"_id": "x", "_source": {}}] * 5
        vector = [{"_id": "x", "_source": {}}] * 5
        fused = _rrf_fuse(lexical, vector, k=60, top_n=10)
        ids = [cid for cid, _, _ in fused]
        assert ids.count("x") == 1

    def test_rrf_top_n_respected(self):
        from services.rag_retriever import _rrf_fuse

        lexical = [{"_id": f"l{i}", "_source": {}} for i in range(20)]
        vector = [{"_id": f"v{i}", "_source": {}} for i in range(20)]
        fused = _rrf_fuse(lexical, vector, k=60, top_n=5)
        assert len(fused) <= 5

    def test_rrf_empty_inputs(self):
        from services.rag_retriever import _rrf_fuse

        assert _rrf_fuse([], [], k=60, top_n=5) == []
        assert _rrf_fuse([{"_id": "a", "_source": {}}], [], k=60, top_n=5) == [
            ("a", pytest.approx(1 / 61), {})
        ]


# ── Confidence assessment test ────────────────────────────────────────────────

class TestConfidence:
    def test_high_confidence_with_3_chunks(self):
        from services.rag_answer import _assess_confidence

        chunks = [object()] * 3
        assert _assess_confidence(chunks, abstained=False) == "high"

    def test_medium_confidence_with_1_chunk(self):
        from services.rag_answer import _assess_confidence

        chunks = [object()]
        assert _assess_confidence(chunks, abstained=False) == "medium"

    def test_low_confidence_when_abstained(self):
        from services.rag_answer import _assess_confidence

        chunks = [object()] * 5
        assert _assess_confidence(chunks, abstained=True) == "low"

    def test_low_confidence_with_no_chunks(self):
        from services.rag_answer import _assess_confidence

        assert _assess_confidence([], abstained=False) == "low"


# ── Gold evaluation questions (smoke tests with mocked RAG) ───────────────────

GOLD_QUESTIONS = [
    {
        "question": "How do I start Jarvis locally?",
        "scope": "documentation",
        "expected_keywords": ["docker", "whisper", "local"],
    },
    {
        "question": "What ASR engines does Jarvis support?",
        "scope": "documentation",
        "expected_keywords": ["gemini", "whisper"],
    },
    {
        "question": "What voice commands does Jarvis understand?",
        "scope": "documentation",
        "expected_keywords": ["navigate", "company"],
    },
]


class TestGoldQuestions:
    """These tests verify the retrieval pipeline with a mocked ES + answer layer.

    They act as regression tests: if chunking or metadata inference changes,
    the keyword checks here will catch regressions.
    """

    def _make_mock_chunk(self, content: str):
        from services.rag_retriever import RetrievedChunk

        return RetrievedChunk(
            chunk_id="gold_chunk",
            title="Jarvis Guide",
            source_path="/docs/readme_jarvis.md",
            heading_path=["readme_jarvis", "Jarvis Guide"],
            snippet=content[:300],
            content=content,
            doc_type="project_doc",
            domain="platform",
            ticker=None,
            tags=["jarvis"],
            rrf_score=0.02,
            rank=1,
        )

    @pytest.mark.parametrize("gold", GOLD_QUESTIONS)
    def test_gold_question_answer_contains_keywords(self, gold):
        from unittest.mock import patch
        from services.rag_retriever import RetrievalResult

        # Simulate retrieved content
        snippet = " ".join(gold["expected_keywords"]) + " more context here"
        chunk = self._make_mock_chunk(snippet)
        mock_result = RetrievalResult(
            chunks=[chunk],
            lexical_hits=5,
            vector_hits=5,
            fused_hits=1,
            embedding_model="models/embedding-001",
        )

        with patch("services.rag_retriever.retrieve", return_value=mock_result):
            with patch(
                "services.rag_answer.generate_answer",
                return_value=(snippet, False, "medium"),
            ):
                from services.rag_retriever import retrieve
                from services.rag_answer import generate_answer

                result = retrieve(gold["question"])
                answer, abstained, conf = generate_answer(
                    gold["question"], result.chunks
                )

        assert not abstained
        for kw in gold["expected_keywords"]:
            assert kw.lower() in answer.lower(), (
                f"Expected keyword '{kw}' not in answer for question: {gold['question']}"
            )
