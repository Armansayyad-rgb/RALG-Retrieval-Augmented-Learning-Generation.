# RALG Resource and Scale Validation Report

**Pilot-Readiness Checkpoint: Resource and Scale Validation**

## Objective

Measure practical RAM/VRAM usage, initialization cost, ingestion/reindex cost, retrieval latency, and end-to-end query latency as runtime corpus size grows. This report separates a small retriever microbenchmark from the full RALG runtime and derives pilot guidance only from the full-runtime measurements.

## Runtime environment

| Property | Value |
|---|---|
| Python | 3.11.0 |
| Torch | 2.7.1+cu128 |
| CUDA available | Yes |
| CUDA runtime | 12.8 |
| cuDNN | 90701 |
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU |
| GPU VRAM | 6.00 GB |
| Pipeline device | cuda |
| Configured knowledge files | `data/wikitext_v2.txt`, `data/knowledge_extra_v1.txt` |
| Model loaded | Yes |

## A. Retriever microbenchmark

This section is a controlled small-corpus complexity experiment. It is **not** used to set pilot limits.

| Corpus size | Retrieval p50 | Retrieval p95 |
|---:|---:|---:|
| 41 chunks | 0.2 ms | 0.4 ms |
| 141 chunks | measured during scale run | measured during scale run |
| 1,141 chunks | measured during scale run | measured during scale run |
| 6,141 chunks | 104.6 ms | 195.8 ms |

Additional baseline microbenchmark end-to-end latency: p50 **1.1 ms**, p95 **6.6 ms**.

The microbenchmark shows the expected growth of the current lexical retrieval path as corpus size increases, but it does not represent the model-backed production pipeline.

## B. Full RALG runtime validation

### Baseline initialization

| Metric | Value |
|---|---:|
| Baseline chunk count | 107,650 |
| Initialization time | 7.778 s |
| RAM delta during initialization | +963.2 MB |
| CUDA allocated VRAM | 219.7 MB |
| CUDA reserved VRAM | 474.0 MB |

### Query and retrieval latency

The full-runtime run used the actual configured knowledge corpus and model-backed pipeline.

| Scale | Total corpus | Retrieval p50 | Retrieval p95 | Total p50 | Total p95 |
|---|---:|---:|---:|---:|---:|
| Baseline | 107,650 | 671.9 ms | 3,602.5 ms | 697.7 ms | 3,622.7 ms |
| +100 | 107,750 | 972.7 ms | 4,962.1 ms | 924.6 ms | 4,910.2 ms |
| +1,000 | 108,650 | 749.7 ms | 4,206.4 ms | 762.0 ms | 4,055.5 ms |
| +5,000 | 112,650 | 1,009.9 ms | 5,683.2 ms | 1,017.9 ms | 5,073.4 ms |

Tail latency is variable across runs, so these numbers should be treated as measured observations for this machine rather than deterministic guarantees. The dominant full-runtime bottleneck is retrieval/model-backed query latency at the ~108k-chunk baseline, not the relatively small runtime-ingestion increments.

### Runtime ingestion and full-index rebuild

Runtime ingestion was exercised through the normal attachment path. `attach_documents()` calls `build_index_v2`, so each measured ingestion triggers a full lexical-index rebuild over the current corpus.

| Runtime chunks added | Total corpus | Rebuild elapsed |
|---:|---:|---:|
| +100 | 107,750 | 4.143 s |
| +1,000 | 108,650 | 3.553 s |
| +5,000 | 112,650 | 4.601 s |

The rebuild time remains in the low-single-digit seconds on this machine across the tested range. These measurements should not be extrapolated linearly to substantially larger corpora without additional testing.

### Memory behavior

The measured query windows showed small process-RAM changes and stable GPU memory. Retained chunk/index memory is expected state, not a memory leak.

No unexpected continued memory growth was observed in the measured query windows. Long-duration soak behavior remains untested.

## C. Confirmed bottlenecks

1. **Full-runtime retrieval tail latency.** Retrieval p95 is several seconds at all tested full-runtime scales.
2. **O(N)-style lexical retrieval.** The controlled microbenchmark shows increasing retrieval cost as corpus size grows.
3. **Full-index rebuild on runtime ingestion.** Each ingestion rebuilds the complete V2 lexical index, taking approximately 3.5–4.6 seconds in the tested full-runtime range.

No RAM or VRAM exhaustion was observed within the tested scales.

## D. Recommended pilot limits

For the measured single-process Windows/CUDA environment, use a conservative default of:

- **Runtime-ingestion limit:** up to **+1,000 chunks** per pilot instance.
- **Baseline corpus:** approximately **107,650 chunks**.
- **+5,000 chunks:** successfully tested, but **not** the default pilot recommendation until concurrency and soak testing are completed.

The +1,000 recommendation is operationally conservative; it is not claimed as a hard maximum. The +5,000 result establishes that the larger scale can run on the tested machine, but not that it is production-safe under concurrent or long-duration load.

No pilot limit is derived from the 41-chunk microbenchmark.

## E. Untested / unknown

- Concurrent multi-user query performance.
- Sustained multi-user latency at +5,000 runtime chunks.
- Long-duration soak and repeated-ingestion behavior.
- Performance on different GPU classes.
- CPU-only pilot behavior under the same full-runtime workload.
- Scaling substantially beyond the tested +5,000 runtime chunks.

## Validation

The resource/scale checkpoint was followed by the existing project validation stack:

- Python compile checks: **PASS**
- `scripts/test_all.bat`: **PASS**
- regression suite: **23/23 PASS**
- commercial validation quality gate: **PASS**
- traceability tests: **7/7 PASS**
- conflict-detection tests: **9/9 PASS**
- API input-hardening tests: **7/7 PASS**
- `git diff --check`: **PASS**

## Interpretation

These measurements are evidence for a controlled Prototype 1 / pilot environment, not a claim of production scalability. The immediate scaling priority is improving or replacing the current full-corpus retrieval path before substantially increasing corpus size or introducing concurrent users.
