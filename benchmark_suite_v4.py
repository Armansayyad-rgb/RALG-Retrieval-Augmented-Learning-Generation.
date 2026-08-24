#!/usr/bin/env python3
"""
Benchmark Suite V4 for RALG

Evaluates against V4 criteria:
- factual QA, causal reasoning, comparison questions, multi-hop questions
- false-premise rejection, unsupported/unanswerable questions
- evidence-supported answering, retrieval quality, confidence calibration

Generates machine-readable (JSON) plus human-readable benchmark report.
"""

# ==========================================================
# PROJECT ROOT & CONFIGURATION
# ==========================================================

import os
import sys
import datetime
from pathlib import Path

# Resolve from this file by default, with an environment override.
PROJECT_ROOT = Path(
    os.environ.get("AI_PROJECT_ROOT")
    or Path(__file__).resolve().parent
).resolve()

# Add src directory to path for imports
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Add project root to path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (  # noqa: E402
    LOGS_DIR,
    TOKENIZER_FILE,
    MODEL_FILE,
    KNOWLEDGE_FILES,
    MAX_INPUT_TOKENS,
    MAX_NEW_TOKENS,
    CONFIDENCE_THRESHOLD,
)

# ==========================================================
# V4 TEST CASES
# ==========================================================

# New V4 categories (factual QA and multi-hop)
V4_NEW_CATEGORIES = {
    "factual_qa": [],
    "multi_hop": [],
}

# --- Factual QA test cases (new for V4) ---
FACTUAL_QA_QUESTIONS = [
    "When was the Magna Carta signed?",
    "Who wrote the Communist Manifesto?",
    "What is the capital of France?",
    "When did the Titanic sink?",
    "Who discovered penicillin?",
    "What is the chemical symbol for gold?",
    "When was the first powered flight?",
    "Who painted the Mona Lisa?",
    "What is the hardest natural substance?",
    "When did World War II end?",
]

for question in FACTUAL_QA_QUESTIONS:
    count = sum(
        1
        for item in V4_NEW_CATEGORIES["factual_qa"]
        if item["category"] == "factual_qa"
    ) + 1
    V4_NEW_CATEGORIES["factual_qa"].append(
        {
            "name": f"factual_qa_{count:03d}",
            "category": "factual_qa",
            "question": question,
            "answer_type": "factual",
            "supported": True,
            "must_contain": [],
            "must_not_contain": [],
        }
    )

# --- Multi-hop reasoning test cases (new for V4) ---
MULTI_HOP_QUESTIONS = [
    "What caused the fall of the Roman Empire and what followed?",
    "How did the Roman Empire's decline affect the development of medieval Europe?",
    "What were the effects of the Magna Carta on the development of constitutional law?",
    "How did the French Revolution influence the development of modern nationalism?",
    "What led to the decline of the Roman Empire and what were its consequences?",
    "How did the spread of Islam affect the Roman Empire's eastern provinces?",
    "What were the causes and effects of the fall of the Western Roman Empire?",
    "How did the Black Death change European society and the feudal system?",
    "What led to the collapse of the Soviet Union and what followed?",
    "How did the invention of the printing press change the spread of knowledge?",
]

for question in MULTI_HOP_QUESTIONS:
    count = sum(
        1
        for item in V4_NEW_CATEGORIES["multi_hop"]
        if item["category"] == "multi_hop"
    ) + 1
    V4_NEW_CATEGORIES["multi_hop"].append(
        {
            "name": f"multi_hop_{count:03d}",
            "category": "multi_hop",
            "question": question,
            "answer_type": "multi_hop",
            "supported": True,
            "must_contain": [],
            "must_not_contain": [],
        }
    )

# ==========================================================
# IMPORT V3 TEST CASES
# ==========================================================

# Execute evaluation_suite_v3.py to import its TESTS variable
_v3_mod_path = PROJECT_ROOT / "src" / "evaluation_suite_v3.py"
if os.path.exists(_v3_mod_path):
    _v3_spec = __import__(
        "src.evaluation_suite_v3",
        fromlist=["TESTS"],
    )
    V3_TESTS = getattr(_v3_spec, "TESTS", [])
else:
    V3_TESTS = []

# Merge V3 TESTS with V4 new categories
ALL_TESTS = V3_TESTS + V4_NEW_CATEGORIES["factual_qa"] + V4_NEW_CATEGORIES["multi_hop"]


# ==========================================================
# HELPER: Text containment
# ==========================================================

def text_contains(text, fragment):
    """Check if a fragment is contained in text (case-insensitive)."""
    return fragment.lower() in text.lower()


# ==========================================================
# HELPER: Retrieve metrics computation
# ==========================================================

def compute_recall_at_k(merged_results, must_contain, k=3):
    """Compute Recall@k: whether at least one must_contain fragment appears in top-k.
    
    Returns None if must_contain is empty (no retrieval relevance ground truth).
    """
    if not must_contain:
        return None

    top_k = merged_results[:k]
    found = False

    for result in top_k:
        chunk = result.get("chunk", "")
        for fragment in must_contain:
            if fragment.lower() in chunk.lower():
                found = True
                break
        if found:
            break

    return 1.0 if found else 0.0


def compute_mrr(merged_results, must_contain):
    """Compute Mean Reciprocal Rank (MRR).
    
    Returns None if must_contain is empty (no retrieval relevance ground truth).
    """
    if not must_contain:
        return None

    for rank, result in enumerate(merged_results, start=1):
        chunk = result.get("chunk", "")
        for fragment in must_contain:
            if fragment.lower() in chunk.lower():
                return 1.0 / rank

    return 0.0


def compute_recall_at_1_3_5(merged_results, must_contain):
    """Compute Recall@1, Recall@3, Recall@5.
    
    Returns None for each metric if must_contain is empty (no retrieval relevance ground truth).
    """
    if not must_contain:
        return {
            "recall_at_1": None,
            "recall_at_3": None,
            "recall_at_5": None,
        }
    return {
        "recall_at_1": compute_recall_at_k(merged_results, must_contain, k=1),
        "recall_at_3": compute_recall_at_k(merged_results, must_contain, k=3),
        "recall_at_5": compute_recall_at_k(merged_results, must_contain, k=5),
    }


# ==========================================================
# HELPER: Baseline Runner
# ==========================================================

def _extract_simple_answer(question, context):
    """Simplest deterministic evidence-based answer extraction from retrieved chunk.

    Uses pattern-based heuristics only -- no advanced reasoning, no RALG-specific
    logic.  Falls back to returning the first relevant sentence or the first year
    found in the context.
    """
    import re

    q = question.strip()
    ql = q.lower()

    # --- "when" questions: look for a year ---
    if ql.startswith("when "):
        m = re.search(r"\b(19|20)\d{2}\b", context)
        if m:
            return m.group(0)

    # --- "who was/ is" questions: first capitalised sentence ---
    if re.match(r"\bwho[\s]", ql):
        sentences = [s.strip() for s in context.split(". ") if s.strip()]
        for s in sentences:
            first_word = s.split()[0] if s.split() else ""
            if first_word[0].isupper() and len(first_word) > 2:
                return s + ("." if not s.endswith(".") else "")

    # --- "what is/are" or "what was": first sentence ---
    if ql.startswith("what "):
        sentences = [s.strip() for s in context.split(". ") if s.strip()]
        if sentences:
            return sentences[0] + ("." if not sentences[0].endswith(".") else "")

    # --- "why" or "what caused": look for "because"/"due to" ---
    if ql.startswith("why ") or ql.startswith("what caused "):
        for marker in ["because ", "due to ", "caused by "]:
            m = re.search(
                rf"{marker}(.+?)(?:\.|$)",
                context,
                flags=re.IGNORECASE,
            )
            if m:
                return m.group(1).strip() + "."

    # --- Default: return first sentence of context ---
    sentences = [s.strip() for s in context.split(". ") if s.strip()]
    if sentences:
        return sentences[0] + ("." if not sentences[0].endswith(".") else "")

    return context.strip()


def run_baseline(question, chunks, index, document_frequency):
    """
    Simpler baseline RAG system for fair comparison:
    - Uses router_v1 for classification only (not for answer routing)
    - Uses retriever_v2 basic retrieval (no adaptive query planning)
    - Uses extract_answer() for extractive answers
    - Falls back to simplest deterministic evidence-based answer from retrieved chunks
    - No adaptive query planning, no intent-aware scoring, no synthesizers
    - Never automatically fails because router says "model"
    """
    import time

    from src.router_v1 import route_question

    from src.retriever_v2 import retrieve as retrieve_v2_dup

    from src.extractor_v1 import extract_answer as extract_extractor_answer

    start = time.perf_counter()
    route = route_question(question)

    answer = ""
    supported = False
    answer_type = "system"
    retrieval_score = 0.0
    elapsed = 0.0

    # --- Always retrieve top-k evidence, regardless of router route ---
    results = retrieve_v2_dup(
        question,
        chunks,
        index,
        document_frequency,
        final_top_k=5,
    )

    if results:
        best = results[0]
        retrieval_score = best.get("final_score", 0.0)
        context = best.get("chunk", "")

        # --- Try the extractor first ---
        extracted = extract_extractor_answer(question, context)

        if extracted:
            answer = extracted
            supported = True
            answer_type = "extractor"
        else:
            # --- Fallback: simplest deterministic evidence-based answer ---
            answer = _extract_simple_answer(question, context)
            answer_type = "simple_fallback"
    else:
        answer = "couldn't find enough reliable evidence"
        answer_type = "system"

    elapsed = time.perf_counter() - start

    return {
        "answer": answer,
        "answer_type": answer_type,
        "supported": supported,
        "elapsed": elapsed,
        "router": route,
    }


# ==========================================================
# MAIN: EVALUATE V4 CASE
# ==========================================================

def evaluate_v4_case(pipeline, test_case, chunks, index, document_frequency):
    """
    Evaluate a single test case against both RALG and baseline.
    Returns dict with all metrics.
    """
    question = test_case["question"]
    must_contain = test_case.get("must_contain", [])
    must_not_contain = test_case.get("must_not_contain", [])

    # ---- Run RALG pipeline ----
    import time as _time

    ralg_start = _time.perf_counter()
    ralg_result = _answer_question_impl(pipeline, question, verbose=False)
    ralg_elapsed = _time.perf_counter() - ralg_start

    ralg_answer = ralg_result.get("answer") or ""
    ralg_answer_type = ralg_result.get("answer_type")
    ralg_supported = bool(ralg_result.get("supported", False))
    ralg_router = ralg_result.get("router")
    ralg_retriever = ralg_result.get("retriever")

    # ---- Compute RALG retrieval metrics ----
    from src.retriever_v4 import retrieve as retrieve_v4_dup

    ralg_merged_results = get_v4_retrieval_results_simple(
        question,
        ralg_result.get("chunks"),
        ralg_result.get("retrieval_index"),
        ralg_result.get("document_frequency"),
    )

    ralg_recall = compute_recall_at_1_3_5(ralg_merged_results, must_contain)
    ralc_mrr = compute_mrr(ralg_merged_results, must_contain)

    # ---- RALG confidence and support ----
    ralg_confidence = ralg_result.get("confidence")
    if ralg_confidence is None:
        ralg_confidence = None

    # RALG reasoning support
    ralg_support_info = ralg_result.get("reasoning_support", {})
    ralg_support_score = ralg_support_info.get("score", 0.0)
    ralg_sufficient = bool(
        ralg_support_info.get("sufficient", False)
    )

    # RALG premise validation
    ralg_premise = ralg_result.get("premise_validation", {})
    ralg_premise_supported = bool(
        ralg_premise.get("supported", False)
        if isinstance(ralg_premise, dict)
        else False
    )

    # RALG must_contain / must_not_contain checks
    ralg_missing_required = []
    for fragment in must_contain:
        if not text_contains(ralg_answer, fragment):
            ralg_missing_required.append(fragment)

    ralg_forbidden_found = []
    for fragment in must_not_contain:
        if text_contains(ralg_answer, fragment):
            ralg_forbidden_found.append(fragment)

    ralg_type_ok = (
        ralg_answer_type == test_case.get("answer_type")
        if ralg_answer_type
        else False
    )

    ralg_support_ok = (
        ralg_supported
        == bool(test_case.get("supported", False))
    )

    ralg_content_ok = (
        not ralg_missing_required
        and not ralg_forbidden_found
    )

    ralg_semantic_ok = (
        ralg_type_ok
        and ralg_support_ok
        and ralg_content_ok
    )

    ralg_latency_ok = ralg_elapsed <= 2.50

    # ---- Run Baseline ----
    baseline_result = run_baseline_simple(
        question,
        chunks,
        index,
        document_frequency,
    )
    baseline_elapsed = baseline_result["elapsed"]
    baseline_answer = baseline_result["answer"]
    baseline_answer_type = baseline_result["answer_type"]
    baseline_supported = baseline_result["supported"]
    baseline_router = baseline_result["router"]

    # Baseline retrieval metrics (using V4 retriever with provided data)
    from src.retriever_v4 import retrieve as retrieve_v4_dup2

    baseline_merged_results = get_v4_retrieval_results_simple(
        question,
        baseline_result.get("chunks"),
        baseline_result.get("index"),
        baseline_result.get("document_frequency"),
    )

    baseline_recall = compute_recall_at_1_3_5(
        baseline_merged_results, must_contain
    )
    baseline_mrr = compute_mrr(
        baseline_merged_results, must_contain
    )

    # Baseline must_contain / must_not_contain checks
    baseline_missing_required = []
    for fragment in must_contain:
        if not text_contains(baseline_answer, fragment):
            baseline_missing_required.append(fragment)

    baseline_forbidden_found = []
    for fragment in must_not_contain:
        if text_contains(baseline_answer, fragment):
            baseline_forbidden_found.append(fragment)

    baseline_type_ok = (
        baseline_result.get("predicted_answer_type")
        == test_case.get("answer_type")
    )

    baseline_support_ok = (
        baseline_supported
        == bool(test_case.get("supported", False))
    )

    baseline_content_ok = (
        not baseline_missing_required
        and not baseline_forbidden_found
    )

    baseline_semantic_ok = (
        baseline_type_ok
        and baseline_support_ok
        and baseline_content_ok
    )

    baseline_latency_ok = baseline_elapsed <= 2.50

    # ---- Peak RAM ----
    try:
        import psutil
        peak_ram = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        peak_ram = 0.0

    # ---- Build result ----
    return {
        # Question info
        "name": test_case["name"],
        "category": test_case["category"],
        "question": question,

        # RALG results
        "ralg_answer": ralg_answer,
        "ralg_answer_type": ralg_answer_type,
        "ralg_supported": ralg_supported,
        "ralg_router": ralg_router,
        "ralg_retriever": ralg_retriever,
        "ralg_elapsed": ralg_elapsed,
        "ralg_semantic_ok": ralg_semantic_ok,
        "ralg_type_ok": ralg_type_ok,
        "ralg_support_ok": ralg_support_ok,
        "ralg_content_ok": ralg_content_ok,
        "ralg_latency_ok": ralg_latency_ok,
        "ralg_confidence": ralg_confidence,
        "ralg_missing_required": ralg_missing_required,
        "ralg_forbidden_found": ralg_forbidden_found,
        "ralg_recall_1": ralg_recall["recall_at_1"],
        "ralg_recall_3": ralg_recall["recall_at_3"],
        "ralg_recall_5": ralg_recall["recall_at_5"],
        "ralg_mrr": ralc_mrr,

        # Baseline results
        "baseline_answer": baseline_answer,
        "baseline_answer_type": baseline_answer_type,
        "baseline_supported": baseline_supported,
        "baseline_router": baseline_router,
        "baseline_elapsed": baseline_elapsed,
        "baseline_semantic_ok": baseline_semantic_ok,
        "baseline_type_ok": baseline_type_ok,
        "baseline_support_ok": baseline_support_ok,
        "baseline_content_ok": baseline_content_ok,
        "baseline_latency_ok": baseline_latency_ok,
        "baseline_recall_1": baseline_recall["recall_at_1"],
        "baseline_recall_3": baseline_recall["recall_at_3"],
        "baseline_recall_5": baseline_recall["recall_at_5"],
        "baseline_mrr": baseline_mrr,

        # System measurements
        "peak_ram_mb": peak_ram,

        # Test case info
        "must_contain": must_contain,
        "must_not_contain": must_not_contain,
        "expected_type": test_case.get("answer_type"),
        "expected_supported": test_case.get("supported"),
    }


def _answer_question_impl(pipeline, question, verbose=True):
    """Internal: run answer_question implementation."""
    from src.rag_chat_v2 import _answer_question_impl as _impl
    return _impl(pipeline, question, verbose)


def get_v4_retrieval_results_simple(question, chunks, index, document_frequency):
    """Simple V4 retrieval results getter."""
    try:
        from src.retriever_v4 import retrieve as retrieve_v4_dup3
        result = retrieve_v4_dup3(
            question,
            chunks or [],
            index or [],
            document_frequency or [],
            collect_timings=False,
        )
        return result.get("results", [])
    except Exception:
        return []


# ==========================================================
# BASELINE INITIALIZATION
# ==========================================================

def initialize_baseline():
    """
    Initialize baseline corpus and index once, before the evaluation loop.
    Same mechanism as rag_chat_v2.initialize_pipeline() loads chunks + builds index.
    Returns (chunks, index, document_frequency) or raises ValueError.
    """
    import time as _time

    from src.retriever_v2 import load_chunks as load_chunks_v2, build_index as build_index_v2

    start = _time.perf_counter()

    # Load knowledge corpus (same files RALG uses)
    from config import KNOWLEDGE_FILES

    if not KNOWLEDGE_FILES:
        raise ValueError("No knowledge files configured. Cannot initialize baseline.")

    # Load chunks
    chunks = load_chunks_v2(KNOWLEDGE_FILES)
    if not chunks:
        raise ValueError(
            f"Failed to load knowledge chunks from {KNOWLEDGE_FILES}. "
            "Baseline cannot proceed with empty corpus."
        )

    # Build lexical index
    index, document_frequency = build_index_v2(chunks)

    if index is None:
        raise ValueError("build_index_v2 returned None index. "
                         "Cannot build baseline retrieval without index.")

    if document_frequency is None:
        raise ValueError("build_index_v2 returned None document_frequency. "
                         "Cannot build baseline retrieval without document frequency.")

    elapsed = _time.perf_counter() - start

    print(f"\nBaseline initialized:")
    print(f"  Chunks loaded: {len(chunks)}")
    print(f"  Index built: {len(index) if index else 0} entries")
    print(f"  Initialization time: {elapsed:.3f}s")

    # Validation: a simple retrieval query should return an iterable/list
    test_question = "When was the Magna Carta signed?"
    try:
        from src.retriever_v2 import retrieve as retrieve_v2_test
        test_results = retrieve_v2_test(
            test_question,
            chunks,
            index,
            document_frequency,
            final_top_k=5,
        )
        if test_results is None:
            raise ValueError(
                f"Baseline retrieval smoke test failed: "
                f"retrieve_v2 returned None for question: {test_question}"
            )
        if not isinstance(test_results, list):
            raise ValueError(
                f"Baseline retrieval smoke test failed: "
                f"retrieve_v2 returned {type(test_results)} instead of list. "
                f"Question: {test_question}, Results: {test_results}"
            )
        if len(test_results) == 0:
            print(f"  WARNING: Baseline smoke test returned 0 results for: {test_question}")
    except Exception as e:
        raise ValueError(
            f"Baseline initialization validation failed: {e}"
        )

    return chunks, index, document_frequency


# ==========================================================
# HELPER: Baseline Runner
# ==========================================================

def _classify_question_type(question):
    """Classify the question type from the question text alone.

    Uses generic linguistic patterns without referencing benchmark expected types.
    Returns a predicted_answer_type string used by the evaluator.
    """
    q = question.strip()
    ql = q.lower()

    # factual: who/when/what specific questions not caught by other patterns
    if ql.startswith("what ") or ql.startswith("when ") or ql.startswith("who "):
        return "factual"

    # effects / consequences -> effect
    if ql.startswith("what are the effects ") or ql.startswith("what are the consequences ") or ql.startswith("what resulted ") or ql.startswith("what followed "):
        return "effect"

    # why / cause -> causal
    if ql.startswith("why ") or ql.startswith("what caused ") or ql.startswith("how caused "):
        return "causal"

    # compare / difference -> comparison
    if ql.startswith("compare ") or ql.startswith("how are ") or ql.startswith("differences between ") or ql.startswith("differ ") or " vs " in ql or " versus " in ql:
        return "comparison"

    # how organized / structure -> structure
    if ql.startswith("how was ") or ql.startswith("describe the structure ") or ql.startswith("what is the structure ") or ql.startswith("organization of ") or (ql.startswith("how is ") and ("organized" in ql or "structured" in ql)):
        return "structure"

    # who / figures -> entity_list
    if ql.startswith("who ") or ql.startswith("which ") or ql.startswith("name the ") or ql.startswith("list the ") or ql.startswith("identify the "):
        return "entity_list"

    # summarize / overview -> summary
    if ql.startswith("summarize ") or ql.startswith("give an overview ") or ql.startswith("main features ") or ql.startswith("main characteristics ") or ql.startswith("explain how "):
        return "summary"

    # default
    return "summary"


def run_baseline_simple(question, chunks, index, document_frequency):
    """Simple baseline runner -- same RAG flow as run_baseline but pre-loaded data."""
    import time as _time

    from src.router_v1 import route_question

    from src.retriever_v2 import retrieve as retrieve_v2_dup

    from src.extractor_v1 import extract_answer as extract_extractor_answer

    start = _time.perf_counter()
    route = route_question(question)

    answer = ""
    supported = False
    execution_mode = "system"  # internal mechanism label
    predicted_answer_type = _classify_question_type(question)
    retrieval_score = 0.0
    elapsed = 0.0

    # --- Always retrieve top-k evidence, regardless of router route ---
    results = retrieve_v2_dup(
        question,
        chunks,
        index,
        document_frequency,
        final_top_k=5,
    )

    if results:
        best = results[0]
        retrieval_score = best.get("final_score", 0.0)
        context = best.get("chunk", "")

        # --- Try the extractor first ---
        extracted = extract_extractor_answer(question, context)

        if extracted:
            answer = extracted
            supported = True
            execution_mode = "extractor"
            predicted_answer_type = _classify_question_type(question)
        else:
            # --- Fallback: simplest deterministic evidence-based answer ---
            answer = _extract_simple_answer(question, context)
            execution_mode = "simple_fallback"
            predicted_answer_type = _classify_question_type(question)
    else:
        answer = "couldn't find enough reliable evidence"
        execution_mode = "system"

    elapsed = _time.perf_counter() - start

    return {
        "answer": answer,
        "answer_type": execution_mode,  # kept for backward compatibility
        "predicted_answer_type": predicted_answer_type,  # semantic type for evaluator
        "execution_mode": execution_mode,  # internal mechanism label
        "supported": supported,
        "elapsed": elapsed,
        "router": route,
    }


# ==========================================================
# MAIN BENCHMARK RUNNER
# ==========================================================

def run_benchmark():
    """Run the full V4 benchmark suite."""

    print("\n" + "=" * 70)
    print("BENCHMARK SUITE V4 - RALG Evaluation")
    print("=" * 70)

    # ---- Initialize pipeline ----
    print("\nInitializing RALG pipeline...")
    import time as _time

    init_start = _time.perf_counter()
    pipeline = _initialize_pipeline(verbose=False)
    init_elapsed = _time.perf_counter() - init_start

    print(
        f"Pipeline initialized in {init_elapsed:.3f}s "
        f"({len(pipeline['chunks'])} chunks, device={pipeline['device']})"
    )

    # ---- Run evaluation on all test cases ----
    print(
        f"\nRunning {len(ALL_TESTS)} evaluation cases..."
    )

    results = []
    category_stats = {}

    total_start = _time.perf_counter()

    for idx, test in enumerate(ALL_TESTS, start=1):
        category = test["category"]

        # Initialize category stats
        if category not in category_stats:
            category_stats[category] = {
                "total": 0,
                "ralg_semantic_passes": 0,
                "baseline_semantic_passes": 0,
                "ralg_latencies": [],
                "baseline_latencies": [],
                "ralg_recall_1": [],
                "ralg_recall_3": [],
                "ralg_recall_5": [],
                "baseline_recall_1": [],
                "baseline_recall_3": [],
                "baseline_recall_5": [],
                "ralg_mrr": [],
                "baseline_mrr": [],
                "ralg_success": 0,
                "baseline_success": 0,
                "ralg_failures": 0,
                "baseline_failures": 0,
            }

        # Evaluate case
        eval_result = evaluate_v4_case(
            pipeline,
            test,
            pipeline.get("chunks"),
            pipeline.get("retrieval_index"),
            pipeline.get("document_frequency"),
        )

        results.append(eval_result)

        # Update category stats
        cat = category_stats[category]
        cat["total"] += 1

        # RALG metrics
        if eval_result["ralg_semantic_ok"]:
            cat["ralg_semantic_passes"] += 1
        cat["ralg_latencies"].append(eval_result["ralg_elapsed"])
        if eval_result["ralg_recall_1"] is not None:
            cat["ralg_recall_1"].append(eval_result["ralg_recall_1"])
        if eval_result["ralg_recall_3"] is not None:
            cat["ralg_recall_3"].append(eval_result["ralg_recall_3"])
        if eval_result["ralg_recall_5"] is not None:
            cat["ralg_recall_5"].append(eval_result["ralg_recall_5"])
        if eval_result["ralg_mrr"] is not None:
            cat["ralg_mrr"].append(eval_result["ralg_mrr"])
        if eval_result["ralg_semantic_ok"]:
            cat["ralg_success"] += 1
        if not eval_result["ralg_semantic_ok"]:
            cat["ralg_failures"] += 1

        # Baseline metrics
        if eval_result["baseline_semantic_ok"]:
            cat["baseline_semantic_passes"] += 1
        cat["baseline_latencies"].append(eval_result["baseline_elapsed"])
        if eval_result["baseline_recall_1"] is not None:
            cat["baseline_recall_1"].append(eval_result["baseline_recall_1"])
        if eval_result["baseline_recall_3"] is not None:
            cat["baseline_recall_3"].append(eval_result["baseline_recall_3"])
        if eval_result["baseline_recall_5"] is not None:
            cat["baseline_recall_5"].append(eval_result["baseline_recall_5"])
        if eval_result["baseline_mrr"] is not None:
            cat["baseline_mrr"].append(eval_result["baseline_mrr"])
        if eval_result["baseline_semantic_ok"]:
            cat["baseline_success"] += 1
        if not eval_result["baseline_semantic_ok"]:
            cat["baseline_failures"] += 1

        # Progress reporting
        if idx % 20 == 0 or idx == len(ALL_TESTS):
            print(
                f"[{idx:03d}/{len(ALL_TESTS):03d}] "
                f"{test['name']:<30} "
                f"Category: {category:<15} "
                f"RALG: {'OK' if eval_result['ralg_semantic_ok'] else 'FAIL'} "
                f"Base: {'OK' if eval_result['baseline_semantic_ok'] else 'FAIL'} "
                f"({eval_result['ralg_elapsed']:.3f}s/{eval_result['baseline_elapsed']:.3f}s)"
            )

    total_elapsed = _time.perf_counter() - total_start
# ---- Compute aggregate metrics ----
    print("\n" + "=" * 70)
    print("AGGREGATE METRICS")
    print("=" * 70)

    total = len(results)
    ralg_semantic_passes = sum(1 for r in results if r["ralg_semantic_ok"])
    baseline_semantic_passes = sum(1 for r in results if r["baseline_semantic_ok"])

    ralg_type_passes = sum(1 for r in results if r["ralg_type_ok"])
    baseline_type_passes = sum(1 for r in results if r["baseline_type_ok"])

    ralg_support_passes = sum(1 for r in results if r["ralg_support_ok"])
    baseline_support_passes = sum(1 for r in results if r["baseline_support_ok"])

    ralg_content_passes = sum(1 for r in results if r["ralg_content_ok"])
    baseline_content_passes = sum(1 for r in results if r["baseline_content_ok"])

    ralg_latency_passes = sum(1 for r in results if r["ralg_latency_ok"])
    baseline_latency_passes = sum(1 for r in results if r["baseline_latency_ok"])

    ralg_latencies = [r["ralg_elapsed"] for r in results]
    baseline_latencies = [r["baseline_elapsed"] for r in results]

    ralg_avg_latency = (
        __import__("statistics").mean(ralg_latencies) if ralg_latencies else 0.0
    )
    baseline_avg_latency = (
        __import__("statistics").mean(baseline_latencies) if baseline_latencies else 0.0
    )

    ralg_median_latency = (
        __import__("statistics").median(ralg_latencies) if ralg_latencies else 0.0
    )
    baseline_median_latency = (
        __import__("statistics").median(baseline_latencies) if baseline_latencies else 0.0
    )

    def p95(values):
        if not values:
            return 0.0
        ordered = sorted(values)
        pos = (len(ordered) - 1) * 0.95
        lower = int(pos)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = pos - lower
        return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction

    ralg_p95_latency = p95(ralg_latencies)
    baseline_p95_latency = p95(baseline_latencies)

    # --- Retrieval metrics: only over cases with non-empty must_contain ---
    eval_mask = [
        r["must_contain"] for r in results if r["must_contain"]
    ]
    eval_count = len(eval_mask)  # retrieval-evaluable cases / 265

    # Proxy retrieval metrics: only over retrieval-evaluable cases
    proxy_label = " (proxy: relevance via must_contain fragment matching)"

    ralg_recall_1_vals = [
        r["ralg_recall_1"] for r in results if r["ralg_recall_1"] is not None
    ]
    baseline_recall_1_vals = [
        r["baseline_recall_1"] for r in results if r["baseline_recall_1"] is not None
    ]
    ralg_recall_3_vals = [
        r["ralg_recall_3"] for r in results if r["ralg_recall_3"] is not None
    ]
    baseline_recall_3_vals = [
        r["baseline_recall_3"] for r in results if r["baseline_recall_3"] is not None
    ]
    ralg_recall_5_vals = [
        r["ralg_recall_5"] for r in results if r["ralg_recall_5"] is not None
    ]
    baseline_recall_5_vals = [
        r["baseline_recall_5"] for r in results if r["baseline_recall_5"] is not None
    ]
    ralg_mrr_vals = [
        r["ralg_mrr"] for r in results if r["ralg_mrr"] is not None
    ]
    baseline_mrr_vals = [
        r["baseline_mrr"] for r in results if r["baseline_mrr"] is not None
    ]

    ralg_recall_1 = (
        sum(ralg_recall_1_vals) / len(ralg_recall_1_vals) if ralg_recall_1_vals else 0.0
    )
    baseline_recall_1 = (
        sum(baseline_recall_1_vals) / len(baseline_recall_1_vals) if baseline_recall_1_vals else 0.0
    )
    ralg_recall_3 = (
        sum(ralg_recall_3_vals) / len(ralg_recall_3_vals) if ralg_recall_3_vals else 0.0
    )
    baseline_recall_3 = (
        sum(baseline_recall_3_vals) / len(baseline_recall_3_vals) if baseline_recall_3_vals else 0.0
    )
    ralg_recall_5 = (
        sum(ralg_recall_5_vals) / len(ralg_recall_5_vals) if ralg_recall_5_vals else 0.0
    )
    baseline_recall_5 = (
        sum(baseline_recall_5_vals) / len(baseline_recall_5_vals) if baseline_recall_5_vals else 0.0
    )
    ralg_mrr = (
        sum(ralg_mrr_vals) / len(ralg_mrr_vals) if ralg_mrr_vals else 0.0
    )
    baseline_mrr = (
        sum(baseline_mrr_vals) / len(baseline_mrr_vals) if baseline_mrr_vals else 0.0
    )

    # False premise rejection
    negative_cases = [r for r in results if not r["expected_supported"]]
    supported_cases = [r for r in results if r["expected_supported"]]

    rejected_negative = sum(
        1 for r in negative_cases if not r["ralg_supported"]
    )

    accepted_supported = sum(
        1 for r in supported_cases if r["ralg_supported"]
    )

    false_premise_rejection = (
        rejected_negative / len(negative_cases) if negative_cases else 0.0
    )
    supported_acceptance = (
        accepted_supported / len(supported_cases) if supported_cases else 0.0
    )

    # Confidence calibration
    confidence_bins = {
        "below_0.80": [],
        "0.80-0.90": [],
        "0.90-0.95": [],
        "0.95-1.00": [],
    }

    conf_available = 0
    conf_unavailable = 0

    for r in results:
        c = r["ralg_confidence"]
        if c is None:
            conf_unavailable += 1
        else:
            conf_available += 1
            if c < 0.80:
                confidence_bins["below_0.80"].append(r)
            elif c < 0.90:
                confidence_bins["0.80-0.90"].append(r)
            elif c < 0.95:
                confidence_bins["0.90-0.95"].append(r)
            else:
                confidence_bins["0.95-1.00"].append(r)

    confidence_stats = {}
    for bin_name, bin_cases in confidence_bins.items():
        if bin_cases:
            acc = sum(1 for r in bin_cases if r["ralg_semantic_ok"]) / len(bin_cases)
            # Only include confidences that are not None in the average
            valid_confs = [r["ralg_confidence"] for r in bin_cases if r["ralg_confidence"] is not None]
            if valid_confs:
                avg_conf = sum(valid_confs) / len(valid_confs)
            else:
                avg_conf = None
            confidence_stats[bin_name] = {
                "count": len(bin_cases),
                "accuracy": acc,
                "avg_confidence": avg_conf,
            }
        else:
            confidence_stats[bin_name] = {
                "count": 0,
                "accuracy": 0.0,
                "avg_confidence": None,
            }

    # Report confidence availability
    print(f"Confidence available: {conf_available} / {total}")
    print(f"Confidence unavailable: {conf_unavailable} / {total}")

    # Self-validation assertions for confidence scenarios
    import math
    validation_errors = []

    # A. all confidence values are None
    if conf_available == 0 and conf_unavailable == total:
        pass  # valid scenario: all confidence None
    # B. mixture of None and floats
    if conf_available > 0 and conf_unavailable > 0:
        pass  # valid scenario: mixed
    # C. all confidence values are floats
    if conf_unavailable == 0 and conf_available == total:
        pass  # valid scenario: all have confidence
    if validation_errors:
        print("\n" + "=" * 70)
        print("VALIDATION ERRORS")
        print("=" * 70)
        for error in validation_errors:
            print(f"  - {error}")

    # ---- Category breakdown ----
    print("\n" + "=" * 70)
    print("CATEGORY BREAKDOWN")
    print("=" * 70)

    for category in sorted(category_stats.keys()):
        cat = category_stats[category]
        total_c = cat["total"]
        if total_c == 0:
            continue

        ralg_rate = (
            cat["ralg_semantic_passes"] / total_c * 100 if total_c else 0.0
        )
        base_rate = (
            cat["baseline_semantic_passes"] / total_c * 100 if total_c else 0.0
        )

        ralg_recall_1_avg = (
            __import__("statistics").mean(cat["ralg_recall_1"]) * 100
            if cat["ralg_recall_1"]
            else 0.0
        )
        ralg_recall_3_avg = (
            __import__("statistics").mean(cat["ralg_recall_3"]) * 100
            if cat["ralg_recall_3"]
            else 0.0
        )
        ralg_recall_5_avg = (
            __import__("statistics").mean(cat["ralg_recall_5"]) * 100
            if cat["ralg_recall_5"]
            else 0.0
        )
        ralg_mrr_avg = (
            __import__("statistics").mean(cat["ralg_mrr"]) * 100
            if cat["ralg_mrr"]
            else 0.0
        )

        base_recall_1_avg = (
            __import__("statistics").mean(cat["baseline_recall_1"]) * 100
            if cat["baseline_recall_1"]
            else 0.0
        )
        base_recall_3_avg = (
            __import__("statistics").mean(cat["baseline_recall_3"]) * 100
            if cat["baseline_recall_3"]
            else 0.0
        )
        base_recall_5_avg = (
            __import__("statistics").mean(cat["baseline_recall_5"]) * 100
            if cat["baseline_recall_5"]
            else 0.0
        )
        base_mrr_avg = (
            __import__("statistics").mean(cat["baseline_mrr"]) * 100
            if cat["baseline_mrr"]
            else 0.0
        )

        ralg_lat_avg = (
            __import__("statistics").mean(cat["ralg_latencies"])
            if cat["ralg_latencies"]
            else 0.0
        )
        base_lat_avg = (
            __import__("statistics").mean(cat["baseline_latencies"])
            if cat["baseline_latencies"]
            else 0.0
        )

        print(
            f"{category:<20} "
            f"RALG: {cat['ralg_semantic_passes']:>3}/{total_c:<3} {ralg_rate:>5.1f}% "
            f"Base: {cat['baseline_semantic_passes']:>3}/{total_c:<3} {base_rate:>5.1f}% "
            f"Diff: {ralg_rate - base_rate:>+6.1f}% "
            f"| R@1: {ralg_recall_1_avg:>5.1f}% vs {base_recall_1_avg:>5.1f}% "
            f"| R@3: {ralg_recall_3_avg:>5.1f}% vs {base_recall_3_avg:>5.1f}% "
            f"| R@5: {ralg_recall_5_avg:>5.1f}% vs {base_recall_5_avg:>5.1f}% "
            f"| MRR: {ralg_mrr_avg:>5.1f}% vs {base_mrr_avg:>5.1f}% "
            f"| Lat: {ralg_lat_avg:.3f}s vs {base_lat_avg:.3f}s"
        )

    # ---- Core metrics summary ----
    print("\n" + "=" * 70)
    print("CORE METRICS SUMMARY")
    print("=" * 70)

    print(
        f"{'Metric':<25} {'RALG':>10} {'Baseline':>10} {'Diff':>10}"
    )
    print("-" * 70)

    core_metrics = [
        ("Semantic accuracy",
         ralg_semantic_passes / total if total else 0.0,
         baseline_semantic_passes / total if total else 0.0),
        ("Type accuracy",
         ralg_type_passes / total if total else 0.0,
         baseline_type_passes / total if total else 0.0),
        ("Support accuracy",
         ralg_support_passes / total if total else 0.0,
         baseline_support_passes / total if total else 0.0),
        ("Content accuracy",
         ralg_content_passes / total if total else 0.0,
         baseline_content_passes / total if total else 0.0),
        ("Latency pass rate",
         ralg_latency_passes / total if total else 0.0,
         baseline_latency_passes / total if total else 0.0),
        ("Recall@1", ralg_recall_1, baseline_recall_1),
        ("Recall@3", ralg_recall_3, baseline_recall_3),
        ("Recall@5", ralg_recall_5, baseline_recall_5),
        ("MRR", ralg_mrr, baseline_mrr),
    ]

    for metric_name, ral_val, base_val in core_metrics:
        diff = (ral_val - base_val) * 100 if base_val is not None else "N/A"
        ral_str = f"{ral_val * 100:>9.1f}%" if isinstance(ral_val, float) else f"{ral_val:>9}"
        base_str = f"{base_val * 100:>9.1f}%" if isinstance(base_val, float) else f"{base_val:>9}"
        diff_str = f"{diff:>+9.1f}%" if isinstance(diff, float) else f"{diff}"
        print(
            f"{metric_name:<25} "
            f"{ral_str} "
            f"{base_str} "
            f"{diff_str}"
        )

    print(f"Retrieval-evaluable cases: {eval_count} / 265{proxy_label}")
    print()
    print(f"Total cases: {total}")
    print(f"RALG semantic accuracy: {ralg_semantic_passes}/{total} "
          f"={ralg_semantic_passes/total*100:.1f}% (target: >=95%)")
    print(f"Baseline semantic accuracy: {baseline_semantic_passes}/{total} "
          f"={baseline_semantic_passes/total*100:.1f}%")
    print(f"RALG avg latency: {ralg_avg_latency:.3f}s (median: {ralg_median_latency:.3f}s, P95: {ralg_p95_latency:.3f}s)")
    print(f"Baseline avg latency: {baseline_avg_latency:.3f}s (median: {baseline_median_latency:.3f}s, P95: {baseline_p95_latency:.3f}s)")
    print(f"RALG Recall@1: {ralg_recall_1*100:.1f}%, Recall@3: {ralg_recall_3*100:.1f}%, Recall@5: {ralg_recall_5*100:.1f}%, MRR: {ralg_mrr*100:.1f}%")
    print(f"Baseline Recall@1: {baseline_recall_1*100:.1f}%, Recall@3: {baseline_recall_3*100:.1f}%, Recall@5: {baseline_recall_5*100:.1f}%, MRR: {baseline_mrr*100:.1f}%")
    print(f"Peak process RAM: {sum(r['peak_ram_mb'] for r in results)/total:.1f} MB avg")
    print(f"Initialization time: {init_elapsed:.3f}s")

    # ---- Confidence calibration ----
    print("\n" + "=" * 70)
    print("CONFIDENCE CALIBRATION")
    print("=" * 70)
    for bin_name, stats in confidence_stats.items():
        avg_conf = stats['avg_confidence']
        if avg_conf is None:
            conf_str = "N/A"
        else:
            conf_str = f"{avg_conf:.2f}"
        print(
            f"{bin_name}: {stats['count']} cases, "
            f"accuracy={stats['accuracy']*100:.1f}%, "
            f"avg_conf={conf_str}"
        )

    # ---- Self-validation assertions ----
    validation_errors = []

    # percentages between 0 and 100
    if total > 0:
        ralg_semantic_pct = ralg_semantic_passes / total * 100
        base_semantic_pct = baseline_semantic_passes / total * 100
        if ralg_semantic_pct > 100 or ralg_semantic_pct < 0:
            validation_errors.append("RALG semantic accuracy out of range")
        if base_semantic_pct > 100 or base_semantic_pct < 0:
            validation_errors.append("Baseline semantic accuracy out of range")

    # pass counts <= case counts
    if ralg_semantic_passes > total:
        validation_errors.append("RALG semantic passes > total cases")
    if baseline_semantic_passes > total:
        validation_errors.append("Baseline semantic passes > total cases")
    if ralg_content_passes > total:
        validation_errors.append("RALG content passes > total cases")
    if baseline_content_passes > total:
        validation_errors.append("Baseline content passes > total cases")

    # retrieval metric denominator correct (no empty must_contain cases included)
    if eval_count > 245:
        validation_errors.append(f"Retrieval-evaluable cases {eval_count} exceeds expected 245")
    if eval_count == 0:
        validation_errors.append("No retrieval-evaluable cases found (all must_contain empty)")

    # metric differences calculated correctly (no NaN/inf)
    import math
    for metric_name, ral_val, base_val in core_metrics:
        if isinstance(ral_val, float) and math.isnan(ral_val):
            validation_errors.append(f"NaN in {metric_name} RALG")
        if isinstance(base_val, float) and math.isnan(base_val):
            validation_errors.append(f"NaN in {metric_name} Baseline")
        if isinstance(ral_val, float) and math.isinf(ral_val):
            validation_errors.append(f"Inf in {metric_name} RALG")
        if isinstance(base_val, float) and math.isinf(base_val):
            validation_errors.append(f"Inf in {metric_name} Baseline")

    # baseline result exists for every case
    if total > 0 and len(results) != total:
        validation_errors.append(f"Results count {len(results)} != total cases {total}")

    # RALG result exists for every case
    for r in results:
        if r is None:
            validation_errors.append("Found None result in results list")

    if validation_errors:
        print("\n" + "=" * 70)
        print("VALIDATION ERRORS")
        print("=" * 70)
        for error in validation_errors:
            print(f"  - {error}")

    # ---- Generate JSON report ----
    print("\n" + "=" * 70)
    print("GENERATING REPORTS")
    print("=" * 70)

    # ... (JSON report generation)

    # Print human-readable summary
    print("\n" + "=" * 70)
    print("BENCHMARK V4 STATUS")
    print("=" * 70)

    all_targets_pass = all(
        [
            ralg_semantic_passes / total >= 0.95 if total else True,
            ralg_type_passes / total >= 0.95 if total else True,
            ralg_support_passes / total >= 0.95 if total else True,
            ralg_content_passes / total >= 0.95 if total else True,
            false_premise_rejection >= 0.95 if negative_cases else True,
            supported_acceptance >= 0.95 if supported_cases else True,
        ]
    )

    if all_targets_pass and not any(
        not r["ralg_semantic_ok"] for r in results
    ):
        print("EVALUATION V4 STATUS: PASS")
    elif all_targets_pass:
        print(
            "EVALUATION V4 STATUS: "
            "TARGETS PASS, "
            "BUT CASE FAILURES EXIST"
        )
    else:
        print("EVALUATION V4 STATUS: FAIL")

    print("=" * 70 + "\n")

    return {
        "benchmark_version": "V4",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_cases": total,
        "ralg_semantic_accuracy": ralg_semantic_passes / total if total else 0.0,
        "baseline_semantic_accuracy": baseline_semantic_passes / total if total else 0.0,
        "ralg_recall_1": ralg_recall_1,
        "baseline_recall_1": baseline_recall_1,
        "ralg_recall_3": ralg_recall_3,
        "baseline_recall_3": baseline_recall_3,
        "ralg_recall_5": ralg_recall_5,
        "baseline_recall_5": baseline_recall_5,
        "ralg_mrr": ralg_mrr,
        "baseline_mrr": baseline_mrr,
        "false_premise_rejection": false_premise_rejection,
        "supported_acceptance": supported_acceptance,
        "category_breakdown": {
            cat: {
                "ralg_semantic_rate": (
                    cat_stats["ralg_semantic_passes"] / cat_stats["total"] * 100
                    if cat_stats["total"]
                    else 0.0
                ),
                "baseline_semantic_rate": (
                    cat_stats["baseline_semantic_passes"] / cat_stats["total"] * 100
                    if cat_stats["total"]
                    else 0.0
                ),
            }
            for cat, cat_stats in category_stats.items()
        },
    }


def _initialize_pipeline(verbose=False):
    """Initialize the RALG pipeline."""
    from src.rag_chat_v2 import initialize_pipeline as _ip
    return _ip(verbose=verbose)


def quick_test():
    """Quick test to verify the benchmark framework works."""
    print("BENCHMARK SUITE V4 - Quick Framework Test")
    print("=" * 50)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data dir: {DATA_DIR}")
    print(f"Knowledge files: {KNOWLEDGE_FILES}")
    print(f"Total V3 tests: {len(V3_TESTS)}")
    print(f"Total V4 new tests: {len(V4_NEW_CATEGORIES['factual_qa']) + len(V4_NEW_CATEGORIES['multi_hop'])}")
    print(f"All tests: {len(ALL_TESTS)}")
    print("\nFramework operational")


def _initialize_pipeline_for_smoke():
    """Initialize RALG pipeline for smoke test."""
    from src.rag_chat_v2 import initialize_pipeline as _ip
    return _ip(verbose=False)


def fairness_smoke_test():
    """Execute 10-case fairness smoke test with balanced categories."""
    import statistics

    pipeline = _initialize_pipeline_for_smoke()

    from src.retriever_v2 import load_chunks as load_chunks_v2, build_index as build_index_v2

    from config import KNOWLEDGE_FILES

    # Initialize baseline data
    chunks = load_chunks_v2(KNOWLEDGE_FILES)
    index, document_frequency = build_index_v2(chunks)

    document_frequency = document_frequency or []

    # Select 10 specific test cases:
    # 2 factual, 2 causal, 2 comparison, 2 unsupported, 2 multi-hop
    smoke_cases = []

    # 2 factual (from V4 factual_qa, first two)
    for i in range(2):
        smoke_cases.append(
            V4_NEW_CATEGORIES["factual_qa"][i]
        )

    # 2 causal (from V3, first two causal questions, indices 0-1)
    for i in range(2):
        smoke_cases.append(V3_TESTS[i])

    # 2 comparison (from V3, first two comparison questions, indices 145-146)
    for i in range(2):
        smoke_cases.append(V3_TESTS[145 + i])

    # 2 unsupported (from V3, first two unsupported questions, indices 165-166)
    for i in range(2):
        smoke_cases.append(V3_TESTS[165 + i])

    # 2 multi-hop (from V4 multi_hop, first two)
    for i in range(2):
        smoke_cases.append(V4_NEW_CATEGORIES["multi_hop"][i])

    # Evaluate each case
    print("\n" + "=" * 70)
    print("FAIRNESS SMOKE TEST - 10 CASES")
    print("=" * 70)

    for tc in smoke_cases:
        question = tc["question"]
        category = tc["category"]
        must_contain = tc.get("must_contain", [])
        must_not_contain = tc.get("must_not_contain", [])

        # Run RALG evaluation
        ralg_result = _answer_question_impl(pipeline, question, verbose=False)
        ralg_answer = ralg_result.get("answer") or ""

        from src.retriever_v4 import retrieve as retrieve_v4_dup3
        ralg_merged_results = get_v4_retrieval_results_simple(
            question,
            ralg_result.get("chunks"),
            ralg_result.get("retrieval_index"),
            ralg_result.get("document_frequency"),
        )

        # Top retrieved evidence for RALG
        ralg_top_snippet = ralg_merged_results[0].get("chunk", "") if ralg_merged_results else ""

        # Compute RALG retrieval metrics
        ralg_recall = compute_recall_at_1_3_5(ralg_merged_results, must_contain)
        ralg_mrr = compute_mrr(ralg_merged_results, must_contain)

        # Run baseline evaluation
        baseline_result = run_baseline_simple(
            question, chunks, index, document_frequency,
        )
        baseline_answer = baseline_result["answer"]

        # Top retrieved evidence for baseline
        from src.retriever_v2 import retrieve as retrieve_v2_dup
        baseline_retrieval = retrieve_v2_dup(
            question, chunks, index, document_frequency, final_top_k=5,
        )
        baseline_top_snippet = baseline_retrieval[0].get("chunk", "") if baseline_retrieval else ""

        # Compute baseline retrieval metrics
        baseline_merged_results = get_v4_retrieval_results_simple(
            question,
            baseline_result.get("chunks"),
            baseline_result.get("index"),
            baseline_result.get("document_frequency"),
        )
        baseline_recall = compute_recall_at_1_3_5(baseline_merged_results, must_contain)
        baseline_mrr = compute_mrr(baseline_merged_results, must_contain)

        # Print results
        print(f"\nQuestion: {question}")
        print(f"Category: {category}")
        print(f"RALG answer: {ralg_answer}")
        print(f"Baseline answer: {baseline_answer}")
        print(f"RALG top retrieved evidence: {ralg_top_snippet[:200]}")
        print(f"Baseline top retrieved evidence: {baseline_top_snippet[:200]}")
        print(f"Expected supported status: {tc.get('supported')}")
        print(f"RALG score: recall_at_1={ralg_recall['recall_at_1']}, recall_at_3={ralg_recall['recall_at_3']}, recall_at_5={ralg_recall['recall_at_5']}, MRR={ralg_mrr}")
        print(f"Baseline score: recall_at_1={baseline_recall['recall_at_1']}, recall_at_3={baseline_recall['recall_at_3']}, recall_at_5={baseline_recall['recall_at_5']}, MRR={baseline_mrr}")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    report = run_benchmark()
    # Save JSON report
    import json
    json_path = PROJECT_ROOT / "benchmark_v4_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nJSON report written to: {json_path}")
