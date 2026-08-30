# Clean-clone setup

## Prerequisites

- Python exactly 3.11 (no other minor version is supported)
- Git
- (Optional) Docker + Docker Compose for containerized runs

## Local setup

Windows development environment (uses `requirements.txt`):

```powershell
git clone <repository-url>
cd <repository-root>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Authoritative Linux / Python 3.11 reproducible deployment (uses the committed
lock file `requirements.lock.txt`):

```bash
git clone <repository-url>
cd <repository-root>
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes \
  --index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  -r requirements.lock.txt
```

`requirements.txt` holds the direct, human-maintained CORE pins and remains the
Windows developer workflow. `requirements.lock.txt` is the fully resolved,
authoritative dependency set for Linux/Python 3.11 deployment and is what the
Docker image installs. PyPI is the primary index; the CPU PyTorch wheel index
is an extra index.

`requirements-polish.txt` is OPTIONAL polish and is **not** part of the
authoritative core deployment lock: `transformers` and `accelerate` are
optional polish dependencies that must not be expected in `requirements.lock.txt`
or in the Docker image.

## Regenerating the dependency lock (manual / authoritative)

The authoritative core lock is generated with `pip-tools==7.4.1` on
Linux/Python 3.11 using this full command (no `--reuse-hashes` — a full hash
regeneration produces the committed lock):

```bash
python -m pip install "pip-tools==7.4.1"
pip-compile requirements.txt \
  --generate-hashes \
  --no-upgrade \
  --no-header \
  --no-annotate \
  --index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  --output-file requirements.lock.txt
```

## CI freshness check

CI does **not** run that full regeneration. Instead it installs
`pip-tools==7.4.1` on Linux/Python 3.11, seeds a temporary copy of the
committed lock, and re-runs `pip-compile` with the extra `--reuse-hashes` flag
so it reuses the existing hashes (full hash regeneration across the PyTorch
index is bandwidth-heavy). It writes only to the temporary file and fails if
the regenerated result differs (byte-compare) from the committed
`requirements.lock.txt`. The committed lock is never overwritten, and
`transformers`/`accelerate` are not expected.

## Configuration

```bash
copy .env.example .env
```

Edit `.env` for local paths. The repository defaults assume execution from the
repository root; `AI_PROJECT_ROOT` resolves automatically when unset.

## Required artifacts

- `data/tokenizer_v2.json` - required tracked tokenizer
- `checkpoints/v2/reasoning_model_v1.pt` - optional external model checkpoint;
  the core API and Gradio UI run without it, but model-backed answers require it

## Run

```bash
python -m webui_bootstrap
```

## Docker

```bash
docker compose up
```

The image is built on `python:3.11-slim` and installs `requirements.lock.txt`,
so container builds use the authoritative locked dependency set. The container
binds `WEBUI_HOST=0.0.0.0` and `WEBUI_PORT=7860` by default.

## Notes

This setup is for controlled technical evaluation. It does not constitute full
production deployment qualification.
