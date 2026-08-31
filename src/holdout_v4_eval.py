#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import sys
import time
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
V4 = ROOT / "evaluation" / "holdout_v4"
BENCH = V4 / "holdout_v4_benchmark.jsonl"
MANIFEST = V4 / "holdout_v4_manifest.json"
SOURCES = V4 / "sources" / "normalized"
RESULT = ROOT / "evaluation" / "results" / "holdout_v4_blind_once.json"

sys.path.insert(0, str(ROOT / "src"))

PRIMARY = {"supported_factual","paraphrased_supported","procedural","causal","cross_document","document_scoped"}
REJECTION = {"unsupported","false_premise","misleading_overlap"}
CONFLICT = {"conflicting_evidence"}
QUALIFIED = {"conditional_or_qualified"}


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(k, n, z=1.96):
    if not n: return [0.0, 0.0]
    p = k/n; d = 1+z*z/n
    c = (p+z*z/(2*n))/d
    s = z*math.sqrt((p*(1-p)/n)+(z*z/(4*n*n)))/d
    return [max(0.0,c-s), min(1.0,c+s)]


def verify_manifest():
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for rel, expected in m["artifacts"].items():
        p = ROOT / rel
        if not p.exists() or sha(p) != expected:
            raise RuntimeError(f"freeze hash mismatch: {rel}")
    return m


def build_pipeline():
    from retriever_v2 import RuntimeChunk, build_index, load_chunks
    chunks=[]
    for sf in sorted(SOURCES.glob("*.txt")):
        for c in load_chunks(sf):
            chunks.append(RuntimeChunk(c, metadata={"document_id": sf.stem}))
    index, df = build_index(chunks)
    return {"device":None,"tokenizer":None,"model":None,"chunks":chunks,"retrieval_index":index,"document_frequency":df,"uploaded_docs":[],"runtime_persistence":False,"runtime_upload_dir":None}


def retrieved_ids(execution_result):
    ids=[]
    for s in execution_result.sources or []:
        if isinstance(s,dict):
            d=s.get("document_id") or s.get("id")
            if d: ids.append(d)
    return ids


def retrieval_metrics(ids, relevant, k):
    relevant=set(relevant); top=ids[:k]
    if not relevant: return (None,None,None)
    found=set(d for d in top if d in relevant)
    recall=len(found)/len(relevant)
    hit=1 if found else 0
    rank=next((i+1 for i,d in enumerate(top) if d in relevant),None)
    return recall,hit,(1/rank if rank else 0.0)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--execute-frozen-blind-run",action="store_true")
    args=ap.parse_args()
    if not args.execute_frozen_blind_run:
        raise SystemExit("V4 execution blocked. Use --execute-frozen-blind-run only for the single official run after freeze verification.")
    if RESULT.exists():
        raise SystemExit(f"official result already exists: {RESULT}; refusing overwrite/rerun")
    m=verify_manifest()
    cases=read_jsonl(BENCH)
    if len(cases)!=160: raise SystemExit("benchmark must contain exactly 160 cases")

    from runtime_architecture import execute_runtime
    from rag_chat_v2 import answer_question
    from webui.chat_handler import build_answer_contract, collect_sources

    pipeline=build_pipeline()
    rows=[]; retrieval=defaultdict(list); errors=0
    machine={"primary_supported":0,"primary_rejected":0,"rejection_correct":0,"rejection_false_support":0,"conflict_supported":0,"conflict_rejected":0,"qualified_supported":0,"qualified_rejected":0}
    t_all=time.time()

    for case in cases:
        try:
            scope=case.get("document_scope") or None
            t0=time.time()
            r=execute_runtime(pipeline,case["question"],top_k=5,answer_fn=answer_question,contract_fn=build_answer_contract,sources_fn=collect_sources,document_ids=scope)
            ids=retrieved_ids(r)
            if case["category"] not in REJECTION:
                for k in (1,3,5):
                    rec,hit,mrr=retrieval_metrics(ids,case.get("relevant_document_ids",[]),k)
                    retrieval[f"recall@{k}"].append(rec); retrieval[f"hit@{k}"].append(hit)
                    if k==5: retrieval["mrr"].append(mrr)
            supported=bool(r.supported)
            cat=case["category"]
            if cat in PRIMARY:
                machine["primary_supported" if supported else "primary_rejected"]+=1
            elif cat in REJECTION:
                machine["rejection_false_support" if supported else "rejection_correct"]+=1
            elif cat in CONFLICT:
                machine["conflict_supported" if supported else "conflict_rejected"]+=1
            elif cat in QUALIFIED:
                machine["qualified_supported" if supported else "qualified_rejected"]+=1
            rows.append({"case_id":case["case_id"],"category":cat,"question":case["question"],"supported":supported,"answer":r.answer,"answer_type":r.answer_type,"sources":r.sources,"retrieved_document_ids":ids,"latency_ms":round((time.time()-t0)*1000,3),"human_adjudication_required":cat not in REJECTION})
        except Exception as e:
            errors+=1
            rows.append({"case_id":case["case_id"],"category":case["category"],"runtime_error":type(e).__name__,"human_adjudication_required":True})

    ret={}
    for key,vals in retrieval.items():
        vals=[v for v in vals if v is not None]
        ret[key]=sum(vals)/len(vals) if vals else 0.0
    ret["hit@1_ci95"]=wilson(sum(retrieval["hit@1"]),len(retrieval["hit@1"]))
    ret["hit@3_ci95"]=wilson(sum(retrieval["hit@3"]),len(retrieval["hit@3"]))
    ret["hit@5_ci95"]=wilson(sum(retrieval["hit@5"]),len(retrieval["hit@5"]))

    result={"benchmark_version":"holdout_v4.0.0","run_status":"complete","methodology":"production_execute_runtime_single_shot_blind","target_code_commit_sha":m["target_code_commit_sha"],"total_cases":160,"completed_cases":160-errors,"error_cases":errors,"denominators":m["denominators"],"retrieval_metrics":ret,"machine_support_gate_counts":machine,"machine_scoring_note":"Supported-answer semantic correctness, conflict resolution correctness, qualification preservation, and evidence traceability require blinded human adjudication under PROTOCOL.md; this artifact does not auto-claim those answers correct.","elapsed_seconds":round(time.time()-t_all,3),"cases":rows}
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    RESULT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"OFFICIAL V4 RESULT WRITTEN ONCE: {RESULT}")
    print(f"sha256={sha(RESULT)}")

if __name__=="__main__":
    main()
