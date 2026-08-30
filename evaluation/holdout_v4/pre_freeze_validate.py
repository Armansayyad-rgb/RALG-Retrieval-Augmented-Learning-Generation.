from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
BENCH = ROOT / "holdout_v4_benchmark.jsonl"
SOURCES = ROOT / "sources_manifest.jsonl"
REVIEW = ROOT / "pre_run_review.jsonl"
CONTAM = ROOT / "contamination_report.json"

EXPECTED = {
    "supported_factual": 20,
    "paraphrased_supported": 20,
    "procedural": 20,
    "causal": 15,
    "cross_document": 15,
    "document_scoped": 10,
    "conflicting_evidence": 10,
    "conditional_or_qualified": 5,
    "unsupported": 20,
    "false_premise": 15,
    "misleading_overlap": 10,
}
REQUIRED_FIELDS = {
    "case_id", "category", "question", "expected_behavior", "relevant_document_ids",
    "answerable", "required_evidence", "reasoning_notes_for_reviewers", "pre_run_review_status"
}


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(msg):
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def main():
    for p in (BENCH, SOURCES, REVIEW, CONTAM):
        if not p.exists(): fail(f"missing {p.name}")
    rows = read_jsonl(BENCH)
    if len(rows) != 160: fail(f"benchmark has {len(rows)} cases, expected 160")
    ids = [r.get("case_id") for r in rows]
    if len(set(ids)) != 160 or None in ids: fail("case IDs must be unique and non-null")
    counts = collections.Counter(r.get("category") for r in rows)
    if dict(counts) != EXPECTED: fail(f"category counts mismatch: {dict(counts)}")
    for r in rows:
        missing = REQUIRED_FIELDS - set(r)
        if missing: fail(f"{r.get('case_id')}: missing {sorted(missing)}")
        if r["category"] in {"supported_factual","paraphrased_supported","procedural","causal","cross_document","document_scoped","conflicting_evidence","conditional_or_qualified"}:
            if not r["relevant_document_ids"]: fail(f"{r['case_id']}: missing relevant documents")
        if r["category"] in {"supported_factual","paraphrased_supported","procedural","causal","cross_document","document_scoped","conflicting_evidence","conditional_or_qualified"} and not r.get("ground_truth_answer"):
            fail(f"{r['case_id']}: missing ground truth answer")
        if r.get("pre_run_review_status") != "APPROVED": fail(f"{r['case_id']}: review not approved")
    sources = read_jsonl(SOURCES)
    if len(sources) < 12: fail("fewer than 12 source documents")
    if len({s.get('domain') for s in sources}) < 10: fail("fewer than 10 source domains")
    if any(s.get("license_review_status") != "APPROVED" for s in sources): fail("source license review incomplete")
    source_ids = {s.get("document_id") for s in sources}
    for r in rows:
        unknown = set(r["relevant_document_ids"]) - source_ids
        if unknown: fail(f"{r['case_id']}: unknown source IDs {sorted(unknown)}")
    review = read_jsonl(REVIEW)
    reviewed = {r.get("case_id") for r in review if r.get("status") == "APPROVED"}
    if reviewed != set(ids): fail("pre-run review record does not approve exactly all 160 cases")
    contamination = json.loads(CONTAM.read_text(encoding="utf-8"))
    if contamination.get("status") != "PASS": fail("contamination report is not PASS")
    print("PASS: Holdout V4 pre-freeze validation")
    print(json.dumps({"benchmark_sha256": sha(BENCH), "sources_manifest_sha256": sha(SOURCES), "pre_run_review_sha256": sha(REVIEW), "contamination_report_sha256": sha(CONTAM)}, indent=2))


if __name__ == "__main__":
    main()
