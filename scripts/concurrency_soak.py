#!/usr/bin/env python3
"""Bounded mixed retrieval concurrency soak."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.retriever_v2 import build_index,retrieve
try:
 import torch
 torch.set_num_threads(1)
except Exception:
 pass
try:
 import psutil
except ImportError: psutil=None
def main():
 p=argparse.ArgumentParser(); p.add_argument("--requests",type=int,default=1000); p.add_argument("--workers",type=int,default=16); p.add_argument("--output",type=Path,default=ROOT/"logs"/"concurrency_soak.json"); a=p.parse_args()
 chunks=[f"soak domain {i%12} policy value {i%37} revision {i%9}" for i in range(500)]; idx,df=build_index(chunks)
 rss=lambda: round(psutil.Process(os.getpid()).memory_info().rss/1048576,2) if psutil else None
 def one(i):
  q=("unsupported near miss question "+str(i)) if i%10==0 else f"domain {i%12} policy value {i%37}"
  s=time.perf_counter(); retrieve(q,chunks,idx,df); return (time.perf_counter()-s)*1000
 errors=[]; lat=[]; start=time.perf_counter(); before=rss()
 with ThreadPoolExecutor(max_workers=a.workers) as ex:
  futures=[ex.submit(one,i) for i in range(a.requests)]
  for f in as_completed(futures):
   try: lat.append(f.result())
   except Exception as exc: errors.append(type(exc).__name__)
 elapsed=(time.perf_counter()-start)*1000
 payload={"requests":a.requests,"workers":a.workers,"elapsed_ms":round(elapsed,2),"completed":len(lat),"errors":len(errors),"error_types":sorted(set(errors)),"rss_before_mb":before,"rss_after_mb":rss(),"p50_ms":round(sorted(lat)[len(lat)//2],3) if lat else None,"p95_ms":round(sorted(lat)[int(len(lat)*.95)-1],3) if lat else None,"deadlock":len(lat)!=a.requests}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,indent=2),encoding="utf-8"); print(json.dumps(payload,indent=2))
if __name__=="__main__": main()
