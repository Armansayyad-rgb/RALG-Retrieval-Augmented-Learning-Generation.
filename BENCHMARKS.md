# Benchmarks

This document summarizes RALG's benchmark discipline and the evidence currently committed to the repository.

## Benchmark principles

RALG does not treat one score as proof of production readiness. Evaluation should keep separate measurements for:

- retrieval quality;
- answer correctness;
- unsupported rejection;
- false-support and false-rejection behavior;
- provenance / evidence traceability;
- runtime errors;
- latency and resource use.

Every serious benchmark should identify the dataset/domain, case count, baseline, RALG version/commit, relevant hardware, metric definitions, failures, and reproducible commands/artifacts.

Frozen blind evaluations must remain immutable after execution. If a blind result exposes a failure, production fixes may be developed afterward, but the original result must not be rerun or rewritten to improve the score.

## Evidence hierarchy

RALG currently uses several evidence classes. They are not interchangeable.

| Evidence class | Purpose | Claim boundary |
| --- | --- | --- |
| Development/regression benchmarks | Fast engineering feedback and generalized hardening | Not independent validation |
| Historical/synthetic evaluations | Architecture and regression history | Not customer/external validation |
| Frozen blind holdouts | Untouched pre-run case sets with integrity controls | Strong internal evidence within the exact methodology |
| Authoritative-source blind holdouts | Stronger source-validity evidence using frozen upstream documents and integrity controls | Not automatically third-party/customer validation |
| Human-reviewed evidence | Independent adjudication of frozen outputs | Must identify reviewer methodology and blinding |
| Customer/pilot evidence | Real deployment validation | Not currently claimed by this repository |

## Holdout V2 — frozen single-shot blind evaluation

`evaluation/holdout_v2/` contains the frozen 70-case Holdout V2 framework. The committed blind result is:

```text
evaluation/results/holdout_v2_blind_once.json
```

The result metadata records:

- benchmark: `holdout_v2.0.0`;
- 70 cases;
- 7 documents;
- status: `single_shot_blind_evaluation_no_tuning_afterwards`;
- benchmark SHA-256: `2cb44e5dee8b2074036985928db9a98688046e81e0088ba92c1838d72017c1b5`.

### Retrieval-supported cases

40 cases were evaluated for ranked retrieval.

| Metric | Lexical | RALG |
| --- | ---: | ---: |
| Recall@1 | 100% | **100%** |
| Recall@3 | 100% | **100%** |
| Recall@5 | 100% | **100%** |
| MRR | 1.000 | **1.000** |

The overall Recall@1/Recall@5 Wilson 95% interval recorded in the result is approximately `[0.9124, 1.0000]` for the 40 ranked cases.

### Rejection/support-gate cases

30 cases exercised unsupported/adversarial support gating.

| Metric | RALG |
| --- | ---: |
| Unsupported rejection | **93.33% (28/30)** |
| False-support rate | **6.67% (2/30)** |

The recorded unsupported-rejection 95% Wilson interval is approximately `[0.7868, 0.9815]`.

The two preserved failures are:

- `holdout_v2_025` — false support;
- `holdout_v2_030` — false support.

Those failures were analyzed only after the blind run and led to a generalized calculation-intent support-gate fix plus development regressions. Holdout V2 itself was not rerun after the fix.

### Holdout V2 limitation

Holdout V2 is strong internal blind evidence, but the seven validation source notes were authored from public technical documentation rather than being a fully authoritative upstream-document corpus. It should not be described as third-party or external validation.

## Holdout V3 — preserved authoritative-source blind evidence

`evaluation/results/holdout_v3_blind_once.json` is the frozen Holdout V3 result. It must remain preserved as negative as well as diagnostic evidence. The result showed materially poor retrieval/answer/rejection performance in that frozen system/evaluator state and must not be rewritten or rerun to improve the headline outcome.

V3 should be described as an **authoritative-source independent blind holdout**, not as third-party/customer validation and not as positive proof of production quality.

## Reliability benchmark — development/regression evidence

`src/reliability_benchmark_v2.py` exercises live HTTP behavior across supported factual, paraphrased, procedural, unsupported, false-premise, misleading-overlap, runtime-ingested, and existing-KB regression cases.

In the validated reliability-hardening run, the 50-case benchmark reached:

| Metric | Result |
| --- | ---: |
| Supported correctness | **100%** |
| Unsupported rejection | **100%** |
| False-support rate | **0%** |
| False-rejection rate | **0%** |
| API errors | **0** |

This benchmark is development/regression evidence. It is not an untouched independent holdout and should not be reported as one.

## Holdout V1 — historical/diagnostic evidence

`evaluation/holdout_v1/` remains preserved for reproducibility and historical comparison. Later reliability work inspected V1 failure modes, so V1 should no longer be described as untouched independent post-fix evidence for that development cycle.

Do not modify or rerun the frozen V1 artifacts to improve historical results.

## Holdout V4 — pre-declared post-freeze protocol

The methodology for the next fresh post-freeze blind evaluation is defined at:

```text
evaluation/holdout_v4/PROTOCOL.md
```

The protocol is merged before V4 source selection, question authoring, evaluator execution, or result inspection. It fixes the benchmark at **160 cases** with explicit denominator families, authoritative-source requirements, contamination controls, pre-run ground-truth review, artifact hashing, one-run protection, post-run blinded human adjudication, failure taxonomy, and reporting rules.

Until the V4 benchmark is frozen and the single official run is executed, **no V4 performance result exists**.

## Earlier retrieval proof runners

The original lightweight retrieval proof runner remains useful for fast local experimentation:

```powershell
python src\retrieval_proof_v1.py --dataset data\technical_doc_benchmark_v1.jsonl --knowledge-file data\technical_docs_sample.txt
```

A harder synthetic benchmark is also available:

```powershell
python src\retrieval_proof_v1.py --dataset data\technical_doc_benchmark_hard_v1.jsonl --knowledge-file data\technical_docs_hard_sample.txt
```

These tests are useful engineering/regression tools but are lower in the evidence hierarchy than frozen blind holdouts.

## Reporting rules

When publishing or discussing RALG benchmark results:

1. State the exact evidence class and methodology.
2. Report retrieval and support/rejection metrics separately.
3. Preserve negative evidence and exact failures.
4. Do not rerun a single-shot blind benchmark after inspecting its failures to obtain a better headline result.
5. Do not weaken thresholds or cases to force a pass.
6. Do not claim global performance from one benchmark/domain.
7. Do not call internally authored benchmark questions third-party/customer validation.
8. Record exact benchmark/result artifacts and hashes when available.
9. Do not infer end-to-end product throughput from retrieval-only performance measurements.

## Next evidence direction

Execute Holdout V4 strictly in the sequence declared by `evaluation/holdout_v4/PROTOCOL.md`: select and license-review new authoritative sources, author/review the fixed case set without probing the target system, freeze all artifacts and hashes, run once, preserve the official result, then perform blinded human answer adjudication.
