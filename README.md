<div align="center">

# RALG Engine
### Retrieval-Augmented Learning & Generation

A local, evidence-grounded technical-document intelligence engine focused on retrieval quality, provenance, safe abstention, and reproducible evaluation.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Source--Available-orange)
![Status](https://img.shields.io/badge/Status-Core%20Architecture%20Hardening-blue)

</div>

---

## Overview

RALG is an experimental local-first AI system for answering questions over technical documents such as manuals, SOPs, maintenance notes, service bulletins, policies, standards, and internal knowledge bases.

The project emphasizes retrieval, evidence selection, provenance, unsupported-question rejection, document lifecycle integrity, and measurable evaluation. The target is not broad general chat; it is reliable, inspectable answers over bounded technical-document collections.

## Current state

Prototype 1 RC1 is preserved at tag `0.1.0-rc1` (tag target `f5cb70505edf34c247d8dfadf56ac65c1bbbb57c`). Since RC1, the project has completed hardening and pilot-evidence work covering persistence, provenance, API lifecycle, concurrency, portability, retrieval performance, clean-install validation, SDK integration, synthetic held-out evaluation, and a first independently sourced external-document evaluation.

Current validated engineering checkpoints include:

- regression suite: **23/23 PASS**
- commercial validation: **10/10 PASS**
- unsupported named-factual smoke tests: **0 false-supported cases** in the validated sets
- clean Python 3.11 install with stable `tokenizers==0.23.1`
- isolated API ingest/query/list/delete/restart lifecycle: **PASS**
- live lightweight SDK integration: **PASS**
- 1000-request / 8-worker soak: **1000/1000 completed, 0 errors**
- optimized 100k-chunk retrieval: approximately **156 ms p50 / 216 ms p95** in the recorded Stage 2 environment
- Stage 4 synthetic external-style benchmark: RALG Recall@1 **100%** vs lexical **96.875%**, with both at Recall@5 **100%**
- Stage 5 preliminary independent-RFC benchmark: lexical retrieval currently leads retrieval quality, while RALG is substantially faster in the recorded harness

These are engineering checkpoints, not production guarantees or customer-data validation.

## Stage 5 independent evidence

Stage 5 adds a corpus of **50 independently sourced IETF RFC documents** and a **300-case preliminary benchmark** (210 supported / 90 unsupported). Provenance, canonical source references, document hashes, corpus-integrity checks, and blinded review tooling are included in the repository.

The first untouched preliminary run did **not** show retrieval-quality superiority for RALG:

| Metric | Lexical | RALG |
| --- | ---: | ---: |
| Recall@1 | 40.48% | 37.14% |
| Recall@3 | 87.62% | 77.62% |
| Recall@5 | 100.00% | 92.86% |
| MRR | 0.6485 | 0.5863 |
| Unsupported rejection | 100% | 100% |
| False-support rate | 0% | 0% |
| Retrieval p50 | ~187.08 ms | ~6.76 ms |
| Retrieval p95 | ~252.90 ms | ~7.37 ms |

All 300 cases are still automatically generated and unreviewed. Therefore the correct Stage 5 status is **BLOCKED ON INDEPENDENT REVIEW**. These results are preliminary and must not be presented as final external validation.

## Core architecture

The current production `/query` path implements most of the intended compound RALG design, but the architecture audit identifies meaningful integration gaps. Current architecture coverage is approximately **70%**.

```text
Question
   ↓
Planning / routing
   ↓
Factual | Comparison | Reasoning
   ↓
V2 / V4 retrieval
   ↓
Optional second multi-hop retrieval
   ↓
Evidence + support checks
   ↓
Extraction / deterministic synthesis / SmallLMV2
   ↓
Answer contract
   ├─ traceability
   ├─ conflict detection
   └─ provenance
   ↓
Supported answer or abstention
```

The next core build focuses on one authoritative execution plan, one answer-level support gate, stronger multi-hop state, explicit model-registry integration, and API/UI parity. See [Current Architecture Status](docs/CURRENT_ARCHITECTURE_STATUS.md).

## Key capabilities

- evidence-grounded question answering
- safe abstention when evidence is insufficient
- V2/V4 retrieval paths with postings-based lexical indexing
- bounded query caching and duplicate-query reuse
- factual extraction, comparison, and reasoning paths
- limited second-pass multi-hop retrieval
- document ingestion for TXT, PDF, and DOCX
- runtime document persistence and restart recovery
- stable document IDs, provenance metadata, listing, and deletion
- conflict-aware and factual-grounding protections
- FastAPI service with `/health`, `/ready`, `/stats`, `/documents`, `/ingest`, `/query`, and delete lifecycle support
- Gradio web interface
- lightweight Python client/SDK
- CPU and CUDA support
- Docker and Docker Compose configuration
- benchmark, regression, performance, portability, persistence, provenance, and hardening test suites

## Quick start

### Requirements

- Python **3.11** recommended
- required model checkpoint supplied separately from Git
- tokenizer and configured corpus available in the repository/data layout

### Local Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the API from the repository root:

```powershell
python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8000
```

Run the web UI:

```powershell
python src\webui_bootstrap.py
```

Liveness and readiness:

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/ready
```

`/health` checks process liveness. `/ready` reports whether the model, tokenizer, corpus, and retrieval index are usable. Missing/corrupt required artifacts keep readiness unavailable with sanitized client-facing errors.

### Runtime documents

Runtime documents are stored under `data/runtime_uploads/` by default and can be redirected with `RUNTIME_UPLOAD_DIR`.

The runtime document lifecycle supports ingest, list, provenance-backed query, delete, restart recovery, and corruption/missing-entry tolerance.

Lifecycle mutation locks are **process-local**. The validated pilot configuration uses a **single Uvicorn/application worker**; multi-process lifecycle safety is not claimed.

### Model and tokenizer configuration

The current API runtime uses the reasoning checkpoint supplied externally at:

```text
checkpoints/v2/reasoning_model_v1.pt
```

or through `MODEL_FILE`.

The tokenizer defaults to:

```text
data/tokenizer_v2.json
```

and can be overridden with `TOKENIZER_FILE`.

Knowledge sources can be configured with `KNOWLEDGE_FILES`, `KNOWLEDGE_FILE_1`, and `KNOWLEDGE_FILE_2`.

Several historical training/model artifacts remain in the repository layout but are not all connected to the current API serving path. They are retained for reproducibility until the model-registry/runtime-integration work classifies them explicitly.

### Optional polish model

The optional polish LLM is not required for the core retrieval/API path. Install optional dependencies with:

```powershell
python -m pip install -r requirements-polish.txt
```

and configure `POLISH_LLM_DIR` if that path is used.

## Docker

Compose configuration is maintained and validated syntactically:

```powershell
docker compose config --quiet
docker compose up --build
```

The default Compose exposure is localhost-oriented and runtime uploads are persisted through the configured data volume.

**Important:** full Docker runtime lifecycle validation has not yet been completed on the recorded development environment. Compose validation is not container-runtime qualification.

## Testing

Run the Windows test suite:

```powershell
scripts\test_all.bat
```

For API-oriented testing after starting the service:

```powershell
scripts\test_all.bat api
```

The repository includes focused coverage for retrieval regression/performance, unsupported/false-support behavior, answer/evidence traceability, conflicting evidence, API input hardening, upload provenance, unified evidence semantics, persistence/restart recovery, portability/readiness, and runtime lifecycle/concurrency.

See [Windows Test Runner](docs/windows_test_runner.md).

## Evaluation

RALG keeps retrieval quality, answer support, rejection behavior, provenance, and runtime performance as separate metrics rather than collapsing them into a single score.

Evidence currently includes:

- direct and hard synthetic technical-document retrieval benchmarks
- held-out commercial validation
- Stage 2 lifecycle/scale/reproducibility evidence
- Stage 3/4 synthetic customer-style and external-style comparisons
- Stage 5 independently sourced RFC corpus and preliminary evaluation
- lexical-vs-RALG comparisons
- retrieval latency and memory measurements
- concurrency soak tests
- clean-install and lifecycle validation

Stage 5 is the most important caution: the independent corpus currently favors lexical retrieval quality, the benchmark still lacks independent human review, and production code should not be tuned to individual Stage 5 case IDs.

See [Validation & Evidence Index](docs/validation_evidence.md).

## Current limitations

RALG is suitable for controlled technical evaluation, not an untrusted public production deployment.

Known limitations include:

- Stage 5 independent benchmark cases are not yet independently human-reviewed
- preliminary Stage 5 retrieval quality currently trails the lexical baseline
- current compound architecture is only partially consolidated (approximately 70% coverage)
- routing responsibility is duplicated between planning and router logic
- answer support is distributed across multiple heuristics rather than one authoritative semantic support gate
- API and Web UI generation/retrieval behavior are not yet fully unified
- multi-hop reasoning remains heuristic
- several trained artifacts are disconnected from the current serving path
- Docker runtime lifecycle remains not fully validated in the recorded environment
- 250k/500k scale validation is deferred for hardware-safety reasons
- lifecycle locking is process-local; multi-worker mutation safety is not claimed
- no production authentication
- no TLS termination provided by the application
- no tenant isolation
- no production-grade rate limiting or multi-process transaction layer
- domain-specific validation is required before safety-critical use

## Documentation

- [Current architecture status](docs/CURRENT_ARCHITECTURE_STATUS.md)
- [Architecture](docs/architecture.md)
- [Repository layout](docs/repository_layout.md)
- [Use cases](docs/use_cases.md)
- [API quick start](docs/API_QUICKSTART.md)
- [Security](SECURITY.md)
- [Roadmap](ROADMAP.md)
- [Benchmarks](BENCHMARKS.md)
- [Benchmark results](BENCHMARK_RESULTS.md)
- [Stage 5 independent evidence](STAGE5_INDEPENDENT_EVIDENCE_REPORT.md)
- [Stage 5 review guide](docs/STAGE5_REVIEW_GUIDE.md)
- [Validation & Evidence Index](docs/validation_evidence.md)

## Security boundary

Treat RALG as a local/trusted-environment prototype unless additional deployment controls are added externally. Do not expose the default service directly to an untrusted public network.

See [SECURITY.md](SECURITY.md) for the current boundary and reporting guidance.

## License

RALG is distributed under the **RALG Source-Available Non-Commercial License v1.0**.

You may use, study, modify, and redistribute the project under the license terms. Commercial redistribution, paid hosted/SaaS use, or presenting the project as your own work requires prior written permission from the copyright holder.

This is a source-available license with commercial restrictions, not an OSI-approved open-source license. See [LICENSE](LICENSE) for the complete terms.

Earlier versions already distributed under the MIT License remain subject to the rights granted with those versions.

## Positioning

> RALG Engine is a local, evidence-grounded technical-document intelligence system designed for private retrieval, provenance-backed answers, and safe abstention.
