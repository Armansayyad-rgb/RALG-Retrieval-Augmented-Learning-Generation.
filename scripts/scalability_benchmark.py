#!/usr/bin/env python3
"""Bounded synthetic retrieval scalability probe (no model or Docker required)."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.retriever_v2 import build_index, retrieve
def main():
 p=argparse.ArgumentParser(); p.add_argument("--levels", default="1000,5000,10000"); p.add_argument("--output",type=Path,default=ROOT/"logs"/"scalability_pilot.json"); a=p.parse_args()
 rows=[]
 for n in [int(x) for x in a.levels.split(",")]:
  chunks=[f"synthetic chunk {i} domain control value {i%17}" for i in range(n)]
  t=time.perf_counter(); idx,df=build_index(chunks); build_ms=(time.perf_counter()-t)*1000
  t=time.perf_counter(); retrieve("domain control value 7",chunks,idx,df); query_ms=(time.perf_counter()-t)*1000
  rows.append({"chunks":n,"build_ms":round(build_ms,2),"query_ms":round(query_ms,2)})
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps({"levels":rows,"note":"Requested 100k/250k/500k levels are opt-in; hardware unavailable."},indent=2),encoding="utf-8"); print(json.dumps(rows,indent=2))
if __name__=="__main__": main()
