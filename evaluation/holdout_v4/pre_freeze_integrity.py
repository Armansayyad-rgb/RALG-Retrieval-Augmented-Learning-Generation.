from __future__ import annotations

import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
BENCH = ROOT / "holdout_v4_benchmark.jsonl"
SOURCES = ROOT / "sources_manifest.jsonl"
REVIEW = ROOT / "pre_run_review.jsonl"
CONTAM = ROOT / "contamination_report.json"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
ANSWERABLE = {
    "supported_factual", "paraphrased_supported", "procedural", "causal",
    "cross_document", "document_scoped", "conflicting_evidence",
    "conditional_or_qualified",
}


def read_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    for path in (BENCH, SOURCES, REVIEW, CONTAM):
        if not path.is_file():
            fail(f"missing {path.name}")

    cases = read_jsonl(BENCH)
    if len(cases) != 160:
        fail(f"expected 160 cases, found {len(cases)}")
    expected_ids = [f"holdout_v4_{i:03d}" for i in range(1, 161)]
    if [c.get("case_id") for c in cases] != expected_ids:
        fail("case IDs/order are not exactly holdout_v4_001..holdout_v4_160")

    sources = read_jsonl(SOURCES)
    if len(sources) != 12:
        fail(f"expected exactly 12 sources, found {len(sources)}")
    source_ids = {s.get("document_id") for s in sources}
    if None in source_ids or len(source_ids) != 12:
        fail("source IDs must be unique and non-null")
    if len({s.get("domain") for s in sources}) < 10:
        fail("fewer than 10 source domains")

    source_text: dict[str, str] = {}
    for source in sources:
        doc_id = source["document_id"]
        if source.get("license_review_status") != "APPROVED":
            fail(f"{doc_id}: license review is not APPROVED")
        if not SHA40.fullmatch(str(source.get("resolved_commit_sha", ""))):
            fail(f"{doc_id}: source ref is not pinned to an immutable commit")
        if not SHA64.fullmatch(str(source.get("raw_sha256", ""))) or not SHA64.fullmatch(str(source.get("normalized_sha256", ""))):
            fail(f"{doc_id}: missing SHA-256 hashes")
        raw = ROOT / str(source.get("raw_path", ""))
        normalized = ROOT / str(source.get("normalized_path", ""))
        if not raw.is_file() or not normalized.is_file():
            fail(f"{doc_id}: acquired source file missing")
        if sha256(raw) != source["raw_sha256"] or sha256(normalized) != source["normalized_sha256"]:
            fail(f"{doc_id}: source hash mismatch")
        source_text[doc_id] = normalized.read_text(encoding="utf-8")

    for case in cases:
        cid = case["case_id"]
        category = case.get("category")
        should_answer = category in ANSWERABLE
        if bool(case.get("answerable")) != should_answer:
            fail(f"{cid}: answerable flag inconsistent with category")
        if case.get("pre_run_review_status") != "APPROVED":
            fail(f"{cid}: benchmark review status is not APPROVED")
        relevant = case.get("relevant_document_ids") or []
        if set(relevant) - source_ids:
            fail(f"{cid}: references unknown source IDs")
        if should_answer:
            if not relevant or not str(case.get("ground_truth_answer", "")).strip():
                fail(f"{cid}: answerable case lacks sources or ground truth")
            evidence = case.get("required_evidence") or []
            if not evidence:
                fail(f"{cid}: answerable case has no required evidence")
            for item in evidence:
                doc = item.get("document_id")
                anchor = str(item.get("anchor", ""))
                if doc not in source_text or not anchor or anchor not in source_text[doc]:
                    fail(f"{cid}: evidence anchor is not verbatim in frozen source {doc}")
        if category == "cross_document" and len(set(relevant)) < 2:
            fail(f"{cid}: cross_document needs >=2 required documents")
        if category == "document_scoped" and not case.get("document_scope"):
            fail(f"{cid}: document_scoped case lacks scope")
        if category == "conflicting_evidence" and not case.get("forbidden_or_contradictory_evidence"):
            fail(f"{cid}: conflicting_evidence case lacks contradiction annotation")

    review = read_jsonl(REVIEW)
    if len(review) != 160:
        fail(f"expected 160 review records, found {len(review)}")
    approved = [r.get("case_id") for r in review if r.get("status") == "APPROVED"]
    if approved != expected_ids:
        fail("review file does not approve exactly all 160 cases in order")

    contamination = json.loads(CONTAM.read_text(encoding="utf-8"))
    if contamination.get("status") != "PASS":
        fail("contamination report is not PASS")
    if contamination.get("benchmark_sha256") != sha256(BENCH):
        fail("contamination report was generated from a different benchmark")

    print("PASS: strict Holdout V4 pre-freeze integrity")


if __name__ == "__main__":
    main()
