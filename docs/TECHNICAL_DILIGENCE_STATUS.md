# Technical Diligence Status

This document is a public technical-diligence summary for controlled pilots, licensing discussions, and strategic technology evaluation. It intentionally excludes valuation targets, prospect lists, negotiation notes, and other private business material.

## Executive summary

RALG now has a coherent grounded production runtime and a measurable preliminary retrieval advantage on independently sourced RFC documents. The strongest current technical story is:

- full-question-first hybrid retrieval;
- one shared grounded runtime across API and WebUI;
- provenance-aware support gating and abstention;
- deterministic evaluation and regression infrastructure;
- local/private deployment orientation;
- explicit disclosure of limitations and historical negative results.

The project is **not** yet an untrusted public-production platform. The remaining diligence blockers are primarily independent review, deployment/security qualification, and third-party/IP inventory rather than missing core retrieval architecture.

## Current technical evidence

### Retrieval

Preliminary Stage 5 evaluation over 50 independently sourced IETF RFC documents and 300 automatically generated/unreviewed cases:

| Metric | Lexical | RALG hybrid |
| --- | ---: | ---: |
| Recall@1 | 40.48% | **50.95%** |
| Recall@3 | 87.62% | **90.95%** |
| Recall@5 | 100.00% | **100.00%** |
| MRR | 0.6485 | **0.7098** |
| Unsupported rejection | 100% | **100%** |
| False-support rate | 0% | **0%** |

The runtime-integration validation preserved the same retrieval-quality metrics. These results remain preliminary until independent human review is completed.

### Runtime architecture

Current grounded request path:

```text
API / WebUI
  -> execute_runtime()
  -> ExecutionPlan
  -> factual extractor OR grounded reasoning
  -> retriever_hybrid for reasoning retrieval
  -> answer contract
  -> unified support / provenance / conflict gate
  -> supported answer or abstention
```

### Reliability / lifecycle

Repository evidence includes:

- 23/23 regression validation;
- commercial quality-gate validation;
- clean Python 3.11 installation evidence;
- isolated ingest/query/list/delete/restart lifecycle evidence;
- SDK integration evidence;
- 1000-request / 8-worker soak evidence with zero recorded errors;
- 100k retrieval-scale measurements;
- upload provenance and persistence/restart tests;
- CI coverage for portability, security-sensitive input handling, retrieval, and evidence behavior.

## Asset inventory by role

### Production/runtime

- `src/api_server.py`
- `src/runtime_architecture.py`
- `src/rag_chat_v2.py`
- `src/retriever_hybrid.py`
- `src/retriever_v2.py`
- factual/comparison/reasoning synthesizers used by the runtime
- `src/webui/`
- configuration and SDK/client components

### Evaluation/validation

- `scripts/stage5_preliminary_evaluation.py`
- `evaluation/`
- regression, commercial, performance, provenance, persistence, and architecture test modules
- Stage 1–5 reports retained for traceability

### Training/research/history

- tokenizer/model training scripts
- older V1/V2/V3/V4 experimental components
- intermediate artifact builders and historical evaluation utilities

Historical files are retained for reproducibility and should not be deleted merely to make the repository smaller. A buyer-facing package should clearly distinguish active runtime dependencies from historical research artifacts.

## Diligence strengths

1. **Benchmark honesty:** negative Stage 5 results were preserved before the general hybrid fix; the repository does not need to erase historical failures to tell the current story.
2. **Independent source provenance:** Stage 5 documents are independently sourced and hash/manifest controlled.
3. **Abstention behavior:** unsupported rejection and false-support are measured separately from retrieval quality.
4. **Runtime convergence:** API and WebUI grounded behavior share the same orchestration boundary.
5. **Reproducibility:** tests, manifests, fixed benchmark files, and historical reports provide a useful audit trail.
6. **Local/private positioning:** the project does not depend on a hosted inference API for its core path.

## Material unresolved items

### P1 — Independent review gap

Stage 5 benchmark cases are automatically generated and unreviewed. This is the largest evidence gap for a buyer claiming external validation.

**Close by:** obtain independent technical review, ingest corrections, freeze accepted cases, rerun the untouched evaluator, and publish reviewer methodology without exposing private reviewer data.

### P1 — Third-party/IP inventory

The repository has a custom source-available license, historical versions were distributed under earlier terms, dependencies have their own licenses, Stage 5 documents have IETF Trust rights/notices, and model/checkpoint rights must be separately confirmed.

**Close by:** produce a machine-readable dependency/license inventory plus a human-readable rights matrix covering source code, models, tokenizer/data, RFC evaluation corpus, and any externally obtained artifacts.

Important: prior permissions already granted for earlier releases cannot simply be revoked retroactively. Strategic diligence should describe that history accurately rather than imply exclusivity that does not exist.

### P1 — Production security boundary

No built-in authentication, TLS termination, tenant isolation, or production-grade rate limiting is claimed.

**Close by:** either implement a minimal authenticated single-tenant deployment profile or explicitly package RALG as an internal/trusted-network component behind an external gateway and document the reference architecture.

### P1 — Current Docker lifecycle evidence

Compose syntax and packaging exist, but a current clean end-to-end container lifecycle should be run against the post-#47/#49 master.

**Close by:** build from a clean checkout, mount required artifacts, verify health/readiness, ingest/query/provenance/delete/restart, record image digest and environment, and archive the report.

### P2 — Multi-process lifecycle safety

Mutation locking is process-local.

**Close by:** keep the controlled reference deployment single-worker, or implement an external/shared transaction/locking mechanism before claiming horizontal application-worker scaling.

### P2 — Larger corpus qualification

100k retrieval has been measured; 250k/500k runs remain deferred for hardware-safety reasons.

**Close by:** validate on a higher-memory machine and record RSS, indexing time, query latency, and soak behavior.

### P2 — Historical-code complexity

Training/research code remains broad and can make diligence harder.

**Close by:** create an active-vs-legacy inventory and dependency map. Archive/refactor only after proving no release/evaluation dependency is lost.

## Licensing / exclusivity caution

The current repository license is source-available/non-commercial, not OSI open source. The license itself states that prior grants remain effective for versions distributed under earlier licenses. A potential buyer should therefore evaluate exactly which commits/assets are exclusive, which were previously published, and what rights were already granted.

This does not prevent a technology transaction, but it matters when describing exclusivity, resale rights, and the value of unpublished/private artifacts.

## Recommended buyer/pilot diligence package

A clean diligence room should contain:

- exact evaluated commit/tag;
- architecture diagram and runtime path;
- API/SDK quick start;
- one-command or documented clean deployment;
- current CI/test evidence;
- Stage 5 source manifest and reviewed benchmark when available;
- benchmark methodology and raw machine-readable output;
- known-failure examples;
- dependency/license/SBOM inventory;
- model/checkpoint rights matrix;
- security boundary and deployment assumptions;
- production-vs-evaluation-vs-training file inventory;
- list of explicitly deferred/unvalidated claims.

## Recommended next milestone

The highest-value next milestone is **diligence closure**, not another internally generated benchmark:

1. independent Stage 5 review;
2. current Docker lifecycle validation;
3. dependency/model/data rights inventory;
4. minimal secure deployment profile or gateway reference architecture;
5. reproducible buyer demo bundle tied to a fixed commit.

Once those are complete, the repository will be substantially easier for a technical acquirer or pilot customer to evaluate without relying on developer-specific context.
