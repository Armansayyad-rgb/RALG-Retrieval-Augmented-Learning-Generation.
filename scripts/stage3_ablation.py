#!/usr/bin/env python3
"""Record honest semantic-ablation applicability without changing production code."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=ROOT/'logs'/'stage3_ablation.json'); a=p.parse_args()
 cases=sum(1 for x in (ROOT/'evaluation/heldout_stage3_customer_v1.jsonl').read_text(encoding='utf-8').splitlines() if x.strip())
 payload={'dataset':'heldout_stage3_customer_v1','cases':cases,'evaluation_only':True,'not_applicable':{'conflict_gate':'No safe public switch isolates conflict resolution without changing production semantics.','factual_grounding_gate':'No safe public switch isolates factual grounding without changing production semantics.','provenance_handling':'No safe public switch isolates provenance handling without changing production semantics.'},'production_defaults_changed':False}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,indent=2),encoding='utf-8'); print(json.dumps(payload,indent=2))
if __name__=='__main__': main()
