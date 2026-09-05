#!/usr/bin/env python3
"""Generate blinded human-adjudication packets for Holdout V4.

This script is post-run analysis only. It reads, but never modifies, the frozen
benchmark and the immutable official result artifact. It deliberately strips
machine support decisions, confidence, scores, latency, answer types, aggregate
metrics, and category-level performance information from reviewer packets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Iterable

OFFICIAL_RESULT_SHA256 = "fad3c3baf73d192fa4fb7b21fa891fa0d6a3a29bd1c52009175a480adcadde23"
HUMAN_FAMILIES = {
    "supported_factual",
    "paraphrased_supported",
    "procedural",
    "causal",
    "cross_document",
    "document_scoped",
    "conflicting_evidence",
    "conditional_or_qualified",
}
EXPECTED_REVIEW_CASES = 115


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"{path}:{lineno}: expected JSON object")
            rows.append(obj)
    return rows


def find_case_records(obj: Any) -> list[dict[str, Any]]:
    """Find the list of per-case output records without relying on one key name."""
    candidates: list[list[dict[str, Any]]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            dicts = [x for x in value if isinstance(x, dict)]
            if dicts and len(dicts) == len(value) and all("case_id" in x for x in dicts):
                candidates.append(dicts)
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(obj)
    if not candidates:
        raise ValueError("Could not locate per-case result records containing case_id")
    return max(candidates, key=len)


def clean_retrieved_evidence(result_case: dict[str, Any]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for source in result_case.get("sources") or []:
        if not isinstance(source, dict):
            continue
        cleaned.append(
            {
                "document_id": source.get("document_id"),
                "evidence": source.get("evidence") or source.get("preview"),
            }
        )
    return cleaned


def make_packet_case(benchmark_case: dict[str, Any], result_case: dict[str, Any]) -> dict[str, Any]:
    # Only information explicitly useful for blinded answer adjudication is exposed.
    # Category, support decision, answer_type, confidence, retrieval scores/ranks,
    # latency, aggregate metrics, and machine pass/fail hints are intentionally absent.
    return {
        "case_id": benchmark_case["case_id"],
        "question": benchmark_case.get("question"),
        "ground_truth_answer": benchmark_case.get("ground_truth_answer"),
        "expected_behavior": benchmark_case.get("expected_behavior"),
        "required_evidence": benchmark_case.get("required_evidence", []),
        "forbidden_or_contradictory_evidence": benchmark_case.get(
            "forbidden_or_contradictory_evidence", []
        ),
        "document_scope": benchmark_case.get("document_scope"),
        "reasoning_notes_for_reviewers": benchmark_case.get("reasoning_notes_for_reviewers"),
        "model_answer": result_case.get("answer"),
        "retrieved_evidence": clean_retrieved_evidence(result_case),
    }


def blank_label(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "substantive_correct": None,
        "evidence_sufficient": None,
        "evidence_traceable": None,
        "conflict_or_qualification_handling": None,
        "reviewer_notes": "",
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("evaluation/holdout_v4/holdout_v4_benchmark.jsonl"),
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("evaluation/results/holdout_v4_blind_once.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/holdout_v4/adjudication/generated"),
    )
    args = parser.parse_args()

    actual_hash = sha256_file(args.result)
    if actual_hash != OFFICIAL_RESULT_SHA256:
        raise SystemExit(
            "REFUSING TO GENERATE: official result byte hash mismatch\n"
            f"expected={OFFICIAL_RESULT_SHA256}\nactual={actual_hash}"
        )

    benchmark = load_jsonl(args.benchmark)
    with args.result.open("r", encoding="utf-8") as f:
        result_obj = json.load(f)
    result_records = find_case_records(result_obj)

    benchmark_by_id = {row["case_id"]: row for row in benchmark}
    result_by_id = {row["case_id"]: row for row in result_records}

    review_ids = [
        row["case_id"]
        for row in benchmark
        if row.get("category") in HUMAN_FAMILIES
    ]
    if len(review_ids) != EXPECTED_REVIEW_CASES:
        raise SystemExit(
            f"REFUSING TO GENERATE: expected {EXPECTED_REVIEW_CASES} adjudication cases, "
            f"found {len(review_ids)}"
        )

    missing = sorted(set(review_ids) - set(result_by_id))
    if missing:
        raise SystemExit(f"REFUSING TO GENERATE: result missing cases: {missing}")

    packet_rows = [make_packet_case(benchmark_by_id[cid], result_by_id[cid]) for cid in review_ids]

    # Deterministic but different order for the two independent reviewers.
    rows_a = packet_rows.copy()
    rows_b = packet_rows.copy()
    random.Random("holdout-v4-reviewer-a-v1").shuffle(rows_a)
    random.Random("holdout-v4-reviewer-b-v1").shuffle(rows_b)

    out = args.output_dir
    write_jsonl(out / "reviewer_a_packet.jsonl", rows_a)
    write_jsonl(out / "reviewer_b_packet.jsonl", rows_b)
    write_jsonl(out / "reviewer_a_labels.jsonl", [blank_label(r["case_id"]) for r in rows_a])
    write_jsonl(out / "reviewer_b_labels.jsonl", [blank_label(r["case_id"]) for r in rows_b])

    manifest = {
        "protocol": "holdout_v4_protocol_v1",
        "purpose": "blinded_human_answer_adjudication",
        "official_result_sha256": actual_hash,
        "review_case_count": len(review_ids),
        "reviewer_packets": ["reviewer_a_packet.jsonl", "reviewer_b_packet.jsonl"],
        "label_files": ["reviewer_a_labels.jsonl", "reviewer_b_labels.jsonl"],
        "prohibited_hints_removed": [
            "aggregate_scores",
            "case_pass_fail_labels",
            "supported_flag",
            "answer_type",
            "internal_confidence",
            "retrieval_scores",
            "retrieval_ranks",
            "latency",
            "category_performance",
        ],
    }
    manifest_path = out / "packet_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Verified official result sha256={actual_hash}")
    print(f"Generated {len(review_ids)} blinded cases for reviewer A and reviewer B")
    print(f"Output directory: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
