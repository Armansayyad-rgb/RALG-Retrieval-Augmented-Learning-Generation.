#!/usr/bin/env python3
"""Inter-reviewer agreement metrics for the Stage 6 human review round.

Consumes two reviewed benchmark artifacts produced by
``stage5_ingest_reviews.py ingest`` (one per reviewer) and reports raw
agreement and Cohen's kappa over the explicit reviewer outcome labels
(accept / reject / ambiguous / invalid_case). A disagreement queue is
written for adjudication.

This tool never fabricates reviewer data; it only summarizes artifacts that
already exist on disk. Cohen's kappa is reported as null (with a reason)
when it is mathematically undefined for the observed label distribution.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_cases(path: Path) -> dict[str, dict]:
    cases = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return {case["case_id"]: case for case in cases}


def outcome(case: dict) -> str | None:
    label = case.get("review_outcome")
    if label:
        return label
    status = case.get("reviewer_status")
    return {"accepted": "accept", "rejected": "reject"}.get(status)


def cohens_kappa(labels_a: list[str], labels_b: list[str]) -> tuple[float | None, str]:
    """Return (kappa, validity_reason). kappa is None when undefined."""
    n = len(labels_a)
    if n == 0:
        return None, "no commonly reviewed cases"
    categories = sorted(set(labels_a) | set(labels_b))
    po = sum(a == b for a, b in zip(labels_a, labels_b)) / n
    pe = 0.0
    for category in categories:
        pa = labels_a.count(category) / n
        pb = labels_b.count(category) / n
        pe += pa * pb
    if len(categories) < 2:
        return None, "only one outcome category observed; kappa undefined"
    if pe == 1.0:
        return None, "expected agreement is 1.0 (degenerate marginals); kappa undefined"
    if abs(1 - pe) < 1e-12:
        return None, "expected agreement equals observed agreement; kappa undefined"
    return (po - pe) / (1 - pe), "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer-a", type=Path, required=True,
                        help="reviewed artifact JSONL from reviewer A")
    parser.add_argument("--reviewer-b", type=Path, required=True,
                        help="reviewed artifact JSONL from reviewer B")
    parser.add_argument("--disagreements", type=Path,
                        default=ROOT / "evaluation" / "results" / "stage6_disagreement_queue.jsonl")
    args = parser.parse_args()

    try:
        first = load_cases(args.reviewer_a)
        second = load_cases(args.reviewer_b)
    except OSError as exc:
        print(json.dumps({"pass": False, "error": str(exc)}, indent=2))
        return 1
    common = sorted(set(first) & set(second))
    if not common:
        print(json.dumps({"pass": False, "error": "no commonly reviewed case IDs"}, indent=2))
        return 1

    labels_a, labels_b = [], []
    rows = []
    for case_id in common:
        left, right = outcome(first[case_id]), outcome(second[case_id])
        if left is None or right is None:
            continue
        labels_a.append(left)
        labels_b.append(right)
        if left != right:
            rows.append({
                "case_id": case_id,
                "reviewer_a": first[case_id].get("reviewer_id"),
                "reviewer_a_outcome": left,
                "reviewer_b": second[case_id].get("reviewer_id"),
                "reviewer_b_outcome": right,
                "notes_a": first[case_id].get("review", {}).get("reviewer_notes", ""),
                "notes_b": second[case_id].get("review", {}).get("reviewer_notes", ""),
            })

    n = len(labels_a)
    raw_agreement = sum(a == b for a, b in zip(labels_a, labels_b)) / n if n else None
    kappa, reason = cohens_kappa(labels_a, labels_b)

    args.disagreements.parent.mkdir(parents=True, exist_ok=True)
    args.disagreements.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    report = {
        "status": "two_reviewer_agreement",
        "cases_commonly_reviewed": n,
        "raw_agreement": raw_agreement,
        "cohens_kappa": kappa,
        "kappa_validity": reason,
        "disagreements": len(rows),
        "outcome_distribution_reviewer_a": {
            label: labels_a.count(label) for label in sorted(set(labels_a))
        },
        "outcome_distribution_reviewer_b": {
            label: labels_b.count(label) for label in sorted(set(labels_b))
        },
        "adjudication_required": bool(rows),
        "disagreement_queue": str(args.disagreements),
        "note": "Agreement statistics describe the review process only; they are not system performance.",
        "pass": True,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
