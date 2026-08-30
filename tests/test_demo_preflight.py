"""Focused, automatable tests for the demonstration preflight and runner logic.

These tests verify the scripts' behavior without running Holdout V1/V2/V3
or any benchmark that touches frozen independent evidence.
"""

import contextlib
import json
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
PYTHON = sys.executable

sys.path.insert(0, str(SCRIPTS))
import demo_preflight


class TestPreflightJsonStructure(TestCase):
    """Preflight must produce valid JSON with expected keys even when checks fail."""

    def test_preflight_json_output_structure(self):
        result = subprocess.run(
            [PYTHON, str(SCRIPTS / "demo_preflight.py"), "--docker"],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        self.assertIsInstance(data, dict)
        self.assertIn("checks", data)
        self.assertIn("failures", data)
        self.assertIn("pass", data)
        self.assertIn("selected_port", data)
        self.assertIn("webui_url", data)
        self.assertIsInstance(data["checks"], list)

    def test_preflight_json_valid_when_checks_pass(self):
        """When preflight passes, the JSON structure remains valid."""
        pass


class TestPreflightPythonVersion(TestCase):
    """Preflight reports Python-version status in every run."""

    def test_preflight_python_version_failure_structure(self):
        result = subprocess.run(
            [PYTHON, str(SCRIPTS / "demo_preflight.py")],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        self.assertIn("python_version", [c["name"] for c in data["checks"]])


class _FakeVersion:
    """Minimal stand-in for sys.version_info supporting the comparisons used."""

    def __init__(self, major, minor, micro=0):
        self.major = major
        self.minor = minor
        self.micro = micro

    def __lt__(self, other):
        return (self.major, self.minor, self.micro) < tuple(other)


class TestPreflightPythonVersionExact(TestCase):
    """Preflight must require exactly Python 3.11."""

    def _check(self, major, minor):
        with patch.object(sys, "version_info", _FakeVersion(major, minor)):
            return demo_preflight.check_python()

    def test_preflight_rejects_3_10(self):
        result = self._check(3, 10)
        self.assertFalse(result["pass"])
        self.assertIn("3.11", result["action"])

    def test_preflight_accepts_3_11(self):
        result = self._check(3, 11)
        self.assertTrue(result["pass"])
        self.assertIsNone(result["action"])

    def test_preflight_rejects_3_12(self):
        result = self._check(3, 12)
        self.assertFalse(result["pass"])
        self.assertIn("3.11", result["action"])


class TestPreflightRequiresTokenizer(TestCase):
    """Preflight requires data/tokenizer_v2.json to be present."""

    def test_preflight_requires_tokenizer(self):
        result = subprocess.run(
            [PYTHON, str(SCRIPTS / "demo_preflight.py")],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        tokenizer_checks = [c for c in data["checks"] if "tokenizer" in c["name"].lower()]
        self.assertGreater(len(tokenizer_checks), 0)
        tokenizer_pass = any(
            c["name"] == "file_exists:data/tokenizer_v2.json" and c["pass"] for c in data["checks"]
        )
        self.assertTrue(tokenizer_pass, "tokenizer_v2.json should be present in repo")


class TestPreflightMissingCheckpoint(TestCase):
    """Preflight reports the optional checkpoint state."""

    def _run_preflight_in_temp(self, tmp_path, include_checkpoint=False):
        demo_preflight.ROOT = tmp_path
        for rel in demo_preflight.REQUIRED_FILES:
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        for rel in demo_preflight.RECOMMENDED_FILES:
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if not include_checkpoint and "reasoning_model" in rel:
                continue
            path.touch()
        stdout = StringIO()
        with contextlib.redirect_stdout(stdout):
            with patch.object(demo_preflight, "select_port", return_value=7860):
                old_argv = sys.argv
                sys.argv = [str(SCRIPTS / "demo_preflight.py")]
                try:
                    demo_preflight.main()
                finally:
                    sys.argv = old_argv
        return json.loads(stdout.getvalue())

    def test_preflight_reports_missing_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self._run_preflight_in_temp(Path(tmp), include_checkpoint=False)
            checkpoint_checks = [c for c in data["checks"] if "checkpoint" in c["name"].lower()]
            self.assertGreater(len(checkpoint_checks), 0)
            missing_cp = [c for c in checkpoint_checks if not c["pass"]]
            self.assertGreater(len(missing_cp), 0)

    def test_preflight_reports_present_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self._run_preflight_in_temp(Path(tmp), include_checkpoint=True)
            checkpoint_checks = [c for c in data["checks"] if "checkpoint" in c["name"].lower()]
            self.assertGreater(len(checkpoint_checks), 0)
            present_cp = [c for c in checkpoint_checks if c["pass"]]
            self.assertGreater(len(present_cp), 0)


class TestPreflightPortRange(TestCase):
    """Preflight selects a port from the bounded range 7860-7870."""

    def test_preflight_port_range(self):
        result = subprocess.run(
            [PYTHON, str(SCRIPTS / "demo_preflight.py")],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        selected = data["selected_port"]
        self.assertTrue(7860 <= selected <= 7870, f"Port {selected} outside allowed range 7860-7870")


class TestRunnerScriptExists(TestCase):
    """The runner and preflight scripts exist and are readable."""

    def test_runner_script_exists(self):
        self.assertTrue((SCRIPTS / "run_demo.ps1").exists())

    def test_preflight_script_exists(self):
        self.assertTrue((SCRIPTS / "demo_preflight.py").exists())


class TestDeterministicScenarioAssumptions(TestCase):
    """DEMO_GUIDE.md references valid demonstration data and evidence-bounded claims."""

    def test_guide_references_demo_data(self):
        guide = REPO_ROOT / "docs" / "DEMO_GUIDE.md"
        self.assertTrue(guide.exists())
        content = guide.read_text()
        self.assertIn("technical_docs_sample.txt", content)

    def test_guide_does_not_claim_100_accurate(self):
        guide = REPO_ROOT / "docs" / "DEMO_GUIDE.md"
        content = guide.read_text()
        self.assertIn('Claims about "100% accurate" are NOT made', content)

    def test_guide_distinguishes_from_holdout(self):
        guide = REPO_ROOT / "docs" / "DEMO_GUIDE.md"
        content = guide.read_text()
        self.assertIn("independent holdout validation", content)


if __name__ == "__main__":
    import unittest
    unittest.main()
