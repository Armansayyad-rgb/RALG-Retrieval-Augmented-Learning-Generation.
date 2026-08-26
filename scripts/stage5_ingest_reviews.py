#!/usr/bin/env python3
"""Ingest real reviewer forms and freeze an accepted Stage 5 benchmark."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    "case_id", "answerable_yes_no", "expected_support_correct",
    "reference_answer_correct", "evidence_supports_answer",
    "source_attribution_correct", "question_clear", "difficulty",
    "accept_reject", "corrected_answer", "corrected_evidence",
    "reviewer_notes", "reviewer_id",
]
REQUIRED_DECISIONS = {
    "answerable_yes_no", "expected_support_correct",
    "reference_answer_correct", "evidence_supports_answer",
    "source_attribution_correct", "question_clear", "accept_reject",
}
# Explicit reviewer outcome labels. "ambiguous" and "invalid_case" are
# recorded but never count as approved cases in downstream evaluation.
VALID_OUTCOMES = {"accept", "reject", "ambiguous", "invalid_case"}


def load_cases(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def read_reviews(path: Path, reviewer_label: str) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"missing reviewer fields: {', '.join(missing)}")
        rows = list(reader)
    seen = set()
    for row in rows:
        case_id = row["case_id"].strip()
        if not case_id:
            raise ValueError("review submission contains an empty case_id")
        if case_id in seen:
            raise ValueError(f"duplicate reviewer submission for {case_id}")
        seen.add(case_id)
        if row["reviewer_id"].strip() != reviewer_label:
            raise ValueError(f"{case_id}: reviewer_id does not match --reviewer-label")
        if not all(row[field].strip() for field in REQUIRED_DECISIONS):
            raise ValueError(f"{case_id}: incomplete review decision")
        outcome = row["accept_reject"].strip().casefold()
        if outcome not in VALID_OUTCOMES:
            allowed = ", ".join(sorted(VALID_OUTCOMES))
            raise ValueError(f"{case_id}: invalid accept_reject label '{row['accept_reject'].strip()}'; allowed: {allowed}")
    if not rows:
        raise ValueError("review submission is empty; no reviewer decisions were provided")
    return rows


def ingest(root: Path, review_file: Path, reviewer_label: str, output: Path, allow_partial: bool = False) -> dict:
    cases = load_cases(root / "evaluation" / "stage5_review_queue.jsonl")
    by_id = {case["case_id"]: case for case in cases}
    reviews = read_reviews(review_file, reviewer_label)
    unknown = sorted(set(row["case_id"] for row in reviews) - set(by_id))
    if unknown:
        raise ValueError(f"unknown case IDs: {', '.join(unknown)}")
    if len(reviews) < len(cases) and not allow_partial:
        raise ValueError(
            f"partial submission: {len(reviews)} of {len(cases)} cases reviewed; "
            "pass --allow-partial to record an explicitly partial review round"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    reviewed = []
    for case in cases:
        item = dict(case)
        row = next((row for row in reviews if row["case_id"] == case["case_id"]), None)
        if row:
            outcome = row["accept_reject"].strip().casefold()
            item["review"] = {field: row[field].strip() for field in FIELDS if field != "case_id"}
            item["reviewer_status"] = "accepted" if outcome == "accept" else "rejected"
            item["review_outcome"] = outcome
            item["reviewer_id"] = reviewer_label
            if row["corrected_answer"].strip():
                item["reviewed_corrected_answer"] = row["corrected_answer"].strip()
            if row["corrected_evidence"].strip():
                item["reviewed_corrected_evidence"] = row["corrected_evidence"].strip()
        reviewed.append(item)
    output.write_text("\n".join(json.dumps(item, sort_keys=True) for item in reviewed) + "\n", encoding="utf-8")
    outcomes = [item.get("review_outcome") for item in reviewed if item.get("review_outcome")]
    return {
        "input_reviewer": reviewer_label,
        "submitted": len(reviews),
        "accepted": sum(item.get("reviewer_status") == "accepted" for item in reviewed),
        "rejected": sum(item.get("reviewer_status") == "rejected" for item in reviewed),
        "ambiguous": outcomes.count("ambiguous"),
        "invalid_case": outcomes.count("invalid_case"),
        "remaining_unreviewed": sum(item.get("reviewer_status") == "unreviewed" for item in reviewed),
        "partial": len(reviews) < len(cases),
        "output": str(output),
    }


def freeze(root: Path, reviewed_path: Path) -> dict:
    cases = load_cases(reviewed_path)
    if not cases:
        raise ValueError("reviewed benchmark is empty")
    if any(case.get("reviewer_status") not in {"accepted", "rejected"} for case in cases):
        raise ValueError("cannot freeze while cases are unreviewed or flagged")
    accepted = [case for case in cases if case["reviewer_status"] == "accepted"]
    final_path = root / "evaluation" / "stage5_final_benchmark.jsonl"
    final_path.write_text("\n".join(json.dumps(case, sort_keys=True) for case in accepted) + "\n", encoding="utf-8")
    corpus_manifest = root / "evaluation" / "stage5_source_manifest.jsonl"
    reviewer_ids = sorted({case.get("reviewer_id") for case in accepted if case.get("reviewer_id")})
    manifest = {
        "benchmark_sha256": hashlib.sha256(final_path.read_bytes()).hexdigest(),
        "case_count": len(accepted),
        "accepted_count": len(accepted),
        "rejected_count": len(cases) - len(accepted),
        "corrected_count": sum(bool(case.get("reviewed_corrected_answer") or case.get("reviewed_corrected_evidence")) for case in accepted),
        "reviewer_ids": reviewer_ids,
        "review_timestamp": datetime.now(timezone.utc).isoformat(),
        "corpus_manifest_sha256": hashlib.sha256(corpus_manifest.read_bytes()).hexdigest(),
        "production_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    }
    manifest_path = root / "evaluation" / "results" / "stage5_final_benchmark_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def merge_reviews(first_path: Path, second_path: Path, output: Path, disagreements: Path) -> dict:
    first = {case["case_id"]: case for case in load_cases(first_path)}
    second = {case["case_id"]: case for case in load_cases(second_path)}
    if set(first) != set(second):
        raise ValueError("reviewed artifacts must contain the same case IDs")
    merged = []
    disagreement_rows = []
    for case_id in sorted(first):
        left, right = first[case_id], second[case_id]
        left_review = left.get("review", {})
        right_review = right.get("review", {})
        differing = sorted(
            field for field in REQUIRED_DECISIONS
            if left_review.get(field) != right_review.get(field)
        )
        item = dict(left)
        item["reviews"] = [
            {"reviewer_id": left.get("reviewer_id"), **left_review},
            {"reviewer_id": right.get("reviewer_id"), **right_review},
        ]
        item["disagreement"] = bool(differing)
        if differing:
            disagreement_rows.append({
                "case_id": case_id,
                "fields": differing,
                "reviewer_ids": [left.get("reviewer_id"), right.get("reviewer_id")],
            })
        merged.append(item)
    output.parent.mkdir(parents=True, exist_ok=True)
    disagreements.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(item, sort_keys=True) for item in merged) + "\n", encoding="utf-8")
    disagreements.write_text("\n".join(json.dumps(item, sort_keys=True) for item in disagreement_rows) + ("\n" if disagreement_rows else ""), encoding="utf-8")
    return {
        "cases": len(merged),
        "disagreements": len(disagreement_rows),
        "output": str(output),
        "disagreement_queue": str(disagreements),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    ingest_parser = sub.add_parser("ingest")
    ingest_parser.add_argument("--input", type=Path, required=True)
    ingest_parser.add_argument("--reviewer-label", required=True)
    ingest_parser.add_argument("--output", type=Path, required=True)
    ingest_parser.add_argument("--allow-partial", action="store_true",
                               help="record an explicitly partial review round instead of failing")
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--reviewed-benchmark", type=Path, required=True)
    merge_parser = sub.add_parser("merge")
    merge_parser.add_argument("--reviewer-a", type=Path, required=True)
    merge_parser.add_argument("--reviewer-b", type=Path, required=True)
    merge_parser.add_argument("--output", type=Path, required=True)
    merge_parser.add_argument("--disagreements", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "ingest":
            result = ingest(ROOT, args.input, args.reviewer_label, args.output, allow_partial=args.allow_partial)
        elif args.command == "freeze":
            result = freeze(ROOT, args.reviewed_benchmark)
        else:
            result = merge_reviews(args.reviewer_a, args.reviewer_b, args.output, args.disagreements)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"pass": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"pass": True, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
