# Claims / Evidence Matrix

This document is the conservative source of truth for public, technical-diligence, pilot, and transaction-facing claims about the current RALG repository. A claim is usable only within the boundary stated here.

Statuses:

- **VERIFIED** — directly supported by committed implementation/tests or immutable evidence artifacts.
- **FROZEN RESULT** — an immutable evaluation result that may be reported exactly, including negative results and limitations.
- **DEVELOPMENT EVIDENCE** — useful engineering evidence, but not independent validation.
- **HISTORICAL** — preserved evidence from a superseded or development-exposed state; not a current headline claim.
- **NOT VALIDATED / DO NOT CLAIM** — evidence is absent or insufficient.

## Evidence lineage

| Evidence | Nature | Current claim boundary |
|---|---|---|
| Stage 1–4 suites | Synthetic/internal development sets | DEVELOPMENT EVIDENCE only |
| Stage 5 RFC evaluation | Authoritative RFC corpus with auto-generated/development-exposed cases | Source provenance may be cited; performance remains DEVELOPMENT/PRELIMINARY evidence |
| Stage 6 | Human-review tooling | Tooling is verified; no completed human-review labels exist |
| Holdout V1 | Frozen historical holdout; later inspected during reliability work | HISTORICAL/diagnostic; do not describe as untouched post-fix evidence |
| Holdout V2 | 70-case frozen single-shot blind evaluation over seven authored technical source notes | FROZEN RESULT; strong internal blind evidence, not third-party/external validation |
| Holdout V3 | 120-case authoritative-source single-shot blind holdout | FROZEN RESULT, including poor performance; methodology/result must not be rewritten as positive validation |
| Authoritative Technical Dev Set V1 | Authoritative-domain development set | DEVELOPMENT EVIDENCE only; not a blind holdout |
| Future V4 | Not yet created/run | DO NOT CLAIM until protocol, freeze, run, and evidence are complete |

## Frozen blind evaluation results

### Holdout V2 — `holdout_v2.0.0`

Committed result: `evaluation/results/holdout_v2_blind_once.json`.

- 70 total cases.
- 40 ranked-retrieval cases: Recall@1 = 100%, Recall@3 = 100%, Recall@5 = 100%, MRR = 1.000.
- 30 rejection/support-gate cases: unsupported rejection = 93.33% (28/30), false-support = 6.67% (2/30).
- Preserved false-support failures: `holdout_v2_025` and `holdout_v2_030`.
- Result-file SHA-256 recorded by the freeze documentation: `f6925b819a2bdd1cc718898a168bc2dafb701fb85e9169e709b8c7766be0798f`.

**Allowed wording:** frozen single-shot internal blind holdout; authored source notes based on public technical documentation.

**Do not call:** third-party validation, external validation, customer validation, or proof of global accuracy.

### Holdout V3 — `holdout_v3.0.0`

Committed result: `evaluation/results/holdout_v3_blind_once.json`.

The immutable result records 120/120 completed cases and 0 runtime errors. It also records materially poor task performance:

- retrieval-supported denominator: 75;
- Recall@1 = 43.33%, Recall@3 = 58.67%, Recall@5 = 60.67%, MRR = 0.5404;
- answer-supported denominator: 70;
- supported-correct = 6 and false-rejection = 64;
- rejection denominator: 45;
- correct-rejection = 1 and false-support = 44;
- qualified cases = 5, qualified-correct = 0.

Frozen hashes recorded for V3:

- benchmark: `ffe5a18fdd20dc4792ff5834333a599a90258f12f8f73e2197af5a2482648617`;
- sources: `163e1d8b9c4c34303cbbdd3ad062305c26a79151b4e6cd3b5537a0dca2b28b7b`;
- evaluator: `65d23eef535ac6acb78f81596515d546a8ae26c3c2c7b1f2bb54cebedb71050d`;
- result: `0f0c2314baac425e1a49222de7357f530f0754731c435e9fd3c4e026a10f5d89`.

**Allowed wording:** authoritative-source independent blind holdout that exposed substantial ingestion/evaluation/runtime limitations in that frozen system state and motivated later generalized engineering corrections.

**Do not claim:** V3 demonstrates production accuracy, strong rejection, or acquisition-grade model quality. Do not rerun, rewrite, or replace the frozen result.

## Current engineering claims

| Claim | Evidence | Status / boundary |
|---|---|---|
| Unified evidence/provenance/conflict-aware runtime exists | `execute_runtime`, answer-contract/support-gate path, traceability/conflict/unified-evidence tests | VERIFIED implementation claim |
| API and WebUI use the shared runtime path | Runtime integration tests | VERIFIED |
| Runtime document persistence, deletion, restart recovery, and rollback/fault handling are tested | Persistence, exception-consistency, runtime integrity tests | VERIFIED in tested single-process profile |
| API input/security hardening exists | Input validation, optional bearer token, CORS/security headers, request-size and process-local rate-limit tests | VERIFIED feature claim; not equivalent to enterprise multi-tenant security |
| Operational observability/privacy redaction exists | Logging/request-ID/feedback redaction implementation and tests | VERIFIED feature claim |
| Python 3.11 is the supported deployment target | release contract, CI and dependency-lock workflow | VERIFIED |
| Linux Python 3.11 deployment dependencies are hash-locked | `requirements.lock.txt`, Docker `--require-hashes`, CI freshness/install checks | VERIFIED for the documented lock workflow |
| Public Python client/API contract is regression-tested | API/client contract suites | VERIFIED |
| Demo/preflight launch path is deterministic under its tested contract | demo/preflight and launcher tests | VERIFIED for the documented demonstration profile |

## Performance claim boundary

Performance artifacts in this repository include retrieval-focused measurements. They must be described as **retrieval-only** unless the artifact explicitly measures another phase. Do not convert retrieval throughput/latency into API, generation, or end-to-end product throughput. Generation/runtime phases marked `NOT_MEASURED` remain unmeasured.

## Development/regression evidence

The 50-case reliability benchmark has recorded runs with 100% supported correctness, 100% unsupported rejection, 0% false support, 0% false rejection, and 0 API errors after reliability hardening. This is **development/regression evidence**, not an untouched blind benchmark and not a customer result.

Stage 5 and the Authoritative Technical Dev Set are likewise development evidence where cases or failure modes were available during engineering. Their scores may be reported only with that qualification.

## Human review

Stage 6 contains deterministic blind-pack, ingestion-guard, and agreement tooling. Those tooling capabilities may be claimed as implemented/tested. No completed reviewer-label artifact has been ingested and frozen, so **human validation has not been completed**.

## Security/deployment non-claims

The current deployment profile is a single-tenant application profile with optional bearer authentication and process-local controls. The repository does **not** establish:

- production multi-tenant isolation;
- enterprise identity/SSO/RBAC;
- built-in TLS termination;
- distributed rate limiting;
- internet-safe deployment without an appropriate gateway/reverse proxy and operational controls.

Do not use “enterprise secure” or “multi-tenant secure” as an unqualified claim.

## IP / data-rights claim boundary

Use `docs/IP_PROVENANCE_AND_RELEASE_BOUNDARIES.md`, `docs/DATA_RIGHTS_INVENTORY.md`, and `THIRD_PARTY_NOTICES.md` as the controlling provenance documents.

In particular:

- `data/train.txt` has incomplete provenance and is excluded from commercial release distribution until resolved;
- custom SmallLM checkpoint lineage is not sufficiently reconstructed for an acquisition/release package and is excluded until provenance is established;
- WikiText license-version ambiguity must remain disclosed;
- historical MIT grants remain part of the repository's licensing history and are not retroactively revoked by the current source-available license.

Do not claim the entire repository/data/model package is “IP clean”, “third-party clear”, or transaction-ready without these qualifications and appropriate legal review.

## Explicit non-claims

| Claim | Status |
|---|---|
| “Production-ready” as a blanket product claim | DO NOT CLAIM; engineering qualification is substantial but real deployment/customer evidence is not complete |
| “Independently validated” without naming the exact frozen holdout and methodology | DO NOT CLAIM |
| “Human validated” | DO NOT CLAIM; reviewer labels are pending |
| “Beats all baselines” | DO NOT CLAIM |
| “Zero hallucinations” / “100% accurate” | DO NOT CLAIM |
| “Enterprise secure” / “multi-tenant secure” | DO NOT CLAIM |
| API/product/generation throughput inferred from retrieval-only measurements | DO NOT CLAIM |
| Customer adoption, revenue, ROI, or production deployment | DO NOT CLAIM unless genuine external evidence is later added |
| A specific company valuation or acquisition price | DO NOT CLAIM as a technical fact |
| V4 results | DO NOT CLAIM; V4 has not yet been executed |

## Reporting rules

1. Name the exact evidence artifact and evidence class.
2. Keep retrieval, answer correctness, rejection, false-support, latency, and runtime-error metrics separate.
3. Preserve negative results and known failures.
4. Never rerun or rewrite V1/V2/V3 to improve a headline result.
5. Never weaken thresholds, labels, or benchmark cases to force a pass.
6. Do not generalize a benchmark result beyond its corpus, denominator, and methodology.
7. Distinguish tested engineering properties from real customer/production validation.
8. Keep IP/provenance qualifications attached to commercial-release statements.
9. New public claims should be added here only after the supporting artifact is committed and reviewed.

**Current standing:** ENGINEERING CODE FROZEN; LEGAL/IP RELEASE BOUNDARIES DOCUMENTED; V1/V2/V3 PRESERVED; HUMAN REVIEW PENDING; FRESH V4 EVIDENCE NOT YET RUN.
