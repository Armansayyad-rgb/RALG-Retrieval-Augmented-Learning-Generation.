"""Hybrid pipeline: rag_chat_v2 (router + RAG) + polish_llm (Qwen-1.5B).

This module composes the two halves:

  - ``rag_chat_v2.runtime_plan`` decides what kind of question it is
    (lookup / generative / comparison / causal / ...).
  - ``chat_handler.collect_sources`` returns the top-K chunks.
  - ``polish_llm`` runs Qwen2.5-1.5B-Instruct as the final answer
    generator for cases where the small custom model is too weak.

For now we only redirect the two modes that the small custom LM cannot
handle well: pure generative (no useful RAG) and hybrid (RAG facts
plus reasoning). For pure lookups we keep the existing rag_chat_v2
path because it is fast and accurate.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Optional

from rag_chat_v2 import answer_question

from webui.chat_handler import (
    build_answer_contract,
    collect_sources,
)
from webui.polish_llm import (
    PolishLLM,
    polish_generative_answer,
    polish_hybrid_answer,
    polish_lookup_answer,
    quick_intent_guess,
)

_LOGGER = logging.getLogger(__name__)
_SAFE_PIPELINE_ERROR = "The answer service is temporarily unavailable."
_SAFE_POLISH_ERROR = "Optional answer polishing failed; showing the core answer."


# Intent labels from rag_chat_v2.runtime_plan that should be handled by
# the polish LLM instead of the small custom model.
GENERATIVE_INTENTS = {"general"}
HYBRID_INTENTS = {
    "cause",
    "effect",
    "change",
    "comparison",
    "structure",
    "summary",
    "entity_list",
}


@dataclass
class HybridTurn:
    question: str
    answer: str
    mode: str                # "rag_only" | "polish_lookup" | "polish_generative" | "polish_hybrid"
    intent: str              # from rag_chat_v2.runtime_plan
    answer_type: str         # from rag_chat_v2 result
    confidence: Optional[float]
    supported: bool
    sources: list[dict]
    traceable: bool = False
    conflict: bool = False
    provenance: list[dict] | None = None
    evidence: object = None
    error: Optional[str] = None


def route_through_hybrid(
    pipeline: dict,
    question: str,
    polish_llm: Optional[PolishLLM],
    *,
    top_k: int = 3,
    max_new_tokens: int = 256,
) -> HybridTurn:
    """Run one turn, choosing between the small custom LM and Qwen polish."""

    if not question or not question.strip():
        return HybridTurn(
            question=question,
            answer="Please enter a question.",
            mode="empty",
            intent="general",
            answer_type="empty",
            confidence=None,
            supported=False,
            sources=[],
        )

    # ------------------------------------------------------------------
    # 1. Let rag_chat_v2 do the routing + retrieval + (small LM) generation.
    # ------------------------------------------------------------------
    try:
        result = answer_question(pipeline, question.strip(), verbose=False)
    except Exception:
        _LOGGER.exception("Unhandled routing pipeline error")
        return HybridTurn(
            question=question,
            answer=(
                "Sorry, the routing pipeline failed. "
                "Please try again."
            ),
            mode="error",
            intent="general",
            answer_type="error",
            confidence=None,
            supported=False,
            sources=[],
            error=_SAFE_PIPELINE_ERROR,
        )

    plan = result.get("runtime_plan") or {}
    intent = plan.get("intent") or "general"
    fallback_sources = None
    if not result.get("evidence"):
        fallback_sources = collect_sources(pipeline, question, top_k)
    contract = build_answer_contract(
        pipeline,
        question,
        result,
        top_k,
        fallback_sources=fallback_sources,
    )
    source_texts = [s["evidence"] for s in contract.sources if s.get("evidence")]
    base_answer = contract.answer

    def make_turn(current_contract, mode, error=None):
        return HybridTurn(
            question=question,
            answer=current_contract.answer or "(no answer)",
            mode=mode,
            intent=intent,
            answer_type=current_contract.answer_type,
            confidence=current_contract.confidence,
            supported=current_contract.supported,
            sources=current_contract.sources,
            traceable=current_contract.traceable,
            conflict=current_contract.conflict,
            provenance=current_contract.provenance,
            evidence=current_contract.evidence,
            error=error,
        )

    def make_polished_contract(polished):
        polished_result = dict(result)
        polished_result["answer"] = polished or base_answer
        # Polishing may preserve support, but never upgrade an answer that
        # the shared base contract rejected.
        polished_result["supported"] = contract.supported
        polished_result["confidence"] = None
        return build_answer_contract(
            pipeline,
            question,
            polished_result,
            top_k,
            fallback_sources=fallback_sources,
        )

    # ------------------------------------------------------------------
    # 2. Decide whether to keep the small-model answer or polish it.
    # ------------------------------------------------------------------
    # If the polish LLM is not loaded, always fall back to rag_chat_v2.
    if polish_llm is None or not polish_llm.is_ready():
        return make_turn(contract, "rag_only")

    # Lookup path: rag_chat_v2 already produced a clean answer; only
    # repolish if the small LM was clearly weak (no confidence, no
    # support, or answer_type=system with no evidence).
    needs_polish_lookup = (
        not contract.supported
        and not base_answer
        or (contract.answer_type == "system" and not source_texts)
    )

    # Generative: pure open-ended question. Skip RAG's weak draft.
    is_generative_intent = intent in GENERATIVE_INTENTS and not source_texts
    if intent not in HYBRID_INTENTS and intent not in GENERATIVE_INTENTS:
        # Unknown / general intent with no retrieved context — treat as
        # generative.
        is_generative_intent = not source_texts

    # ------------------------------------------------------------------
    # 3a. Pure generative branch — no useful retrieval, just ask Qwen.
    # ------------------------------------------------------------------
    if is_generative_intent and not source_texts:
        try:
            polished = polish_generative_answer(
                polish_llm,
                question,
                max_new_tokens=max_new_tokens,
            )
            return make_turn(
                make_polished_contract(polished),
                "polish_generative",
            )
        except Exception:
            _LOGGER.exception("Generative polish failed")
            return make_turn(contract, "rag_only", _SAFE_POLISH_ERROR)

    # ------------------------------------------------------------------
    # 3b. Hybrid branch — RAG supplies facts, Qwen writes the answer.
    # ------------------------------------------------------------------
    if intent in HYBRID_INTENTS and source_texts:
        try:
            polished = polish_hybrid_answer(
                polish_llm,
                question,
                source_texts,
                max_new_tokens=max_new_tokens,
            )
            return make_turn(
                make_polished_contract(polished),
                "polish_hybrid",
            )
        except Exception:
            _LOGGER.exception("Hybrid polish failed")
            return make_turn(contract, "rag_only", _SAFE_POLISH_ERROR)

    # ------------------------------------------------------------------
    # 3c. Lookup polish — Qwen rewrites the retrieved context cleanly.
    # Only used when the small LM answer is weak.
    # ------------------------------------------------------------------
    if needs_polish_lookup and source_texts:
        try:
            polished = polish_lookup_answer(
                polish_llm,
                question,
                source_texts,
                max_new_tokens=max_new_tokens,
            )
            return make_turn(
                make_polished_contract(polished),
                "polish_lookup",
            )
        except Exception:
            _LOGGER.exception("Lookup polish failed")
            return make_turn(contract, "rag_only", _SAFE_POLISH_ERROR)

    # ------------------------------------------------------------------
    # 4. Default: trust the small custom model.
    # ------------------------------------------------------------------
    return make_turn(contract, "rag_only")


__all__ = ["HybridTurn", "route_through_hybrid", "quick_intent_guess"]