#!/usr/bin/env python3
"""RALG hardware & scalability qualification (measurement only, no tuning).

Subcommands
-----------
model-inventory : measure parameter counts/dtype/size for every checkpoint
                  used or shipped alongside the active runtime, plus an
                  architecture-level count from ``SmallLMV2`` itself.
runtime-profile : initialize the real pipeline (CPU or GPU) and measure
                  startup/index-build timings, RSS/VRAM, and query latency
                  through the unmodified production code path.
scaling         : build synthetic in-memory corpora at increasing sizes and
                  measure pure-retrieval index build time, RAM, and retrieval
                  latency. Never touches fixtures or production behavior and
                  stops safely before memory exhaustion.
storage         : measured disk footprint of repo/checkpoints/data areas.

Generated outputs are small JSON summaries written under logs/.
This tool never modifies benchmark fixtures, Stage 5/6 artifacts, retrieval,
model, or scoring logic.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs"

# Fixed question set spanning factual/reasoning intents (not benchmark data).
PROFILE_QUESTIONS = [
    "What is photosynthesis?",
    "Explain how a transformer neural network works.",
    "Why do seasons change on Earth?",
    "What is the capital of France?",
    "How does HTTP transfer documents?",
    "What causes inflation in an economy?",
    "List the primary colors of light.",
    "Describe the water cycle.",
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolated percentile on sorted values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def latency_summary(latencies_ms: list[float]) -> dict:
    return {
        "n": len(latencies_ms),
        "p50_ms": round(percentile(latencies_ms, 50), 2),
        "p95_ms": round(percentile(latencies_ms, 95), 2),
        "mean_ms": round(statistics.fmean(latencies_ms), 2) if latencies_ms else 0.0,
        "max_ms": round(max(latencies_ms), 2) if latencies_ms else 0.0,
    }


def _peak_working_set_bytes() -> int:
    """Windows peak working set via GetProcessMemoryInfo (no extra deps)."""
    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_uint32),
            ("PageFaultCount", ctypes.c_uint32),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    handle = ctypes.c_void_p(ctypes.windll.kernel32.GetCurrentProcess())
    # K32GetProcessMemoryInfo lives in kernel32 on Win7+; psapi.dll otherwise.
    getters = (ctypes.windll.kernel32.K32GetProcessMemoryInfo, ctypes.windll.psapi.GetProcessMemoryInfo)
    for getter in getters:
        if getter(handle, ctypes.byref(counters), counters.cb):
            return counters.PeakWorkingSetSize
    return 0


def rss_bytes(process=None) -> int:
    try:
        import psutil
        process = process or psutil.Process()
        return process.memory_info().rss
    except ImportError:
        return 0


def dir_size_bytes(path: Path) -> int:
    total = 0
    if path.is_file():
        return path.stat().st_size
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def human(nbytes: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if nbytes < 1024 or unit == "TiB":
            return f"{nbytes:.2f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.2f} TiB"


def write_result(name: str, payload: dict) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    out = LOGS_DIR / f"{name}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Results written: {out}")
    return out


# --------------------------------------------------------------------------
# Part A: model inventory
# --------------------------------------------------------------------------

def inspect_state_dict(path: Path) -> dict:
    import torch
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(payload, dict):
        state = None
        for key in ("model_state_dict", "state_dict", "model"):
            candidate = payload.get(key)
            if isinstance(candidate, dict) and candidate:
                state = candidate
                break
        if state is None:
            state = {k: v for k, v in payload.items() if torch.is_tensor(v)}
    else:
        state = {}
    total_params = 0
    dtype_counts: Counter = Counter()
    for value in state.values():
        if torch.is_tensor(value):
            total_params += value.numel()
            dtype_counts[str(value.dtype)] += value.numel()
    try:
        relative = str(path.relative_to(ROOT))
    except ValueError:
        relative = str(path)
    return {
        "file": relative,
        "size_bytes": path.stat().st_size,
        "parameter_count": total_params,
        "dtype_distribution": dict(dtype_counts),
        "estimated_raw_param_ram_bytes": _raw_ram(state),
        "top_level_keys": sorted(payload.keys())[:12] if isinstance(payload, dict) else [],
    }


def _dtype_map():
    import torch
    return {
        "torch.float32": torch.float32, "torch.float64": torch.float64,
        "torch.float16": torch.float16, "torch.bfloat16": torch.bfloat16,
        "torch.int64": torch.int64, "torch.int32": torch.int32,
        "torch.uint8": torch.uint8, "torch.int8": torch.int8,
        "torch.bool": torch.bool,
    }


def _raw_ram(state: dict) -> int:
    import torch
    mapping = _dtype_map()
    total = 0
    for value in state.values():
        if torch.is_tensor(value):
            total += value.numel() * value.element_size()
    return total


def model_inventory() -> dict:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    import torch

    checkpoint_specs = [
        ("checkpoints/v2/reasoning_model_v1.pt", "REQUIRED",
         "Active SmallLM V2 reasoning/generation model loaded at startup"),
        ("checkpoints/embedding_model.pt", "OPTIONAL",
         "Offline index-building artifact; runtime loads prebuilt index instead"),
        ("checkpoints/instruction_model.pt", "OPTIONAL",
         "Legacy instruction-tuned variant; not loaded by active runtime"),
        ("checkpoints/final_model.pt", "OPTIONAL",
         "Historical training artifact; not loaded by active runtime"),
    ]
    entries = []
    for rel, requirement, purpose in checkpoint_specs:
        path = ROOT / rel
        if not path.exists():
            entries.append({"file": rel, "present": False, "requirement": requirement})
            continue
        info = inspect_state_dict(path)
        info.update({
            "present": True,
            "requirement": requirement,
            "purpose": purpose,
            "size_human": human(info["size_bytes"]),
            "estimated_raw_param_ram_human": human(info["estimated_raw_param_ram_bytes"]),
        })
        entries.append(info)

    # Architecture-level count from the live model definition (measured).
    arch_count = None
    try:
        from model_v2 import SmallLMV2
        model = SmallLMV2()
        arch_count = sum(p.numel() for p in model.parameters())
        arch_dtypes = Counter(str(p.dtype) for p in model.parameters())
        del model
    except Exception as exc:  # pragma: no cover - environment dependent
        arch_dtypes = {"error": str(exc)[:120]}

    qwen_dir = ROOT / "checkpoints" / "qwen2.5-1.5b-instruct"
    report = {
        "reasoning_model_architecture_parameter_count": arch_count,
        "reasoning_model_is_approx_20m_params": (
            bool(arch_count) and 15_000_000 <= arch_count <= 25_000_000
        ),
        "architecture_dtypes": dict(arch_dtypes) if isinstance(arch_dtypes, dict) else dict(arch_dtypes),
        "optional_polish_llm": {
            "path": "checkpoints/qwen2.5-1.5b-instruct",
            "present": qwen_dir.is_dir(),
            "size_bytes": dir_size_bytes(qwen_dir) if qwen_dir.is_dir() else 0,
            "requirement": "OPTIONAL",
            "note": "Qwen2.5-1.5B-Instruct answer-polish LLM; failure falls back to core answers",
        },
        "checkpoints": entries,
    }
    print(json.dumps(report, indent=2, default=str))
    return write_result("hardware_model_inventory", report)


# --------------------------------------------------------------------------
# Parts B/C: runtime profile (CPU/GPU)
# --------------------------------------------------------------------------

def runtime_profile(device_mode: str, queries_per_question: int) -> dict:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    if device_mode == "cpu":
        # Mask the GPU before torch initializes anywhere.
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    import psutil
    import torch
    from rag_chat_v2 import initialize_pipeline, answer_question
    from retriever_v2 import load_chunks, build_index
    import config as project_config

    proc = psutil.Process()
    cpu_samples: list[float] = []
    cpu_path_finding = None

    if device_mode == "cpu":
        # Qualification probe: does the UNMODIFIED production path start
        # without a GPU? Production code selects device via
        # ``torch.cuda.is_available()`` and passes ``map_location=device``
        # to torch.load itself, so forcing a truthful CPU answer lets the
        # unmodified path run end-to-end. NOTE: this torch build reports
        # ``is_available()==True`` even with an empty CUDA_VISIBLE_DEVICES,
        # so env masking alone is insufficient; we also patch the predicate.
        original_is_available = torch.cuda.is_available
        if not original_is_available():
            cpu_path_finding = {"unmodified_cpu_startup": "PASS", "note": "no GPU present"}
        else:
            try:
                t0 = time.perf_counter()
                pipeline_probe = initialize_pipeline(verbose=False)
                t_init = time.perf_counter() - t0
                cpu_path_finding = {
                    "unmodified_gpu_visible_startup_seconds": round(t_init, 2),
                    "note": "probe ran with GPU visible; real CPU path follows",
                }
            except RuntimeError as exc:
                cpu_path_finding = {"gpu_visible_probe_error": str(exc)[:200]}
            torch.cuda.is_available = lambda: False
            cpu_path_finding["harness_shim_applied"] = (
                "torch.cuda.is_available patched to False by THIS TOOL ONLY "
                "(production code then selects cpu and map_location=cpu itself)"
            )
    else:
        cpu_path_finding = {"unmodified_gpu_startup": "expected PASS"}

    t0 = time.perf_counter()
    pipeline = initialize_pipeline(verbose=True)
    t_init = time.perf_counter() - t0

    device = pipeline.get("device")
    chunk_count = len(pipeline["chunks"])

    # Retrieval-only init cost (deterministic components, separate pass).
    t0 = time.perf_counter()
    chunks_only = load_chunks(list(project_config.KNOWLEDGE_FILES))
    t_knowledge = time.perf_counter() - t0
    t0 = time.perf_counter()
    _, _ = build_index(chunks_only)
    t_index_build = time.perf_counter() - t0
    del chunks_only

    rss_idle = rss_bytes(proc)
    peak_rss = _peak_working_set_bytes()

    latencies: list[float] = []
    for round_index in range(queries_per_question):
        for question in PROFILE_QUESTIONS:
            start = time.perf_counter()
            answer_question(pipeline, question, verbose=False)
            latencies.append((time.perf_counter() - start) * 1000)
            cpu_samples.append(psutil.cpu_percent(interval=None))
    time.sleep(0.5)
    cpu_samples.append(psutil.cpu_percent(interval=1.0))

    peak_rss_queries = _peak_working_set_bytes()

    vram = {}
    if device == "cuda":
        vram = {
            "allocated_bytes": torch.cuda.memory_allocated(),
            "reserved_bytes": torch.cuda.memory_reserved(),
            "allocated_human": human(torch.cuda.memory_allocated()),
            "reserved_human": human(torch.cuda.memory_reserved()),
            "vram_total_human": human(torch.cuda.get_device_properties(0).total_memory),
        }

    report = {
        "mode": device_mode,
        "pipeline_device_selected": device,
        "corpus_chunks": chunk_count,
        "cpu_only_path_finding": cpu_path_finding,
        "timings_seconds": {
            "pipeline_init_total": round(t_init, 2),
            "knowledge_load_only": round(t_knowledge, 2),
            "index_build_only": round(t_index_build, 2),
        },
        "memory": {
            "idle_rss_after_init_bytes": rss_idle,
            "idle_rss_after_init_human": human(rss_idle),
            "peak_working_set_bytes": peak_rss_queries or peak_rss,
            "peak_working_set_human": human(max(peak_rss, peak_rss_queries)),
        },
        "cpu_utilization_avg_pct": round(statistics.fmean(cpu_samples), 1) if cpu_samples else None,
        "query_latency": latency_summary(latencies),
        "queries_run": len(latencies),
        "vram": vram,
    }
    print(json.dumps(report, indent=2, default=str))
    return write_result(f"hardware_runtime_{device_mode}", report)


# --------------------------------------------------------------------------
# Part D: scaling
# --------------------------------------------------------------------------

def _synthetic_chunks(base_text: str, count: int, chunk_words: int = 90) -> list[str]:
    """Deterministic synthetic corpus cycled from existing knowledge text."""
    words = base_text.split()
    if not words:
        raise ValueError("base text is empty")
    chunks = []
    cursor = 0
    for i in range(count):
        piece = []
        while len(piece) < chunk_words:
            piece.append(words[cursor % len(words)])
            cursor += 1
        chunks.append(f"synthetic doc {i}: " + " ".join(piece))
    return chunks


def scaling(sizes: list[int], max_rss_fraction: float = 0.8) -> dict:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    import psutil
    from retriever_v2 import build_index
    from retriever_hybrid import retrieve

    total_ram = psutil.virtual_memory().total
    rss_limit = total_ram * max_rss_fraction
    data_path = ROOT / "data" / "wikitext_v2.txt"
    base_text = data_path.read_text(encoding="utf-8-sig", errors="replace")[:2_000_000]

    results = []
    stopped_reason = None
    baseline_rss = rss_bytes()
    for size in sizes:
        current_rss = rss_bytes()
        # Rough linear projection from the last measured point as a guard.
        if results:
            last = results[-1]
            projected = current_rss + (last["steady_state_rss_bytes"] - baseline_rss) \
                * (size / last["chunks"])
            if projected > rss_limit:
                stopped_reason = (
                    f"stopped before {size} chunks: projected RSS "
                    f"{human(projected)} exceeds {max_rss_fraction:.0%} of total RAM"
                )
                break
        chunks = _synthetic_chunks(base_text, size)
        t0 = time.perf_counter()
        index, df = build_index(chunks)
        t_build = time.perf_counter() - t0
        steady = rss_bytes()
        latencies = []
        for question in PROFILE_QUESTIONS[:6]:
            start = time.perf_counter()
            retrieve(question, chunks, index, df)
            latencies.append((time.perf_counter() - start) * 1000)
        entry = {
            "chunks": size,
            "index_build_seconds": round(t_build, 2),
            "steady_state_rss_bytes": steady,
            "steady_state_rss_human": human(steady),
            "peak_working_set_human": human(_peak_working_set_bytes()),
            "retrieval_latency": latency_summary(latencies),
        }
        print(json.dumps(entry))
        results.append(entry)
        del chunks, index, df
        if steady > rss_limit:
            stopped_reason = (
                f"stopped after {size} chunks: steady RSS {human(steady)} "
                f"exceeded {max_rss_fraction:.0%} of total RAM"
            )
            break

    report = {
        "mode": "retrieval-index-scaling (synthetic corpus, production retriever unmodified)",
        "results": results,
        "largest_successfully_tested_chunks": max((r["chunks"] for r in results), default=0),
        "stopped_reason": stopped_reason,
        "rss_limit_human": human(rss_limit),
    }
    print(json.dumps(report, indent=2))
    return write_result("hardware_scaling", report)


# --------------------------------------------------------------------------
# Part E: storage
# --------------------------------------------------------------------------

def storage() -> dict:
    areas = {
        "repo_software_incl_git": ROOT / ".git",
        "repo_software_excl_git_src_docs_scripts_evaluation": ROOT / "src",
        "checkpoints_total": ROOT / "checkpoints",
        "checkpoints_required_reasoning_v1": ROOT / "checkpoints" / "v2",
        "checkpoints_optional_embedding": ROOT / "checkpoints" / "embedding_model.pt",
        "checkpoints_optional_qwen_polish": ROOT / "checkpoints" / "qwen2.5-1.5b-instruct",
        "data_tokenizer": ROOT / "data" / "tokenizer_v2.json",
        "source_documents_stage5_rfcs": ROOT / "evaluation" / "stage5_documents",
        "derived_runtime_data": ROOT / "logs",
    }
    report = {}
    for label, path in areas.items():
        exists = path.exists()
        size = dir_size_bytes(path) if exists else 0
        report[label] = {"exists": exists, "bytes": size, "human": human(size)}
    print(json.dumps(report, indent=2))
    return write_result("hardware_storage_measured", report)


# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("model-inventory")
    profile = sub.add_parser("runtime-profile")
    profile.add_argument("--device", choices=["cpu", "gpu"], default="cpu")
    profile.add_argument("--queries-per-question", type=int, default=3)
    scaling_parser = sub.add_parser("scaling")
    scaling_parser.add_argument("--sizes", type=int, nargs="+",
                                default=[10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000])
    scaling_parser.add_argument("--max-rss-fraction", type=float, default=0.8)
    sub.add_parser("storage")
    args = parser.parse_args()

    if args.command == "model-inventory":
        model_inventory()
    elif args.command == "runtime-profile":
        runtime_profile(args.device, args.queries_per_question)
    elif args.command == "scaling":
        scaling(args.sizes, args.max_rss_fraction)
    else:
        storage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
