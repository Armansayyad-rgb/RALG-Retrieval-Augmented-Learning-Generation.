<div align="center">

# RALG Engine
### Retrieval-Augmented Learning & Generation

A local, evidence-grounded technical-document intelligence engine focused on retrieval quality, provenance, safe abstention, and reproducible evaluation.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Source--Available-orange)
![Status](https://img.shields.io/badge/Status-Controlled%20Technical%20Evaluation-blue)

</div>

---

## Overview

RALG is an experimental local-first AI system for answering questions over technical documents such as manuals, SOPs, maintenance notes, service bulletins, policies, standards, and internal knowledge bases.

The project emphasizes retrieval, evidence selection, provenance, unsupported-question rejection, document lifecycle integrity, and measurable evaluation. The target is not broad general chat; it is reliable, inspectable answers over bounded technical-document collections.

## Current state

Prototype 1 RC1 is preserved at tag `0.1.0-rc1` (tag target `f5cb70505edf34c247d8dfadf56ac65c1bbbb57c`). Since RC1, the project has completed hardening, pilot-evidence, hybrid-retrieval, and runtime-consolidation work covering persistence, provenance, API lifecycle, concurrency, portability, retrieval performance, clean-install validation, SDK integration, independently sourced evaluation material, and unified API/WebUI grounded execution.

Current engineering checkpoints include:

- regression suite: **23/23 PASS** in the current runtime-integration validation;
- commercial validation: **quality gate PASS**;
- unsupported rejection: **100%** on the current preliminary Stage 5 benchmark;
- false-support rate: **0%** on the current preliminary Stage 5 benchmark;
- clean Python 3.11 install: previously validated;
- isolated API ingest/query/list/delete/restart lifecycle: previously validated;
- live lightweight SDK integration: previously validated;
- 1000-request / 8-worker soak: previously validated with **0 errors**;
- 100k retrieval scale: previously measured in the Stage 2 environment;
- Stage 4 synthetic external-style benchmark: historical rank-1 differentiation evidence;
- Stage 5 independently sourced RFC benchmark: current preliminary hybrid retrieval leads the lexical baseline at Recall@1, Recall@3, and MRR while tying Recall@5.

These are engineering checkpoints, not production guarantees, customer-data validation, revenue, or safety certification.

## Stage 5 independent-source evidence

Stage 5 uses **50 independently sourced IETF RFC documents** and a **300-case preliminary benchmark** (210 supported / 90 unsupported). Provenance, canonical source references, document hashes, corpus-integrity checks, and blinded review tooling are included in the repository.

Current untouched preliminary retrieval results:

| Metric | Lexical | RALG hybrid |
| --- | ---: | ---: |
| Recall@1 | 40.48% | **50.95%** |
| Recall@3 | 87.62% | **90.95%** |
| Recall@5 | 100.00% | **100.00%** |
| MRR | 0.6485 | **0.7098** |
| Unsupported rejection | 100% | **100%** |
| False-support rate | 0% | **0%** |

The runtime-integration validation preserved these quality metrics; recorded retrieval latency in that local integration run was approximately **6.9 ms p50 / 14.6 ms p95**.

Authoritative artifact: `evaluation/results/stage5_preliminary_results.json` (hybrid run, reproduced from frozen code). Historical pre-hybrid result and provenance: `docs/STAGE5_EVIDENCE_HISTORY.md`.

All 300 benchmark cases are still automatically generated and unreviewed. Therefore the correct Stage 5 status remains **BLOCKED ON INDEPENDENT REVIEW**. These numbers are preliminary engineering evidence and must not be presented as final independent validation.

## Core architecture

Grounded API and WebUI behavior now share one runtime orchestration boundary:

```text
Question
   ↓
execute_runtime()
   ↓
ExecutionPlan
   ├─ intent
   ├─ authoritative route
   ├─ retrieval strategy
   └─ multi-hop state
   ↓
Factual extractor OR grounded reasoning
   ↓
Full-question-first hybrid retrieval
   ↓
Evidence / answer contract
   ↓
Unified support gate
   ├─ traceability
   ├─ conflict detection
   └─ provenance
   ↓
Supported answer or abstention
```

`src/retriever_hybrid.py` is the authoritative grounded reasoning retriever. It protects strong full-question candidates and uses bounded secondary queries as additional evidence signals rather than replacing the complete-question match.

The factual extractor route retains a cheaper single-pass V2 lookup as intentional route specialization.

See [Current Architecture Status](docs/CURRENT_ARCHITECTURE_STATUS.md).

## Key capabilities

- evidence-grounded question answering;
- safe abstention when evidence is insufficient;
- full-question-first hybrid grounded retrieval;
- deterministic candidate deduplication/fusion;
- factual extraction, comparison, reasoning, and bounded multi-hop state;
- provenance and conflict-aware support gating;
- document ingestion for TXT, PDF, and DOCX;
- runtime document persistence and restart recovery;
- stable document IDs, provenance metadata, listing, and deletion;
- FastAPI service with `/health`, `/ready`, `/stats`, `/documents`, `/ingest`, `/query`, and delete lifecycle support;
- Gradio web interface using the same grounded runtime boundary;
- lightweight Python client/SDK;
- CPU and CUDA support;
- Docker and Docker Compose configuration;
- benchmark, regression, performance, portability, persistence, provenance, and architecture test suites;
- explicit model-registry classification for active, compatible, superseded, and legacy artifacts.

## Quick start

### Requirements

- Python **3.11** recommended;
- required model checkpoint supplied separately from Git;
- tokenizer and configured corpus available in the repository/data layout.

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

`/health` checks process liveness. `/ready` reports whether the configured model, tokenizer, corpus, and retrieval index are usable. Client-facing readiness errors are sanitized.

### Runtime documents

Runtime documents are stored under `data/runtime_uploads/` by default and can be redirected with `RUNTIME_UPLOAD_DIR`.

The runtime document lifecycle supports ingest, list, provenance-backed query, delete, restart recovery, and corruption/missing-entry tolerance.

Lifecycle mutation locks are **process-local**. The validated pilot configuration uses a **single Uvicorn/application worker**; multi-process lifecycle safety is not claimed.

### Model and tokenizer configuration

The active grounded reasoning role uses the configured checkpoint, normally:

```text
checkpoints/v2/reasoning_model_v1.pt
```

or `MODEL_FILE`.

The tokenizer defaults to:

```text
data/tokenizer_v2.json
```

and can be overridden with `TOKENIZER_FILE`.

Historical model/training artifacts remain for reproducibility but are explicitly classified by the runtime model registry rather than silently auto-loaded.

### Optional polish model

The optional Qwen polish path is not required for core grounded retrieval. It remains a non-grounded, opt-in role and cannot establish answer support.

Install optional dependencies with:

```powershell
python -m pip install -r requirements-polish.txt
```

## Docker

Compose configuration is maintained and localhost-oriented:

```powershell
docker compose config --quiet
docker compose up --build
```

Runtime uploads are persisted through the configured data volume.

**Important:** a current full post-runtime-consolidation Docker lifecycle is still a diligence item. Compose syntax/configuration is not equivalent to end-to-end container qualification.

## Testing

Run the Windows suite:

```powershell
scripts\test_all.bat
```

For API-oriented testing after starting the service:

```powershell
scripts\test_all.bat api
```

The repository includes focused coverage for retrieval performance, hybrid ranking, unsupported/false-support behavior, architecture integration, answer/evidence traceability, conflicting evidence, API input hardening, upload provenance, persistence/restart recovery, portability/readiness, and runtime lifecycle/concurrency.

See [Windows Test Runner](docs/windows_test_runner.md).

## Evaluation

RALG keeps retrieval quality, answer support, rejection behavior, provenance, and runtime performance as separate metrics rather than collapsing them into one score.

Evidence includes:

- direct and hard synthetic technical-document retrieval benchmarks;
- held-out commercial validation;
- Stage 2 lifecycle/scale/reproducibility evidence;
- Stage 3/4 synthetic customer-style/external-style comparisons;
- Stage 5 independently sourced RFC corpus and preliminary evaluation;
- lexical-vs-RALG comparisons;
- retrieval latency/memory measurements;
- concurrency soak tests;
- clean-install and lifecycle validation.

See [Validation & Evidence Index](docs/validation_evidence.md).

## Current limitations

RALG is suitable for controlled technical evaluation, not an untrusted public production deployment.

Known limitations include:

- Stage 5 benchmark cases are not yet independently human-reviewed;
- Docker runtime lifecycle needs a current post-#47/#49 end-to-end qualification;
- 250k/500k scale validation is deferred for hardware-safety reasons;
- lifecycle locking is process-local; multi-worker mutation safety is not claimed;
- no built-in production authentication;
- no TLS termination provided by the application;
- no tenant isolation;
- no production-grade rate limiting or shared multi-process transaction layer;
- dependency/model/data-rights diligence is still incomplete;
- historical training/research code remains in the repository for reproducibility;
- domain-specific validation is required before safety-critical use.

## Documentation

- [Current architecture status](docs/CURRENT_ARCHITECTURE_STATUS.md)
- [Technical diligence status](docs/TECHNICAL_DILIGENCE_STATUS.md)
- [Architecture](docs/architecture.md)
- [Repository layout](docs/repository_layout.md)
- [Use cases](docs/use_cases.md)
- [API quick start](docs/API_QUICKSTART.md)
- [Security](SECURITY.md)
- [Commercial readiness](COMMERCIAL_READINESS.md)
- [Roadmap](ROADMAP.md)
- [Benchmarks](BENCHMARKS.md)
- [Stage 5 independent evidence](STAGE5_INDEPENDENT_EVIDENCE_REPORT.md)
- [Stage 5 review guide](docs/STAGE5_REVIEW_GUIDE.md)
- [Validation & Evidence Index](docs/validation_evidence.md)

## Security boundary

Treat RALG as a local/trusted-environment prototype unless additional deployment controls are added externally. Do not expose the default service directly to an untrusted public network.

See [SECURITY.md](SECURITY.md).

## License

RALG is distributed under the **RALG Source-Available Non-Commercial License v1.0**.

You may use, study, modify, and redistribute the project under the license terms. Commercial redistribution, paid hosted/SaaS use, or presenting the project as your own work requires prior written permission from the copyright holder.

This is a source-available license with commercial restrictions, not an OSI-approved open-source license. See [LICENSE](LICENSE).

Earlier versions distributed under earlier licenses remain subject to the rights already granted with those versions.

## Positioning

> RALG Engine is a local, evidence-grounded technical-document intelligence system designed for private retrieval, provenance-backed answers, conservative abstention, and reproducible evaluation.
