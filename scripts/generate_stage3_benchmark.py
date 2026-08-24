#!/usr/bin/env python3
"""Deterministically generate the Stage 3 customer-style corpus and heldout set."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DOMAINS=('finance','healthcare','manufacturing','energy','logistics','education','software','public-sector')
def main():
 corpus=[]
 for i in range(96):
  d=DOMAINS[i%8]; topic=f'control-{i:03d}'; current=f'v{i%17+3}'; prior=f'v{i%17+1}'; code=f'POL-{d[:3].upper()}-{i:03d}'
  text=(f'{d.title()} operations handbook, {code}, revision {current}. The current approved control for {topic} is {current} and requires owner review every {i%9+2} days. This revision supersedes {prior}, which is retained only for audit history and must not be used for current decisions. Operators record evidence in the {d} ledger before closing the control. Exceptions require documented escalation to the duty lead and a linked ticket. This paragraph is intentionally longer and includes procedural context, audit language, and revision history for customer-style retrieval evaluation.')
  corpus.append({'id':f's3-doc-{i:03d}','domain':d,'topic':topic,'revision':current,'text':text})
 cases=[]
 for i in range(360):
  doc=i%96; d=DOMAINS[doc%8]; topic=f'control-{doc:03d}'; current=f'v{doc%17+3}'; uid=f'S3 reference {i:03d}'
  if i%3==0:
   q=f'For the {d} team, what is the approved current revision for {topic}? {uid}'
   kind='revision'; supported=True; req=current
  elif i%3==1:
   q=f'Which control value applies to {topic} in {d} operations, and which revision is current? {uid}'
   kind='factual'; supported=True; req=current
  else:
   fake=f'v{900+i}'; q=f'What is the approved current revision for near-miss control-{doc:03d}-{i:03d} in {d}? {uid}'
   kind='near_miss'; supported=False; req=fake
  cases.append({'id':f's3-{i:03d}','case_type':kind,'domain':d,'question':q,'supported':supported,'required_answer_groups':[[req]],'required_source_terms':[req],'source_doc':f's3-doc-{doc:03d}' if supported else None})
 (ROOT/'data'/'stage3_customer_corpus_v1.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in corpus),encoding='utf-8')
 (ROOT/'evaluation'/'heldout_stage3_customer_v1.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in cases),encoding='utf-8')
 questions=[x['question'] for x in cases]; print(json.dumps({'documents':len(corpus),'cases':len(cases),'duplicate_questions':len(questions)-len(set(questions))}))
if __name__=='__main__': main()
