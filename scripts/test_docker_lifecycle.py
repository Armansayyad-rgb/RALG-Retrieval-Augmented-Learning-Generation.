"""Docker lifecycle qualification tests for RALG Engine."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBUI_PORT = 7860
BASE_URL = f"http://127.0.0.1:{WEBUI_PORT}"
HEALTH_TIMEOUT = 90
RESULTS: list[dict] = []


def _run(cmd: list[str], check: bool = True, capture: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, check=check, cwd=str(PROJECT_ROOT), **kw)


def _cname() -> str:
    r = _run(["docker", "ps", "--filter", "ancestor=ralg-engine:latest", "--format", "{{.Names}}"], check=False)
    lines = r.stdout.strip().splitlines()
    return lines[0] if lines else "ralg-engine"


def _record(name: str, passed: bool, detail: str = "") -> None:
    s = "PASS" if passed else "FAIL"
    RESULTS.append({"name": name, "status": s, "detail": detail})
    icon = "\u2713" if passed else "\u2717"
    print(f"  [{s}] {icon} {name}" + (f" -- {detail}" if detail else ""))


def main() -> int:
    build_flag = "--build" in sys.argv
    CN = _cname()
    print(f"Container: {CN}")
    print("=" * 60)
    print("RALG Engine -- Docker Lifecycle Qualification")
    print("=" * 60)

    if build_flag:
        print("\n[BUILD] docker compose build --no-cache ...")
        r = _run(["docker", "compose", "build", "--no-cache"], check=False)
        _record("compose_build", r.returncode == 0, r.stderr.strip()[:200] if r.returncode else "ok")

    # --- Phase 1: Compose + Image ---
    print("\n[Phase 1] Compose + Image")
    r = _run(["docker", "compose", "config", "--quiet"], check=False)
    _record("compose_config_valid", r.returncode == 0, r.stderr.strip()[:100] if r.returncode else "valid")

    r = _run(["docker", "image", "inspect", "ralg-engine:latest"], check=False)
    _record("image_exists", r.returncode == 0)
    if r.returncode == 0:
        info = json.loads(r.stdout)
        digest = info[0].get("Id", "?")[:19]
        size_mb = info[0].get("Size", 0) / (1024**2)
        _record("image_digest", True, digest)
        _record("image_size_mb", True, f"{size_mb:.1f}")

    # --- Phase 2: Container State ---
    print("\n[Phase 2] Container State")
    r = _run(["docker", "ps", "--filter", f"id={CN}", "--format", "{{.Status}}"], check=False)
    status = r.stdout.strip() if r.returncode == 0 else ""
    # fallback: filter by ancestor
    if not status:
        r = _run(["docker", "ps", "--filter", "ancestor=ralg-engine:latest", "--format", "{{.Names}}|{{.Status}}"], check=False)
        for line in r.stdout.strip().splitlines():
            if CN in line:
                status = line.split("|", 1)[1]
                break
    _record("container_running", "Up" in status, status)
    _record("container_healthy", "healthy" in status.lower(), status)

    # Volumes
    r = _run(["docker", "inspect", CN, "--format", "{{range .Mounts}}{{.Type}}:{{.Source}}->{{.Destination}} {{end}}"], check=False)
    mounts = r.stdout.strip()
    _record("volumes_mounted", bool(mounts), mounts[:120] if mounts else "no mounts")

    # --- Phase 3: Application ---
    print("\n[Phase 3] Application Health")
    try:
        import urllib.request
        req = urllib.request.urlopen(f"{BASE_URL}/", timeout=10)
        _record("webui_root_200", req.getcode() == 200, f"HTTP {req.getcode()}")
        html = req.read().decode("utf-8", errors="replace")
        _record("webui_gradio_loaded", "gradio" in html.lower() or "gr-" in html.lower())
    except Exception as e:
        _record("webui_root_200", False, str(e)[:120])

    # --- Phase 4: Exec checks ---
    print("\n[Phase 4] Container Internals")
    execs = [
        ("python_version", "import sys; print(sys.version)"),
        ("torch_ok", "import torch; print(torch.__version__)"),
        ("rag_import", "import sys; sys.path.insert(0,'/app/src'); import rag_chat_v2; print('ok')"),
        ("retriever_ok", "import sys; sys.path.insert(0,'/app/src'); import retriever_hybrid; print('ok')"),
        ("config_ok", "import sys; sys.path.insert(0,'/app/src'); import config; print('ok')"),
    ]
    for name, code in execs:
        r = _run(["docker", "exec", CN, "python", "-c", code], check=False)
        _record(f"exec_{name}", r.returncode == 0, (r.stdout.strip() if r.returncode == 0 else r.stderr.strip()[:100]))

    # --- Phase 5: Resources ---
    print("\n[Phase 5] Resources")
    r = _run(["docker", "stats", CN, "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}"], check=False)
    if r.returncode == 0:
        parts = r.stdout.strip().split("|")
        if len(parts) == 3:
            _record("cpu", True, parts[0])
            _record("memory", True, parts[1])
            _record("mem_pct", True, parts[2])

    # --- Phase 6: Restart Recovery ---
    print("\n[Phase 6] Restart Recovery")
    _run(["docker", "compose", "restart"], check=False)
    start = time.time()
    recovered = False
    while time.time() - start < HEALTH_TIMEOUT:
        time.sleep(3)
        r = _run(["docker", "inspect", CN, "--format", "{{.State.Health.Status}}"], check=False)
        if "healthy" in r.stdout.lower():
            recovered = True
            break
    elapsed = time.time() - start
    _record("restart_recovery_healthy", recovered, f"{elapsed:.0f}s")

    # --- Phase 7: Final ---
    print("\n[Phase 7] Final")
    r = _run(["docker", "ps", "--filter", "ancestor=ralg-engine:latest", "--format", "{{.Status}}"], check=False)
    _record("final_running", "Up" in r.stdout and "healthy" in r.stdout.lower(), r.stdout.strip())

    # Summary
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    total = len(RESULTS)
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
    if failed:
        print("Failed:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  - {r['name']}: {r['detail']}")

    out = PROJECT_ROOT / "logs" / "docker_lifecycle_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"total": total, "passed": passed, "failed": failed, "tests": RESULTS}, f, indent=2)
    print(f"\nResults: {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
