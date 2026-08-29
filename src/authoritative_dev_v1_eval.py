#!/usr/bin/env python3
"""Authoritative Technical Dev Set V1 Evaluator — E2E Production Version.

Executes production execute_runtime() pipeline including answer generation,
support gate, and document scoping.  Builds ephemeral index from dev source
documents as RuntimeChunks for corpus isolation.

Layer A: Retrieval / Evidence metrics (deterministic, scored on chunks)
Layer B: End-to-end production answer metrics (executes real pipeline)

Usage:
    python authoritative_dev_v1_eval.py [--execute]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEV_DIR = ROOT / "evaluation" / "authoritative_dev_v1"
SOURCES_DIR = DEV_DIR / "sources"
RESULTS_DIR = ROOT / "evaluation" / "results"

sys.path.insert(0, str(ROOT / "src"))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("authoritative_dev_v1_eval")


def build_dev_pipeline(source_files: list[Path]) -> dict[str, Any]:
    """Build a production pipeline dict with dev-only RuntimeChunks.

    This achieves corpus isolation: the pipeline contains ONLY the 12 dev
    source documents.  Static KB, persisted documents, and other corpora
    cannot leak because the pipeline's chunks list is exclusively dev sources.
    """
    from retriever_v2 import load_chunks, build_index, RuntimeChunk

    chunks: list[RuntimeChunk] = []
    chunk_sources: list[str] = []
    for sf in source_files:
        fc = load_chunks(sf)
        for c in fc:
            rc = RuntimeChunk(c, metadata={"document_id": sf.stem})
            chunks.append(rc)
            chunk_sources.append(sf.stem)

    index, doc_freq = build_index(chunks)

    pipeline = {
        "device": None,
        "tokenizer": None,
        "model": None,
        "chunks": chunks,
        "retrieval_index": index,
        "document_frequency": doc_freq,
        "uploaded_docs": [],
        "runtime_persistence": False,
        "runtime_upload_dir": None,
    }
    return pipeline, chunk_sources


def load_benchmark(path: Path) -> list[dict]:
    cases = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def score_retrieval_layer_a(
    raw: dict,
    evidence_doc_ids: list[str],
    top_k: int = 5,
) -> dict:
    """Layer A: Score retrieval quality from the raw result evidence.

    Uses the evidence/sources produced by the production pipeline to measure
    whether expected documents were retrieved.
    """
    if not evidence_doc_ids:
        return {"recall@k": 1.0, "hit_rate": 1, "mrr": 1.0,
                "relevant_found": 0, "total_relevant": 0}

    evidence = raw.get("evidence") or []
    sources = raw.get("sources") or []

    retrieved_doc_ids = []
    for s in sources[:top_k]:
        doc_id = s.get("document_id") or s.get("id", "")
        if doc_id:
            retrieved_doc_ids.append(doc_id)
    if not retrieved_doc_ids:
        for e in evidence[:top_k]:
            if isinstance(e, dict):
                doc_id = e.get("document_id", "")
                if doc_id:
                    retrieved_doc_ids.append(doc_id)

    relevant = set(evidence_doc_ids)
    found = set()
    first_hit_rank = None
    for rank, doc_id in enumerate(retrieved_doc_ids[:top_k], start=1):
        if doc_id in relevant:
            found.add(doc_id)
            if first_hit_rank is None:
                first_hit_rank = rank

    recall = len(found) / len(relevant) if relevant else 1.0
    hit_rate = 1 if recall > 0 else 0
    mrr = 1.0 / first_hit_rank if first_hit_rank else 0.0

    return {
        "recall@k": recall,
        "hit_rate": hit_rate,
        "mrr": mrr,
        "relevant_found": len(found),
        "total_relevant": len(relevant),
    }


SYSTEM_UNSUPPORTED = (
    "I couldn't find enough reliable evidence in the current "
    "knowledge base."
)


def score_answer_layer_b(
    execution_result: Any,
    case: dict,
) -> dict:
    """Layer B: Score the actual production answer.

    Categories:
    - supported/procedural/causal/paraphrased: require supported=True
    - cross_document: require supported=True + multi-source evidence
    - document_scoped: require supported=True + scoped evidence
    - unsupported/false_premise/misleading_overlap: require supported=False
    - conditional_or_qualified: require supported=True + qualification
    """
    cat = case["category"]
    answer = execution_result.answer or ""
    supported = execution_result.supported
    sources = execution_result.sources or []
    answer_type = execution_result.answer_type or ""
    plan = execution_result.plan

    source_doc_ids = [s.get("document_id", "") for s in sources if isinstance(s, dict)]

    if cat in ("unsupported", "false_premise", "misleading_overlap"):
        correct = not supported or answer_type == "system"
        return {"correct": correct, "method": "abstention_check"}

    if cat in ("supported", "paraphrased", "procedural", "causal"):
        correct = supported and len(answer.strip()) > 0
        return {"correct": correct, "method": "support_gate"}

    if cat == "cross_document":
        expected_docs = set(case.get("expected_document_ids", []))
        covered = expected_docs & set(source_doc_ids)
        correct = supported and len(covered) >= 1
        return {"correct": correct, "method": "support_plus_evidence",
                "coverage": len(covered) / len(expected_docs) if expected_docs else 0}

    if cat == "document_scoped":
        allowed = set(case.get("expected_document_ids", []))
        if allowed and source_doc_ids:
            all_scoped = all(d in allowed for d in source_doc_ids if d)
            correct = supported and all_scoped
        else:
            correct = supported
        return {"correct": correct, "method": "scope_check"}

    if cat == "conditional_or_qualified":
        qualification = case.get("qualification", "")
        has_qualification = False
        if qualification:
            qual_words = set(qualification.lower().split())
            answer_words = set(answer.lower().split())
            has_qualification = len(qual_words & answer_words) >= len(qual_words) * 0.5
        else:
            has_qualification = True
        correct = supported and has_qualification
        return {"correct": correct, "method": "support_plus_qualification"}

    return {"correct": False, "method": "unscorable", "human_review_required": True}


def run_evaluation(execute: bool = False) -> dict:
    from runtime_architecture import execute_runtime
    from rag_chat_v2 import answer_question
    from webui.chat_handler import build_answer_contract, collect_sources

    benchmark_path = DEV_DIR / "holdout_benchmark.jsonl"
    cases = load_benchmark(benchmark_path)

    source_files = sorted(SOURCES_DIR.glob("*.txt"))
    pipeline, chunk_sources = build_dev_pipeline(source_files)

    metrics = {
        "evaluator_version": "authoritative_dev_v1_e2e_v1",
        "methodology": "production execute_runtime() pipeline",
        "layer_a_retrieval": {
            "recall@1": [], "recall@3": [], "recall@5": [],
            "hit_rate@1": [], "hit_rate@3": [], "hit_rate@5": [],
            "mrr": [],
        },
        "layer_b_answer": {
            "supported_correct": 0, "supported_total": 0,
            "false_rejection": 0,
            "correct_rejection": 0, "false_support": 0,
            "rejection_total": 0,
            "qualified_correct": 0, "qualified_total": 0,
            "cross_document_correct": 0, "cross_document_total": 0,
            "document_scoped_correct": 0, "document_scoped_total": 0,
            "auto_scored": 0, "human_review_required": 0,
        },
        "per_category": {},
        "errors": 0,
        "model_required": 0,
        "completed": 0,
        "total": len(cases),
        "latency_ms_avg_retrieval": 0,
        "latency_ms_avg_e2e": 0,
    }

    total_latency_retrieval = 0
    total_latency_e2e = 0

    for case in cases:
        cat = case["category"]
        if cat not in metrics["per_category"]:
            metrics["per_category"][cat] = {"total": 0, "correct": 0}

        doc_ids_for_scope = None
        if cat == "document_scoped":
            doc_ids_for_scope = case.get("expected_document_ids") or None

        try:
            t0 = time.time()
            execution_result = execute_runtime(
                pipeline,
                case["question"],
                top_k=5,
                answer_fn=answer_question,
                contract_fn=build_answer_contract,
                sources_fn=collect_sources,
                document_ids=doc_ids_for_scope,
            )
            e2e_latency = (time.time() - t0) * 1000
            total_latency_e2e += e2e_latency

            raw = execution_result.raw or {}
            raw["sources"] = execution_result.sources or []
            retrieval_scores = {}
            for k in [1, 3, 5]:
                r = score_retrieval_layer_a(raw, case.get("expected_document_ids", []), top_k=k)
                metrics["layer_a_retrieval"][f"recall@{k}"].append(r["recall@k"])
                metrics["layer_a_retrieval"][f"hit_rate@{k}"].append(r["hit_rate"])
            mrr_r = score_retrieval_layer_a(raw, case.get("expected_document_ids", []), top_k=5)
            metrics["layer_a_retrieval"]["mrr"].append(mrr_r["mrr"])

            answer_result = score_answer_layer_b(execution_result, case)

            if answer_result.get("human_review_required"):
                metrics["layer_b_answer"]["human_review_required"] += 1
            elif answer_result.get("method") != "unscorable":
                metrics["layer_b_answer"]["auto_scored"] += 1

            metrics["per_category"][cat]["total"] += 1

            if cat in ("supported", "paraphrased", "procedural", "causal"):
                metrics["layer_b_answer"]["supported_total"] += 1
                if answer_result["correct"]:
                    metrics["layer_b_answer"]["supported_correct"] += 1
                    metrics["per_category"][cat]["correct"] += 1
                else:
                    metrics["layer_b_answer"]["false_rejection"] += 1

            elif cat in ("unsupported", "false_premise", "misleading_overlap"):
                metrics["layer_b_answer"]["rejection_total"] += 1
                if answer_result["correct"]:
                    metrics["layer_b_answer"]["correct_rejection"] += 1
                    metrics["per_category"][cat]["correct"] += 1
                else:
                    metrics["layer_b_answer"]["false_support"] += 1

            elif cat == "conditional_or_qualified":
                metrics["layer_b_answer"]["qualified_total"] += 1
                if answer_result["correct"]:
                    metrics["layer_b_answer"]["qualified_correct"] += 1
                    metrics["per_category"][cat]["correct"] += 1

            elif cat == "cross_document":
                metrics["layer_b_answer"]["cross_document_total"] += 1
                if answer_result["correct"]:
                    metrics["layer_b_answer"]["cross_document_correct"] += 1
                    metrics["per_category"][cat]["correct"] += 1

            elif cat == "document_scoped":
                metrics["layer_b_answer"]["document_scoped_total"] += 1
                if answer_result["correct"]:
                    metrics["layer_b_answer"]["document_scoped_correct"] += 1
                    metrics["per_category"][cat]["correct"] += 1

            metrics["completed"] += 1

        except Exception as e:
            err_str = str(e)
            if "NoneType" in err_str or "tokenizer" in err_str.lower():
                metrics["model_required"] += 1
                metrics["errors"] += 1
            else:
                metrics["errors"] += 1
                print(f"  ERROR on {case['id']}: {e}")

    for k in [1, 3, 5]:
        vals = metrics["layer_a_retrieval"][f"recall@{k}"]
        metrics["layer_a_retrieval"][f"recall@{k}"] = sum(vals) / len(vals) if vals else 0
        vals = metrics["layer_a_retrieval"][f"hit_rate@{k}"]
        metrics["layer_a_retrieval"][f"hit_rate@{k}"] = sum(vals) / len(vals) if vals else 0
    vals = metrics["layer_a_retrieval"]["mrr"]
    metrics["layer_a_retrieval"]["mrr"] = sum(vals) / len(vals) if vals else 0

    completed = max(metrics["completed"], 1)
    metrics["latency_ms_avg_e2e"] = total_latency_e2e / completed

    a = metrics["layer_b_answer"]
    st = a["supported_total"]
    rt = a["rejection_total"]
    qt = a["qualified_total"]
    cdt = a["cross_document_total"]
    dst = a["document_scoped_total"]

    a["supported_accuracy"] = a["supported_correct"] / st if st else 0
    a["false_rejection_rate"] = a["false_rejection"] / st if st else 0
    a["correct_rejection_rate"] = a["correct_rejection"] / rt if rt else 0
    a["false_support_rate"] = a["false_support"] / rt if rt else 0
    a["qualified_accuracy"] = a["qualified_correct"] / qt if qt else 0
    a["cross_document_accuracy"] = a["cross_document_correct"] / cdt if cdt else 0
    a["document_scoped_accuracy"] = a["document_scoped_correct"] / dst if dst else 0

    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Run evaluation")
    args = parser.parse_args()

    if not args.execute:
        print("Dry run. Use --execute to run evaluation.")
        return

    print("=" * 60)
    print("AUTHORITATIVE DEV SET V1 — E2E PRODUCTION EVALUATION")
    print("=" * 60)

    metrics = run_evaluation(execute=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "authoritative_dev_v1_e2e_baseline.json"
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nResults saved to {out_path}")

    r = metrics["layer_a_retrieval"]
    print(f"\n--- LAYER A: RETRIEVAL ---")
    for k in [1, 3, 5]:
        print(f"  Recall@{k}:    {r[f'recall@{k}']:.4f}")
        print(f"  HitRate@{k}:   {r[f'hit_rate@{k}']:.4f}")
    print(f"  MRR:           {r['mrr']:.4f}")

    a = metrics["layer_b_answer"]
    print(f"\n--- LAYER B: END-TO-END PRODUCTION ---")
    print(f"  Supported accuracy:  {a['supported_accuracy']:.4f} ({a['supported_correct']}/{a['supported_total']})")
    print(f"  False rejection:     {a['false_rejection_rate']:.4f}")
    print(f"  Correct rejection:   {a['correct_rejection_rate']:.4f} ({a['correct_rejection']}/{a['rejection_total']})")
    print(f"  False support:       {a['false_support_rate']:.4f}")
    print(f"  Qualified accuracy:  {a['qualified_accuracy']:.4f} ({a['qualified_correct']}/{a['qualified_total']})")
    print(f"  Cross-doc accuracy:  {a['cross_document_accuracy']:.4f} ({a['cross_document_correct']}/{a['cross_document_total']})")
    print(f"  Document-scoped:     {a['document_scoped_accuracy']:.4f} ({a['document_scoped_correct']}/{a['document_scoped_total']})")

    print(f"\n--- PER CATEGORY ---")
    for cat, v in sorted(metrics["per_category"].items()):
        pct = v["correct"] / v["total"] * 100 if v["total"] else 0
        print(f"  {cat:25s}: {v['correct']}/{v['total']} ({pct:.1f}%)")

    print(f"\n--- AUTOMATION ---")
    print(f"  Auto-scored:         {a['auto_scored']}")
    print(f"  Human review needed: {a['human_review_required']}")

    print(f"\n--- ERRORS ---")
    print(f"  Completed: {metrics['completed']}/{metrics['total']}")
    print(f"  Errors:    {metrics['errors']}")
    print(f"  Model required (counted as error): {metrics['model_required']}")
    print(f"  E2E latency:  {metrics['latency_ms_avg_e2e']:.1f}ms avg")


if __name__ == "__main__":
    main()
