# Windows Test Runner

Use this after pulling the latest repo changes on Windows.

## Normal benchmark/compile test

From the repository root:

```powershell
scripts\test_all.bat
```

This runs:

- Python version check
- compile check for important files
- simple 50-case benchmark
- hard benchmark
- regression, hardening, provenance, and unified-evidence tests
- commercial validation

The runner must be invoked from any clone's repository root, but runtime
configuration itself is path-independent. Set `RUNTIME_UPLOAD_DIR`,
`AI_PROJECT_DATA_DIR`, `MODEL_FILE`, or `TOKENIZER_FILE` to use external
locations.

## API demo test

First start the API server:

```powershell
uvicorn src.api_server:app --host 127.0.0.1 --port 8000
```

Then open another PowerShell in the repository root and run:

```powershell
scripts\test_all.bat api
```

This also runs `src\test_api_demo.py` if it exists.

## Output

Benchmark output is written to:

```text
logs\retrieval_proof_v1_results.json
```
