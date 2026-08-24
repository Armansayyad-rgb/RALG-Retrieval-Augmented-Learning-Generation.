# Stage 3 Pilot Readiness Evidence

Additive evidence for branch `pilot/pilot-hardening-v3`; no commit or push was performed.

## Inventory

- New customer-style corpus: `data/stage3_customer_corpus_v1.jsonl` — **96 documents** across 8 domains.
- New heldout set: `evaluation/heldout_stage3_customer_v1.jsonl` — **360 cases**: 240 supported (revision/factual) and 120 unsupported near misses.
- The generator adds a deterministic case reference to every question; duplicate-question count after regeneration is **0**.
- Every document contains longer procedural context and an explicit current revision superseding a prior revision; cases are distinct from Stage 2 fixtures.
- New runners: `scripts/generate_stage3_benchmark.py`, `scripts/stage3_evaluation.py`, and `scripts/stage3_ablation.py`.

## Results

Command:

```powershell
.venv\Scripts\python.exe scripts\stage3_evaluation.py
```

Observed after regeneration: lexical and current RALG retrieval both reached recall@5 **1.00**, near-miss false-support **0.00**, and rejection **1.00**. Lexical p50/p95 latency was **0.986/1.201 ms**; RALG was **0.305/0.420 ms** on this machine. This is retrieval evidence, not generated-answer quality.

## Semantic ablation boundary

`stage3_ablation.py` records conflict, factual-grounding, and provenance gates as **N/A**: no safe public switch isolates these behaviors without changing production semantics. It confirms production defaults were unchanged. No causal ablation claim is made.

## Stage 2 evidence carried forward

Stage 2 reports document clean-install lifecycle, live API and Python SDK checks, persistence/provenance behavior, bounded scale/soak results, and known limitations. The measured 100k scale run and bounded 250/500/1000-request soak are accepted as known results; unvalidated larger/16-worker windows remain unavailable rather than passes. A single application worker remains the deployment guidance.

## Environment and security

Docker CLI is installed, but the daemon is unavailable (`docker info` cannot connect), so Docker validation is **unavailable**. Clean-install and live API/SDK evidence remains from Stage 2. The benchmark uses synthetic data only. Runtime uploads, model/tokenizer/checkpoint binaries, `.opencode/`, existing fixtures/thresholds, and `0.1.0-rc1` were not modified. Production defaults and security boundaries are unchanged; uploaded documents remain runtime-scoped and provenance is not upgraded into authorization.

## Reproduction

```powershell
.venv\Scripts\python.exe scripts\generate_stage3_benchmark.py
.venv\Scripts\python.exe scripts\stage3_evaluation.py
.venv\Scripts\python.exe scripts\stage3_ablation.py
```
