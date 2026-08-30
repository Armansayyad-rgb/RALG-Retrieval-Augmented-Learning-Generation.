# RALG Engine - CPU-only Docker image.
#
# Build: docker build -t ralg-engine .
# Run:   docker run -p 7860:7860 -v ralg_data:/app/data -v ralg_logs:/app/logs ralg-engine

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG PYPI_INDEX_URL=https://pypi.org/simple

WORKDIR /app

COPY requirements.lock.txt .

# Authoritative Linux install path: every dependency version comes from the
# committed lock file (regenerated with pip-tools==7.4.1 from requirements.txt).
# PyPI stays the primary index and the CPU PyTorch wheel index is the extra
# index, matching the lock generation contract. Hashes are enforced explicitly
# so the image only installs the exact locked wheels.
RUN pip install --no-cache-dir --require-hashes \
        --index-url ${PYPI_INDEX_URL} \
        --extra-index-url ${TORCH_INDEX_URL} \
        -r requirements.lock.txt

COPY . .

RUN mkdir -p /app/data/runtime_uploads /app/logs /app/checkpoints

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src:/app \
    AI_PROJECT_ROOT=/app \
    WEBUI_HOST=0.0.0.0 \
    WEBUI_PORT=7860

EXPOSE 7860

# src/webui/app.py already owns the supported Gradio configuration. Start the
# real module directly so the container executes the same source committed to Git.
CMD ["python", "-m", "webui_bootstrap"]
