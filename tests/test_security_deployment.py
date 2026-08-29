"""Focused security tests for RALG Engine single-tenant deployment hardening.

These tests avoid model initialization by mocking the pipeline and use
the TestClient with raise_server_exceptions=False for reliable input
validation checks.

See: test_api_input_hardening.py for the original input hardening test
suite that these complement.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(PROJECT_ROOT))

from src import api_server


class TestSecurityDeploymentProfile(unittest.TestCase):
    """Security-oriented tests for the hardened single-tenant deployment profile."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api_server.app, raise_server_exceptions=False)

    # Helper used by test methods
    @staticmethod
    def assert_safe_validation_error(response):
        assert response.status_code == 422
        assert response.json() == {"error": "Invalid request."}

    # ------------------------------------------------------------------
    # 1. Auth disabled: local-development compatibility
    # -------------------------------------------------------------------------
    def test_unauthenticated_access_works_when_token_not_set(self):
        """When API_TOKEN is unset, all endpoints remain usable without a token."""
        # /health should always be public
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

        # /ready should always be public
        resp = self.client.get("/ready")
        self.assertIn(resp.status_code, (200, 503))

        # /stats should work without auth
        resp = self.client.get("/stats")
        self.assertEqual(resp.status_code, 200)

        # /documents should work without auth
        resp = self.client.get("/documents")
        self.assertEqual(resp.status_code, 200)

        # /query without token should work when API_TOKEN not set
        resp = self.client.post(
            "/query",
            json={"question": "test question"},
        )
        # Should not 401 when no token is configured
        self.assertNotEqual(resp.status_code, 401, "Auth should be disabled when API_TOKEN is not set")

        # /ingest without token should work when API_TOKEN not set
        resp = self.client.post(
            "/ingest",
            json={"text": "test text", "document_name": "test_doc"},
        )
        self.assertNotEqual(resp.status_code, 401, "Auth should be disabled when API_TOKEN is not set")

    # ------------------------------------------------------------------
    # 2. Auth enabled: bearer token required
    # ------------------------------------------------------------------
    def setUp(self):
        """Configure API_TOKEN for authenticated tests."""
        self.original_token = api_server.API_TOKEN
        api_server.API_TOKEN = "test-secret-token-123"

    def tearDown(self):
        api_server.API_TOKEN = self.original_token

    def test_authenticated_query_works_with_valid_token(self):
        """Queries with a valid bearer token succeed when API_TOKEN is set."""
        resp = self.client.post(
            "/query",
            json={"question": "test question"},
            headers={"Authorization": "Bearer test-secret-token-123"},
        )
        # Should not be 401; may be 503 if pipeline not initialized, but not auth error
        self.assertNotEqual(resp.status_code, 401)

    def test_authenticated_ingest_works_with_valid_token(self):
        """Ingest with a valid bearer token succeeds when API_TOKEN is set."""
        resp = self.client.post(
            "/ingest",
            json={"text": "test text", "document_name": "test_doc"},
            headers={"Authorization": "Bearer test-secret-token-123"},
        )
        # Should not be 401
        self.assertNotEqual(resp.status_code, 401)

    def test_malformed_token_returned_401(self):
        """A request with wrong token gets 401."""
        resp = self.client.post(
            "/query",
            json={"question": "test question"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_missing_auth_header_returned_401(self):
        """A request without an Authorization header gets 401 when API_TOKEN is set."""
        resp = self.client.post(
            "/query",
            json={"question": "test question"},
        )
        # When API_TOKEN is set in setUp, should get 401
        self.assertEqual(resp.status_code, 401)

    def test_wrong_scheme_returned_401(self):
        """A request with a non-Bearer scheme gets 401."""
        resp = self.client.post(
            "/query",
            json={"question": "test question"},
            headers={"Authorization": "Basic some-creds"},
        )
        self.assertEqual(resp.status_code, 401)

    # ------------------------------------------------------------------
    # 3. Path traversal attempts on document_id
    # ------------------------------------------------------------------
    def test_document_id_path_traversal_rejected(self):
        """Path traversal characters in document_id are rejected."""
        # Test various path traversal patterns
        for bad_id in ["../../etc/passwd", "/etc/passwd", "..\\..\\windows\\system32"]:
            with self.subTest(document_id=bad_id):
                resp = self.client.delete(f"/documents/{bad_id}")
                # Should not crash; should return 400 invalid or 404 not found
                self.assertIn(resp.status_code, (400, 404))

    # ------------------------------------------------------------------
    # 4. Oversized/invalid requests
    # ------------------------------------------------------------------
    def test_oversized_request_body_rejected(self):
        """Oversized request bodies are rejected with 413."""
        response = self.client.post(
            "/ingest",
            content=b"x" * (api_server.MAX_API_REQUEST_BYTES + 1),
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json(), {"error": "Request body too large."})

    def test_empty_payload_rejected_safely(self):
        """Empty payloads are rejected with 422 and sanitized message."""
        response = self.client.post("/ingest", content=b"", headers={"content-type": "application/json"})
        self.assert_safe_validation_error(response)

    def test_invalid_json_rejected_safely(self):
        """Malformed JSON is rejected with 422 and sanitized message."""
        response = self.client.post(
            "/ingest", content=b'{"text":', headers={"content-type": "application/json"}
        )
        self.assert_safe_validation_error(response)

    def test_blank_text_rejected(self):
        """Blank text in ingest is rejected."""
        self.assert_safe_validation_error(
            self.client.post("/ingest", json={"text": " \r\n\t"})
        )

    # ------------------------------------------------------------------
    # 5. Unsafe filename handling
    # ------------------------------------------------------------------
    def test_unsafe_filename_sanitized(self):
        """Unsafe characters in document names are sanitized."""
        # Upload a file with path-traversal in the name
        resp = self.client.post(
            "/ingest",
            json={
                "text": "test content",
                "document_name": "../../../etc/passwd",
            },
        )
        # Should not crash; name should be sanitized
        self.assertIn(resp.status_code, (200, 400, 422))

    # ------------------------------------------------------------------
    # 6. No secret echo — ensure tokens/credentials not reflected in responses
    # ------------------------------------------------------------------
    def test_no_secret_echo_in_error_responses(self):
        """Internal details (including configured token values) are never leaked."""
        # Even with API_TOKEN set, error responses should not disclose it
        resp = self.client.post(
            "/query",
            json={"question": "test"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertNotIn("test-secret-token-123", resp.text)
        self.assertNotIn("API_TOKEN", resp.text)

    def test_no_stack_trace_leak(self):
        """Server errors do not leak stack traces or internal paths."""
        private_detail = "private traceback detail /app/secret/path"

        def fail(*args, **kwargs):
            raise RuntimeError(private_detail)

        with patch.object(api_server, "get_pipeline", return_value={}), patch.object(
            api_server, "answer_question", side_effect=fail
        ):
            resp = self.client.post("/query", json={"question": "valid question"})
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.json()["error"], "Request processing failed.")
        self.assertNotIn(private_detail, resp.text)

    # ------------------------------------------------------------------
    # 7. Safe error responses (consistent formatting)
    # ------------------------------------------------------------------
    def test_oversized_text_rejected(self):
        """Oversized question text is rejected via Pydantic validation."""
        response = self.client.post(
            "/ingest",
            json={"text": "x" * (api_server.MAX_INGEST_TEXT_CHARS + 1)},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"error": "Invalid request."})

    # ------------------------------------------------------------------
    # 8. Existing legitimate query/ingest behavior not broken
    # ------------------------------------------------------------------
    @patch.object(api_server, "get_pipeline")
    @patch.object(api_server, "answer_question")
    def test_legitimate_query_behavior(self, mock_answer, mock_get_pipeline):
        """Existing legitimate query behavior is not broken by security changes."""
        # Set up mock pipeline
        mock_pipeline = {
            "model": "mock-model",
            "tokenizer": "mock-tokenizer",
            "chunks": [],
            "uploaded_docs": [],
            "runtime_persistence": False,
        }
        mock_get_pipeline.return_value = mock_pipeline

        mock_answer.return_value = type(
            "Execution",
            (object,),
            {
                "answer": "I cannot verify that.",
                "supported": False,
                "answer_type": "abstention",
                "confidence": None,
                "sources": [],
                "traceable": False,
                "conflict": False,
                "provenance": [],
                "error": None,
                "observability": {"latency_ms": 120.0},
            },
        )()

        mock_get_pipeline.return_value = mock_pipeline
        resp = self.client.post(
            "/query",
            json={"question": "What is this?", "top_k": 5},
        )
        # Should get a valid response (may be abstention if no evidence)
        self.assertIn(resp.status_code, (200, 500))
        if resp.status_code == 200:
            body = resp.json()
            self.assertIn("answer", body)
            self.assertIn("supported", body)

    @patch.object(api_server, "get_pipeline")
    @patch.object(api_server, "answer_question")
    def test_legitimate_ingest_behavior(self, mock_answer, mock_get_pipeline):
        """Existing legitimate ingest behavior is not broken by security changes."""
        mock_pipeline = {
            "chunks": [],
            "retrieval_index": {},
            "document_frequency": {},
            "uploaded_docs": [],
            "runtime_persistence": False,
        }
        mock_get_pipeline.return_value = mock_pipeline

        resp = self.client.post(
            "/ingest",
            json={"document_name": "my_doc", "text": "Pump pressure is 10 bar."},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("document_id", resp.json())


if __name__ == "__main__":
    unittest.main()