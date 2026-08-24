# Roadmap

RALG is now past its first release-candidate and core hardening phases. The roadmap is focused on turning a strong local technical proof into a reproducible controlled-pilot system with defensible external evidence.

## Completed foundations

- local retrieval and evidence-grounded answer pipeline
- FastAPI service and Gradio web UI
- TXT/PDF/DOCX ingestion
- runtime document persistence and restart recovery
- stable document IDs, provenance, listing, and deletion
- safe abstention and unsupported-question rejection
- conflict and factual-grounding protections
- unified API/UI evidence semantics
- portability and readiness checks
- clean Python 3.11 installation validation
- lightweight Python SDK/client
- postings-based lexical indexing
- V4 duplicate-query reuse and bounded query cache
- incremental runtime indexing
- process-local lifecycle locking
- 100k-scale retrieval validation
- 1000-request / 8-worker soak validation
- CI sanity, benchmark integrity, secret scanning, and Compose validation
- Prototype 1 RC1 preserved at `0.1.0-rc1`

## Completed validation milestones

### Stage 1 — pilot differentiation

- 180-case synthetic held-out benchmark
- lexical vs RALG comparison
- RALG Recall@5 100% vs lexical 93.75% in the recorded run
- unsupported rejection 100% in that harness

### Stage 2 — lifecycle, scale, and reproducibility

- clean Python 3.11 environment
- stable `tokenizers==0.23.1`
- isolated live API ingest/query/list/delete/restart lifecycle
- live SDK integration
- 100k retrieval optimized to approximately 156 ms p50 / 216 ms p95 in the recorded environment
- 250/500/1000-request soak progression with 0 errors at 8 workers

### Stage 3 — customer-style synthetic evaluation

- 360 unique evaluation questions
- 96 synthetic customer-style documents across 8 domains
- 240 supported / 120 unsupported cases
- 0 duplicate questions after generator correction
- lexical and RALG both reached Recall@5 100%, exposing a benchmark ceiling effect rather than proving further retrieval-quality superiority

## Current priority — Stage 4 external-style evidence

The highest-value next step is not another easy synthetic benchmark. Stage 4 should determine whether RALG has a reproducible technical advantage on genuinely difficult retrieval/evidence cases.

### 1. Harder untouched evaluation

Build a new separated evaluation with substantial coverage of:

- paraphrased queries
- high-overlap distractor documents
- similar entity names
- conflicting revisions
- near-miss unsupported questions
- cross-document evidence
- numerical predicate confusion
- terminology variation
- revision/version ambiguity

The benchmark must avoid ceiling effects and must not be tuned to make RALG win.

### 2. Fair baseline comparison

Evaluate identical corpus/questions with at least:

- simple lexical baseline
- current production RALG

Where practical, also compare postings-only and reduced V4 variants.

Report:

- Recall@1/3/5
- MRR
- unsupported rejection
- false-support rate
- provenance/evidence correctness
- p50/p95 latency
- per-category results

### 3. Failure analysis

For each meaningful failure category, classify whether the cause is:

- retrieval/ranking
- entity resolution
- grounding
- conflict resolution
- provenance/source selection
- unsupported rejection

Preserve representative case IDs and do not hide failures behind aggregate scores.

### 4. Semantic ablation evidence

Conflict handling, factual grounding, and provenance-aware handling remain difficult to isolate safely. Add test-only seams only if they can be introduced without weakening production defaults or distorting the architecture.

### 5. Real or permitted technical documents

Synthetic/customer-style evaluation is useful engineering evidence but not customer validation. The next major credibility step is evaluation against permitted real technical documents or an independently sourced external-style corpus.

## Deployment priorities

### Docker runtime validation

Compose configuration is validated, but the recorded development environment did not have a usable Docker daemon for complete lifecycle qualification.

When a Docker-enabled environment is available, validate:

- clean build
- localhost-only host exposure
- health/readiness
- ingest/query/delete
- persistence across restart
- unsupported rejection
- clean shutdown

### Larger-scale validation

100k scale is validated. 250k/500k remain intentionally deferred until a machine with confirmed safe memory headroom is available.

Do not risk host instability merely to obtain larger benchmark numbers.

## Operational boundary

The currently validated pilot configuration is:

- local/trusted environment
- single Uvicorn/application worker
- process-local mutation locking
- no built-in production authentication
- no TLS termination
- no tenant isolation

Do not describe RALG as production multi-tenant infrastructure until those boundaries are deliberately changed and validated.

## Repository / engineering hygiene

Continue to:

- keep model checkpoints outside Git
- keep runtime uploads and coding-agent state untracked
- preserve deterministic benchmark generation
- distinguish measured, previously measured, deferred, and not validated results
- archive obsolete research utilities only after dependency review
- avoid benchmark-specific production logic

## Not a priority yet

- broad consumer chatbot features
- cosmetic UI work without reliability/deployment value
- unsupported superiority claims
- multi-tenant SaaS features before the technical evidence is mature
- large-scale runs that exceed safe local hardware limits

## Target use case

Private technical-document intelligence for manufacturing, maintenance, engineering, operations, and other environments where evidence, provenance, privacy, and conservative unsupported handling matter more than open-ended chat.
