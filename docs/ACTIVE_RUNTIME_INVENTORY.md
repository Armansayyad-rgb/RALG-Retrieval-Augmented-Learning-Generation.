# Active Runtime Inventory

**Branch:** `hardening/acquisition-diligence-v1`
**Date:** 2026-08-25

---

## Classification Legend

| Status | Meaning |
|--------|---------|
| **ACTIVE PRODUCTION** | Used in the live runtime path (API + WebUI) |
| **ACTIVE SUPPORT** | Supporting module actively imported by production code |
| **EVALUATION** | Used in benchmark/evaluation scripts, not production runtime |
| **TRAINING/OFFLINE** | Used for offline training/fine-tuning only |
| **LEGACY (HISTORY)** | Retained for historical reference; not called in production |
| **SUPERSEDED** | Functionally replaced; retained only for backward compatibility |
| **REMOVAL CANDIDATE** | Can be removed in future cleanup without functional impact |

---

## 1. Core Runtime Modules

### ACTIVE PRODUCTION

| Module | Path | Role | Import Chain |
|--------|------|------|--------------|
| `runtime_architecture` | `src/runtime_architecture.py` | Unified execution plan, model registry, `execute_runtime()` — shared by API and WebUI | `api_server` → `execute_runtime`, `webui.hybrid_pipeline` → `execute_runtime` |
| `rag_chat_v2` | `src/rag_chat_v2.py` | RAG pipeline: routes questions, retrieves context, generates/extracts answers | `runtime_architecture` → `answer_question` |
| `retriever_hybrid` | `src/retriever_hybrid.py` | Full-question-first hybrid retriever — single authoritative retrieval path | `rag_chat_v2.retrieve_for_reasoning` → `retrieve_hybrid` |
| `retriever_v2` | `src/retriever_v2.py` | Core lexical retriever (TF-IDF index, factual-relation scoring) | `retriever_hybrid` → `retrieve_v2`, `rag_chat_v2` → `build_index`, `load_chunks` |
| `api_server` | `src/api_server.py` | FastAPI HTTP server (`/query`, `/ingest`, `/documents`, `/health`, `/ready`, `/stats`) | Entry point: `python -m api_server` |
| `webui/hybrid_pipeline` | `src/webui/hybrid_pipeline.py` | Chat turn routing — delegates to small model or Qwen polish LLM | `webui.app` → `route_through_hybrid` |
| `webui/chat_handler` | `src/webui/chat_handler.py` | Bridge between Gradio callbacks and pipeline; builds source citations, enforces grounding policy | `webui.hybrid_pipeline` → `build_answer_contract`, `collect_sources` |
| `webui/app` | `src/webui/app.py` | Gradio Blocks web UI (chat, upload, export, feedback) | Entry point: `python -m webui.app` |
| `webui/document_processor` | `src/webui/document_processor.py` | Document upload parsing (PDF via PyPDF2, DOCX via python-docx) | `api_server` → `ingest_document`, `webui.app` → `upload_document` |
| `config` | `src/config.py` | Central configuration: paths, model config, upload policy | Imported by most modules |

### ACTIVE SUPPORT

| Module | Path | Role | Import Chain |
|--------|------|------|--------------|
| `model` | `src/model.py` | SmallLM custom model definition | `rag_chat_v2` → `initialize_pipeline` |
| `model_v2` | `src/model_v2.py` | SmallLM V2 model definition | `rag_chat_v2` → `initialize_pipeline` |
| `embedding_model` | `src/embedding_model.py` | Embedding model for semantic scoring | `rag_chat_v2` → `initialize_pipeline` |
| `log_helper` | `src/log_helper.py` | Logging setup | `api_server`, `webui.app` |
| `extractor_v1` | `src/extractor_v1.py` | Factual answer extraction from context | `rag_chat_v2` → `extract_factual_answer` |
| `query_planner_v1` | `src/query_planner_v1.py` | Intent-aware query decomposition | `rag_chat_v2` → `runtime_plan` |
| `router_v1` | `src/router_v1.py` | Question routing (factual/comparison/general) | `rag_chat_v2` → `route_question` |
| `confidence_v1` | `src/confidence_v1.py` | Extraction confidence scoring | `rag_chat_v2` → `extraction_confidence` |
| `reasoning_confidence_v1` | `src/reasoning_confidence_v1.py` | Reasoning confidence scoring | `rag_chat_v2` |
| `webui/polish_llm` | `src/webui/polish_llm.py` | Qwen2.5-1.5B-Instruct polish runtime (optional) | `webui.hybrid_pipeline` → `polish_hybrid_answer` |
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
| `retriever_v4` | `src/retriever_v4.py` | **SUPERSEDED** | Intent-aware multi-query retriever. Replaced by `retriever_hybrid` as single authoritative path. Still imported by `rag_chat_v2` for `aggregate_results()` and `build_adaptive_query_plan()` utility functions (not for retrieval). |
| `model.py` (SmallLM V1) | `src/model.py` | **SUPERSEDED** | Original SmallLM definition; `model_v2.py` is the active version. Both still imported. |

---

## 4. Training/OFFLINE Modules

| Module | Path | Role |
|--------|------|------|
| `finetune_instructions` | `src/finetune_instructions.py` | Fine-tuning script for instruction model |
| `build_embedding_data` | `src/build_embedding_data.py` | Generates embedding training data from WikiText |
| `download_corpus` | `src/download_corpus.py` | Downloads WikiText from HuggingFace |
| `download_polish_llm` | `src/download_polish_llm.py` | Downloads Qwen2.5-1.5B-Instruct via hf_hub_download |
| `download_polish_llm_direct` | `src/download_polish_llm_direct.py` | Alternative direct download for Qwen model |

---

## 5. Evaluation/Benchmark Modules

| Module | Path | Role |
|--------|------|------|
| `benchmark_suite_v4.py` | `benchmark_suite_v4.py` | Main benchmark runner |
| `heldout_evaluation.py` | `scripts/heldout_evaluation.py` | Held-out evaluation |
| `heldout_evaluation_v2.py` | `scripts/heldout_evaluation_v2.py` | V2 held-out evaluation |
| `run_commercial_validation.py` | `scripts/run_commercial_validation.py` | 25-case commercial validation |
| `stage5_preliminary_evaluation.py` | `scripts/stage5_preliminary_evaluation.py` | Stage 5 preliminary evaluation |
| `stage5_evaluation.py` | `scripts/stage5_evaluation.py` | Stage 5 full evaluation |
| `run_ablation.py` | `scripts/run_ablation.py` | Ablation studies |
| `run_resource_validation.py` | `scripts/run_resource_validation.py` | Resource/performance validation |
| `concurrency_soak.py` | `scripts/concurrency_soak.py` | Concurrency stress testing |
| `scalability_benchmark.py` | `scripts/scalability_benchmark.py` | Scalability benchmarking |
| `test_all.bat` | `scripts/test_all.bat` | Full test runner (13 steps) |

---

## 6. Test Modules

| Module | Path | Role |
|--------|------|------|
| `test_retrieval_hybrid.py` | `src/test_retrieval_hybrid.py` | Hybrid retriever tests |
| `test_retrieval_performance.py` | `src/test_retrieval_performance.py` | Retrieval performance regression |
| `test_runtime_architecture.py` | `src/test_runtime_architecture.py` | Runtime architecture tests |
| `test_runtime_integration.py` | `src/test_runtime_integration.py` | API/WebUI integration tests |
| `test_unified_evidence.py` | `src/test_unified_evidence.py` | Evidence traceability and conflict tests |
| `test_upload_provenance.py` | `src/test_upload_provenance.py` | Upload/provenance tests |
| `test_api_input_hardening.py` | `src/test_api_input_hardening.py` | API input hardening tests |
| `test_portability.py` | `src/test_portability.py` | Portability tests |
| `test_readiness.py` | `src/test_readiness.py` | Readiness tests |
| `test_persistence.py` | `src/test_persistence.py` | Persistence tests |
| `regression_tests_v2.py` | `src/regression_tests_v2.py` | 23-case regression suite |
| `test_all_simple_benchmark.py` | `src/test_all_simple_benchmark.py` | 50-case simple benchmark |
| `test_all_hard_benchmark.py` | `src/test_all_hard_benchmark.py` | Hard benchmark |

---

## 7. Retrieval Dependency Graph

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

## 8. Docker Image Module Coverage

The Dockerfile runs `python -m webui.app` which imports:
- `webui/app.py` → `webui/hybrid_pipeline.py` → `rag_chat_v2.py` → `retriever_hybrid.py`, `retriever_v2.py`, `retriever_v4.py` (utilities only)
- `runtime_architecture.py` → `model.py`/`model_v2.py`, `embedding_model.py`
- All synthesizer modules, planner, router, confidence modules
- `webui/document_processor.py`, `webui/polish_llm.py` (lazy import), `webui/config.py`
- `config.py`, `log_helper.py`

**Not in Docker image:** `api_server.py` (standalone entry point), evaluation scripts, training scripts, benchmark scripts, test modules.
