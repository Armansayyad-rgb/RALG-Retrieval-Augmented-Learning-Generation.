"""Holdout integrity and human-review infrastructure tests."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for entry in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import check_holdout_contamination as guard  # noqa: E402


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n",
                    encoding="utf-8")


def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


class RealHoldoutGuardTests(unittest.TestCase):
    def test_real_holdout_passes_guard(self):
        report = guard.run_guard(PROJECT_ROOT / "evaluation" / "holdout_v1", PROJECT_ROOT)
        self.assertTrue(report["pass"], f"issues: {report['issues']}")
        self.assertEqual(report["benchmark_version"], "holdout_v1.0.0")
        self.assertGreaterEqual(report["cases_checked"], 100)
        self.assertEqual(report["sources_checked"], 11)

    def test_holdout_independent_of_stage5(self):
        s5 = {entry["sha256"] for entry in guard.load_jsonl(
            PROJECT_ROOT / "evaluation" / "stage5_source_manifest.jsonl")}
        sources = guard.load_jsonl(
            PROJECT_ROOT / "evaluation" / "holdout_v1" / "sources_manifest.jsonl")
        hashes = {guard.sha256_file(PROJECT_ROOT / e["source_filename"]) for e in sources}
        self.assertFalse(hashes & s5, "holdout source identical to a Stage 5 document")
        ids = {c["case_id"] for c in guard.load_jsonl(
            PROJECT_ROOT / "evaluation" / "holdout_v1" / "holdout_benchmark.jsonl")}
        s5_ids = {c["case_id"] for c in guard.load_jsonl(
            PROJECT_ROOT / "evaluation" / "stage5_review_queue.jsonl")}
        self.assertFalse(ids & s5_ids)


class GuardLogicTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # Synthetic Stage 5 fixture set.
        doc_bytes = b"stage five rfc corpus text"
        _write_jsonl(self.root / "evaluation" / "stage5_source_manifest.jsonl",
                     [{"doc_id": "rfc_0001", "sha256": _sha(doc_bytes)}])
        (self.root / "evaluation" / "stage5_docs.bin").write_bytes(doc_bytes)
        _write_jsonl(self.root / "evaluation" / "stage5_review_queue.jsonl",
                     [{"case_id": "s5_case_001", "question": "What is TCP flow control?"}])
        # Synthetic holdout.
        h = self.root / "holdout"
        src = h / "sources"
        src.mkdir(parents=True)
        pep = b"public domain pep text about python"
        (src / "pep_0008.rst").write_bytes(pep)
        _write_jsonl(h / "sources_manifest.jsonl",
                     [{"doc_id": "pep_0008", "source_filename": str(src / "pep_0008.rst")
                       .replace("\\", "/"), "sha256": _sha(pep)}])
        benchmark = [{"case_id": "holdout_001",
                      "question": "What is the title of PEP 8?"}]
        _write_jsonl(h / "holdout_benchmark.jsonl", benchmark)
        manifest = {"benchmark_version": "holdout_v1.0.0-test",
                    "benchmark_sha256": _sha((h / "holdout_benchmark.jsonl").read_bytes()),
                    "sources_manifest_sha256":
                        _sha((h / "sources_manifest.jsonl").read_bytes())}
        (h / "holdout_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.holdout_dir = h

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_synthetic_holdout_passes(self):
        report = guard.run_guard(self.holdout_dir, self.root)
        self.assertTrue(report["pass"], report["issues"])

    def test_post_freeze_tampering_is_detected(self):
        bench = self.holdout_dir / "holdout_benchmark.jsonl"
        rows = json.loads(bench.read_text(encoding="utf-8").splitlines()[0])
        rows["question"] = "tampered question?"
        _write_jsonl(bench, [rows])
        report = guard.run_guard(self.holdout_dir, self.root)
        self.assertFalse(report["pass"])
        self.assertTrue(any("modified after freeze" in issue for issue in report["issues"]))

    def test_duplicate_question_across_stage5_is_detected(self):
        rows = [json.loads(self.holdout_dir.joinpath("holdout_benchmark.jsonl")
                           .read_text(encoding="utf-8").splitlines()[0])]
        rows.append({"case_id": "holdout_002", "question": "what is tcp flow control?"})
        _write_jsonl(self.holdout_dir / "holdout_benchmark.jsonl", rows)
        manifest = json.loads((self.holdout_dir / "holdout_manifest.json").read_text())
        manifest["benchmark_sha256"] = _sha(
            (self.holdout_dir / "holdout_benchmark.jsonl").read_bytes())
        (self.holdout_dir / "holdout_manifest.json").write_text(json.dumps(manifest))
        report = guard.run_guard(self.holdout_dir, self.root)
        self.assertTrue(any("duplicated from Stage 5" in i or "duplicate case ID" in i
                            for i in report["issues"]))

    def test_stage5_case_id_collision_detected(self):
        rows = [json.loads(self.holdout_dir.joinpath("holdout_benchmark.jsonl")
                           .read_text(encoding="utf-8").splitlines()[0]),
                {"case_id": "s5_case_001", "question": "unique question here?"}]
        _write_jsonl(self.holdout_dir / "holdout_benchmark.jsonl", rows)
        manifest = json.loads((self.holdout_dir / "holdout_manifest.json").read_text())
        manifest["benchmark_sha256"] = _sha(
            (self.holdout_dir / "holdout_benchmark.jsonl").read_bytes())
        (self.holdout_dir / "holdout_manifest.json").write_text(json.dumps(manifest))
        report = guard.run_guard(self.holdout_dir, self.root)
        self.assertTrue(any("collides with a Stage 5 case ID" in i for i in report["issues"]))


class ReviewInfrastructureTests(unittest.TestCase):
    def test_runbook_exists_and_covers_labels(self):
        runbook = PROJECT_ROOT / "docs" / "HUMAN_REVIEW_RUNBOOK.md"
        self.assertTrue(runbook.exists())
        text = runbook.read_text(encoding="utf-8")
        for token in ("accept", "reject", "ambiguous", "invalid_case", "reviewer_id"):
            self.assertIn(token, text)

    def test_no_human_review_results_exist_yet(self):
        """Honesty check: no fabricated review artifacts may be committed."""
        self.assertFalse(
            (PROJECT_ROOT / "evaluation" / "results" / "stage6_human_review_results.json")
            .exists(),
            "Stage 6 human review results must not exist before real reviews")

    def test_holdout_baseline_is_one_shot(self):
        output = PROJECT_ROOT / "evaluation" / "results" / "holdout_v1_baseline.json"
        if not output.exists():
            self.skipTest("baseline not yet generated")
        first = output.read_text(encoding="utf-8")
        from run_holdout_baseline import main as baseline_main
        with patch("sys.argv", ["run_holdout_baseline.py"]):
            exit_code = baseline_main()
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(output.read_text(encoding="utf-8"), first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
