# Clean-clone setup

## Prerequisites

- Python 3.11
- Git
- (Optional) Docker + Docker Compose for containerized runs

## Local setup

```bash
git clone <repository-url>
cd <repository-root>
python -m venv .venv
.\.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Unix
pip install -r requirements.txt
```

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

The container binds `WEBUI_HOST=0.0.0.0` and `WEBUI_PORT=7860` by default.

## Notes

This setup is for controlled technical evaluation. It does not constitute full
production deployment qualification.
