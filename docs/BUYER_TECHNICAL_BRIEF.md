# RALG Engine — Technical Brief for Buyers

**Status line:** technical qualification complete; independent human review of benchmark evidence pending.

---

## What RALG does

RALG Engine is a local, retrieval-augmented question-answering system for
technical document corpora. It answers questions **only** when retrieved
evidence supports the answer, returns that evidence with provenance, and
visibly abstains when the corpus does not contain an answer. It is not a
chatbot over model memory: unsupported questions do not get invented answers.

## Target use cases

- Technical-document Q&A over controlled corpora (standards, RFCs, manuals,
  policies)
- Compliance/support workflows where fabricated answers are unacceptable
- Evidence-backed internal knowledge tools for single-tenant deployment

## Architecture summary

```
API (FastAPI) / WebUI (Gradio)
  -> execute_runtime()            shared orchestration boundary
  -> ExecutionPlan                intent + route decision
  -> factual extractor OR grounded reasoning
  -> retriever_hybrid             full-question-first hybrid retrieval
  -> unified support gate         evidence identity, traceability,
                                  conflict status, provenance
  -> supported answer OR abstention
```

- **Hybrid retrieval:** `retriever_hybrid` fuses full-question lexical
  candidates with bounded secondary sub-query passes; `retriever_v2` is the
  core lexical index. One authoritative retrieval path.
- **Evidence-grounded answering:** accepted answers cite identifiable spans.
- **Abstention/support gate:** answers lacking support are refused; measured
  false-support rate on Stage 5: 0% (preliminary).
- **Provenance:** source document, excerpt, and attribution per answer.
- **Small local models:** SmallLM V2 (~230 MB checkpoint) + tokenizer;
  optional Qwen2.5-1.5B polish LLM. No external AI APIs.

## Measured results (Stage 5 preliminary — NOT independently reviewed)

300 auto-generated cases over 50 independently sourced IETF RFC documents
(`status: preliminary_unreviewed`):

| Metric | Lexical | RALG hybrid |
|---|---|---|
| Recall@1 | 40.48% | 50.95% |
| Recall@3 | 87.62% | 90.95% |
| Recall@5 | 100% | 100% |
| MRR | 0.6485 | 0.7098 |
| Unsupported rejection | 100% | 100% |
| False-support rate | 0% | 0% |

The authoritative artifact (`evaluation/results/stage5_preliminary_results.json`) was regenerated from frozen code and reproduces exactly these values; the earlier pre-hybrid run is preserved as `..._legacy.json`. Provenance and both metric sets: `docs/STAGE5_EVIDENCE_HISTORY.md`. Latency: lexical p50 ≈ 187–206 ms on reference workstations (machine-specific, not a claim).

A deterministic 75-case pilot review pack is prepared for independent human
reviewers; full-review pack covers all 300 cases
(`docs/STAGE6_HUMAN_REVIEW_GUIDE.md`).

## Deployment

- Local Docker image `ralg-engine:latest`; WebUI on `127.0.0.1:7860`;
  named volumes for data/logs/checkpoints; healthcheck included.
- Docker lifecycle qualification: **19/19 PASS** in controlled environment
  (`scripts/test_docker_lifecycle.py`) including `docker restart` recovery.
- Reproducible buyer demo: `docs/BUYER_DEMO_GUIDE.md`,
  `scripts/run_buyer_demo.ps1`.

## Dependency / IP / data-rights audit

- 15 runtime dependencies audited; all OSI-approved (MIT, Apache-2.0,
  BSD-3-Clause); zero copyleft in the runtime path.
- Corpus rights documented (IETF Trust Legal Provisions; WikiText CC-BY-SA-3.0
  for training data). PyPDF2 (BSD-3-Clause) flagged for pypdf migration.
- Full detail: `docs/DEPENDENCY_AND_IP_AUDIT.md`, `docs/DATA_RIGHTS_INVENTORY.md`.

## Security boundary (current)

- No built-in authentication, no TLS termination, no tenant isolation, no
  production-grade rate limiting. Documented as a local/trusted-network
  component only.
- Single-worker deployment; process-local mutation locking.
- Uploaded documents are untrusted input (parsing hardened and tested).

## Current limitations

1. Stage 5 cases are auto-generated and not yet independently human-reviewed.
2. No auth/TLS — must sit behind a gateway or remain trusted-network only.
3. Single-worker scale; 250k/500k-chunk tests deferred.
4. Optional polish LLM may fail to load (non-blocking fallback).
5. PyPDF2 deprecation (migration to pypdf recommended).
6. Stage 5 was used during architecture development; it is not a pristine
   final holdout set (see `docs/STAGE5_EVIDENCE_HISTORY.md`).

## What we do not claim

No production-readiness claim, no multi-tenant security claim, no independent
validation claim until genuine human review artifacts exist. Claim-by-claim
mapping with sources: `docs/CLAIMS_EVIDENCE_MATRIX.md`.
