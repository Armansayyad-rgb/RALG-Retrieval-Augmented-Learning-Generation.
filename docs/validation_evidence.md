# Validation & Evidence Index

This page organizes RALG's engineering evidence so current results are not confused with historical, synthetic, development, or future validation work.

## Current status

The current repository state is suitable for controlled technical evaluation in a trusted environment. It is not a claim of public production readiness, customer validation, revenue, or safety certification.

Current high-value checkpoints include:

- Prototype 1 RC1 preserved at tag `0.1.0-rc1`;
- unified grounded API/WebUI execution;
- document-scoped retrieval and safe invalid-scope behavior;
- persistent runtime document lifecycle with provenance and restart recovery;
- support-gate hardening against misleading overlap and unsupported factual claims;
- portability cleanup and third-party notices;
- reproducible frozen holdout tooling;
- a preserved single-shot blind Holdout V2 result;
- generalized post-blind regression fixes without rewriting the original Holdout V2 result.

## Evidence interpretation hierarchy

| Evidence | Interpretation |
| --- | --- |
| Development/regression suites | Engineering feedback; may inform production changes |
| Historical/synthetic evaluations | Useful for regression/history, not external validation |
| Frozen independent holdouts | Strong internal evidence if untouched before the run |
| Authoritative-source independent holdouts | Stronger source-validity evidence when methodology is frozen before execution |
| Customer / third-party validation | Separate evidence class; not currently claimed |

## Holdout V2 — current frozen blind evidence

### Framework

`evaluation/holdout_v2/` contains the frozen 70-case Holdout V2 framework across seven technical-document domains.

### Immutable blind result

`evaluation/results/holdout_v2_blind_once.json` is the preserved single-shot result.

Recorded result metadata includes:

- benchmark: `holdout_v2.0.0`;
- benchmark SHA-256: `2cb44e5dee8b2074036985928db9a98688046e81e0088ba92c1838d72017c1b5`;
- 70 cases / 7 documents;
- status: `single_shot_blind_evaluation_no_tuning_afterwards`.

### Retrieval-supported result

40 retrieval-supported cases:

| Metric | Lexical | RALG |
| --- | ---: | ---: |
| Recall@1 | 100% | **100%** |
| Recall@3 | 100% | **100%** |
| Recall@5 | 100% | **100%** |
| MRR | 1.000 | **1.000** |

### Rejection/support-gate result

30 gate cases:

| Metric | RALG |
| --- | ---: |
| Unsupported rejection | **93.33% (28/30)** |
| False-support rate | **6.67% (2/30)** |

Preserved failures:

- `holdout_v2_025` — false support;
- `holdout_v2_030` — false support.

The failures were diagnosed after the blind evaluation. A generalized calculation-intent evidence gate and development regressions were added afterward. The original V2 benchmark/result was not rerun or rewritten.

### Claim boundary

Holdout V2 is a strong internal independent holdout, but its source notes were authored validation material derived from public documentation. It is not third-party or acquisition-grade external validation.

## Reliability benchmark — current development evidence

`src/reliability_benchmark_v2.py` is a 50-case live HTTP development/regression benchmark covering supported factual, paraphrased, SOP/procedural, unsupported, false-premise, misleading-overlap, runtime-ingested, and existing-KB regression behavior.

Validated hardening checkpoint:

- supported correctness: **100%**;
- unsupported rejection: **100%**;
- false-support: **0%**;
- false-rejection: **0%**;
- API errors: **0**.

This is development evidence and should not be described as an untouched independent holdout.

## Holdout V1 — historical/diagnostic evidence

`evaluation/holdout_v1/` remains preserved. Later reliability work inspected its failure modes, so it is historical/diagnostic evidence rather than untouched post-fix independent evidence for that development cycle.

## Stage 5 and earlier evaluation history

Earlier Stage 1–5 reports remain useful for architecture and benchmark history, but they should not supersede newer frozen evidence.

### Stage 5

The RFC-based Stage 5 work used independently sourced RFC documents but automatically generated, unreviewed benchmark cases. Its preliminary results remain historical engineering evidence. Independent source documents alone do not make benchmark authoring independent.

Relevant artifacts include:

- `STAGE5_INDEPENDENT_EVIDENCE_REPORT.md`;
- `STAGE5_FAILURE_ANALYSIS.md`;
- `STAGE5_FRAMEWORK_STATUS.md`;
- `docs/STAGE5_REVIEW_GUIDE.md`;
- `evaluation/stage5_source_manifest.jsonl`;
- `evaluation/results/stage5_integrity_report.json`.

### Stage 4

`STAGE4_EXTERNAL_EVIDENCE_REPORT.md` is a synthetic external-style evaluation. It is historical/synthetic evidence, not external customer validation.

### Stage 3

`STAGE3_PILOT_READINESS.md` records synthetic customer-style evaluation and limitations at that stage.

### Stage 2

`PILOT_READINESS_REPORT_V2.md`, `DEPLOYMENT_VALIDATION.md`, `SCALE_VALIDATION.md`, and `ABLATION_RESULTS.md` contain lifecycle, scale, reproducibility, deployment, and ablation evidence from earlier milestones.

## Architecture and runtime evidence

### `docs/CURRENT_ARCHITECTURE_STATUS.md`

Current production-runtime architecture and grounded execution boundary.

### Document scoping

The runtime now threads document IDs through the API/query/retrieval path. Scoped requests are prevented from silently falling back to unrelated global/static evidence when the requested scope is invalid or empty.

### Persistence/provenance

Runtime ingestion, stable document IDs, provenance, listing, deletion, restart recovery, and corruption/missing-entry handling are covered by dedicated tests and implementation artifacts.

## Retrieval/performance evidence

- `BENCHMARKS.md` — current benchmark methodology/evidence summary;
- `BENCHMARK_RESULTS.md` — historical retrieval results;
- `PERFORMANCE_VALIDATION.md` — retrieval-latency optimization evidence;
- `RESOURCE_VALIDATION.md` — resource/runtime methodology and measurements;
- `RELIABILITY_BENCHMARK.md` — reliability-oriented development evidence.

## Release, portability, and diligence evidence

- `PROTOTYPE1_RELEASE_CANDIDATE.md` — historical RC1 report;
- `RELEASE_ARTIFACTS.md` — release artifact classification;
- `PORTABILITY_READINESS.md` — portability/readiness evidence;
- `docs/TECHNICAL_DILIGENCE_STATUS.md` — buyer/pilot-facing diligence inventory;
- `THIRD_PARTY_NOTICES.md` — third-party attribution and provenance notes.

## Commercial / pilot framing

- `PILOT_READINESS.md` — controlled pilot release gates;
- `COMMERCIAL_READINESS.md` — current public readiness framing;
- `CUSTOMER_DEMO.md` — local demonstration flow;
- `docs/BUYER_DEMO_GUIDE.md` — buyer-demo guidance where applicable.

## Interpretation rules

1. **Development is not independent.** Benchmarks used during engineering may support regression claims but not untouched-holdout claims.
2. **Synthetic is synthetic.** Synthetic success is not customer-data validation.
3. **Independent source documents do not automatically imply independent benchmark authoring.**
4. **Preserve negative evidence.** Generalized post-failure fixes do not erase the original frozen result.
5. **Do not rerun a single-shot blind benchmark to improve a score after failure inspection.**
6. **Use exact metric denominators and definitions.** Retrieval, answer correctness, rejection, and runtime errors are separate measurements.
7. **No single metric proves production readiness.** Security, provenance, persistence, scale, operational boundaries, and domain-specific validation remain separate gates.
8. **Do not tune production rules to specific frozen-case IDs.** Fixes must generalize.
9. **Compose validation is not equivalent to a full production Docker qualification.**
10. **Use precise evidence labels:** historical, development, synthetic, frozen blind, authoritative-source, third-party, or customer-validated.

## Next evidence direction

The next stronger evaluation should use authoritative upstream technical sources with exact provenance/hashes, contamination checks against prior benchmarks, canonical frozen artifacts, conventional metric definitions, explicit single-shot overwrite protection, and a blind run only after the benchmark/evaluator is frozen and merged.
