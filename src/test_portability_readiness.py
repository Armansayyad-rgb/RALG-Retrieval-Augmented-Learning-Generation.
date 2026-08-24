"""Portability and API readiness checks that do not require model inference."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import api_server


class PortabilityReadinessTests(unittest.TestCase):
    def setUp(self):
        self.original_pipeline = api_server._PIPELINE
        self.original_error = api_server._INIT_ERROR

    def tearDown(self):
        api_server._PIPELINE = self.original_pipeline
        api_server._INIT_ERROR = self.original_error

    def test_health_is_lightweight(self):
        api_server._PIPELINE = None
        api_server._INIT_ERROR = None
        with patch.object(api_server, "initialize_pipeline", side_effect=AssertionError):
            self.assertEqual(api_server.health(), {"status": "ok"})

    def test_ready_reports_fully_initialized_runtime(self):
        api_server._PIPELINE = {
            "model": object(),
            "tokenizer": object(),
            "retrieval_index": {},
            "document_frequency": {},
            "chunks": ["static"],
        }
        api_server._INIT_ERROR = None
        response = api_server.ready()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.body)
        self.assertNotIn(str(PROJECT_ROOT).encode(), response.body)

    def test_ready_fails_safely_for_missing_model(self):
        api_server._PIPELINE = {
            "model": None,
            "tokenizer": object(),
            "retrieval_index": {},
            "document_frequency": {},
            "chunks": ["static"],
        }
        api_server._INIT_ERROR = None
        response = api_server.ready()
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'"ready":false', response.body)
        self.assertNotIn(b"Traceback", response.body)

    def test_ready_preserves_initialization_failure_state(self):
        api_server._PIPELINE = None
        api_server._INIT_ERROR = None
        with patch.object(api_server, "initialize_pipeline", side_effect=RuntimeError("secret path")):
            with self.assertRaises(RuntimeError):
                api_server.get_pipeline()
        response = api_server.ready()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"secret path", response.body)
        self.assertNotIn(str(PROJECT_ROOT).encode(), response.body)

    def test_config_resolves_overrides_from_arbitrary_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            script = (
                "import config; print(config.PROJECT_ROOT); "
                "print(config.DATA_DIR); print(config.MODEL_FILE)"
            )
            env = os.environ.copy()
            env["AI_PROJECT_ROOT"] = str(Path(directory) / "clone")
            env["AI_PROJECT_DATA_DIR"] = str(data_dir)
            env["MODEL_FILE"] = str(Path(directory) / "model.pt")
            env["PYTHONPATH"] = str(PROJECT_ROOT)
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
        self.assertIn(str(data_dir.resolve()), result.stdout)
        self.assertIn(str(Path(directory).resolve() / "model.pt"), result.stdout)
        self.assertNotIn(r"C:\AI-Project", result.stdout)

    def test_retriever_uses_canonical_config(self):
        import retriever_v2
        import retriever_v4

        from config import KNOWLEDGE_FILES

        self.assertEqual(retriever_v2.KNOWLEDGE_FILES, KNOWLEDGE_FILES)
        self.assertEqual(retriever_v4.KNOWLEDGE_FILE, KNOWLEDGE_FILES[0])


if __name__ == "__main__":
    unittest.main()
