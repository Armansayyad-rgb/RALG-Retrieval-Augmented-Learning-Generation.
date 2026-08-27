"""Independent Holdout V2 infrastructure tests."""

import json
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

import check_holdout_v2_integrity as guard  # noqa: E402


class HoldoutV2IntegrityTests(unittest.TestCase):
    def test_real_holdout_v2_passes_guard(self):
        report = guard.run_guard(PROJECT_ROOT / "evaluation" / "holdout_v2", PROJECT_ROOT)
        self.assertTrue(report["pass"], report["issues"])
        self.assertEqual(report["benchmark_version"], "holdout_v2.0.0")
        self.assertEqual(report["cases_checked"], 70)
        self.assertEqual(report["sources_checked"], 7)
        self.assertEqual(set(report["category_counts"].values()), {10})

    def test_all_traceable_spans_match_source_text(self):
        cases = guard.load_jsonl(
            PROJECT_ROOT / "evaluation" / "holdout_v2" / "holdout_benchmark.jsonl")
        sources = {
            row["doc_id"]: (PROJECT_ROOT / row["source_filename"]).read_text(encoding="utf-8-sig")
            for row in guard.load_jsonl(
                PROJECT_ROOT / "evaluation" / "holdout_v2" / "sources_manifest.jsonl")
        }
        span_count = 0
        for case in cases:
            for span in case.get("evidence_spans", []):
                span_count += 1
                self.assertEqual(
                    sources[span["doc_id"]][span["span_start"]:span["span_end"]],
                    span["quoted_text"],
                    case["case_id"],
                )
        self.assertGreaterEqual(span_count, 60)

    def test_frozen_files_are_lf_only(self):
        files = [p for p in (PROJECT_ROOT / "evaluation" / "holdout_v2").rglob("*")
                 if p.is_file()]
        self.assertGreaterEqual(len(files), 10)
        for path in files:
            data = path.read_bytes()
            self.assertNotIn(b"\r\n", data, str(path))
            self.assertTrue(data.endswith(b"\n"), str(path))

    def test_runner_refuses_existing_output_without_evaluating(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing.json"
            output.write_text('{"sentinel": true}\n', encoding="utf-8")
            from run_holdout_v2_once import main as runner_main
            with patch("sys.argv", ["run_holdout_v2_once.py", "--output", str(output)]):
                exit_code = runner_main()
            self.assertNotEqual(exit_code, 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["sentinel"], True)

    def test_builder_is_deterministic(self):
        before = (PROJECT_ROOT / "evaluation" / "holdout_v2" / "holdout_manifest.json").read_text(
            encoding="utf-8")
        subprocess.run([sys.executable, "scripts/build_holdout_v2.py"],
                       cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
        after = (PROJECT_ROOT / "evaluation" / "holdout_v2" / "holdout_manifest.json").read_text(
            encoding="utf-8")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
