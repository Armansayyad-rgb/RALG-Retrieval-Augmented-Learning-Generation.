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
- current public/customer-style evaluation material remains primarily synthetic

## Current pilot evidence

### `STAGE3_PILOT_READINESS.md`
Latest merged Stage 3 pilot-hardening summary. Includes the corrected 360-case synthetic customer-style evaluation and current limitations.

### `PILOT_READINESS_REPORT_V2.md`
Stage 2 validation report covering clean-install reproducibility, 100k scale, performance optimization, bounded soak testing, API lifecycle, and SDK integration.

### `DEPLOYMENT_VALIDATION.md`
Deployment-oriented evidence and explicit distinction between validated local lifecycle behavior and Docker runtime items that remain unvalidated.

### `SCALE_VALIDATION.md`
Scale measurements and hardware-safety decisions for larger corpus tests.

### `ABLATION_RESULTS.md`
Current ablation evidence. Some semantic capabilities remain intentionally marked not isolated/deferred rather than being represented by unsafe or misleading toggles.

### `TECHNICAL_DIFFERENTIATION.md`
Summary of measured comparisons and limitations around technical differentiation.

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
Commercial-readiness framing. Treat older metrics in this document as historical checkpoints when newer Stage 2/3 reports supersede them.

### `CUSTOMER_DEMO.md`
Five-minute local demo flow for ingestion, grounded answering, and safe abstention.

## Important interpretation rules

1. **Synthetic is synthetic.** Public benchmark success is not customer-data validation.
2. **Compose validation is not Docker runtime validation.** Docker runtime remains explicitly unvalidated where the daemon was unavailable.
3. **Historical reports are retained for traceability.** Newer Stage reports supersede older status claims without erasing the earlier evidence trail.
4. **No single metric proves production readiness.** Retrieval quality, false support, provenance, latency, persistence, and operational boundaries must be considered separately.
5. **Unvalidated items remain unvalidated.** Reports should use measured, previously measured, deferred, or not validated labels rather than infer success.

## Next evidence priority

The highest-value next step is harder external-style or permitted real technical-document evaluation that avoids the ceiling effect seen in Stage 3, followed by Docker runtime qualification and larger-scale testing on suitable hardware.
