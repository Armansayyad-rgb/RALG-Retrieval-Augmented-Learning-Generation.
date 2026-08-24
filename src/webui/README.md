# AI Project - Web UI (Phase 1 MVP)

A Gradio web interface for the AI Project RAG chatbot. Lets non-technical users ask questions and inspect the answers, supporting evidence, and confidence of the existing `rag_chat_v2` pipeline.

## Run it locally

```powershell
cd <repository-root>
python src\webui_bootstrap.py
```

Then open http://127.0.0.1:7860.

## Files in this package

| File | Purpose |
|---|---|
| `app.py` | Gradio Blocks app; the only entry point. |
| `chat_handler.py` | Bridges the RAG pipeline to UI callbacks, normalizes sources. |
| `config.py` | UI constants (host, port, defaults, paths). |
| `__init__.py` | Package marker. |
| `README.md` | This file. |

## What works today (Phase 1)

- Chat bubble conversation with user + assistant turns
- "Send" button + Enter-to-submit
- "Clear conversation" button
- Answer detail panel showing intent, answer type, supported flag, color-coded confidence
- Sources list (rank + chunk id + score + snippet) shown below the answer and as JSON
- Settings: top-K slider, confidence threshold slider
- Example questions to start from
- Mobile-friendly (Gradio default responsive layout)
- Streaming-style: full answer appears once the pipeline finishes; true token streaming comes in Phase 3

## What is not in this build (later phases)

- Document upload (PDF / DOCX / TXT) - Phase 2
- Conversation export - Phase 3
- Multiple sessions - Phase 3
- User feedback (thumbs up/down) - Phase 3
- True token-level streaming - Phase 3
- HuggingFace Spaces deployment - Phase 4

See `WEB_UI_PLAN.md` at the repository root for the full roadmap.

## Backend integration

The Gradio layer calls `rag_chat_v2.answer_question()` unchanged. Runtime
documents are restored during the same canonical pipeline initialization used by
the API.

When the upstream pipeline is extended to expose `result["sources"]` natively, `collect_sources()` can be replaced with `result.get("sources", [])` for zero overhead.
