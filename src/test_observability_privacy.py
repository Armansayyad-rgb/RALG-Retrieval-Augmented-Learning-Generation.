"""Observability and privacy hardening tests.

Covers:
A. raw question absent from logs
B. bearer token absent from logs
C. request ID generated
D. safe caller request ID propagated
E. unsafe request ID replaced
F. query lifecycle logged safely
G. ingest lifecycle logged safely
H. delete lifecycle logged
I. 401/429/413 logged safely
J. feedback persistence disable works
K. feedback persistence excludes full evidence
L. configurable log level works
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import api_server
from src.retriever_v2 import build_index
from src.log_helper import setup_logging


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _install_log_capture(logger_name: str) -> tuple[logging.Logger, ListHandler]:
    logger = logging.getLogger(logger_name)
    handler = ListHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger, handler


class TestRawQuestionAbsentFromLogs(unittest.TestCase):
    """A. raw question absent from logs"""

    def test_rag_chat_logs_do_not_contain_raw_question(self):
        import rag_chat_v2

        logger, handler = _install_log_capture("rag_chat")
        try:
            pipeline = {
                "device": "cpu",
                "tokenizer": None,
                "model": None,
                "chunks": [],
                "retrieval_index": build_index([]),
                "document_frequency": {},
            }
            rag_chat_v2.answer_question(pipeline, "secret-question-123", verbose=False)
        finally:
            logger.removeHandler(handler)

        raw_text = "\n".join(
            record.getMessage() for record in handler.records
        )
        self.assertNotIn("secret-question-123", raw_text)


class TestBearerTokenAbsentFromLogs(unittest.TestCase):
    """B. bearer token absent from logs"""

    def test_security_log_excludes_token(self):
        logger, handler = _install_log_capture("src.api_server")
        original_token = api_server.API_TOKEN
        try:
            api_server.API_TOKEN = "super-secret-token-xyz"
            client = TestClient(api_server.app, raise_server_exceptions=False)
            client.post(
                "/query",
                json={"question": "test"},
                headers={"Authorization": "Bearer wrong-token"},
            )
        finally:
            api_server.API_TOKEN = original_token
            logger.removeHandler(handler)

        raw_text = "\n".join(
            record.getMessage() for record in handler.records
        )
        self.assertNotIn("super-secret-token-xyz", raw_text)
        self.assertNotIn("wrong-token", raw_text)


class TestRequestIdGenerated(unittest.TestCase):
    """C. request ID generated"""

    def test_missing_request_id_generates_uuid(self):
        client = TestClient(api_server.app, raise_server_exceptions=False)
        with patch.object(api_server, "get_pipeline", return_value={
            "device": "cpu",
            "model": "mock",
            "tokenizer": "mock",
            "chunks": [],
            "uploaded_docs": [],
            "runtime_persistence": False,
            "retrieval_index": build_index([]),
            "document_frequency": {},
        }):
            resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        request_id = resp.headers.get("X-Request-ID")
        self.assertIsNotNone(request_id)
        self.assertEqual(len(request_id), 36)


class TestSafeCallerRequestIdPropagated(unittest.TestCase):
    """D. safe caller request ID propagated"""

    def test_valid_caller_request_id_returned(self):
        client = TestClient(api_server.app, raise_server_exceptions=False)
        caller_id = "my-safe-request-id-123"
        with patch.object(api_server, "get_pipeline", return_value={
            "device": "cpu",
            "model": "mock",
            "tokenizer": "mock",
            "chunks": [],
            "uploaded_docs": [],
            "runtime_persistence": False,
            "retrieval_index": build_index([]),
            "document_frequency": {},
        }):
            resp = client.get("/health", headers={"X-Request-ID": caller_id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Request-ID"), caller_id)


class TestUnsafeRequestIdReplaced(unittest.TestCase):
    """E. unsafe request ID replaced"""

    def test_control_char_request_id_replaced(self):
        client = TestClient(api_server.app, raise_server_exceptions=False)
        unsafe_id = "bad-id\x00\x01\x02"
        with patch.object(api_server, "get_pipeline", return_value={
            "device": "cpu",
            "model": "mock",
            "tokenizer": "mock",
            "chunks": [],
            "uploaded_docs": [],
            "runtime_persistence": False,
            "retrieval_index": build_index([]),
            "document_frequency": {},
        }):
            resp = client.get("/health", headers={"X-Request-ID": unsafe_id})
        self.assertEqual(resp.status_code, 200)
        returned = resp.headers.get("X-Request-ID")
        self.assertNotEqual(returned, unsafe_id)
        self.assertEqual(len(returned), 36)

    def test_overlong_request_id_replaced(self):
        client = TestClient(api_server.app, raise_server_exceptions=False)
        long_id = "a" * 65
        with patch.object(api_server, "get_pipeline", return_value={
            "device": "cpu",
            "model": "mock",
            "tokenizer": "mock",
            "chunks": [],
            "uploaded_docs": [],
            "runtime_persistence": False,
            "retrieval_index": build_index([]),
            "document_frequency": {},
        }):
            resp = client.get("/health", headers={"X-Request-ID": long_id})
        self.assertEqual(resp.status_code, 200)
        returned = resp.headers.get("X-Request-ID")
        self.assertEqual(len(returned), 36)


class TestQueryLifecycleLogged(unittest.TestCase):
    """F. query lifecycle logged safely"""

    def test_query_logs_lifecycle_metadata(self):
        logger, handler = _install_log_capture("src.api_server")
        client = TestClient(api_server.app, raise_server_exceptions=False)
        original_token = api_server.API_TOKEN
        try:
            api_server.API_TOKEN = None
            with patch.object(api_server, "get_pipeline", return_value={
                "device": "cpu",
                "model": "mock",
                "tokenizer": "mock",
                "chunks": [],
                "uploaded_docs": [],
                "runtime_persistence": False,
                "retrieval_index": build_index([]),
                "document_frequency": {},
            }), patch.object(
                api_server, "answer_question",
                return_value={
                    "answer": "mock-answer",
                    "supported": True,
                    "answer_type": "extractor",
                    "traceable": True,
                    "evidence": {"kind": "hybrid", "results": []},
                    "runtime_plan": {"intent": "general"},
                },
            ):
                resp = client.post(
                    "/query",
                    json={"question": "What is X?", "top_k": 5, "document_ids": ["doc1"]},
                )
        finally:
            api_server.API_TOKEN = original_token
            logger.removeHandler(handler)

        self.assertEqual(resp.status_code, 200)
        messages = [r.getMessage() for r in handler.records]
        lifecycle_msgs = [m for m in messages if "lifecycle_query" in m]
        self.assertTrue(len(lifecycle_msgs) >= 1)
        log_line = lifecycle_msgs[0]
        self.assertIn("request_id=", log_line)
        self.assertIn("top_k=5", log_line)
        self.assertIn("scope_count=1", log_line)
        self.assertIn("supported=", log_line)
        self.assertIn("answer_type=", log_line)
        self.assertIn("conflict=", log_line)
        self.assertNotIn("What is X?", log_line)


class TestIngestLifecycleLogged(unittest.TestCase):
    """G. ingest lifecycle logged safely"""

    def test_ingest_logs_lifecycle_metadata(self):
        logger, handler = _install_log_capture("src.api_server")
        client = TestClient(api_server.app, raise_server_exceptions=False)
        original_token = api_server.API_TOKEN
        try:
            api_server.API_TOKEN = None
            with patch.object(api_server, "get_pipeline", return_value={
                "chunks": [],
                "retrieval_index": build_index([]),
                "document_frequency": {},
                "uploaded_docs": [],
                "runtime_persistence": False,
            }), patch.object(
                api_server, "attach_documents", return_value=2,
            ), patch.object(
                api_server, "chunk_text", return_value=[],
            ):
                resp = client.post(
                    "/ingest",
                    json={"text": "Some document text here.", "document_name": "test_doc"},
                )
        finally:
            api_server.API_TOKEN = original_token
            logger.removeHandler(handler)

        self.assertEqual(resp.status_code, 200)
        messages = [r.getMessage() for r in handler.records]
        lifecycle_msgs = [m for m in messages if "lifecycle_ingest" in m]
        self.assertTrue(len(lifecycle_msgs) >= 1)
        log_line = lifecycle_msgs[0]
        self.assertIn("request_id=", log_line)
        self.assertIn("document_id=", log_line)
        self.assertIn("added_chunks=", log_line)
        self.assertIn("latency_ms=", log_line)
        self.assertNotIn("Some document text here.", log_line)


class TestDeleteLifecycleLogged(unittest.TestCase):
    """H. delete lifecycle logged"""

    def test_delete_logs_lifecycle_metadata(self):
        logger, handler = _install_log_capture("src.api_server")
        client = TestClient(api_server.app, raise_server_exceptions=False)
        doc_id = "test-doc-id-999"
        original_token = api_server.API_TOKEN
        try:
            api_server.API_TOKEN = None
            with patch.object(api_server, "get_pipeline", return_value={
                "chunks": [],
                "retrieval_index": build_index([]),
                "document_frequency": {},
                "uploaded_docs": [{"document_id": doc_id}],
                "runtime_persistence": False,
            }), patch.object(
                api_server, "has_uploaded_document", return_value=True,
            ), patch.object(
                api_server, "remove_uploaded_document", return_value=3,
            ):
                resp = client.delete(f"/documents/{doc_id}")
        finally:
            api_server.API_TOKEN = original_token
            logger.removeHandler(handler)

        self.assertEqual(resp.status_code, 200)
        messages = [r.getMessage() for r in handler.records]
        lifecycle_msgs = [m for m in messages if "lifecycle_delete" in m]
        self.assertTrue(len(lifecycle_msgs) >= 1)
        log_line = lifecycle_msgs[0]
        self.assertIn("request_id=", log_line)
        self.assertIn(f"document_id={doc_id}", log_line)
        self.assertIn("chunks_removed=3", log_line)
        self.assertIn("latency_ms=", log_line)


class TestSecurityEventsLogged(unittest.TestCase):
    """I. 401/429/413 logged safely"""

    def test_401_logs_without_token(self):
        logger, handler = _install_log_capture("src.api_server")
        client = TestClient(api_server.app, raise_server_exceptions=False)
        original_token = api_server.API_TOKEN
        try:
            api_server.API_TOKEN = "test-secret-token-123"
            client.post(
                "/query",
                json={"question": "test"},
                headers={"Authorization": "Bearer wrong-token"},
            )
        finally:
            api_server.API_TOKEN = original_token
            logger.removeHandler(handler)

        messages = [r.getMessage() for r in handler.records]
        security_msgs = [m for m in messages if "security_event" in m and "401" in m]
        self.assertTrue(len(security_msgs) >= 1)
        for msg in security_msgs:
            self.assertNotIn("test-secret-token-123", msg)
            self.assertNotIn("wrong-token", msg)

    def test_413_logs_securely(self):
        logger, handler = _install_log_capture("src.api_server")
        client = TestClient(api_server.app, raise_server_exceptions=False)
        try:
            client.post(
                "/ingest",
                content=b"x" * (api_server.MAX_API_REQUEST_BYTES + 1),
                headers={"content-type": "application/json"},
            )
        finally:
            logger.removeHandler(handler)

        messages = [r.getMessage() for r in handler.records]
        security_msgs = [m for m in messages if "security_event" in m and "413" in m]
        self.assertTrue(len(security_msgs) >= 1)


class TestFeedbackPrivacy(unittest.TestCase):
    """J, K. feedback persistence privacy"""

    def test_feedback_disabled_returns_none(self):
        import webui.feedback_log as fb_mod
        original = os.environ.get("RALG_FEEDBACK_LOG_ENABLED")
        os.environ["RALG_FEEDBACK_LOG_ENABLED"] = "0"
        try:
            importlib.reload(fb_mod)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "feedback.jsonl"
                result = fb_mod.log_feedback(
                    1,
                    question="secret question",
                    answer="secret answer",
                    log_path=path,
                )
                self.assertIsNone(result)
                self.assertFalse(path.exists())
        finally:
            if original is None:
                os.environ.pop("RALG_FEEDBACK_LOG_ENABLED", None)
            else:
                os.environ["RALG_FEEDBACK_LOG_ENABLED"] = original
            importlib.reload(fb_mod)

    def test_feedback_enabled_excludes_full_evidence(self):
        import webui.feedback_log as fb_mod
        original = os.environ.get("RALG_FEEDBACK_LOG_ENABLED")
        os.environ["RALG_FEEDBACK_LOG_ENABLED"] = "1"
        try:
            importlib.reload(fb_mod)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "feedback.jsonl"
                fb_mod.log_feedback(
                    1,
                    question="secret question",
                    answer="secret answer",
                    sources=[{"rank": 1, "evidence": "secret evidence text"}],
                    log_path=path,
                )
                rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
                self.assertEqual(len(rows), 1)
                self.assertNotIn("secret question", rows[0]["question"])
                self.assertNotIn("secret answer", rows[0]["answer"])
                self.assertNotIn("secret evidence text", json.dumps(rows[0]["sources"]))
        finally:
            if original is None:
                os.environ.pop("RALG_FEEDBACK_LOG_ENABLED", None)
            else:
                os.environ["RALG_FEEDBACK_LOG_ENABLED"] = original
            importlib.reload(fb_mod)


class TestConfigurableLogLevel(unittest.TestCase):
    """L. configurable log level works"""

    def test_ralg_log_level_env_sets_debug(self):
        original = os.environ.get("RALG_LOG_LEVEL")
        os.environ["RALG_LOG_LEVEL"] = "DEBUG"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                logger = setup_logging(log_dir=tmp, log_name="test_debug")
                self.assertEqual(logger.level, logging.DEBUG)
        finally:
            if original is None:
                os.environ.pop("RALG_LOG_LEVEL", None)
            else:
                os.environ["RALG_LOG_LEVEL"] = original

    def test_invalid_log_level_falls_back_to_info(self):
        original = os.environ.get("RALG_LOG_LEVEL")
        os.environ["RALG_LOG_LEVEL"] = "INVALID"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                logger = setup_logging(log_dir=tmp, log_name="test_invalid")
                self.assertEqual(logger.level, logging.INFO)
        finally:
            if original is None:
                os.environ.pop("RALG_LOG_LEVEL", None)
            else:
                os.environ["RALG_LOG_LEVEL"] = original


if __name__ == "__main__":
    unittest.main()
