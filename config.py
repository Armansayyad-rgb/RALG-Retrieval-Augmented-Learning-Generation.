"""Centralized configuration for the RALG pipeline.

All paths and runtime settings can be overridden through environment variables.
By default, paths resolve relative to this repository rather than a machine-specific
location, so a normal clone works from any directory.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Architecture used by the legacy local language-model modules.  Keeping this
# small config in the canonical project config avoids import-order-dependent
# import-order shims.
MODEL_CONFIG = {
    "vocab_size": 7207,
    "context_length": 512,
    "d_model": 384,
    "n_heads": 6,
    "n_layers": 8,
    "dropout": 0.1,
}


# ----------------------------------------------------------------------
# Project root resolution
# ----------------------------------------------------------------------

# Priority:
#   1. AI_PROJECT_ROOT environment variable
#   2. Repository root (directory containing this config.py)
_REPO_ROOT = Path(__file__).resolve().parent

PROJECT_ROOT: Path = Path(
    os.environ.get("AI_PROJECT_ROOT", str(_REPO_ROOT))
).expanduser().resolve()


# ----------------------------------------------------------------------
# Data / checkpoints / logs
# ----------------------------------------------------------------------

DATA_DIR: Path = Path(
    os.environ.get("AI_PROJECT_DATA_DIR", str(PROJECT_ROOT / "data"))
).expanduser().resolve()

CHECKPOINTS_DIR: Path = Path(
    os.environ.get("AI_PROJECT_CHECKPOINTS_DIR", str(PROJECT_ROOT / "checkpoints"))
).expanduser().resolve()

LOGS_DIR: Path = Path(
    os.environ.get("AI_PROJECT_LOGS_DIR", str(PROJECT_ROOT / "logs"))
).expanduser().resolve()

RUNTIME_UPLOAD_DIR: Path = Path(
    os.environ.get("RUNTIME_UPLOAD_DIR", str(DATA_DIR / "runtime_uploads"))
).expanduser().resolve()


# ----------------------------------------------------------------------
# Model / tokenizer artifacts
# ----------------------------------------------------------------------

TOKENIZER_FILE: Path = Path(
    os.environ.get("TOKENIZER_FILE", str(DATA_DIR / "tokenizer_v2.json"))
).expanduser().resolve()

MODEL_FILE: Path = Path(
    os.environ.get(
        "MODEL_FILE",
        str(CHECKPOINTS_DIR / "v2" / "reasoning_model_v1.pt"),
    )
).expanduser().resolve()


# ----------------------------------------------------------------------
# Knowledge corpus
# ----------------------------------------------------------------------

_DEFAULT_KNOWLEDGE_FILES = [
    DATA_DIR / "wikitext_v2.txt",
    DATA_DIR / "knowledge_extra_v1.txt",
]


def _split_knowledge_override(raw: str) -> list[str]:
    """Accept comma-separated values and the platform path separator."""
    if not raw:
        return []
    if os.pathsep == ";":
        parts = re.split(r"[;,]", raw)
    else:
        # On POSIX, ':' may appear in unusual path-like values; comma is the
        # documented portable delimiter while os.pathsep remains supported.
        parts = raw.split(",") if "," in raw else raw.split(os.pathsep)
    return [part.strip() for part in parts if part.strip()]


def _resolve_knowledge_files() -> list[Path]:
    override = os.environ.get("KNOWLEDGE_FILES")
    if override:
        return [Path(p).expanduser().resolve() for p in _split_knowledge_override(override)]

    resolved: list[Path] = []
    for index, default_path in enumerate(_DEFAULT_KNOWLEDGE_FILES, start=1):
        raw = os.environ.get(f"KNOWLEDGE_FILE_{index}")
        resolved.append(
            Path(raw).expanduser().resolve()
            if raw
            else default_path.expanduser().resolve()
        )
    return resolved


KNOWLEDGE_FILES: list[Path] = _resolve_knowledge_files()


# ----------------------------------------------------------------------
# Generation / retrieval settings
# ----------------------------------------------------------------------

MAX_INPUT_TOKENS: int = int(os.environ.get("MAX_INPUT_TOKENS", "480"))
MAX_NEW_TOKENS: int = int(os.environ.get("MAX_NEW_TOKENS", "50"))
CONFIDENCE_THRESHOLD: float = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.80"))


# ----------------------------------------------------------------------
# Runtime upload policy
# ----------------------------------------------------------------------

class UploadPolicy:
    """Authoritative limits shared by upload validation and UI copy."""

    def __init__(
        self,
        allowed_extensions: frozenset[str],
        per_file_bytes: dict[str, int],
        max_batch_bytes: int,
        max_extracted_text_chars: int,
        max_chunks_per_document: int,
        max_total_chunks_per_batch: int,
    ) -> None:
        self.allowed_extensions = allowed_extensions
        self.per_file_bytes = per_file_bytes
        self.max_batch_bytes = max_batch_bytes
        self.max_extracted_text_chars = max_extracted_text_chars
        self.max_chunks_per_document = max_chunks_per_document
        self.max_total_chunks_per_batch = max_total_chunks_per_batch


UPLOAD_POLICY = UploadPolicy(
    allowed_extensions=frozenset({".txt", ".pdf", ".docx"}),
    per_file_bytes={
        ".txt": 1 * 1024 * 1024,
        ".pdf": 10 * 1024 * 1024,
        ".docx": 10 * 1024 * 1024,
    },
    max_batch_bytes=50 * 1024 * 1024,
    max_extracted_text_chars=5_000_000,
    max_chunks_per_document=5000,
    max_total_chunks_per_batch=5000,
)


def knowledge_files_str() -> str:
    return ", ".join(str(p) for p in KNOWLEDGE_FILES)


if __name__ == "__main__":
    print("PROJECT_ROOT      :", PROJECT_ROOT)
    print("DATA_DIR          :", DATA_DIR)
    print("CHECKPOINTS_DIR   :", CHECKPOINTS_DIR)
    print("LOGS_DIR          :", LOGS_DIR)
    print("TOKENIZER_FILE    :", TOKENIZER_FILE)
    print("MODEL_FILE        :", MODEL_FILE)
    print("KNOWLEDGE_FILES   :", KNOWLEDGE_FILES)
    print("MAX_INPUT_TOKENS  :", MAX_INPUT_TOKENS)
    print("MAX_NEW_TOKENS    :", MAX_NEW_TOKENS)
    print("CONFIDENCE_THRESH :", CONFIDENCE_THRESHOLD)
