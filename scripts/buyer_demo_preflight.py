#!/usr/bin/env python3
"""Preflight checks for the RALG buyer demo.

Verifies the local environment can run the existing WebUI/API demo path
without downloading anything, mutating runtime data, or requiring network
services beyond localhost. Exits non-zero with actionable failures.

Checks:
- Python version (3.10+)
- Required checkpoint/tokenizer files exist
- Required source modules and demo assets exist
- Docker availability is reported optionally (--docker), never required
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "config.py",
    "src/webui/app.py",
    "src/api_server.py",
    "data/tokenizer_v2.json",
    "checkpoints/v2/reasoning_model_v1.pt",
    "checkpoints/embedding_model.pt",
    "docs/BUYER_DEMO_GUIDE.md",
]

REQUIRED_CHECKPOINT_DIRS = [
    "checkpoints/v2",
]


def check_python() -> dict:
    version = sys.version_info
    ok = version >= (3, 10)
    return {
        "name": "python_version",
        "pass": ok,
        "detail": f"{version.major}.{version.minor}.{version.micro}",
        "action": None if ok else "Install Python 3.10 or newer and re-run.",
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
    for rel in REQUIRED_CHECKPOINT_DIRS:
        path = root / rel
        results.append({
            "name": f"dir_exists:{rel}",
            "pass": path.is_dir(),
            "detail": str(path),
            "action": None if path.is_dir()
            else f"Missing checkpoint directory {rel}; the external model bundle must be placed there first.",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", action="store_true", help="also report Docker availability")
    args = parser.parse_args()

    results = [check_python()] + check_files(ROOT)
    if args.docker:
        results.append(check_docker())
    failures = [result for result in results if not result["pass"]]
    report = {
        "preflight": "buyer_demo",
        "checks": results,
        "failures": len(failures),
        "pass": not failures,
    }
    print(json.dumps(report, indent=2))
    for result in failures:
        print(f"[FAIL] {result['name']}: {result['action']}", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
