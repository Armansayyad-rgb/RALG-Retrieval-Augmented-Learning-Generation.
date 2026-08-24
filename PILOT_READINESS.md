# RALG Customer Pilot Readiness

This checklist tracks the minimum technical evidence required before RALG should be offered to an external customer for a limited pilot. It is intentionally stricter than a demo checklist and does not imply production readiness.

## Current checkpoint

Prototype 1 RC1 (`0.1.0-rc1`) is immutable at validated commit
`c210eb8ae168a740b65189fc9245034dfe58e40e`. The default UI is local-only;
network exposure requires an operator-controlled boundary. Validation is
isolated and synthetic, not customer-data testing.

The current `master` branch has demonstrated the following on the repository's synthetic held-out commercial validation set:

- retrieval correctness: 5/5 supported cases
- answer completeness: 5/5 supported cases
- unsupported rejection: 5/5 unsupported cases
- safe abstention: 5/5 unsupported cases
- false-support rate: 0%
- runtime errors: 0
- average API latency: about 1.3 seconds on the measured local run
- regression suite: 23/23 passed
- existing simple and hard retrieval benchmarks: passed
- GitHub Actions sanity workflow: passed on `master`

These results are engineering evidence only. The held-out set is small and
synthetic, and validation is isolated; they should not be presented as
production performance or network/security validation.

## Pilot gate

A limited customer pilot should not begin until every required item below is complete or explicitly accepted as a documented pilot risk.

### Reliability

- [x] supported and unsupported questions are evaluated separately
- [x] false-support behavior is measured
- [x] runtime-ingested documents can be distinguished from the static corpus without hard-coded corpus-size assumptions
- [x] a held-out commercial validation set exists and is reproducible with one command
- [ ] expand held-out evaluation beyond the current small synthetic set
- [ ] add realistic or independently sourced manuals/SOPs with clear usage rights
- [ ] preserve representative failure examples alongside aggregate metrics

### Evidence integrity

- [x] API responses can return source evidence
- [x] factual-answer extraction is grounded against matching retrieved chunks
- [x] automated traceability checks require supported answers to match returned evidence
- [x] conflicting high-relevance evidence is handled conservatively rather than presented as a settled fact
- [ ] make answer-generation provenance and returned citations share the exact same evidence object rather than reconstructing citations after answering

### Security and input handling

- [x] public security boundaries are documented in `SECURITY.md`
- [x] explicit API request/text/query limits are enforced
- [ ] verify filename/path sanitization for uploaded documents
- [ ] test malformed PDF, DOCX, and TXT upload handling end to end
- [x] external API exception details are not returned to untrusted clients
- [ ] define retention/deletion behavior for uploaded documents, indexes, logs, and feedback
- [x] add explicit UI upload-size limits matching the documented pilot policy
- [x] document that upload/delete locking is process-local only

### Reproducibility and deployment

- [x] GitHub Actions CI exists and passes on `master`
- [x] manual CI dispatch is available
- [x] a Windows test runner is documented
- [x] installation from a fresh disposable Python 3.11 environment has been verified
- [ ] verify Docker build and startup from a clean checkout
- [x] validated direct dependency versions are pinned for the current checkpoint
- [x] optional Qwen polish dependencies are isolated from core installation
- [ ] tag a reproducible pilot candidate commit

### Performance

- [x] API latency is measured in the held-out validation runner
- [ ] record peak RAM usage on representative CPU hardware
- [ ] record peak VRAM usage when CUDA is enabled
- [ ] measure ingest time and query latency at multiple corpus sizes
- [ ] define a practical pilot latency target and failure threshold

### Pilot operations

- [ ] choose one narrow customer/document domain
- [ ] define accepted file types and maximum file sizes for that pilot
- [ ] define a pilot-specific evaluation set before tuning on customer failures
- [ ] define what data may be logged
- [ ] define a deletion/export procedure for customer data
- [ ] require human review for safety-critical or high-impact answers

## Recommended next engineering checkpoint

The next checkpoint should focus on measured scale and remaining operational hardening rather than additional retrieval-score tuning:

1. record RAM/VRAM and ingest/query performance at multiple corpus sizes;
2. harden PDF/DOCX/TXT upload limits, errors, provenance, and deletion behavior;
3. make citation provenance originate from the exact evidence used by answer generation;
4. verify Docker build/start on a clean checkout;
5. expand the held-out set with realistic licensed technical documents.

Only after those gates are stable should the project move to a real external pilot.
