# Active Runtime Inventory

**Branch:** `hardening/acquisition-diligence-v1`
**Date:** 2026-08-25 (review-corrected)

---

## Classification Legend

| Status | Meaning |
|--------|---------|
| **ACTIVE PRODUCTION** | Used in the live runtime path (API + WebUI) |
| **ACTIVE SUPPORT** | Supporting module actively imported by production code |
| **EVALUATION** | Used in benchmark/evaluation scripts, not production runtime |
| **TRAINING/OFFLINE** | Used for offline training/fine-tuning only |
| **LEGACY BUT HISTORICALLY REQUIRED** | Retained for historical reference or reproducibility; not called in production |
| **SUPERSEDED** | Functionally replaced; retained only for backward compatibility or utility functions |
| **CANDIDATE FOR FUTURE REMOVAL** | Can be removed in future cleanup without functional impact |
| **TEST** | Unit, integration, regression, or validation test modules |

---

## 1. Core Runtime Modules

### ACTIVE PRODUCTION

| Module | Path | Role | Import Chain |
|--------|------|------|--------------|
| `runtime_architecture` | `src/runtime_architecture.py` | Unified execution plan, model registry, `execute_runtime()` -- shared by API and WebUI | `api_server` -> `execute_runtime`, `webui.hybrid_pipeline` -> `execute_runtime` |
| `rag_chat_v2` | `src/rag_chat_v2.py` | RAG pipeline: routes questions, retrieves context, generates/extracts answers | `runtime_architecture` -> `answer_question` |
| `retriever_hybrid` | `src/retriever_hybrid.py` | Full-question-first hybrid retriever -- single authoritative retrieval path | `rag_chat_v2.retrieve_for_reasoning` -> `retrieve_hybrid` |
| `retriever_v2` | `src/retriever_v2.py` | Core lexical retriever (TF-IDF index, factual-relation scoring) | `retriever_hybrid` -> `retrieve_v2`, `rag_chat_v2` -> `build_index`, `load_chunks` |
| `api_server` | `src/api_server.py` | FastAPI HTTP server (`/query`, `/ingest`, `/documents`, `/health`, `/ready`, `/stats`) | Entry point: `python -m api_server` |
| `webui/hybrid_pipeline` | `src/webui/hybrid_pipeline.py` | Chat turn routing -- delegates to small model or Qwen polish LLM | `webui.app` -> `route_through_hybrid` |
| `webui/chat_handler` | `src/webui/chat_handler.py` | Bridge between Gradio callbacks and pipeline; builds source citations, enforces grounding policy | `webui.hybrid_pipeline` -> `build_answer_contract`, `collect_sources` |
| `webui/app` | `src/webui/app.py` | Gradio Blocks web UI (chat, upload, export, feedback) | Entry point: `python -m webui.app` |
| `webui/document_processor` | `src/webui/document_processor.py` | Document upload parsing (PDF via PyPDF2, DOCX via python-docx) | `api_server` -> `ingest_document`, `webui.app` -> `upload_document` |
| `config` | `src/config.py` | Central configuration: paths, model config, upload policy | Imported by most modules |

### ACTIVE SUPPORT

| Module | Path | Role | Import Chain |
|--------|------|------|--------------|
| `model_v2` | `src/model_v2.py` | SmallLM V2 model definition (active model used at runtime) | `rag_chat_v2` -> `from model_v2 import SmallLMV2` -> `initialize_pipeline` |
| `embedding_model` | `src/embedding_model.py` | Embedding model for semantic scoring | `rag_chat_v2` -> `initialize_pipeline` |
| `log_helper` | `src/log_helper.py` | Logging setup | `api_server`, `webui.app` |
| `extractor_v1` | `src/extractor_v1.py` | Factual answer extraction from context | `rag_chat_v2` -> `extract_factual_answer` |
| `query_planner_v1` | `src/query_planner_v1.py` | Intent-aware query decomposition | `rag_chat_v2` -> `runtime_plan` |
| `router_v1` | `src/router_v1.py` | Question routing (factual/comparison/general) | `rag_chat_v2` -> `route_question` |
| `confidence_v1` | `src/confidence_v1.py` | Extraction confidence scoring | `rag_chat_v2` -> `extraction_confidence` |
| `reasoning_confidence_v1` | `src/reasoning_confidence_v1.py` | Reasoning confidence scoring | `rag_chat_v2` |
| `webui/polish_llm` | `src/webui/polish_llm.py` | Qwen2.5-1.5B-Instruct polish runtime (optional) | `webui.hybrid_pipeline` -> `polish_hybrid_answer` |
| `webui/export` | `src/webui/export.py` | Chat export functionality | `webui.app` |
| `webui/feedback_log` | `src/webui/feedback_log.py` | User feedback logging | `webui.app` |
| `webui/config` | `src/webui/config.py` | WebUI-specific configuration | `webui.app`, `webui.hybrid_pipeline` |

---

## 2. Synthesizer Modules (ACTIVE PRODUCTION)

All synthesizers are called by `rag_chat_v2` for specialized intent handling.

| Module | Path | Role |
|--------|------|------|
| `causal_synthesizer_v1` | `src/causal_synthesizer_v1.py` | Causal "why" questions |
| `change_synthesizer_v1` | `src/change_synthesizer_v1.py` | Change/comparison questions |
| `comparison_synthesizer_v1` | `src/comparison_synthesizer_v1.py` | Direct comparison questions |
| `comparison_planner_v1` | `src/comparison_planner_v1.py` | Comparison query planning |
| `comparison_retrieval_v1` | `src/comparison_retrieval_v1.py` | Comparison retrieval |
| `comparison_confidence_v1` | `src/comparison_confidence_v1.py` | Comparison confidence scoring |
| `effect_synthesizer_v1` | `src/effect_synthesizer_v1.py` | Effect/consequence questions |
| `entity_list_synthesizer_v1` | `src/entity_list_synthesizer_v1.py` | Entity enumeration |
| `structure_synthesizer_v1` | `src/structure_synthesizer_v1.py` | Structural questions |
| `summary_synthesizer_v1` | `src/summary_synthesizer_v1.py` | Summary questions |

---

## 3. SUPERSEDED Modules (Retained for History)

| Module | Path | Status | Notes |
|--------|------|--------|-------|
| `model.py` (SmallLM V1) | `src/model.py` | **SUPERSEDED** | Original SmallLM definition. `model_v2.py` is the active version. `model.py` is NOT imported by any production runtime path; used only by training/legacy scripts (`finetune_instructions.py`, `rag_chat.py`, `train.py`). |
| `retriever_v4` | `src/retriever_v4.py` | **SUPERSEDED** | Intent-aware multi-query retriever. Replaced by `retriever_hybrid` as single authoritative retrieval path. Still imported by `rag_chat_v2` for `aggregate_results()` and `build_adaptive_query_plan()` utility functions (not for retrieval). |
| `rag_chat.py` | `src/rag_chat.py` | **SUPERSEDED** | Legacy V1 RAG pipeline. Replaced by `rag_chat_v2`. Retained for historical reference. |
| `retriever_v3` | `src/retriever_v3.py` | **SUPERSEDED** | Intermediate retriever version between v2 and v4/hybrid. Not imported by any production path. |
| `hybrid_search.py` | `src/hybrid_search.py` | **SUPERSEDED** | Earlier semantic search module. Superseded by `retriever_hybrid`. |

---

## 4. LEGACY BUT HISTORICALLY REQUIRED

| Module | Path | Role |
|--------|------|------|
| `webui_launcher.py` | `src/webui_launcher.py` | Thin launcher: `from webui.app import main` |
| `webui_bootstrap.py` | `src/webui_bootstrap.py` | Gradio compatibility bootstrap/patch |
| `ralg_client.py` | `src/ralg_client.py` | Client library for the RALG API |
| `search_knowledge.py` | `src/search_knowledge.py` | Standalone knowledge search utility |
| `generate.py` | `src/generate.py` | V1 generation script |
| `generate_v2.py` | `src/generate_v2.py` | V2 generation script |
| `evidence_selector_v1.py` | `src/evidence_selector_v1.py` | Evidence selection logic |

---

## 5. TRAINING/OFFLINE Modules

| Module | Path | Role |
|--------|------|------|
| `finetune_instructions` | `src/finetune_instructions.py` | Fine-tuning script for instruction model |
| `finetune_instructions_v2` | `src/finetune_instructions_v2.py` | V2 fine-tuning script for instruction model |
| `finetune_v2_instructions` | `src/finetune_v2_instructions.py` | Alternative V2 instruction fine-tuning |
| `finetune_v4_extractive` | `src/finetune_v4_extractive.py` | V4 extractive fine-tuning |
| `finetune_reasoning_v1` | `src/finetune_reasoning_v1.py` | Reasoning model fine-tuning |
| `train` | `src/train.py` | V1 model training script |
| `train_v2` | `src/train_v2.py` | V2 model training script |
| `train_v2_continue` | `src/train_v2_continue.py` | V2 training continuation script |
| `train_embeddings` | `src/train_embeddings.py` | Embedding model training |
| `train_tokenizer` | `src/train_tokenizer.py` | Tokenizer training |
| `train_tokenizer_v2` | `src/train_tokenizer_v2.py` | V2 tokenizer training |
| `build_embedding_data` | `src/build_embedding_data.py` | Generates embedding training data from WikiText |
| `build_knowledge` | `src/build_knowledge.py` | Knowledge corpus builder |
| `build_instruction_data` | `src/build_instruction_data.py` | Instruction training data builder |
| `build_instruction_data_v2` | `src/build_instruction_data_v2.py` | V2 instruction training data builder |
| `build_instruction_data_v3` | `src/build_instruction_data_v3.py` | V3 instruction training data builder |
| `build_reasoning_data_v1` | `src/build_reasoning_data_v1.py` | Reasoning training data builder |
| `build_extractive_qa_v4` | `src/build_extractive_qa_v4.py` | V4 extractive QA data builder |
| `filter_extractive_qa_v4` | `src/filter_extractive_qa_v4.py` | V4 extractive QA data filter |
| `filter_reasoning_data_v1` | `src/filter_reasoning_data_v1.py` | Reasoning data filter |
| `download_corpus` | `src/download_corpus.py` | Downloads WikiText from HuggingFace |
| `download_polish_llm` | `src/download_polish_llm.py` | Downloads Qwen2.5-1.5B-Instruct via hf_hub_download |
| `download_polish_llm_direct` | `src/download_polish_llm_direct.py` | Alternative direct download for Qwen model |

---

## 6. EVALUATION/BENCHMARK Modules

| Module | Path | Role |
|--------|------|------|
| `benchmark_suite_v4.py` | `benchmark_suite_v4.py` | Main benchmark runner |
| `retrieval_proof_v1.py` | `src/retrieval_proof_v1.py` | Retrieval proof/benchmark script |
| `reliability_benchmark_v2.py` | `src/reliability_benchmark_v2.py` | Reliability benchmarking |
| `performance_profile_v1.py` | `src/performance_profile_v1.py` | Performance profiling |
| `evaluation_suite_v1.py` | `src/evaluation_suite_v1.py` | V1 evaluation suite |
| `evaluation_suite_v2.py` | `src/evaluation_suite_v2.py` | V2 evaluation suite |
| `evaluation_suite_v3.py` | `src/evaluation_suite_v3.py` | V3 evaluation suite |
| `heldout_evaluation.py` | `scripts/heldout_evaluation.py` | Held-out evaluation |
| `heldout_evaluation_v2.py` | `scripts/heldout_evaluation_v2.py` | V2 held-out evaluation |
| `run_commercial_validation.py` | `scripts/run_commercial_validation.py` | 10-case commercial validation |
| `stage5_preliminary_evaluation.py` | `scripts/stage5_preliminary_evaluation.py` | Stage 5 preliminary evaluation |
| `stage5_evaluation.py` | `scripts/stage5_evaluation.py` | Stage 5 full evaluation |
| `run_ablation.py` | `scripts/run_ablation.py` | Ablation studies |
| `run_resource_validation.py` | `scripts/run_resource_validation.py` | Resource/performance validation |
| `concurrency_soak.py` | `scripts/concurrency_soak.py` | Concurrency stress testing |
| `scalability_benchmark.py` | `scripts/scalability_benchmark.py` | Scalability benchmarking |

---

## 7. TEST Modules

### Unit / Architecture Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_runtime_architecture.py` | `src/test_runtime_architecture.py` | Runtime architecture unit tests | YES |
| `test_retrieval_hybrid.py` | `src/test_retrieval_hybrid.py` | Hybrid retriever unit tests | YES |

### Integration Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_runtime_integration.py` | `src/test_runtime_integration.py` | API/WebUI integration (execute_runtime parity) | YES |

### Retrieval / Performance Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_retrieval_performance.py` | `src/test_retrieval_performance.py` | Retrieval correctness and performance regression (10 cases) | YES |

### Evidence / Traceability / Conflict Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_unified_evidence.py` | `src/test_unified_evidence.py` | Evidence traceability and conflict behavior (10 cases) | YES |
| `test_traceability.py` | `src/test_traceability.py` | Source attribution and provenance chain (7 cases) | YES |
| `test_conflict_detection.py` | `src/test_conflict_detection.py` | Conflicting evidence detection (9 cases) | YES |
| `test_asserted_relation.py` | `src/test_asserted_relation.py` | Asserted relation tests | YES |

### Upload / Provenance Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_upload_provenance.py` | `src/test_upload_provenance.py` | Upload parsing, provenance, duplicate detection (25 cases) | YES |

### API Hardening Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_api_input_hardening.py` | `src/test_api_input_hardening.py` | Oversized/blank/extra-field rejection (8 cases) | YES |

### Persistence Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_document_persistence.py` | `src/test_document_persistence.py` | Registry corruption, missing docs, restart recovery (8 cases) | YES |

### Portability Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_portability_readiness.py` | `src/test_portability_readiness.py` | Path portability and pipeline init under error conditions (8 cases) | YES |

### Regression Harnesses

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `regression_tests_v2.py` | `src/regression_tests_v2.py` | 23-case regression suite (10 baseline + 7 routing + 6 unsupported) | YES |
| `regression_tests_v1.py` | `src/regression_tests_v1.py` | Legacy V1 regression suite (retained for history) | LEGACY |

### Docker Lifecycle Tests

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_docker_lifecycle.py` | `scripts/test_docker_lifecycle.py` | Docker Compose lifecycle qualification (19 checks) | YES |

### Additional Test Modules

| Module | Path | Role | Verified |
|--------|------|------|----------|
| `test_embeddings.py` | `src/test_embeddings.py` | Embedding model tests | YES |
| `test_feedback_log.py` | `src/test_feedback_log.py` | Feedback logging tests | YES |
| `test_stream_generate.py` | `src/test_stream_generate.py` | Stream generation tests | YES |
| `test_api_demo.py` | `src/test_api_demo.py` | Live API demo test (requires running server) | YES |

### Test Runner

| Module | Path | Role |
|--------|------|------|
| `test_all.bat` | `scripts/test_all.bat` | Full test runner (13 steps, compile + all suites) |

---

## 8. Retrieval Dependency Graph

```
retriever_v2 (core lexical)
    ↑
retriever_hybrid (fuses v2 + secondary sub-queries)
    ↑
rag_chat_v2 (imports v2 for build_index/load_chunks, hybrid for retrieval, v4 for aggregate/adaptive)
    ↑
runtime_architecture.execute_runtime (shared by API + WebUI)
    ↑
api_server  |  webui/hybrid_pipeline → webui/app
```

**Key insight:** `retriever_v4` is NOT called for retrieval in any production path. It is retained only for `aggregate_results()` and `build_adaptive_query_plan()` utility functions used by `rag_chat_v2`.

---

## 9. Docker Image Module Coverage

The Dockerfile runs `python -m webui.app` which imports:
- `webui/app.py` -> `webui/hybrid_pipeline.py` -> `rag_chat_v2.py` -> `retriever_hybrid.py`, `retriever_v2.py`, `retriever_v4.py` (utilities only)
- `runtime_architecture.py` -> `model_v2.py`, `embedding_model.py`
- All synthesizer modules, planner, router, confidence modules
- `webui/document_processor.py`, `webui/polish_llm.py` (lazy import), `webui/config.py`
- `config.py`, `log_helper.py`

**Not in Docker image:** `api_server.py` (standalone entry point), evaluation scripts, training scripts, benchmark scripts, test modules.
