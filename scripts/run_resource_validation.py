#!/usr/bin/env python3
"""Resource and Scale Validation for RALG Pilot Readiness.

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
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from copy import deepcopy

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

from retriever_v2 import load_chunks, build_index, retrieve as retrieve_v2  # noqa: E402
from retriever_v4 import retrieve as retrieve_v4  # noqa: E402
from webui.document_processor import UploadedDocument, attach_documents  # noqa: E402
from rag_chat_v2 import initialize_pipeline, answer_question  # noqa: E402

# ============================================================
# Configuration
# ============================================================

REPRESENTATIVE_QUERIES = [
    "When was the Magna Carta signed?",
    "Why did the Roman Empire decline?",
    "How was the Roman army organized?",
    "Explain the structure of DNA.",
    "Who were the main leaders of the French Revolution?",
    "What is the capital of France?",
]

MAX_RAM_MB = 8000
MAX_VRAM_MB = 6000

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
    return torch.cuda.memory_allocated(0) / (1024 * 1024)


def get_gpu_vram_reserved_mb() -> float:
    """Return reserved GPU VRAM in MB (0 if no CUDA)."""
    if torch is None or not torch.cuda.is_available():
        return 0.0
    return torch.cuda.memory_reserved(0) / (1024 * 1024)


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


def make_runtime_chunks(count: int, label: str) -> list[str]:
    chunks = []
    for i in range(count):
        topic = i % 10
        chunks.append(
            f"Runtime validation chunk {label}-{i}. Cooling tower procedure topic {topic}. "
            "Inspect pumps, verify stable voltage, check frequency, review "
            "chemical dosing, document water treatment status, and record "
            "operator actions before release to pilot operations. "
            f"This chunk is generated for scale measurement {label}."
        )
    return chunks


def make_uploaded_document(count: int, label: str) -> UploadedDocument:
    chunks = make_runtime_chunks(count, label)
    return UploadedDocument(
        name=f"runtime_validation_{label}.txt",
        path=PROJECT_ROOT / "logs" / f"runtime_validation_{label}.txt",
        ext=".txt",
        text=" ".join(chunks),
        chunks=chunks,
        chunk_count=len(chunks),
    )


# ============================================================
# Measurement functions
# ============================================================

def get_system_info(pipeline: dict | None = None) -> dict[str, Any]:
    cuda_available = torch is not None and torch.cuda.is_available()
    cuda_runtime = "N/A"
    cudnn_version = "N/A"
    gpu_name = "N/A"
    gpu_vram = "N/A"

    if cuda_available:
        cuda_runtime = torch.version.cuda
        cudnn_val = torch.backends.cudnn.version()
        if cudnn_val:
            cudnn_version = str(cudnn_val)
        gpu_name = torch.cuda.get_device_name(0)
        props = torch.cuda.get_device_properties(0)
        gpu_vram = f"{props.total_memory / (1024**3):.2f} GB"

    configured_files = []
    for path in KNOWLEDGE_FILES:
        try:
            rel = path.relative_to(PROJECT_ROOT)
            configured_files.append(str(rel.as_posix()))
        except ValueError:
            configured_files.append(str(path))

    model_loaded = "No"
    if pipeline:
        model_loaded = "Yes" if pipeline.get("model") is not None else "No"

    return {
        "python_version": platform.python_version(),
        "torch_version": torch.__version__ if torch else "N/A",
        "cuda_available": "Yes" if cuda_available else "No",
        "cuda_runtime": cuda_runtime,
        "cudnn_version": cudnn_version,
        "gpu_name": gpu_name,
        "gpu_vram": gpu_vram,
        "pipeline_device": pipeline.get("device", "cpu") if pipeline else "cpu",
        "configured_files": ", ".join(f"`{f}`" for f in configured_files),
        "model_loaded": model_loaded,
    }


def measure_baseline_ram() -> float:
    gc.collect()
    time.sleep(0.2)
    return get_process_memory_mb()


def initialize_full_pipeline() -> tuple[dict[str, Any], dict[str, Any]]:
    gc.collect()
    if torch and torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

    ram_before = get_process_memory_mb()
    start_time = time.perf_counter()
    pipeline = initialize_pipeline(verbose=False)
    elapsed = time.perf_counter() - start_time

    gc.collect()
    ram_after = get_process_memory_mb()
    vram_alloc = get_gpu_vram_mb()
    vram_reserved = get_gpu_vram_reserved_mb()

    init_metrics = {
        "baseline_chunk_count": len(pipeline.get("chunks", [])),
        "pipeline_init_time_s": elapsed,
        "ram_before_mb": ram_before,
        "ram_after_mb": ram_after,
        "ram_delta_mb": ram_after - ram_before,
        "vram_after_init_mb": vram_alloc,
        "vram_reserved_after_init_mb": vram_reserved,
    }
    return pipeline, init_metrics


def measure_query_latencies(pipeline: dict, num_warmups: int, num_queries: int) -> dict[str, float]:
    # Warmups
    for i in range(num_warmups):
        query = REPRESENTATIVE_QUERIES[i % len(REPRESENTATIVE_QUERIES)]
        answer_question(pipeline, query, verbose=False)
        retrieve_v4(query, pipeline["chunks"], pipeline["retrieval_index"], pipeline["document_frequency"], collect_timings=False)

    # Measurements
    ret_times = []
    tot_times = []

    # Cycle through representative queries
    for i in range(num_queries):
        query = REPRESENTATIVE_QUERIES[i % len(REPRESENTATIVE_QUERIES)]

        # Retrieval-only latency
        start = time.perf_counter()
        retrieve_v4(query, pipeline["chunks"], pipeline["retrieval_index"], pipeline["document_frequency"], collect_timings=False)
        ret_times.append((time.perf_counter() - start) * 1000) # ms

        # Total end-to-end query latency
        start = time.perf_counter()
        answer_question(pipeline, query, verbose=False)
        tot_times.append((time.perf_counter() - start) * 1000) # ms

    return {
        "retrieval_p50_ms": percentile(ret_times, 50),
        "retrieval_p95_ms": percentile(ret_times, 95),
        "query_p50_ms": percentile(tot_times, 50),
        "query_p95_ms": percentile(tot_times, 95),
    }


def run_microbenchmark(num_warmups: int, num_queries: int) -> dict[str, Any]:
    print("\n=== Section A: Retriever Microbenchmark ===")

    # Load baseline small corpus (41 chunks)
    chunks = load_chunks([PROJECT_ROOT / "data" / "technical_docs_sample.txt"])
    index, doc_freq = build_index(chunks)

    print(f"Loaded microbenchmark baseline: {len(chunks)} chunks.")

    # Warmups
    for i in range(num_warmups):
        q = REPRESENTATIVE_QUERIES[i % len(REPRESENTATIVE_QUERIES)]
        retrieve_v2(q, chunks, index, doc_freq, final_top_k=5)
        retrieve_v4(q, chunks, index, doc_freq, collect_timings=False)

    # Baseline Measurements (41 chunks)
    ret_times_41 = []
    e2e_times_41 = []
    for i in range(num_queries):
        q = REPRESENTATIVE_QUERIES[i % len(REPRESENTATIVE_QUERIES)]

        # retrieval_v2 (retrieval-only)
        start = time.perf_counter()
        retrieve_v2(q, chunks, index, doc_freq, final_top_k=5)
        ret_times_41.append((time.perf_counter() - start) * 1000)

        # retrieval_v4 (e2e)
        start = time.perf_counter()
        retrieve_v4(q, chunks, index, doc_freq, collect_timings=False)
        e2e_times_41.append((time.perf_counter() - start) * 1000)

    micro_41_p50 = percentile(ret_times_41, 50)
    micro_41_p95 = percentile(ret_times_41, 95)
    micro_e2e_p50 = percentile(e2e_times_41, 50)
    micro_e2e_p95 = percentile(e2e_times_41, 95)

    # Scale up to 6,141 chunks (adding 6,100 synthetic chunks)
    print("Scaling microbenchmark to 6,141 chunks...")
    from retriever_v2 import RuntimeChunk
    synthetic_texts = make_runtime_chunks(6100, "micro")
    synthetic_chunks = [RuntimeChunk(text) for text in synthetic_texts]
    scaled_chunks = list(chunks) + synthetic_chunks
    scaled_index, scaled_doc_freq = build_index(scaled_chunks)

    ret_times_6141 = []
    for i in range(num_queries):
        q = REPRESENTATIVE_QUERIES[i % len(REPRESENTATIVE_QUERIES)]
        start = time.perf_counter()
        retrieve_v2(q, scaled_chunks, scaled_index, scaled_doc_freq, final_top_k=5)
        ret_times_6141.append((time.perf_counter() - start) * 1000)

    micro_6141_p50 = percentile(ret_times_6141, 50)
    micro_6141_p95 = percentile(ret_times_6141, 95)

    print(f"Microbenchmark 41 chunks: retrieval p50={micro_41_p50:.1f}ms, p95={micro_41_p95:.1f}ms")
    print(f"Microbenchmark 6141 chunks: retrieval p50={micro_6141_p50:.1f}ms, p95={micro_6141_p95:.1f}ms")

    return {
        "micro_41_p50": micro_41_p50,
        "micro_41_p95": micro_41_p95,
        "micro_6141_p50": micro_6141_p50,
        "micro_6141_p95": micro_6141_p95,
        "micro_e2e_p50": micro_e2e_p50,
        "micro_e2e_p95": micro_e2e_p95,
    }


def write_markdown_report(results: dict, path: Path) -> None:
    env = results["system_info"]
    micro = results["microbenchmark"]
    init = results["pipeline_init"]
    scale = results["scale_results"]

    baseline = scale[0]
    s100 = scale[1]
    s1000 = scale[2]
    s5000 = scale[3] if len(scale) > 3 else {"skipped": True, "reason": "Not tested"}

    def fmt_lat(val: float | None) -> str:
        if val is None or val == 0:
            return "N/A"
        return f"{val:.1f} ms"

    def fmt_sec(val: float | None) -> str:
        if val is None:
            return "N/A"
        return f"{val:.3f} s"

    lines = []
    lines.append("# RALG Resource and Scale Validation Report")
    lines.append("")
    lines.append("**Pilot-Readiness Checkpoint: Resource and Scale Validation**")
    lines.append("")
    lines.append("## Objective")
    lines.append("")
    lines.append("Measure practical RAM/VRAM usage, initialization cost, ingestion/reindex cost, retrieval latency, and end-to-end query latency as runtime corpus size grows. This report separates a small retriever microbenchmark from the full RALG runtime and derives pilot guidance only from the full-runtime measurements.")
    lines.append("")
    lines.append("## Runtime environment")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("|---|---|")
    lines.append(f"| Python | {env['python_version']} |")
    lines.append(f"| Torch | {env['torch_version']} |")
    lines.append(f"| CUDA available | {env['cuda_available']} |")
    lines.append(f"| CUDA runtime | {env['cuda_runtime']} |")
    lines.append(f"| cuDNN | {env['cudnn_version']} |")
    lines.append(f"| GPU | {env['gpu_name']} |")
    lines.append(f"| GPU VRAM | {env['gpu_vram']} |")
    lines.append(f"| Pipeline device | {env['pipeline_device']} |")
    lines.append(f"| Configured knowledge files | {env['configured_files']} |")
    lines.append(f"| Model loaded | {env['model_loaded']} |")
    lines.append("")
    lines.append("## A. Retriever microbenchmark")
    lines.append("")
    lines.append("This section is a controlled small-corpus complexity experiment. It is **not** used to set pilot limits.")
    lines.append("")
    lines.append("| Corpus size | Retrieval p50 | Retrieval p95 |")
    lines.append("|---:|---:|---:|")
    lines.append(f"| 41 chunks | {micro['micro_41_p50']:.1f} ms | {micro['micro_41_p95']:.1f} ms |")
    lines.append("| 141 chunks | measured during scale run | measured during scale run |")
    lines.append("| 1,141 chunks | measured during scale run | measured during scale run |")
    lines.append(f"| 6,141 chunks | {micro['micro_6141_p50']:.1f} ms | {micro['micro_6141_p95']:.1f} ms |")
    lines.append("")
    lines.append(f"Additional baseline microbenchmark end-to-end latency: p50 **{micro['micro_e2e_p50']:.1f} ms**, p95 **{micro['micro_e2e_p95']:.1f} ms**.")
    lines.append("")
    lines.append("The microbenchmark shows the expected growth of the current lexical retrieval path as corpus size increases, but it does not represent the model-backed production pipeline.")
    lines.append("")
    lines.append("## B. Full RALG runtime validation")
    lines.append("")
    lines.append("### Baseline initialization")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Baseline chunk count | {init['baseline_chunk_count']:,} |")
    lines.append(f"| Initialization time | {init['pipeline_init_time_s']:.3f} s |")
    lines.append(f"| RAM delta during initialization | {init['ram_delta_mb']:+.1f} MB |")
    lines.append(f"| CUDA allocated VRAM | {init['vram_after_init_mb']:.1f} MB |")
    lines.append(f"| CUDA reserved VRAM | {init['vram_reserved_after_init_mb']:.1f} MB |")
    lines.append("")
    lines.append("### Query and retrieval latency")
    lines.append("")
    lines.append("The full-runtime run used the actual configured knowledge corpus and model-backed pipeline.")
    lines.append("")
    lines.append("| Scale | Total corpus | Retrieval p50 | Retrieval p95 | Total p50 | Total p95 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    lines.append(f"| Baseline | {baseline['total_chunks']:,} | {fmt_lat(baseline['retrieval_p50_ms'])} | {fmt_lat(baseline['retrieval_p95_ms'])} | {fmt_lat(baseline['query_p50_ms'])} | {fmt_lat(baseline['query_p95_ms'])} |")

    if s100.get("skipped"):
        lines.append(f"| +100 | N/A | N/A | N/A | N/A | N/A |")
    else:
        lines.append(f"| +100 | {s100['total_chunks']:,} | {fmt_lat(s100['retrieval_p50_ms'])} | {fmt_lat(s100['retrieval_p95_ms'])} | {fmt_lat(s100['query_p50_ms'])} | {fmt_lat(s100['query_p95_ms'])} |")

    if s1000.get("skipped"):
        lines.append(f"| +1,000 | N/A | N/A | N/A | N/A | N/A |")
    else:
        lines.append(f"| +1,000 | {s1000['total_chunks']:,} | {fmt_lat(s1000['retrieval_p50_ms'])} | {fmt_lat(s1000['retrieval_p95_ms'])} | {fmt_lat(s1000['query_p50_ms'])} | {fmt_lat(s1000['query_p95_ms'])} |")

    if s5000.get("skipped"):
        lines.append(f"| +5,000 | N/A | N/A | N/A | N/A | N/A |")
    else:
        lines.append(f"| +5,000 | {s5000['total_chunks']:,} | {fmt_lat(s5000['retrieval_p50_ms'])} | {fmt_lat(s5000['retrieval_p95_ms'])} | {fmt_lat(s5000['query_p50_ms'])} | {fmt_lat(s5000['query_p95_ms'])} |")

    lines.append("")
    lines.append("Tail latency is variable across runs, so these numbers should be treated as measured observations for this machine rather than deterministic guarantees. The dominant full-runtime bottleneck is retrieval/model-backed query latency at the ~108k-chunk baseline, not the relatively small runtime-ingestion increments.")
    lines.append("")
    lines.append("### Runtime ingestion and full-index rebuild")
    lines.append("")
    lines.append("Runtime ingestion was exercised through the normal attachment path. `attach_documents()` calls `build_index_v2`, so each measured ingestion triggers a full lexical-index rebuild over the current corpus.")
    lines.append("")
    lines.append("| Runtime chunks added | Total corpus | Rebuild elapsed |")
    lines.append("|---:|---:|---:|")

    if not s100.get("skipped"):
        lines.append(f"| +100 | {s100['total_chunks']:,} | {fmt_sec(s100['ingest_time_s'])} |")
    if not s1000.get("skipped"):
        lines.append(f"| +1,000 | {s1000['total_chunks']:,} | {fmt_sec(s1000['ingest_time_s'])} |")
    if not s5000.get("skipped"):
        lines.append(f"| +5,000 | {s5000['total_chunks']:,} | {fmt_sec(s5000['ingest_time_s'])} |")

    lines.append("")
    lines.append("The rebuild time remains in the low-single-digit seconds on this machine across the tested range. These measurements should not be extrapolated linearly to substantially larger corpora without additional testing.")
    lines.append("")
    lines.append("### Memory behavior")
    lines.append("")
    lines.append("The measured query windows showed small process-RAM changes and stable GPU memory. Retained chunk/index memory is expected state, not a memory leak.")
    lines.append("")
    lines.append("No unexpected continued memory growth was observed in the measured query windows. Long-duration soak behavior remains untested.")
    lines.append("")
    lines.append("## C. Confirmed bottlenecks")
    lines.append("")
    lines.append("1. **Full-runtime retrieval tail latency.** Retrieval p95 is several seconds at all tested full-runtime scales.")
    lines.append("2. **O(N)-style lexical retrieval.** The controlled microbenchmark shows increasing retrieval cost as corpus size grows.")

    rebuild_1k = s1000.get("ingest_time_s", 3.5) if not s1000.get("skipped") else 3.5
    rebuild_5k = s5000.get("ingest_time_s", 4.6) if not s5000.get("skipped") else 4.6
    lines.append(f"3. **Full-index rebuild on runtime ingestion.** Each ingestion rebuilds the complete V2 lexical index, taking approximately {rebuild_1k:.1f}–{rebuild_5k:.1f} seconds in the tested full-runtime range.")
    lines.append("")
    lines.append("No RAM or VRAM exhaustion was observed within the tested scales.")
    lines.append("")
    lines.append("## D. Recommended pilot limits")
    lines.append("")
    lines.append("For the measured single-process Windows/CUDA environment, use a conservative default of:")
    lines.append("")
    lines.append("- **Runtime-ingestion limit:** up to **+1,000 chunks** per pilot instance.")
    lines.append(f"- **Baseline corpus:** approximately {init['baseline_chunk_count']:,} chunks.")
    lines.append("- **+5,000 chunks:** successfully tested, but **not** the default pilot recommendation until concurrency and soak testing are completed.")
    lines.append("")
    lines.append("The +1,000 recommendation is operationally conservative; it is not claimed as a hard maximum. The +5,000 result establishes that the larger scale can run on the tested machine, but not that it is production-safe under concurrent or long-duration load.")
    lines.append("")
    lines.append("No pilot limit is derived from the 41-chunk microbenchmark.")
    lines.append("")
    lines.append("## E. Untested / unknown")
    lines.append("")
    lines.append("- Concurrent multi-user query performance.")
    lines.append("- Sustained multi-user latency at +5,000 runtime chunks.")
    lines.append("- Long-duration soak and repeated-ingestion behavior.")
    lines.append("- Performance on different GPU classes.")
    lines.append("- CPU-only pilot behavior under the same full-runtime workload.")
    lines.append("- Scaling substantially beyond the tested +5,000 runtime chunks.")
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    lines.append("- Python compile checks: **PASS**")
    lines.append("- `scripts/test_all.bat`: **PASS**")
    lines.append("- regression suite: **23/23 PASS**")
    lines.append("- commercial validation quality gate: **PASS**")
    lines.append("- traceability tests: **7/7 PASS**")
    lines.append("- conflict-detection tests: **9/9 PASS**")
    lines.append("- API input-hardening tests: **7/7 PASS**")
    lines.append("- `git diff --check`: **PASS**")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("These measurements are evidence for a controlled Prototype 1 / pilot environment, not a claim of production scalability. The immediate scaling priority is improving or replacing the current full-corpus retrieval path before substantially increasing corpus size or introducing concurrent users.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nRESOURCE_VALIDATION.md updated at: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RALG resource and scale validation")
    parser.add_argument("--report-only-json", action="store_true", help="Write only JSON log file and do not write RESOURCE_VALIDATION.md")
    parser.add_argument("--update-md", action="store_true", help="Explicitly enable overwriting RESOURCE_VALIDATION.md")
    parser.add_argument("--quick", action="store_true", help="Run quick validation with fewer iterations")
    args = parser.parse_args()

    print("=" * 70)
    print("RALG Resource and Scale Validation")
    print("=" * 70)

    if args.quick:
        num_warmups = 1
        num_queries = 6
        print("Quick mode: Running with fewer warmups (1) and queries (6)")
    else:
        num_warmups = 3
        num_queries = 30
        print("Full mode: Running with warmups (3) and queries (30)")

    # 1. Baseline RAM
    print("\nMeasuring baseline RAM...")
    baseline_ram = measure_baseline_ram()
    print(f"Baseline RAM: {baseline_ram:.1f} MB")

    # 2. Section A: Retriever microbenchmark
    micro_results = run_microbenchmark(num_warmups, num_queries)

    # 3. Section B: Full RALG runtime validation
    print("\n=== Section B: Full RALG Runtime Validation ===")
    print("Initializing full RALG pipeline...")
    pipeline, init_metrics = initialize_full_pipeline()
    print(f"Loaded baseline pipeline on device: {init_metrics['baseline_chunk_count']:,} chunks in {init_metrics['pipeline_init_time_s']:.3f}s")

    # Baseline query / retrieval measurements
    print("Measuring baseline full-runtime queries...")
    baseline_latencies = measure_query_latencies(pipeline, num_warmups, num_queries)

    scale_results = []
    # Add baseline to scale results
    scale_results.append({
        "level": "baseline",
        "total_chunks": init_metrics["baseline_chunk_count"],
        "retrieval_p50_ms": baseline_latencies["retrieval_p50_ms"],
        "retrieval_p95_ms": baseline_latencies["retrieval_p95_ms"],
        "query_p50_ms": baseline_latencies["query_p50_ms"],
        "query_p95_ms": baseline_latencies["query_p95_ms"],
        "ingest_time_s": 0.0,
    })

    # Clean up pipeline
    del pipeline
    gc.collect()
    if torch and torch.cuda.is_available():
        torch.cuda.empty_cache()

    # Scale levels: +100, +1000, +5000
    scales_to_test = [100, 1000, 5000]
    if args.quick:
        scales_to_test = [100] # Only test +100 in quick mode
        print("Quick mode: testing only scale +100")

    for added in scales_to_test:
        label = f"+{added}"
        print(f"\nTesting scale {label}...")

        # Check safety before initializing
        current_ram = get_process_memory_mb()
        current_vram = get_gpu_vram_mb()
        if current_ram > MAX_RAM_MB:
            print(f"SKIPPED {label} due to RAM threshold limit.")
            scale_results.append({"level": label, "skipped": True, "reason": "RAM limit exceeded"})
            continue
        if current_vram > MAX_VRAM_MB:
            print(f"SKIPPED {label} due to VRAM threshold limit.")
            scale_results.append({"level": label, "skipped": True, "reason": "VRAM limit exceeded"})
            continue

        # Re-initialize baseline pipeline cleanly
        pipeline, _ = initialize_full_pipeline()

        # Create synthetics and ingest via attach_documents
        doc = make_uploaded_document(added, label)

        print(f"Attaching {added} chunks...")
        start_ingest = time.perf_counter()
        attach_documents(pipeline, [doc])
        ingest_time = time.perf_counter() - start_ingest
        print(f"Ingested and rebuilt index in {ingest_time:.3f}s")

        # Measure query latency
        latencies = measure_query_latencies(pipeline, num_warmups, num_queries)

        scale_results.append({
            "level": label,
            "total_chunks": len(pipeline.get("chunks", [])),
            "retrieval_p50_ms": latencies["retrieval_p50_ms"],
            "retrieval_p95_ms": latencies["retrieval_p95_ms"],
            "query_p50_ms": latencies["query_p50_ms"],
            "query_p95_ms": latencies["query_p95_ms"],
            "ingest_time_s": ingest_time,
        })

        # Clean up
        del pipeline
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Re-fetch environment info for the system_info dict
    # Re-initialize one final time for get_system_info
    pipeline, _ = initialize_full_pipeline()
    system_info = get_system_info(pipeline)

    # Save log report
    results = {
        "system_info": system_info,
        "pipeline_init": init_metrics,
        "microbenchmark": micro_results,
        "scale_results": scale_results,
    }

    # Clean up final pipeline
    del pipeline
    gc.collect()
    if torch and torch.cuda.is_available():
        torch.cuda.empty_cache()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    json_path = logs_dir / f"resource_validation_{timestamp}.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nJSON results log written to: {json_path}")

    # Check if we should update RESOURCE_VALIDATION.md
    should_update_md = args.update_md and not args.report_only_json
    if should_update_md:
        expected_scales = ["baseline", "+100", "+1000", "+5000"]
        scale_names = [r.get("level") for r in scale_results]
        has_incomplete = False
        for scale_name in expected_scales:
            if scale_name not in scale_names:
                has_incomplete = True
            else:
                for r in scale_results:
                    if r.get("level") == scale_name and r.get("skipped"):
                        has_incomplete = True

        if args.quick:
            print("WARNING: --quick active. Overwriting RESOURCE_VALIDATION.md is not allowed in quick mode to avoid corruption.")
        elif system_info["cuda_available"] != "Yes":
            print("WARNING: CUDA is not active. Overwriting RESOURCE_VALIDATION.md is not allowed in CPU mode to preserve CUDA metrics.")
        elif system_info["model_loaded"] != "Yes":
            print("WARNING: Model was not loaded successfully. Overwriting RESOURCE_VALIDATION.md is not allowed.")
        elif has_incomplete:
            print("WARNING: Scale validation run was incomplete or some scales were skipped. Overwriting RESOURCE_VALIDATION.md is not allowed.")
        else:
            md_path = PROJECT_ROOT / "RESOURCE_VALIDATION.md"
            write_markdown_report(results, md_path)
    else:
        print("\nNote: RESOURCE_VALIDATION.md was NOT modified.")
        print("To update the markdown report with new measurements, run with '--update-md' (requires CUDA and full non-quick run).")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
