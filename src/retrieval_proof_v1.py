"""Baseline-vs-RALG retrieval proof runner.

This script is intentionally lightweight: it evaluates retrieval quality
without requiring the trained generation checkpoint. That makes it useful
for quick technical proof work and CI-style regression checks.

Run from the project root:

    python src/retrieval_proof_v1.py --dataset data/technical_doc_benchmark_v1.jsonl

The dataset is JSONL. Each row should contain:

    {
      "id": "case_001",
      "question": "...",
      "expected_terms": ["term one", "term two"],
      "supported": true,
      "category": "maintenance"
    }

For supported questions, a retrieval hit is counted when a retrieved chunk
contains any expected term. For unsupported questions, a correct result is
no expected-term hit in the top-k retrieval window.

This is not a final product benchmark. It is a repeatable first gate for
retrieval quality, recall, latency, and failure analysis.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(1, str(SRC_DIR))
from config import KNOWLEDGE_FILES  # noqa: E402

from retriever_v2 import build_index, load_chunks, retrieve as retrieve_v2  # noqa: E402
from retriever_v4 import retrieve as retrieve_v4  # noqa: E402


@dataclass
class Case:
    id: str
    question: str
    expected_terms: list[str]
    supported: bool
    category: str = "general"
    contradiction_terms: list[str] | None = None
    required_terms: list[str] | None = None
    match_mode: str = "any_term"


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _contains_expected(text: str, expected_terms: Iterable[str]) -> bool:
    haystack = _normalise(text)
    return any(_normalise(term) in haystack for term in expected_terms if term)


def _contains_contradiction(text: str, contradiction_terms: Iterable[str] | None) -> bool:
    if not contradiction_terms:
        return False
    haystack = _normalise(text)
    return any(_normalise(term) in haystack for term in contradiction_terms if term)


def _case_supported_by_texts(case: Case, texts: list[str]) -> tuple[bool, int | None]:
    """Return whether retrieved texts satisfy the case and the first hit rank.

    Modes:
    - any_term: any expected term in any retrieved chunk
    - all_terms_anywhere: every required term appears somewhere across top-k evidence
    """
    if case.match_mode == "all_terms_anywhere":
        required = case.required_terms or case.expected_terms
        combined = _normalise(" ".join(texts))
        ok = all(_normalise(term) in combined for term in required if term)
        first_rank = None
        if ok:
            for rank, text in enumerate(texts, start=1):
                if any(_normalise(term) in _normalise(text) for term in required if term):
                    first_rank = rank
                    break
        return ok, first_rank

    ranks = [
        rank
        for rank, text in enumerate(texts, start=1)
        if _contains_expected(text, case.expected_terms)
    ]
    return bool(ranks), (ranks[0] if ranks else None)


def load_cases(path: Path) -> list[Case]:
    cases: list[Case] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            cases.append(
                Case(
                    id=str(raw.get("id") or f"case_{line_no:03d}"),
                    question=str(raw["question"]),
                    expected_terms=list(raw.get("expected_terms") or []),
                    supported=bool(raw.get("supported", True)),
                    category=str(raw.get("category") or "general"),
                    contradiction_terms=list(raw.get("contradiction_terms") or []),
                    required_terms=list(raw.get("required_terms") or []),
                    match_mode=str(raw.get("match_mode") or "any_term"),
                )
            )
    return cases


def _v2_texts(result: list[dict]) -> list[str]:
    texts = []
    for item in result:
        chunk = item.get("chunk") or item.get("text") or item.get("context") or ""
        texts.append(str(chunk))
    return texts


def _v4_texts(result: dict) -> list[str]:
    texts = []
    for item in result.get("results", []):
        chunk = item.get("chunk") or item.get("text") or item.get("context") or ""
        texts.append(str(chunk))
    return texts


def evaluate_system(name: str, cases: list[Case], chunks, index, document_frequency, top_k: int) -> dict:
    rows = []
    latencies = []
    supported_total = 0
    supported_hits_at_1 = 0
    supported_hits_at_3 = 0
    supported_hits_at_5 = 0
    unsupported_total = 0
    unsupported_correct = 0

    for case in cases:
        started = time.perf_counter()

        if name == "baseline_v2":
            raw = retrieve_v2(
                case.question,
                chunks,
                index,
                document_frequency,
                final_top_k=top_k,
            )
            texts = _v2_texts(raw)
        elif name == "ralg_v4":
            raw = retrieve_v4(
                case.question,
                chunks,
                index,
                document_frequency,
                collect_timings=True,
            )
            texts = _v4_texts(raw)[:top_k]
        else:
            raise ValueError(f"Unknown system: {name}")

        latency = time.perf_counter() - started
        latencies.append(latency)

        supported_by_evidence, first_rank = _case_supported_by_texts(case, texts)

        contradiction_ranks = [
            rank
            for rank, text in enumerate(texts, start=1)
            if _contains_contradiction(text, case.contradiction_terms)
        ]

        first_contradiction_rank = (
            contradiction_ranks[0]
            if contradiction_ranks
            else None
        )

        hit_at_1 = supported_by_evidence and first_rank is not None and first_rank <= 1
        hit_at_3 = supported_by_evidence and first_rank is not None and first_rank <= 3
        hit_at_5 = supported_by_evidence
        contradiction_at_5 = (
            first_contradiction_rank is not None
            and first_contradiction_rank <= 5
        )

        if case.supported:
            supported_total += 1
            supported_hits_at_1 += int(hit_at_1)
            supported_hits_at_3 += int(hit_at_3)
            supported_hits_at_5 += int(hit_at_5)
            correct = hit_at_5
        else:
            unsupported_total += 1
            # Unsupported questions are correct if retrieval finds no support.
            # False-premise questions are also correct when the top evidence
            # explicitly contradicts the premise, e.g. "do not allow X".
            correct = not supported_by_evidence or contradiction_at_5
            unsupported_correct += int(correct)

        rows.append(
            {
                "id": case.id,
                "category": case.category,
                "question": case.question,
                "supported": case.supported,
                "first_rank": first_rank,
                "first_contradiction_rank": first_contradiction_rank,
                "correct": bool(correct),
                "latency_ms": round(latency * 1000, 2),
                "top_preview": texts[0][:220].replace("\n", " ") if texts else "",
            }
        )

    def ratio(num: int, den: int) -> float:
        return round(num / den, 4) if den else 0.0

    mrr_values = [
        1.0 / row["first_rank"]
        for row in rows
        if row["supported"] and row["first_rank"]
    ]

    summary = {
        "system": name,
        "cases": len(cases),
        "supported_cases": supported_total,
        "unsupported_cases": unsupported_total,
        "recall_at_1": ratio(supported_hits_at_1, supported_total),
        "recall_at_3": ratio(supported_hits_at_3, supported_total),
        "recall_at_5": ratio(supported_hits_at_5, supported_total),
        "mrr": round(statistics.mean(mrr_values), 4) if mrr_values else 0.0,
        "unsupported_rejection_at_5": ratio(unsupported_correct, unsupported_total),
        "accuracy_at_5": ratio(sum(int(row["correct"]) for row in rows), len(rows)),
        "avg_latency_ms": round(statistics.mean(latencies) * 1000, 2) if latencies else 0.0,
        "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18] * 1000, 2)
        if len(latencies) >= 20
        else round(max(latencies, default=0.0) * 1000, 2),
    }

    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run baseline-vs-RALG retrieval proof benchmark.")
    parser.add_argument("--dataset", type=Path, default=PROJECT_ROOT / "data" / "technical_doc_benchmark_v1.jsonl")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "logs" / "retrieval_proof_v1_results.json")
    parser.add_argument("--knowledge-file", action="append", default=None)
    args = parser.parse_args()

    if not args.dataset.exists():
        raise SystemExit(f"Dataset not found: {args.dataset}")

    knowledge_files = [Path(p) for p in args.knowledge_file] if args.knowledge_file else KNOWLEDGE_FILES
    cases = load_cases(args.dataset)

    chunks = load_chunks(knowledge_files)
    index, document_frequency = build_index(chunks)

    results = {
        "dataset": str(args.dataset),
        "knowledge_files": [str(path) for path in knowledge_files],
        "top_k": args.top_k,
        "systems": [
            evaluate_system("baseline_v2", cases, chunks, index, document_frequency, args.top_k),
            evaluate_system("ralg_v4", cases, chunks, index, document_frequency, args.top_k),
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(json.dumps({"output": str(args.output), "summaries": [s["summary"] for s in results["systems"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
