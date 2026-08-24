<div align="center">

# RALG Engine
### Retrieval-Augmented Learning & Generation

A local, evidence-grounded technical-document intelligence engine focused on retrieval quality, provenance, safe abstention, and reproducible evaluation.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Source--Available-orange)
![Status](https://img.shields.io/badge/Status-Controlled%20Pilot%20Evaluation-blue)

</div>

---

## Overview

RALG is an experimental local-first AI system for answering questions over technical documents such as manuals, SOPs, maintenance notes, service bulletins, policies, and internal knowledge bases.

The project emphasizes the parts of document AI that are easy to under-engineer: retrieval, evidence selection, provenance, unsupported-question rejection, document lifecycle integrity, and measurable evaluation. The goal is not broad general chat; it is reliable, inspectable answers over bounded document collections.

## Current state

Prototype 1 RC1 is preserved at tag `0.1.0-rc1` (tag target `f5cb70505edf34c247d8dfadf56ac65c1bbbb57c`). Since RC1, the project has completed multiple hardening and pilot-evidence stages covering persistence, provenance, API lifecycle, concurrency, portability, retrieval performance, clean-install validation, SDK integration, and synthetic held-out evaluation.

Current validated engineering checkpoints include:

- regression suite: **23/23 PASS**
- commercial validation: **10/10 PASS**
- unsupported named-factual smoke tests: **0 false-supported cases** in the validated sets
- clean Python 3.11 install with stable `tokenizers==0.23.1`
- isolated API ingest/query/list/delete/restart lifecycle: **PASS**
- live lightweight SDK integration: **PASS**
- 1000-request / 8-worker soak: **1000/1000 completed, 0 errors**
- optimized 100k-chunk retrieval: approximately **156 ms p50 / 216 ms p95** in the validated Stage 2 environment
- Stage 1 pilot benchmark: RALG Recall@5 **100%** vs lexical **93.75%** on a synthetic held-out set
- Stage 3 customer-style synthetic benchmark: both lexical and RALG reached Recall@5 **100%**, so that benchmark is treated as a ceiling-effect result rather than evidence of retrieval-quality superiority

These are engineering checkpoints, not production guarantees or customer-data validation.

## Key capabilities

- evidence-grounded question answering
- safe abstention when evidence is insufficient
- V2/V4 retrieval paths with postings-based lexical indexing
- bounded query caching and duplicate-query reuse
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

## Architecture

```text
User / SDK / Web UI
        ↓
      API layer
        ↓
Query planning + retrieval
        ↓
Evidence selection / provenance
        ↓
Grounding + conflict checks
        ↓
Supported answer or safe abstention
```

The retrieval pipeline is intentionally explicit and testable. Expensive or additional work is only used when needed, while supported answers remain tied to retrieved evidence.

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

The runtime document lifecycle supports:

- ingest
- list
- provenance-backed query
- delete
- restart recovery
- corruption/missing-entry tolerance

Lifecycle mutation locks are **process-local**. The validated pilot configuration uses a **single Uvicorn/application worker**; multi-process lifecycle safety is not claimed.

### Model and tokenizer configuration

The reasoning checkpoint is external to Git and must be supplied at:

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

**Important:** full Docker runtime lifecycle validation has not yet been completed on the current development machine because its Docker daemon was unavailable during the recorded pilot-validation runs. Do not interpret Compose validation as a completed container-runtime qualification.

## Testing

Run the Windows test suite:

```powershell
scripts\test_all.bat
```

For API-oriented testing after starting the service:

```powershell
scripts\test_all.bat api
```

The repository includes focused coverage for:

- retrieval regression and performance
- unsupported/false-support behavior
- answer/evidence traceability
- conflicting evidence
- API input hardening
- upload provenance
- unified evidence semantics
- persistence and restart recovery
- portability/readiness
- runtime lifecycle and concurrency

See [Windows Test Runner](docs/windows_test_runner.md).

## Evaluation

RALG keeps retrieval quality, answer support, rejection behavior, and runtime performance as separate metrics rather than collapsing them into a single score.

Current evidence includes:

- direct and hard synthetic technical-document retrieval benchmarks
- held-out commercial validation
- pilot/customer-style synthetic held-out evaluations
- lexical-vs-RALG comparisons
- retrieval latency and memory measurements
- concurrency soak tests
- clean-install and lifecycle validation

Important caveat: the current public evaluation material is primarily **synthetic**. Stage 3 also exposed a ceiling effect where both lexical retrieval and RALG achieved Recall@5 of 100%. The next evidence stage therefore focuses on harder external-style evaluation rather than adding more easy synthetic cases.

See [Validation & Evidence Index](docs/validation_evidence.md) for the current and historical reports.

## Current limitations

RALG is suitable for controlled technical evaluation, not an untrusted public production deployment.

Known limitations include:

- evaluation is still predominantly synthetic rather than permitted real customer data
- Docker runtime lifecycle remains not validated on the current development machine
- 250k/500k scale validation is deferred for hardware-safety reasons
- conflict, factual-grounding, and provenance semantic ablations are not yet cleanly isolated
- lifecycle locking is process-local; multi-worker mutation safety is not claimed
- no production authentication
- no TLS termination provided by the application
- no tenant isolation
- no production-grade rate limiting or multi-process transaction layer
- domain-specific validation is required before safety-critical use

## Documentation

- [Architecture](docs/architecture.md)
- [Repository layout](docs/repository_layout.md)
- [Use cases](docs/use_cases.md)
- [API quick start](docs/API_QUICKSTART.md)
- [Security](SECURITY.md)
- [Roadmap](ROADMAP.md)
- [Benchmarks](BENCHMARKS.md)
- [Benchmark results](BENCHMARK_RESULTS.md)
- [Pilot readiness](PILOT_READINESS.md)
- [Stage 3 pilot readiness](STAGE3_PILOT_READINESS.md)
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
