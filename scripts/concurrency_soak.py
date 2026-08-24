#!/usr/bin/env python3
"""Small deterministic threaded retrieval soak against an in-memory index."""
from concurrent.futures import ThreadPoolExecutor
import argparse,json,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.retriever_v2 import build_index,retrieve
def main():
 p=argparse.ArgumentParser(); p.add_argument("--requests",type=int,default=100); p.add_argument("--workers",type=int,default=8); a=p.parse_args()
 chunks=[f"soak document {i} control alpha value {i%9}" for i in range(1000)]; idx,df=build_index(chunks)
 def one(i): retrieve(f"control alpha value {i%9}",chunks,idx,df)
 t=time.perf_counter()
 with ThreadPoolExecutor(max_workers=a.workers) as ex: list(ex.map(one,range(a.requests)))
 print(json.dumps({"requests":a.requests,"workers":a.workers,"elapsed_ms":round((time.perf_counter()-t)*1000,2),"errors":0}))
if __name__=="__main__": main()
