#!/usr/bin/env python3
"""Safe, feature-isolated retrieval ablations with ranking metrics."""
from __future__ import annotations
import argparse, json, re, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from src.retriever_v2 import build_index, retrieve, RuntimeChunk
from src import retriever_v4

def metric(rows):
    supported = [r for r in rows if r["supported"]]
    unsupported = [r for r in rows if not r["supported"]]
    def at(k): return sum(r["rank"] is not None and r["rank"] <= k for r in supported)/len(supported)
    rr = [1/r["rank"] if r["rank"] else 0 for r in supported]
    return {
        "recall_at_1": at(1), "recall_at_3": at(3), "recall_at_5": at(5),
        "mrr": statistics.fmean(rr), "unsupported_rejection_rate":
            sum(r["rank"] is None for r in unsupported)/len(unsupported),
        "false_support_rate": sum(r["rank"] is not None for r in unsupported)/len(unsupported),
        "evidence_rate": sum(bool(r["results"]) for r in rows)/len(rows),
        "p50_latency_ms": statistics.median(r["latency_ms"] for r in rows),
        "p95_latency_ms": sorted(r["latency_ms"] for r in rows)[int(len(rows)*.95)-1],
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=ROOT/"logs"/"ablation_results.json")
    a = p.parse_args()
    chunks = [f"domain {i%8} policy control value {i%31} revision {i%5}" for i in range(240)]
    chunks += [RuntimeChunk("runtime domain 3 policy control value 7", {"id":"synthetic"})]
    index, df = build_index(chunks)
    cases = [(f"what is policy control value {i%31}", True, str(i%31)) for i in range(80)]
    cases += [(f"unsupported near miss value {i+1000}", False, str(i+1000)) for i in range(16)]

    def rows_for(fn):
        rows = []
        for q, supported, expected in cases:
            start = time.perf_counter(); results = fn(q)
            texts = [str(x) for x in results]
            rank = next((i+1 for i, text in enumerate(texts[:5]) if f"value {expected}" in text.lower()), None)
            rows.append({"supported": supported, "rank": rank, "results": texts,
                         "latency_ms": (time.perf_counter()-start)*1000})
        return rows

    def v2(use_postings=True, runtime_boost=True):
        if use_postings and runtime_boost:
            return lambda q: retrieve(q, chunks, index, df, final_top_k=5)
        plain = [str(x) for x in chunks] if not runtime_boost else chunks
        scan = list(index) if use_postings else type("ScanIndex", (list,), {})(index)
        if not use_postings:
            scan = type("ScanIndex", (list,), {})(index)
        return lambda q: retrieve(q, plain, scan if runtime_boost else build_index(plain)[0], df, final_top_k=5)

    measured = {
        "production": metric(rows_for(v2())),
        "no_postings_optimization": metric(rows_for(v2(use_postings=False))),
        "no_runtime_boost": metric(rows_for(v2(runtime_boost=False))),
    }

    def v4_variant(expanded=True, reuse=True):
        def run(q):
            plan = retriever_v4.build_queries(q)
            queries = plan["queries"] if expanded else plan["queries"][:1]
            all_results, seen = [], set()
            for query in queries:
                key = retriever_v4.normalize_text(query)
                if reuse and key in seen:
                    continue
                seen.add(key)
                all_results.extend(retriever_v4.retrieve_v2(query, chunks, index, df, final_top_k=5))
            return [item[-1] if isinstance(item, tuple) else item for item in all_results[:5]]
        return run
    measured["v4_expansion"] = metric(rows_for(v4_variant(expanded=True)))
    measured["no_v4_expansion"] = metric(rows_for(v4_variant(expanded=False)))
    measured["no_duplicate_query_reuse"] = metric(rows_for(v4_variant(expanded=True, reuse=False)))
    not_applicable = {
        "no_conflict_gate": "No public safe switch; not isolated.",
        "no_factual_grounding_gate": "No public safe switch; not isolated.",
        "no_provenance_handling": "No public safe switch; not isolated.",
    }
    payload = {"dataset":"synthetic_ablation_v3", "cases":len(cases),
               "switches":measured, "not_applicable":not_applicable,
               "note":"Variants use explicit retrieval seams; production defaults and fixtures are unchanged."}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
if __name__ == "__main__":
    main()
