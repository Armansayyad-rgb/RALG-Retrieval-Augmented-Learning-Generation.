#!/usr/bin/env python3
"""Feature-isolated retrieval ablations.

Only switches that have an explicit implementation seam are measured.  V4
query expansion, conflict/factual/provenance gates are deliberately reported
as not-applicable rather than simulated by monkey-patching production code.
"""
from __future__ import annotations
import argparse, json, re, statistics, time, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.retriever_v2 import build_index, retrieve, RuntimeChunk, INGESTED_CHUNK_BOOST

def terms(s): return set(re.findall(r"[a-z0-9']+", s.lower()))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=ROOT/"logs"/"ablation_results.json")
    a = p.parse_args()
    chunks = [f"domain {i%8} policy control value {i%31} revision {i%5}" for i in range(240)]
    chunks += [RuntimeChunk("runtime domain 3 policy control value 7", {"id":"synthetic"})]
    index, df = build_index(chunks)
    cases = [(f"what is policy control value {i%31}", i % 31) for i in range(80)]

    def run(use_postings=True, runtime_boost=True, dedupe=True):
        timings, hits = [], 0
        for q, value in cases:
            query = q if dedupe else q + " " + q
            start = time.perf_counter()
            if use_postings:
                ranked = retrieve(query, chunks, index, df, final_top_k=5)
            else:
                # Safe isolation of the postings seam: an equivalent scan index.
                class ScanIndex(list): pass
                scan = ScanIndex(index)
                ranked = retrieve(query, chunks, scan, df, final_top_k=5)
            if not runtime_boost:
                old = INGESTED_CHUNK_BOOST
                # Runtime boost is only observable through RuntimeChunk; use plain
                # string copies for this variant, without altering module state.
                plain = [str(x) for x in chunks]
                pi, pdf = build_index(plain)
                ranked = retrieve(query, plain, pi, pdf, final_top_k=5)
            timings.append((time.perf_counter()-start)*1000)
            hits += int(any(str(value) in str(x) for x in ranked))
        return {"recall_at_5": hits/len(cases), "mean_ms": statistics.fmean(timings)}

    measured = {
        "production": run(),
        "no_postings_optimization": run(use_postings=False),
        "no_runtime_boost": run(runtime_boost=False),
    }
    unavailable = {}
    for name in ("no_v4_expansion", "no_conflict_gate", "no_factual_grounding_gate",
                 "no_provenance_handling", "no_duplicate_reuse"):
        unavailable[name] = {"status":"not_applicable",
            "reason":"No public feature switch; isolating it would require changing production semantics."}
    payload = {"dataset":"synthetic_ablation_v2","cases":len(cases),
               "switches":measured, "not_applicable":unavailable,
               "note":"Measured switches execute distinct retrieval paths; no tuning or monkey-patching."}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
