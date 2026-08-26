# Claims / Evidence Matrix

Buyer-facing mapping of each meaningful claim to its evidence, source, and
current status. Statuses:

- **VERIFIED** — reproducible from committed artifacts/tests in this repo
- **PRELIMINARY** — measured, but auto-generated benchmark, not independently human-reviewed
- **NOT YET VALIDATED / DO NOT CLAIM** — no supporting evidence exists

---

## Retrieval & answering quality

| Claim | Evidence | Source file/test | Status |
|---|---|---|---|
| Unsupported rejection = 100% on Stage 5 (both systems) | Committed metrics artifact | `evaluation/results/stage5_preliminary_results.json` | PRELIMINARY (auto-generated cases; human review pending) |
| False-support rate = 0% on Stage 5 | Committed metrics artifact | same as above | PRELIMINARY |
| Stage 5 corpus is independent, permission-cleared IETF RFC content | 50-doc manifest, all confirmed/permitted/non-synthetic | `evaluation/stage5_source_manifest.jsonl`, `evaluation/results/stage5_integrity_report.json` | VERIFIED (provenance); PRELIMINARY (case quality) |
| "RALG improves Recall@1 vs lexical" (50.95% vs 40.48%) | Narrative docs vs committed artifact disagree (artifact: 37.14%) | `README.md` / `COMMERCIAL_READINESS.md` vs `stage5_preliminary_results.json`; freeze record §5 | NOT YET VALIDATED — discrepancy recorded in `docs/STAGE6_VALIDATION_FREEZE.md`, adjudication required |
| Answer provenance/evidence trace works end-to-end | Traceability + conflict test suites | `src/test_traceability.py` (7), `src/test_conflict_detection.py` (9), `src/test_unified_evidence.py` (10) | VERIFIED (in-repo tests) |
| Grounded abstention behavior | Regression unsupported-premise suite | `src/regression_tests_v2.py` (6 unsupported cases) | VERIFIED (in-repo tests) |

## Engineering qualification

| Claim | Evidence | Source file/test | Status |
|---|---|---|---|
| Core suite passes 118/118 | Test suites sum (23+8+7+9+25+8+8+10+10+10) | `scripts/test_all.bat` steps 5–12 | VERIFIED |
| Docker lifecycle qualifies 19/19 incl. restart recovery via `docker restart` | Lifecycle script, Phase 6 uses `docker restart <container>` | `scripts/test_docker_lifecycle.py`; `docs/ACQUISITION_DILIGENCE_FINAL_REPORT.md` §26–32 | VERIFIED (controlled local environment) |
| API input hardening (oversized/blank/extra-field rejection) | 8-case hardening suite | `src/test_api_input_hardening.py` | VERIFIED |
| Upload parsing/provenance/duplicate detection robustness | 25-case upload suite | `src/test_upload_provenance.py` | VERIFIED |
| Document persistence survives registry corruption and restarts | Persistence suite | `src/test_document_persistence.py` (8) | VERIFIED |
| API/WebUI behavioral parity via shared `execute_runtime()` | Integration tests | `src/test_runtime_integration.py` | VERIFIED |
| All runtime dependencies OSI-approved, zero copyleft | Dependency audit | `docs/DEPENDENCY_AND_IP_AUDIT.md`, `docs/dependency_inventory.json` | VERIFIED (as of audit date) |

## Review process (Stage 6)

| Claim | Evidence | Source file/test | Status |
|---|---|---|---|
| Blind reviewer pack contains no model-performance leakage | Blinding check passes on pack | `scripts/stage5_review_blinding_check.py`, `evaluation/stage5_review_pack/review_pack_manifest.json` | VERIFIED (tooling) |
| Deterministic 75-case pilot (seed 5202025; 38 supported / 37 unsupported) | Regeneration reproduces shipped pilot exactly | `scripts/stage5_review_pack.py::pilot_sample`; `src/test_stage6_review_tooling.py` | VERIFIED |
| Review ingestion rejects duplicates/unknown IDs/invalid labels/partial rounds | Ingestion guard tests | `src/test_stage6_review_tooling.py` (IngestionGuardTests) | VERIFIED (tooling) |
| Inter-reviewer agreement (raw % + Cohen's kappa) computable | Agreement tool + tests | `scripts/stage6_review_agreement.py`; tests | VERIFIED (tooling; kappa reported as undefined when degenerate) |
| Human reviewers have validated case quality | — | none exists yet | NOT YET VALIDATED — no reviewer artifact ingested |
| Post-review metrics on approved subset available | Evaluator writes `evaluation/results/stage6_human_review_results.json` only after real review files | `scripts/stage6_evaluator.py` | VERIFIED (tooling); output PENDING |

## Explicit non-claims

| Claim | Status |
|---|---|
| "Production-ready" | NOT YET VALIDATED / DO NOT CLAIM |
| "Multi-tenant secure" / internet-safe without gateway | NOT YET VALIDATED / DO NOT CLAIM (no auth/TLS by design) |
| "Independently validated" | DO NOT CLAIM until genuine human review artifacts are ingested and frozen |
| "Beats all baselines" | PRELIMINARY at best; current artifact shows lexical ahead on ranked-recall metrics |
| Any customer, revenue, pricing, or timeline claims | Not made anywhere in this repository |

**Final standing status: REVIEW INFRASTRUCTURE READY — HUMAN REVIEW PENDING.**
