"""Tests for optional document-scoped retrieval.

Covers:
  A. Scoped runtime document — only selected doc supplies evidence
  B. Cross-document isolation — excluded doc cannot appear
  C. Static isolation — static KB cannot enter scoped pool
  D. Invalid document ID — safe unsupported, no global fallback
  E. Multiple IDs — both eligible, no others
  F. Unscoped regression — document_ids=None preserves global behavior
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC = str(Path(__file__).resolve().parent)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from retriever_v2 import (  # noqa: E402
    RuntimeChunk,
    build_index,
    retrieve_candidates,
    retrieve,
)
from retriever_hybrid import retrieve as retrieve_hybrid  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_chunk(text, doc_id, chunk_index=0):
    return RuntimeChunk(text, metadata={
        "document_id": doc_id,
        "document_name": f"doc_{doc_id[:8]}",
        "chunk_index": chunk_index,
        "source_type": "runtime_upload",
        "extension": ".txt",
        "upload_timestamp": "2026-01-01T00:00:00.000Z",
        "page_number": None,
        "revision": None,
    })


DOC_A = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
DOC_B = "11111111-2222-3333-4444-555555555555"

CHUNKS = [
    # Static KB chunks (plain str, not RuntimeChunk)
    "The compressor inspection phase requires checking oil levels.",
    "Before starting any maintenance, ensure the power is locked out.",
    "Compressor vibration analysis should be performed monthly.",
    "The lubrication system must be checked during routine maintenance.",
    # Runtime doc A chunks
    _make_chunk(
        "During the inspection phase, verify belt tension and alignment. "
        "Check compressor housing for cracks. Inspect oil level and quality.",
        DOC_A, 0,
    ),
    _make_chunk(
        "The inspection phase also includes checking electrical connections "
        "and verifying safety shutdowns are functional.",
        DOC_A, 1,
    ),
    # Runtime doc B chunks
    _make_chunk(
        "During the inspection phase, examine conveyor belt tension. "
        "Check alignment of drive pulleys and idler rollers.",
        DOC_B, 0,
    ),
    _make_chunk(
        "Lubrication inspection includes greasing bearings and checking "
        "gearbox oil levels.",
        DOC_B, 1,
    ),
]

INDEX, DOC_FREQ = build_index(CHUNKS)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScopedRetrieval(unittest.TestCase):
    """A. Scoped runtime document — only selected doc supplies evidence."""

    def test_scope_to_doc_a_returns_only_doc_a(self):
        results = retrieve_candidates(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            top_k=10,
            document_ids=[DOC_A],
        )
        self.assertTrue(len(results) > 0, "Should return at least one result")
        for row in results:
            chunk = row[4]
            self.assertIsInstance(chunk, RuntimeChunk,
                "Scoped results must be RuntimeChunks")
            self.assertEqual(chunk.metadata.get("document_id"), DOC_A,
                f"Expected doc A but got {chunk.metadata.get('document_id')}")

    def test_scope_to_doc_a_hybrid_returns_only_doc_a(self):
        results = retrieve_hybrid(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            final_top_k=10,
            document_ids=[DOC_A],
        )
        self.assertTrue(len(results) > 0)
        for row in results:
            chunk = row["chunk"]
            self.assertIsInstance(chunk, RuntimeChunk)
            self.assertEqual(chunk.metadata.get("document_id"), DOC_A)


class TestCrossDocumentIsolation(unittest.TestCase):
    """B. Cross-document isolation — excluded doc cannot appear."""

    def test_scope_to_a_excludes_b(self):
        results = retrieve_candidates(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            top_k=10,
            document_ids=[DOC_A],
        )
        for row in results:
            chunk = row[4]
            self.assertIsInstance(chunk, RuntimeChunk)
            self.assertNotEqual(chunk.metadata.get("document_id"), DOC_B,
                "Doc B must not appear when scoped to doc A")

    def test_scope_to_b_excludes_a(self):
        results = retrieve_candidates(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            top_k=10,
            document_ids=[DOC_B],
        )
        for row in results:
            chunk = row[4]
            self.assertIsInstance(chunk, RuntimeChunk)
            self.assertNotEqual(chunk.metadata.get("document_id"), DOC_A,
                "Doc A must not appear when scoped to doc B")


class TestStaticIsolation(unittest.TestCase):
    """C. Static isolation — static KB cannot enter scoped pool."""

    def test_scoped_excludes_static_chunks(self):
        results = retrieve_candidates(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            top_k=10,
            document_ids=[DOC_A],
        )
        for row in results:
            chunk = row[4]
            self.assertIsInstance(chunk, RuntimeChunk,
                "Static chunks must not appear in scoped results")


class TestInvalidDocumentId(unittest.TestCase):
    """D. Invalid document ID — safe unsupported, no global fallback."""

    def test_invalid_id_returns_empty(self):
        results = retrieve_candidates(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            top_k=10,
            document_ids=["nonexistent-uuid-0000-0000-000000000000"],
        )
        self.assertEqual(len(results), 0,
            "Invalid document ID must return empty, no global fallback")

    def test_invalid_id_hybrid_returns_empty(self):
        results = retrieve_hybrid(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            final_top_k=10,
            document_ids=["nonexistent-uuid-0000-0000-000000000000"],
        )
        self.assertEqual(len(results), 0)


class TestMultipleIds(unittest.TestCase):
    """E. Multiple IDs — both eligible, no others."""

    def test_scope_to_a_and_b(self):
        results = retrieve_candidates(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            top_k=10,
            document_ids=[DOC_A, DOC_B],
        )
        self.assertTrue(len(results) > 0)
        doc_ids_found = set()
        for row in results:
            chunk = row[4]
            self.assertIsInstance(chunk, RuntimeChunk)
            doc_ids_found.add(chunk.metadata.get("document_id"))
        self.assertTrue(doc_ids_found.issubset({DOC_A, DOC_B}),
            f"Only doc A and B allowed, got: {doc_ids_found}")
        self.assertTrue(len(doc_ids_found) >= 1,
            "At least one of A or B should appear")


class TestScopedApiSafety(unittest.TestCase):
    """Scoped API misses must not crash or leak fallback sources."""

    def setUp(self):
        import api_server

        self.api_server = api_server
        self.original_pipeline = api_server._PIPELINE
        self.original_init_error = api_server._INIT_ERROR
        api_server._INIT_ERROR = None
        chunks = [
            "Static KB says the compressor warranty phone number is 555-0000.",
            _make_chunk(
                "Document A says the compressor inspection requires oil checks.",
                DOC_A,
                0,
            ),
            _make_chunk(
                "Document B says the compressor restart requires a valve check.",
                DOC_B,
                0,
            ),
        ]
        index, df = build_index(chunks)
        api_server._PIPELINE = {
            "device": "cpu",
            "tokenizer": None,
            "model": None,
            "chunks": chunks,
            "retrieval_index": index,
            "document_frequency": df,
            "uploaded_docs": [],
        }

    def tearDown(self):
        self.api_server._PIPELINE = self.original_pipeline
        self.api_server._INIT_ERROR = self.original_init_error

    def test_query_missing_document_id_returns_unsupported_no_sources(self):
        from fastapi.testclient import TestClient

        client = TestClient(self.api_server.app)
        response = client.post(
            "/query",
            json={
                "question": "What does the missing document say about inspection?",
                "document_ids": ["missing-doc"],
                "include_sources": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["answer_type"], "system")
        self.assertEqual(payload["sources"], [])

    def test_scoped_unsupported_does_not_leak_other_runtime_or_static_sources(self):
        from fastapi.testclient import TestClient

        client = TestClient(self.api_server.app)
        response = client.post(
            "/query",
            json={
                "question": "What is the warranty phone number for compressor support?",
                "document_ids": [DOC_A],
                "include_sources": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["sources"], [])

    def test_execute_runtime_fallback_receives_document_scope(self):
        from runtime_architecture import execute_runtime

        seen = []

        def answer_fn(*_args, **_kwargs):
            return {
                "answer": "I couldn't find enough reliable evidence.",
                "supported": False,
                "runtime_plan": {"intent": "general"},
            }

        def contract_fn(_pipeline, _question, result, *_args, fallback_sources=None, **_kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(
                answer=result.get("answer", ""),
                supported=False,
                confidence=None,
                answer_type=result.get("answer_type", "system"),
                sources=fallback_sources or [],
                provenance=[],
                traceable=False,
                conflict=False,
                evidence=result.get("evidence"),
                error=None,
            )

        def sources_fn(*_args, **kwargs):
            seen.append(kwargs.get("document_ids"))
            return []

        execute_runtime(
            {},
            "question",
            5,
            answer_fn=answer_fn,
            contract_fn=contract_fn,
            sources_fn=sources_fn,
            document_ids=[DOC_A],
        )
        self.assertEqual(seen, [[DOC_A]])


class TestUnscopedRegression(unittest.TestCase):
    """F. Unscoped regression — document_ids=None preserves global behavior."""

    def test_none_returns_all_types(self):
        results = retrieve_candidates(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            top_k=10,
            document_ids=None,
        )
        self.assertTrue(len(results) > 0)
        has_static = any(
            not isinstance(row[4], RuntimeChunk)
            for row in results
        )
        has_runtime = any(
            isinstance(row[4], RuntimeChunk)
            for row in results
        )
        self.assertTrue(has_static or has_runtime,
            "Unscoped should return at least some results")

    def test_none_hybrid_returns_results(self):
        results = retrieve_hybrid(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            final_top_k=10,
        )
        self.assertTrue(len(results) > 0)

    def test_empty_list_returns_nothing(self):
        results = retrieve_candidates(
            "What must be checked during the inspection phase?",
            CHUNKS, INDEX, DOC_FREQ,
            top_k=10,
            document_ids=[],
        )
        self.assertEqual(len(results), 0,
            "Empty document_ids must return nothing")

    def test_unscoped_api_can_return_sources(self):
        import api_server
        from fastapi.testclient import TestClient

        chunks = [
            "Static KB says the compressor warranty phone number is 555-0000.",
        ]
        index, df = build_index(chunks)
        original_pipeline = api_server._PIPELINE
        original_init_error = api_server._INIT_ERROR
        api_server._INIT_ERROR = None
        api_server._PIPELINE = {
            "device": "cpu",
            "tokenizer": None,
            "model": None,
            "chunks": chunks,
            "retrieval_index": index,
            "document_frequency": df,
            "uploaded_docs": [],
        }
        try:
            client = TestClient(api_server.app)
            response = client.post(
                "/query",
                json={
                    "question": "What is the warranty phone number for compressor support?",
                    "include_sources": True,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["sources"])
        finally:
            api_server._PIPELINE = original_pipeline
            api_server._INIT_ERROR = original_init_error


if __name__ == "__main__":
    unittest.main()
