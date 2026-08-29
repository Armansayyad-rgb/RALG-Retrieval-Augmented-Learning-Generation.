"""Focused launcher-contract tests for the buyer demo.

Verifies the canonical Windows buyer-demo path launches ``webui_bootstrap``
(not ``webui.app``), the bounded port-failure message is valid, the endpoint
display is not misleading, and the readiness documentation matches ``/ready``
semantics.

These tests do not run Holdout V1/V2/V3 or any benchmark that touches frozen
independent evidence, and they do not modify ``/ready`` behavior or semantics.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
SRC = REPO_ROOT / "src"
DOCS = REPO_ROOT / "docs"

LAUNCHER = SCRIPTS / "run_buyer_demo.ps1"
BOOTSTRAP = SRC / "webui_bootstrap.py"
GUIDE = DOCS / "BUYER_DEMO_GUIDE.md"
README = REPO_ROOT / "README.md"


class TestLauncherWebUIEntrypoint(unittest.TestCase):
    """The canonical Windows buyer-demo path must launch webui_bootstrap."""

    def test_launcher_launches_webui_bootstrap(self):
        content = LAUNCHER.read_text()
        self.assertIn("-m webui_bootstrap", content)
        # The direct app entry point must not be used: it bypasses the gradio
        # compatibility patch and the Python 3.11 runtime guard.
        self.assertNotIn("-m webui.app", content)

    def test_launcher_preserves_port_env_behavior(self):
        content = LAUNCHER.read_text()
        # Port selection from preflight is still threaded through WEBUI_PORT.
        self.assertIn("WEBUI_PORT", content)
        self.assertIn("selected_port", content)


class TestBootstrapReachesRuntimeGuard(unittest.TestCase):
    """webui_bootstrap wires in the gradio patch and the Python 3.11 guard."""

    def test_bootstrap_imports_runtime_guard(self):
        content = BOOTSTRAP.read_text()
        self.assertIn("import runtime_guard", content)
        self.assertIn("runtime_guard.enforce_python_311()", content)

    def test_bootstrap_patches_gradio_client(self):
        content = BOOTSTRAP.read_text()
        self.assertIn("get_type", content)
        self.assertIn('"boolean"', content)


class TestPortFailureMessage(unittest.TestCase):
    """The all-ports-busy message must reference the real bounded range."""

    def test_port_failure_message_uses_bounded_range(self):
        content = LAUNCHER.read_text()
        self.assertIn("7860-7870", content)

    def test_port_failure_message_has_no_undefined_vars(self):
        content = LAUNCHER.read_text()
        self.assertNotIn("$PORT_RANGE_START", content)
        self.assertNotIn("$PORT_RANGE_END", content)


class TestEndpointDisplayNotMisleading(unittest.TestCase):
    """The launcher's endpoint line must not present a partial list as complete."""

    def test_endpoint_display_qualifies_list(self):
        content = LAUNCHER.read_text()
        # The old misleading bare "endpoints:" partial list must be gone.
        self.assertNotIn(
            "(endpoints: /health, /ready, /ingest, /query)", content
        )
        # It should label the shown URLs as common/demo rather than complete.
        self.assertRegex(content, r"(common|demo).*(endpoints|/health)")

    def test_api_only_variant_lists_delete_route(self):
        content = GUIDE.read_text()
        self.assertIn("DELETE /documents/{document_id}", content)


class TestDocsReadinessSemantics(unittest.TestCase):
    """Docs must not imply extractive-without-checkpoint => /ready 200."""

    def test_buyer_guide_readiness_semantics(self):
        content = GUIDE.read_text()
        self.assertIn("extractive-only", content)
        self.assertIn("503", content)

    def test_readme_readiness_semantics(self):
        content = README.read_text()
        self.assertIn("extractive-only", content)
        self.assertIn("503", content)


if __name__ == "__main__":
    unittest.main()
