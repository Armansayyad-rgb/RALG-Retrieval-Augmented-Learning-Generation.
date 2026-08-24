# Pilot Readiness Report V2 — Stage 2 Evidence

This is an additive, synthetic engineering evidence package. It does not
modify `.opencode/`, runtime uploads, checkpoints/tokenizers, benchmark
fixtures, or release artifacts.

## Reproduction

```powershell
.venv\Scripts\python.exe scripts\heldout_evaluation_v2.py
.venv\Scripts\python.exe scripts\run_ablation.py
.venv\Scripts\python.exe scripts\scalability_benchmark.py --levels 100000,250000
.venv\Scripts\python.exe scripts\concurrency_soak.py --requests 1000 --workers 16
.venv\Scripts\python.exe scripts\deployment_validation.py
```

## Evidence and limitations

The independent held-out benchmark contains 320 generated cases across eight
domains, longer documents, revisions/conflicts, and unsupported near-miss
queries. Scale and soak results include RSS where psutil is installed and are
machine-dependent. All measured values are in `logs/`; unavailable API,
clean-install, or unsafe scale checks remain explicitly unavailable.

The held-out harness is retrieval-only and does not establish model-backed
answer quality. Human review remains required for safety-critical use.

Observed held-out run: 320 cases, 1.00 supported recall@5, 0.00 near-miss
false-support rate, p50 1.270 ms, p95 1.799 ms. The 100k level was subsequently completed safely: RSS 395.32 MB to 639.37 MB,
575.88 ms build, 1,455.817 ms query p50, and 1,523.975 ms query p95.
250k/500k remain not validated because the run was stopped after the first
large level to avoid unsafe memory pressure.
The 1000-query/16-worker soak was bounded and did not complete within the
available run window; treat concurrency evidence as unavailable, not as a pass.
