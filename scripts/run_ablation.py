#!/usr/bin/env python3
"""Run safe retrieval ablations without changing production constants."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def main():
    out = ROOT/"logs"/"heldout_pilot_v1_ablation.json"
    cmd = [sys.executable, str(ROOT/"scripts"/"heldout_evaluation.py"), "--output", str(out)]
    subprocess.run(cmd, check=True)
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["ablation"] = {"production_rules_changed": False, "switches": ["lexical_baseline", "current_ralg"], "note": "No tuning or monkey-patching applied."}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["metrics"], indent=2))
if __name__ == "__main__": main()
