# Current Production Architecture

This document describes the current RALG production runtime on `master`. It supersedes the older architecture snapshot that ended at the hybrid-retrieval consolidation stage.

## Product boundary

RALG is a local-first, evidence-grounded technical-document intelligence engine. It is designed for trusted/local deployments over bounded document collections. It is not currently a hardened public multi-tenant SaaS.

The defining architectural rule is:

> Retrieval can propose evidence; only the grounding and support pipeline can authorize an answer.

## End-to-end runtime

```text
Documents
PDF / DOCX / TXT
      |
      v
parse -> normalize -> chunk -> persistent runtime corpus/index
                                      |
                                      v
User question -> FastAPI / WebUI -> execute_runtime()
                                      |
                                      v
                               ExecutionPlan
                    intent / route / document scope /
                    retrieval strategy / model role
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
            extractor route                    reasoning route
            retriever_v2                       retriever_hybrid
            cheap factual pass                 full-question-first
                    |                                   |
                    +-----------------+-----------------+
                                      |
                                      v
                           answer construction
              factual / definition / procedure / causal /
              comparison / bounded broad synthesis / etc.
                                      |
                                      v
                         build_answer_contract()
                   relation + definition + subject checks
                   source/evidence + conflict + provenance
                                      |
                                      v
                         unified_support_gate()
                  raw.supported AND contract.supported
                   evidence/source AND traceability
                   no unresolved conflict + provenance
                                      |
                         +------------+------------+
                         |                         |
                         v                         v
                 supported answer              abstention
                 with traceability             fail closed
```

FastAPI and WebUI share the same `execute_runtime()` orchestration boundary, so grounded support policy is not supposed to diverge between interfaces.

## 1. Runtime orchestration

### `src/runtime_architecture.py`

This is the authoritative orchestration boundary. It owns:

- `ExecutionPlan`;
- model-role resolution and registry guardrails;
- route/retrieval strategy representation;
- `MultiHopTrace` construction;
- `ExecutionResult`;
- `unified_support_gate()`;
- `execute_runtime()` shared by API and UI.

The final gate is intentionally additive. A weak upstream `raw.supported=True` cannot override a contract that was rejected after grounding. `contract.supported=False` contributes `contract_unsupported` and causes the final support decision to fail.

## 2. Question routing and answer construction

### `src/rag_chat_v2.py`

`rag_chat_v2` is the active answer pipeline. It performs question classification/routing, invokes the appropriate retrieval path, and constructs candidate answers.

Current behavior includes specialized handling for factual, definitional, procedural, causal/effect/change, comparison, entity/structure/summary-style, multi-hop, and broad explanatory questions.

The recent broad-grounded-synthesis path addresses a specific architectural limitation: a broad explanatory request may be supported across several passages even when no single chunk contains the entire answer. The system may synthesize those individually grounded claims without globally lowering the support threshold.

Narrow factual/attribute questions remain subject to stronger relation binding than broad explanatory synthesis.

## 3. Retrieval architecture

### `src/retriever_hybrid.py` — grounded reasoning

The authoritative reasoning retriever is full-question-first:

1. run the complete question through the fast V2 retrieval path;
2. protect strong full-question candidates;
3. measure full-question evidence coverage;
4. only when useful, run a bounded number of secondary/sub-query passes;
5. deduplicate by candidate identity;
6. fuse candidates deterministically using full-question coverage and rank signals;
7. preserve candidate identity/provenance into the answer path.

Secondary retrieval is deliberately bounded and cannot displace a stronger primary candidate merely because a heuristic sub-query matched it.

### `src/retriever_v2.py` — factual extraction

The factual extractor intentionally retains the cheaper V2 retrieval path. This is route specialization inside the same grounded runtime, not an independent user-facing architecture.

Document IDs can constrain retrieval. Invalid or empty scope must fail safely rather than silently reverting to unrelated global evidence.

## 4. Grounding contract

### `src/webui/chat_handler.py`

The answer contract is the post-answer grounding boundary. It is responsible for source collection and checks used by the final support gate.

Current grounding behavior includes:

- structured subject extraction;
- subject/entity anchor validation;
- predicate/relation grounding;
- definition-specific relation checks;
- answer-addressing validation;
- identifier-sensitive grounding;
- multi-part completeness protections;
- conflict detection;
- evidence/source traceability;
- provenance propagation.

A title/header or lexical mention alone is not enough to support a simple definition. Generic overlapping words are not intended to establish an unrelated technical relation.

Conflict detection is applied after basic grounding. Evidence that does not ground the requested relation should not be mislabeled as a genuine contradiction.

## 5. Broad grounded synthesis

Broad explanatory questions use a different evidence shape from narrow attribute lookups.

The permitted pattern is:

```text
broad question
   -> retrieve several relevant passages
   -> keep passages grounded to the requested subject/topic
   -> extract supported claims
   -> combine only supported claims
   -> run normal contract/support checks
   -> answer or abstain
```

The forbidden pattern is:

```text
broad question -> lower global threshold -> free generation
```

This preserves conservative behavior for unsupported, false-premise, misleading-overlap, narrow factual, and definition questions while allowing evidence distributed across multiple chunks to form a bounded explanation.

## 6. Model architecture and optional generation

`src/model_v2.py` defines the active `SmallLMV2` architecture. Runtime configuration maps the grounded model role to:

```text
checkpoints/v2/reasoning_model_v1.pt
```

The checkpoint is external to Git. Its absence must fail safely; it does not justify an exception in the grounding policy.

The runtime can operate in extractive/retrieval-only mode without the checkpoint when the required tokenizer/index/retrieval components are healthy.

The optional Qwen polish role is explicitly non-grounded. It may rewrite/polish text when enabled, but it cannot establish support or substitute for retrieved evidence.

## 7. Document ingestion and persistence

The active ingestion path accepts PDF, DOCX, and TXT documents through the API/WebUI document processor. Runtime documents are assigned stable identities and stored with provenance metadata. The index is updated for newly ingested chunks and runtime documents can be listed/deleted and restored after restart.

Document lifecycle and query scope are part of the same production system rather than demo-only state.

## 8. API and UI

### FastAPI

The service includes the core endpoints:

```text
/health
/ready
/stats
/ingest
/query
/documents
```

`/ready` represents usable runtime readiness, including the validated extractive/retrieval-only mode; an absent optional generation checkpoint is reported separately rather than automatically making the core retrieval system unusable.

### WebUI

The Gradio interface uses the same grounded runtime boundary and supports document upload, querying, source display, document scope, and related user-facing workflow.

## 9. Startup and deployment tooling

`scripts/run_demo.ps1` is the canonical Windows demo launcher. Current launch behavior:

- discovers a Python 3.11 interpreter, including `py -3.11` correctly;
- runs preflight validation;
- treats recommended/optional model artifacts as nonfatal when extractive mode is viable;
- starts API and WebUI jobs with explicit interpreter arguments/environment;
- probes readiness using an HTTP-success check;
- retries until ready or fails cleanly with job diagnostics/cleanup;
- selects the WebUI from the bounded `7860-7870` port range.

## 10. Evidence and evaluation boundary

The repository contains historical development benchmarks, several holdout generations, frozen blind artifacts, adjudication outputs, and regression suites. Architecture documentation must not collapse these into one accuracy number.

Frozen blind evaluations remain immutable after execution. Later semantic adjudication and derived scorecards are separate evidence layers. Production fixes made after a frozen evaluation require fresh evaluation before making a new global correctness claim.

The current architecture therefore prioritizes reproducibility and evidence labeling as well as runtime correctness.

## 11. Security/deployment boundary

RALG is suitable for controlled local/trusted technical evaluation. A public untrusted multi-tenant deployment still requires additional hardening, including tenant isolation, hardened authentication/authorization, TLS termination, production rate limiting, secrets/operations controls, and multi-process-safe mutation semantics.

## 12. Key production files

| Path | Role |
| --- | --- |
| `src/runtime_architecture.py` | authoritative runtime orchestration and final support gate |
| `src/rag_chat_v2.py` | active question/answer pipeline |
| `src/retriever_hybrid.py` | reasoning retrieval |
| `src/retriever_v2.py` | fast lexical/factual retrieval |
| `src/webui/chat_handler.py` | answer contract, grounding, conflicts, source/provenance handling |
| `src/api_server.py` | FastAPI service |
| `src/webui/app.py` | Gradio UI |
| `src/webui/document_processor.py` | document parsing/ingestion support |
| `src/model_v2.py` | SmallLM V2 model definition |
| `src/config.py` | central runtime paths/configuration |
| `scripts/run_demo.ps1` | canonical Windows demo launcher |

## Interpretation

The current architecture is best described as an **evidence-gated document intelligence runtime**, not simply retrieval followed by an LLM. Retrieval, answer construction, grounding, conflict handling, provenance, and the final support decision are distinct stages so that a plausible-looking answer does not automatically become a supported answer.
