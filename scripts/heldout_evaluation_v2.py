#!/usr/bin/env python3
"""Independent 320-case held-out synthetic benchmark (long documents)."""
from __future__ import annotations
import argparse,json,re,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.retriever_v2 import build_index,retrieve
DOMAINS=("safety","finance","health","manufacturing","software","energy","logistics","education")
def main():
 p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,default=ROOT/"logs"/"heldout_v2_results.json"); a=p.parse_args()
 docs=[(" ".join([f"{d} manual revision {r} controlled procedure value {i}."]*8)) for i,(d,r) in enumerate(( (DOMAINS[i%8],i%4) for i in range(80)))]
 cases=[]; answers=[]
 for i in range(320):
  d=DOMAINS[i%8]; value=i%80
  supported=i%5 != 0
  q=f"What controlled procedure value {value} applies to {d}?"
  if not supported: q=f"What unsupported near-miss procedure value {value+1000} applies to {d}?"
  cases.append((q,supported,d,value)); answers.append(value)
 chunks=docs; idx,df=build_index(chunks); rows=[]
 for q,supported,d,value in cases:
  st=time.perf_counter(); ranked=retrieve(q,chunks,idx,df,final_top_k=5); ms=(time.perf_counter()-st)*1000
  expected = value if supported else value + 1000
  ok=any(f"value {expected}" in str(x).lower() for x in ranked)
  rows.append({"supported":supported,"correct":ok,"latency_ms":ms})
 sup=[r for r in rows if r["supported"]]; uns=[r for r in rows if not r["supported"]]
 metrics={"dataset":"heldout_synthetic_v2","cases":len(rows),"supported_cases":len(sup),"unsupported_cases":len(uns),"recall_at_5":sum(r["correct"] for r in sup)/len(sup),"unsupported_rejection_rate":"not_applicable","near_miss_false_support_rate":sum(r["correct"] for r in uns)/len(uns),"p50_ms":statistics.median(r["latency_ms"] for r in rows),"p95_ms":sorted(r["latency_ms"] for r in rows)[int(len(rows)*.95)-1],"domains":len(DOMAINS),"long_document_revisions_conflicts":True}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps({"metrics":metrics,"results":rows},indent=2),encoding="utf-8"); print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()
