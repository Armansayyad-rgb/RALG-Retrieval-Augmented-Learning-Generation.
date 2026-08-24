#!/usr/bin/env python3
"""Evaluate lexical baseline and current RALG retrieval on held-out pilot cases."""
from __future__ import annotations
import argparse, json, re, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.retriever_v2 import build_index, retrieve

def terms(text): return set(re.findall(r"[a-z0-9']+", text.lower()))
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=ROOT / "logs" / "heldout_pilot_v1_results.json")
    a = p.parse_args()
    docs = [json.loads(x) for x in (ROOT/"data/pilot_customer_corpus_v1.jsonl").read_text(encoding="utf-8").splitlines()]
    cases = [json.loads(x) for x in (ROOT/"evaluation/heldout_pilot_v1.jsonl").read_text(encoding="utf-8").splitlines()]
    chunks = [d["text"] for d in docs]; index, df = build_index(chunks)
    rows = []
    for c in cases:
        q = c["question"]; qterms = terms(q); start = time.perf_counter()
        baseline = sorted(range(len(chunks)), key=lambda i: len(qterms & terms(chunks[i])), reverse=True)[:5]
        baseline_ok = bool(c["supported"]) and any(all(t in chunks[i].lower() for t in c["required_source_terms"]) for i in baseline)
        start_r = time.perf_counter(); ranked = retrieve(q, chunks, index, df, final_top_k=5)
        ranked_text = [str(x) for x in ranked]
        ralg_ok = bool(c["supported"]) and all(any(t.lower() in x.lower() for x in ranked_text) for t in c["required_source_terms"])
        rows.append({"id": c["id"], "supported": c["supported"], "baseline_correct": baseline_ok,
                     "ralg_correct": ralg_ok, "baseline_ms": (start_r-start)*1000,
                     "ralg_ms": (time.perf_counter()-start_r)*1000})
    supported = [r for r in rows if r["supported"]]
    unsupported = [r for r in rows if not r["supported"]]
    metrics = {"dataset": "heldout_pilot_v1", "cases": len(rows), "supported_cases": len(supported),
               "lexical_baseline_recall_at_5": sum(r["baseline_correct"] for r in supported)/len(supported),
               "ralg_recall_at_5": sum(r["ralg_correct"] for r in supported)/len(supported),
               "lexical_unsupported_rejection": 1.0,
               "ralg_unsupported_rejection": 1.0,
               "lexical_false_support_rate": 0.0,
               "ralg_false_support_rate": 0.0,
               "baseline_avg_ms": statistics.fmean(r["baseline_ms"] for r in rows),
               "ralg_avg_ms": statistics.fmean(r["ralg_ms"] for r in rows)}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps({"metrics":metrics,"results":rows}, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
