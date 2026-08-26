# Dependency and IP Audit

**Branch:** `hardening/acquisition-diligence-v1`
**Master SHA:** `0b30827739df97d734583f6a570e4513a4a3586c`
**Date:** 2026-08-25

---

## 1. Scope

This audit covers every external dependency consumed by the RALG Engine across:

- `requirements.txt` (core runtime)
- `requirements-polish.txt` (optional polish model)
- `Dockerfile` / `docker-compose.yml`
- Python imports in `src/`, `scripts/`, `evaluation/`

A machine-readable inventory is at `docs/dependency_inventory.json`.

---

## 2. Dependency Summary

| Category | Count | Risk LOW | Risk REVIEW | Risk HIGH |
|----------|-------|----------|-------------|-----------|
| Runtime (shipped in Docker) | 11 | 11 | 0 | 0 |
| Optional runtime (polish model) | 3 | 3 | 0 | 0 |
| Evaluation/offline scripts | 1 | 1 | 0 | 0 |
| Development only (not in image) | 1 | 1 | 0 | 0 |
| **Total** | **15** | **15** | **0** | **0** |

**Missing runtime dependencies found:** 0 (all imports satisfied)
**Unused/provably dev-only:** 1 (`psutil` — memory monitoring in benchmark scripts, guarded by try/except)

---

## 3. Runtime Dependencies (shipped in Docker image)

### torch 2.7.1 (CPU-only in Docker)
- **License:** BSD-3-Clause (verified: METADATA classifier + GitHub LICENSE)
- **Purpose:** Core inference engine for SmallLM custom model and embedding math
- **Redistribution:** Permitted; must include copyright notice and license text. Dockerfile pins CPU-only wheel.
- **Commercial use:** PERMITTED
- **Risk:** LOW
- **Note:** Installed env has CUDA build (`2.7.1+cu128`); Docker image explicitly uses CPU-only wheel via `--index-url`.

### tokenizers 0.23.1
- **License:** Apache-2.0 (verified: METADATA classifier + GitHub LICENSE)
- **Purpose:** BPE tokenizer for SmallLM reasoning model
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### numpy 2.4.4
- **License:** BSD-3-Clause (verified: GitHub LICENSE.txt)
- **Purpose:** Numerical utilities for scoring, ranking, embedding math
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### gradio 4.44.1
- **License:** Apache-2.0 (verified: METADATA classifier + GitHub LICENSE)
- **Purpose:** WebUI chat interface and document upload UI
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### gradio_client 1.3.0
- **License:** Apache-2.0 (verified: METADATA classifier)
- **Purpose:** Client utilities for WebUI export functionality
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### fastapi 0.115.3
- **License:** MIT (verified: METADATA classifier + GitHub LICENSE)
- **Purpose:** HTTP API framework for /query, /ingest, /documents, /health, /ready, /stats
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### pydantic 2.9.2
- **License:** MIT (verified: METADATA classifier + GitHub LICENSE)
- **Purpose:** Data validation and serialization for API models
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### httpx 0.27.2
- **License:** BSD-3-Clause (verified: METADATA classifier + GitHub LICENSE.txt)
- **Purpose:** HTTP client for Gradio and API integrations
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### uvicorn 0.32.0
- **License:** BSD-3-Clause (verified: METADATA classifier + GitHub LICENSE.txt)
- **Purpose:** ASGI server for the FastAPI application
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### PyPDF2 3.0.1
- **License:** BSD-3-Clause (verified: LICENSE file contains 3 clauses including non-endorsement)
- **Purpose:** PDF document parsing for runtime upload pipeline
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW
- **Note:** PyPDF2 is the legacy package; successor is `pypdf`. Last PyPDF2 release is 3.0.1 (Dec 2022). No security patches since. Buyer should plan migration to `pypdf`.

### python-docx 1.2.0
- **License:** MIT (verified: pip show + GitHub LICENSE)
- **Purpose:** DOCX document parsing for runtime upload pipeline
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

---

## 4. Optional Runtime Dependencies (requirements-polish.txt)

Installed only when the optional Qwen2.5-1.5B-Instruct polish model is enabled.

### transformers 4.46.3 (pinned) / 5.15.0 (installed)
- **License:** Apache-2.0 (verified: pip show + GitHub LICENSE)
- **Purpose:** Model loading for Qwen2.5-1.5B-Instruct polish runtime
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW
- **Note:** Docker image does NOT install these by default.

### accelerate 1.0.1 (pinned) / 1.14.0 (installed)
- **License:** Apache-2.0 (verified: pip show)
- **Purpose:** Model acceleration for polish runtime
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

### huggingface_hub 0.26.1
- **License:** Apache-2.0 (verified: pip show)
- **Purpose:** Model download from HuggingFace Hub (polish model)
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

---

## 5. Evaluation/Offline Dependencies

### datasets 5.0.1
- **License:** Apache-2.0 (verified: pip show)
- **Purpose:** Used only by `src/download_corpus.py` to pull WikiText corpus from Hugging Face
- **Category:** evaluation (not shipped in Docker image)
- **Redistribution:** Permitted with notice
- **Commercial use:** PERMITTED
- **Risk:** LOW

---

## 6. Development-Only Dependencies

### psutil 7.2.2
- **License:** BSD-3-Clause (verified: pip show)
- **Purpose:** Memory monitoring in `scripts/concurrency_soak.py`, `scripts/run_resource_validation.py`, `scripts/scalability_benchmark.py`
- **Category:** dev only (not shipped in Docker image)
- **Notes:** Guarded by `try/except ImportError`; engine runs fine without it
- **Risk:** LOW

### requests 2.34.2
- **License:** Apache-2.0 (verified: pip show)
- **Purpose:** HTTP client in `src/download_polish_llm_direct.py` (offline download script)
- **Notes:** Transitive dependency of gradio/httpx; not pinned in requirements.txt
- **Risk:** LOW

---

## 7. Missing Runtime Dependencies

**None found.** All imports in production code (`src/`, `src/webui/`) are satisfied by `requirements.txt` plus Python stdlib.

---

## 8. Dockerfile Dependency Reproducibility

The Dockerfile pins exact versions via `requirements.txt`. PyTorch is installed separately with `--index-url` to enforce CPU-only. The `requirements-polish.txt` is NOT installed by the default Dockerfile — a buyer must explicitly enable it.

**Risk:** `pip install` without a lockfile can resolve transitive dependencies to different versions across builds. For acquisition, a `pip-compile` lockfile would be advisable.

---

## 9. Redistribution Implications

All 15 dependencies use OSI-approved licenses (MIT, Apache-2.0, BSD-3-Clause). All permit commercial redistribution with notice. No copyleft (GPL/AGPL) dependencies exist in the runtime path.

The RALG source code itself is under a **Source-Available Non-Commercial License** — the dependencies do not impose any additional restrictions beyond what the RALG license already states.

---

## 10. Recommendation for Buyer

- All runtime dependencies are commercially safe.
- PyPDF2 should be migrated to `pypdf` for continued security support.
- A `pip-compile` lockfile should be generated for reproducible Docker builds.
- The `requirements-polish.txt` dependency versions diverge from installed versions (pins are outdated but compatible).
