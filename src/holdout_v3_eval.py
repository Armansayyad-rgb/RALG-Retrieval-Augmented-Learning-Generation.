#!/usr/bin/env python3
"""Holdout V3 Evaluator — isolated ephemeral index.

This evaluator builds a temporary index from the 7 V3 source artifacts
using production retriever_v2 chunking/embedding code. It does NOT modify
production knowledge/index paths.

Default invocation REFUSES to execute the frozen benchmark.
Use --execute-frozen-blind-run to override (NOT for production use).

Metrics:
  Recall@K = |relevant docs in top K| / |relevant docs|
  HitRate@K = 1 if Recall@K > 0, else 0
  MRR = 1 / rank of first relevant doc (0 if none)

Denominators:
  retrieval_supported = 75 (all categories with evidence spans)
  answer_supported = 70 (ordinary support categories)
  qualified = 5 (conditional_or_qualified — scored separately)
  rejection = 45 (unsupported + false_premise + misleading_overlap)
  total = 120
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
HOLDOUT_DIR = ROOT / "evaluation" / "holdout_v3"
SOURCES_DIR = HOLDOUT_DIR / "sources"
RESULTS_DIR = ROOT / "evaluation" / "results"

# Add src to path for production imports
sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------------------
# Execution guard
# ---------------------------------------------------------------------------

BLIND_GUARD = """
╔══════════════════════════════════════════════════════════════╗
║  HOLDOUT V3 BLIND RUN — EXECUTION BLOCKED                  ║
║                                                              ║
║  This would execute the frozen V3 benchmark and consume the  ║
║  blind evaluation. The default invocation refuses to do this. ║
║                                                              ║
║  Use --execute-frozen-blind-run to override.                  ║
║                                                              ║
║  WARNING: This flag should NOT be used during development.    ║
╚══════════════════════════════════════════════════════════════╝
"""


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_benchmark() -> list[dict]:
    bench_path = HOLDOUT_DIR / "holdout_v3_benchmark.jsonl"
    cases = []
    with open(bench_path, "r", encoding="utf-8") as f:
        for line in f:
            cases.append(json.loads(line))
    return cases


def load_manifest() -> dict:
    manifest_path = HOLDOUT_DIR / "holdout_v3_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Ephemeral index builder
# ---------------------------------------------------------------------------

def build_ephemeral_index(source_files: list[Path]) -> tuple[Any, Any, list[str], list[str]]:
    from retriever_v2 import load_chunks, build_index

    print("Building ephemeral V3 index...")
    chunks = []
    chunk_sources = []
    for source_file in source_files:
        file_chunks = load_chunks(source_file)
        chunks.extend(file_chunks)
        chunk_sources.extend([source_file.stem] * len(file_chunks))
    index, doc_freq = build_index(chunks)
    print(f"  Index built: {len(chunks)} chunks")
    return index, doc_freq, chunks, chunk_sources


def retrieve_from_index(
    index: Any,
    doc_freq: Any,
    chunks: list[str],
    chunk_sources: list[str],
    question: str,
    top_k: int = 5,
) -> list[dict]:
    from retriever_v2 import words, STOPWORDS

    q_words = [w for w in words(question) if w not in STOPWORDS]

    scores = []
    for i, chunk_count in enumerate(index):
        score = 0.0
        for qw in q_words:
            if qw in chunk_count:
                df = doc_freq.get(qw, 1)
                idf = 1.0 / df
                score += chunk_count[qw] * idf
        if score > 0:
            scores.append((i, score))

    scores.sort(key=lambda x: -x[1])
    results = []
    for idx, score in scores[:top_k]:
        results.append({
            "chunk_index": idx,
            "text": chunks[idx],
            "score": score,
            "source_document_id": chunk_sources[idx],
        })
    return results


# ---------------------------------------------------------------------------
# Scoring — retrieval metrics
# ---------------------------------------------------------------------------

def score_retrieval(
    retrieved: list[dict],
    evidence_document_ids: list[str],
    top_k: int = 5,
) -> dict:
    """Score unique relevant document IDs in the top K ranked chunks."""
    relevant = set(evidence_document_ids)
    if not relevant:
        return {"recall_at_k": 1.0, "hit_rate_at_k": 1, "mrr": 1.0,
                "relevant_found": 0, "total_relevant": 0}

    found = set()
    first_hit_rank = None
    for rank, item in enumerate(retrieved[:top_k], start=1):
        source_id = item["source_document_id"]
        if source_id in relevant:
            found.add(source_id)
            if first_hit_rank is None:
                first_hit_rank = rank
    recall = len(found) / len(relevant)
    hit_rate = 1 if recall > 0 else 0
    mrr = 1.0 / first_hit_rank if first_hit_rank else 0.0
    return {
        "recall_at_k": recall,
        "hit_rate_at_k": hit_rate,
        "mrr": mrr,
        "relevant_found": len(found),
        "total_relevant": len(relevant),
    }


# ---------------------------------------------------------------------------
# Scoring — answer quality
# ---------------------------------------------------------------------------

def score_answer(
    retrieved_text: str,
    expected_answer: str | None,
    expected_behavior: str | None,
    category: str,
) -> dict:
    result = {"correct": False, "method": "unknown"}

    if expected_behavior == "reject_or_state_insufficient_evidence":
        reject_signals = [
            "insufficient evidence", "not mentioned", "not found",
            "do not have", "cannot determine", "not available",
            "no information", "outside the scope",
        ]
        for signal in reject_signals:
            if signal.lower() in retrieved_text.lower():
                result["correct"] = True
                result["method"] = "rejection_match"
                break
        if not result["correct"]:
            result["method"] = "no_rejection_signal"
    elif expected_answer:
        if expected_answer.lower() in retrieved_text.lower():
            result["correct"] = True
            result["method"] = "exact_match"
        else:
            answer_words = set(expected_answer.lower().split())
            retrieved_words = set(retrieved_text.lower().split())
            overlap = len(answer_words & retrieved_words) / len(answer_words) if answer_words else 0
            if overlap > 0.5:
                result["correct"] = True
                result["method"] = "partial_match"

    return result


# ---------------------------------------------------------------------------
# Wilson CI
# ---------------------------------------------------------------------------

def compute_wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p_hat = k / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    spread = z * ((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    lower = max(0, center - spread)
    upper = min(1, center + spread)
    return p_hat, lower, upper


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

REJECTION_CATEGORIES = {"unsupported", "false_premise", "misleading_overlap"}
SUPPORTED_CATEGORIES = {"supported", "paraphrased", "procedural", "causal",
                        "cross_document", "document_scoped"}
QUALIFIED_CATEGORIES = {"conditional_or_qualified"}


def run_evaluation(*, dry_run: bool = True) -> dict:
    manifest = load_manifest()
    benchmark = load_benchmark()

    print(f"Benchmark version: {manifest['benchmark_version']}")
    print(f"Total cases: {len(benchmark)}")

    if dry_run:
        print("\nDRY RUN — not executing benchmark cases")
        print("Use --execute-frozen-blind-run for actual execution")
        return {"dry_run": True, "case_count": len(benchmark)}

    # Build ephemeral index
    source_files = sorted(SOURCES_DIR.glob("*.txt"))
    source_files = [f for f in source_files if f.name != "raw"]

    index, doc_freq, chunks, chunk_sources = build_ephemeral_index(source_files)

    # Score each case with error handling
    results = []
    errors = []
    for case in benchmark:
        try:
            t0 = time.time()
            retrieved = retrieve_from_index(
                index, doc_freq, chunks, chunk_sources, case["question"])
            latency_ms = (time.time() - t0) * 1000

            retrieved_texts = [r["text"] for r in retrieved]
            retrieval_score = score_retrieval(
                retrieved, case.get("evidence_document_ids", []))

            combined_text = " ".join(retrieved_texts)
            answer_score = score_answer(
                combined_text,
                case.get("expected_answer"),
                case.get("expected_behavior"),
                case["category"],
            )

            results.append({
                "case_id": case["case_id"],
                "category": case["category"],
                "retrieval": retrieval_score,
                "answer": answer_score,
                "latency_ms": latency_ms,
                "_retrieved": retrieved,
                "_evidence_document_ids": case.get("evidence_document_ids", []),
            })
        except Exception as e:
            errors.append({
                "case_id": case["case_id"],
                "category": case["category"],
                "error": str(e),
                "error_type": type(e).__name__,
            })

    # Determine run status
    error_cases = len(errors)
    completed_cases = len(results)
    total_cases = len(benchmark)
    run_status = "complete" if error_cases == 0 else "incomplete"

    print(f"\nCompleted: {completed_cases}/{total_cases} cases")
    if error_cases > 0:
        print(f"ERRORS: {error_cases} cases failed:")
        for err in errors:
            print(f"  {err['case_id']}: {err['error_type']}: {err['error'][:80]}")

    # Aggregate metrics (only if all cases completed)
    if run_status == "incomplete":
        print("\nWARNING: Run incomplete — aggregate metrics NOT computed")
        report = {
            "benchmark_version": manifest["benchmark_version"],
            "run_status": run_status,
            "total_cases": total_cases,
            "completed_cases": completed_cases,
            "error_cases": error_cases,
            "errors": errors,
            "metrics": None,
            "metrics_valid": False,
        }
        return report

    # Classify cases
    categories = Counter(r["category"] for r in results)
    retrieval_supported = [r for r in results
                          if r["category"] not in REJECTION_CATEGORIES]
    answer_supported = [r for r in results
                       if r["category"] in SUPPORTED_CATEGORIES]
    qualified_cases = [r for r in results
                      if r["category"] in QUALIFIED_CATEGORIES]
    rejection_cases = [r for r in results
                      if r["category"] in REJECTION_CATEGORIES]

    # Retrieval metrics (macro-averaged)
    recall_values = [r["retrieval"]["recall_at_k"] for r in retrieval_supported]
    hit_values = [r["retrieval"]["hit_rate_at_k"] for r in retrieval_supported]
    mrr_values = [r["retrieval"]["mrr"] for r in retrieval_supported]

    avg_recall = sum(recall_values) / len(recall_values) if recall_values else 0
    avg_hit_rate = sum(hit_values) / len(hit_values) if hit_values else 0
    avg_mrr = sum(mrr_values) / len(mrr_values) if mrr_values else 0

    # Per-K breakdown
    def macro_at_k(k: int, field: str) -> float:
        values = [
            score_retrieval(r["_retrieved"], r["_evidence_document_ids"], k)[field]
            for r in retrieval_supported
        ]
        return sum(values) / len(values) if values else 0.0

    recall_at_1 = macro_at_k(1, "recall_at_k")
    recall_at_3 = macro_at_k(3, "recall_at_k")
    recall_at_5 = macro_at_k(5, "recall_at_k")
    hit_rate_at_1 = macro_at_k(1, "hit_rate_at_k")
    hit_rate_at_3 = macro_at_k(3, "hit_rate_at_k")
    hit_rate_at_5 = macro_at_k(5, "hit_rate_at_k")

    # Answer correctness
    supported_correct = sum(1 for r in answer_supported if r["answer"]["correct"])
    false_rejection = sum(1 for r in answer_supported if not r["answer"]["correct"])

    correct_rejection = sum(1 for r in rejection_cases if r["answer"]["correct"])
    false_support = sum(1 for r in rejection_cases if not r["answer"]["correct"])

    # Qualified support (separate metric)
    qualified_correct = sum(1 for r in qualified_cases if r["answer"]["correct"])

    # Wilson CI for key metrics
    sr_prop, sr_lower, sr_upper = compute_wilson_ci(supported_correct, len(answer_supported))
    cr_prop, cr_lower, cr_upper = compute_wilson_ci(correct_rejection, len(rejection_cases))

    avg_latency = sum(r["latency_ms"] for r in results) / len(results) if results else 0
    for result in results:
        result.pop("_retrieved", None)
        result.pop("_evidence_document_ids", None)

    report = {
        "benchmark_version": manifest["benchmark_version"],
        "run_status": run_status,
        "total_cases": total_cases,
        "completed_cases": completed_cases,
        "error_cases": error_cases,
        "denominators": {
            "retrieval_supported": len(retrieval_supported),
            "answer_supported": len(answer_supported),
            "qualified": len(qualified_cases),
            "rejection": len(rejection_cases),
        },
        "metrics": {
            "retrieval": {
                "macro_recall": round(avg_recall, 4),
                "macro_hit_rate": round(avg_hit_rate, 4),
                "macro_mrr": round(avg_mrr, 4),
                "recall_at_1": round(recall_at_1, 4),
                "recall_at_3": round(recall_at_3, 4),
                "recall_at_5": round(recall_at_5, 4),
                "hit_rate_at_1": round(hit_rate_at_1, 4),
                "hit_rate_at_3": round(hit_rate_at_3, 4),
                "hit_rate_at_5": round(hit_rate_at_5, 4),
                "formula_note": (
                    "Recall@K = |relevant docs in top K| / |relevant docs|. "
                    "HitRate@K = 1 if Recall@K > 0 else 0. "
                    "MRR = 1/rank of first relevant doc. "
                    "All macro-averaged across retrieval-supported cases."
                ),
            },
            "answer": {
                "supported_correct": supported_correct,
                "false_rejection": false_rejection,
                "correct_rejection": correct_rejection,
                "false_support": false_support,
                "supported_accuracy_ci95": [round(sr_lower, 4), round(sr_upper, 4)],
                "correct_rejection_ci95": [round(cr_lower, 4), round(cr_upper, 4)],
            },
            "qualified": {
                "qualified_correct": qualified_correct,
                "qualified_total": len(qualified_cases),
                "qualified_accuracy": round(qualified_correct / len(qualified_cases), 4) if qualified_cases else 0,
                "note": "conditional_or_qualified cases scored separately; included in retrieval metrics but not in answer_supported denominator",
            },
        },
        "metrics_valid": True,
        "latency_ms_avg": round(avg_latency, 2),
        "category_counts": dict(categories),
    }

    print(json.dumps(report, indent=2))
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Holdout V3 Evaluator")
    parser.add_argument(
        "--execute-frozen-blind-run",
        action="store_true",
        help="Actually execute the frozen V3 benchmark (CONSUMES blind run)",
    )
    args = parser.parse_args()

    if not args.execute_frozen_blind_run:
        print(BLIND_GUARD)
        sys.exit(0)

    # Single-shot protection: fail CLOSED if result file already exists
    result_path = RESULTS_DIR / "holdout_v3_blind_once.json"
    if result_path.exists():
        print(f"ERROR: {result_path} already exists.")
        print("Refusing to overwrite the original blind result.")
        print("Delete the file manually only if you accept losing the original result.")
        sys.exit(1)

    # Execute evaluation
    result = run_evaluation(dry_run=False)

    # Save result with exclusive-create semantics
    try:
        with open(result_path, "x", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\nResult saved to {result_path}")
    except FileExistsError:
        # Race condition safeguard: another process created it between our check and write
        print(f"ERROR: {result_path} was created by another process during execution.")
        print("Result NOT saved. The original blind result is preserved.")
        sys.exit(1)


if __name__ == "__main__":
    main()
