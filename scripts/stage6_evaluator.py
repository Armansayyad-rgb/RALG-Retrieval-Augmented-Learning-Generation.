#!/usr/bin/env python3
"""Stage 6 evaluator: retrieval metrics on HUMAN-APPROVED cases only.

Reads reviewed benchmark artifact(s) produced by ``stage5_ingest_reviews.py
ingest`` (or the merged two-reviewer artifact), keeps only cases approved by
every supplied reviewer, and evaluates the lexical baseline and RALG hybrid
on that subset using exactly the same scoring method as
``stage5_preliminary_evaluation.py``.

Guarantees:
- Never writes to ``evaluation/results/stage5_preliminary_results.json``.
- Never modifies Stage 5 fixtures, labels, or documents.
- Refuses to emit metrics when no human-reviewed artifacts exist or no case
  is approved; absence of review is reported explicitly, never papered over.

Output namespace: evaluation/results/stage6_human_review_results.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from retriever_v2 import build_index  # noqa: E402
from retriever_hybrid import retrieve  # noqa: E402
from stage5_preliminary_evaluation import words, rank_for  # noqa: E402

DEFAULT_OUTPUT = ROOT / "evaluation" / "results" / "stage6_human_review_results.json"
BASELINE_REFERENCE = (
    "evaluation/results/stage5_preliminary_results.json "
    "(authoritative frozen Stage 5 baseline artifact; never mutated by this tool)"
)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def outcome(case: dict) -> str | None:
    label = case.get("review_outcome")
    if label:
        return label
    return {"accepted": "accept", "rejected": "reject"}.get(case.get("reviewer_status"))


def approval_map(paths: list[Path]) -> tuple[dict[str, bool], dict]:
    """Return {case_id: approved} for cases covered by every reviewer artifact."""
    per_reviewer: list[dict[str, str]] = []
    for path in paths:
        cases = load_jsonl(path)
        per_reviewer.append({
            case["case_id"]: outcome(case)
            for case in cases if outcome(case)
        })
    common: set[str] | None = None
    for outcomes in per_reviewer:
        ids = set(outcomes)
        common = ids if common is None else (common & ids)
    approved: dict[str, bool] = {}
    ambiguous = invalid_case = rejected = 0
    for case_id in sorted(common or set()):
        labels = [outcomes[case_id] for outcomes in per_reviewer]
        if all(label == "accept" for label in labels):
            approved[case_id] = True
        else:
            approved[case_id] = False
            if any(label == "ambiguous" for label in labels):
                ambiguous += 1
            elif any(label == "invalid_case" for label in labels):
                invalid_case += 1
            else:
                rejected += 1
    summary = {
        "reviewer_files": [str(path) for path in paths],
        "cases_covered_by_all_reviewers": len(approved),
        "approved": sum(1 for value in approved.values() if value),
        "rejected": rejected,
        "ambiguous": ambiguous,
        "invalid_case": invalid_case,
    }
    return approved, summary


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    """Wilson score interval for a binomial proportion; None when undefined."""
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def evaluate_subset(case_ids: set[str], documents: list[str], doc_ids: list[str],
                    index, df) -> dict:
    queue_path = ROOT / "evaluation" / "stage5_review_queue.jsonl"
    all_cases = load_jsonl(queue_path)
    cases = [case for case in all_cases if case["case_id"] in case_ids]
    systems: dict[str, dict] = {}
    for system in ("lexical", "ralg"):
        supported_ranks: list[int | None] = []
        unsupported_hits = []
        for case in cases:
            expected_id = case["evidence_document_ids"][0] if case["evidence_document_ids"] else None
            expected_text = documents[doc_ids.index(expected_id)] if expected_id else ""
            if system == "lexical":
                query_terms = words(case["question"])
                ranked = sorted(
                    range(len(documents)),
                    key=lambda i: len(query_terms & words(documents[i])),
                    reverse=True,
                )[:5]
                results = [{"chunk": documents[i]} for i in ranked]
            else:
                results = retrieve(case["question"], documents, index, df)
            rank = rank_for(results, expected_text[:120]) if expected_id else None
            if case["category"] == "supported":
                supported_ranks.append(rank)
            else:
                unsupported_hits.append(rank is not None)
        n_supported = len(supported_ranks)
        n_unsupported = len(unsupported_hits)
        mrr_values = [1 / rank if rank else 0 for rank in supported_ranks]
        recall_1 = sum(rank == 1 for rank in supported_ranks)
        recall_5 = sum(rank is not None and rank <= 5 for rank in supported_ranks)
        rejections = sum(not hit for hit in unsupported_hits)
        false_supports = sum(unsupported_hits)
        systems[system] = {
            "recall_at_1": recall_1 / n_supported if n_supported else None,
            "recall_at_3": (sum(rank is not None and rank <= 3 for rank in supported_ranks) / n_supported) if n_supported else None,
            "recall_at_5": recall_5 / n_supported if n_supported else None,
            "mrr": statistics.fmean(mrr_values) if mrr_values else None,
            "unsupported_rejection": rejections / n_unsupported if n_unsupported else None,
            "false_support_rate": false_supports / n_unsupported if n_unsupported else None,
            "confidence_intervals_95": {
                "recall_at_1_wilson": wilson_interval(recall_1, n_supported),
                "recall_at_5_wilson": wilson_interval(recall_5, n_supported),
                "unsupported_rejection_wilson": wilson_interval(rejections, n_unsupported),
                "false_support_rate_wilson": wilson_interval(false_supports, n_unsupported),
            },
            "supported_cases_scored": n_supported,
            "unsupported_cases_scored": n_unsupported,
        }
    return systems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed", type=Path, action="append", required=True,
                        help="reviewed artifact JSONL (repeat for multiple reviewers)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    for path in args.reviewed:
        if not path.exists():
            print(json.dumps({"pass": False, "error": f"missing reviewed artifact: {path}"}, indent=2))
            return 1

    manifest = load_jsonl(ROOT / "evaluation" / "stage5_source_manifest.jsonl")
    documents = []
    doc_ids = []
    for item in manifest:
        number = item["revision_version"].split()[-1]
        path = ROOT / "evaluation" / "stage5_documents" / f"rfc{number}.txt"
        documents.append(path.read_text(encoding="utf-8-sig"))
        doc_ids.append(item["doc_id"])
    index, df = build_index(documents)

    approved, review_summary = approval_map(args.reviewed)
    report: dict = {
        "status": "human_approved_subset_evaluated",
        "warning": (
            "Metrics describe ONLY the human-approved subset of Stage 5 cases "
            "under the stated review round. They are not independent validation "
            "unless the underlying human review files were produced by qualified "
            "independent reviewers."
        ),
        "baseline_reference": BASELINE_REFERENCE,
        "review_summary": review_summary,
        "counts": {
            "reviewed": review_summary["cases_covered_by_all_reviewers"],
            "valid": review_summary["approved"],
            "invalid_or_ambiguous": (
                review_summary["rejected"] + review_summary["ambiguous"]
                + review_summary["invalid_case"]
            ),
            "supported": 0,
            "unsupported": 0,
        },
    }

    approved_ids = {case_id for case_id, ok in approved.items() if ok}
    if not approved_ids:
        report["status"] = "no_human_approved_cases"
        report["warning"] = (
            "No human-approved cases available; no Stage 6 metrics computed. "
            "Human review must be completed and ingested before evaluation."
        )
        report["systems"] = {}
    else:
        queue = load_jsonl(ROOT / "evaluation" / "stage5_review_queue.jsonl")
        approved_cases = [case for case in queue if case["case_id"] in approved_ids]
        report["counts"]["supported"] = sum(case["category"] == "supported" for case in approved_cases)
        report["counts"]["unsupported"] = sum(case["category"] != "supported" for case in approved_cases)
        report["systems"] = evaluate_subset(
            approved_ids, documents, doc_ids, index, df,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
