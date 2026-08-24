#!/usr/bin/env python3
"""Integrity checks for Stage 4 data: duplicates, overlap, and answer leakage."""
import hashlib, json, re
from difflib import SequenceMatcher
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"[a-z0-9]+")
def norm(s): return " ".join(TOKEN.findall(s.lower()))
def load(path): return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
def main():
    cases = load(ROOT/"evaluation/heldout_stage4_customer_v1.jsonl")
    prior = []
    for p in (ROOT/"evaluation").glob("*.jsonl"):
        if "stage4" not in p.name:
            prior.extend(load(p))
    questions = [norm(x["question"]) for x in cases]
    duplicates = [q for q in set(questions) if questions.count(q) > 1]
    near_duplicates = sum(1 for i, q in enumerate(questions) for other in questions[i+1:]
                          if q != other and SequenceMatcher(None, q, other).ratio() >= .97)
    overlap = sorted(set(questions) & {norm(x.get("question","")) for x in prior})
    leakage = []
    for c in cases:
        q = norm(c["question"])
        q_tokens = q.split()
        for term in c.get("required_source_terms", []):
            if str(term).isdigit():
                continue  # numeric IDs in entity names/case references are not answer leakage
            term_tokens = norm(str(term)).split()
            for start in range(len(q_tokens) - len(term_tokens) + 1):
                if term_tokens and q_tokens[start:start + len(term_tokens)] == term_tokens:
                    leakage.append({"id": c["id"], "term": term})
                    break
    payload = {"cases": len(cases), "duplicate_questions": len(duplicates),
               "near_duplicate_pairs": near_duplicates,
               "overlap_with_prior_benchmarks": len(overlap), "answer_leakage": len(leakage),
               "duplicate_ids": len(cases) - len({x["id"] for x in cases}),
               "sha256": hashlib.sha256((ROOT/"evaluation/heldout_stage4_customer_v1.jsonl").read_bytes()).hexdigest(),
               "pass": not (duplicates or overlap or leakage)}
    (ROOT/"logs"/"stage4_integrity.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["pass"]: raise SystemExit(1)
if __name__ == "__main__": main()
