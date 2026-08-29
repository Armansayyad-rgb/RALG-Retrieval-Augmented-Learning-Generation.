"""Single source of truth for the supported Python runtime check.

This release is validated on exactly Python 3.11. Any other interpreter
(including 3.10 and 3.12) fails fast here with a clear message instead of
producing an opaque import, syntax, or ABI error later during startup.

Both official entry points (``src/api_server.py`` and
``src/webui_bootstrap.py``) call :func:`enforce_python_311` at import time.
"""

from __future__ import annotations

import sys

SUPPORTED = (3, 11)
MESSAGE = (
    "RALG requires Python 3.11 for this release. The validated runtime is "
    "exactly Python 3.11; Python 3.10 and 3.12 are not supported. "
    "Create a Python 3.11 virtual environment and re-run."
)


def enforce_python_311() -> None:
    """Raise ``RuntimeError`` if the running interpreter is not Python 3.11."""
    if (sys.version_info.major, sys.version_info.minor) != SUPPORTED:
        raise RuntimeError(MESSAGE)
