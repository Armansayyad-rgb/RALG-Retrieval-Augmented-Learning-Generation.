from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
V4 = ROOT / "evaluation" / "holdout_v4"
OUT = V4 / "holdout_v4_manifest.json"
ARTIFACTS = [
    V4 / "holdout_v4_benchmark.jsonl",
    V4 / "sources_manifest.jsonl",
    V4 / "contamination_report.json",
    V4 / "pre_run_review.jsonl",
    ROOT / "src" / "holdout_v4_eval.py",
    V4 / "pre_freeze_validate.py",
    V4 / "check_contamination.py",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main():
    missing = [p for p in ARTIFACTS if not p.exists()]
    if missing:
        raise SystemExit("missing freeze artifacts: " + ", ".join(str(p.relative_to(ROOT)) for p in missing))
    manifest = {
        "benchmark_version": "holdout_v4.0.0",
        "status": "single_shot_blind_evaluation_no_tuning_afterwards",
        "target_code_commit_sha": git_head(),
        "total_cases": 160,
        "denominators": {
            "primary_answer_supported": 100,
            "conflicting_evidence": 10,
            "conditional_or_qualified": 5,
            "rejection": 45,
            "retrieval_supported": 115,
        },
        "artifacts": {str(p.relative_to(ROOT)).replace('\\','/'): sha(p) for p in ARTIFACTS},
        "official_result_path": "evaluation/results/holdout_v4_blind_once.json",
        "official_run_completed": False,
    }
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
