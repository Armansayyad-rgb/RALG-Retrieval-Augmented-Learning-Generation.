<div align="center">

# RALG Engine
### Retrieval-Augmented Learning & Generation

A local-first, evidence-grounded technical-document intelligence engine focused on retrieval quality, provenance, document-scoped reasoning, conservative abstention, and reproducible evaluation.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Source--Available-orange)
![Status](https://img.shields.io/badge/Status-Controlled%20Technical%20Evaluation-blue)

</div>

---

## What RALG is

RALG is built for question answering over bounded technical-document collections such as manuals, SOPs, maintenance notes, service bulletins, policies, standards, and internal knowledge bases.

The project is deliberately not positioned as a general-purpose chatbot. Its core design goal is to produce inspectable answers that are tied to retrieved evidence, preserve provenance, respect document scope, detect unsupported or misleading requests, and abstain when the available evidence is insufficient.

## Current state

Prototype 1 RC1 is preserved at tag `0.1.0-rc1`. Current `master` contains substantial post-RC hardening across:

- unified API/WebUI grounded execution;
- document-scoped retrieval;
- persistent runtime documents and restart recovery;
- stable document IDs, provenance, listing, deletion, and scoped querying;
- support-gate hardening against false support and misleading overlap;
- conflict-aware evidence handling;
- retrieval performance and reproducibility work;
- portability and third-party attribution cleanup;
- buyer-demo and technical-diligence tooling;
- frozen independent holdout methodology and immutable blind-result preservation.

RALG remains a controlled technical-evaluation system rather than a hardened public SaaS deployment.

## Current independent holdout evidence

The strongest frozen blind evidence currently committed on `master` is **Holdout V2**, a 70-case internal independent holdout spanning seven technical domains.

### Retrieval-supported cases

40 cases were retrieval-supported.

| Metric | Lexical | RALG |
| --- | ---: | ---: |
| Recall@1 | 100% | **100%** |
| Recall@3 | 100% | **100%** |
| Recall@5 | 100% | **100%** |
| MRR | 1.000 | **1.000** |

### Rejection / support-gate cases

30 cases tested unsupported/adversarial behavior.

| Metric | RALG |
| --- | ---: |
| Unsupported rejection | **93.33% (28/30)** |
| False-support rate | **6.67% (2/30)** |

The original blind result is intentionally preserved unchanged in:

```text
evaluation/results/holdout_v2_blind_once.json
```

Two false-support failures were diagnosed only **after** the blind run and led to a generalized calculation-support gate fix plus new development regressions. The original V2 result was not rerun or rewritten after that fix.

**Important evidence boundary:** Holdout V2 is strong internal independent evidence, but its seven source notes were authored validation material derived from public technical documentation. It should not be represented as third-party or acquisition-grade external validation.

## Reliability development benchmark

A separate 50-case reliability benchmark is used as development/regression evidence. In the validated hardening run it reached:

- supported correctness: **100%**;
- unsupported rejection: **100%**;
- false-support rate: **0%**;
- false-rejection rate: **0%**;
- API errors: **0**.

This is useful engineering evidence, but it is a development benchmark and must not be described as an untouched independent holdout.

## Architecture

Grounded API and WebUI behavior share one runtime orchestration boundary:

```text
Question
   ↓
execute_runtime()
   ↓
ExecutionPlan
   ├─ intent / route
   ├─ document scope
   ├─ retrieval strategy
   └─ reasoning state
   ↓
Retrieval + factual extraction / grounded reasoning
   ↓
Evidence contract
   ↓
Support gate
   ├─ predicate / subject validation
   ├─ conflict handling
   ├─ traceability
   └─ provenance
   ↓
Supported answer or abstention
```

Document scope is threaded end-to-end through the API and runtime retrieval path. Invalid or empty document scopes fail safely rather than falling back to unrelated global evidence.

## Key capabilities

- local/private technical-document question answering;
- evidence-backed answers and conservative abstention;
- document-scoped retrieval and multi-document querying;
- provenance and answer/evidence traceability;
- misleading-overlap and false-premise resistance;
- conflict-aware support gating;
- factual extraction, comparison, procedural, and bounded reasoning paths;
- TXT, PDF, and DOCX ingestion;
- persistent runtime documents and restart recovery;
- stable document IDs, listing, deletion, and provenance metadata;
- FastAPI service with health/readiness, ingest, query, statistics, and document lifecycle endpoints;
- Gradio web UI using the same grounded runtime boundary;
- lightweight Python client/SDK;
- CPU and CUDA support;
- Docker / Docker Compose configuration;
- benchmark, regression, persistence, provenance, portability, performance, and integrity tooling.

## Quick start

### Requirements

- Python **3.11** recommended;
- required model checkpoint supplied separately from Git where applicable;
- configured tokenizer/corpus available in the expected repository layout.

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

Health endpoints:

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/ready
```

`/health` checks process liveness. `/ready` reports whether the configured model, tokenizer, corpus, and retrieval index are usable.

## Runtime documents

Runtime documents are stored under `data/runtime_uploads/` by default and can be redirected with `RUNTIME_UPLOAD_DIR`.

The runtime lifecycle supports ingest, list, query, provenance, delete, restart recovery, and tolerance for missing/corrupt runtime entries.

Lifecycle mutation locks are process-local. The validated deployment profile is therefore a trusted, single-application-worker configuration unless additional coordination is added externally.

## Model and tokenizer configuration

Portable path handling is centralized in `config.py`; repository-root-relative defaults are preferred over machine-specific paths.

The active grounded reasoning role normally uses:

```text
checkpoints/v2/reasoning_model_v1.pt
```

or `MODEL_FILE`.

The tokenizer normally uses:

```text
data/tokenizer_v2.json
```

or `TOKENIZER_FILE`.

Historical model/training artifacts are retained for reproducibility but should not be treated as automatically active runtime assets.

## Docker

```powershell
docker compose config --quiet
docker compose up --build
```

Compose configuration is maintained, but Compose syntax/configuration alone is not equivalent to a current full production-container qualification.

## Testing

Run the Windows suite:

```powershell
scripts\test_all.bat
```

For API-oriented tests after starting the service:

```powershell
scripts\test_all.bat api
```

Focused tests cover support-gate behavior, document scoping, retrieval performance, traceability, conflicting evidence, unified evidence handling, persistence, provenance, portability, runtime integrity, and holdout integrity.

## Evaluation discipline

RALG intentionally separates:

- retrieval quality;
- answer correctness;
- unsupported rejection / false support;
- provenance and traceability;
- runtime errors;
- latency and resource behavior.

Historical failures remain part of the evidence record. Frozen blind holdouts are not rerun to improve a score after failure analysis.

See [Benchmarks](BENCHMARKS.md) and [Validation & Evidence Index](docs/validation_evidence.md).

## Current limitations

RALG is suitable for controlled technical evaluation in a trusted environment, not direct exposure as an untrusted public production service.

Known limitations include:

- no built-in production authentication/authorization layer;
- no application-provided TLS termination;
- no tenant isolation;
- no production-grade rate limiting;
- process-local lifecycle mutation locking;
- no claim of multi-process transactional document mutation safety;
- no customer-production or safety-certification claim;
- model/data/license diligence still requires human/legal review for some assets;
- historical research/training code remains for reproducibility;
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
- [Validation & Evidence Index](docs/validation_evidence.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Security boundary

Treat RALG as a local/trusted-environment prototype unless additional deployment controls are added externally. Do not expose the default service directly to an untrusted public network.

See [SECURITY.md](SECURITY.md).

## License

RALG is distributed under the **RALG Source-Available Non-Commercial License v1.0**.

You may use, study, modify, and redistribute the project under the license terms. Commercial redistribution, paid hosted/SaaS use, or presenting the project as your own work requires prior written permission from the copyright holder.

This is a source-available license with commercial restrictions, not an OSI-approved open-source license. See [LICENSE](LICENSE).

Earlier versions distributed under earlier licenses remain subject to rights already granted with those versions.

## Positioning

> RALG Engine is a local, evidence-grounded technical-document intelligence system designed for private retrieval, provenance-backed answers, conservative abstention, document-scoped reasoning, and reproducible evaluation.
