"""Compatibility bootstrap for the AI-Project Gradio web UI.

Gradio 4.44.1 / gradio_client 1.3.0 can receive boolean JSON-schema nodes
(such as ``additionalProperties: false``) while generating API metadata.
The client parser assumes a mapping and crashes before the root page can
respond, after which ``Blocks.launch()`` misleadingly reports that localhost
is inaccessible.

Patch the parser in-memory before importing the project Web UI. Keeping this
at runtime is deterministic and avoids modifying site-packages during the
Docker build.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import runtime_guard
runtime_guard.enforce_python_311()


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gradio_client import utils as client_utils


_original_get_type = client_utils.get_type


def _safe_get_type(schema):
    if isinstance(schema, bool):
        return "boolean"
    return _original_get_type(schema)


client_utils.get_type = _safe_get_type

# Import only after the compatibility patch is installed.
from webui.app import main  # noqa: E402


if __name__ == "__main__":
    main()
