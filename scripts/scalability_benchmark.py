#!/usr/bin/env python3
"""Large-scale synthetic retrieval validation with bounded safety controls."""
from __future__ import annotations
import argparse, json, os, statistics, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.retriever_v2 import build_index, retrieve
try:
    import psutil
except ImportError:
    psutil = None

def rss_mb():
    return round(psutil.Process(os.getpid()).memory_info().rss/1048576, 2) if psutil else None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--levels", default="100000,250000")
    p.add_argument("--allow-500k", action="store_true")
    p.add_argument("--max-safe-chunks", type=int, default=50000,
                   help="skip larger levels unless explicitly raised")
    p.add_argument("--output",type=Path,default=ROOT/"logs"/"scale_validation.json")
    a=p.parse_args(); rows=[]
    levels=[int(x) for x in a.levels.split(",") if x.strip()]
    if 500000 in levels and not a.allow_500k: levels.remove(500000)
    for n in levels:
        if n > 500000: rows.append({"chunks":n,"status":"not_run","reason":"safety limit"}); continue
        if n > a.max_safe_chunks:
            rows.append({"chunks":n,"status":"not_run",
                         "reason":f"bounded safety budget ({a.max_safe_chunks} chunks); raise --max-safe-chunks"})
            continue
        before=rss_mb()
        chunks=[f"synthetic domain {i%16} revision {i%11} control value {i%97} document {i}" for i in range(n)]
        t=time.perf_counter(); idx,df=build_index(chunks); build_ms=(time.perf_counter()-t)*1000
        qs=[f"domain {i%16} control value {i%97}" for i in range(100)]
        lat=[]
        for q in qs:
            s=time.perf_counter(); retrieve(q,chunks,idx,df); lat.append((time.perf_counter()-s)*1000)
        inc={}
        for amount in (100,1000,5000):
            extra=[f"incremental domain {i%7} value {i}" for i in range(amount)]
            s=time.perf_counter(); chunks.extend(extra); from src.retriever_v2 import extend_index
            extend_index(idx,df,extra,n); inc[str(amount)]=round((time.perf_counter()-s)*1000,2)
        delete_n=min(100, len(chunks)); del chunks[-delete_n:]
        s=time.perf_counter(); ridx,rdf=build_index(chunks); rebuild_ms=(time.perf_counter()-s)*1000
        rows.append({"chunks":n,"status":"measured","rss_before_mb":before,"rss_after_mb":rss_mb(),
          "build_ms":round(build_ms,2),"query_p50_ms":round(statistics.median(lat),3),
          "query_p95_ms":round(sorted(lat)[int(len(lat)*.95)-1],3),"incremental_ms":inc,
          "delete_count":delete_n,"rebuild_after_delete_ms":round(rebuild_ms,2)})
        del chunks,idx,df,ridx,rdf
    payload={"levels":rows,"psutil_available":psutil is not None,
             "note":"500k requires --allow-500k; measurements are machine-dependent."}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(json.dumps(payload,indent=2))
if __name__=="__main__": main()
