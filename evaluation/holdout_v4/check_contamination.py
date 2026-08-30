from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import pathlib
import re
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
V4 = ROOT / "evaluation" / "holdout_v4" / "holdout_v4_benchmark.jsonl"
REPORT = ROOT / "evaluation" / "holdout_v4" / "contamination_report.json"
PRIOR_GLOBS = [
    "evaluation/holdout_v1/**/*.json*",
    "evaluation/holdout_v2/**/*.json*",
    "evaluation/holdout_v3/**/*.json*",
    "evaluation/stage5*.json*",
    "evaluation/authoritative_tech_dev_v1/**/*.json*",
    "data/*benchmark*.jsonl",
]


def norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", s.lower()))


def strings_from_json(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_from_json(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_from_json(v)


def load_jsonish(path: pathlib.Path):
    try:
        if path.suffix == ".jsonl":
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip():
                    yield json.loads(line)
        else:
            yield json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.90)
    args = ap.parse_args()
    if not V4.exists():
        raise SystemExit(f"missing {V4}")
    v4_rows = [json.loads(x) for x in V4.read_text(encoding="utf-8").splitlines() if x.strip()]
    prior = []
    seen = set()
    for pattern in PRIOR_GLOBS:
        for path in ROOT.glob(pattern):
            if path.resolve() == V4.resolve() or path in seen or not path.is_file():
                continue
            seen.add(path)
            for obj in load_jsonish(path):
                for s in strings_from_json(obj):
                    n = norm(s)
                    if len(n) >= 20:
                        prior.append((path.relative_to(ROOT).as_posix(), n))
    exact = []
    near = []
    for row in v4_rows:
        for field in ("question", "ground_truth_answer"):
            n = norm(str(row.get(field, "")))
            if len(n) < 20:
                continue
            for path, old in prior:
                if n == old:
                    exact.append({"case_id": row.get("case_id"), "field": field, "prior_path": path})
                elif len(n) >= 35 and len(old) >= 35:
                    r = difflib.SequenceMatcher(None, n, old, autojunk=True).ratio()
                    if r >= args.threshold:
                        near.append({"case_id": row.get("case_id"), "field": field, "prior_path": path, "ratio": round(r, 4)})
    report = {
        "schema_version": "holdout_v4_contamination_v1",
        "benchmark_sha256": hashlib.sha256(V4.read_bytes()).hexdigest(),
        "prior_files_scanned": len(seen),
        "exact_overlaps": exact,
        "near_overlaps": near,
        "status": "PASS" if not exact and not near else "FAIL",
    }
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
