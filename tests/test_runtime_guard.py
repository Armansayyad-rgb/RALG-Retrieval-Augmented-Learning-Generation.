"""Tests for the shared Python 3.11 runtime-version guard.

These tests verify the guard's behavior directly and that both official
startup paths wire it in. They do not require the project's heavy
dependencies (FastAPI, Gradio, torch) to be installed.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
RUNTIME_GUARD = SRC / "runtime_guard.py"
API_SERVER = SRC / "api_server.py"
WEBUI_BOOTSTRAP = SRC / "webui_bootstrap.py"


def _load_runtime_guard():
    spec = importlib.util.spec_from_file_location("runtime_guard_under_test", RUNTIME_GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeVersion:
    """Stand-in for sys.version_info supporting the guard's comparison."""

    def __init__(self, major, minor, micro=0):
        self.major = major
        self.minor = minor
        self.micro = micro

    def __eq__(self, other):
        if isinstance(other, tuple):
            return (self.major, self.minor) == other
        return NotImplemented


class TestRuntimeGuardBehavior(unittest.TestCase):
    def setUp(self):
        self.runtime_guard = _load_runtime_guard()

    def test_passes_on_3_11(self):
        with unittest.mock.patch.object(sys, "version_info", _FakeVersion(3, 11)):
            self.runtime_guard.enforce_python_311()  # should not raise

    def test_fails_on_3_10(self):
        with unittest.mock.patch.object(sys, "version_info", _FakeVersion(3, 10)):
            with self.assertRaises(RuntimeError):
                self.runtime_guard.enforce_python_311()

    def test_fails_on_3_12(self):
        with unittest.mock.patch.object(sys, "version_info", _FakeVersion(3, 12)):
            with self.assertRaises(RuntimeError):
                self.runtime_guard.enforce_python_311()


class TestEntrypointsWireGuard(unittest.TestCase):
    """Both official startup paths must import and invoke the guard."""

    def test_api_server_wires_guard(self):
        source = API_SERVER.read_text()
        self.assertIn("runtime_guard.enforce_python_311()", source)

    def test_webui_bootstrap_wires_guard(self):
        source = WEBUI_BOOTSTRAP.read_text()
        self.assertIn("runtime_guard.enforce_python_311()", source)


if __name__ == "__main__":
    unittest.main()
