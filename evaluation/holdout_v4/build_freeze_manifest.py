from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys

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


def get_target_commit_sha() -> str:
    env_sha = os.environ.get("FREEZE_TARGET_COMMIT_SHA", "").strip()
    if not env_sha:
        sys.stderr.write(
            "FREEZE_TARGET_COMMIT_SHA is required for deterministic V4 freeze manifest generation\n"
        )
        raise SystemExit(1)
    canonical = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{env_sha}^{{commit}}"],
        cwd=ROOT,
        text=True,
    ).strip()
    if not canonical:
        sys.stderr.write(
            f"FREEZE_TARGET_COMMIT_SHA does not resolve to a Git commit: {env_sha}\n"
        )
        raise SystemExit(1)
    return canonical


def canonical_blob_sha(path: pathlib.Path, target_sha: str) -> str:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    try:
        content = subprocess.check_output(
            ["git", "show", f"{target_sha}:{rel}"],
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        sys.stderr.write(
            f"artifact not found in target commit {target_sha}: {rel}\n"
        )
        raise SystemExit(1)
    return hashlib.sha256(content).hexdigest()


def main() -> None:
    target_sha = get_target_commit_sha()
    print(f"Using target_code_commit_sha: {target_sha}")

    artifacts = {
        str(p.relative_to(ROOT)).replace("\\", "/"): canonical_blob_sha(p, target_sha)
        for p in ARTIFACTS
    }

    manifest = {
        "benchmark_version": "holdout_v4.0.0",
        "status": "single_shot_blind_evaluation_no_tuning_afterwards",
        "target_code_commit_sha": target_sha,
        "total_cases": 160,
        "denominators": {
            "primary_answer_supported": 100,
            "conflicting_evidence": 10,
            "conditional_or_qualified": 5,
            "rejection": 45,
            "retrieval_supported": 115,
        },
        "artifacts": artifacts,
        "official_result_path": "evaluation/results/holdout_v4_blind_once.json",
        "official_run_completed": False,
    }
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
