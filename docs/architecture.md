# Architecture

RALG is a retrieval-first local AI pipeline.

## High-level flow

```text
Question
  -> api_server / webui
  -> execute_runtime()            shared orchestration boundary
  -> ExecutionPlan                intent + route decision
  -> factual extractor OR grounded reasoning
  -> retriever_hybrid             full-question-first hybrid retrieval
  -> unified support gate         evidence identity, traceability,
                                  conflict status, provenance
  -> supported answer OR abstention
```

## Main components

| Component | Role |
|---|---|
| Query planner | Builds retrieval queries from the user question |
| Retriever | Finds candidate evidence chunks from the knowledge base |
| Router | Chooses whether the question needs factual extraction, reasoning, or abstention logic |
| Reasoning model/path | Handles selected questions where lightweight reasoning is useful |
| Extractor | Produces grounded answers from retrieved support |
| Confidence/support logic | Decides whether the system should answer or abstain |
| Web UI | Provides an interactive Gradio interface |
| Evaluation suites | Test accuracy, support, false-premise rejection, and multi-hop behavior |
| `execute_runtime` | Shared orchestration boundary for API and WebUI |
| `retriever_hybrid` | Authoritative full-question-first hybrid retriever |

## Authoritative runtime path

- `src/api_server.py` → `execute_runtime()` → `rag_chat_v2.answer_question()` → `retriever_hybrid.retrieve()`
- `src/webui/hybrid_pipeline.py` → `execute_runtime()` → same grounded path
- API contract: `uvicorn src.api_server:app --host 127.0.0.1 --port 8000`
- Request uses `question`; response uses `sources` / `answer`
- Endpoints: `/health`, `/ready`, `/stats`, `/documents`, `DELETE /documents/{id}`, `/ingest`, `/query`

## Design constraints

The current design favors:

- local execution
- modest hardware
- evidence-grounded output
- limited extra retrieval passes
- simple dependencies
- repeatable evaluation

## Future architecture needs

- cleaner API layer
- separate public demo data from private/pilot data
- better benchmark runner
- deployment profiles for CPU and CUDA
- structured logs that avoid storing sensitive document text by default
