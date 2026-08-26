#!/usr/bin/env python3
"""ONE-SHOT baseline evaluation of the frozen holdout_v1 benchmark.

Runs the current frozen lexical baseline and RALG hybrid retrieval plus the
production support gate. Results are written ONCE to
``evaluation/results/holdout_v1_baseline.json``; this tool must not be re-run
after tuning (there is no tuning in this branch).

Methodology:
- supported / paraphrase / multi_document cases: rank of the expected
  document(s) via the same text-match rule as the Stage 5 preliminary run;
  multi-document cases use the BEST rank among expected documents.
- unsupported / false_premise cases: scored through the production support
  gate (answer_question + build_answer_contract). Rejection = gate does NOT
  report support. The lexical baseline has no support gate; its rejection is
  reported as not-defined rather than fabricated.
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

from retriever_hybrid import retrieve  # noqa: E402
from stage6_evaluator import wilson_interval  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def words(text: str) -> set[str]:
    import re
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def rank_for(results: list, expected: str) -> int | None:
    for rank, result in enumerate(results, 1):
        if expected.casefold() in str(result.get("chunk", result)).casefold():
            return rank
    return None


def best_rank(results: list, doc_ids: list[str], texts: dict[str, str]) -> int | None:
    ranks = [rank_for(results, texts[doc_id][:120])
             for doc_id in doc_ids if doc_id in texts]
    ranks = [r for r in ranks if r is not None]
    return min(ranks) if ranks else None


def ranked_metrics(rows: list[dict]) -> dict:
    ranks = [row["rank"] for row in rows if row.get("rank") is not None] or []
    hit_rows = [row for row in rows if "rank" in row]
    n = len(hit_rows)
    r1 = sum(row.get("rank") == 1 for row in hit_rows)
    r5 = sum(row.get("rank") is not None and row["rank"] <= 5 for row in hit_rows)
    mrr_values = [1 / row["rank"] if row.get("rank") else 0 for row in hit_rows]
    return {
        "n": n,
        "recall_at_1": r1 / n if n else None,
        "recall_at_3": (sum(row.get("rank") is not None and row["rank"] <= 3
                            for row in hit_rows) / n) if n else None,
        "recall_at_5": r5 / n if n else None,
        "mrr": statistics.fmean(mrr_values) if mrr_values else None,
        "recall_at_1_ci95": wilson_interval(r1, n),
        "recall_at_5_ci95": wilson_interval(r5, n),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",
                        type=Path,
                        default=ROOT / "evaluation" / "results" / "holdout_v1_baseline.json")
    parser.add_argument("--skip-gate", action="store_true",
                        help="skip the model-backed support gate (retrieval only)")
    args = parser.parse_args()

    out_path = args.output
    if out_path.exists():
        print(json.dumps({"pass": False,
                          "error": f"{out_path} already exists; holdout baseline "
                                   "is one-shot and must not be overwritten"}))
        return 1

    holdout_dir = ROOT / "evaluation" / "holdout_v1"
    cases = load_jsonl(holdout_dir / "holdout_benchmark.jsonl")
    sources_manifest = load_jsonl(holdout_dir / "sources_manifest.jsonl")
    texts: dict[str, str] = {}
    doc_ids: list[str] = []
    documents: list[str] = []
    for entry in sources_manifest:
        path = ROOT / entry["source_filename"]
        text = path.read_text(encoding="utf-8-sig")
        doc_id = entry["doc_id"]
        texts[doc_id] = text
        doc_ids.append(doc_id)
        documents.append(text)

    from retriever_v2 import build_index
    index, df = build_index(documents)

    gate_cases = [c for c in cases if c["category"] in ("unsupported", "false_premise")]
    gate_results: dict[str, bool] = {}
    if not args.skip_gate:
        from rag_chat_v2 import answer_question, initialize_pipeline
        from webui.chat_handler import build_answer_contract
        pipeline = initialize_pipeline(verbose=True)
        for case in gate_cases:
            result = answer_question(pipeline, case["question"], verbose=False)
            contract = build_answer_contract(pipeline, case["question"], result, top_k=5)
            gate_results[case["case_id"]] = bool(contract.supported)

    failures: list[dict] = []
    systems: dict[str, dict] = {}
    for system in ("lexical", "ralg"):
        ranked_rows = []
        rejection_hits = []
        for case in cases:
            category = case["category"]
            if category in ("supported", "paraphrase", "multi_document"):
                if system == "lexical":
                    query_terms = words(case["question"])
                    ranked = sorted(range(len(documents)),
                                    key=lambda i: len(query_terms & words(documents[i])),
                                    reverse=True)[:5]
                    results = [{"chunk": documents[i]} for i in ranked]
                else:
                    results = retrieve(case["question"], documents, index, df)
                rank = best_rank(results, case["evidence_document_ids"], texts)
                ranked_rows.append({"case_id": case["case_id"], "category": category,
                                    "rank": rank})
                if rank is None or (category != "multi_document" and rank != 1):
                    failures.append({"system": system, "case_id": case["case_id"],
                                     "category": category, "rank": rank})
            else:
                if system == "lexical":
                    continue  # no support gate exists for a bare lexical ranker
                supported = gate_results.get(case["case_id"])
                rejected = supported is not True
                rejection_hits.append(not supported if supported is not None else False)
                if supported:
                    failures.append({"system": system, "case_id": case["case_id"],
                                     "category": category, "issue": "false_support"})
                ranked_rows.append({"case_id": case["case_id"], "category": category,
                                    "rank": None})
        metrics_by_category = {}
        for cat in ("supported", "paraphrase", "multi_document"):
            metrics_by_category[cat] = ranked_metrics(
                [r for r in ranked_rows if r["category"] == cat])
        overall = ranked_metrics([r for r in ranked_rows
                                  if r["category"] in ("supported", "paraphrase",
                                                       "multi_document")])
        gated_n = len(gate_cases) if system == "ralg" and not args.skip_gate else 0
        rejections = sum(1 for case in gate_cases if gate_results.get(case["case_id"]) is not True) \
            if system == "ralg" and not args.skip_gate else None
        systems[system] = {
            "overall_ranked": overall,
            "by_category": metrics_by_category,
            "unsupported_rejection": (rejections / gated_n) if gated_n else None,
            "false_support_rate": ((gated_n - rejections) / gated_n) if gated_n else None,
            "unsupported_rejection_ci95": wilson_interval(
                rejections or 0, gated_n) if gated_n else None,
            "note": "" if system == "ralg"
            else "lexical baseline has no support gate; rejection metrics undefined",
        }

    delta = {}
    lex_overall = systems["lexical"]["overall_ranked"]
    ralg_overall = systems["ralg"]["overall_ranked"]
    for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr"):
        if lex_overall[key] is not None and ralg_overall[key] is not None:
            delta[key] = round(ralg_overall[key] - lex_overall[key], 4)

    report = {
        "benchmark": "holdout_v1.0.0 (FROZEN / DO NOT TUNE)",
        "status": "single_shot_baseline_no_tuning_afterwards",
        "cases": len(cases),
        "documents": len(doc_ids),
        "systems": systems,
        "delta_ralg_minus_lexical": delta,
        "case_level_failures": failures[:100],
        "failure_count": {"lexical": sum(1 for f in failures if f["system"] == "lexical"),
                          "ralg": sum(1 for f in failures if f["system"] == "ralg")},
        "gate_cases_run": len(gate_results),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    summary = {name: {
        "R@1": sys_["overall_ranked"]["recall_at_1"],
        "R@3": sys_["overall_ranked"]["recall_at_3"],
        "R@5": sys_["overall_ranked"]["recall_at_5"],
        "MRR": sys_["overall_ranked"]["mrr"],
        "unsupported_rejection": sys_["unsupported_rejection"],
        "false_support_rate": sys_["false_support_rate"],
    } for name, sys_ in systems.items()}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
