# Stage 2 Scale Validation

`scripts\scalability_benchmark.py` targets 100,000 and 250,000 synthetic
chunks, records optional psutil RSS, p50/p95 query latency, build/query time,
incremental +100/+1000/+5000 updates, delete, and rebuild. 500,000 is opt-in
(`--allow-500k`) to avoid unsafe memory pressure. Run:

```powershell
.venv\Scripts\python.exe scripts\scalability_benchmark.py --levels 100000,250000
```

See `logs\scale_validation.json`; unavailable levels are explicitly marked.
On this host, 100,000 chunks completed safely. Before the scoring fix, RSS
rose from 395.32 MB to 639.37 MB with 575.88 ms index build time, 1,455.817
ms query p50, and 1,523.975 ms query p95. After replacing per-term scalar
Torch logarithms with the equivalent standard-library calculation, RSS was
395.78 MB to 636.94 MB, build time was 715.25 ms, query p50 was 156.186 ms,
and p95 was 215.893 ms. Incremental indexing took 0.29/3.01/13.43 ms for
+100/+1000/+5000 chunks; deletion followed by rebuild took 723.33 ms.
250,000 and 500,000 were not validated because the run was intentionally
stopped after the first large level to avoid unsafe memory pressure.
