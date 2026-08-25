#!/usr/bin/env python3
"""Run an explicitly preliminary Stage 5 retrieval comparison.

This command never represents expert-reviewed evidence. It is useful for
diagnosing the corpus before independent reviewers inspect the cases.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.retriever_v2 import build_index, retrieve


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def rank_for(results: list, expected: str) -> int | None:
    for rank, result in enumerate(results, 1):
        if expected.casefold() in str(result.get("chunk", result)).casefold():
            return rank
    return None


def bootstrap(values: list[float], seed: int = 5_202_025, samples: int = 1000) -> list[float]:
    rng = random.Random(seed)
    return [
        statistics.fmean(rng.choices(values, k=len(values)))
        for _ in range(samples)
    ]


def metrics(rows: list[dict]) -> dict:
    supported = [row for row in rows if row["supported"]]
    unsupported = [row for row in rows if not row["supported"]]
    ranks = [row["rank"] for row in supported]
    return {
        "recall_at_1": sum(rank == 1 for rank in ranks) / len(ranks),
        "recall_at_3": sum(rank is not None and rank <= 3 for rank in ranks) / len(ranks),
        "recall_at_5": sum(rank is not None and rank <= 5 for rank in ranks) / len(ranks),
        "mrr": statistics.fmean(1 / rank if rank else 0 for rank in ranks),
        "unsupported_rejection": sum(row["rank"] is None for row in unsupported) / len(unsupported),
        "false_support_rate": sum(row["rank"] is not None for row in unsupported) / len(unsupported),
        "evidence_correctness": sum(row["rank"] is not None for row in supported) / len(supported),
        "latency_p50_ms": statistics.median(row["latency_ms"] for row in rows),
        "latency_p95_ms": sorted(row["latency_ms"] for row in rows)[max(0, int(len(rows) * .95) - 1)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results" / "stage5_preliminary_results.json")
    args = parser.parse_args()
    manifest = [
        json.loads(line) for line in (ROOT / "evaluation" / "stage5_source_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    cases = [
        json.loads(line) for line in (ROOT / "evaluation" / "stage5_review_queue.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    documents = []
    doc_ids = []
    for item in manifest:
        number = item["revision_version"].split()[-1]
        path = ROOT / "evaluation" / "stage5_documents" / f"rfc{number}.txt"
        documents.append(path.read_text(encoding="utf-8-sig"))
        doc_ids.append(item["doc_id"])
    index, df = build_index(documents)
    systems: dict[str, dict] = {}
    for system in ("lexical", "ralg"):
        rows = []
        for case in cases:
            start = time.perf_counter()
            if system == "lexical":
                query_terms = words(case["question"])
                ranked = sorted(
                    range(len(documents)),
                    key=lambda i: len(query_terms & words(documents[i])),
                    reverse=True,
                )[:5]
                results = [{"chunk": documents[i]} for i in ranked]
            else:
                results = retrieve(case["question"], documents, index, df, final_top_k=5)
            latency = (time.perf_counter() - start) * 1000
            expected = case["evidence_document_ids"][0] if case["evidence_document_ids"] else None
            expected_text = documents[doc_ids.index(expected)] if expected else ""
            rank = rank_for(results, expected_text[:120]) if expected else None
            rows.append({
                "case_id": case["case_id"],
                "category": case["category"],
                "supported": case["category"] == "supported",
                "rank": rank,
                "latency_ms": latency,
            })
        systems[system] = {"metrics": metrics(rows), "rows": rows}
    diff = [
        systems["ralg"]["rows"][i]["rank"] == systems["lexical"]["rows"][i]["rank"]
        for i in range(len(cases))
    ]
    report = {
        "status": "preliminary_unreviewed",
        "warning": "Automatically generated and unreviewed cases; not a final Stage 5 claim.",
        "documents": len(documents),
        "cases": len(cases),
        "systems": systems,
        "bootstrap": {
            "seed": 5_202_025,
            "samples": 1000,
            "recall_at_1_difference_ci": [
                min(bootstrap([
                    int(systems["ralg"]["rows"][i]["rank"] == 1)
                    - int(systems["lexical"]["rows"][i]["rank"] == 1)
                    for i in range(len(cases))
                ])),
                max(bootstrap([
                    int(systems["ralg"]["rows"][i]["rank"] == 1)
                    - int(systems["lexical"]["rows"][i]["rank"] == 1)
                    for i in range(len(cases))
                ])),
            ],
        },
        "ties": sum(diff),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: value["metrics"] for name, value in systems.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
