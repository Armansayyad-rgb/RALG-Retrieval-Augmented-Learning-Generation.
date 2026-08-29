#!/usr/bin/env python3
"""Verify frozen hashes from committed content."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

files = {
    "benchmark": ROOT / "evaluation" / "holdout_v3" / "holdout_v3_benchmark.jsonl",
    "sources_manifest": ROOT / "evaluation" / "holdout_v3" / "sources_manifest.jsonl",
    "evaluator": ROOT / "src" / "holdout_v3_eval.py",
}

print("=== SHA-256 from committed content ===")
actual = {}
for name, path in files.items():
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    actual[name] = h
    print(f"  {name}: {h}")

with open(ROOT / "evaluation" / "holdout_v3" / "holdout_v3_manifest.json") as f:
    m = json.load(f)

checks = [
    ("benchmark_sha256", actual["benchmark"]),
    ("sources_manifest_sha256", actual["sources_manifest"]),
    ("evaluator_sha256", actual["evaluator"]),
]

print("\n=== Hash verification ===")
all_ok = True
for key, expected in checks:
    recorded = m.get(key, "MISSING")
    ok = recorded == expected
    status = "PASS" if ok else "FAIL"
    print(f"  {key}: {status}")
    if not ok:
        print(f"    recorded: {recorded}")
        print(f"    actual:   {expected}")
        all_ok = False

print(f"\n  status: {m.get('status', 'MISSING')}")
print(f"  evaluator_executed_before_freeze: {m.get('evaluator_executed_before_freeze', 'MISSING')}")

result_path = ROOT / "evaluation" / "results" / "holdout_v3_blind_once.json"
print(f"  V3 result file exists: {result_path.exists()}")

if all_ok:
    print("\nALL HASH CHECKS PASS")
else:
    print("\nSOME HASH CHECKS FAILED")
