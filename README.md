<div align="center">

# RALG Engine
### Retrieval-Augmented Learning & Generation

A local-first, evidence-grounded technical-document intelligence engine focused on retrieval quality, provenance, document-scoped reasoning, conservative abstention, and reproducible evaluation.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
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

`API_TOKEN` authentication is optional under the current single-tenant deployment profile.

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

## Quick start (canonical path for technical buyer)

The following gets a buyer to a running demo with minimal commands. All paths
are repository-root-relative; no machine-specific absolute paths are encoded.

### 1. OS assumption

Windows 10/11 with PowerShell 5.1+ (the provided `run_buyer_demo.ps1` and
`buyer_demo_preflight.py` are Windows-native; Linux/macOS users can adapt the
PowerShell logic to bash or run the Python preflight directly).

### 2. Python version

Python **3.11** is required. The preflight check (`scripts/buyer_demo_preflight.py`)
validates this and reports `[FAIL] python_version` if the installed version is
not exactly 3.11. If a different Python version is installed, create a venv with
Python 3.11 before proceeding.

```powershell
# Verify Python version
python --version
# Expected: 3.11.x
```

### 3. Dependency install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Local model requirements

The checkpoint bundle `checkpoints/v2/reasoning_model_v1.pt` is **external to
Git** and governed by the RALG Source-Available Non-Commercial License v1.0.
It is not auto-downloaded. Place the checkpoint under `checkpoints/v2/` before
running the demo if model-backed (generative) answers are required. The core
pipeline supports extractive/lookup answers without it.

The tokenizer `data/tokenizer_v2.json` is tracked in Git and always required.

### 5. Optional model behavior

The polish LLM (Qwen2.5-1.5B-Instruct) is optional. If available, it enables
generative and hybrid answer modes. If not available, the system produces
extractive grounded answers only. The preflight reports this as a warning, not
a failure.

### 6. CPU/GPU assumptions

The default Docker image is CPU-only (`python:3.11-slim` with CPU PyTorch).
GPU execution is supported if CUDA is available and the appropriate PyTorch
wheel is installed, but the buyer-demo workflow is validated on CPU.

### 7. Startup command

```powershell
# From the repository root
powershell -ExecutionPolicy Bypass -File scripts\run_buyer_demo.ps1
```

This script:
1. Discovers Python (venv or system)
2. Runs preflight checks (Python version, required files, checkpoint status,
   bounded port selection 7860-7870)
3. Launches FastAPI on 127.0.0.1:8000
4. Launches the Gradio WebUI on the preflight-selected port 7860-7870
5. Probes FastAPI `/ready` on port 8000 after startup (up to 30s timeout)

If preflight fails, the script prints actionable messages and exits with code 1.

### 8. Demo command

After the service starts, open the WebUI URL printed by the launcher (selected from 127.0.0.1:7860-7870) in a browser and follow
the deterministic buyer-demo scenario (Section 5 of `docs/BUYER_DEMO_GUIDE.md`):

- Ingest `data/technical_docs_sample.txt` (or a subset via the WebUI or API)
- Ask a supported question → verify grounded answer with cited sources
- Ask an unsupported question → verify visible abstention
- Inspect evidence/provenance traces for accepted answers
- Try document-scoped queries via the WebUI scope dropdown

### 9. Expected high-level behavior

| Step | Expected outcome |
|---|---|
| Service health (`/health`) | `{"status":"ok"}` |
| Service readiness (`/ready`) | `{"ready":true, ...}` when the model/checkpoint is present and initialization is healthy; extractive-only mode without the checkpoint may return `503` |
| Document ingestion | Document parsed, chunked, indexed; KB table updates |
| Supported question | Direct answer with cited sources; answer_type="supported" |
| Unsupported question | System reports corpus does not contain the answer (abstention) |
| Evidence trace | Each accepted answer traces to specific spans in named documents |
| Persistence (Docker) | Document survives `docker restart` via named volume `ralg_data` |

### 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `[FAIL] python_version` | Install Python 3.11 and re-run; or create a venv with Python 3.11 |
| `[FAIL] file_exists:checkpoints/v2` | Place the external checkpoint bundle under `checkpoints/v2/` or run in extractive mode without it |
| `[FAIL] webui_port_available` | Free one of ports 7860-7870 on 127.0.0.1; the launcher never terminates other processes |
| Service starts but `/ready` returns 503 | Wait a few seconds for initialization; check logs for initialization errors |
| Answer appears without citations | Verify the document was successfully ingested (check KB table) |
| Ctrl+C does not stop the server | Press Ctrl+C again; the Gradio process may need a moment to shut down gracefully |

### Canonical path summary

```powershell
# 1. Create venv and install deps
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 2. Place checkpoint (external, license-governed)
#    - checkpoints/v2/reasoning_model_v1.pt  (RALG Source-Available license)

# 3. Start the demo
powershell -ExecutionPolicy Bypass -File scripts\run_buyer_demo.ps1

# 4. Follow the deterministic scenario (Section 5 of BUYER_DEMO_GUIDE.md)
```
