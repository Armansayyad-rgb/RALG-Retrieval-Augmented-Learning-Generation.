# Validation & Evidence Index

This page organizes RALG's engineering evidence so current status is easier to understand without treating every historical report as equally current.

## Current status

The current repository state is suitable for controlled technical evaluation in a trusted, single-worker environment. It is not a claim of public production readiness.

Key current checkpoints:

- Prototype 1 RC1 preserved at `0.1.0-rc1`
- regression suite: 23/23 PASS
- commercial validation: 10/10 PASS
- clean Python 3.11 install: PASS
- isolated API lifecycle: PASS
- live SDK integration: PASS
- 1000-request / 8-worker soak: 0 errors
- optimized 100k retrieval: ~156 ms p50 / ~216 ms p95 in the recorded Stage 2 environment
- Stage 4 synthetic external-style evaluation showed a measurable rank-1 advantage for RALG but a Recall@5 ceiling for both systems
- Stage 5 added 50 independently sourced IETF RFC documents and a 300-case preliminary benchmark
- Stage 5 preliminary retrieval quality currently favors the lexical baseline; RALG's strongest measured result in that harness is latency
- Stage 5 remains **BLOCKED ON INDEPENDENT REVIEW** because the 300 cases are automatically generated and unreviewed

## Current architecture evidence

### `docs/CURRENT_ARCHITECTURE_STATUS.md`
Current production-runtime architecture summary. The original compound architecture is approximately 70% integrated. Highest-priority gaps are duplicate routing authority, distributed support adjudication, training/runtime disconnect, API/UI divergence, and heuristic multi-hop state.

## Stage 5 — independent evidence

### `STAGE5_INDEPENDENT_EVIDENCE_REPORT.md`
Current Stage 5 report covering the independently sourced RFC corpus, preliminary untouched lexical-vs-RALG evaluation, provenance/integrity controls, and explicit review limitation.

### `STAGE5_FAILURE_ANALYSIS.md`
Preliminary failure categories and representative retrieval/evidence issues. These failures must not be used for benchmark-ID-specific production tuning.

### `STAGE5_FRAMEWORK_STATUS.md`
Status of the independent-evidence framework, review workflow, and unresolved human-review gate.

### `STAGE5_DATA_ACQUISITION_GUIDE.md`
Independent-source acquisition and legal/provenance guidance.

### `docs/STAGE5_REVIEW_GUIDE.md`
Blinded review protocol and reviewer acceptance/correction process.

### `evaluation/results/stage5_preliminary_results.json`
Machine-readable preliminary Stage 5 results. Treat as unreviewed benchmark evidence, not final external validation.

### `evaluation/results/stage5_integrity_report.json`
Machine-readable corpus/manifest/hash integrity report.

## Stage 4 — external-style synthetic evidence

### `STAGE4_EXTERNAL_EVIDENCE_REPORT.md`
600-case synthetic external-style evaluation. RALG reached Recall@1 100% versus lexical 96.875%, while both reached Recall@5 100%; therefore the result demonstrates rank-1 differentiation but still contains a deeper-retrieval ceiling effect.

### `STAGE4_FAILURE_ANALYSIS.md`
Stage 4 ranking/failure analysis.

## Stage 3 — customer-style synthetic evidence

### `STAGE3_PILOT_READINESS.md`
Corrected 360-case synthetic customer-style evaluation and current limitations at that stage.

## Stage 2 — lifecycle, scale, and reproducibility

### `PILOT_READINESS_REPORT_V2.md`
Clean-install reproducibility, 100k scale, performance optimization, bounded soak testing, API lifecycle, and SDK integration.

### `DEPLOYMENT_VALIDATION.md`
Deployment-oriented evidence and explicit distinction between validated local lifecycle behavior and Docker runtime items that remain unvalidated.

### `SCALE_VALIDATION.md`
Scale measurements and hardware-safety decisions for larger corpus tests.

### `ABLATION_RESULTS.md`
Current ablation evidence. Some semantic capabilities remain intentionally marked not isolated/deferred rather than represented by unsafe or misleading toggles.

### `TECHNICAL_DIFFERENTIATION.md`
Historical summary of measured comparisons and limitations around technical differentiation.

## Retrieval and performance evidence

### `BENCHMARKS.md`
Benchmark definitions and methodology.

### `BENCHMARK_RESULTS.md`
Recorded retrieval benchmark results.

### `PERFORMANCE_VALIDATION.md`
Postings-index and retrieval-latency optimization evidence.

### `RESOURCE_VALIDATION.md`
Resource/runtime measurements and methodology.

### `RELIABILITY_BENCHMARK.md`
End-to-end reliability-oriented evidence.

## Release and portability evidence

### `PROTOTYPE1_RELEASE_CANDIDATE.md`
Historical RC1 release-candidate report. Retained as release history rather than current status.

### `RELEASE_ARTIFACTS.md`
Required external artifact classification and release hashes/expectations.

### `PORTABILITY_READINESS.md`
Portability/readiness validation and known platform/runtime limitations.

## Commercial / pilot framing

### `PILOT_READINESS.md`
Pilot release gates and controlled-deployment expectations.

### `COMMERCIAL_READINESS.md`
Commercial-readiness framing. Treat older metrics in this document as historical checkpoints when newer Stage reports supersede them.

### `CUSTOMER_DEMO.md`
Five-minute local demo flow for ingestion, grounded answering, and safe abstention.

## Interpretation rules

1. **Synthetic is synthetic.** Stage 1–4 success is not customer-data validation.
2. **Independent source documents do not equal independent benchmark review.** Stage 5 documents are independently sourced, but its generated cases remain unreviewed.
3. **Do not hide negative evidence.** The preliminary Stage 5 lexical baseline currently leads retrieval-quality metrics and must remain visible.
4. **Compose validation is not Docker runtime validation.** Docker runtime remains explicitly unvalidated where a full lifecycle was not run.
5. **Historical reports are retained for traceability.** Newer Stage reports supersede older status claims without erasing earlier evidence.
6. **No single metric proves production readiness.** Retrieval quality, false support, provenance, latency, persistence, and operational boundaries must be considered separately.
7. **Unvalidated items remain unvalidated.** Reports should use measured, previously measured, deferred, or not validated labels rather than infer success.
8. **Do not tune production code to individual Stage 5 case IDs.** Architecture fixes must generalize and preserve benchmark integrity.

## Next evidence priority

The next engineering priority is core architecture consolidation: one authoritative execution plan, unified answer-level support adjudication, stronger multi-hop state, model-registry integration, and API/UI parity. After that work is validated without benchmark-specific tuning, the independent Stage 5 evaluation can be rerun while the human-review requirement remains explicit.
