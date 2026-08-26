#!/usr/bin/env python3
"""Contamination / freeze-integrity guard for the holdout_v1 benchmark.

Fails if:
- any Stage 5 source document hash appears in the holdout corpus
- any Stage 5 case ID appears in the holdout
- any question is duplicated across Stage 5 and the holdout
- holdout files were modified after freeze without explicit version bump
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "evaluation" / "holdout_v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def run_guard(holdout_dir: Path, project_root: Path = ROOT) -> dict:
    issues: list[str] = []

    # --- freeze integrity -------------------------------------------------
    manifest = json.loads((holdout_dir / "holdout_manifest.json").read_text(encoding="utf-8"))
    benchmark_hash = sha256_bytes((holdout_dir / "holdout_benchmark.jsonl").read_bytes())
    sources_manifest_hash = sha256_bytes((holdout_dir / "sources_manifest.jsonl").read_bytes())
    if benchmark_hash != manifest.get("benchmark_sha256"):
        issues.append(
            "holdout_benchmark.jsonl modified after freeze "
            "(hash mismatch); bump benchmark_version and re-freeze explicitly"
        )
    if sources_manifest_hash != manifest.get("sources_manifest_sha256"):
        issues.append("sources_manifest.jsonl modified after freeze")

    # --- source document overlap -----------------------------------------
    stage5_sources_path = project_root / "evaluation" / "stage5_source_manifest.jsonl"
    stage5_hashes = set()
    if stage5_sources_path.exists():
        stage5_hashes = {entry["sha256"] for entry in load_jsonl(stage5_sources_path)}
    holdout_sources = load_jsonl(holdout_dir / "sources_manifest.jsonl")
    for entry in holdout_sources:
        source_path = project_root / entry["source_filename"]
        if not source_path.exists():
            issues.append(f"{entry['doc_id']}: source file missing")
            continue
        actual = sha256_file(source_path)
        if actual != entry["sha256"]:
            issues.append(f"{entry['doc_id']}: source file hash drift")
        if actual in stage5_hashes:
            issues.append(f"{entry['doc_id']}: hash identical to a Stage 5 document")

    # --- case IDs and questions ------------------------------------------
    holdout_cases = load_jsonl(holdout_dir / "holdout_benchmark.jsonl")
    stage5_cases_path = project_root / "evaluation" / "stage5_review_queue.jsonl"
    stage5_ids: set[str] = set()
    stage5_questions: set[str] = set()
    if stage5_cases_path.exists():
        stage5_cases = load_jsonl(stage5_cases_path)
        stage5_ids = {case["case_id"] for case in stage5_cases}
        stage5_questions = {case["question"].strip().casefold() for case in stage5_cases}

    seen_ids = set()
    for case in holdout_cases:
        case_id = case["case_id"]
        if case_id in seen_ids:
            issues.append(f"{case_id}: duplicate case ID inside holdout")
        seen_ids.add(case_id)
        if case_id in stage5_ids:
            issues.append(f"{case_id}: collides with a Stage 5 case ID")
        if case["question"].strip().casefold() in stage5_questions:
            issues.append(f"{case_id}: question duplicated from Stage 5")

    return {
        "guard": "holdout_contamination",
        "benchmark_version": manifest.get("benchmark_version"),
        "cases_checked": len(holdout_cases),
        "sources_checked": len(holdout_sources),
        "issues": issues,
        "pass": not issues,
    }


def main() -> int:
    report = run_guard(HOLDOUT, ROOT)
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
