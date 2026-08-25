# Validation & Evidence Index

This page organizes RALG's engineering evidence so current status is easier to interpret without treating every historical report as equally current.

## Current status

The current repository state is suitable for controlled technical evaluation in a trusted, single-worker environment. It is not a claim of public production readiness.

Key current checkpoints:

- Prototype 1 RC1 preserved at `0.1.0-rc1`;
- regression suite: 23/23 PASS in the current runtime-integration validation;
- commercial validation: quality gate PASS;
- clean Python 3.11 install: previously validated;
- isolated API lifecycle: previously validated;
- live SDK integration: previously validated;
- 1000-request / 8-worker soak: previously validated with 0 errors;
- 100k retrieval: previously measured in the Stage 2 environment;
- Stage 4 synthetic external-style evaluation showed rank-1 differentiation but remained synthetic;
- Stage 5 uses 50 independently sourced IETF RFC documents and 300 automatically generated cases;
- current Stage 5 preliminary hybrid retrieval beats the lexical baseline at Recall@1, Recall@3, and MRR while tying Recall@5;
- Stage 5 still remains **BLOCKED ON INDEPENDENT REVIEW** because those cases are not independently human-reviewed.

## Current architecture evidence

### `docs/CURRENT_ARCHITECTURE_STATUS.md`
Current production-runtime architecture after PRs #49 and #47. Grounded API/WebUI requests share `execute_runtime()`, the reasoning path uses the full-question-first hybrid retriever, and support/provenance/conflict decisions are consolidated behind one runtime boundary.

## Stage 5 — independent-source evidence

### `STAGE5_INDEPENDENT_EVIDENCE_REPORT.md`
Historical/current Stage 5 narrative covering the independently sourced RFC corpus, provenance controls, preliminary evaluation, and the unresolved review gate. Where older metrics differ from current code, treat the current evaluator output as newer engineering evidence and keep the report's review limitation intact.

### `scripts/stage5_preliminary_evaluation.py`
Authoritative preliminary retrieval evaluator. It explicitly labels its output unreviewed and uses `retriever_hybrid` for RALG retrieval.

### Current preliminary retrieval checkpoint

| Metric | Lexical | RALG hybrid |
| --- | ---: | ---: |
| Recall@1 | 40.48% | **50.95%** |
| Recall@3 | 87.62% | **90.95%** |
| Recall@5 | 100.00% | **100.00%** |
| MRR | 0.6485 | **0.7098** |
| Unsupported rejection | 100% | **100%** |
| False-support rate | 0% | **0%** |

The runtime-integration validation preserved these quality metrics. These results are **preliminary/unreviewed**, not final independent validation.

### `STAGE5_FAILURE_ANALYSIS.md`
Historical preliminary failure analysis. Do not use individual case IDs to create production rules.

### `STAGE5_FRAMEWORK_STATUS.md`
Independent-evidence framework and review-workflow status.

### `docs/STAGE5_REVIEW_GUIDE.md`
Blinded reviewer protocol and acceptance/correction process.

### `evaluation/stage5_source_manifest.jsonl`
Machine-readable source provenance and rights metadata.

### `evaluation/results/stage5_integrity_report.json`
Corpus/manifest/hash integrity evidence.

## Stage 4 — external-style synthetic evidence

### `STAGE4_EXTERNAL_EVIDENCE_REPORT.md`
600-case synthetic external-style evaluation. Useful for regression/history, but not external customer validation.

### `STAGE4_FAILURE_ANALYSIS.md`
Stage 4 ranking/failure analysis.

## Stage 3 — customer-style synthetic evidence

### `STAGE3_PILOT_READINESS.md`
Corrected synthetic customer-style evaluation and limitations at that stage.

## Stage 2 — lifecycle, scale, and reproducibility

### `PILOT_READINESS_REPORT_V2.md`
Clean-install reproducibility, 100k scale, performance optimization, bounded soak testing, API lifecycle, and SDK integration.

### `DEPLOYMENT_VALIDATION.md`
Local lifecycle evidence and explicit Docker-runtime limitations.

### `SCALE_VALIDATION.md`
Scale measurements and hardware-safety decisions for larger corpus tests.

### `ABLATION_RESULTS.md`
Ablation evidence; some semantic capabilities remain not isolated/deferred.

## Retrieval and performance evidence

### `BENCHMARKS.md`
Benchmark definitions and methodology.

### `BENCHMARK_RESULTS.md`
Historical retrieval benchmark results.

### `PERFORMANCE_VALIDATION.md`
Postings-index and retrieval-latency optimization evidence.

### `RESOURCE_VALIDATION.md`
Resource/runtime measurements and methodology.

### `RELIABILITY_BENCHMARK.md`
End-to-end reliability-oriented evidence.

## Release, portability, and diligence evidence

### `PROTOTYPE1_RELEASE_CANDIDATE.md`
Historical RC1 release-candidate report.

### `RELEASE_ARTIFACTS.md`
Required external artifact classification and release expectations.

### `PORTABILITY_READINESS.md`
Portability/readiness validation and known limitations.

### `docs/TECHNICAL_DILIGENCE_STATUS.md`
Current buyer/pilot-facing technical-diligence inventory: strengths, unresolved evidence/security/IP items, and next gates.

## Commercial / pilot framing

### `PILOT_READINESS.md`
Controlled pilot release gates.

### `COMMERCIAL_READINESS.md`
Current public commercial-readiness framing and diligence gaps.

### `CUSTOMER_DEMO.md`
Local demo flow for ingestion, grounded answering, and abstention.

## Interpretation rules

1. **Synthetic is synthetic.** Stage 1–4 success is not customer-data validation.
2. **Independent source documents do not equal independent benchmark review.** Stage 5 documents are independently sourced; the generated benchmark cases remain unreviewed.
3. **Use current code/results for current engineering claims.** Older reports remain historical evidence and may describe superseded retrieval paths.
4. **Do not hide negative evidence.** Preserve historical failures and limitations even after a general fix improves the metric.
5. **Compose validation is not Docker runtime validation.** A complete current container lifecycle must be demonstrated separately.
6. **No single metric proves production readiness.** Retrieval quality, false support, provenance, latency, persistence, security, and operational boundaries are separate gates.
7. **Unvalidated items remain unvalidated.** Use measured, previously measured, deferred, preliminary/unreviewed, or not validated labels.
8. **Do not tune production code to individual Stage 5 case IDs.** Architecture/retrieval fixes must generalize and preserve benchmark integrity.

## Next evidence priority

1. independent human review/freeze of Stage 5;
2. current Docker lifecycle validation;
3. dependency/model/data-rights inventory;
4. buyer/pilot reproducibility package;
5. representative customer-style evaluation under permission rather than another internally generated benchmark stage.
