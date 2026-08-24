# Retrieval Performance Validation

Prototype 1 performance checkpoint for the configured 107,650-chunk corpus.
Historical `RESOURCE_VALIDATION.md` was not overwritten.

## Environment and methodology

Python 3.11.0, Torch 2.7.1+cu128, CUDA 12.8, NVIDIA GeForce RTX 3050
6 GB, pipeline on CUDA. The resource validator used six representative
queries, one warmup in quick mode, and measured retrieval separately from
end-to-end query latency. The full post-change run used an isolated upload
directory and the same nominal static corpus size. Raw measurements are in
`logs/resource_validation_20260824_111115.json`; the comparable retrieval
micro-run used 18 warmed iterations over the six queries.

## Before / after

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Retrieval p50 (full runtime) | 1,005.7 ms | 49.4 ms | -95.1% |
| Retrieval p95 (full runtime) | 1,403.7 ms | 271.9 ms | -80.6% |
| Total query p50 | 1,002.1 ms | 53.5 ms | -94.7% |
| Total query p95 | 1,468.9 ms | 273.8 ms | -81.4% |
| Average retrieval (comparable 18-run micro-run) | 110.0 ms | 37.4 ms | -66.0% |
| Average total query (18-run post-change run) | not captured | 95.5 ms | n/a |
| +100 ingestion/reindex | 3.610 s | 0.004 s | -99.9% |
| +1,000 ingestion/reindex | 3.553 s | 0.019 s | -99.5% |
| +5,000 ingestion/reindex | 4.601 s | 0.078 s | -98.3% |

The before full-runtime values are the prior validated measurements at
107,650 chunks. The after full-runtime run measured 107,650, 107,750,
108,659, and 112,748 chunks for baseline, +100, +1,000, and +5,000 cases;
runtime additions accumulate in the validator, so those rows are not claims
that different corpus sizes are identical. The comparable retrieval run
measured both algorithms against the same 107,650-chunk corpus in one
process.

Initialization after the index change was 9.099 s with a +1,054.4 MB RSS
delta, versus the fresh pre-change quick run’s 7.843 s and +980.5 MB. The
postings index contained 155,245 unique terms and 6,694,607 posting pairs;
shallow Python container sizes were 65.3 MiB for posting lists and 3.7 MiB
for the postings dictionary (not including referenced integer objects).
The additional postings memory is included in the process delta. GPU
allocation remained 219.7 MB (474.0 MB reserved).

## Confirmed bottlenecks and architecture

The pre-change bottleneck was full-corpus V2 lexical scoring for every query
and repeated scans for V4 variants. V2 now builds a `LexicalIndex` containing
the existing per-chunk `Counter` entries plus an exact `term -> chunk IDs`
postings map. Candidate IDs are the sorted union of query-term postings and
runtime chunks (the latter preserves the exact fixed ingestion boost).
Scoring, factual bonuses, reranking, deterministic tie-breaking, and
provenance remain unchanged.

V4 now reuses results for normalized duplicate variants within one retrieval
call while still merging the evidence for each planned variant. Query term
normalization is bounded by a 1,024-entry in-process cache and contains no
document data, so uploads/deletions do not require invalidation.

Runtime attachment extends postings and document frequency in O(new chunks).
Deletion rebuilds the compact index in O(N), preserving static chunks,
remaining runtime documents, IDs, and persistence recovery.

## Retrieval passes and quality

Normal evidence-bearing API/UI paths continue to format the exact evidence
attached by `answer_question`; fallback retrieval is only used for legacy
results without evidence. V4 profiling showed duplicate normalized variants
served from cache, while meaningful multi-query variants still execute.
Single-hop queries remain one algorithmic V4 sequence; genuine multi-hop
queries retain the second hop.

The focused retrieval, upload, persistence, and unified-evidence tests passed.
The existing quality/regression gates must be run with the full validation
commands before release; benchmark fixtures were not modified or weakened.

## Limitations

This remains a local in-process exact lexical index. Postings memory grows
with the number of unique term occurrences, deletion remains a full rebuild,
concurrent mutation/query synchronization is not a broad redesign, and
long-duration soak, multi-user concurrency, and corpora substantially beyond
the tested +5,000 runtime chunks remain unmeasured.
