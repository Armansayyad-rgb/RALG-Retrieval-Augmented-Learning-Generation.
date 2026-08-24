# Stage 2 Ablation Results

Run ` .venv\Scripts\python.exe scripts\run_ablation.py` to regenerate
`logs\ablation_results.json`. The harness measures distinct retrieval paths for
postings optimization and runtime boost. Duplicate reuse, V4 expansion,
conflict gate, factual grounding gate, and provenance handling are reported
**not applicable** because production exposes no safe feature switches; no
monkey-patching or synthetic substitute is used.

Results are machine-dependent and the generated JSON is authoritative.

Observed run: production recall 0.8875 (mean 3.672 ms), no-postings recall
0.8875 (3.447 ms), and no-runtime-boost recall 0.8125 (7.896 ms).
