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

## API documentation

FastAPI serves interactive API docs at:

- `/openapi.json` — OpenAPI schema (JSON)
- `/docs` — Swagger UI
- `/redoc` — ReDoc UI

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

Example response shape:
```json
{"status":"ok"}
```

### /ready

```bash
curl http://127.0.0.1:8000/ready
```

`200` means the model, tokenizer, corpus, and retrieval index are usable.
`503` means the process is alive but initialization is incomplete or failed.

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

Authenticated:

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-token" \
  -d '{"text":"Safety step: de-energize the panel and verify zero voltage with a certified tester before removing the cover.","document_name":"compressor_sop"}'
```

Response:
```json
{
  "document_id": "abc123...",
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

Authenticated:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-token" \
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
  "traceable": false,
  "conflict": false,
  "provenance": [],
  "error": null
}
```

### /query with document scoping

Restrict retrieval to specific runtime-uploaded documents:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What safety step is required before opening the electrical panel?",
    "top_k": 5,
    "include_sources": true,
    "document_ids": ["doc_id_1", "doc_id_2"]
  }'
```

When `document_ids` is provided, the runtime only considers chunks from those documents. Unscoped queries search the full knowledge base.

Each `document_id` must be a safe identifier: no empty/whitespace-only, `..`, `/`, `\`, control characters, or values longer than 255 characters. Malformed `document_ids` are rejected with `422` and `{"error": "Invalid request."}`. Up to 10 ids are allowed per request.

### /documents

```bash
curl http://127.0.0.1:8000/documents
```

Response:
```json
[
  {
    "document_id": "abc123...",
    "document_name": "compressor_sop",
    "chunk_count": 1,
    "upload_timestamp": "2026-01-01T00:00:00Z"
  }
]
```

### DELETE /documents/{document_id}

```bash
curl -X DELETE http://127.0.0.1:8000/documents/abc123...
```

Response:
```json
{
  "document_id": "abc123...",
  "deleted": true,
  "chunks_removed": 1
}
```

Malformed `document_id` values return `400` and unknown ids return `404`, both with the `{"error": ...}` envelope (consistent with the rest of the API).

## Python client (test script)

```bash
python src/test_api_demo.py
```

Assumes the server is already running on `http://127.0.0.1:8000`.

### Authenticated requests

If the server is started with `API_TOKEN`, pass the token to the client:

```python
from src.ralg_client import RALGClient

client = RALGClient(api_token="your-api-token")
print(client.query("What is the inspection interval?"))
```

When `api_token` is omitted, the client sends unauthenticated requests.

### Document-scoped queries

```python
response = client.query(
    "What safety step is required?",
    document_ids=["doc_id_1", "doc_id_2"]
)
```

When `document_ids` is provided, the runtime only considers chunks from those documents.
