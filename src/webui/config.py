"""Configuration constants for the Gradio web UI.

Project paths (PROJECT_ROOT, LOGS_DIR) are sourced from the env-var-aware
root config repository-root `config.py` so the webui follows the same
override contract as `rag_chat_v2`. UI-specific constants (server host
and port, defaults, upload limits, example questions) live here because
they are webui-only.
"""

import os
from pathlib import Path

from config import LOGS_DIR, PROJECT_ROOT, UPLOAD_POLICY  # noqa: E402


# Project paths
# Mirrors rag_chat_v2.py constants, sourced from root config.

SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
RUNTIME_UPLOAD_DIR = Path(
    os.getenv("RUNTIME_UPLOAD_DIR", str(DATA_DIR / "runtime_uploads"))
).expanduser().resolve()


# Generated artifacts

FEEDBACK_LOG = LOGS_DIR / "webui_feedback.jsonl"
SESSIONS_LOG = LOGS_DIR / "webui_sessions.jsonl"


# Server settings
#
# Local Python runs default to localhost.
# Docker overrides these with:
#   WEBUI_HOST=0.0.0.0
#   WEBUI_PORT=7860
#
# This allows the Gradio server to bind correctly inside Docker while
# keeping local non-Docker usage restricted to localhost by default.

WEBUI_HOST = os.getenv("WEBUI_HOST", "127.0.0.1")

try:
    WEBUI_PORT = int(os.getenv("WEBUI_PORT", "7860"))
except ValueError:
    WEBUI_PORT = 7860

WEBUI_TITLE = "AI Project - RAG Chatbot"


# RAG tunables

DEFAULT_MAX_NEW_TOKENS = 50
DEFAULT_TOP_K = 3


# Default confidence threshold for highlighting in the UI

DEFAULT_DISPLAY_THRESHOLD = 0.60


# Upload limits

ALLOWED_UPLOAD_EXTS = UPLOAD_POLICY.allowed_extensions
MAX_UPLOAD_BYTES = UPLOAD_POLICY.max_batch_bytes
MAX_UPLOADED_CHUNKS = UPLOAD_POLICY.max_total_chunks_per_batch


def upload_policy_text() -> str:
    """Render user-facing upload limits from the authoritative policy."""
    extensions = ", ".join(sorted(UPLOAD_POLICY.allowed_extensions))
    per_file = ", ".join(
        f"{ext} {limit // (1024 * 1024)} MB"
        for ext, limit in sorted(UPLOAD_POLICY.per_file_bytes.items())
    )
    return (
        f"Supported types: {extensions}. "
        f"Per-file limits: {per_file}. "
        f"Batch limit: {UPLOAD_POLICY.max_batch_bytes // (1024 * 1024)} MB total; "
        f"extracted text: {UPLOAD_POLICY.max_extracted_text_chars:,} characters; "
        f"chunks: {UPLOAD_POLICY.max_chunks_per_document:,} per document, "
        f"{UPLOAD_POLICY.max_total_chunks_per_batch:,} per batch."
    )


# UI copy

EXAMPLE_QUESTIONS = [
    "Why did the Roman Empire decline?",
    "What caused World War I?",
    "Compare the economies of France and Germany in the 20th century.",
    "What is the capital of France?",
    "Summarize the plot of Hamlet.",
]