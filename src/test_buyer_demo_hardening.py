"""Buyer-demo hardening regression tests.

Covers: module-path resolution without externally-set PYTHONPATH, bounded
port fallback selection, preflight port reporting, checkpoint requirement
accuracy, non-overlapping review-summary categories, and Stage 5 artifact
immutability guarantees for the Stage 6 evaluator.
"""

import csv
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for entry in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import buyer_demo_preflight as preflight  # noqa: E402
import stage5_ingest_reviews as ingest_mod  # noqa: E402
import stage6_evaluator as evaluator_mod  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _occupy(port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform == "win32":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    return sock


class ModulePathTests(unittest.TestCase):
    def test_webui_unimportable_from_root_without_pythonpath(self):
        """Reproduces failure #1: bare `python -c 'import webui.config'` must fail."""
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        proc = subprocess.run(
            [sys.executable, "-c", "import webui.config"],
            cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("No module named", proc.stderr)

    def test_launcher_provides_module_path_itself(self):
        """The launcher sets PYTHONPATH=<root>\\src so buyers need no manual step."""
        script = (PROJECT_ROOT / "scripts" / "run_buyer_demo.ps1").read_text(encoding="utf-8")
        self.assertIn("$env:PYTHONPATH = (Join-Path $ProjectRoot \"src\")", script)
        # ...and that path makes webui importable for the interpreter.
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
        proc = subprocess.run(
            [sys.executable, "-c", "from webui.config import WEBUI_PORT; print(WEBUI_PORT)"],
            cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip())

    def test_launcher_reads_selected_port_from_preflight(self):
        script = (PROJECT_ROOT / "scripts" / "run_buyer_demo.ps1").read_text(encoding="utf-8")
        self.assertIn("selected_port", script)
        self.assertIn("$env:WEBUI_PORT = [string]$preflight.selected_port", script)
        self.assertIn("webui_url", script)


class PortSelectionTests(unittest.TestCase):
    def test_prefers_requested_port_when_free(self):
        base = self._free_port()  # bound then released -> free again
        self.assertEqual(preflight.select_port(preferred=base, range_end=base), base)

    def test_falls_back_to_next_bounded_port(self):
        base = self._free_port()
        occupier = _occupy(base)
        try:
            selected = preflight.select_port(preferred=base, range_end=base + 2)
            self.assertEqual(selected, base + 1)
        finally:
            occupier.close()

    def test_returns_none_when_whole_range_occupied(self):
        base = self._free_port()
        socks = [_occupy(base), _occupy(base + 1)]
        try:
            self.assertIsNone(preflight.select_port(preferred=base, range_end=base + 1))
        finally:
            for sock in socks:
                sock.close()

    def test_never_terminates_the_occupying_process(self):
        base = self._free_port()
        occupier = _occupy(base)
        try:
            preflight.select_port(preferred=base, range_end=base + 3)
            # The occupying listener must still be alive and accepting.
            self.assertTrue(occ := occupier.getsockname()[1] == base)
            self.assertTrue(occ)
        finally:
            occupier.close()

    def test_preflight_reports_selected_port_consistently(self):
        result = preflight.check_webui_port()
        if result["pass"]:
            self.assertTrue(7860 <= result["selected_port"] <= preflight.PORT_RANGE_END)
            self.assertEqual(result["webui_url"], f"http://127.0.0.1:{result['selected_port']}")

    @staticmethod
    def _free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]


class CheckpointRequirementTests(unittest.TestCase):
    def test_embedding_model_not_required_for_runtime(self):
        """embedding_model.pt is offline index-build-only (runtime_architecture says so)."""
        self.assertNotIn(
            "checkpoints/embedding_model.pt", preflight.REQUIRED_FILES,
            "embedding_model.pt must not be mandatory: runtime loads the prebuilt index",
        )

    def test_runtime_marks_embedding_model_unused(self):
        source = (PROJECT_ROOT / "src" / "runtime_architecture.py").read_text(encoding="utf-8")
        self.assertIn("COMPATIBLE BUT UNUSED", source)

    def test_genuinely_required_artifacts_still_listed(self):
        self.assertIn("checkpoints/v2/reasoning_model_v1.pt", preflight.REQUIRED_FILES)
        self.assertIn("data/tokenizer_v2.json", preflight.REQUIRED_FILES)
        self.assertIn("checkpoints/v2", preflight.REQUIRED_CHECKPOINT_DIRS)


class ReviewSummaryCategoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        queue_dir = self.root / "evaluation"
        queue_dir.mkdir(parents=True)
        cases = [{"case_id": f"s5_case_{i:03d}", "question": f"q{i}",
                  "category": "supported", "evidence_document_ids": [],
                  "evidence_spans": [], "expected_answer": "a",
                  "difficulty": "easy", "reviewer_status": "unreviewed"}
                 for i in range(1, 5)]
        (queue_dir / "stage5_review_queue.jsonl").write_text(
            "\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_summary_categories_are_disjoint(self):
        fields = ingest_mod.FIELDS
        path = self.root / "reviews.csv"
        rows = []
        outcomes = ["accept", "reject", "ambiguous", "invalid_case"]
        for case_index, outcome in enumerate(outcomes, start=1):
            row = {field: "" for field in fields}
            row.update({
                "case_id": f"s5_case_{case_index:03d}",
                "accept_reject": outcome,
                "answerable_yes_no": "yes", "expected_support_correct": "yes",
                "reference_answer_correct": "yes", "evidence_supports_answer": "yes",
                "source_attribution_correct": "yes", "question_clear": "yes",
                "difficulty": "easy", "reviewer_notes": "checked",
                "reviewer_id": "reviewer_a",
            })
            rows.append(row)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        summary = ingest_mod.ingest(self.root, path, "reviewer_a", self.root / "out.jsonl")
        categories = (
            summary["accepted"] + summary["rejected"]
            + summary["ambiguous"] + summary["invalid_case"]
        )
        # Non-overlapping: rejected counts EXPLICIT rejects only.
        self.assertEqual(summary["accepted"], 1)
        self.assertEqual(summary["rejected"], 1)
        self.assertEqual(summary["ambiguous"], 1)
        self.assertEqual(summary["invalid_case"], 1)
        self.assertEqual(categories, summary["submitted"])
        self.assertEqual(summary["remaining_unreviewed"], 0)

    def test_remaining_unreviewed_counts_missing_submissions(self):
        path = self.root / "partial.csv"
        row = {field: "" for field in ingest_mod.FIELDS}
        row.update({
            "case_id": "s5_case_001", "accept_reject": "accept",
            "answerable_yes_no": "yes", "expected_support_correct": "yes",
            "reference_answer_correct": "yes", "evidence_supports_answer": "yes",
            "source_attribution_correct": "yes", "question_clear": "yes",
            "difficulty": "easy", "reviewer_notes": "checked",
            "reviewer_id": "reviewer_a",
        })
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=ingest_mod.FIELDS)
            writer.writeheader()
            writer.writerow(row)
        summary = ingest_mod.ingest(self.root, path, "reviewer_a",
                                    self.root / "p.jsonl", allow_partial=True)
        self.assertEqual(summary["remaining_unreviewed"], 3)
        self.assertTrue(summary["partial"])


class Stage5ArtifactImmutabilityTests(unittest.TestCase):
    def test_evaluator_wording_names_authoritative_baseline(self):
        self.assertIn("authoritative frozen Stage 5 baseline artifact",
                      evaluator_mod.BASELINE_REFERENCE)
        self.assertIn("never mutated", evaluator_mod.BASELINE_REFERENCE)

    def test_evaluator_output_is_a_separate_namespace(self):
        self.assertEqual(evaluator_mod.DEFAULT_OUTPUT.name, "stage6_human_review_results.json")
        self.assertNotEqual(
            evaluator_mod.DEFAULT_OUTPUT,
            PROJECT_ROOT / "evaluation" / "results" / "stage5_preliminary_results.json",
        )

    def test_evaluator_run_leaves_stage5_artifact_byte_identical(self):
        stage5_path = PROJECT_ROOT / "evaluation" / "results" / "stage5_preliminary_results.json"
        if not stage5_path.exists():
            self.skipTest("Stage 5 artifact not present")
        queue = PROJECT_ROOT / "evaluation" / "stage5_review_queue.jsonl"
        first_case_id = json.loads(queue.read_text(encoding="utf-8").splitlines()[0])["case_id"]
        with tempfile.TemporaryDirectory() as tmp:
            reviewed = Path(tmp) / "reviewed.jsonl"
            reviewed.write_text(json.dumps({
                "case_id": first_case_id, "reviewer_id": "r1",
                "review_outcome": "accept", "reviewer_status": "accepted",
            }) + "\n", encoding="utf-8")
            before = _sha256(stage5_path)
            from unittest.mock import patch
            with patch("sys.argv", ["stage6_evaluator.py", "--reviewed", str(reviewed),
                                    "--output", str(Path(tmp) / "out.json")]):
                exit_code = evaluator_mod.main()
            after = _sha256(stage5_path)
        self.assertEqual(exit_code, 0)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
