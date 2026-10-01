<div align="center">

# RALG Engine
### Retrieval-Augmented Learning & Generation

**Private, evidence-grounded technical-document intelligence.**

RALG ingests bounded document collections, retrieves evidence, answers only when support survives grounding checks, and preserves source/provenance information for inspection.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Source--Available-orange)
![Status](https://img.shields.io/badge/Status-Controlled%20Technical%20Evaluation-blue)

</div>

---

## What RALG is

RALG is a local-first document-intelligence engine for manuals, SOPs, maintenance and engineering documentation, service bulletins, safety/compliance material, policies, standards, and private enterprise knowledge.

It is deliberately **not a general-purpose chatbot**. The production runtime is organized around evidence identity, subject/relation grounding, provenance, traceability, document scope, conflict handling, and conservative abstention. If the retrieved corpus does not support the requested claim, the intended behavior is to reject the answer rather than fill the gap from model memory.

## Current production state

Current `master` contains the post-freeze reliability, launch-readiness, manual-upload grounding, broad grounded-synthesis, and documentation work completed after the historical RC1 milestone. The latest merged documentation refresh is PR #104; this follow-up documentation PR keeps the public README, demonstration guide, and release-readiness material aligned as the repository moves toward fresh independent evaluation.

Current capabilities include:

- shared FastAPI/WebUI execution through `execute_runtime()`;
- full-question-first hybrid retrieval for grounded reasoning paths;
- fast V2 retrieval for factual extraction;
- subject, predicate/relation, entity, identifier, and answer-addressing checks;
- broad explanatory synthesis from multiple independently grounded passages;
- conservative rejection of unsupported, false-premise, and misleading-overlap questions;
- conflict-aware abstention;
- document-scoped querying with safe failure for invalid/empty scopes;
- evidence, provenance, and traceability carried into the final support decision;
- persistent runtime documents, stable document IDs, restart recovery, listing, deletion, and provenance metadata;
- PDF, DOCX, and TXT ingestion;
- FastAPI, Gradio WebUI, lightweight Python client, Docker/Compose, and deterministic demo tooling.

RALG remains intended for **local/trusted controlled deployment**, not as a hardened public multi-tenant internet SaaS.

## Architecture

API and WebUI converge on the same authoritative grounded runtime:

```text
PDF / DOCX / TXT
      |
      v
Document parsing -> chunking -> persistent runtime corpus/index
                                      |
User question                          |
      |                               |
      v                               v
FastAPI / WebUI ----------------> execute_runtime()
                                      |
                                      v
                               ExecutionPlan
                         intent / route / scope / model
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
          factual extractor route             grounded reasoning route
          V2 single-pass retrieval             full-question-first hybrid
                    |                                   |
                    +-----------------+-----------------+
                                      |
                                      v
                         answer construction
                factual / procedural / causal / comparison /
                 definitional / broad grounded synthesis
                                      |
                                      v
                         Answer/Evidence contract
                                      |
                                      v
                         unified_support_gate()
                  raw support + contract support + evidence
                    + traceability + conflict + provenance
                                      |
                         +------------+------------+
                         |                         |
                         v                         v
                supported answer              abstention
                + source trace             (fail closed)
```

### Core production modules

| Module | Responsibility |
| --- | --- |
| `src/runtime_architecture.py` | Shared `ExecutionPlan`, `execute_runtime()`, model registry, multi-hop trace, final unified support gate |
| `src/rag_chat_v2.py` | Question classification/routing, retrieval orchestration, extraction and grounded answer construction |
| `src/retriever_hybrid.py` | Full-question-first hybrid retrieval with bounded secondary queries and deterministic fusion |
| `src/retriever_v2.py` | Fast lexical/index retrieval and factual-relation scoring |
| `src/webui/chat_handler.py` | Answer contract, relation/definition grounding, conflict checks, source/provenance collection |
| `src/api_server.py` | FastAPI service and document lifecycle endpoints |
| `src/webui/app.py` | Gradio user interface |
| `src/webui/document_processor.py` | PDF/DOCX/TXT upload parsing and ingestion support |
| `src/model_v2.py` | SmallLM V2 architecture used by the optional model-backed grounded path |

See [`docs/CURRENT_ARCHITECTURE_STATUS.md`](docs/CURRENT_ARCHITECTURE_STATUS.md) for the detailed runtime description.

## Grounding and answer policy

RALG separates retrieval from permission to answer. A relevant-looking chunk is not sufficient by itself.

For narrow factual and attribute questions, the runtime applies strong subject/relation/value-style grounding and answer-addressing checks. For definitions, title/header mentions alone do not establish a definition. For broad explanatory questions, the runtime can combine several relevant passages, but the synthesized claims must remain grounded in the retrieved evidence. The final contract cannot be overridden by a weaker raw support signal.

A final supported answer therefore requires the support gate to retain evidence/traceability/provenance and to find no unresolved conflict. Otherwise RALG abstains.

## Retrieval

Grounded reasoning uses `src/retriever_hybrid.py`. It always begins with the complete user question, preserves strong full-question candidates, and only adds a bounded number of secondary/sub-query passes when useful. Candidate fusion uses deterministic full-question coverage/rank signals and prevents secondary-query heuristics from displacing strong primary evidence.

Factual extraction intentionally uses the cheaper V2 retrieval path. This is route specialization inside one user-facing runtime, not a second product stack.

## Model behavior

The active model architecture is `SmallLMV2`. The configured checkpoint is:

```text
checkpoints/v2/reasoning_model_v1.pt
```

The checkpoint is external to Git. RALG can still operate in extractive/retrieval-only mode when it is absent; model-backed generation is optional. Optional Qwen polishing is non-grounded and must never establish evidence support.

## API surface

The local FastAPI service exposes the core runtime and document lifecycle through:

```text
GET  /health
GET  /ready
GET  /stats
POST /ingest
POST /query
GET  /documents
```

Document lifecycle operations also support persistent runtime ingestion/deletion behavior used by the WebUI and API.

## Quick start

### Requirements

- Windows 10/11 + PowerShell for the provided demo launcher
- Python **3.11**
- dependencies from `requirements.txt`

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The tracked tokenizer is required. The model checkpoint is optional unless model-backed answers are specifically required.

### Launch

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
```

The launcher discovers a Python 3.11 interpreter, runs preflight checks, starts FastAPI on `127.0.0.1:8000`, starts the Gradio WebUI on an available port in `7860-7870`, and waits for an HTTP-successful readiness response before declaring startup successful.

The readiness contract supports the validated extractive/retrieval-only operating mode: absence of the optional model checkpoint is reported, but does not by itself make the service unusable when the tokenizer/index/retrieval runtime is healthy.

For the deterministic demonstration flow, see [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md).

## Validation and evidence boundaries

The repository contains several generations of benchmarks, holdouts, regression suites, and frozen evaluation artifacts. They do **not** all have the same evidentiary status.

In particular:

- historical development/regression benchmarks are engineering evidence, not untouched external validation;
- frozen blind holdout artifacts must remain immutable and must not be rerun or rewritten after seeing results;
- post-run semantic adjudication/derived scorecards must not be relabeled as the original official blind metric;
- current production fixes after a frozen holdout require fresh independent evaluation before making a new global accuracy claim.

See [`docs/CLAIMS_EVIDENCE_MATRIX.md`](docs/CLAIMS_EVIDENCE_MATRIX.md) and the `evaluation/` tree for the exact frozen artifacts, evidence classes, and methodology boundaries.

## Documentation map

| Document | Purpose |
| --- | --- |
| [`docs/CURRENT_ARCHITECTURE_STATUS.md`](docs/CURRENT_ARCHITECTURE_STATUS.md) | Authoritative description of the current runtime architecture |
| [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md) | Reproducible local demonstration and evaluator walkthrough |
| [`docs/CLAIMS_EVIDENCE_MATRIX.md`](docs/CLAIMS_EVIDENCE_MATRIX.md) | Conservative source of truth for technical claims and evidence boundaries |
| [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md) | Current release/technical-diligence checklist and remaining gates |
| [`docs/IP_PROVENANCE_AND_RELEASE_BOUNDARIES.md`](docs/IP_PROVENANCE_AND_RELEASE_BOUNDARIES.md) | IP, data, model, and commercial-release boundaries |
| [`docs/DATA_RIGHTS_INVENTORY.md`](docs/DATA_RIGHTS_INVENTORY.md) | Data provenance and rights inventory |
| [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) | Third-party attribution and licensing notices |

The architecture, demonstration, claims, and release-readiness documents are intentionally separated so implementation behavior, demonstration procedure, evidence status, and commercial-release diligence are not conflated.

## Deployment boundary

RALG is designed for local or trusted single-tenant deployment. It should not currently be represented as a hardened public multi-tenant SaaS. Public internet deployment would require additional security/operations work such as tenant isolation, hardened authentication/authorization, TLS termination, production rate limiting, and multi-process mutation safety.

## License

RALG is distributed under the **RALG Source-Available Non-Commercial License v1.0**. It is source-available, not OSI open source. Commercial use, sale, paid SaaS/API operation, or commercial rebranding requires permission from the copyright holder.

See [`LICENSE`](LICENSE) for the controlling terms.
