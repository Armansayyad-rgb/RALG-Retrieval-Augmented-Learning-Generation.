from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "holdout_v4_authoring_template.jsonl"
REVIEW = ROOT / "pre_run_review_template.jsonl"

DISTRIBUTION = [
    ("supported_factual", 20),
    ("paraphrased_supported", 20),
    ("procedural", 20),
    ("causal", 15),
    ("cross_document", 15),
    ("document_scoped", 10),
    ("conflicting_evidence", 10),
    ("conditional_or_qualified", 5),
    ("unsupported", 20),
    ("false_premise", 15),
    ("misleading_overlap", 10),
]


def main() -> None:
    rows = []
    reviews = []
    number = 1
    for category, count in DISTRIBUTION:
        for _ in range(count):
            case_id = f"holdout_v4_{number:03d}"
            answerable = category not in {"unsupported", "false_premise", "misleading_overlap"}
            rows.append({
                "case_id": case_id,
                "category": category,
                "question": "",
                "expected_behavior": "answer_with_grounded_evidence" if answerable else "reject_or_state_insufficient_evidence",
                "relevant_document_ids": [],
                "answerable": answerable,
                "ground_truth_answer": "" if answerable else None,
                "required_evidence": [],
                "forbidden_or_contradictory_evidence": [],
                "document_scope": [] if category == "document_scoped" else None,
                "reasoning_notes_for_reviewers": "",
                "pre_run_review_status": "PENDING",
            })
            reviews.append({
                "case_id": case_id,
                "status": "PENDING",
                "reviewer": "",
                "question_clear": None,
                "category_correct": None,
                "ground_truth_supported": None,
                "evidence_verified": None,
                "contamination_checked": None,
                "notes": "",
            })
            number += 1

    OUT.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    REVIEW.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in reviews), encoding="utf-8")
    print(f"wrote {len(rows)} exact-distribution authoring slots to {OUT}")
    print(f"wrote {len(reviews)} review slots to {REVIEW}")


if __name__ == "__main__":
    main()
