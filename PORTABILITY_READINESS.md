# Portability and Readiness

This Prototype 1 checkpoint is validated with Python 3.11 on Windows. Create
a fresh environment and install `requirements.txt`; the repository does not
require a particular clone directory or current working directory for its
configured paths.

## Startup

From the repository root:

```powershell
python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8000
python -m webui_bootstrap
```

From another directory, use the repository as the application directory:

```powershell
python -m uvicorn src.api_server:app --app-dir <repository-root> --host 127.0.0.1 --port 8000
```

The API requires the external reasoning checkpoint
`checkpoints/v2/reasoning_model_v1.pt` and tokenizer
`data/tokenizer_v2.json` unless `MODEL_FILE` and `TOKENIZER_FILE` override
them. Knowledge files default to `DATA_DIR`; `AI_PROJECT_DATA_DIR` and
`KNOWLEDGE_FILES` provide overrides.

`GET /health` is a lightweight process-liveness check and does not initialize
the model. `GET /ready` returns HTTP 200 only when model, tokenizer, corpus,
and retrieval index are usable. Initialization failures return HTTP 503 with
safe state flags and no local paths or stack traces.

Runtime uploads persist under `DATA_DIR/runtime_uploads` by default and Docker
mounts `/app/data` through `ralg_data`. This remains Prototype 1 storage:
there are no multi-process transactions, authentication, or production-grade
durability guarantees.

Validation performed for this checkpoint: repository compile checks, the
Windows test runner, regression/evidence/provenance/persistence suites, and
an isolated non-repository-cwd configuration check. Docker validation depends
on Docker Desktop/daemon availability.
