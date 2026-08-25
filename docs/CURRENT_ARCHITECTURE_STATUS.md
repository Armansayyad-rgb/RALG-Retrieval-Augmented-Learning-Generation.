# Current Architecture Status

This document summarizes the production architecture on `master` before the next core-runtime consolidation build.

## Coverage

The original RALG compound architecture is approximately **70% implemented** across routing, retrieval, factual/reasoning paths, multi-hop retrieval, grounding, support adjudication, generation, abstention, provenance, and learning/runtime integration.

## Current `/query` runtime

```text
POST /query
  -> api_server.query()
  -> get_pipeline() / initialize_pipeline()
  -> rag_chat_v2.answer_question()
     -> runtime_plan() / query_planner_v1.build_queries()
     -> router_v1.route_question()
     -> factual, comparison, or reasoning path
     -> V2 and/or V4 retrieval
     -> optional second retrieval pass for multi-hop
     -> evidence/support checks
     -> deterministic extraction/synthesis or SmallLMV2 generation
     -> abstention when support is insufficient
  -> build_answer_contract()
     -> traceability
     -> conflict detection
     -> provenance
  -> QueryResponse
```

## Implemented and active

- V2/V4 retrieval paths
- factual extraction path
- reasoning path
- comparison handling
- unsupported-query abstention/refusal
- provenance and answer-contract construction
- runtime document ingestion and indexing
- one additional multi-hop retrieval pass

## Partial or architecturally split

- Routing has two authorities: `runtime_plan()` and `router_v1.route_question()`.
- Multi-hop decomposition is heuristic rather than explicit subquestion/entity-state tracking.
- Evidence sufficiency, factual predicates, premise validation, overlap checks, conflict detection, and support decisions are distributed rather than owned by one authoritative support gate.
- API and Web UI can follow different retrieval/generation behavior.
- The API uses the custom runtime path while optional Qwen generation is Web-UI-only.
- Most trained artifacts are not connected to the current API runtime.

## Trained artifacts and legacy paths

The current API runtime loads the configured tokenizer and `checkpoints/v2/reasoning_model_v1.pt`. Older embedding, factual/instruction, and language-model artifacts exist but are not all loaded by production initialization.

Historical research/training implementations remain for reproducibility and should not be deleted until dependency and benchmark-history checks confirm they are unnecessary.

## Highest-priority architecture gaps

1. Replace duplicate routing authorities with one authoritative execution plan.
2. Create one answer-level evidence/support adjudication gate.
3. Establish a model registry that clearly maps training artifacts to serving behavior.
4. Bring API and Web UI onto the same grounded core execution pipeline.
5. Replace weak multi-hop heuristics with explicit subquestion/evidence/intermediate-fact state.

## Current evidence context

Stage 5 includes 50 independently sourced IETF RFC documents and a 300-case preliminary benchmark. The preliminary untouched retrieval result favored the lexical baseline on retrieval quality while RALG was substantially faster. The cases remain automatically generated and unreviewed, so Stage 5 is **blocked on independent review** rather than final external validation.

No production retrieval change should be justified by individual Stage 5 cases until the architecture and review gates are handled without benchmark-specific tuning.

## Next build

The next core build should introduce a single `ExecutionPlan` orchestration layer that owns routing, retrieval strategy, multi-hop state, evidence selection, support adjudication, generation/extraction, abstention, and provenance. It should also add an explicit model registry and preserve benchmark integrity while measuring whether the more coherent architecture improves generalization.
