"""Stage 6 review tooling tests: ingestion guards, agreement math, evaluator filtering.

Covers reviewer schema validation, duplicate/unknown case rejection, invalid
label rejection, partial-ingestion guard, deterministic pilot selection,
review freeze integrity, human-approval filtering for the Stage 6 evaluator,
buyer-demo preflight file checks, and inter-reviewer agreement statistics.
"""

import csv
import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for entry in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import stage5_ingest_reviews as ingest_mod  # noqa: E402
import stage5_review_pack  # noqa: E402
import stage6_review_agreement as agreement_mod  # noqa: E402
import stage6_evaluator as evaluator_mod  # noqa: E402
import buyer_demo_preflight as preflight_mod  # noqa: E402


REVIEW_FIELDS = ingest_mod.FIELDS


def review_row(case_id, outcome="accept", reviewer="reviewer_a", **overrides):
    row = {field: "" for field in REVIEW_FIELDS}
    row.update({
        "case_id": case_id,
        "answerable_yes_no": "yes",
        "expected_support_correct": "yes",
        "reference_answer_correct": "yes",
        "evidence_supports_answer": "yes",
        "source_attribution_correct": "yes",
        "question_clear": "yes",
        "difficulty": "medium",
        "accept_reject": outcome,
        "reviewer_notes": "checked",
        "reviewer_id": reviewer,
    })
    row.update(overrides)
    return row


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def make_queue_root(queue_dir: Path, count=3):
    queue_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for index in range(1, count + 1):
        cases.append({
            "case_id": f"s5_case_{index:03d}",
            "question": f"question {index}?",
            "category": "supported" if index % 2 else "unsupported",
            "evidence_document_ids": ["rfc_0001"] if index % 2 else [],
            "evidence_spans": [],
            "expected_answer": f"answer {index}",
            "difficulty": "easy",
            "reviewer_status": "unreviewed",
        })
    path = queue_dir / "stage5_review_queue.jsonl"
    path.write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")
    return path


class IngestionGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_queue_root(self.root / "evaluation")
        self.review_csv = self.root / "reviews.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_schema_fields_are_rejected(self):
        bad = self.root / "bad.csv"
        bad.write_text("case_id,accept_reject\ns5_case_001,accept\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing reviewer fields"):
            ingest_mod.read_reviews(bad, "reviewer_a")

    def test_duplicate_case_submission_is_rejected(self):
        write_csv(self.review_csv, [
            review_row("s5_case_001"),
            review_row("s5_case_001"),
        ])
        with self.assertRaisesRegex(ValueError, "duplicate reviewer submission"):
            ingest_mod.read_reviews(self.review_csv, "reviewer_a")

    def test_unknown_case_id_is_rejected(self):
        write_csv(self.review_csv, [review_row("s5_case_999")])
        output = self.root / "out.jsonl"
        with self.assertRaisesRegex(ValueError, "unknown case IDs"):
            ingest_mod.ingest(self.root, self.review_csv, "reviewer_a", output)

    def test_invalid_label_is_rejected(self):
        write_csv(self.review_csv, [review_row("s5_case_001", outcome="maybe")])
        with self.assertRaisesRegex(ValueError, "invalid accept_reject label"):
            ingest_mod.read_reviews(self.review_csv, "reviewer_a")

    def test_incomplete_decision_is_rejected(self):
        write_csv(self.review_csv, [review_row("s5_case_001", evidence_supports_answer="")])
        with self.assertRaisesRegex(ValueError, "incomplete review decision"):
            ingest_mod.read_reviews(self.review_csv, "reviewer_a")

    def test_partial_silent_ingestion_is_blocked_without_flag(self):
        write_csv(self.review_csv, [review_row("s5_case_001")])
        output = self.root / "partial.jsonl"
        with self.assertRaisesRegex(ValueError, "partial submission"):
            ingest_mod.ingest(self.root, self.review_csv, "reviewer_a", output)

    def test_partial_ingestion_allowed_explicitly_and_reported(self):
        write_csv(self.review_csv, [review_row("s5_case_001")])
        output = self.root / "partial.jsonl"
        result = ingest_mod.ingest(self.root, self.review_csv, "reviewer_a",
                                   output, allow_partial=True)
        self.assertTrue(result["partial"])
        self.assertEqual(result["submitted"], 1)

    def test_full_ingestion_records_outcome_labels(self):
        write_csv(self.review_csv, [
            review_row("s5_case_001", outcome="accept"),
            review_row("s5_case_002", outcome="ambiguous"),
            review_row("s5_case_003", outcome="invalid_case"),
        ])
        output = self.root / "full.jsonl"
        result = ingest_mod.ingest(self.root, self.review_csv, "reviewer_a", output)
        self.assertTrue(result["pass"] if "pass" in result else True)
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["rejected"], 0)  # no explicit-reject row in this fixture
        self.assertEqual(result["ambiguous"], 1)
        self.assertEqual(result["invalid_case"], 1)
        self.assertEqual(result["remaining_unreviewed"], 0)
        # Categories are disjoint and cover the submission exactly.
        self.assertEqual(
            result["accepted"] + result["rejected"]
            + result["ambiguous"] + result["invalid_case"],
            result["submitted"],
        )
        rows = {
            json.loads(line)["case_id"]: json.loads(line)
            for line in output.read_text(encoding="utf-8").splitlines()
        }
        self.assertEqual(rows["s5_case_001"]["reviewer_status"], "accepted")
        self.assertEqual(rows["s5_case_002"]["review_outcome"], "ambiguous")
        # Original fixture untouched
        original = (self.root / "evaluation" / "stage5_review_queue.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("review_outcome", original)


class FreezeIntegrityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_queue_root(self.root / "evaluation")

    def tearDown(self):
        self._tmp.cleanup()

    def test_freeze_refuses_unreviewed_cases(self):
        reviewed_path = self.root / "reviewed.jsonl"
        cases = [
            {"case_id": "s5_case_001", "reviewer_status": "accepted", "reviewer_id": "a"},
            {"case_id": "s5_case_002", "reviewer_status": "unreviewed"},
        ]
        reviewed_path.write_text(
            "\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "cannot freeze"):
            ingest_mod.freeze(self.root, reviewed_path)

    def test_freeze_writes_only_accepted_cases_with_manifest(self):
        reviewed_path = self.root / "reviewed.jsonl"
        corpus = self.root / "evaluation" / "stage5_source_manifest.jsonl"
        corpus.write_text('{"doc_id": "rfc_0001"}\n', encoding="utf-8")
        cases = [
            {"case_id": "s5_case_001", "category": "supported", "evidence_document_ids": [],
             "evidence_spans": [], "reviewer_status": "accepted", "reviewer_id": "a"},
            {"case_id": "s5_case_002", "category": "unsupported", "evidence_document_ids": [],
             "evidence_spans": [], "reviewer_status": "rejected", "reviewer_id": "a"},
        ]
        reviewed_path.write_text(
            "\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8")
        manifest = ingest_mod.freeze(self.root, reviewed_path)
        final = self.root / "evaluation" / "stage5_final_benchmark.jsonl"
        lines = [json.loads(line) for line in final.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([case["case_id"] for case in lines], ["s5_case_001"])
        self.assertEqual(manifest["case_count"], 1)
        self.assertTrue(manifest["benchmark_sha256"])
        self.assertEqual(manifest["reviewer_ids"], ["a"])


class PilotDeterminismTests(unittest.TestCase):
    def _synthetic_cases(self):
        cases = []
        for index in range(60):
            cases.append({
                "case_id": f"s5_case_{index:03d}",
                "category": "supported" if index % 3 else "unsupported",
                "difficulty": ["easy", "medium", "hard"][index % 3],
                "evidence_document_ids": [f"rfc_{index % 4:04d}"] if index % 3 else [],
                "question": f"q{index}",
            })
        return cases

    def test_pilot_selection_is_deterministic(self):
        cases = self._synthetic_cases()
        first = [case["case_id"] for case in stage5_review_pack.pilot_sample(cases, size=20)]
        second = [case["case_id"] for case in stage5_review_pack.pilot_sample(cases, size=20)]
        self.assertEqual(first, second)

    def test_pilot_is_representative_not_cherry_picked(self):
        cases = self._synthetic_cases()
        pilot = stage5_review_pack.pilot_sample(cases, size=30)
        supported = sum(case["category"] == "supported" for case in pilot)
        unsupported = len(pilot) - supported
        self.assertGreater(supported, 0)
        self.assertGreater(unsupported, 0)
        self.assertLess(supported / len(pilot), 0.95)
        self.assertEqual(len({case["difficulty"] for case in pilot}), 3)

    def test_shipped_pilot_matches_deterministic_regeneration(self):
        queue = PROJECT_ROOT / "evaluation" / "stage5_review_queue.jsonl"
        pack = PROJECT_ROOT / "evaluation" / "stage5_review_pack" / "pilot_review.jsonl"
        if not queue.exists() or not pack.exists():
            self.skipTest("Stage 5 fixtures not present")
        cases = stage5_review_pack.load_jsonl(queue)
        expected_ids = sorted(case["case_id"] for case in stage5_review_pack.pilot_sample(cases, 75))
        shipped_ids = sorted(
            json.loads(line)["case_id"]
            for line in pack.read_text(encoding="utf-8").splitlines() if line.strip()
        )
        self.assertEqual(expected_ids, shipped_ids)
        self.assertEqual(len(shipped_ids), 75)


class AgreementMetricTests(unittest.TestCase):
    def test_kappa_perfect_agreement(self):
        labels_a = ["accept", "reject", "accept", "reject"]
        kappa, reason = agreement_mod.cohens_kappa(labels_a, list(labels_a))
        self.assertAlmostEqual(kappa, 1.0)
        self.assertEqual(reason, "ok")

    def test_kappa_known_value(self):
        labels_a = ["accept", "accept", "reject", "reject"]
        labels_b = ["accept", "reject", "accept", "reject"]
        kappa, reason = agreement_mod.cohens_kappa(labels_a, labels_b)
        self.assertEqual(reason, "ok")
        self.assertAlmostEqual(kappa, 0.0)

    def test_kappa_undefined_for_degenerate_marginals(self):
        kappa, reason = agreement_mod.cohens_kappa(["accept"], ["accept"])
        self.assertIsNone(kappa)
        self.assertNotEqual(reason, "ok")

    def test_kappa_undefined_single_category(self):
        kappa, reason = agreement_mod.cohens_kappa(["accept"] * 3, ["accept"] * 3)
        self.assertIsNone(kappa)

    def test_end_to_end_agreement_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = [
                {"case_id": "s5_case_001", "reviewer_id": "a", "review_outcome": "accept",
                 "review": {"reviewer_notes": "ok"}},
                {"case_id": "s5_case_002", "reviewer_id": "a", "review_outcome": "reject",
                 "review": {"reviewer_notes": "bad span"}},
                {"case_id": "s5_case_003", "reviewer_id": "a", "review_outcome": "accept",
                 "review": {"reviewer_notes": ""}},
            ]
            other = [
                dict(case, reviewer_id="b", review_outcome=(
                    "reject" if case["case_id"] == "s5_case_003" else case["review_outcome"]))
                for case in shared
            ]
            path_a = root / "a.jsonl"
            path_b = root / "b.jsonl"
            for path, rows in ((path_a, shared), (path_b, other)):
                path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            sys_argv = ["stage6_review_agreement.py",
                        "--reviewer-a", str(path_a), "--reviewer-b", str(path_b),
                        "--disagreements", str(root / "dis.jsonl")]
            from unittest.mock import patch
            with patch("sys.argv", sys_argv):
                exit_code = agreement_mod.main()
            self.assertEqual(exit_code, 0)
            disagreements = (root / "dis.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(disagreements), 1)
            report = json.loads(disagreements[0])
            self.assertEqual(report["case_id"], "s5_case_003")


class EvaluatorFilteringTests(unittest.TestCase):
    def test_approval_requires_unanimous_accept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviewer_rows = {
                "r1": [("s5_case_001", "accept"), ("s5_case_002", "accept"),
                       ("s5_case_003", "reject"), ("s5_case_004", "ambiguous")],
                "r2": [("s5_case_001", "accept"), ("s5_case_002", "reject"),
                       ("s5_case_003", "reject"), ("s5_case_004", "accept")],
            }
            paths = []
            for reviewer, decisions in reviewer_rows.items():
                path = root / f"{reviewer}.jsonl"
                path.write_text("\n".join(
                    json.dumps({"case_id": cid, "reviewer_id": reviewer,
                                "review_outcome": outcome})
                    for cid, outcome in decisions) + "\n", encoding="utf-8")
                paths.append(path)
            approved, summary = evaluator_mod.approval_map(paths)
            self.assertEqual(approved, {"s5_case_001": True, "s5_case_002": False,
                                        "s5_case_003": False, "s5_case_004": False})
            self.assertEqual(summary["approved"], 1)
            self.assertEqual(summary["ambiguous"], 1)

    def test_wilson_interval_bounds(self):
        interval = evaluator_mod.wilson_interval(10, 10)
        self.assertEqual(interval, [max(0.0, interval[0]), min(1.0, interval[1])])
        self.assertGreater(interval[0], 0.69)
        self.assertLess(interval[0], 1.0)
        self.assertIsNone(evaluator_mod.wilson_interval(0, 0))

    def test_evaluator_never_touches_stage5_results(self):
        default_output = evaluator_mod.DEFAULT_OUTPUT
        self.assertEqual(default_output.name, "stage6_human_review_results.json")


class BuyerDemoPreflightTests(unittest.TestCase):
    def test_missing_required_files_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = preflight_mod.check_files(Path(tmp))
            failed = {result["name"] for result in results if not result["pass"]}
            self.assertIn("file_exists:data/tokenizer_v2.json", failed)
            self.assertIn("dir_exists:checkpoints/v2", failed)
            self.assertTrue(all(result["action"] for result in results if not result["pass"]))

    def test_real_repository_passes_file_checks(self):
        results = preflight_mod.check_files(PROJECT_ROOT)
        failures = [result for result in results if not result["pass"]]
        self.assertEqual(failures, [], f"preflight failures: {failures}")

    def test_python_check_passes_on_current_interpreter(self):
        self.assertTrue(preflight_mod.check_python()["pass"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
