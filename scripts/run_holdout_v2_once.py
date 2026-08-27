#!/usr/bin/env python3
"""ONE-SHOT blind evaluation runner for Independent Holdout V2.

Do not run this during benchmark construction. It refuses to overwrite an
existing result and records the frozen benchmark hash in the output.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from check_holdout_v2_integrity import run_guard  # noqa: E402

RETRIEVAL_CATEGORIES = {"supported", "paraphrased", "procedural", "cross_document"}
REJECTION_CATEGORIES = {"unsupported", "false_premise", "misleading_overlap"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def rank_for(results: list, expected_text: str) -> int | None:
    for rank, result in enumerate(results, 1):
        if expected_text.casefold() in str(result.get("chunk", result)).casefold():
            return rank
    return None


def best_rank(results: list, case: dict) -> int | None:
    ranks = [rank_for(results, span["quoted_text"]) for span in case.get("evidence_spans", [])]
    ranks = [rank for rank in ranks if rank is not None]
    return min(ranks) if ranks else None


def wilson_interval(successes: int, n: int, z: float = 1.96) -> list[float | None]:
    if n == 0:
        return [None, None]
    phat = successes / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * ((phat * (1 - phat) + z * z / (4 * n)) / n) ** 0.5
    return [(centre - margin) / denom, (centre + margin) / denom]


def ranked_metrics(rows: list[dict]) -> dict:
    n = len(rows)
    r1 = sum(row.get("rank") == 1 for row in rows)
    r3 = sum(row.get("rank") is not None and row["rank"] <= 3 for row in rows)
    r5 = sum(row.get("rank") is not None and row["rank"] <= 5 for row in rows)
    return {
        "n": n,
        "recall_at_1": r1 / n if n else None,
        "recall_at_3": r3 / n if n else None,
        "recall_at_5": r5 / n if n else None,
        "mrr": statistics.fmean(1 / row["rank"] if row.get("rank") else 0
                                  for row in rows) if rows else None,
        "recall_at_1_ci95": wilson_interval(r1, n),
        "recall_at_5_ci95": wilson_interval(r5, n),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "evaluation" / "results" / "holdout_v2_blind_once.json")
    parser.add_argument("--skip-gate", action="store_true",
                        help="skip production support gate and run retrieval metrics only")
    args = parser.parse_args()

    if args.output.exists():
        print(json.dumps({"pass": False,
                          "error": f"{args.output} already exists; Holdout V2 is one-shot"}))
        return 1

    holdout_dir = ROOT / "evaluation" / "holdout_v2"
    guard_report = run_guard(holdout_dir, ROOT)
    if not guard_report["pass"]:
        print(json.dumps({"pass": False, "error": "integrity guard failed",
                          "issues": guard_report["issues"]}, indent=2))
        return 1

    manifest = json.loads((holdout_dir / "holdout_manifest.json").read_text(encoding="utf-8"))
    cases = load_jsonl(holdout_dir / "holdout_benchmark.jsonl")
    source_rows = load_jsonl(holdout_dir / "sources_manifest.jsonl")
    documents = [(ROOT / row["source_filename"]).read_text(encoding="utf-8-sig")
                 for row in source_rows]

    from retriever_hybrid import retrieve
    from retriever_v2 import build_index

    index, df = build_index(documents)

    gate_results: dict[str, bool] = {}
    gate_cases = [c for c in cases if c["category"] in REJECTION_CATEGORIES]
    if not args.skip_gate:
        from rag_chat_v2 import answer_question, initialize_pipeline
        from webui.chat_handler import build_answer_contract
        pipeline = initialize_pipeline(verbose=True)
        for case in gate_cases:
            result = answer_question(pipeline, case["question"], verbose=False)
            contract = build_answer_contract(pipeline, case["question"], result, top_k=5)
            gate_results[case["case_id"]] = bool(contract.supported)

    systems: dict[str, dict] = {}
    failures: list[dict] = []
    for system in ("lexical", "ralg"):
        ranked_rows = []
        for case in cases:
            if case["category"] in RETRIEVAL_CATEGORIES:
                if system == "lexical":
                    query_terms = words(case["question"])
                    ranked = sorted(range(len(documents)),
                                    key=lambda i: len(query_terms & words(documents[i])),
                                    reverse=True)[:5]
                    results = [{"chunk": documents[i]} for i in ranked]
                else:
                    results = retrieve(case["question"], documents, index, df)
                rank = best_rank(results, case)
                ranked_rows.append({"case_id": case["case_id"],
                                    "category": case["category"], "rank": rank})
                if rank is None or (case["category"] != "cross_document" and rank != 1):
                    failures.append({"system": system, "case_id": case["case_id"],
                                     "category": case["category"], "rank": rank})
            elif system == "ralg" and not args.skip_gate:
                supported = gate_results.get(case["case_id"])
                if supported:
                    failures.append({"system": system, "case_id": case["case_id"],
                                     "category": case["category"], "issue": "false_support"})

        by_category = {
            category: ranked_metrics([r for r in ranked_rows if r["category"] == category])
            for category in sorted(RETRIEVAL_CATEGORIES)
        }
        gated_n = len(gate_cases) if system == "ralg" and not args.skip_gate else 0
        rejections = sum(1 for case in gate_cases
                         if gate_results.get(case["case_id"]) is not True) if gated_n else None
        systems[system] = {
            "overall_ranked": ranked_metrics(ranked_rows),
            "by_category": by_category,
            "unsupported_rejection": (rejections / gated_n) if gated_n else None,
            "false_support_rate": ((gated_n - rejections) / gated_n) if gated_n else None,
            "unsupported_rejection_ci95": wilson_interval(rejections or 0, gated_n)
            if gated_n else None,
            "note": "" if system == "ralg"
            else "lexical baseline has no production support gate",
        }

    report = {
        "benchmark": manifest["benchmark_version"],
        "benchmark_sha256": manifest["benchmark_sha256"],
        "status": "single_shot_blind_evaluation_no_tuning_afterwards",
        "cases": len(cases),
        "documents": len(documents),
        "systems": systems,
        "case_level_failures": failures[:100],
        "gate_cases_run": len(gate_results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v["overall_ranked"] for k, v in systems.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
