"""Compatibility facade for scripts executed with ``src`` first on sys.path."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "config.py"
_SPEC = importlib.util.spec_from_file_location("_ralg_project_config", _ROOT)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Could not load project config at {_ROOT}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

for _name in dir(_MODULE):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_MODULE, _name)