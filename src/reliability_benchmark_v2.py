#!/usr/bin/env python3
"""RALG End-to-End Reliability Benchmark (V2).

Small end-to-end reliability test for the CURRENT API behavior in
src/api_server.py. It queries the running /query endpoint over HTTP and
does NOT import or modify any production code.

Approximately 50 test cases across:
  1. supported factual questions
  2. paraphrased questions
  3. SOP / procedure questions
  4. unsupported questions
  5. false-premise questions
  6. misleading keyword-overlap questions
  7. questions about runtime-ingested documents
  8. existing-KB regression questions

Metrics computed:
  - supported-answer correctness
  - unsupported rejection rate
  - false-support rate
  - false-rejection rate
  - average latency
  - number of runtime/API errors

Every failed case is recorded with: test ID, question, expected result,
actual answer, supported flag, answer type, confidence, top source score,
and failure reason.

Outputs:
  logs/reliability_benchmark_results.json
  RELIABILITY_BENCHMARK.md

Usage (server must be running on 127.0.0.1:8000):
  python src/reliability_benchmark_v2.py
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://127.0.0.1:8000"
OUTPUT_JSON = PROJECT_ROOT / "logs" / "reliability_benchmark_results.json"
OUTPUT_MD = PROJECT_ROOT / "RELIABILITY_BENCHMARK.md"
TOP_K = 5

# Reliability targets used for the overall pass/fail determination.
TARGETS = {
    "supported_correctness_ge_90": 0.90,
    "rejection_rate_ge_95": 0.95,
    "false_support_rate_le_5": 0.05,
    "false_rejection_rate_le_5": 0.05,
    "api_errors_zero": 0,
}

COMPRESSOR_SOP = """STANDARD OPERATING PROCEDURE: COMPRESSOR MAINTENANCE

1. BEFORE STARTING
   - De-energize the compressor unit at the main disconnect.
   - Verify zero voltage with a calibrated tester on all three phases.
   - Apply lockout/tagout (LOTO) per site procedure.
   - Allow system pressure to bleed to zero; confirm gauges read 0 PSI.

2. INSPECTION
   - Check oil level in sight glass; top up if below minimum mark.
   - Inspect belts for cracks, glazing, or excessive wear; replace if needed.
   - Verify belt tension: 1/2 inch deflection at center span under thumb pressure.
   - Clean intake filter; replace if clogged or damaged.
   - Check all electrical connections for tightness and signs of overheating.

3. LUBRICATION
   - Use only OEM-approved synthetic compressor oil (ISO VG 46).
   - Drain old oil while warm; collect and dispose per environmental regulations.
   - Refill to correct level; do not overfill.

4. RESTART
   - Remove LOTO devices.
   - Re-energize at main disconnect.
   - Start compressor; verify unloaded start (no pressure load).
   - Monitor for unusual vibration, noise, or temperature rise for 10 minutes.
   - Log all readings in maintenance register."""


@dataclass
class TestCase:
    id: str
    category: str
    question: str
    expected_supported: bool
    expected_terms: list[str] = field(default_factory=list)


# ============================================================
# Test cases (~50)
# ============================================================

TEST_CASES: list[TestCase] = [
    # ---- 1. Supported factual questions (8) ----
    TestCase("fact_001", "supported_factual", "What is the structure of DNA?", True, ["double helix", "nucleotides"]),
    TestCase("fact_002", "supported_factual", "Who were the key figures of the French Revolution?", True, ["Robespierre", "Danton"]),
    TestCase("fact_003", "supported_factual", "How does photosynthesis work?", True, ["sunlight", "carbon dioxide", "water", "oxygen"]),
    TestCase("fact_004", "supported_factual", "What was the significance of the Magna Carta?", True, ["royal power", "law", "rights"]),
    TestCase("fact_005", "supported_factual", "What are the main features of the Roman Republic?", True, ["Senate", "government"]),
    TestCase("fact_006", "supported_factual", "Why did the Roman Empire decline?", True, ["overrun", "Germanic", "revolt"]),
    TestCase("fact_007", "supported_factual", "What were the effects of the fall of the Roman Empire?", True, ["Germanic kingdoms", "Eastern Roman Empire"]),
    TestCase("fact_008", "supported_factual", "How were Roman legions organized?", True, ["cohort", "century", "legion"]),
    # ---- 2. Paraphrased questions (5) ----
    TestCase("para_001", "paraphrased", "Explain the molecular structure of DNA.", True, ["double helix", "nucleotides"]),
    TestCase("para_002", "paraphrased", "What happens during photosynthesis in plants?", True, ["sunlight", "carbon dioxide", "oxygen"]),
    TestCase("para_003", "paraphrased", "Why was the Magna Carta historically important?", True, ["royal power", "law"]),
    TestCase("para_004", "paraphrased", "What defined the Roman Republic's political system?", True, ["Senate", "government"]),
    TestCase("para_005", "paraphrased", "Describe the organization of the Roman army.", True, ["cohort", "century"]),
    # ---- 3. SOP / procedure questions (6) ----
    TestCase("sop_001", "sop_procedure", "What must be done before starting compressor maintenance?", True, ["de-energize", "verify zero voltage", "lockout", "tagout", "bleed"]),
    TestCase("sop_002", "sop_procedure", "What are the restart steps after compressor maintenance?", True, ["remove LOTO", "re-energize", "unloaded start", "monitor"]),
    TestCase("sop_003", "sop_procedure", "How should belt tension be verified during inspection?", True, ["1/2 inch", "deflection", "thumb pressure"]),
    TestCase("sop_004", "sop_procedure", "What oil should be used for compressor lubrication?", True, ["OEM-approved", "ISO VG 46", "synthetic"]),
    TestCase("sop_005", "sop_procedure", "What must be checked during the inspection phase?", True, ["oil level", "belts", "intake filter", "electrical connections"]),
    TestCase("sop_006", "sop_procedure", "What should be done with the old oil when draining it?", True, ["warm", "dispose", "environmental"]),
    # ---- 4. Unsupported questions (8) ----
    TestCase("unsup_001", "unsupported", "What is the warranty phone number for the compressor manufacturer?", False),
    TestCase("unsup_002", "unsupported", "What is the supplier email for compressor parts?", False),
    TestCase("unsup_003", "unsupported", "What is the serial number of the compressor unit?", False),
    TestCase("unsup_004", "unsupported", "Which employee signed the maintenance register?", False),
    TestCase("unsup_005", "unsupported", "What is the weather forecast for the maintenance day?", False),
    TestCase("unsup_006", "unsupported", "Who invented the Roman Empire?", False),
    TestCase("unsup_007", "unsupported", "What is the phone number for the French Revolution museum?", False),
    TestCase("unsup_008", "unsupported", "What is the contact email for DNA research funding?", False),
    # ---- 5. False-premise questions (7) ----
    TestCase("false_001", "false_premise", "Why did the Roman Empire fall in 2020?", False),
    TestCase("false_002", "false_premise", "What caused the DNA double helix to be discovered in 1800?", False),
    TestCase("false_003", "false_premise", "How does photosynthesis work in animals?", False),
    TestCase("false_004", "false_premise", "Why was the Magna Carta signed by Napoleon?", False),
    TestCase("false_005", "false_premise", "What safety step requires bypassing lockout tagout before opening the electrical panel?", False),
    TestCase("false_006", "false_premise", "Explain why the Roman Republic had a President.", False),
    TestCase("false_007", "false_premise", "What caused the French Revolution to happen in ancient Egypt?", False),
    # ---- 6. Misleading keyword-overlap questions (7) ----
    TestCase("mislead_001", "misleading_keyword_overlap", "What is the compressor stages configuration of the Roman Empire?", False),
    TestCase("mislead_002", "misleading_keyword_overlap", "How does the DNA photosynthesis process work?", False),
    TestCase("mislead_003", "misleading_keyword_overlap", "What are the compressor lockout steps for DNA replication?", False),
    TestCase("mislead_004", "misleading_keyword_overlap", "Describe the Magna Carta compressor maintenance procedure.", False),
    TestCase("mislead_005", "misleading_keyword_overlap", "What are the French Revolution stages of a compressor?", False),
    TestCase("mislead_006", "misleading_keyword_overlap", "How do Roman legion lockout tagout procedures work?", False),
    TestCase("mislead_007", "misleading_keyword_overlap", "What is the lockout procedure for the 38th Engineer Battalion's electrical systems?", False),
    # ---- 7. Questions about runtime-ingested documents (5) ----
    TestCase("rt_001", "runtime_ingested", "What safety step is required before opening the compressor electrical panel?", True, ["de-energize", "main disconnect", "lockout", "tagout"]),
    TestCase("rt_002", "runtime_ingested", "What is the lockout/tagout procedure for compressor maintenance?", True, ["lockout", "tagout", "site procedure"]),
    TestCase("rt_003", "runtime_ingested", "What oil specification is required for compressor lubrication?", True, ["OEM-approved", "ISO VG 46"]),
    TestCase("rt_004", "runtime_ingested", "What is the warranty phone number for compressor support?", False),
    TestCase("rt_005", "runtime_ingested", "What is the serial number of this compressor unit?", False),
    # ---- 8. Existing-KB regression questions (4) ----
    TestCase("reg_001", "existing_kb_regression", "Why did the Roman Empire decline?", True, ["overrun", "Germanic", "revolt"]),
    TestCase("reg_002", "existing_kb_regression", "Explain how photosynthesis works.", True, ["sunlight", "carbon dioxide", "oxygen", "energy"]),
    TestCase("reg_003", "existing_kb_regression", "What is the structure of DNA?", True, ["double helix", "nucleotides"]),
    TestCase("reg_004", "existing_kb_regression", "What was the significance of the Magna Carta?", True, ["royal power", "law", "rights"]),
]

assert len(TEST_CASES) == 50, f"Expected 50 test cases, got {len(TEST_CASES)}"


# ============================================================
# API helpers
# ============================================================

def query_api(question: str, top_k: int = TOP_K, document_ids: list[str] | None = None) -> dict:
    """Query the /query endpoint and return the raw response dict."""
    payload: dict[str, Any] = {
        "question": question,
        "top_k": top_k,
        "include_sources": True,
    }
    if document_ids:
        payload["document_ids"] = document_ids
    try:
        r = httpx.post(f"{BASE_URL}/query", json=payload, timeout=300)
        if r.status_code == 200:
            return r.json()
        return {
            "answer": "",
            "supported": False,
            "confidence": None,
            "answer_type": "error",
            "sources": [],
            "latency_ms": 0.0,
            "error": f"HTTP {r.status_code}: {r.text[:200]}",
        }
    except Exception as exc:  # pragma: no cover - network guards
        return {
            "answer": "",
            "supported": False,
            "confidence": None,
            "answer_type": "error",
            "sources": [],
            "latency_ms": 0.0,
            "error": repr(exc),
        }


def ingest(text: str, document_name: str) -> dict:
    r = httpx.post(
        f"{BASE_URL}/ingest",
        json={"text": text, "document_name": document_name},
        timeout=120,
    )
    if r.status_code == 200:
        return r.json()
    return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}


# ============================================================
# Evaluation
# ============================================================

@dataclass
class CaseResult:
    test_id: str
    category: str
    question: str
    expected_supported: bool
    expected_result: str
    actual_supported: bool
    answer: str
    answer_type: str
    confidence: float | None
    top_source_score: float | None
    latency_ms: float
    api_error: str | None
    passed: bool
    failure_reason: str | None = None


def _top_source_score(response: dict) -> float | None:
    sources = response.get("sources") or []
    if sources:
        score = sources[0].get("score")
        if isinstance(score, (int, float)):
            return float(score)
    return None


def evaluate_case(case: TestCase, response: dict) -> CaseResult:
    answer = str(response.get("answer") or "")
    actual_supported = bool(response.get("supported", False))
    answer_type = str(response.get("answer_type", "unknown"))
    confidence = response.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = None
    latency_ms = response.get("latency_ms", 0.0)
    api_error = response.get("error")
    expected_result = "supported" if case.expected_supported else "unsupported"

    failure_reason: str | None = None
    passed = True

    if api_error:
        passed = False
        failure_reason = "api_error"
    elif case.expected_supported:
        terms_found = [
            t for t in case.expected_terms if t.lower() in answer.lower()
        ]
        if not actual_supported:
            passed = False
            failure_reason = "false_rejection"
        elif not terms_found:
            passed = False
            failure_reason = "wrong_content"
    else:
        if actual_supported:
            passed = False
            failure_reason = "false_support"

    return CaseResult(
        test_id=case.id,
        category=case.category,
        question=case.question,
        expected_supported=case.expected_supported,
        expected_result=expected_result,
        actual_supported=actual_supported,
        answer=answer,
        answer_type=answer_type,
        confidence=confidence,
        top_source_score=_top_source_score(response),
        latency_ms=latency_ms,
        api_error=api_error,
        passed=passed,
        failure_reason=failure_reason,
    )


# ============================================================
# Metrics
# ============================================================

def compute_metrics(results: list[CaseResult], started_at: str) -> dict:
    total = len(results)
    exp_supported = sum(1 for r in results if r.expected_supported)
    exp_unsupported = total - exp_supported

    supported_results = [r for r in results if r.expected_supported]
    unsupported_results = [r for r in results if not r.expected_supported]

    supported_correct = sum(1 for r in supported_results if r.passed)
    supported_correctness = supported_correct / len(supported_results) if supported_results else 0.0

    unsupported_rejected = sum(
        1 for r in unsupported_results if not r.actual_supported and not r.api_error
    )
    rejection_rate = unsupported_rejected / len(unsupported_results) if unsupported_results else 0.0

    false_support = sum(1 for r in unsupported_results if r.actual_supported)
    false_support_rate = false_support / exp_unsupported if exp_unsupported else 0.0

    false_rejection = sum(1 for r in supported_results if not r.actual_supported)
    false_rejection_rate = false_rejection / exp_supported if exp_supported else 0.0

    ok_latencies = [r.latency_ms for r in results if not r.api_error and r.latency_ms]
    avg_latency = statistics.mean(ok_latencies) if ok_latencies else 0.0
    p50_latency = statistics.median(ok_latencies) if ok_latencies else 0.0
    p95_latency = (
        sorted(ok_latencies)[int(0.95 * len(ok_latencies))]
        if ok_latencies else 0.0
    )

    api_errors = sum(1 for r in results if r.api_error)
    failed = [r for r in results if not r.passed]

    targets_passed = {
        "supported_correctness_ge_90": supported_correctness >= TARGETS["supported_correctness_ge_90"],
        "rejection_rate_ge_95": rejection_rate >= TARGETS["rejection_rate_ge_95"],
        "false_support_rate_le_5": false_support_rate <= TARGETS["false_support_rate_le_5"],
        "false_rejection_rate_le_5": false_rejection_rate <= TARGETS["false_rejection_rate_le_5"],
        "api_errors_zero": api_errors == TARGETS["api_errors_zero"],
    }

    by_category: dict[str, dict] = {}
    for r in results:
        cat = by_category.setdefault(
            r.category,
            {"total": 0, "passed": 0, "failed": 0, "supported": 0, "unsupported": 0},
        )
        cat["total"] += 1
        if r.passed:
            cat["passed"] += 1
        else:
            cat["failed"] += 1
        if r.actual_supported:
            cat["supported"] += 1
        else:
            cat["unsupported"] += 1

    failures_by_type: dict[str, list[str]] = {}
    for r in failed:
        reason = r.failure_reason or "unknown"
        failures_by_type.setdefault(reason, []).append(r.test_id)

    return {
        "metadata": {
            "benchmark": "ralg_end_to_end_reliability_v2",
            "run_started_at": started_at,
            "api_base_url": BASE_URL,
            "top_k": TOP_K,
            "total_cases": total,
            "ingested_document": "compressor_sop_reliability_v2",
        },
        "summary": {
            "total_cases": total,
            "expected_supported": exp_supported,
            "expected_unsupported": exp_unsupported,
            "actual_supported": sum(1 for r in results if r.actual_supported),
            "actual_unsupported": sum(1 for r in results if not r.actual_supported),
            "passed_count": sum(1 for r in results if r.passed),
            "failed_count": len(failed),
            "supported_accuracy": supported_correctness,
            "supported_correct": supported_correct,
            "supported_total": len(supported_results),
            "unsupported_rejection_rate": rejection_rate,
            "unsupported_rejected": unsupported_rejected,
            "unsupported_total": len(unsupported_results),
            "false_support_rate": false_support_rate,
            "false_support_count": false_support,
            "false_rejection_rate": false_rejection_rate,
            "false_rejection_count": false_rejection,
            "avg_latency_ms": round(avg_latency, 2),
            "p50_latency_ms": round(p50_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "api_error_count": api_errors,
        },
        "targets": targets_passed,
        "by_category": by_category,
        "failures_by_type": failures_by_type,
        "failures": [
            {
                "test_id": r.test_id,
                "question": r.question,
                "expected_result": r.expected_result,
                "actual_answer": r.answer,
                "supported": r.actual_supported,
                "answer_type": r.answer_type,
                "confidence": r.confidence,
                "top_source_score": r.top_source_score,
                "failure_reason": r.failure_reason,
            }
            for r in failed
        ],
        "detailed_results": [asdict(r) for r in results],
    }


# ============================================================
# Reporting
# ============================================================

def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_markdown(metrics: dict, started_at: str) -> str:
    s = metrics["summary"]
    lines = [
        "# RALG End-to-End Reliability Benchmark",
        "",
        f"Run at: {started_at}",
        f"Target: current `/query` behavior of `src/api_server.py`",
        f"API: `{metrics['metadata']['api_base_url']}` (top_k={metrics['metadata']['top_k']})",
        "",
        "## Summary",
        "",
        f"- Total cases: {s['total_cases']}",
        f"- Expected supported: {s['expected_supported']} / Expected unsupported: {s['expected_unsupported']}",
        f"- Passed: {s['passed_count']} / Failed: {s['failed_count']}",
        f"- Actual supported: {s['actual_supported']} / Actual unsupported: {s['actual_unsupported']}",
        "",
        "## Scores",
        "",
        f"- **Supported-answer correctness**: {_pct(s['supported_accuracy'])} ({s['supported_correct']}/{s['supported_total']})",
        f"- **Unsupported rejection rate**: {_pct(s['unsupported_rejection_rate'])} ({s['unsupported_rejected']}/{s['unsupported_total']})",
        f"- **False-support rate**: {_pct(s['false_support_rate'])} ({s['false_support_count']} cases)",
        f"- **False-rejection rate**: {_pct(s['false_rejection_rate'])} ({s['false_rejection_count']} cases)",
        f"- **Average latency**: {s['avg_latency_ms']:.0f} ms (p50 {s['p50_latency_ms']:.0f} ms, p95 {s['p95_latency_ms']:.0f} ms)",
        f"- **Runtime/API errors**: {s['api_error_count']}",
        "",
        "## Targets",
        "",
    ]
    for target, ok in metrics["targets"].items():
        lines.append(f"- `{target}`: {'PASS' if ok else 'FAIL'}")
    lines.append("")
    lines.append("## Failures by type")
    lines.append("")
    failures_by_type = metrics["failures_by_type"]
    if failures_by_type:
        for reason, ids in sorted(failures_by_type.items()):
            lines.append(f"- **{reason}** ({len(ids)}): {', '.join(ids)}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Per-category breakdown")
    lines.append("")
    lines.append("| Category | Total | Passed | Failed | Supported | Unsupported |")
    lines.append("|---|---|---|---|---|---|")
    for cat, data in metrics["by_category"].items():
        lines.append(
            f"| {cat} | {data['total']} | {data['passed']} | {data['failed']} | "
            f"{data['supported']} | {data['unsupported']} |"
        )
    lines.append("")
    lines.append("## Failed cases (details)")
    lines.append("")
    failures = metrics["failures"]
    if failures:
        lines.append("| Test ID | Question | Expected | Actual answer | Supported | Answer type | Confidence | Top source score | Failure reason |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for f in failures:
            answer_short = f["actual_answer"][:80].replace("|", "\\|").replace("\n", " ")
            question_short = f["question"][:70].replace("|", "\\|")
            conf = "N/A" if f["confidence"] is None else f"{f['confidence']:.2f}"
            top = "N/A" if f["top_source_score"] is None else f"{f['top_source_score']:.2f}"
            lines.append(
                f"| {f['test_id']} | {question_short} | {f['expected_result']} | "
                f"{answer_short} | {f['supported']} | {f['answer_type']} | {conf} | {top} | {f['failure_reason']} |"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


# ============================================================
# Main
# ============================================================

def main() -> int:
    print("RALG End-to-End Reliability Benchmark (V2)")
    print(f"API: {BASE_URL}")
    print(f"Cases: {len(TEST_CASES)}")
    print("=" * 78)

    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=10)
        if r.status_code != 200:
            print(f"Server not healthy: HTTP {r.status_code}")
            return 2
    except Exception as exc:
        print(f"Cannot reach API at {BASE_URL}: {exc!r}")
        print("Start the server with: uvicorn src.api_server:app --host 127.0.0.1 --port 8000")
        return 2

    started_at = time.strftime("%Y-%m-%d %H:%M:%S")

    print("\nIngesting compressor SOP for runtime-ingested cases...")
    ingest_result = ingest(COMPRESSOR_SOP, "compressor_sop_reliability_v2")
    print(f"Ingest response: {json.dumps(ingest_result)[:200]}")

    # Capture document_id for scoped queries — SOP/runtime cases
    # exercise the actual document-scoped retrieval product path.
    sop_document_id = ingest_result.get("document_id")

    results: list[CaseResult] = []

    for i, case in enumerate(TEST_CASES, start=1):
        print(f"[{i:02d}/50] {case.id} ({case.category}) - {case.question[:72]}")
        # SOP and runtime-ingested cases use document-scoped retrieval
        # to query only the ingested SOP document, not the static KB.
        scoped_ids = (
            [sop_document_id]
            if sop_document_id
            and case.category in ("sop_procedure", "runtime_ingested")
            else None
        )
        response = query_api(case.question, document_ids=scoped_ids)
        result = evaluate_case(case, response)
        results.append(result)
        print(
            f"  {'PASS' if result.passed else 'FAIL'} | supported={result.actual_supported} "
            f"(exp={result.expected_supported}) | type={result.answer_type} | "
            f"latency={result.latency_ms:.0f}ms | conf={result.confidence} | "
            f"top_score={result.top_source_score}"
        )
        if result.failure_reason:
            print(f"  reason: {result.failure_reason}")

    metrics = compute_metrics(results, started_at)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(metrics, started_at), encoding="utf-8")

    print("\n" + "=" * 78)
    print("RELIABILITY BENCHMARK RESULTS")
    print("=" * 78)
    s = metrics["summary"]
    print(f"Total cases: {s['total_cases']}")
    print(f"Passed: {s['passed_count']} | Failed: {s['failed_count']}")
    print(f"Supported-answer correctness: {_pct(s['supported_accuracy'])}")
    print(f"Unsupported rejection rate: {_pct(s['unsupported_rejection_rate'])}")
    print(f"False-support rate: {_pct(s['false_support_rate'])}")
    print(f"False-rejection rate: {_pct(s['false_rejection_rate'])}")
    print(f"Average latency: {s['avg_latency_ms']:.0f} ms")
    print(f"API errors: {s['api_error_count']}")
    print("\nTargets:")
    for target, ok in metrics["targets"].items():
        print(f"  {target}: {'PASS' if ok else 'FAIL'}")
    print("\nFailures by type:")
    for reason, ids in metrics["failures_by_type"].items():
        print(f"  {reason} ({len(ids)}): {', '.join(ids)}")

    print(f"\nSaved: {OUTPUT_JSON}")
    print(f"Saved: {OUTPUT_MD}")

    return 0 if s["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
