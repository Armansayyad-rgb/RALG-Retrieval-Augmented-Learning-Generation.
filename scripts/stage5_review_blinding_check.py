#!/usr/bin/env python3
"""Fail if blind reviewer materials contain model-performance information."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROHIBITED = (
    "ralg", "lexical", "bm25", "retrieval_score", "ranking", "latency",
    "false_support", "mrr", "recall_at", "model_won", "system_a", "system_b",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("evaluation/stage5_review_pack"))
    args = parser.parse_args()
    findings = []
    for path in args.path.rglob("*"):
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace").casefold()
            for term in PROHIBITED:
                if term in content:
                    findings.append({"file": str(path), "term": term})
    report = {"path": str(args.path), "prohibited_model_fields": findings, "pass": not findings}
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
