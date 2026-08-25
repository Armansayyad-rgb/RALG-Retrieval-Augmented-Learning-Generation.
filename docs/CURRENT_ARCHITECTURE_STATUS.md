# Current Architecture Status

This document summarizes the production architecture on current `master` after the hybrid-retrieval and core-runtime consolidation work merged in PRs #49 and #47.

## Current `/query` runtime

```text
POST /query
  -> api_server.query()
  -> execute_runtime()
     -> ExecutionPlan
        -> semantic intent + one authoritative route decision
     -> answer_question()
        -> factual extractor OR grounded reasoning path
        -> retriever_hybrid for grounded reasoning retrieval
        -> bounded optional secondary queries
        -> explicit evidence / multi-hop trace
     -> build_answer_contract()
     -> unified_support_gate()
        -> evidence identity
        -> traceability
        -> conflict status
        -> provenance
     -> supported answer OR abstention
  -> QueryResponse
```

The FastAPI and WebUI surfaces now share the same `execute_runtime()` orchestration boundary for grounded RALG behavior.

## Authoritative retrieval

`src/retriever_hybrid.py` is the authoritative grounded reasoning retriever.

It uses a full-question-first strategy:

1. run the complete user question through the fast V2 lexical/index path;
2. preserve strong full-question candidates;
3. optionally run a bounded number of secondary/sub-query passes when useful;
4. deduplicate by canonical candidate identity;
5. fuse candidates deterministically using general full-question coverage/rank signals;
6. preserve provenance through the final evidence path.

The factual extractor route still uses a cheaper single-pass V2 lookup. This is intentional route specialization, not a separate user-facing retrieval stack.

## Current preliminary Stage 5 retrieval checkpoint

Stage 5 contains 50 independently sourced IETF RFC documents and 300 automatically generated, still-unreviewed benchmark cases.

After the hybrid-retrieval change, the untouched preliminary evaluator recorded:

| Metric | Lexical | RALG hybrid |
| --- | ---: | ---: |
| Recall@1 | 40.48% | **50.95%** |
| Recall@3 | 87.62% | **90.95%** |
| Recall@5 | 100.00% | **100.00%** |
| MRR | 0.6485 | **0.7098** |
| Unsupported rejection | 100% | **100%** |
| False-support rate | 0% | **0%** |

The runtime-integration validation preserved those quality metrics. Retrieval latency in the integration run was approximately 6.9 ms p50 / 14.6 ms p95 in the recorded local environment.

These numbers are **preliminary engineering evidence, not final independent validation** because the benchmark cases have not been independently human-reviewed.

## Runtime architecture now implemented

- one shared `ExecutionPlan` / `execute_runtime()` orchestration boundary;
- one authoritative route value produced by runtime planning;
- shared API/WebUI grounded execution behavior;
- hybrid full-question-first grounded reasoning retrieval;
- unified answer-level support gate;
- provenance/traceability requirements before `supported=true`;
- conflict-aware abstention;
- explicit `MultiHopTrace` state;
- declarative model registry with runtime model-selection guardrails;
- active/compatible/superseded/legacy artifact classification;
- focused architecture and integration tests.

## Model registry

The current active grounded model role is mapped to `checkpoints/v2/reasoning_model_v1.pt` through configuration. Other known artifacts are explicitly classified rather than silently auto-loaded.

The optional Qwen polish role remains non-grounded and opt-in. It must not establish evidence support.

## Remaining architecture / production gaps

The main remaining gaps are no longer duplicate routing or API/UI divergence. Current material gaps are:

1. **Independent review:** Stage 5 cases remain automatically generated and unreviewed.
2. **Public-production security:** no built-in authentication, TLS termination, tenant isolation, or production-grade rate limiting.
3. **Multi-process lifecycle safety:** document mutation locking is process-local; controlled pilots should use one application worker.
4. **Docker runtime qualification:** Compose is maintained, but a complete clean Docker lifecycle still needs current end-to-end evidence.
5. **Large-scale validation:** 250k/500k corpus runs remain deferred pending suitable memory headroom.
6. **Retrieval headroom:** some rank-1 ties remain among documents sharing the same terminology; phrase/proximity signals are a possible future general improvement, but should be validated independently before adoption.
7. **Artifact/dependency diligence:** historical training utilities and model artifacts remain for reproducibility and should be inventoried rather than deleted blindly.

## Interpretation

RALG is appropriate for controlled technical evaluation in a trusted environment. It is not yet an untrusted multi-tenant public service.

The highest-value next work is independent review, deployment/security diligence, reproducible Docker validation, and a clean technical-diligence package rather than another synthetic benchmark stage.
