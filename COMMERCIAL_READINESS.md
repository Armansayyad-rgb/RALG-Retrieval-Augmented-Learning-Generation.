# Commercial Readiness

This document describes RALG's public technical/commercial readiness without exposing private strategy, prospect lists, negotiation notes, or valuation targets.

## Current stage

RALG is a controlled technical-evaluation / pilot-oriented product, not a hardened public SaaS service.

Current `master` includes:

- shared grounded execution for API and WebUI;
- document-scoped retrieval;
- evidence/provenance/conflict-aware support gating;
- runtime document ingestion, persistence, listing, deletion, and restart recovery;
- stable document IDs and scoped querying;
- API and lightweight SDK flows;
- deterministic benchmark/evaluation tooling;
- portability and third-party attribution hardening;
- frozen holdout integrity tooling and preserved blind-result evidence;
- explicit security/deployment limitations.

These are engineering checkpoints, not customer adoption, revenue, production-SLA, safety-certification, or acquisition-value guarantees.

## Strongest current blind evidence

The strongest frozen blind result currently committed on `master` is Holdout V2:

- 70 cases across 7 technical domains;
- 40 retrieval-supported cases;
- 30 unsupported/adversarial gate cases;
- RALG Recall@1/3/5: **100% / 100% / 100%** on the ranked subset;
- RALG MRR: **1.000** on the ranked subset;
- unsupported rejection: **93.33% (28/30)**;
- false-support rate: **6.67% (2/30)**.

The result is preserved at:

```text
evaluation/results/holdout_v2_blind_once.json
```

The two false-support failures were analyzed only after the blind run. A generalized post-blind fix and development regressions were added without rerunning or rewriting the original result.

### Evidence boundary

Holdout V2 is strong internal independent evidence, but its source notes were authored validation material derived from public documentation. It is not third-party or acquisition-grade external validation.

## Current development reliability evidence

A separate 50-case live reliability benchmark reached the following validated hardening checkpoint:

| Metric | Result |
| --- | ---: |
| Supported correctness | **100%** |
| Unsupported rejection | **100%** |
| False-support rate | **0%** |
| False-rejection rate | **0%** |
| API errors | **0** |

This benchmark is development/regression evidence, not an untouched independent holdout.

## What is demonstrated today

- local/private technical-document ingestion and grounded question answering;
- evidence-oriented answers with source/provenance handling;
- conservative unsupported/false-premise behavior on validated sets;
- one shared grounded runtime boundary across API and WebUI;
- document-scoped retrieval with safe invalid-scope behavior;
- factual, comparison, procedural, and bounded reasoning paths;
- persistent runtime documents and restart recovery;
- deterministic test and benchmark harnesses;
- API, WebUI, SDK, and Docker/Compose packaging;
- explicit deployment/security boundaries;
- reproducible frozen-holdout evidence preservation.

## Material gaps before stronger commercial claims

1. **Authoritative-source blind validation** — stronger evidence should use authoritative upstream technical documents with frozen provenance, benchmark, evaluator, and contamination controls.
2. **External/customer validation** — no customer production deployment, revenue, or third-party benchmark authoring is claimed.
3. **Security boundary** — no built-in production auth/authorization, TLS termination, tenant isolation, or production-grade rate limiting.
4. **Multi-process lifecycle safety** — process-local mutation locking means the validated deployment profile is single application worker unless external coordination is added.
5. **Container qualification** — Compose configuration exists, but a current full end-to-end production-container qualification remains a separate diligence item.
6. **Large-corpus/concurrency qualification** — larger-scale and broader operational qualification should be reported separately from retrieval quality.
7. **Dependency/IP diligence** — third-party dependency, model, dataset, and document-source rights require a maintained inventory and human/legal review where necessary.
8. **Model/checkpoint distribution** — required private/local model assets must have explicit ownership and redistribution status.

## Technical diligence priorities

Before a serious strategic, licensing, pilot, or buyer diligence process, be able to provide:

- a clean release/evaluation commit or tag;
- architecture and runtime-path documentation;
- benchmark methodology and machine-readable results;
- source provenance and exact hashes;
- exact benchmark/evaluator hashes for frozen blind runs;
- preserved negative/failure evidence;
- dependency and third-party license inventory;
- model/checkpoint ownership and redistribution status;
- clean-install and deployment reproduction steps;
- security boundary and known limitations;
- an asset inventory distinguishing production, evaluation, training, and legacy code;
- a clear separation between internal, independent, authoritative-source, third-party, and customer evidence.

See [Technical Diligence Status](docs/TECHNICAL_DILIGENCE_STATUS.md).

## Safe positioning

> RALG Engine is a local, evidence-grounded technical-document intelligence engine with provenance-backed answers, conservative abstention, document-scoped retrieval, and reproducible evaluation.

## Suggested target users

- manufacturing and maintenance teams;
- industrial documentation groups;
- internal technical-support teams;
- engineering/operations teams with manuals, SOPs, standards, and policies;
- organizations evaluating local/private document intelligence.

## Security/deployment boundary

Treat the current system as trusted-environment software unless deployment controls are provided externally. Do not present the default service as safe for direct public-internet exposure.

## Keep private

Do not store in the public repository:

- valuation or minimum-price targets;
- acquisition strategy or buyer lists;
- negotiation notes;
- private customer/prospect data;
- proprietary customer documents;
- credentials/tokens;
- private model weights or licensed assets that cannot be redistributed.

## Public-reporting rules

Always distinguish:

- historical evidence;
- development/regression evidence;
- synthetic evidence;
- frozen blind evidence;
- authoritative-source evidence;
- third-party/customer validation;
- targets or planned work.

Never present an internally authored, synthetic, development, or unreviewed result as customer-validated production performance.
