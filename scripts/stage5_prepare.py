#!/usr/bin/env python3
"""Prepare and validate the independent Stage 5 corpus and benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"[a-z0-9]+")
STOP = {
    "the", "and", "for", "with", "that", "this", "from", "shall", "must",
    "are", "not", "can", "may", "will", "was", "were", "have", "has",
    "into", "only", "also", "when", "then", "than", "their", "which",
}


def norm(value: str) -> str:
    return " ".join(TOKEN.findall(value.lower()))


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def validate(root: Path) -> dict:
    manifest = load_jsonl(root / "evaluation" / "stage5_source_manifest.jsonl")
    ids = [item.get("doc_id") for item in manifest]
    urls = [item.get("canonical_source_url") for item in manifest]
    hashes = [item.get("sha256") for item in manifest]
    issues: list[str] = []
    for item in manifest:
        required = (
            "source_organization", "title", "canonical_source_url",
            "acquisition_date", "license_type", "redistribution_status",
            "domain", "sha256", "independence_declaration",
        )
        for field in required:
            if not item.get(field):
                issues.append(f"{item.get('doc_id')}: missing {field}")
        if item.get("synthetically_generated") is not False:
            issues.append(f"{item.get('doc_id')}: synthetic flag is not false")
        if item.get("used_in_development") is not False:
            issues.append(f"{item.get('doc_id')}: development-use flag is not false")
        path = root / "evaluation" / "stage5_documents" / f"rfc{int(item['revision_version'].split()[-1])}.txt"
        if not path.exists():
            issues.append(f"{item.get('doc_id')}: document file missing")
        else:
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != item.get("sha256"):
                issues.append(f"{item.get('doc_id')}: SHA-256 mismatch")
            if path.stat().st_size != item.get("content_length_bytes"):
                issues.append(f"{item.get('doc_id')}: content length mismatch")
    duplicate_ids = len(ids) - len(set(ids))
    duplicate_urls = len(urls) - len(set(urls))
    duplicate_hashes = len(hashes) - len(set(hashes))
    return {
        "manifest_documents": len(manifest),
        "domains": sorted({item.get("domain") for item in manifest}),
        "duplicate_doc_ids": duplicate_ids,
        "duplicate_urls": duplicate_urls,
        "duplicate_hashes": duplicate_hashes,
        "issues": issues,
        "pass": not issues and not any((duplicate_ids, duplicate_urls, duplicate_hashes)),
    }


def build_benchmark(root: Path, count: int = 300) -> int:
    manifest = load_jsonl(root / "evaluation" / "stage5_source_manifest.jsonl")
    cases: list[dict] = []
    seen_questions: set[str] = set()
    for item in manifest:
        number = int(item["revision_version"].split()[-1])
        path = root / "evaluation" / "stage5_documents" / f"rfc{number}.txt"
        text = path.read_text(encoding="utf-8-sig")
        for match in re.finditer(r"(?s)(?<!\S)(?!RFC\b|Table of Contents|References\b|Copyright\b).{90,420}?(?=\n\s*\n|\Z)", text):
            quote = " ".join(match.group(0).split())
            words = [w for w in TOKEN.findall(quote.lower()) if w not in STOP and len(w) > 3]
            if len(words) < 4:
                continue
            topic = " ".join(words[:8])
            question = f"What requirement or behavior does RFC {number} specify concerning {topic}?"
            if norm(question) in seen_questions:
                continue
            seen_questions.add(norm(question))
            case_no = len(cases) + 1
            cases.append({
                "case_id": f"s5_case_{case_no:03d}",
                "question": question,
                "expected_answer": quote,
                "acceptable_answers": [quote],
                "evidence_document_ids": [item["doc_id"]],
                "evidence_spans": [{
                    "doc_id": item["doc_id"],
                    "span_start": match.start(),
                    "span_end": match.end(),
                    "quoted_text": quote,
                }],
                "category": "supported",
                "difficulty": "medium",
                "support_type": "single_document",
                "reviewer_status": "unreviewed",
                "review_origin": "automatically_generated",
                "reviewer_id": None,
                "reviewer_notes": "",
                "disagreement_status": "none",
                "confidence": None,
            })
            if len(cases) >= count * 7 // 10:
                break
        if len(cases) >= count * 7 // 10:
            break
    supported = len(cases)
    for i in range(count - supported):
        case_no = supported + i + 1
        cases.append({
            "case_id": f"s5_case_{case_no:03d}",
            "question": f"Which RFC defines the fictional control token stage5-unsupported-{case_no}?",
            "expected_answer": None,
            "acceptable_answers": [],
            "evidence_document_ids": [],
            "evidence_spans": [],
            "category": "unsupported",
            "difficulty": "hard",
            "support_type": "single_document",
            "reviewer_status": "unreviewed",
            "review_origin": "automatically_generated",
            "reviewer_id": None,
            "reviewer_notes": "",
            "disagreement_status": "none",
            "confidence": None,
        })
    output = root / "evaluation" / "stage5_review_queue.jsonl"
    output.write_text("\n".join(json.dumps(case, sort_keys=True) for case in cases) + "\n", encoding="utf-8")
    return len(cases)


def benchmark_integrity(root: Path) -> dict:
    cases = load_jsonl(root / "evaluation" / "stage5_review_queue.jsonl")
    manifest = {item["doc_id"]: item for item in load_jsonl(root / "evaluation" / "stage5_source_manifest.jsonl")}
    prior_questions = []
    for path in (root / "evaluation").glob("*.jsonl"):
        if path.name not in {"stage5_review_queue.jsonl", "stage5_source_manifest.jsonl"}:
            prior_questions.extend(load_jsonl(path))
    questions = [norm(item.get("question", "")) for item in cases]
    duplicate_pairs = sum(1 for i, q in enumerate(questions) for other in questions[i + 1:] if q == other)
    overlap = sum(q in {norm(item.get("question", "")) for item in prior_questions} for q in questions)
    issues = []
    for case in cases:
        for doc_id in case.get("evidence_document_ids", []):
            if doc_id not in manifest:
                issues.append(f"{case['case_id']}: unknown evidence document {doc_id}")
    return {
        "cases": len(cases),
        "supported": sum(item.get("category") == "supported" for item in cases),
        "unsupported": sum(item.get("category") == "unsupported" for item in cases),
        "duplicate_question_pairs": duplicate_pairs,
        "prior_benchmark_overlap": overlap,
        "unreviewed": sum(item.get("reviewer_status") == "unreviewed" for item in cases),
        "automatically_generated": sum(item.get("review_origin") == "automatically_generated" for item in cases),
        "issues": issues,
        "pass": not issues and duplicate_pairs == 0 and overlap == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        print(json.dumps({"built_cases": build_benchmark(args.root)}, indent=2))
    report = {"manifest": validate(args.root), "benchmark": benchmark_integrity(args.root)}
    report["pass"] = report["manifest"]["pass"] and report["benchmark"]["pass"]
    output = args.root / "evaluation" / "results" / "stage5_integrity_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
