# Stage 2 Scale Validation

`scripts\scalability_benchmark.py` targets 100,000 and 250,000 synthetic
chunks, records optional psutil RSS, p50/p95 query latency, build/query time,
incremental +100/+1000/+5000 updates, delete, and rebuild. 500,000 is opt-in
(`--allow-500k`) to avoid unsafe memory pressure. Run:

```powershell
.venv\Scripts\python.exe scripts\scalability_benchmark.py --levels 100000,250000
```

See `logs\scale_validation.json`; unavailable levels are explicitly marked.
On this host, 100,000 chunks completed safely with RSS rising from 395.32 MB
to 639.37 MB, 575.88 ms index build time, 1,455.817 ms query p50, and
1,523.975 ms query p95. Incremental indexing took 0.32/3.23/12.55 ms for
+100/+1000/+5000 chunks; deletion followed by rebuild took 700.94 ms.
250,000 and 500,000 were not validated because the run was intentionally
stopped after the first large level to avoid unsafe memory pressure.
