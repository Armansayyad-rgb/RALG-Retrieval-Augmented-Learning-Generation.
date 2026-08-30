# Commercial Readiness

This document describes RALG's current technical/commercial readiness without asserting customer adoption, transaction value, or production guarantees.

## Current stage

RALG is a code-frozen technical-evaluation / pilot-oriented product, not a hardened public SaaS service. The repository demonstrates a substantial local technical-document runtime, but real customer deployment evidence and fresh post-freeze blind quality evidence remain outstanding.

Current `master` includes shared grounded execution for API and WebUI, document-scoped retrieval, evidence/provenance/conflict-aware support gating, runtime document ingestion/persistence/deletion/restart recovery, API/client flows, security/deployment controls for a documented single-tenant profile, reproducible dependency locking, deterministic evaluation tooling, and preserved frozen holdout evidence.

These are engineering properties, not customer adoption, revenue, production-SLA, safety-certification, or valuation guarantees.

## Frozen blind evidence

### Holdout V2

Holdout V2 is the strongest **positive internal blind result** currently preserved:

- 70 cases across 7 authored technical source notes;
- 40 ranked-retrieval cases: Recall@1/3/5 = **100% / 100% / 100%**, MRR = **1.000**;
- 30 unsupported/adversarial gate cases: unsupported rejection = **93.33% (28/30)**, false-support = **6.67% (2/30)**;
- preserved false-support failures: `holdout_v2_025`, `holdout_v2_030`.

Artifact: `evaluation/results/holdout_v2_blind_once.json`.

Result SHA-256 recorded by the freeze documentation: `f6925b819a2bdd1cc718898a168bc2dafb701fb85e9169e709b8c7766be0798f`.

Holdout V2 is internal blind evidence. Its source notes were authored from public technical documentation, so it is not third-party, customer, or external validation.

### Holdout V3

Holdout V3 is an immutable authoritative-source independent blind holdout and must be presented alongside V2 rather than omitted. Its frozen 120-case result exposed severe limitations in the then-frozen system/evaluator state:

- Recall@1/3/5 = **43.33% / 58.67% / 60.67%** across 75 retrieval-supported cases;
- MRR = **0.5404**;
- supported-correct = **6/70**, false-rejection = **64/70**;
- correct-rejection = **1/45**, false-support = **44/45**;
- qualified-correct = **0/5**;
- runtime errors = **0**.

Artifact: `evaluation/results/holdout_v3_blind_once.json`.

This result is negative evidence, not a positive quality claim. It was preserved rather than rerun after later generalized engineering corrections. V3 must not be described as proof of production accuracy or strong rejection performance.

## Development/regression evidence

A separate 50-case live reliability benchmark has recorded a hardening checkpoint with 100% supported correctness, 100% unsupported rejection, 0% false support, 0% false rejection, and 0 API errors. This is **development/regression evidence**, not an untouched blind holdout.

Stage 5 and the Authoritative Technical Dev Set are also development evidence where cases/failure modes were available during engineering.

## What is demonstrated today

- local/private technical-document ingestion and grounded question answering;
- evidence/provenance handling and conservative support gating;
- shared API/WebUI grounded runtime;
- document-scoped retrieval and runtime document lifecycle operations;
- restart recovery and tested rollback/fault behavior;
- API/client/Docker packaging and deterministic preflight tooling;
- Python 3.11 deployment contract and hash-locked Linux dependency workflow;
- explicit single-tenant security/deployment boundaries;
- reproducible preservation of positive and negative frozen-holdout evidence.

## Material gaps before stronger commercial claims

1. **Fresh post-freeze blind evidence (V4)** — required to measure the final frozen engineering state without rewriting V1/V2/V3.
2. **Human review** — Stage 6 tooling exists, but no completed reviewer-label artifact is frozen.
3. **Customer/pilot validation** — no production customer deployment, revenue, ROI, or third-party benchmark authoring is claimed.
4. **IP/provenance closure** — `data/train.txt` and custom checkpoint lineage remain excluded from commercial distribution until provenance is resolved; WikiText license-version ambiguity remains disclosed.
5. **Security boundary** — current evidence supports the documented single-tenant profile, not enterprise multi-tenant isolation, built-in TLS, SSO/RBAC, or distributed rate limiting.
6. **Performance boundary** — retrieval-only performance measurements must not be represented as API/generation/end-to-end throughput.

## Readiness checklist

| Item | Status | Evidence / boundary |
|---|---|---|
| Engineering code freeze | Complete | Final pre-freeze regression approved; subsequent changes are documentation/release hygiene only |
| Python 3.11 release/dependency contract | Complete | CI, Docker, `requirements.lock.txt` |
| API/runtime/security regression coverage | Complete for tested profile | Repository contract/hardening suites |
| Holdout V1 preserved | Complete | Historical/diagnostic only; never rerun |
| Holdout V2 preserved | Complete | Frozen internal blind result; never rerun |
| Holdout V3 preserved | Complete | Frozen authoritative-source negative result; never rerun |
| Claims/evidence source of truth | Complete | `docs/CLAIMS_EVIDENCE_MATRIX.md` |
| IP/release boundaries documented | Complete with exclusions | `docs/IP_PROVENANCE_AND_RELEASE_BOUNDARIES.md`, `docs/DATA_RIGHTS_INVENTORY.md` |
| Human validation | Incomplete | Review tooling exists; labels pending |
| Fresh V4 blind evidence | Incomplete | Not yet created/run |
| Customer/pilot evidence | Incomplete | No genuine external deployment evidence committed |
| Custom checkpoint provenance for distribution | Incomplete / excluded | Must be reconstructed before inclusion in transaction/release package |
| `data/train.txt` provenance | Incomplete / excluded | Do not distribute commercially until resolved |
| Legal review of transaction/license terms | External review | Counsel review required for an actual transaction/commercial license |

## Technical diligence package

A serious pilot, licensing, or transaction process should be able to provide a clean release/evaluation commit or tag, architecture/runtime documentation, exact benchmark methodology and machine-readable results, source provenance/hashes, preserved failures, dependency and third-party inventory, model/checkpoint ownership status, clean-install/deployment steps, security limitations, and an asset inventory separating production, evaluation, training, legacy, and excluded materials.

The controlling claim document is `docs/CLAIMS_EVIDENCE_MATRIX.md`. The controlling provenance documents are `docs/IP_PROVENANCE_AND_RELEASE_BOUNDARIES.md`, `docs/DATA_RIGHTS_INVENTORY.md`, and `THIRD_PARTY_NOTICES.md`.

## Safe positioning

> RALG Engine is a local, evidence-grounded technical-document intelligence engine with provenance-oriented answers, conservative support gating, document-scoped retrieval, and reproducible evaluation infrastructure.

This positioning describes implemented capabilities; it does not assert global accuracy, customer validation, production readiness, or transaction value.

## Suggested target users

Potential evaluation/pilot users include manufacturing and maintenance teams, industrial documentation groups, internal technical-support teams, and engineering/operations groups working with manuals, SOPs, standards, policies, or other private technical knowledge.

## Security/deployment boundary

Treat the current system according to `SECURITY.md`. Do not infer public-internet, multi-tenant, enterprise-authentication, or distributed-control guarantees beyond that documented profile.

## Keep private

Do not place valuation targets, transaction strategy, prospect lists, negotiation notes, private customer/prospect data, proprietary customer documents, credentials/tokens, or non-redistributable model/data assets in the public repository.

## Reporting rules

Always distinguish historical, development/regression, synthetic, frozen blind, authoritative-source, human-reviewed, and customer evidence. Preserve negative evidence. Never present an internally authored, development-exposed, unreviewed, or retrieval-only result as customer-validated end-to-end production performance.
