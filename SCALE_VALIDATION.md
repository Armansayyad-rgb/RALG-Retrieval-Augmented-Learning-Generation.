# Stage 2 Scale Validation

`scripts\scalability_benchmark.py` targets 100,000 and 250,000 synthetic
chunks, records optional psutil RSS, p50/p95 query latency, build/query time,
incremental +100/+1000/+5000 updates, delete, and rebuild. 500,000 is opt-in
(`--allow-500k`) to avoid unsafe memory pressure. Run:

```powershell
.venv\Scripts\python.exe scripts\scalability_benchmark.py --levels 100000,250000
```

See `logs\scale_validation.json`; unavailable levels are explicitly marked.
On this host, both requested levels were recorded as `not_run` under the
default 50,000-chunk safety budget; raise `--max-safe-chunks` only on a
representative machine with sufficient RAM.
