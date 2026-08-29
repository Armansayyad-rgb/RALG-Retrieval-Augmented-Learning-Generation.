# Repository Layout

RALG currently contains both product/runtime code and research/evaluation tooling. This document makes those boundaries explicit without moving files that may still be imported by the active system.

## Runtime / product-facing code

- `src/api_server.py` — local FastAPI interface (`uvicorn src.api_server:app --host 127.0.0.1 --port 8000`)
- `src/runtime_architecture.py` — shared orchestration boundary (`execute_runtime`); used by API and WebUI
- `src/rag_chat_v2.py` — main question-answering orchestration
- `src/query_planner_v1.py` — intent/query planning
- `src/retriever_hybrid.py` — **authoritative** full-question-first hybrid retriever
- `src/retriever_v2.py` — core lexical retriever (used by `retriever_hybrid` for candidate generation)
- `src/webui/` — Gradio UI, document ingestion, feedback, export, and optional answer-polish components
- `config.py` — shared runtime paths and settings

Changes to these files can directly affect benchmark and user-facing behavior and should be covered by regression tests.

## Legacy / superseded modules (not authoritative)

These files remain in the repository for historical/reproducibility reasons but are **not** the active production path:

- `src/retriever_v4.py` — **SUPERSEDED**. Intent-aware multi-query retriever. Replaced by `retriever_hybrid` as the single authoritative retrieval path. Still imported by `rag_chat_v2` for `aggregate_results()` and `build_adaptive_query_plan()` utility functions only.
- `src/retriever_v3.py` — **SUPERSEDED**. Intermediate retriever version between v2 and v4/hybrid. Not imported by any production path.
- `src/hybrid_search.py` — **SUPERSEDED**. Earlier semantic search module. Superseded by `retriever_hybrid`.
- `src/rag_chat.py` — **SUPERSEDED**. Legacy V1 RAG pipeline. Replaced by `rag_chat_v2`. Retained for historical reference.
- `src/model.py` — **SUPERSEDED**. Original SmallLM definition. `model_v2.py` is the active version. Not imported by any production runtime path.

## Evaluation / benchmark code

- `src/retrieval_proof_v1.py`
- benchmark/evaluation scripts under `src/`
- `data/technical_doc_benchmark_v1.jsonl`
- `data/technical_doc_benchmark_hard_v1.jsonl`
- `data/technical_docs_sample.txt`
- `data/technical_docs_hard_sample.txt`
- `BENCHMARKS.md`
- `BENCHMARK_RESULTS.md`
- `RELIABILITY_BENCHMARK.md`

Benchmark data should remain fixed for a reported run. Production code must not contain question-specific or answer-specific logic added solely to make benchmark cases pass.

## Research / training utilities

Files such as the following are build or experimentation utilities rather than the primary runtime path:

- `src/build_embedding_data.py`
- `src/build_extractive_qa_v4.py`
- `src/build_instruction_data.py`
- `src/build_instruction_data_v2.py`
- `src/build_instruction_data_v3.py`
- `src/build_reasoning_data_v1.py`
- `src/build_knowledge.py`
- corpus/model download utilities

They remain in place for reproducibility while the project is under active development. A future cleanup may move them to `tools/` or `research/` once imports and workflows are verified.

## Generated / large artifacts

- `checkpoints/` and model weights are intentionally ignored by Git.
- `logs/` and local feedback/session records are ignored.
- `indexes/knowledge.json` is a generated index currently tracked for historical/reproducibility reasons and should be reviewed before a future repository-size cleanup.
- `data/wikitext_v2.txt` is a large tracked corpus and should eventually be replaced by a reproducible download step or external artifact once corpus provenance and release workflow are finalized.

## Change-safety rule

Before moving or deleting a file:

1. search for imports/references;
2. verify the active local and Docker entrypoints;
3. run compile/tests/benchmarks as appropriate; and
4. avoid combining repository-layout refactors with retrieval-quality changes in the same commit.

This keeps engineering cleanup separate from model/retrieval behavior changes and makes benchmark regressions easier to diagnose.
