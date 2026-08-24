# Pilot readiness evidence report

**Scope.** This package is a reproducible, synthetic engineering checkpoint for
`0.1.0-rc1`; it is not customer-data validation and does not tune production
rules to the benchmark.

## Evidence

- `data/pilot_customer_corpus_v1.jsonl`: 14 safe synthetic documents across six
  domains, including superseded versions and explicitly conflicting drafts.
- `evaluation/heldout_pilot_v1.jsonl`: 180 deterministic held-out cases
  (seed 3817), separate from existing fixtures; 144 supported and 36
  unsupported cases.
- `scripts/heldout_evaluation.py`: lexical baseline versus current RALG
  retrieval; `scripts/run_ablation.py` records the no-tuning comparison.
- `scripts/scalability_benchmark.py`: bounded levels by default; 100k/250k/500k
  can be selected with `--levels`, subject to available RAM.
- `scripts/concurrency_soak.py`: deterministic threaded retrieval smoke.

## Reproduction

```powershell
python scripts\generate_pilot_evidence.py
python scripts\heldout_evaluation.py
python scripts\run_ablation.py
python scripts\scalability_benchmark.py
python scripts\concurrency_soak.py
```

Measured JSON is written under `logs/`. Values are machine-dependent and must
be reported from the generated files, not copied as universal claims.

The measured run in this workspace produced RALG Recall@5 **1.00** (144/144
supported cases) versus lexical baseline **0.9375**; mean retrieval timings
were **0.194 ms** and **0.083 ms**, respectively. Both retrieval-only paths
rejected all 36 unsupported cases in this harness (false-support rate **0**).
The bounded scale probe measured 1k/5k/10k chunks at approximately
3.40/16.94/64.52 ms index build and 15.67/70.00/143.97 ms query. The
100-request, 8-worker soak completed with zero errors in 6.84 s.

## Availability and risks

This environment did not provide a clean Docker daemon or representative
customer hardware, so Docker startup, peak RAM/VRAM, and 100k/250k/500k
measurements are **unavailable/not release-gated here**. Model-backed API
latency is likewise not claimed by this package. Human review remains required
for safety-critical decisions; synthetic results do not establish production
accuracy, security, or domain suitability.
