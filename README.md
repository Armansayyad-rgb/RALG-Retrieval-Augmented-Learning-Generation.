<div align="center">

# RALG Engine
### Retrieval-Augmented Learning & Generation

A local, evidence-grounded AI engine for answering questions over private documents with efficient retrieval, compact reasoning, and clear abstention when support is weak.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Source--Available-orange)
![Status](https://img.shields.io/badge/Status-Active%20Development-blue)

</div>

---

## What is RALG?

RALG, short for Retrieval-Augmented Learning & Generation, is an experimental local AI system that combines document retrieval, lightweight reasoning, and evidence-grounded answering.

The project is designed around a simple constraint: useful AI should not always require a large model, cloud inference, or heavy hardware. RALG explores how far a smaller local pipeline can go when retrieval, routing, grounding, and refusal behavior are treated as first-class parts of the system.

## Current focus

The current product direction is a private technical-document intelligence engine for teams that need answers from manuals, SOPs, maintenance notes, safety documents, policies, or internal knowledge bases.

The near-term goal is not broad general chat. The goal is reliable, cited answers in narrow domains where privacy, evidence, and compute efficiency matter.

## Key capabilities

- Local document retrieval from a knowledge base
- Evidence-grounded answer generation
- Lightweight reasoning path for selected questions
- False-premise and unsupported-question rejection
- Conditional multi-hop retrieval with a maximum extra pass
- PDF, DOCX, and TXT ingestion
- Gradio web interface
- Local FastAPI interface
- CPU and CUDA support
- Docker and Docker Compose support
- Evaluation and regression tooling

## How it works

```text
User question
   ↓
Query planning and retrieval
   ↓
Evidence selection
   ↓
Answer / reasoning route
   ↓
Support check
   ↓
Cited answer or abstention
```

RALG uses extra computation only when the query appears to need it. Simple questions stay on the cheaper path; harder questions can trigger additional retrieval/reasoning logic.

## Why this matters

Many AI document systems improve quality by adding larger models, rerankers, hosted APIs, or expensive inference layers. RALG explores another path: improving the pipeline itself so that smaller local systems can become more useful and more trustworthy.

This makes the project relevant for:

- private enterprise document search
- technical support knowledge bases
- manufacturing and maintenance documentation
- safety and compliance document lookup
- local-first AI deployments
- low-resource AI reasoning experiments

## Current status

RALG is in active development. Prototype 1 release candidate `0.1.0-rc1`
is immutable and is validated at commit
`c210eb8ae168a740b65189fc9245034dfe58e40e` (the corresponding release tag
must continue to point at that commit). The system includes a working local
pipeline, web UI, document ingestion, API, Docker packaging, evaluation
scripts, and a reproducible held-out commercial validation runner.

A recent small synthetic held-out checkpoint passed all 5 supported-answer cases for retrieval and completeness, rejected all 5 unsupported cases, produced a 0% false-support rate on that set, and preserved 23/23 regression passes. GitHub Actions CI has also been verified on `master`.

Those results are engineering checkpoints, not proof of production performance. The most important work now is pilot hardening: larger realistic evaluation data, clean-install and Docker reproducibility, malformed/oversized input handling, evidence-traceability assertions, and representative RAM/VRAM and latency measurements.

See:

- [Benchmarks](BENCHMARKS.md)
- [Benchmark Results](BENCHMARK_RESULTS.md)
- [Reliability Benchmark](RELIABILITY_BENCHMARK.md)
- [Roadmap](ROADMAP.md)
- [Architecture](docs/architecture.md)
- [Repository Layout](docs/repository_layout.md)
- [Use cases](docs/use_cases.md)
- [Security](SECURITY.md)
- [Commercial readiness](COMMERCIAL_READINESS.md)
- [Customer pilot readiness](PILOT_READINESS.md)

## Quick start

### Local Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run the web UI from the repository root:

```powershell
python src\webui_bootstrap.py
```

Run the local API from the repository root:

```powershell
uvicorn src.api_server:app --host 127.0.0.1 --port 8000
```

The API can also be launched from another directory with
`uvicorn src.api_server:app --app-dir <repository-root>`. `/health` reports
that the process is alive; `/ready` reports whether model, tokenizer, corpus,
and retrieval index are usable. A missing or corrupt required artifact keeps
`/ready` at HTTP 503 with a safe error.

### Docker

```bash
docker compose up --build
```

Then open:

```text
http://localhost:7860
```

Model checkpoints are not stored in Git. If your chosen runtime path requires a checkpoint, provide it through the configured checkpoint directory or Docker volume.

The Docker image includes the repository corpus and tokenizer. The Compose
`ralg_data` volume is used only for runtime uploads; provide the model
checkpoint separately at `/app/checkpoints/v2/reasoning_model_v1.pt` before
starting model-backed API or UI requests.

The optional polish LLM is not required for the core API or UI. If its model
files or optional runtime dependencies are unavailable, startup logs a warning
and the UI continues with the core retrieval answer path.

To enable Qwen2.5-1.5B-Instruct polish, install the optional dependencies with
`pip install -r requirements-polish.txt` and provide the model under
`POLISH_LLM_DIR` (or the default checkpoint directory). This does not change
the core dependency set or make network access necessary at runtime.

Runtime-uploaded documents are persisted under `data/runtime_uploads/` by
default (`RUNTIME_UPLOAD_DIR` overrides this). Each document has an application
generated ID and content file plus an atomic `metadata.json` registry. The
registry is rehydrated during pipeline startup, and documents can be listed or
deleted through `GET /documents`, `DELETE /documents/{document_id}`, or the
Documents tab. Docker persists this directory through the `ralg_data` volume.
Prototype 1 skips malformed or missing entries at startup and does not provide
multi-process transactions or production-grade durability. Upload and delete
mutations use a process-local lock only; they are not safe coordination across
multiple workers. The default UI upload policy is 50 MiB per batch, with
per-format and extracted-text/chunk limits enforced by the parser.

The reasoning checkpoint is external to Git and must be supplied at
`checkpoints/v2/reasoning_model_v1.pt`, or via `MODEL_FILE`. The tokenizer
defaults to `data/tokenizer_v2.json` and can be overridden with
`TOKENIZER_FILE`. Knowledge files default to the configured data directory and
can be overridden with `KNOWLEDGE_FILES`, `KNOWLEDGE_FILE_1`, and
`KNOWLEDGE_FILE_2`.

## Windows test runner

After setup, run:

```powershell
scripts\test_all.bat
```

For API testing after starting the server:

```powershell
scripts\test_all.bat api
```

See [Windows Test Runner](docs/windows_test_runner.md).

## Evaluation

Evaluation is part of the project, not an afterthought. The repo includes tests for factual QA, unsupported questions, false-premise rejection, causal questions, comparisons, and multi-hop behavior.

Two 50-case synthetic technical-document retrieval benchmarks are included: a direct set and a harder distractor/multi-evidence set. End-to-end API reliability is reported separately. A small held-out commercial validation set is also included to test supported-answer completeness, safe abstention, false-support behavior, and latency after runtime ingestion.

Published metrics should distinguish retrieval quality from answer reliability and include, where applicable:

- accuracy and support/rejection rates
- Recall@K and MRR
- false-support examples
- latency
- RAM/VRAM usage
- failure examples

Synthetic benchmark success is an engineering checkpoint, not proof of
production performance. Validation runs use isolated synthetic fixtures and
must not be interpreted as customer-data or production-network validation.

## Limitations

RALG is not production-ready yet.

Known limitations:

- current evaluation remains primarily synthetic and the held-out commercial set is small
- clean-machine installation and Docker startup still need explicit release-gate verification
- malformed and oversized upload behavior needs stronger automated coverage
- RAM/VRAM and scale-dependent ingest/query performance need formal measurement
- some runtime/research paths remain experimental
- model/data provenance needs stronger documentation for commercial diligence
- domain-specific validation is required before deployment

## License

RALG is released under the **RALG Source-Available Non-Commercial License v1.0**.

You may use, study, modify, and redistribute the project free of charge under the license terms. Selling RALG, commercially redistributing it, offering it as a paid hosted/SaaS service, or presenting the project as your own work is not permitted without prior written permission from the copyright holder.

This is a source-available license with commercial restrictions, not an OSI-approved open-source license. See [LICENSE](LICENSE) for the complete terms.

Earlier versions that were already distributed under the MIT License remain subject to the rights granted with those versions; the current license applies to versions distributed under the new license.

## Positioning

A safe one-line description:

> RALG Engine is a local, evidence-grounded AI system for private technical-document question answering with efficient retrieval and compact reasoning.
