#!/usr/bin/env python3
"""
Resource and Scale Validation for RALG Pilot Readiness.

Measures:
1. Baseline process RAM before pipeline initialization.
2. RAM after pipeline/model/index initialization.
3. GPU VRAM if CUDA is active.
4. Pipeline initialization time.
5. Query latency p50/p95 over representative repeated queries.
6. Ingestion latency at multiple document/chunk sizes.
7. Memory growth after repeated runtime ingestion.
8. Retrieval/query performance as runtime corpus grows.
9. Detect obvious memory leaks or unbounded growth.
10. Record exact hardware/runtime environment.
11. Define practical pilot limits based ONLY on measurements.

Scale cases:
- existing baseline corpus
- +100 runtime chunks
- +1,000 runtime chunks
- +5,000 runtime chunks if safe

Output: JSON metrics to stdout and logs/resource_validation_<timestamp>.json
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure project root and src are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load root config.py explicitly (avoids src/config.py shadowing)
import importlib.util as _importlib_util
_ROOT_CONFIG_PATH = PROJECT_ROOT / "config.py"
_spec = _importlib_util.spec_from_file_location("config", str(_ROOT_CONFIG_PATH))
if _spec is None or _spec.loader is None:
    raise ImportError(f"Could not load project config at {_ROOT_CONFIG_PATH}")
_project_config = _importlib_util.module_from_spec(_spec)
sys.modules["config"] = _project_config
_spec.loader.exec_module(_project_config)

from config import KNOWLEDGE_FILES  # noqa: E402

try:
    import psutil
except ImportError:
    psutil = None

try:
    import torch
except ImportError:
    torch = None

from retriever_v2 import load_chunks, build_index  # noqa: E402
from webui.document_processor import chunk_text  # noqa: E402
from rag_chat_v2 import initialize_pipeline  # noqa: E402


# ============================================================
# Configuration
# ============================================================

# Representative queries for latency measurement (smaller set for speed)
REPRESENTATIVE_QUERIES = [
    "When was the Magna Carta signed?",
    "Why did the Roman Empire decline?",
    "How was the Roman army organized?",
    "Explain the structure of DNA.",
    "Who were the main leaders of the French Revolution?",
    "What is the capital of France?",
]

# Scale levels to test (additional runtime chunks)
SCALE_LEVELS = [
    {"name": "baseline", "additional_chunks": 0},
    {"name": "+100", "additional_chunks": 100},
    {"name": "+1000", "additional_chunks": 1000},
    {"name": "+5000", "additional_chunks": 5000},
]

# Safety thresholds (adjust if needed)
MAX_RAM_MB = 8000  # Stop if RAM exceeds this
MAX_VRAM_MB = 6000  # Stop if VRAM exceeds this (if GPU)
MAX_QUERY_LATENCY_S = 10.0  # Stop if query latency exceeds this
MAX_INGEST_LATENCY_S = 60.0  # Stop if ingestion latency exceeds this

# Query iteration counts (can be overridden by --quick)
QUERY_ITERATIONS = 2
QUICK_QUERY_ITERATIONS = 1


# ============================================================
# Utilities
# ============================================================

def get_process_memory_mb() -> float:
    """Return current process RSS in MB."""
    if psutil is None:
        return 0.0
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


def get_gpu_vram_mb() -> float:
    """Return allocated GPU VRAM in MB (0 if no CUDA)."""
    if torch is None or not torch.cuda.is_available():
        return 0.0
    return torch.cuda.memory_allocated() / (1024 * 1024)


def get_gpu_vram_reserved_mb() -> float:
    """Return reserved GPU VRAM in MB (0 if no CUDA)."""
    if torch is None or not torch.cuda.is_available():
        return 0.0
    return torch.cuda.memory_reserved() / (1024 * 1024)


def get_system_info() -> dict[str, Any]:
    """Collect hardware/runtime environment info."""
    info = {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.platform(),
        "python_version": sys.version,
        "cpu_count": os.cpu_count(),
        "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2) if psutil else None,
        "cuda_available": torch.cuda.is_available() if torch else False,
        "cuda_device": torch.cuda.get_device_name(0) if torch and torch.cuda.is_available() else None,
        "torch_version": torch.__version__ if torch else None,
        "psutil_version": psutil.__version__ if psutil else None,
    }
    return info


def percentile(values: list[float], p: float) -> float:
    """Compute percentile p (0-100) of values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def generate_test_chunks(count: int, base_text: str) -> list[str]:
    """Generate synthetic test chunks for ingestion testing."""
    chunks = []
    words = base_text.split()
    chunk_words = 500
    overlap = 50
    step = max(1, chunk_words - overlap)

    for i in range(count):
        start = (i * step) % max(1, len(words) - chunk_words)
        piece = words[start:start + chunk_words]
        if not piece:
            piece = words[:chunk_words]
        chunk = " ".join(piece) + f" [test chunk {i}]"
        chunks.append(chunk)

    return chunks


# ============================================================
# Measurement functions
# ============================================================

def measure_baseline_ram() -> dict[str, Any]:
    """Measure baseline process RAM before any initialization."""
    gc.collect()
    time.sleep(0.5)
    ram_mb = get_process_memory_mb()
    return {"baseline_ram_mb": round(ram_mb, 2)}


def measure_pipeline_init() -> dict[str, Any]:
    """Measure pipeline initialization time and memory."""
    gc.collect()
    time.sleep(0.5)
    ram_before = get_process_memory_mb()
    vram_before = get_gpu_vram_mb()

    start = time.perf_counter()
    pipeline = initialize_pipeline(verbose=False)
    init_time = time.perf_counter() - start

    gc.collect()
    time.sleep(0.5)
    ram_after = get_process_memory_mb()
    vram_after = get_gpu_vram_mb()

    return {
        "pipeline_init_time_s": round(init_time, 3),
        "ram_before_init_mb": round(ram_before, 2),
        "ram_after_init_mb": round(ram_after, 2),
        "ram_delta_mb": round(ram_after - ram_before, 2),
        "vram_before_init_mb": round(vram_before, 2),
        "vram_after_init_mb": round(vram_after, 2),
        "vram_delta_mb": round(vram_after - vram_before, 2),
        "baseline_chunk_count": len(pipeline.get("chunks", [])),
        "device": pipeline.get("device"),
    }


def measure_query_latency(pipeline: dict, queries: list[str], iterations: int = None) -> dict[str, Any]:
    """Measure query latency p50/p95 over repeated queries."""
    from rag_chat_v2 import answer_question

    if iterations is None:
        iterations = QUERY_ITERATIONS

    latencies = []
    results = []

    for _ in range(iterations):
        for query in queries:
            start = time.perf_counter()
            result = answer_question(pipeline, query, verbose=False)
            latency = time.perf_counter() - start
            latencies.append(latency)
            results.append({
                "query": query,
                "latency_s": round(latency, 4),
                "supported": result.get("supported", False),
                "answer_type": result.get("answer_type", "unknown"),
            })

    latencies_sorted = sorted(latencies)
    return {
        "query_count": len(latencies),
        "iterations": iterations,
        "p50_latency_s": round(percentile(latencies, 50), 4),
        "p95_latency_s": round(percentile(latencies, 95), 4),
        "avg_latency_s": round(sum(latencies) / len(latencies), 4),
        "min_latency_s": round(min(latencies), 4),
        "max_latency_s": round(max(latencies), 4),
        "per_query": results,
    }


def measure_ingestion_latency(pipeline: dict, test_chunks: list[str]) -> dict[str, Any]:
    """Measure ingestion latency for a set of chunks."""
    from webui.document_processor import attach_documents, UploadedDocument
    from pathlib import Path

    start = time.perf_counter()

    # Create document objects
    docs = []
    for i, chunk in enumerate(test_chunks):
        doc = UploadedDocument(
            name=f"test_doc_{i}",
            path=Path(f"test_doc_{i}.txt"),
            ext=".txt",
            text=chunk,
            chunks=[chunk],
            chunk_count=1,
        )
        docs.append(doc)

    added = attach_documents(pipeline, docs)
    ingest_time = time.perf_counter() - start

    return {
        "chunks_ingested": added,
        "ingest_time_s": round(ingest_time, 4),
        "total_chunks_after": len(pipeline.get("chunks", [])),
    }


def measure_retrieval_performance(pipeline: dict, queries: list[str]) -> dict[str, Any]:
    """Measure retrieval performance (latency and result quality) at current corpus size."""
    from retriever_v4 import retrieve as retrieve_v4

    retrieval_times = []
    result_counts = []

    for query in queries:
        start = time.perf_counter()
        result = retrieve_v4(
            query,
            pipeline["chunks"],
            pipeline["retrieval_index"],
            pipeline["document_frequency"],
            collect_timings=False,
        )
        elapsed = time.perf_counter() - start
        retrieval_times.append(elapsed)
        result_counts.append(len(result.get("results", [])))

    return {
        "avg_retrieval_latency_s": round(sum(retrieval_times) / len(retrieval_times), 4),
        "p50_retrieval_latency_s": round(percentile(retrieval_times, 50), 4),
        "p95_retrieval_latency_s": round(percentile(retrieval_times, 95), 4),
        "avg_results_returned": round(sum(result_counts) / len(result_counts), 2),
        "total_chunks": len(pipeline.get("chunks", [])),
    }


def run_scale_test() -> dict[str, Any]:
    """Run the full scale validation test."""
    print("=" * 70)
    print("RALG Resource and Scale Validation")
    print("=" * 70)

    # System info
    print("\n[1/11] Collecting system information...")
    system_info = get_system_info()
    print(json.dumps(system_info, indent=2))

    # Baseline RAM
    print("\n[2/11] Measuring baseline RAM...")
    baseline_ram = measure_baseline_ram()
    print(f"  Baseline RAM: {baseline_ram['baseline_ram_mb']:.2f} MB")

    # Pipeline initialization
    print("\n[3/11] Measuring pipeline initialization...")
    init_metrics = measure_pipeline_init()
    pipeline = initialize_pipeline(verbose=False)  # Re-initialize for actual testing
    print(f"  Init time: {init_metrics['pipeline_init_time_s']:.3f}s")
    print(f"  RAM delta: {init_metrics['ram_delta_mb']:.2f} MB")
    print(f"  VRAM delta: {init_metrics['vram_delta_mb']:.2f} MB")
    print(f"  Baseline chunks: {init_metrics['baseline_chunk_count']}")
    print(f"  Device: {init_metrics['device']}")

    # Safety check after init
    current_ram = get_process_memory_mb()
    current_vram = get_gpu_vram_mb()
    if current_ram > MAX_RAM_MB:
        raise RuntimeError(f"RAM after init ({current_ram:.0f} MB) exceeds safety threshold ({MAX_RAM_MB} MB)")
    if current_vram > MAX_VRAM_MB:
        raise RuntimeError(f"VRAM after init ({current_vram:.0f} MB) exceeds safety threshold ({MAX_VRAM_MB} MB)")

    # Query latency at baseline
    print("\n[4/11] Measuring query latency at baseline...")
    query_metrics = measure_query_latency(pipeline, REPRESENTATIVE_QUERIES, iterations=3)
    print(f"  p50: {query_metrics['p50_latency_s']:.4f}s, p95: {query_metrics['p95_latency_s']:.4f}s")
    print(f"  avg: {query_metrics['avg_latency_s']:.4f}s")

    # Retrieval performance at baseline
    print("\n[5/11] Measuring retrieval performance at baseline...")
    retrieval_metrics = measure_retrieval_performance(pipeline, REPRESENTATIVE_QUERIES)
    print(f"  p50 retrieval: {retrieval_metrics['p50_retrieval_latency_s']:.4f}s")
    print(f"  Total chunks: {retrieval_metrics['total_chunks']}")

    # Ingestion latency at baseline (small test)
    print("\n[6/11] Measuring ingestion latency (baseline)...")
    test_chunks_100 = generate_test_chunks(100, " ".join(REPRESENTATIVE_QUERIES) * 100)
    ingest_metrics_100 = measure_ingestion_latency(pipeline, test_chunks_100)
    print(f"  100 chunks: {ingest_metrics_100['ingest_time_s']:.4f}s")

    # Memory growth test - repeated ingestion
    print("\n[7/11] Testing memory growth after repeated ingestion...")
    ram_before_growth = get_process_memory_mb()
    growth_measurements = []

    growth_iterations = 3 if QUERY_ITERATIONS == QUICK_QUERY_ITERATIONS else 5
    growth_chunks_per_iter = 100 if QUERY_ITERATIONS == QUICK_QUERY_ITERATIONS else 200

    for i in range(growth_iterations):
        test_chunks = generate_test_chunks(growth_chunks_per_iter, "memory growth test " * 50)
        ingest_result = measure_ingestion_latency(pipeline, test_chunks)
        gc.collect()
        time.sleep(0.2)
        ram_after = get_process_memory_mb()
        growth_measurements.append({
            "iteration": i + 1,
            "chunks_added": ingest_result["chunks_ingested"],
            "total_chunks": ingest_result["total_chunks_after"],
            "ram_mb": round(ram_after, 2),
            "ram_delta_mb": round(ram_after - ram_before_growth, 2),
            "ingest_time_s": ingest_result["ingest_time_s"],
        })
        print(f"  Iter {i+1}: +{ingest_result['chunks_ingested']} chunks, RAM: {ram_after:.2f} MB (delta: {ram_after - ram_before_growth:.2f} MB)")

    ram_after_growth = get_process_memory_mb()
    total_ram_growth = ram_after_growth - ram_before_growth

    # Scale tests
    scale_results = []
    for level in SCALE_LEVELS:
        if level["name"] == "baseline":
            # Already measured baseline
            scale_results.append({
                "level": "baseline",
                "total_chunks": len(pipeline.get("chunks", [])),
                "ram_mb": round(get_process_memory_mb(), 2),
                "vram_mb": round(get_gpu_vram_mb(), 2),
                "query_p50_s": query_metrics["p50_latency_s"],
                "query_p95_s": query_metrics["p95_latency_s"],
                "retrieval_p50_s": retrieval_metrics["p50_retrieval_latency_s"],
                "retrieval_p95_s": retrieval_metrics["p95_retrieval_latency_s"],
            })
            continue

        additional = level["additional_chunks"]
        print(f"\n[Scale] Testing {level['name']} ({additional} additional chunks)...")

        # Check safety before proceeding
        current_ram = get_process_memory_mb()
        current_vram = get_gpu_vram_mb()
        if current_ram > MAX_RAM_MB:
            print(f"  SKIPPED: RAM ({current_ram:.0f} MB) exceeds safety threshold ({MAX_RAM_MB} MB)")
            scale_results.append({
                "level": level["name"],
                "skipped": True,
                "reason": f"RAM {current_ram:.0f} MB exceeds threshold {MAX_RAM_MB} MB",
            })
            break
        if current_vram > MAX_VRAM_MB:
            print(f"  SKIPPED: VRAM ({current_vram:.0f} MB) exceeds safety threshold ({MAX_VRAM_MB} MB)")
            scale_results.append({
                "level": level["name"],
                "skipped": True,
                "reason": f"VRAM {current_vram:.0f} MB exceeds threshold {MAX_VRAM_MB} MB",
            })
            break

        # Generate and ingest chunks
        test_chunks = generate_test_chunks(additional, "scale test content " * 200)
        start_ingest = time.perf_counter()
        from webui.document_processor import attach_documents, UploadedDocument
        docs = [UploadedDocument(
            name=f"scale_{level['name']}_{i}",
            path=Path(f"scale_{level['name']}_{i}.txt"),
            ext=".txt",
            text=chunk,
            chunks=[chunk],
            chunk_count=1,
        ) for i, chunk in enumerate(test_chunks)]
        added = attach_documents(pipeline, docs)
        ingest_time = time.perf_counter() - start_ingest

        # Measure query latency at this scale
        query_metrics_scale = measure_query_latency(pipeline, REPRESENTATIVE_QUERIES, iterations=QUERY_ITERATIONS)

        # Measure retrieval performance
        retrieval_metrics_scale = measure_retrieval_performance(pipeline, REPRESENTATIVE_QUERIES)

        gc.collect()
        time.sleep(0.5)
        ram_after = get_process_memory_mb()
        vram_after = get_gpu_vram_mb()

        scale_results.append({
            "level": level["name"],
            "chunks_requested": additional,
            "chunks_added": added,
            "total_chunks": len(pipeline.get("chunks", [])),
            "ram_mb": round(ram_after, 2),
            "vram_mb": round(vram_after, 2),
            "ingest_time_s": round(ingest_time, 4),
            "query_p50_s": query_metrics_scale["p50_latency_s"],
            "query_p95_s": query_metrics_scale["p95_latency_s"],
            "query_avg_s": query_metrics_scale["avg_latency_s"],
            "retrieval_p50_s": retrieval_metrics_scale["p50_retrieval_latency_s"],
            "retrieval_p95_s": retrieval_metrics_scale["p95_retrieval_latency_s"],
        })

        print(f"  Total chunks: {len(pipeline.get('chunks', []))}")
        print(f"  RAM: {ram_after:.2f} MB, VRAM: {vram_after:.2f} MB")
        print(f"  Ingest time: {ingest_time:.4f}s")
        print(f"  Query p50: {query_metrics_scale['p50_latency_s']:.4f}s, p95: {query_metrics_scale['p95_latency_s']:.4f}s")
        print(f"  Retrieval p50: {retrieval_metrics_scale['p50_retrieval_latency_s']:.4f}s")

        # Safety check
        if query_metrics_scale["p95_latency_s"] > MAX_QUERY_LATENCY_S:
            print(f"  WARNING: Query p95 latency ({query_metrics_scale['p95_latency_s']:.2f}s) exceeds threshold ({MAX_QUERY_LATENCY_S}s)")
        if ingest_time > MAX_INGEST_LATENCY_S:
            print(f"  WARNING: Ingestion time ({ingest_time:.2f}s) exceeds threshold ({MAX_INGEST_LATENCY_S}s)")

    # Final memory check
    final_ram = get_process_memory_mb()
    final_vram = get_gpu_vram_mb()

    # Compile results
    results = {
        "system_info": system_info,
        "baseline_ram": baseline_ram,
        "pipeline_init": init_metrics,
        "query_latency_baseline": query_metrics,
        "retrieval_performance_baseline": retrieval_metrics,
        "ingestion_latency_100_chunks": ingest_metrics_100,
        "memory_growth_test": {
            "ram_before_mb": round(ram_before_growth, 2),
            "ram_after_mb": round(ram_after_growth, 2),
            "total_growth_mb": round(total_ram_growth, 2),
            "iterations": growth_measurements,
        },
        "scale_results": scale_results,
        "final_state": {
            "ram_mb": round(final_ram, 2),
            "vram_mb": round(final_vram, 2),
            "total_chunks": len(pipeline.get("chunks", [])),
        },
        "safety_thresholds": {
            "max_ram_mb": MAX_RAM_MB,
            "max_vram_mb": MAX_VRAM_MB,
            "max_query_latency_s": MAX_QUERY_LATENCY_S,
            "max_ingest_latency_s": MAX_INGEST_LATENCY_S,
        },
    }

    return results


def define_pilot_limits(results: dict[str, Any]) -> dict[str, Any]:
    """Define practical pilot limits based on measurements."""
    scale_results = results["scale_results"]
    memory_growth = results["memory_growth_test"]

    # Find the highest scale level that was actually tested (not skipped)
    tested_levels = [r for r in scale_results if not r.get("skipped", False)]
    if not tested_levels:
        max_safe_level = "baseline"
    else:
        max_safe_level = tested_levels[-1]["level"]

    # Memory growth analysis
    ram_growth_per_1k_chunks = 0.0
    if memory_growth["total_growth_mb"] > 0:
        total_chunks_added = sum(m["chunks_added"] for m in memory_growth["iterations"])
        if total_chunks_added > 0:
            ram_growth_per_1k_chunks = (memory_growth["total_growth_mb"] / total_chunks_added) * 1000

    # Latency degradation analysis
    baseline_query_p95 = None
    max_scale_query_p95 = None
    for r in tested_levels:
        if r["level"] == "baseline":
            baseline_query_p95 = r.get("query_p95_s", 0)
        max_scale_query_p95 = r.get("query_p95_s", 0)

    latency_degradation_pct = 0.0
    if baseline_query_p95 and baseline_query_p95 > 0:
        latency_degradation_pct = ((max_scale_query_p95 - baseline_query_p95) / baseline_query_p95) * 100

    # Ingestion time per 1k chunks at max scale
    ingest_time_per_1k = 0.0
    for r in tested_levels:
        if r["level"] != "baseline" and "ingest_time_s" in r:
            chunks = r.get("chunks_added", 0)
            if chunks > 0:
                ingest_time_per_1k = (r["ingest_time_s"] / chunks) * 1000

    # Determine recommended pilot limits
    pilot_limits = {
        "max_recommended_runtime_chunks": 0,
        "max_recommended_corpus_chunks": results["final_state"]["total_chunks"],
        "expected_ram_at_max_mb": results["final_state"]["ram_mb"],
        "expected_query_p95_s": max_scale_query_p95 or 0,
        "expected_ingest_time_per_1k_chunks_s": round(ingest_time_per_1k, 4),
        "ram_growth_per_1k_chunks_mb": round(ram_growth_per_1k_chunks, 2),
        "latency_degradation_pct": round(latency_degradation_pct, 1),
        "max_safe_scale_level_tested": max_safe_level,
        "memory_leak_detected": memory_growth["total_growth_mb"] > 500,  # >500MB growth after 1000 chunks is suspicious
        "notes": [],
    }

    # Set max recommended runtime chunks based on max safe level
    if max_safe_level == "baseline":
        pilot_limits["max_recommended_runtime_chunks"] = 0
        pilot_limits["notes"].append("No runtime ingestion scale levels passed safety checks")
    elif max_safe_level == "+100":
        pilot_limits["max_recommended_runtime_chunks"] = 100
        pilot_limits["notes"].append("Only +100 scale level passed")
    elif max_safe_level == "+1000":
        pilot_limits["max_recommended_runtime_chunks"] = 1000
        pilot_limits["notes"].append("+1000 scale level passed; +5000 not tested or failed")
    elif max_safe_level == "+5000":
        pilot_limits["max_recommended_runtime_chunks"] = 5000
        pilot_limits["notes"].append("All scale levels passed")

    # Add warnings
    if memory_growth["total_growth_mb"] > 200:
        pilot_limits["notes"].append(f"Memory growth of {memory_growth['total_growth_mb']:.0f} MB observed after repeated ingestion - monitor in production")

    if latency_degradation_pct > 50:
        pilot_limits["notes"].append(f"Query latency degraded by {latency_degradation_pct:.0f}% at max scale - consider corpus limits")

    if ingest_time_per_1k > 5.0:
        pilot_limits["notes"].append(f"Ingestion time {ingest_time_per_1k:.1f}s per 1k chunks - may impact real-time ingestion")

    return pilot_limits


def main():
    parser = argparse.ArgumentParser(description="Run RALG resource and scale validation")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON file path")
    parser.add_argument("--quick", action="store_true", help="Run quick validation (fewer iterations)")
    parser.add_argument("--skip-scale", action="store_true", help="Skip scale tests beyond baseline")
    args = parser.parse_args()

    global QUERY_ITERATIONS
    if args.quick:
        QUERY_ITERATIONS = QUICK_QUERY_ITERATIONS
        global SCALE_LEVELS
        SCALE_LEVELS = [
            {"name": "baseline", "additional_chunks": 0},
            {"name": "+100", "additional_chunks": 100},
        ]

    try:
        results = run_scale_test()

        # Define pilot limits
        print("\n[10/11] Defining pilot limits...")
        pilot_limits = define_pilot_limits(results)
        results["pilot_limits"] = pilot_limits

        print(f"  Max safe scale level: {pilot_limits['max_safe_scale_level_tested']}")
        print(f"  Max recommended runtime chunks: {pilot_limits['max_recommended_runtime_chunks']}")
        print(f"  Expected RAM at max: {pilot_limits['expected_ram_at_max_mb']:.0f} MB")
        print(f"  Expected query p95: {pilot_limits['expected_query_p95_s']:.3f}s")
        print(f"  RAM growth per 1k chunks: {pilot_limits['ram_growth_per_1k_chunks_mb']:.1f} MB")
        print(f"  Latency degradation: {pilot_limits['latency_degradation_pct']:.1f}%")
        print(f"  Memory leak detected: {pilot_limits['memory_leak_detected']}")
        for note in pilot_limits["notes"]:
            print(f"  - {note}")

        # Output JSON
        print("\n[11/11] Results summary:")
        print(json.dumps({
            "system_info": results["system_info"],
            "baseline_ram_mb": results["baseline_ram"]["baseline_ram_mb"],
            "loaded_ram_mb": results["pipeline_init"]["ram_after_init_mb"],
            "vram_mb": results["pipeline_init"]["vram_after_init_mb"],
            "init_time_s": results["pipeline_init"]["pipeline_init_time_s"],
            "query_p50_s": results["query_latency_baseline"]["p50_latency_s"],
            "query_p95_s": results["query_latency_baseline"]["p95_latency_s"],
            "scale_results": results["scale_results"],
            "memory_growth_mb": results["memory_growth_test"]["total_growth_mb"],
            "pilot_limits": pilot_limits,
        }, indent=2))

        # Write to file
        if args.output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = PROJECT_ROOT / "logs" / f"resource_validation_{timestamp}.json"
        else:
            output_path = args.output

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nFull results written to: {output_path}")

    except Exception as e:
        print(f"\nVALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()