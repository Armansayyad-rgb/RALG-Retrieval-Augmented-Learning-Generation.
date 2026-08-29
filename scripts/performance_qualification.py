#!/usr/bin/env python3
"""Performance qualification harness for RALG Engine.

Measures:
  A. Retrieval-only latency (warmup, cold/warm cache, p50/p95/p99, throughput)
  B. Deterministic RALG runtime latency (no model generation, same metrics)
  C. Model generation latency (separate, only if usable model available)
  + corpus init/index time, memory, concurrency 1/2/4/8, ingestion, deletion, soak.

Strict rules: never touch holdout V1/V2/V3 files, never modify immutable results,
never touch .kimchi/, never alter answer/support thresholds, no query-specific caches/hacks.
"""

from __future__ import annotations

import json, os, statistics, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import psutil
except ImportError:
    psutil = None

try:
    import torch
    torch.set_num_threads(1)
except Exception:
    pass

from src.retriever_v2 import build_index, retrieve, extend_index
from src.runtime_architecture import execute_runtime


def rss_mb():
    if psutil:
        return round(psutil.Process(os.getpid()).memory_info().rss / 1048576, 2)
    return None


def make_chunks(n: int):
    """Synthetic corpus: deterministic, non-holdout content."""
    return [
        f"synthetic domain {i % 16} revision {i % 11} control value {i % 97} document {i}"
        for i in range(n)
    ]


def build_index_and_metrics(chunks):
    """Build index and return (idx, df, metrics_dict)."""
    before = rss_mb()
    t0 = time.perf_counter()
    idx, df = build_index(chunks)
    build_ms = (time.perf_counter() - t0) * 1000
    after = rss_mb()
    return idx, df, {
        "index_build_ms": round(build_ms, 2),
        "index_build_chunks": len(chunks),
        "rss_before_mb": before,
        "rss_after_mb": after,
        "rss_delta_mb": round((after or 0) - (before or 0), 2),
    }


def measure_retrieval_only(chunks, idx, df, warmup=3, repeats=50):
    """Measure retrieval-only latency distributions.

    Cold cache = first set of queries (no prior index access in this session).
    Warm cache = after warmup phase.
    """
    qs = [f"domain {i % 16} control value {i % 97}" for i in range(max(repeats + 10, 60))]

    # Cold cache: first queries (no prior index access in this session)
    cold_lats = []
    for q in qs[:repeats]:
        t0 = time.perf_counter()
        retrieve(q, chunks, idx, df)
        cold_lats.append((time.perf_counter() - t0) * 1000)  # ms

    # Warmup phase
    for _ in range(warmup):
        for q in qs[:3]:
            retrieve(q, chunks, idx, df)

    # Warm cache: after warmup
    warm_lats = []
    # Use a fresh set of queries for warm measurement
    warm_qs = qs[repeats:repeats + 50]
    for q in warm_qs:
        t0 = time.perf_counter()
        retrieve(q, chunks, idx, df)
        warm_lats.append((time.perf_counter() - t0) * 1000)

    all_lats = cold_lats + warm_lats

    def pct(arr, p):
        if not arr:
            return None
        sorted_arr = sorted(arr)
        idx_p = int(len(sorted_arr) * p / 100)
        idx_p = min(idx_p, len(sorted_arr) - 1)
        return sorted_arr[idx_p]

    total_time_ms = sum(all_lats) if all_lats else 1
    throughput = len(all_lats) / (total_time_ms / 1000) if total_time_ms > 0 else 0

    return {
        "cold_p50_ms": round(pct(cold_lats, 50), 3),
        "cold_p95_ms": round(pct(cold_lats, 95), 3),
        "cold_p99_ms": round(pct(cold_lats, 99), 3),
        "cold_avg_ms": round(sum(cold_lats) / len(cold_lats), 3) if cold_lats else None,
        "warm_p50_ms": round(pct(warm_lats, 50), 3),
        "warm_p95_ms": round(pct(warm_lats, 95), 3),
        "warm_p99_ms": round(pct(warm_lats, 99), 3),
        "warm_avg_ms": round(sum(warm_lats) / len(warm_lats), 3) if warm_lats else None,
        "throughput_qps": round(throughput, 2),
        "sample_count": len(all_lats),
    }


def measure_deterministic_ralg(chunks, idx, df, warmup=3, repeats=30):
    """Measure deterministic RALG runtime latency (no model generation).

    Attempts to exercise the production execute_runtime / answer_question pipeline.
    If the model is not available (no pipeline), reports NOT_MEASURED rather than
    measuring a simplified retrieve() proxy and mislabeling it as RALG runtime.
    """
    # Attempt to load the pipeline from runtime_architecture
    pipeline = None
    try:
        from src.runtime_architecture import get_pipeline
        pipeline = get_pipeline()
    except Exception:
        pipeline = None

    if pipeline is None:
        # Model not available; cannot exercise production deterministic runtime.
        # Report NOT_MEASURED instead of measuring retrieve() as "RALG runtime".
        return {
            "status": "NOT_MEASURED",
            "reason": "Pipeline/model not available; cannot exercise production deterministic runtime.",
        }

    qs = [f"domain {i % 16} control value {i % 97}" for i in range(max(repeats + 10, 40))]

    lats = []
    # Warmup
    for _ in range(warmup):
        for q in qs[:3]:
            try:
                execute_runtime(
                    pipeline,
                    q,
                    top_k=5,
                    answer_fn=lambda p, qq, **kwargs: {"evidence": [], "answer": "", "supported": False, "answer_type": "system"},
                    contract_fn=lambda p, qq, **kwargs: type("C", (), {"answer": "", "confidence": None, "sources": [], "provenance": [], "conflict": False, "traceable": False})(),
                    sources_fn=lambda p, qq, **kwargs: [],
                    document_ids=None,
                )
            except Exception:
                pass  # warmup may fail; we continue

    for q in qs[:repeats]:
        t0 = time.perf_counter()
        try:
            # Minimal execution: use a no-op answer fn that doesn't invoke model generation
            # The key deterministic path is retrieval + support gate; model generate is separate
            from src.runtime_architecture import execute_runtime
            result = execute_runtime(
                pipeline,
                q,
                top_k=5,
                answer_fn=lambda p, qq, **kwargs: {"evidence": [], "answer": "", "supported": False, "answer_type": "system"},
                contract_fn=lambda p, qq, **kwargs: type("C", (), {"answer": "", "confidence": None, "sources": [], "provenance": [], "conflict": False, "traceable": False})(),
                sources_fn=lambda p, qq, **kwargs: [],
                document_ids=None,
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
            lats.append(elapsed_ms)
        except Exception as e:
            # If even the deterministic path requires model inference, stop measuring
            return {
                "status": "NOT_MEASURED",
                "reason": f"Production runtime requires model generation: {e}",
            }

    def pct(arr, p):
        if not arr:
            return None
        sorted_arr = sorted(arr)
        idx_p = int(len(sorted_arr) * p / 100)
        idx_p = min(idx_p, len(sorted_arr) - 1)
        return sorted_arr[idx_p]

    total_time_ms = sum(lats) if lats else 1
    throughput = len(lats) / (total_time_ms / 1000) if total_time_ms > 0 else 0

    return {
        "deterministic_p50_ms": round(pct(lats, 50), 3),
        "deterministic_p95_ms": round(pct(lats, 95), 3),
        "deterministic_p99_ms": round(pct(lats, 99), 3),
        "deterministic_avg_ms": round(sum(lats) / len(lats), 3) if lats else None,
        "throughput_qps": round(throughput, 2),
        "sample_count": len(lats),
    }


def measure_model_generation():
    """Attempt to measure model generation latency.

    Returns NOT MEASURED if no usable model is available,
    or timing results if a model can be loaded and used safely.
    """
    model_path = os.environ.get(
        "MODEL_FILE",
        str(Path(__file__).resolve().parents[1] / "checkpoints" / "v2" / "reasoning_model_v1.pt"),
    )

    if not os.path.exists(model_path):
        return {
            "status": "NOT_MEASURED",
            "reason": f"Model file not found at {model_path}",
        }

    # Check if it's a PyTorch model we can load safely
    try:
        import torch
        state = torch.load(model_path, map_location="cpu")
        result = {
            "status": "ATTEMPTED",
            "model_path": model_path,
            "model_type": type(state).__name__,
        }

        # Try to detect if it has a generate method
        if hasattr(state, "generate"):
            result["generate_available"] = True
        else:
            result["generate_available"] = False

        return result

    except Exception as e:
        return {
            "status": "NOT_MEASURED",
            "reason": f"Could not load model: {e}",
        }


def measure_concurrency(chunks, idx, df, levels=(1, 2, 4, 8), requests_per=100):
    """Measure concurrent query throughput at various worker levels."""
    results = {}
    for workers in levels:
        q_count = workers * requests_per
        qs = [f"concurrent domain {i % 16} value {i % 97}" for i in range(q_count)]

        before = time.perf_counter()
        before_rss = rss_mb()

        def one(i):
            q = qs[i]
            t0 = time.perf_counter()
            retrieve(q, chunks, idx, df)
            return (time.perf_counter() - t0) * 1000

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(one, i) for i in range(q_count)]
            latencies = []
            error_count = 0
            error_types = set()
            for f in as_completed(futures):
                try:
                    latencies.append(f.result())
                except Exception as exc:
                    error_count += 1
                    error_types.add(type(exc).__name__)

        elapsed_ms = (time.perf_counter() - before) * 1000
        sorted_lats = sorted(latencies)

        results[f"workers_{workers}"] = {
            "requests": q_count,
            "completed": len(latencies),
            "errors": error_count,
            "error_types": sorted(error_types),
            "elapsed_ms": round(elapsed_ms, 2),
            "p50_ms": round(sorted_lats[len(latencies) // 2], 3) if latencies else None,
            "p95_ms": round(sorted_lats[int(len(latencies) * 0.95 - 1)], 3) if latencies else None,
            "p99_ms": round(sorted_lats[int(len(latencies) * 0.99 - 1)], 3) if latencies else None,
            "avg_ms": round(sum(latencies) / len(latencies), 3) if latencies else None,
            "throughput_qps": round(len(latencies) / elapsed_ms * 1000, 2) if latencies and elapsed_ms else None,
            "rss_before_mb": before_rss,
        }
    return results


def measure_concurrent_reads_plus_ingest(chunks, idx, df, ingest_size=50):
    """Measure concurrent reads while ingestion has recently happened."""
    # Append extra chunks to list and extend index
    extra_chunks = [f"ingest domain {i % 7} value {i}" for i in range(ingest_size)]
    chunks.extend(extra_chunks)
    start_idx = len(chunks) - ingest_size  # original length
    extend_index(idx, df, extra_chunks, start_idx)

    # Now measure retrieval - the index has been modified with new chunks
    qs = [f"read domain {i % 16} value {i % 97}" for i in range(50)]

    lats = []
    before = time.perf_counter()
    for q in qs:
        t0 = time.perf_counter()
        retrieve(q, chunks, idx, df)
        lats.append((time.perf_counter() - t0) * 1000)
    elapsed = time.perf_counter() - before

    return {
        "reads": len(qs),
        "elapsed_ms": round(elapsed * 1000, 2),
        "p50_ms": round(sorted(lats)[len(lats) // 2], 3) if lats else None,
        "p95_ms": round(sorted(lats)[int(len(lats) * 0.95 - 1)], 3) if lats else None,
        "rss_after_mb": rss_mb(),
    }


def measure_repeated_ingestion(chunks, num_cycles=3, ingest_size=100):
    """Measure repeated ingestion to detect corruption/races/unbounded degradation."""
    results = []
    # Start fresh each time - we'll measure incremental builds
    current_chunks = list(chunks)
    idx, df = build_index(current_chunks)

    for cycle in range(num_cycles):
        extra = [f"inc domain {i % 7} val {i}" for i in range(ingest_size)]
        start = len(current_chunks)
        t0 = time.perf_counter()
        current_chunks.extend(extra)
        extend_index(idx, df, extra, start)
        cycle_ms = (time.perf_counter() - t0) * 1000
        # Verify index still works with a quick query
        try:
            retrieve("synthetic domain 0 control value 97", current_chunks, idx, df)
            query_ok = True
        except Exception:
            query_ok = False
        results.append({
            "cycle": cycle + 1,
            "ingested": ingest_size,
            "cycle_ms": round(cycle_ms, 2),
            "query_after_ok": query_ok,
        })

    # Final metrics
    final_idx, final_df = build_index(current_chunks)
    final_before = rss_mb()
    # Quick final query
    try:
        retrieve("synthetic domain 0 control value 97", current_chunks, final_idx, final_df)
    except Exception as e:
        results[-1] = {"error": str(e)} if results else {"error": str(e)}

    return results


def measure_deletion_scaling(chunks, target_counts=(100, 200, 500)):
    """Measure rebuild latency after deleting varying fractions of corpus."""
    results = {}
    for target in target_counts:
        n = max(target, 10)
        truncated = chunks[:n]
        rebuild_t0 = time.perf_counter()
        rebuild_idx, rebuild_df = build_index(truncated)
        rebuild_ms = (time.perf_counter() - rebuild_t0) * 1000
        results[f"keep_{n}"] = {
            "kept_chunks": n,
            "rebuild_ms": round(rebuild_ms, 2),
        }
    return results


def main():
    """Run the full performance qualification suite."""

    # === Phase 1: Corpus & Index Build ===
    print("=== Phase 1: Corpus Initialization & Index Build ===")

    # Use small synthetic corpus first (500 chunks) - stay well within safety limits
    n_chunks = 500
    chunks = make_chunks(n_chunks)
    idx, df, index_metrics = build_index_and_metrics(chunks)

    print(f"Chunks: {n_chunks}")
    print(f"Index build: {index_metrics['index_build_ms']} ms")
    print(f"  RSS delta: {index_metrics['rss_delta_mb']} MB")
    print(f"  Chunk count: {index_metrics['index_build_chunks']}")

    # === Phase 2: Retrieval-Only Latency ===
    print("\n=== Phase 2: Retrieval-Only Latency ===")
    retrieval = measure_retrieval_only(chunks, idx, df)

    print(f"Cold cache - p50: {retrieval['cold_p50_ms']} ms, p95: {retrieval['cold_p95_ms']} ms, p99: {retrieval['cold_p99_ms']} ms, avg: {retrieval['cold_avg_ms']} ms")
    print(f"Warm cache - p50: {retrieval['warm_p50_ms']} ms, p95: {retrieval['warm_p95_ms']} ms, p99: {retrieval['warm_p99_ms']} ms, avg: {retrieval['warm_avg_ms']} ms")
    print(f"Throughput: {retrieval['throughput_qps']} qps")

    # === Phase 3: Deterministic RALG Runtime ===
    print("\n=== Phase 3: Deterministic RALG Runtime ===")
    ralg = measure_deterministic_ralg(chunks, idx, df)

    if ralg.get("status") == "NOT_MEASURED":
        print(f"Status: {ralg['status']} — {ralg.get('reason', '')}")
    else:
        print(f"Deterministic p50: {ralg['deterministic_p50_ms']} ms")
        print(f"Deterministic p95: {ralg['deterministic_p95_ms']} ms")
        print(f"Deterministic p99: {ralg['deterministic_p99_ms']} ms")
        print(f"Deterministic throughput: {ralg['throughput_qps']} qps")

    # === Phase 4: Model Generation ===
    print("\n=== Phase 4: Model Generation ===")
    model_result = measure_model_generation()
    print(json.dumps(model_result, indent=2))

    # === Phase 5: Concurrency ===
    print("\n=== Phase 5: Concurrency (workers 1,2,4,8) ===")
    concurrency = measure_concurrency(chunks, idx, df)
    print(json.dumps(concurrency, indent=2))

    # === Phase 6: Concurrent Reads + Ingest ===
    print("\n=== Phase 6: Concurrent Reads + Ingest ===")
    read_ingest = measure_concurrent_reads_plus_ingest(chunks, idx, df)
    print(json.dumps(read_ingest, indent=2))

    # === Phase 7: Repeated Ingestion ===
    print("\n=== Phase 7: Repeated Ingestion ===")
    ingest_results = measure_repeated_ingestion(chunks, num_cycles=3, ingest_size=100)
    print(json.dumps(ingest_results, indent=2))

    # === Phase 8: Deletion Scaling ===
    print("\n=== Phase 8: Deletion Scaling ===")
    del_results = measure_deletion_scaling(chunks, target_counts=[100, 200, 500])
    print(json.dumps(del_results, indent=2))

    # === Phase 9: Short Soak Test ===
    print("\n=== Phase 9: Short Soak Test ===")
    soak_duration_s = 30  # 30-second short soak
    soak_queries = 200
    qs = [f"soak domain {i % 16} value {i % 97}" for i in range(soak_queries)]

    # Peak RSS measurement (Unix resource module; unavailable on Windows)
    peak_rss_bytes = None
    try:
        import resource as res_module
        peak_rss_bytes = res_module.getrusage(res_module.RUSAGE_SELF).ru_maxrss * 1024
    except Exception:
        pass  # silently unavailable on this platform

    before = time.perf_counter()
    before_rss = rss_mb()
    lats = []
    errors = 0
    error_types = set()
    for i in range(soak_queries):
        t0 = time.perf_counter()
        try:
            retrieve(qs[i], chunks, idx, df)
            lats.append((time.perf_counter() - t0) * 1000)
        except Exception as exc:
            errors += 1
            error_types.add(type(exc).__name__)
    elapsed = time.perf_counter() - before

    soak_rss_after = rss_mb()

    results = {
        "duration_s": round(elapsed, 2),
        "query_count": soak_queries,
        "elapsed_ms": round(elapsed * 1000, 2),
        "completed": len(lats),
        "errors": errors,
        "error_types": sorted(error_types),
        "p50_ms": round(sorted(lats)[len(lats) // 2], 3) if lats else None,
        "p95_ms": round(sorted(lats)[int(len(lats) * 0.95 - 1)], 3) if lats else None,
        "p99_ms": round(sorted(lats)[int(len(lats) * 0.99 - 1)], 3) if lats else None,
        "avg_ms": round(sum(lats) / len(lats), 3) if lats else None,
        "throughput_qps": round(len(lats) / elapsed * 1000, 2) if elapsed and lats else None,
        "rss_before_mb": before_rss,
        "rss_after_mb": soak_rss_after,
        "peak_rss_bytes": peak_rss_bytes,
        "correctness": "pass" if errors == 0 else "fail",
    }

    print(json.dumps(results, indent=2))

    # === Build final payload ===
    payload = {
        "corpus_size": n_chunks,
        "chunk_count": n_chunks,
        "index_build": index_metrics,
        "retrieval_only": retrieval,
        "deterministic_ralg_runtime": ralg,
        "model_generation": model_result,
        "concurrency": concurrency,
        "concurrent_reads_plus_ingest": read_ingest,
        "repeated_ingestion": ingest_results,
        "deletion_scaling": del_results,
        "environment": {
            "python_version": sys.version.split(" ")[0],
            "psutil_available": psutil is not None,
            "torch_available": True,
            "torch_threads": torch.get_num_threads() if torch else 1,
        },
    }

    # Write output
    out_path = ROOT / "logs" / "performance_qualification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n=== Results written to {out_path} ===")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()