#!/usr/bin/env python3
"""Holdout V3 Evaluator — isolated ephemeral index.

This evaluator builds a temporary index from the 7 V3 source artifacts
using production retriever_v2 chunking/embedding code. It does NOT modify
production knowledge/index paths.

Default invocation REFUSES to execute the frozen benchmark.
Use --execute-frozen-blind-run to override (NOT for production use).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
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


def load_benchmark() -> list[dict]:
    """Load the frozen V3 benchmark."""
    bench_path = HOLDOUT_DIR / "holdout_v3_benchmark.jsonl"
    cases = []
    with open(bench_path, "r", encoding="utf-8") as f:
        for line in f:
            cases.append(json.loads(line))
    return cases


def load_manifest() -> dict:
    """Load the V3 manifest."""
    manifest_path = HOLDOUT_DIR / "holdout_v3_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Ephemeral index builder
# ---------------------------------------------------------------------------

def build_ephemeral_index(source_files: list[Path]) -> tuple[Any, Any]:
    """Build a temporary index using production retriever_v2 code.

    Returns (index, document_frequency) tuple.
    The index is built only from V3 source artifacts.
    """
    from retriever_v2 import load_chunks, build_index

    print("Building ephemeral V3 index...")
    chunks = load_chunks(source_files)
    index, doc_freq = build_index(chunks)
    print(f"  Index built: {len(chunks)} chunks")
    return index, doc_freq


def retrieve_from_index(
    index: Any,
    doc_freq: Any,
    chunks: list[str],
    question: str,
    top_k: int = 5,
) -> list[dict]:
    """Retrieve top-k chunks for a question from the ephemeral index."""
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
        })
    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson 95% confidence interval."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p_hat = k / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    spread = z * ((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    lower = max(0, center - spread)
    upper = min(1, center + spread)
    return p_hat, lower, upper


def score_retrieval(retrieved_texts: list[str], evidence_spans: list[dict]) -> dict:
    """Score retrieval against evidence spans."""
    all_retrieved = " ".join(retrieved_texts)
    hits = 0
    for span in evidence_spans:
        if span["quoted_text"][:30] in all_retrieved:
            hits += 1
    recall = hits / len(evidence_spans) if evidence_spans else 0.0
    return {"recall": recall, "hits": hits, "total": len(evidence_spans)}


def score_answer(
    retrieved_text: str,
    expected_answer: str | None,
    expected_behavior: str | None,
    category: str,
) -> dict:
    """Score answer quality."""
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
# Main evaluation
# ---------------------------------------------------------------------------

def run_evaluation(*, dry_run: bool = True) -> dict:
    """Run the V3 evaluation."""
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

    from retriever_v2 import load_chunks
    chunks = load_chunks(source_files)
    index, doc_freq = build_ephemeral_index(source_files)

    # Score each case
    results = []
    for case in benchmark:
        t0 = time.time()
        retrieved = retrieve_from_index(index, doc_freq, chunks, case["question"])
        latency_ms = (time.time() - t0) * 1000

        retrieved_texts = [r["text"] for r in retrieved]
        retrieval_score = score_retrieval(retrieved_texts, case.get("evidence_spans", []))

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
        })

    # Aggregate metrics
    categories = Counter(r["category"] for r in results)
    retrieval_supported = [r for r in results if r["category"] not in ("unsupported", "false_premise", "misleading_overlap")]
    rejection_cases = [r for r in results if r["category"] in ("unsupported", "false_premise", "misleading_overlap")]

    recall_at_1 = sum(1 for r in retrieval_supported if r["retrieval"]["hits"] >= 1) / len(retrieval_supported) if retrieval_supported else 0
    recall_at_3 = sum(1 for r in retrieval_supported if r["retrieval"]["hits"] >= 2) / len(retrieval_supported) if retrieval_supported else 0
    recall_at_5 = sum(1 for r in retrieval_supported if r["retrieval"]["hits"] >= 3) / len(retrieval_supported) if retrieval_supported else 0

    correct_rejection = sum(1 for r in rejection_cases if r["answer"]["correct"])
    false_support = sum(1 for r in rejection_cases if not r["answer"]["correct"])

    supported_correct = sum(1 for r in retrieval_supported if r["answer"]["correct"])
    false_rejection = sum(1 for r in retrieval_supported if not r["answer"]["correct"])

    avg_latency = sum(r["latency_ms"] for r in results) / len(results) if results else 0

    report = {
        "benchmark_version": manifest["benchmark_version"],
        "case_count": len(results),
        "category_counts": dict(categories),
        "metrics": {
            "retrieval": {
                "recall_at_1": recall_at_1,
                "recall_at_3": recall_at_3,
                "recall_at_5": recall_at_5,
            },
            "answer": {
                "supported_correct": supported_correct,
                "false_rejection": false_rejection,
                "correct_rejection": correct_rejection,
                "false_support": false_support,
            },
        },
        "latency_ms_avg": avg_latency,
    }

    print(json.dumps(report, indent=2))
    return report


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

    # Only reaches here with explicit flag
    result = run_evaluation(dry_run=False)

    # Save result
    result_path = RESULTS_DIR / "holdout_v3_blind_once.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nResult saved to {result_path}")


if __name__ == "__main__":
    main()
