#!/usr/bin/env python3
"""Preflight checks and port selection for the RALG buyer demo.

Verifies the local environment can run the existing WebUI/API demo path
without downloading anything, mutating runtime data, or requiring network
services beyond localhost. Also selects the actual WebUI port so the
launcher and the checks agree on one bounded, verified choice.

Checks:
- Python version (3.10+)
- Required source modules and demo assets exist
- Checkpoint/tokenizer assets documented (external, not in Git; see README)
- Bounded port selection: 7860 first, then 7861-7870; never arbitrary ports
- Docker availability is reported optionally (--docker), never required
- Runtime directories and configuration validity

Note on checkpoints: ``checkpoints/v2/reasoning_model_v1.pt`` is external to
Git and governed by the RALG Source-Available Non-Commercial License v1.0.
It is not auto-downloaded. Place the checkpoint bundle under
``checkpoints/v2/`` before running the demo if model-backed answers are
required. The core pipeline can run extractive/lookup answers without it.

Note on tokenizer: ``data/tokenizer_v2.json`` is tracked in Git and always
required. ``data/tokenizer.json`` is the legacy fallback.
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "config.py",
    "src/webui/app.py",
    "src/api_server.py",
    "data/tokenizer_v2.json",
    "docs/BUYER_DEMO_GUIDE.md",
]

RECOMMENDED_FILES = [
    "data/tokenizer.json",
    "checkpoints/v2/reasoning_model_v1.pt",
]

PREFERRED_PORT = 7860
PORT_RANGE_START = 7860
PORT_RANGE_END = 7870  # allowed fallback window: 7861-7870


def check_python() -> dict:
    version = sys.version_info
    ok = version >= (3, 10)
    return {
        "name": "python_version",
        "pass": ok,
        "detail": f"{version.major}.{version.minor}.{version.micro}",
        "action": ("Install Python 3.10 or newer and re-run."
                   if not ok
                   else None),
    }


def check_files(root: Path = ROOT) -> list[dict]:
    results = []
    for rel in REQUIRED_FILES:
        path = root / rel
        results.append({
            "name": f"file_exists:{rel}",
            "pass": path.is_file(),
            "detail": str(path),
            "action": None if path.is_file()
            else f"Missing required file. Verify the repository checkout provides {rel}.",
        })
    for rel in RECOMMENDED_FILES:
        path = root / rel
        results.append({
            "name": f"file_present:{rel}",
            "pass": path.is_file(),
            "detail": str(path),
            "action": None if path.is_file()
            else f"Recommended file not found: {rel}. "
                  "Not required for extractive operation; see README for "
                  "checkpoint licensing details.",
        })
    return results


def check_docker() -> dict:
    docker = shutil.which("docker")
    if docker is None:
        return {"name": "docker_available", "pass": True, "detail": "not installed (optional)",
                "action": None}
    try:
        proc = subprocess.run([docker, "info", "--format", "{{.ServerVersion}}"],
                              capture_output=True, text=True, timeout=30)
        running = proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        running = False
    return {
        "name": "docker_available",
        "pass": True,  # optional check; never fails preflight
        "detail": "daemon reachable" if running else "installed but daemon not reachable",
        "action": None,
    }


def port_available(port: int, host: str = "127.0.0.1") -> bool:
    """True iff we can bind a listener socket on the port right now.

    Uses an exclusive bind on Windows so a port already held by another
    process (e.g. com.docker.backend) is correctly reported as unavailable;
    SO_REUSEADDR would allow a silent double-bind there.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def select_port(preferred: int = PREFERRED_PORT, range_start: int = PORT_RANGE_START,
                range_end: int = PORT_RANGE_END) -> int | None:
    """First available port in the bounded allowed window, else None."""
    for port in range(preferred, range_end + 1):
        if port_available(port):
            return port
    return None


def check_webui_port() -> dict:
    selected = select_port()
    return {
        "name": "webui_port_available",
        "pass": selected is not None,
        "detail": (
            f"selected {selected} (tried {PORT_RANGE_START}-{PORT_RANGE_END})"
            if selected is not None
            else f"no available port in allowed range {PORT_RANGE_START}-{PORT_RANGE_END}"
        ),
        "selected_port": selected,
        "webui_url": f"http://127.0.0.1:{selected}" if selected is not None else None,
        "action": None if selected is not None
        else f"Free one of ports {PORT_RANGE_START}-{PORT_RANGE_END} on 127.0.0.1 "
             "(this tool never terminates other processes), then re-run.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", action="store_true", help="also report Docker availability")
    args = parser.parse_args()

    results = [check_python()] + check_files(ROOT) + [check_webui_port()]
    if args.docker:
        results.append(check_docker())
    failures = [result for result in results if not result["pass"]]
    port_result = next(result for result in results if result["name"] == "webui_port_available")
    report = {
        "preflight": "buyer_demo",
        "checks": results,
        "failures": len(failures),
        "selected_port": port_result.get("selected_port"),
        "webui_url": port_result.get("webui_url"),
        "pass": not failures,
    }
    print(json.dumps(report, indent=2))
    for result in failures:
        print(f"[FAIL] {result['name']}: {result['action']}", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
