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

These are engineering checkpoints, not customer adoption, revenue, production-SLA, safety-certification, or transaction-value guarantees.

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

Holdout V2 is strong internal independent evidence, but its source notes were authored validation material derived from public documentation. It is not third-party or external validation.

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
3. **Security boundary** — deployment controls must match the documented single-tenant security profile.
4. **Multi-process lifecycle safety** — process-local mutation locking means the validated deployment profile is single application worker unless external coordination is added.
5. **Container qualification** — Compose configuration exists, but a current full end-to-end production-container qualification remains a separate technical-review item.
6. **Large-corpus/concurrency qualification** — larger-scale and broader operational qualification should be reported separately from retrieval quality.
7. **Dependency/IP diligence** — third-party dependency, model, dataset, and document-source rights require a maintained inventory and human/legal review where necessary.
8. **Model/checkpoint distribution** — required private/local model assets must have explicit ownership and redistribution status.
9. **Readiness checklist** — all items below must have repository evidence; unmarked items require external legal/provenance review.

### Technical and Commercial Readiness Checklist

| Category | Item | Evidence / Reference | Status |
|---|---|---|---|
| Complete | Repo baseline commit/tag identified | `git log --oneline -1` shows current SHA | |
| Complete | License clearly documented | `LICENSE` file present, RALG Source-Available Non-Commercial License v1.0 | |
| Complete | Dependency inventory maintained | `requirements.txt` with pinned versions; `THIRD_PARTY_NOTICES.md` covers data/model licenses | |
| Complete | Model provenance documented | `config.py` model/tokenizer paths; `THIRD_PARTY_NOTICES.md` lists checkpoint/Qwen status | |
| Complete | Source manifest with hashes | `evaluation/stage5_source_manifest.jsonl` (50 IETF RFCs with SHA-256); `holdout_v2/sources_manifest.jsonl` (7 sources) | |
| Complete | Holdout V2 blind result preserved | `evaluation/results/holdout_v2_blind_once.json` immutable; SHA-256: `f6925b819a2bdd1cc718898a168bc2dafb701fb85e9169e709b8c7766be0798f` | |
| Complete | Holdout V1 historical preserved | `evaluation/holdout_v1/` unchanged; not rerun after fix | |
| Complete | Claims-to-evidence matrix | `docs/CLAIMS_EVIDENCE_MATRIX.md` with VERIFIED/PRELIMINARY/NOT YET VALIDATED labels | |
| Complete | Security boundary documented | `SECURITY.md` | |
| Complete | Reproduction steps documented | `README.md` local Python and Docker commands; `PORTABILITY_READINESS.md` | |
| Complete | Docker lifecycle validation evidence | `docs/ACQUISITION_DILIGENCE_FINAL_REPORT.md` §26–32: 19/19 PASS on its recorded branching commit | |
| Complete | Regression coverage | Repository test suites cover regression, hardening, API, traceability, persistence, and related contracts | |
| Incomplete | Independent Stage 5 human review | Stage 5 cases auto-generated, unreviewed; human review pending (see `docs/STAGE6_HUMAN_REVIEW_GUIDE.md`) | |
| Incomplete | Full Docker end-to-end qualification | Lifecycle evidence exists on an earlier branching commit; current-master qualification is tracked separately | |
| Incomplete | Large-scale validation | Higher-scale qualification remains separate from current retrieval evidence | |
| Incomplete | Multi-tenant deployment profile | Current documented profile is single-tenant/trusted-environment oriented | |
| Incomplete | Optional polish LLM integration | Optional model path is separate from the core runtime | |
| Incomplete | PyPDF2 migration to pypdf | Dependency modernization is a separate maintenance item | |
| External review | IETF RFC redistribution permissions | See `THIRD_PARTY_NOTICES.md` and source manifests | |
| External review | Model checkpoint redistribution rights | `checkpoints/v2/reasoning_model_v1.pt` is not committed; provenance/redistribution must be confirmed before distribution | |
| External review | Qwen2.5-1.5B-Instruct license terms | Apache 2.0; optional dependency; see third-party notices | |
| External review | Holdout V3 source license compliance | Upstream source licenses/revisions are documented in third-party notices and manifests | |
| External review | Commercial redistribution permission | RALG Source-Available Non-Commercial License v1.0 restricts commercial use without written permission | |
| Legal review | Prior version license grants | Earlier versions distributed under earlier licenses; prior grants remain effective per Section 8 of LICENSE | |
| Legal review | Source-available license scope | Not OSI-approved open source; commercial redistribution requires permission from the copyright holder | |
| Legal review | Data rights for commercial use | Dataset/source-license ambiguities require verification before commercial distribution | |
| Legal review | Model checkpoint ownership | Custom checkpoint provenance and redistribution status must be documented before distribution | |

## Technical diligence priorities

Before a serious strategic, licensing, pilot, or technical diligence process, be able to provide:

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

Treat the current system according to the deployment profile documented in `SECURITY.md`. Do not infer public-internet or multi-tenant guarantees beyond that documented boundary.

## Keep private

Do not store in the public repository:

- valuation or minimum-price targets;
- transaction strategy or prospect lists;
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
