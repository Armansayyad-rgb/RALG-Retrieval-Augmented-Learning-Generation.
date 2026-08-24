#!/usr/bin/env python3
"""Stage 3 heldout evaluation: lexical baseline versus the current RALG retriever."""
from __future__ import annotations
import argparse,json,re,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.retriever_v2 import build_index,retrieve

def terms(text): return set(re.findall(r"[a-z0-9']+",text.lower()))
def main():
 p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=ROOT/'logs'/'stage3_evaluation.json'); a=p.parse_args()
 docs=[json.loads(x) for x in (ROOT/'data/stage3_customer_corpus_v1.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
 cases=[json.loads(x) for x in (ROOT/'evaluation/heldout_stage3_customer_v1.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
 chunks=[d['text'] for d in docs]; idx,df=build_index(chunks); rows=[]
 for c in cases:
  qterms=terms(c['question']); t=time.perf_counter(); base=sorted(range(len(chunks)),key=lambda i:len(qterms&terms(chunks[i])),reverse=True)[:5]; bms=(time.perf_counter()-t)*1000
  t=time.perf_counter(); ranked=[str(x) for x in retrieve(c['question'],chunks,idx,df,final_top_k=5)]; rms=(time.perf_counter()-t)*1000
  required=[x.lower() for x in c['required_source_terms']]
  bok=bool(c['supported']) and any(all(x in chunks[i].lower() for x in required) for i in base)
  rok=bool(c['supported']) and any(all(x in xtext.lower() for x in required) for xtext in ranked)
  rows.append({'id':c['id'],'case_type':c['case_type'],'supported':c['supported'],'lexical_correct':bok,'ralg_correct':rok,'lexical_ms':bms,'ralg_ms':rms})
 sup=[r for r in rows if r['supported']]; uns=[r for r in rows if not r['supported']]
 metrics={'dataset':'heldout_stage3_customer_v1','cases':len(rows),'supported_cases':len(sup),'unsupported_cases':len(uns),'domains':len(set(c['domain'] for c in cases)),'lexical_recall_at_5':sum(r['lexical_correct'] for r in sup)/len(sup),'ralg_recall_at_5':sum(r['ralg_correct'] for r in sup)/len(sup),'lexical_near_miss_false_support_rate':sum(r['lexical_correct'] for r in uns)/len(uns),'ralg_near_miss_false_support_rate':sum(r['ralg_correct'] for r in uns)/len(uns),'lexical_rejection_rate':1-sum(r['lexical_correct'] for r in uns)/len(uns),'ralg_rejection_rate':1-sum(r['ralg_correct'] for r in uns)/len(uns),'lexical_p50_ms':statistics.median(r['lexical_ms'] for r in rows),'ralg_p50_ms':statistics.median(r['ralg_ms'] for r in rows),'lexical_p95_ms':sorted(r['lexical_ms'] for r in rows)[int(len(rows)*.95)-1],'ralg_p95_ms':sorted(r['ralg_ms'] for r in rows)[int(len(rows)*.95)-1]}
 payload={'metrics':metrics,'results':rows}; a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,indent=2),encoding='utf-8'); print(json.dumps(metrics,indent=2))
if __name__=='__main__': main()
