# Stage 2 Deployment Validation

`scripts\deployment_validation.py` performs a non-mutating `pip check` and
tries `/health` plus the Python SDK against a running API. Clean installation
is intentionally not performed in the active environment; use
`pip install --requirement requirements.txt` in a disposable environment.
The stable `tokenizers==0.23.1` release is required for Python 3.11 and the
project's `Tokenizer` API.
Results are written to `logs/deployment_validation.json`. API and SDK status
are **unavailable** when no server is listening.

Validation on Python 3.11 completed successfully with the full
`requirements.txt`; `tokenizers 0.23.1` imported and the `Tokenizer` API
loaded. The disposable environment was removed after validation.

**PASS — isolated live API/SDK lifecycle:** Using a disposable
`RUNTIME_UPLOAD_DIR` and one Uvicorn worker, `/health`, `/ready`, `/stats`, and
`/documents` succeeded. A temporary document was ingested, queried with
`supported=true` and provenance, deleted, and confirmed absent after restart.
A second document recovered after restart, was queried successfully, and was
deleted. The SDK independently passed health, readiness, stats, ingest, list,
supported query, unsupported query (`supported=false`), and delete. Responses
contained no absolute paths, tracebacks, secrets, or internal exceptions.

**PASS — process boundary documented:** Lifecycle locks are process-local.
Pilot deployments must use one application worker; multiple Uvicorn workers
are not claimed safe for shared runtime-document mutations.
