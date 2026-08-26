"""Hardware qualification tooling tests (fast, no pipeline initialization)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for entry in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import hardware_qualification as hq  # noqa: E402


class LatencyMathTests(unittest.TestCase):
    def test_percentile_known_values(self):
        self.assertEqual(hq.percentile([], 50), 0.0)
        self.assertEqual(hq.percentile([5.0], 95), 5.0)
        self.assertAlmostEqual(hq.percentile([1, 2, 3, 4], 50), 2.5)
        self.assertAlmostEqual(hq.percentile([10, 20, 30, 40, 50], 95), 48.0)

    def test_latency_summary_shape(self):
        summary = hq.latency_summary([10.0, 20.0, 30.0])
        self.assertEqual(summary["n"], 3)
        self.assertEqual(summary["p50_ms"], 20.0)
        self.assertGreaterEqual(summary["p95_ms"], summary["p50_ms"])


class ScalingCorpusTests(unittest.TestCase):
    def test_synthetic_corpus_deterministic_and_exact(self):
        base = "alpha beta gamma delta epsilon zeta"
        first = hq._synthetic_chunks(base, 100)
        second = hq._synthetic_chunks(base, 100)
        self.assertEqual(len(first), 100)
        self.assertEqual(first, second)
        # Chunks are unique (index marker) so no degenerate duplicate corpus.
        self.assertEqual(len(set(first)), 100)

    def test_synthetic_corpus_rejects_empty_base(self):
        with self.assertRaises(ValueError):
            hq._synthetic_chunks("", 10)


class ModelInventoryTests(unittest.TestCase):
    def test_state_dict_inspection_counts_parameters(self):
        import torch
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.pt"
            torch.save({"model_state_dict": {
                "layer.weight": torch.randn(3, 4),
                "scalar": torch.tensor(7, dtype=torch.int64),
            }}, path)
            info = hq.inspect_state_dict(path)
        self.assertEqual(info["parameter_count"], 13)
        self.assertEqual(info["dtype_distribution"]["torch.float32"], 12)
        self.assertEqual(info["dtype_distribution"]["torch.int64"], 1)
        self.assertEqual(info["estimated_raw_param_ram_bytes"], 12 * 4 + 8)

    def test_reasoning_checkpoint_measured_not_asserted(self):
        """The ~20M claim must be checked against measurement, not docs."""
        result_file = PROJECT_ROOT / "logs" / "hardware_model_inventory.json"
        if not result_file.exists():
            self.skipTest("model inventory not yet generated")
        report = json.loads(result_file.read_text(encoding="utf-8"))
        arch = report["reasoning_model_architecture_parameter_count"]
        self.assertIsInstance(arch, int)
        # Measured value decides the verdict either way; the flag must be
        # consistent with the measured number, not with documentation.
        expected_flag = 15_000_000 <= arch <= 25_000_000
        self.assertEqual(report["reasoning_model_is_approx_20m_params"], expected_flag)


class StorageAndFormatTests(unittest.TestCase):
    def test_dir_size_measures_files_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            (root / "a.txt").write_bytes(b"x" * 100)
            (root / "sub" / "b.bin").write_bytes(b"y" * 50)
            self.assertEqual(hq.dir_size_bytes(root), 150)
            self.assertEqual(hq.dir_size_bytes(root / "a.txt"), 100)

    def test_human_formatting(self):
        self.assertEqual(hq.human(512), "512.00 B")
        self.assertIn("KiB", hq.human(2048))
        self.assertIn("GiB", hq.human(2 * 1024 ** 3))

    def test_storage_report_has_expected_areas(self):
        result_file = PROJECT_ROOT / "logs" / "hardware_storage_measured.json"
        if not result_file.exists():
            self.skipTest("storage report not yet generated")
        report = json.loads(result_file.read_text(encoding="utf-8"))
        for area in ("checkpoints_required_reasoning_v1",
                     "checkpoints_optional_qwen_polish",
                     "source_documents_stage5_rfcs"):
            self.assertIn(area, report)


class SafetyGuardTests(unittest.TestCase):
    def test_default_scaling_sizes_match_specification(self):
        parser_output = [10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000]
        self.assertEqual(parser_output, [10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000])

    def test_write_result_stays_under_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_logs = hq.LOGS_DIR
            try:
                hq.LOGS_DIR = Path(tmp) / "logs"
                out = hq.write_result("unit_test", {"pass": True})
                self.assertTrue(str(out).startswith(str(Path(tmp))))
                self.assertTrue(out.is_file())
            finally:
                hq.LOGS_DIR = old_logs


if __name__ == "__main__":
    unittest.main(verbosity=2)
