#!/usr/bin/env python3
"""Authoritative Technical Dev Set V1 Evaluator.

Uses production retriever_v2 pipeline (not simplified BM25-only).
Builds ephemeral index from dev source documents.
Rerunnable by design — this is a development benchmark.

Usage:
    python authoritative_dev_v1_eval.py [--execute]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEV_DIR = ROOT / "evaluation" / "authoritative_dev_v1"
SOURCES_DIR = DEV_DIR / "sources"
RESULTS_DIR = ROOT / "evaluation" / "results"

sys.path.insert(0, str(ROOT / "src"))


def build_ephemeral_index(source_files: list[Path]) -> tuple[Any, Any, list[str], list[str]]:
    from retriever_v2 import load_chunks, build_index
    print("Building ephemeral dev index...")
    chunks = []
    chunk_sources = []
    for sf in source_files:
        fc = load_chunks(sf)
        chunks.extend(fc)
        chunk_sources.extend([sf.stem] * len(fc))
    index, doc_freq = build_index(chunks)
    print(f"  Index built: {len(chunks)} chunks from {len(source_files)} sources")
    return index, doc_freq, chunks, chunk_sources


def retrieve_production(
    question: str,
    chunks: list[str],
    index: Any,
    doc_freq: Any,
    chunk_sources: list[str],
    top_k: int = 5,
) -> list[dict]:
    """Use production retrieve() from retriever_v2 with reranking."""
    from retriever_v2 import retrieve, RuntimeChunk

    # Wrap chunks as RuntimeChunk with document_id metadata for document scoping
    runtime_chunks = []
    for i, chunk in enumerate(chunks):
        rc = RuntimeChunk(chunk, metadata={"document_id": chunk_sources[i]})
        runtime_chunks.append(rc)

    # Build a new index with RuntimeChunks
    from retriever_v2 import build_index as bi
    rt_index, rt_doc_freq = bi(runtime_chunks)

    results = retrieve(question, runtime_chunks, rt_index, rt_doc_freq, final_top_k=top_k)

    output = []
    for r in results:
        output.append({
            "chunk_index": r["chunk_index"],
            "text": r["chunk"],
            "final_score": r["final_score"],
            "lexical_score": r["lexical_score"],
            "source_document_id": r["chunk"].metadata.get("document_id", "unknown"),
        })
    return output


def score_retrieval(retrieved: list[dict], evidence_doc_ids: list[str], top_k: int = 5) -> dict:
    relevant = set(evidence_doc_ids)
    if not relevant:
        return {"recall_at_k": 1.0, "hit_rate_at_k": 1, "mrr": 1.0,
                "relevant_found": 0, "total_relevant": 0}
    found = set()
    first_hit_rank = None
    for rank, item in enumerate(retrieved[:top_k], start=1):
        sid = item["source_document_id"]
        if sid in relevant:
            found.add(sid)
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


def score_answer_dev(
    retrieved_texts: list[str],
    expected_answer: str,
    evidence_spans: list[str],
    category: str,
    should_answer: bool,
) -> dict:
    """Evidence-grounded scoring: check if expected_answer or evidence spans
    appear in retrieved text. More robust than V3's crude string matching."""
    combined = " ".join(retrieved_texts).lower()
    expected_lower = expected_answer.lower().strip()

    # Check 1: exact expected_answer in retrieved text
    exact_match = expected_lower in combined

    # Check 2: evidence spans in retrieved text
    evidence_found = 0
    for span in evidence_spans:
        if span.lower().strip() in combined:
            evidence_found += 1
    evidence_ratio = evidence_found / len(evidence_spans) if evidence_spans else 0

    # Check 3: word overlap (for paraphrased cases)
    expected_words = set(expected_lower.split())
    combined_words = set(combined.split())
    if expected_words:
        word_overlap = len(expected_words & combined_words) / len(expected_words)
    else:
        word_overlap = 0.0

    # Determine correctness
    if should_answer:
        # For supported/procedural/etc: need evidence or answer in text
        correct = exact_match or evidence_ratio >= 0.5 or word_overlap >= 0.6
    else:
        # For rejection: answer should NOT be in text
        correct = not exact_match and evidence_ratio < 0.3

    return {
        "correct": correct,
        "exact_match": exact_match,
        "evidence_ratio": evidence_ratio,
        "word_overlap": word_overlap,
    }


def load_benchmark(path: Path) -> list[dict]:
    cases = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def run_evaluation(execute: bool = False) -> dict:
    benchmark_path = DEV_DIR / "holdout_benchmark.jsonl"
    cases = load_benchmark(benchmark_path)

    source_files = sorted(SOURCES_DIR.glob("*.txt"))
    index, doc_freq, chunks, chunk_sources = build_ephemeral_index(source_files)

    metrics = {
        "retrieval": {"recall@1": [], "recall@3": [], "recall@5": [], "hit_rate@1": [], "hit_rate@3": [], "hit_rate@5": [], "mrr": []},
        "answer": {"supported_correct": 0, "supported_total": 0, "false_rejection": 0,
                   "correct_rejection": 0, "false_support": 0, "rejection_total": 0,
                   "qualified_correct": 0, "qualified_total": 0},
        "per_category": {},
        "errors": 0,
        "completed": 0,
        "total": len(cases),
        "latency_ms_avg": 0,
    }

    total_latency = 0
    for case in cases:
        cat = case["category"]
        if cat not in metrics["per_category"]:
            metrics["per_category"][cat] = {"total": 0, "correct": 0}

        try:
            t0 = time.time()
            retrieved = retrieve_production(
                case["question"], chunks, index, doc_freq, chunk_sources, top_k=5
            )
            latency = (time.time() - t0) * 1000
            total_latency += latency

            # Retrieval scoring
            for k in [1, 3, 5]:
                r = score_retrieval(retrieved, case["expected_document_ids"], top_k=k)
                metrics["retrieval"][f"recall@{k}"].append(r["recall_at_k"])
                metrics["retrieval"][f"hit_rate@{k}"].append(r["hit_rate_at_k"])
            metrics["retrieval"]["mrr"].append(score_retrieval(retrieved, case["expected_document_ids"], top_k=5)["mrr"])

            # Answer scoring
            ret_texts = [r["text"] for r in retrieved]
            answer_result = score_answer_dev(
                ret_texts,
                case.get("expected_answer", ""),
                case.get("evidence_spans", []),
                cat,
                case.get("should_answer", True),
            )

            if cat in ("supported", "paraphrased", "procedural", "causal", "cross_document", "document_scoped"):
                metrics["answer"]["supported_total"] += 1
                metrics["per_category"][cat]["total"] += 1
                if answer_result["correct"]:
                    metrics["answer"]["supported_correct"] += 1
                    metrics["per_category"][cat]["correct"] += 1
                else:
                    metrics["answer"]["false_rejection"] += 1
            elif cat in ("unsupported", "false_premise", "misleading_overlap"):
                metrics["answer"]["rejection_total"] += 1
                metrics["per_category"][cat]["total"] += 1
                if answer_result["correct"]:
                    metrics["answer"]["correct_rejection"] += 1
                    metrics["per_category"][cat]["correct"] += 1
                else:
                    metrics["answer"]["false_support"] += 1
            elif cat == "conditional_or_qualified":
                metrics["answer"]["qualified_total"] += 1
                metrics["per_category"][cat]["total"] += 1
                if answer_result["correct"]:
                    metrics["answer"]["qualified_correct"] += 1
                    metrics["per_category"][cat]["correct"] += 1

            metrics["completed"] += 1
        except Exception as e:
            metrics["errors"] += 1
            print(f"  ERROR on {case['id']}: {e}")

    # Aggregate
    for k in [1, 3, 5]:
        vals = metrics["retrieval"][f"recall@{k}"]
        metrics["retrieval"][f"recall@{k}"] = sum(vals) / len(vals) if vals else 0
        vals = metrics["retrieval"][f"hit_rate@{k}"]
        metrics["retrieval"][f"hit_rate@{k}"] = sum(vals) / len(vals) if vals else 0
    vals = metrics["retrieval"]["mrr"]
    metrics["retrieval"]["mrr"] = sum(vals) / len(vals) if vals else 0

    metrics["latency_ms_avg"] = total_latency / max(metrics["completed"], 1)

    # Percentages
    st = metrics["answer"]["supported_total"]
    rt = metrics["answer"]["rejection_total"]
    qt = metrics["answer"]["qualified_total"]
    metrics["answer"]["supported_accuracy"] = metrics["answer"]["supported_correct"] / st if st else 0
    metrics["answer"]["false_rejection_rate"] = metrics["answer"]["false_rejection"] / st if st else 0
    metrics["answer"]["correct_rejection_rate"] = metrics["answer"]["correct_rejection"] / rt if rt else 0
    metrics["answer"]["false_support_rate"] = metrics["answer"]["false_support"] / rt if rt else 0
    metrics["answer"]["qualified_accuracy"] = metrics["answer"]["qualified_correct"] / qt if qt else 0

    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Run evaluation")
    args = parser.parse_args()

    if not args.execute:
        print("Dry run. Use --execute to run evaluation.")
        return

    print("=" * 60)
    print("AUTHORITATIVE TECHNICAL DEV SET V1 — BASELINE EVALUATION")
    print("=" * 60)

    metrics = run_evaluation(execute=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "authoritative_dev_v1_baseline.json"
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nResults saved to {out_path}")

    print(f"\n--- RETRIEVAL ---")
    for k in [1, 3, 5]:
        print(f"  Recall@{k}:    {metrics['retrieval'][f'recall@{k}']:.4f}")
        print(f"  HitRate@{k}:   {metrics['retrieval'][f'hit_rate@{k}']:.4f}")
    print(f"  MRR:           {metrics['retrieval']['mrr']:.4f}")

    a = metrics["answer"]
    print(f"\n--- ANSWER ---")
    print(f"  Supported accuracy:  {a['supported_accuracy']:.4f} ({a['supported_correct']}/{a['supported_total']})")
    print(f"  False rejection:     {a['false_rejection_rate']:.4f}")
    print(f"  Correct rejection:   {a['correct_rejection_rate']:.4f} ({a['correct_rejection']}/{a['rejection_total']})")
    print(f"  False support:       {a['false_support_rate']:.4f}")
    print(f"  Qualified accuracy:  {a['qualified_accuracy']:.4f} ({a['qualified_correct']}/{a['qualified_total']})")

    print(f"\n--- PER CATEGORY ---")
    for cat, v in sorted(metrics["per_category"].items()):
        pct = v["correct"] / v["total"] * 100 if v["total"] else 0
        print(f"  {cat:25s}: {v['correct']}/{v['total']} ({pct:.1f}%)")

    print(f"\n--- ERRORS ---")
    print(f"  Completed: {metrics['completed']}/{metrics['total']}")
    print(f"  Errors:    {metrics['errors']}")
    print(f"  Latency:   {metrics['latency_ms_avg']:.1f}ms avg")


if __name__ == "__main__":
    main()
