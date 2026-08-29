# Roadmap

RALG is past its first release-candidate and initial pilot-validation phases. The project now has enough evidence to distinguish engineering strengths from architectural gaps, so the roadmap is shifting from "add more benchmarks" to "complete the intended compound runtime, then revalidate externally."

## Completed foundations

- local retrieval and evidence-grounded answer pipeline
- FastAPI service and Gradio web UI
- TXT/PDF/DOCX ingestion
- runtime document persistence and restart recovery
- stable document IDs, provenance, listing, and deletion
- safe abstention and unsupported-question rejection
- conflict and factual-grounding protections
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
- lexical and RALG both reached Recall@5 100%, exposing a benchmark ceiling effect

### Stage 4 — external-style synthetic evaluation

- 600-case benchmark over 120 synthetic technical documents
- 480 supported / 120 unsupported
- RALG Recall@1 100% vs lexical 96.875%
- both reached Recall@5 100%, so differentiation was primarily rank-1 rather than deeper retrieval
- adversarial unsupported set retained 0 false support in the recorded harness

### Stage 5 — independently sourced RFC evidence

- 50 independently sourced IETF RFC documents
- provenance manifest and SHA-256 integrity validation
- 300-case preliminary benchmark, 210 supported / 90 unsupported
- blinded review pack and deterministic 75-case pilot-review sample
- corpus-integrity controls added to CI

Preliminary untouched Stage 5 retrieval results currently favor the lexical baseline (**HISTORICAL — pre-hybrid implementation**):

- lexical Recall@1/3/5: 40.48% / 87.62% / 100.00%
- RALG Recall@1/3/5: 37.14% / 77.62% / 92.86%
- lexical MRR: 0.6485
- RALG MRR: 0.5863
- unsupported rejection: 100% for both
- false-support rate: 0% for both
- RALG retrieval latency was substantially lower in the recorded harness

The 300 cases remain automatically generated and unreviewed. Stage 5 therefore remains **BLOCKED ON INDEPENDENT REVIEW** and is not final external validation.

## Current priority — core architecture completion

The architecture audit estimates the original compound RALG design at approximately **70% integrated**. The next build should complete the runtime architecture before any benchmark-specific retrieval tuning.

### 1. One authoritative execution plan

Replace duplicate routing responsibility between planning logic and `router_v1` with one execution plan that owns:

- query classification
- factual/comparison/reasoning route
- retrieval strategy
- multi-hop decision
- evidence selection
- support adjudication
- generation/extraction
- abstention
- provenance

### 2. Unified answer-level support gate

Consolidate retrieval confidence, premise validation, evidence sufficiency, factual predicates, conflict detection, and traceability into one authoritative supported/unsupported decision.

A `supported=true` answer must have identifiable supporting evidence.

### 3. Explicit model registry

Classify every trained artifact as active, compatible-but-unused, superseded, historical, or incompatible. Map serving configuration to the exact model/tokenizer artifacts used by runtime instead of leaving training outputs disconnected from production.

### 4. Stronger multi-hop state

Move beyond connector-pattern decomposition toward explicit:

```text
question
-> subquestions
-> evidence per subquestion
-> supported intermediate facts
-> final evidence set
-> answer/support decision
```

Every intermediate fact used by the final answer should remain traceable.

### 5. API/UI parity

Make API and Web UI use the same grounded core execution pipeline. Any unconstrained/pure-generative mode should be explicit and separate from normal grounded RALG behavior.

See [Current Architecture Status](docs/CURRENT_ARCHITECTURE_STATUS.md).

## Validation after architecture completion

After the architecture consolidation is complete and existing gates pass:

1. rerun regression and commercial validation
2. rerun Stage 4 without modifying its fixtures
3. rerun the untouched Stage 5 preliminary evaluation
4. compare retrieval, support, false-support, provenance, and latency changes
5. document whether improvements generalize rather than benefiting individual case IDs
6. keep independent human review explicitly pending until a real reviewer exists

Do not tune production logic directly to Stage 5 expected answers or failure IDs.

## Deployment priorities

### Docker runtime validation

Compose configuration is validated, but full container lifecycle qualification remains outstanding in the recorded evidence.

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
- keep negative benchmark evidence visible
- archive obsolete research utilities only after dependency/reproducibility review
- avoid benchmark-specific production logic
- keep acquisition/pilot claims tied to reproducible evidence

## Commercial-readiness priorities

For a fast strategic-sale or pilot path, the highest-value technical work is:

1. architecture completion and runtime coherence
2. independent-document retrieval-quality recovery without overfitting
3. one-command reproducible deployment
4. concise technical due-diligence package
5. real external/pilot evidence when available

Broad feature expansion and cosmetic UI work are lower priority than these items.

## Target use case

Private technical-document intelligence for manufacturing, maintenance, engineering, operations, cybersecurity, and other environments where evidence, provenance, privacy, and conservative unsupported handling matter more than open-ended chat.
