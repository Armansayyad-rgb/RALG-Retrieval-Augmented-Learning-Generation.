# RALG Engine API Quickstart

Local, evidence-grounded question answering API built with FastAPI.

## Start the server

Run from the project root:

```bash
uvicorn src.api_server:app --host 127.0.0.1 --port 8000
```

The server loads the pipeline on first request (model + corpus index).
The default model checkpoint is `checkpoints/v2/reasoning_model_v1.pt`; the
tokenizer is `data/tokenizer_v2.json`. Override them with `MODEL_FILE` and
`TOKENIZER_FILE`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check, returns `{"status": "ok"}` |
| GET | `/ready` | Readiness status for model, tokenizer, corpus, and index |
| GET | `/stats` | Pipeline stats (device, model_loaded, chunk_count, knowledge_files, uptime_seconds) |
| GET | `/documents` | List persisted runtime document metadata |
| DELETE | `/documents/{document_id}` | Delete one persisted runtime document |
| POST | `/ingest` | Ingest plain text into the running pipeline |
| POST | `/query` | Ask a question, get answer + sources |

## curl examples

### /health

```bash
curl http://127.0.0.1:8000/health
```

Example response shape (answer content, scores, and latency vary with the knowledge base):
```json
{"status":"ok"}
```

### /ready

```bash
curl http://127.0.0.1:8000/ready
```

`200` means the model, tokenizer, corpus, and retrieval index are usable.
`503` means the process is alive but initialization is incomplete or failed.
The response contains safe state flags and a concise error, never local paths
or stack traces.

### /stats

```bash
curl http://127.0.0.1:8000/stats
```

Response:
```json
{
  "device": "cpu",
  "model_loaded": true,
  "chunk_count": 107650,
  "knowledge_files": ["data/wikitext_v2.txt", "data/knowledge_extra_v1.txt"],
  "uptime_seconds": 42.5
}
```

### /ingest

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text":"Safety step: de-energize the panel and verify zero voltage with a certified tester before removing the cover.","document_name":"compressor_sop"}'
```

Response:
```json
{
  "document_name": "compressor_sop",
  "added_chunks": 1,
  "total_chunks": 107651
}
```

### /query

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What safety step is required before opening the electrical panel?","top_k":5,"include_sources":true}'
```

Response:
```json
{
  "answer": "...",
  "supported": false,
  "confidence": null,
  "answer_type": "system",
  "sources": [
    {"rank": 1, "id": 107650, "preview": "Safety step: de-energize...", "score": 12.34}
  ],
  "latency_ms": 234.1,
  "error": null
}
```

## Python client (test script)

```bash
python src/test_api_demo.py
```

Assumes the server is already running on `http://127.0.0.1:8000`.
