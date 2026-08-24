#!/usr/bin/env python3
"""Render the machine-readable Stage 4 results as an auditable report."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def main():
    ev = json.loads((ROOT/"logs"/"stage4_evaluation.json").read_text(encoding="utf-8"))
    integrity = json.loads((ROOT/"logs"/"stage4_integrity.json").read_text(encoding="utf-8"))
    lines = ["# Stage 4 Evidence Package", "", "Additive synthetic evidence; no production benchmark tuning, commit, or push.",
             "", "## Inventory", "- 120 deterministic customer-style documents.",
             f"- {ev['cases']} held-out cases, including 100 adversarial false-support probes.",
             "", "## Integrity", f"- pass: **{integrity['pass']}**; duplicates: {integrity['duplicate_questions']}; "
             f"near-duplicate pairs: {integrity['near_duplicate_pairs']}; prior overlap: {integrity['overlap_with_prior_benchmarks']}; "
             f"answer leakage: {integrity['answer_leakage']}.", "", "## Retrieval results"]
    for name, data in ev["systems"].items():
        m = data["metrics"]; lines.append(f"- **{name}**: Recall@1/3/5 {m['recall_at_1']:.3f}/{m['recall_at_3']:.3f}/{m['recall_at_5']:.3f}; "
            f"MRR {m['mrr']:.3f}; unsupported rejection {m['unsupported_rejection']:.3f}; false support {m['false_support']:.3f}; "
            f"evidence correctness {m['evidence_correctness']:.3f}; p50/p95 {m['p50_ms']:.3f}/{m['p95_ms']:.3f} ms.")
    lex = ev["systems"]["lexical"]["rows"]
    examples = [r["id"] for r in lex if r["supported"] and (r["rank"] or 99) > 1][:5]
    false_support = [r["id"] for r in lex if not r["supported"] and r["rank"] is not None][:5]
    lines += ["", "## Semantic ablations", "Conflict, factual-grounding, and provenance ablations are N/A: no safe public seams isolate them.",
              "", "## Failure analysis",
              f"Lexical rank-not-1 representative IDs: {', '.join(examples) or 'none'}.",
              f"False-support representative IDs: {', '.join(false_support) or 'none'}.",
              "Full per-case rows and timings are retained in `logs/stage4_evaluation.json`."]
    (ROOT/"STAGE4_EVIDENCE_REPORT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
if __name__ == "__main__": main()
