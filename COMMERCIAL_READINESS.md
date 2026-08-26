# Commercial Readiness

This document describes RALG's public technical/commercial readiness without exposing private strategy, prospect lists, negotiation notes, or valuation targets.

## Current stage

RALG is a controlled-pilot technical product, not a hardened public SaaS service.

The current `master` includes:

- shared `ExecutionPlan` / `execute_runtime()` orchestration for API and WebUI;
- full-question-first hybrid grounded retrieval;
- unified support/provenance/conflict gating;
- document ingestion, persistence, listing, deletion, and restart recovery;
- API and lightweight SDK flows;
- deterministic benchmark/evaluation tooling;
- synthetic and independently sourced evaluation corpora;
- reproducibility, portability, soak, scale, and lifecycle evidence.

These are engineering checkpoints, not customer adoption, revenue, production-SLA, or safety-certification claims.

## Current validated engineering checkpoints

- regression suite: **23/23 PASS** in the current integration validation;
- commercial validation: **quality gate PASS**;
- Stage 5 preliminary unsupported rejection: **100%**;
- Stage 5 preliminary false-support rate: **0%**;
- clean Python 3.11 install: previously validated;
- isolated API ingest/query/list/delete/restart lifecycle: previously validated;
- live lightweight SDK integration: previously validated;
- 1000-request / 8-worker soak: previously validated with 0 errors;
- 100k retrieval scale: previously measured; larger 250k/500k runs remain deferred;
- current CI on the core-runtime integration: **PASS**.

## Current preliminary independent-source retrieval result

Stage 5 uses 50 independently sourced IETF RFC documents and 300 automatically generated cases (210 supported / 90 unsupported).

The current untouched preliminary retrieval run records:

| Metric | Lexical | RALG hybrid |
| --- | ---: | ---: |
| Recall@1 | 40.48% | **50.95%** |
| Recall@3 | 87.62% | **90.95%** |
| Recall@5 | 100.00% | **100.00%** |
| MRR | 0.6485 | **0.7098** |
| Unsupported rejection | 100% | **100%** |
| False-support rate | 0% | **0%** |

This is meaningful engineering evidence, but the 300 benchmark cases are still **not independently human-reviewed**. Therefore Stage 5 remains **BLOCKED ON INDEPENDENT REVIEW** and must not be represented as final external validation.

Authoritative artifact: `evaluation/results/stage5_preliminary_results.json` (hybrid run, reproduced from frozen code). Historical pre-hybrid result and provenance: `docs/STAGE5_EVIDENCE_HISTORY.md`.

## What is demonstrated today

- local/private technical-document ingestion and question answering;
- evidence-oriented answers with source/provenance handling;
- conservative unsupported/false-premise behavior in validated sets;
- one shared grounded runtime boundary across API and WebUI;
- deterministic full-question-first hybrid retrieval;
- factual extraction, comparison, reasoning, and bounded multi-hop state;
- persistent runtime documents and restart recovery;
- reproducible test and benchmark harnesses;
- local API, WebUI, SDK, and Docker/Compose packaging;
- explicit security and deployment limitations.

## Material gaps before a stronger commercial pilot

1. **Independent benchmark review** — Stage 5 cases need reviewer acceptance/correction and a frozen reviewed benchmark.
2. **Docker lifecycle qualification** — current Compose is maintained, but a current clean end-to-end Docker run is still required.
3. **Security boundary** — no built-in auth, TLS, tenant isolation, or production-grade rate limiting.
4. **Multi-process lifecycle safety** — process-local mutation locking means the validated pilot deployment is single-worker.
5. **Large-corpus qualification** — 250k/500k measurements are still deferred pending suitable hardware.
6. **Dependency/IP diligence** — maintain an inventory of dependency licenses, third-party data rights, model rights, and historical source-license grants.
7. **Customer evidence** — no customer revenue, reference deployment, or production workload is claimed by this repository.

## Technical diligence priorities

Before any serious strategic, licensing, or buyer diligence process, be able to provide:

- a clean commit/tag representing the evaluation build;
- architecture and runtime-path documentation;
- benchmark methodology and machine-readable results;
- independent-source provenance and hashes;
- explicit negative/failure evidence;
- dependency and third-party license inventory;
- model/checkpoint ownership and redistribution status;
- clean-install and Docker reproduction steps;
- security boundary and known limitations;
- an asset inventory distinguishing production, evaluation, training, and legacy code.

See [Technical Diligence Status](docs/TECHNICAL_DILIGENCE_STATUS.md).

## Safe positioning

> RALG Engine is a local, evidence-grounded technical-document intelligence engine with provenance-backed answers, conservative abstention, a unified grounded runtime, and reproducible retrieval evaluation.

## Suggested target users

- manufacturing and maintenance teams;
- industrial documentation groups;
- internal technical-support teams;
- engineering/operations teams with manuals, SOPs, standards, and policies;
- organizations evaluating local/private document intelligence.

## Keep private

Do not store in the public repository:

- valuation or minimum-price targets;
- acquisition strategy or buyer lists;
- negotiation notes;
- private customer/prospect data;
- proprietary customer documents;
- credentials/tokens;
- private model weights or licensed assets that cannot be redistributed.

## Public-reporting rule

Always distinguish **historical**, **current measured**, **preliminary/unreviewed**, and **target** results. Never present synthetic, unreviewed, or historical results as customer-validated production performance.
