# Stage 2 Deployment Validation

`scripts\deployment_validation.py` performs a non-mutating `pip check` and
tries `/health` plus the Python SDK against a running API. Clean installation
is intentionally not performed in the active environment; use
`pip install --requirement requirements.txt` in a disposable environment.
Some mirrors do not publish the final `tokenizers==0.23.1`; the requirements
pin `0.23.1rc0`, whose `cp310-abi3` wheel is compatible with Python 3.11 and
the project's `Tokenizer` API.
Results are written to `logs/deployment_validation.json`. API and SDK status
are **unavailable** when no server is listening.
