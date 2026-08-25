"""Authoritative RALG runtime orchestration shared by API and UI.

The legacy model/retriever implementation remains behind this small boundary;
all callers receive the same plan, evidence gate, provenance and telemetry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


REASONING_INTENTS = {
    "cause", "change", "effect", "structure", "process", "features",
    "significance", "entity_list", "comparison",
}


@dataclass(frozen=True)
class ModelSpec:
    name: str
    grounded: bool
    role: str
    artifact: str | None = None
    loaded: bool = False
    status: str = "UNCLASSIFIED"
    compatibility_reason: str = ""


# Explicit classification of every relevant checkpoint/model artifact.
# Nothing outside ACTIVE status is ever loaded by the runtime.
MODEL_REGISTRY: Mapping[str, ModelSpec] = {
    "small-lm-v2": ModelSpec(
        "small-lm-v2", True, "grounded-answering",
        artifact="checkpoints/v2/reasoning_model_v1.pt", loaded=True, status="ACTIVE",
        compatibility_reason="ACTIVE — current checkpoint loaded by rag_chat_v2 via config.MODEL_FILE.",
    ),
    "final-model-v2": ModelSpec(
        "final-model-v2", True, "grounded-answering",
        artifact="checkpoints/v2/final_model_v2.pt", loaded=False,
        status="COMPATIBLE BUT UNUSED",
        compatibility_reason=(
            "Same v2 architecture/format as the active checkpoint; kept as a "
            "fallback candidate but not wired into config.MODEL_FILE."
        ),
    ),
    "qwen-polish": ModelSpec(
        "qwen-polish", False, "non-grounded-polishing",
        artifact="checkpoints/qwen2.5-1.5b-instruct/", loaded=False,
        status="COMPATIBLE BUT UNUSED",
        compatibility_reason=(
            "Optional Qwen instruction model. May rewrite text only as an "
            "explicit NON-GROUNDED mode; can never establish support."
        ),
    ),
    "instruction-model-v3-v4": ModelSpec(
        "instruction-model-v3-v4", False, "unused-legacy",
        artifact="checkpoints/v2/instruction_model_v3.pt, checkpoints/v2/instruction_model_v4.pt",
        loaded=False,
        status="SUPERSEDED",
        compatibility_reason="Superseded by reasoning_model_v1 training lineage; never auto-loaded.",
    ),
    "instruction-model-v1": ModelSpec(
        "instruction-model-v1", False, "unused-legacy",
        artifact="checkpoints/instruction_model.pt, checkpoints/instruction_model_v2.pt",
        loaded=False,
        status="LEGACY/INCOMPATIBLE",
        compatibility_reason="Pre-v2 format lineage; retained on disk only, not loadable by v2 runtime.",
    ),
    "epoch-and-step-checkpoints": ModelSpec(
        "epoch-and-step-checkpoints", False, "training-artifacts",
        artifact="checkpoints/epoch_*.pt, checkpoints/final_model.pt, checkpoints/v2/step_*.pt, checkpoints/v2/final_model_v2_3000.pt",
        loaded=False,
        status="LEGACY/INCOMPATIBLE",
        compatibility_reason="Intermediate training snapshots; not runtime artifacts. Never auto-loaded.",
    ),
    "embedding-model": ModelSpec(
        "embedding-model", False, "retrieval-index-input",
        artifact="checkpoints/embedding_model.pt", loaded=False,
        status="COMPATIBLE BUT UNUSED",
        compatibility_reason=(
            "Embedding model used to build the retrieval index offline; the "
            "runtime loads the prebuilt index instead of this binary."
        ),
    ),
}


@dataclass(frozen=True)
class ExecutionPlan:
    intent: str
    route: str
    canonical_question: str | None
    subject: str
    multi_hop: bool
    retrieval_passes: int = 1
    retrieval_strategy: str = "hybrid"
    generator: str = "small-lm-v2"
    model: str = "small-lm-v2"


# Only ACTIVE registry entries may be selected automatically by runtime
# planning. Everything else is opt-in/explicit only.
AUTO_SELECTABLE_STATUS = "ACTIVE"
DEFAULT_GROUNDED_MODEL = "small-lm-v2"
DEFAULT_EXTRACTOR = "extractor"


def resolve_runtime_model(requested: str | None = None) -> ModelSpec:
    """Resolve a model for automatic runtime planning.

    Inactive artifacts (SUPERSEDED, LEGACY/INCOMPATIBLE, COMPATIBLE BUT
    UNUSED) can never be auto-selected; requests for them fall back to
    the ACTIVE grounded checkpoint. Non-grounded polish models stay
    separate from grounded factual answering by construction.
    """
    if requested:
        spec = MODEL_REGISTRY.get(str(requested))
        if spec is not None and spec.status == AUTO_SELECTABLE_STATUS and spec.grounded:
            return spec
    return MODEL_REGISTRY[DEFAULT_GROUNDED_MODEL]


@dataclass
class ExecutionResult:
    question: str
    answer: str
    supported: bool
    confidence: float | None
    answer_type: str
    sources: list[dict[str, Any]]
    provenance: list[dict[str, Any]]
    traceable: bool
    conflict: bool
    plan: ExecutionPlan
    raw: dict[str, Any] = field(default_factory=dict)
    evidence: Any = None
    error: str | None = None
    observability: dict[str, Any] = field(default_factory=dict)
    multi_hop_trace: MultiHopTrace | None = None


def _plan(question: str, raw: dict[str, Any]) -> ExecutionPlan:
    runtime = raw.get("runtime_plan") or {}
    intent = str(runtime.get("intent") or "general")
    multi_hop = bool(raw.get("multi_hop") or runtime.get("multi_hop"))
    route = str(raw.get("router") or "")
    if intent in REASONING_INTENTS or multi_hop:
        route = "model"
    elif route not in {"extractor", "model"}:
        route = "model"
    resolved = resolve_runtime_model(
        raw.get("model") or raw.get("generator_model")
    )
    return ExecutionPlan(
        intent=intent,
        route=route,
        canonical_question=raw.get("canonical_question"),
        subject=str(runtime.get("subject") or ""),
        multi_hop=multi_hop,
        retrieval_passes=int(raw.get("retrieval_passes") or (2 if multi_hop else 1)),
        # One authoritative production retrieval architecture: the
        # validated full-question-first hybrid retriever backs every
        # grounded reasoning route.
        retrieval_strategy=(
            "hybrid" if route == "model" else "v2-extractor"
        ),
        generator=(
            DEFAULT_EXTRACTOR
            if route == "extractor"
            else resolved.name
        ),
        model=resolved.name,
    )


@dataclass(frozen=True)
class MultiHopTrace:
    """Explicit multi-hop state, fully traceable end to end."""

    original_question: str
    subquestions: list[str]
    evidence_per_subquestion: dict[str, list[str]]
    supported_intermediate_facts: list[str]
    final_evidence_ids: list[str]
    final_support_decision: bool


def build_multi_hop_trace(
    question: str,
    plan: ExecutionPlan,
    raw: Mapping[str, Any],
    sources: list[dict[str, Any]],
    supported: bool,
) -> MultiHopTrace | None:
    if not plan.multi_hop:
        return None
    runtime = raw.get("runtime_plan") or {}
    subquestions = [
        str(item)
        for item in (
            runtime.get("subquestions")
            or raw.get("subquestions")
            or [raw.get("subject") or "", runtime.get("object") or ""]
        )
        if item
    ]
    evidence_per_hop: dict[str, list[str]] = {}
    for index, sub in enumerate(subquestions):
        chunk_sources = [
            str(source.get("id") or source.get("chunk_index"))
            for source in sources
            if isinstance(source, dict)
            and (source.get("id") is not None or source.get("chunk_index") is not None)
        ]
        hop_sources = [chunk_sources[index]] if index < len(chunk_sources) else []
        evidence_per_hop[sub] = hop_sources
    intermediate = [
        str(fact)
        for fact in (
            raw.get("intermediate_facts")
            or runtime.get("intermediate_facts")
            or []
        )
        if fact
    ]
    return MultiHopTrace(
        original_question=question,
        subquestions=subquestions,
        evidence_per_subquestion=evidence_per_hop,
        supported_intermediate_facts=intermediate,
        final_evidence_ids=[
            str(source.get("id") or source.get("chunk_index"))
            for source in sources
            if isinstance(source, dict)
            and (source.get("id") is not None or source.get("chunk_index") is not None)
        ],
        final_support_decision=supported,
    )


def unified_support_gate(raw: dict[str, Any], contract: Any) -> tuple[bool, list[str]]:
    """Apply the non-negotiable evidence/support policy after formatting."""
    reasons: list[str] = []
    if not bool(raw.get("supported")):
        reasons.append("raw_unsupported")
    if not contract.evidence and not contract.sources:
        reasons.append("missing_evidence")
    if not bool(contract.traceable):
        reasons.append("not_traceable")
    if contract.conflict:
        reasons.append("conflicting_evidence")
    if contract.provenance:
        provenance_ok = any(bool(item) for item in contract.provenance)
    else:
        # Static corpus evidence pre-dates runtime provenance metadata.
        provenance_ok = bool(contract.sources or contract.evidence)
    if not provenance_ok:
        reasons.append("missing_provenance")
    return not reasons, reasons


def execute_runtime(
    pipeline: dict[str, Any],
    question: str,
    top_k: int = 5,
    *,
    answer_fn: Callable[..., dict[str, Any]],
    contract_fn: Callable[..., Any],
    sources_fn: Callable[..., list[dict[str, Any]]],
) -> ExecutionResult:
    """Run the single shared grounded execution path.

    ``answer_fn`` and formatting functions are injectable to preserve legacy
    integrations and make API/UI parity testable without loading a model.
    """
    normalized = question.strip()
    started = time.perf_counter()
    raw = answer_fn(pipeline, normalized, verbose=False)
    fallback = None
    if not raw.get("evidence"):
        fallback = sources_fn(pipeline, normalized, top_k, answer=raw.get("answer", ""))
    contract = contract_fn(
        pipeline, normalized, raw, top_k, fallback_sources=fallback
    )
    gate_passed, gate_reasons = unified_support_gate(raw, contract)
    if not gate_passed and not contract.conflict:
        # Use the established system-answer wording rather than exposing a
        # generated answer that failed the unified support policy.
        raw = dict(raw)
        raw["answer"] = (
            "I couldn't find enough reliable evidence in the current "
            "knowledge base."
        )
        raw["answer_type"] = "system"
        raw["supported"] = False
        raw["confidence"] = None
        contract = contract_fn(
            pipeline, normalized, raw, top_k, fallback_sources=fallback
        )
    # The unified support gate is authoritative: nothing is reported as
    # supported unless the gate passed, even if an upstream contract
    # object claims support.
    final_supported = bool(gate_passed)
    plan = _plan(normalized, raw)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    multi_hop_trace = build_multi_hop_trace(
        normalized, plan, raw, contract.sources, final_supported
    )
    return ExecutionResult(
        question=normalized,
        answer=contract.answer,
        supported=final_supported,
        confidence=contract.confidence if gate_passed else None,
        answer_type=contract.answer_type,
        sources=contract.sources,
        provenance=contract.provenance,
        traceable=contract.traceable,
        conflict=contract.conflict,
        plan=plan,
        raw=raw,
        evidence=contract.evidence,
        error=contract.error,
        observability={
            "latency_ms": elapsed_ms,
            "route": plan.route,
            "intent": plan.intent,
            "retrieval_passes": plan.retrieval_passes,
            "retrieval_strategy": plan.retrieval_strategy,
            "generator": plan.generator,
            "evidence_ids": [
                str(source.get("id") or source.get("chunk_index"))
                for source in contract.sources
                if isinstance(source, dict)
                and (source.get("id") is not None or source.get("chunk_index") is not None)
            ],
            "grounded_model": MODEL_REGISTRY[plan.model].grounded,
            "support_gate": gate_passed,
            "support_gate_reasons": gate_reasons,
            "multi_hop": bool(multi_hop_trace),
            "conflict": bool(contract.conflict),
            "abstained": not bool(gate_passed),
            "abstention_reason": (
                gate_reasons if not gate_passed else []
            ),
        },
        multi_hop_trace=multi_hop_trace,
    )


__all__ = [
    "AUTO_SELECTABLE_STATUS", "DEFAULT_GROUNDED_MODEL", "ExecutionPlan",
    "ExecutionResult", "MODEL_REGISTRY", "ModelSpec",
    "MultiHopTrace", "build_multi_hop_trace",
    "execute_runtime", "resolve_runtime_model",
    "unified_support_gate",
]
