# Stage 2 Ablation Results

Run `.venv\Scripts\python.exe scripts\run_ablation.py`; authoritative output is
`logs\ablation_results.json`. The harness uses explicit seams and leaves
production defaults and fixtures unchanged.

Observed 96-case synthetic run (supported and unsupported cases):

| Variant | R@1 | R@3 | R@5 | MRR | rejection | false support | evidence | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| production | .0375 | .7375 | .8125 | .3981 | 1.00 | 0 | 1.00 | 3.485 | 5.140 |
| no postings optimization | .0375 | .7375 | .8125 | .3981 | 1.00 | 0 | 1.00 | 3.422 | 3.782 |
| no runtime boost | .6625 | .7375 | .8125 | .7106 | 1.00 | 0 | 1.00 | 4.186 | 4.809 |
| V4 expansion | .6625 | .7375 | .8125 | .7106 | 1.00 | 0 | 1.00 | 6.882 | 7.693 |
| no V4 expansion | .6625 | .7375 | .8125 | .7106 | 1.00 | 0 | 1.00 | 3.498 | 3.995 |
| no duplicate-query reuse | .6625 | .7375 | .8125 | .7106 | 1.00 | 0 | 1.00 | 6.832 | 7.637 |

Conflict, factual-grounding, and provenance gates remain **N/A**: no safe
public switch exists to isolate them without changing production semantics.
