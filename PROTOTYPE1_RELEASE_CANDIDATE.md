# RALG Prototype 1 Release Candidate

## Release identity

**Prototype 1 RC1 (`0.1.0-rc1`)**. This report tests merged commit
`0dac5ebbf7ceac8eaed5ccba53c5b330e4c222bb` on branch `master`, dated
2026-08-24.

## Inventory and architecture

The active runtime is `src/api_server.py` (FastAPI) and
`src/webui/app.py` / `src/webui_bootstrap.py` (Gradio). Retrieval uses V4
multi-query orchestration over V2 exact lexical postings, with V3 and
historical modules retained for research/compatibility. `src/rag_chat_v2.py`
performs planning, retrieval, reasoning, factual extraction, grounding, and
evidence attachment. `src/webui/document_processor.py` handles TXT/PDF/DOCX
runtime ingestion, persistence, restoration, and deletion. Benchmarks,
regression suites, and validation scripts are test/evaluation surfaces.

The configured static corpus contains **107,650 chunks**. Runtime uploads are
local persisted documents and retain document ID, name, source type, extension,
timestamp, and chunk metadata. The reasoning checkpoint and tokenizer are
required local artifacts. Docker exposes the Web UI on port 7860; the API
defaults to port 8000.

## Validation results

- Clean API startup: PASS. `/health` and `/ready` returned success; model,
  tokenizer, corpus, and postings index initialized.
- API workflow: PASS. Health, readiness, stats, static queries, ingestion,
  provenance, listing, deletion, and restart/delete lifecycle passed.
- UI: callback/component coverage exists; browser E2E was not performed
  because no Reticle browser session was available.
- API/UI evidence contract: existing unified-evidence tests PASS.
- Persistence/recovery: PASS in the focused suite, including malformed,
  missing, unsafe, duplicate, unsupported, and empty entries.
- Retrieval performance: historical non-regression reference remains
  retrieval p50 49.4 ms and p95 271.9 ms on the documented environment.
  Postings, V4 duplicate-query caching, incremental upload indexing, and
  unchanged ingestion boost are covered by tests.
- Docker Compose syntax: PASS. Docker build/runtime: NOT VALIDATED because
  Docker Desktop Linux daemon was unavailable.
- Clean install: PASS. A disposable Python 3.11 environment installed
  `requirements.txt` completely. Torch, tokenizers, FastAPI, Gradio, and
  the runtime module imported successfully using the repository's `src`
  module-path convention.

## Release blocker audit

The commercial gate now passes 10/10. The root cause was a generic extractor
fallback accepting an answer that was not present in the entity-bound
retrieval evidence. Factual fallback is now limited to grounded evidence, and
the regression is covered by `test_retrieval_performance.py`.

**NON-BLOCKING:** authentication, authorization, TLS, tenant isolation,
rate limiting, and production durability are absent by design. Docker runtime
and browser E2E remain unvalidated in this environment.

## Security boundary

RALG Prototype 1 is a **local / trusted-environment prototype**. It must not
be exposed directly to an untrusted public network. Upload parsers, persisted
documents, logs, and feedback require operator-controlled filesystem and
network boundaries.

## Required artifacts and reproducibility

See `RELEASE_ARTIFACTS.md` for required artifact classifications and hashes.
The model checkpoint is external to Git. The configured corpus and tokenizer
were present and hashed during validation.

## Recommendation

READY FOR PROTOTYPE 1 RC TAG
