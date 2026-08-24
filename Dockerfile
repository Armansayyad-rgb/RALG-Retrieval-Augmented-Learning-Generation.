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

WORKDIR /app

COPY requirements.txt .

# Install the CPU PyTorch wheel explicitly first. The later requirements
# install sees the satisfied torch requirement and keeps this build CPU-only.
RUN pip install --no-cache-dir --index-url ${TORCH_INDEX_URL} "torch==2.7.1"
RUN pip install --no-cache-dir -r requirements.txt

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
CMD ["python", "-m", "webui.app"]
