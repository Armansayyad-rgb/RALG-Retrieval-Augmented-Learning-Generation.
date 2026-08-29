"""Focused regression tests for API contract consistency fixes.

Covers:
- DELETE error envelope normalization (400/404 return {"error": ...})
- document_ids per-item validation (reject malformed, accept valid, max-count)
- authentication behavior unchanged

Run with: python -m unittest tests.test_api_contract_consistency -v
"""

import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src import api_server


def _fake_execution_result():
    return types.SimpleNamespace(
        answer="ok",
        supported=True,
        confidence=0.5,
        answer_type="fact",
        sources=[],
        observability={"latency_ms": 1.0},
        traceable=False,
        conflict=False,
        provenance=[],
        error=None,
    )


class APIContractConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api_server.app, raise_server_exceptions=False)

    # ------------------------------------------------------------------
    # DELETE error-envelope normalization
    # ------------------------------------------------------------------

    def test_delete_malformed_id_returns_error_envelope(self):
        """Path-traversal / malformed ids return 400 with {"error": ...}."""
        # NOTE: ids containing "/" become multiple path segments and never reach
        # the handler (Starlette returns 404 route-not-found), so we assert the
        # single-segment ids that actually reach delete_document.
        for bad_id in ["a\\b", "  ", "....", "foo..bar"]:
            with self.subTest(document_id=bad_id):
                resp = self.client.delete(f"/documents/{bad_id}")
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.json(), {"error": "Invalid document ID."})

    def test_delete_unknown_id_returns_error_envelope(self):
        """Unknown (well-formed) ids return 404 with {"error": ...}."""
        with patch.object(api_server, "get_pipeline", return_value={}), patch.object(
            api_server, "has_uploaded_document", return_value=False
        ):
            resp = self.client.delete("/documents/does_not_exist_123")
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.json(), {"error": "Document not found."})

    def test_delete_success_response_unchanged(self):
        """Successful delete keeps the DocumentDeleteResponse shape."""
        with patch.object(api_server, "get_pipeline", return_value={}), patch.object(
            api_server, "has_uploaded_document", return_value=True
        ), patch.object(api_server, "remove_uploaded_document", return_value=3):
            resp = self.client.delete("/documents/valid_doc_id")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(
                resp.json(),
                {"document_id": "valid_doc_id", "deleted": True, "chunks_removed": 3},
            )

    # ------------------------------------------------------------------
    # document_ids validation
    # ------------------------------------------------------------------

    def test_query_accepts_valid_document_ids(self):
        """Well-formed document_ids pass schema validation (no 422)."""
        with patch.object(api_server, "get_pipeline", return_value={}), patch.object(
            api_server, "execute_runtime", return_value=_fake_execution_result()
        ):
            resp = self.client.post(
                "/query",
                json={"question": "What is required?", "document_ids": ["doc_a", "doc-b", "Doc_3"]},
            )
            self.assertNotEqual(resp.status_code, 422)
            self.assertEqual(resp.status_code, 200)

    def test_query_rejects_malformed_document_ids(self):
        """Malformed document_ids reject with 422 + {"error": ...}."""
        for bad_ids in [[""], ["a/b"], ["x\\y"], ["\x00ctrl"], ["  "]]:
            with self.subTest(document_ids=bad_ids):
                resp = self.client.post(
                    "/query", json={"question": "What is required?", "document_ids": bad_ids}
                )
                self.assertEqual(resp.status_code, 422)
                self.assertEqual(resp.json(), {"error": "Invalid request."})

    def test_query_document_ids_max_count_preserved(self):
        """More than max list length is still rejected with 422."""
        with patch.object(api_server, "get_pipeline", return_value={}):
            resp = self.client.post(
                "/query",
                json={"question": "What is required?", "document_ids": [f"d{i}" for i in range(11)]},
            )
            self.assertEqual(resp.status_code, 422)
            self.assertEqual(resp.json(), {"error": "Invalid request."})

    def test_query_document_ids_optional(self):
        """Omitting document_ids is allowed (unchanged behavior)."""
        with patch.object(api_server, "get_pipeline", return_value={}), patch.object(
            api_server, "execute_runtime", return_value=_fake_execution_result()
        ):
            resp = self.client.post("/query", json={"question": "What is required?"})
            self.assertEqual(resp.status_code, 200)

    # ------------------------------------------------------------------
    # auth behavior unchanged
    # ------------------------------------------------------------------

    def test_delete_requires_auth_when_token_set(self):
        """With API_TOKEN set, DELETE without a token is 401 (unchanged)."""
        original = api_server.API_TOKEN
        api_server.API_TOKEN = "test-secret-token-123"
        try:
            resp = self.client.delete("/documents/valid_doc_id")
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(resp.json(), {"error": "Unauthorized. API token required."})
        finally:
            api_server.API_TOKEN = original

    def test_delete_auth_allows_valid_token(self):
        """With API_TOKEN set, a valid bearer token proceeds to delete logic."""
        original = api_server.API_TOKEN
        api_server.API_TOKEN = "test-secret-token-123"
        try:
            with patch.object(api_server, "get_pipeline", return_value={}), patch.object(
                api_server, "has_uploaded_document", return_value=False
            ):
                resp = self.client.delete(
                    "/documents/valid_doc_id",
                    headers={"Authorization": "Bearer test-secret-token-123"},
                )
                self.assertEqual(resp.status_code, 404)
                self.assertEqual(resp.json(), {"error": "Document not found."})
        finally:
            api_server.API_TOKEN = original


if __name__ == "__main__":
    unittest.main()
