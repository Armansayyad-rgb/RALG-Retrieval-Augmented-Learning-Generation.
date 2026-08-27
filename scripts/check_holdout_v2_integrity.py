#!/usr/bin/env python3
"""Integrity and contamination guard for Independent Holdout V2."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "evaluation" / "holdout_v2"
EXPECTED_CATEGORIES = {
    "supported",
    "unsupported",
    "paraphrased",
    "false_premise",
    "misleading_overlap",
    "procedural",
    "cross_document",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def normalize_question(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def case_question_sets(project_root: Path) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    questions: set[str] = set()
    paths = [
        project_root / "evaluation" / "stage5_review_queue.jsonl",
        project_root / "evaluation" / "holdout_v1" / "holdout_benchmark.jsonl",
        project_root / "evaluation" / "dev_support_gate_v1.jsonl",
        project_root / "evaluation" / "heldout_pilot_v1.jsonl",
        project_root / "evaluation" / "heldout_stage3_customer_v1.jsonl",
        project_root / "evaluation" / "heldout_stage4_customer_v1.jsonl",
        project_root / "data" / "technical_doc_benchmark_v1.jsonl",
        project_root / "data" / "technical_doc_benchmark_hard_v1.jsonl",
    ]
    for path in paths:
        if not path.exists():
            continue
        for row in load_jsonl(path):
            if isinstance(row, dict):
                if row.get("case_id"):
                    ids.add(str(row["case_id"]))
                if row.get("question"):
                    questions.add(normalize_question(str(row["question"])))
    return ids, questions


def run_guard(holdout_dir: Path = HOLDOUT, project_root: Path = ROOT) -> dict:
    issues: list[str] = []
    manifest_path = holdout_dir / "holdout_manifest.json"
    benchmark_path = holdout_dir / "holdout_benchmark.jsonl"
    sources_manifest_path = holdout_dir / "sources_manifest.jsonl"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for path in [manifest_path, benchmark_path, sources_manifest_path]:
        if b"\r\n" in path.read_bytes():
            issues.append(f"{path.name}: non-canonical CRLF line endings")
    actual_benchmark_hash = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
    actual_sources_manifest_hash = hashlib.sha256(
        sources_manifest_path.read_bytes()).hexdigest()
    if actual_benchmark_hash != manifest.get("benchmark_sha256"):
        issues.append("holdout_benchmark.jsonl hash mismatch after freeze")
    if actual_sources_manifest_hash != manifest.get("sources_manifest_sha256"):
        issues.append("sources_manifest.jsonl hash mismatch after freeze")

    source_rows = load_jsonl(sources_manifest_path)
    source_hashes: set[str] = set()
    source_texts: dict[str, str] = {}
    for row in source_rows:
        source_path = project_root / row["source_filename"]
        if not source_path.exists():
            issues.append(f"{row['doc_id']}: source file missing")
            continue
        if b"\r\n" in source_path.read_bytes():
            issues.append(f"{row['doc_id']}: non-canonical CRLF line endings")
        actual = sha256_file(source_path)
        if actual != row.get("sha256"):
            issues.append(f"{row['doc_id']}: source file hash drift")
        source_hashes.add(actual)
        source_texts[row["doc_id"]] = source_path.read_text(encoding="utf-8-sig")

    for manifest_file in (
        project_root / "evaluation" / "stage5_source_manifest.jsonl",
        project_root / "evaluation" / "holdout_v1" / "sources_manifest.jsonl",
    ):
        if manifest_file.exists():
            for row in load_jsonl(manifest_file):
                if row.get("sha256") in source_hashes:
                    issues.append(f"{row.get('doc_id')}: source hash overlaps prior holdout/dev corpus")

    cases = load_jsonl(benchmark_path)
    if len(cases) != manifest.get("case_count"):
        issues.append("case_count in manifest does not match benchmark rows")

    ids_seen: set[str] = set()
    questions_seen: set[str] = set()
    prior_ids, prior_questions = case_question_sets(project_root)
    category_counts: dict[str, int] = {}
    for case in cases:
        case_id = case.get("case_id")
        category = case.get("category")
        category_counts[category] = category_counts.get(category, 0) + 1
        if category not in EXPECTED_CATEGORIES:
            issues.append(f"{case_id}: unknown category {category!r}")
        if case_id in ids_seen:
            issues.append(f"{case_id}: duplicate case ID inside holdout_v2")
        ids_seen.add(case_id)
        if case_id in prior_ids:
            issues.append(f"{case_id}: case ID collides with existing evaluation material")
        normalized = normalize_question(case.get("question", ""))
        if normalized in questions_seen:
            issues.append(f"{case_id}: duplicate question inside holdout_v2")
        questions_seen.add(normalized)
        if normalized in prior_questions:
            issues.append(f"{case_id}: question duplicates existing evaluation material")
        for doc_id in case.get("evidence_document_ids", []):
            if doc_id not in source_texts:
                issues.append(f"{case_id}: unknown evidence document {doc_id}")
        for span in case.get("evidence_spans", []):
            text = source_texts.get(span.get("doc_id"), "")
            start = span.get("span_start")
            end = span.get("span_end")
            quoted = span.get("quoted_text")
            if not isinstance(start, int) or not isinstance(end, int) or start >= end:
                issues.append(f"{case_id}: invalid evidence span bounds")
                continue
            if text[start:end] != quoted:
                issues.append(f"{case_id}: evidence span text mismatch")
        if category in {"supported", "paraphrased", "procedural", "cross_document"}:
            if not case.get("expected_answer"):
                issues.append(f"{case_id}: supported-style case lacks expected_answer")
            if not case.get("evidence_spans"):
                issues.append(f"{case_id}: supported-style case lacks evidence spans")
        if category == "cross_document" and len(case.get("evidence_document_ids", [])) < 2:
            issues.append(f"{case_id}: cross_document case needs multiple evidence documents")
        if category in {"unsupported", "false_premise", "misleading_overlap"}:
            if case.get("expected_answer") is not None:
                issues.append(f"{case_id}: rejection case should not have expected_answer")
            if case.get("expected_behavior") != "reject_or_state_insufficient_evidence":
                issues.append(f"{case_id}: rejection case lacks expected_behavior")

    if set(category_counts) != EXPECTED_CATEGORIES:
        issues.append("category set is incomplete")
    if len(set(category_counts.values())) != 1:
        issues.append(f"category counts are not balanced: {category_counts}")
    if category_counts != manifest.get("category_counts"):
        issues.append("category_counts in manifest do not match benchmark")

    return {
        "guard": "holdout_v2_integrity",
        "benchmark_version": manifest.get("benchmark_version"),
        "cases_checked": len(cases),
        "sources_checked": len(source_rows),
        "category_counts": category_counts,
        "issues": issues,
        "pass": not issues,
    }


def main() -> int:
    report = run_guard()
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
