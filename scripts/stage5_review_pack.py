#!/usr/bin/env python3
"""Audit and build blind Stage 5 review materials."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_FIELDS = [
    "case_id", "answerable_yes_no", "expected_support_correct",
    "reference_answer_correct", "evidence_supports_answer",
    "source_attribution_correct", "question_clear", "difficulty",
    "accept_reject", "corrected_answer", "corrected_evidence",
    "reviewer_notes", "reviewer_id",
]
PROHIBITED = (
    "ralg", "lexical", "bm25", "retrieval_score", "ranking", "latency",
    "false_support", "mrr", "recall_at", "model_won", "system_a", "system_b",
)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def source_texts(root: Path, manifest: list[dict]) -> dict[str, tuple[dict, str]]:
    output = {}
    for item in manifest:
        number = item["revision_version"].split()[-1]
        path = root / "evaluation" / "stage5_documents" / f"rfc{number}.txt"
        output[item["doc_id"]] = (item, path.read_text(encoding="utf-8-sig"))
    return output


def audit(root: Path) -> dict:
    cases = load_jsonl(root / "evaluation" / "stage5_review_queue.jsonl")
    sources = source_texts(root, load_jsonl(root / "evaluation" / "stage5_source_manifest.jsonl"))
    ids = [case.get("case_id") for case in cases]
    duplicates = len(ids) - len(set(ids))
    suspicious = []
    issues = []
    for case in cases:
        case_id = case.get("case_id")
        if not case.get("question", "").strip():
            issues.append(f"{case_id}: empty question")
        evidence_ids = case.get("evidence_document_ids", [])
        supported = case.get("category") == "supported"
        if supported != bool(evidence_ids):
            issues.append(f"{case_id}: support/category mismatch")
        if supported and not case.get("expected_answer"):
            issues.append(f"{case_id}: missing expected answer")
        if len(evidence_ids) != len(case.get("evidence_spans", [])):
            issues.append(f"{case_id}: evidence linkage length mismatch")
        for span in case.get("evidence_spans", []):
            doc_id = span.get("doc_id")
            if doc_id not in sources:
                issues.append(f"{case_id}: unknown source {doc_id}")
                continue
            text = sources[doc_id][1]
            start, end = span.get("span_start"), span.get("span_end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start or end > len(text):
                issues.append(f"{case_id}: invalid evidence offsets")
                continue
            raw = text[start:end]
            if span.get("quoted_text") not in raw:
                suspicious.append({"case_id": case_id, "reason": "quoted_text_not_verbatim_in_span"})
            if span.get("quoted_text") and span.get("quoted_text") not in text:
                suspicious.append({"case_id": case_id, "reason": "quoted_text_not_verbatim_in_source"})
            if doc_id not in evidence_ids:
                issues.append(f"{case_id}: span source not listed")
        if case.get("reviewer_status") != "unreviewed":
            suspicious.append({"case_id": case_id, "reason": "unexpected_review_status"})
    questions = [case.get("question", "") for case in cases]
    exact_duplicates = len(questions) - len(set(questions))
    return {
        "cases_audited": len(cases),
        "structurally_valid": len(cases) - len(set(issue.split(":", 1)[0] for issue in issues)),
        "suspicious_cases": len({item["case_id"] for item in suspicious}),
        "suspicious_reasons": sorted({item["reason"] for item in suspicious}),
        "duplicate_case_ids": duplicates,
        "duplicate_exact_questions": exact_duplicates,
        "issues": issues,
        "pass": not duplicates and not exact_duplicates and not issues,
    }


def blind_case(case: dict, source_map: dict[str, tuple[dict, str]]) -> dict:
    evidence_ids = case.get("evidence_document_ids") or [None]
    doc_id = evidence_ids[0]
    item, text = source_map[doc_id] if doc_id else ({}, "")
    span = case.get("evidence_spans", [{}])[0] if doc_id else {}
    excerpt = text[span.get("span_start", 0):span.get("span_end", 0)] if doc_id else ""
    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "claimed_supported": case["category"] == "supported",
        "proposed_reference_answer": case.get("expected_answer"),
        "evidence_excerpt": excerpt,
        "document_title": item.get("title"),
        "rfc_number": item.get("revision_version"),
        "canonical_source_url": item.get("canonical_source_url"),
        "source_section_indicator": "Reviewer should consult the original RFC as needed.",
        "difficulty": case.get("difficulty"),
        "review": {field: "" for field in REVIEW_FIELDS if field not in {"case_id", "difficulty"}},
    }


def pilot_sample(cases: list[dict], size: int = 75, seed: int = 5_202_025) -> list[dict]:
    groups = defaultdict(list)
    for case in cases:
        source = (case.get("evidence_document_ids") or ["unsupported"])[0]
        key = (case.get("category"), source, case.get("difficulty"))
        groups[key].append(case)
    rng = random.Random(seed)
    for values in groups.values():
        rng.shuffle(values)
    selected = []
    keys = sorted(groups)
    while len(selected) < min(size, len(cases)) and keys:
        progressed = False
        for key in keys:
            if groups[key] and len(selected) < size:
                selected.append(groups[key].pop())
                progressed = True
        if not progressed:
            break
    return selected


def write_csv_template(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()


def blinding_check(pack_dir: Path) -> dict:
    findings = []
    for path in pack_dir.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace").casefold()
        for term in PROHIBITED:
            if term in content:
                findings.append({"file": str(path.relative_to(pack_dir)), "term": term})
    return {"files_checked": len(list(pack_dir.rglob("*"))), "prohibited_fields": findings, "pass": not findings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--sample-size", type=int, default=75)
    args = parser.parse_args()
    root = args.root
    cases = load_jsonl(root / "evaluation" / "stage5_review_queue.jsonl")
    manifest = load_jsonl(root / "evaluation" / "stage5_source_manifest.jsonl")
    source_map = source_texts(root, manifest)
    pack = root / "evaluation" / "stage5_review_pack"
    pack.mkdir(parents=True, exist_ok=True)
    full = [blind_case(case, source_map) for case in cases]
    pilot = [blind_case(case, source_map) for case in pilot_sample(cases, args.sample_size)]
    for name, rows in (("full_review.jsonl", full), ("pilot_review.jsonl", pilot)):
        (pack / name).write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    write_csv_template(root / "evaluation" / "stage5_review_template.csv")
    report = {
        "audit": audit(root),
        "full_review_cases": len(full),
        "pilot_review_cases": len(pilot),
        "pilot_seed": 5_202_025,
        "pilot_supported": sum(row["claimed_supported"] for row in pilot),
        "pilot_unsupported": sum(not row["claimed_supported"] for row in pilot),
    }
    report["blinding"] = blinding_check(pack)
    report["pass"] = report["audit"]["pass"] and report["blinding"]["pass"]
    (pack / "review_pack_manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
