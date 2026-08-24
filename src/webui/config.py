"""Configuration constants for the Gradio web UI.

Project paths (PROJECT_ROOT, LOGS_DIR) are sourced from the env-var-aware
root config repository-root `config.py` so the webui follows the same
override contract as `rag_chat_v2`. UI-specific constants (server host
and port, defaults, upload limits, example questions) live here because
they are webui-only.
"""

import os
import sys
from pathlib import Path

# Resolve `from config import ...` to the env-var-aware config at
# `<project>/config.py` unambiguously. `src/config.py` would shadow
# this on a cwd==src/ run because it defines an unrelated
# `MODEL_CONFIG` dict. We load the root config by absolute path into
# `sys.modules['config']` BEFORE the import statement runs, so the
# lookup skips the file-system resolver entirely. Same trick used by
# `rag_chat_v2.py` so the two modules share the same config source.

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
_ROOT_CONFIG_PATH = _PROJECT_ROOT / "config.py"

import importlib.util as _importlib_util

_spec = _importlib_util.spec_from_file_location(
    "config", str(_ROOT_CONFIG_PATH)
)

if _spec is None or _spec.loader is None:
    raise ImportError(
        f"Could not load project config at {_ROOT_CONFIG_PATH}. "
        f"Expected an env-var-aware config.py at the project root."
    )

_project_config = _importlib_util.module_from_spec(_spec)
_project_config.__package__ = ""

sys.modules["config"] = _project_config
_spec.loader.exec_module(_project_config)

from config import LOGS_DIR, PROJECT_ROOT  # noqa: E402


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

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_UPLOADED_CHUNKS = 5000

ALLOWED_UPLOAD_EXTS = {
    ".pdf",
    ".docx",
    ".txt",
}


# UI copy

EXAMPLE_QUESTIONS = [
    "Why did the Roman Empire decline?",
    "What caused World War I?",
    "Compare the economies of France and Germany in the 20th century.",
    "What is the capital of France?",
    "Summarize the plot of Hamlet.",
]