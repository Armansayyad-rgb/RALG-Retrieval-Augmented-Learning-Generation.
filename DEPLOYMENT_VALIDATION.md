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
