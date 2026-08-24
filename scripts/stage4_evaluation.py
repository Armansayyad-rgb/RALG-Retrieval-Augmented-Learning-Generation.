#!/usr/bin/env python3
"""Evaluate Stage 4 evidence retrieval without changing production configuration."""
from __future__ import annotations
import argparse, json, re, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from src.retriever_v2 import build_index, retrieve
from src import retriever_v4

def terms(text): return set(re.findall(r"[a-z0-9]+", text.lower()))
def rank_for(results, required):
    for rank, item in enumerate(results, 1):
        text = str(item).lower()
        if all(str(x).lower() in text for x in required):
            return rank
    return None
def summarize(rows):
    sup, uns = [r for r in rows if r["supported"]], [r for r in rows if not r["supported"]]
    def at(k): return sum(r["rank"] is not None and r["rank"] <= k for r in sup) / len(sup) if sup else None
    lat = sorted(r["latency_ms"] for r in rows)
    return {"recall_at_1": at(1), "recall_at_3": at(3), "recall_at_5": at(5),
            "mrr": statistics.fmean(1/r["rank"] if r["rank"] else 0 for r in sup) if sup else None,
            "unsupported_rejection": sum(r["rank"] is None for r in uns)/len(uns) if uns else None,
            "false_support": sum(r["rank"] is not None for r in uns)/len(uns) if uns else None,
            "evidence_correctness": sum(r["evidence_correct"] for r in sup)/len(sup) if sup else None,
            "p50_ms": statistics.median(lat), "p95_ms": lat[int(len(lat)*.95)-1]}
def main():
    p = argparse.ArgumentParser(); p.add_argument("--output", type=Path, default=ROOT/"logs"/"stage4_evaluation.json"); a = p.parse_args()
    docs = [json.loads(x) for x in (ROOT/"data"/"stage4_customer_corpus_v1.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    cases = [json.loads(x) for x in (ROOT/"evaluation"/"heldout_stage4_customer_v1.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    chunks = [d["text"] for d in docs]; index, df = build_index(chunks)
    def run(kind, question):
        if kind == "lexical":
            qt = terms(question); return sorted(chunks, key=lambda x: len(qt & terms(x)), reverse=True)[:5]
        if kind == "ralg":
            return retrieve(question, chunks, index, df, final_top_k=5)
        out = retriever_v4.retrieve(question, chunks, index, df)
        return out.get("results", [])[:5] if isinstance(out, dict) else out[:5]
    all_results = {}
    for kind in ("lexical", "ralg", "v4"):
        rows = []
        for c in cases:
            st = time.perf_counter(); results = run(kind, c["question"]); ms = (time.perf_counter()-st)*1000
            required = c["required_source_terms"]
            rank = rank_for(results, required)
            rows.append({"id": c["id"], "case_type": c["case_type"], "supported": c["supported"],
                         "rank": rank, "evidence_correct": (rank is not None) == bool(c["supported"]), "latency_ms": ms})
        by_cat = {cat: summarize([r for r,c in zip(rows,cases) if c["case_type"] == cat]) for cat in sorted({c["case_type"] for c in cases})}
        all_results[kind] = {"metrics": summarize(rows), "per_category": by_cat, "rows": rows}
    payload = {"dataset": "heldout_stage4_customer_v1", "cases": len(cases), "systems": all_results,
               "semantic_ablations": {"conflict": "N/A", "factual": "N/A", "provenance": "N/A"}}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: v["metrics"] for k,v in all_results.items()}, indent=2))
if __name__ == "__main__": main()
