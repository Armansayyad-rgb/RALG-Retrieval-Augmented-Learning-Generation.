"""Unit tests for the dependency-light runtime architecture boundary."""

import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime_architecture import (
    MODEL_REGISTRY,
    MultiHopTrace,
    _plan,
    execute_runtime,
)


def run(raw):
    def contract_fn(*args, **_kwargs):
        current = args[2] if len(args) > 2 else raw
        return SimpleNamespace(
            answer=current.get("answer", ""),
            supported=current.get("supported", False),
            confidence=current.get("confidence"),
            answer_type=current.get("answer_type", "system"),
            sources=current.get("sources", []),
            provenance=current.get("provenance", []),
            traceable=current.get("traceable", False),
            conflict=current.get("conflict", False),
            evidence=current.get("evidence"),
            error=None,
        )
    return execute_runtime(
        {}, "  question  ", 3,
        answer_fn=lambda *_args, **_kwargs: raw,
        contract_fn=contract_fn,
        sources_fn=lambda *_args, **_kwargs: [],
    )


class RuntimeArchitectureTests(unittest.TestCase):
    def test_supported_and_unsupported_share_gate(self):
        supported = run({
            "answer": "Yes", "supported": True, "traceable": True,
            "runtime_plan": {"intent": "general"}, "evidence": {"kind": "v2"},
        })
        unsupported = run({
            "answer": "I don't know", "supported": False,
            "runtime_plan": {"intent": "general"},
        })
        self.assertTrue(supported.supported)
        self.assertFalse(unsupported.supported)
        self.assertEqual(supported.plan.route, "model")

    def test_reasoning_comparison_and_multihop_routes_are_deterministic(self):
        for intent in ("cause", "comparison"):
            result = run({
                "runtime_plan": {"intent": intent, "subject": "x"},
                "multi_hop": intent == "cause",
                "retrieval_passes": 2,
            })
            self.assertEqual(result.plan.route, "model")
            self.assertEqual(result.plan.multi_hop, intent == "cause")
            self.assertEqual(result.plan.retrieval_passes, 2)

    def test_qwen_is_explicitly_non_grounded(self):
        self.assertFalse(MODEL_REGISTRY["qwen-polish"].grounded)
        self.assertEqual(MODEL_REGISTRY["qwen-polish"].role, "non-grounded-polishing")

    def test_authoritative_plan_overrides_legacy_router(self):
        plan = _plan("why", {
            "router": "extractor",
            "runtime_plan": {"intent": "cause", "subject": "x"},
        })
        self.assertEqual(plan.route, "model")

    def test_support_gate_rejects_untraceable_generated_support(self):
        result = run({
            "answer": "unsupported prose",
            "supported": True,
            "runtime_plan": {"intent": "general"},
            "evidence": {"kind": "v2"},
            "traceable": False,
        })
        self.assertFalse(result.supported)
        self.assertEqual(result.answer_type, "system")
        self.assertIn("reliable evidence", result.answer)

    def test_observability_and_provenance_are_preserved(self):
        result = run({
            "runtime_plan": {"intent": "comparison"},
            "sources": [{"document_id": "d1"}],
            "provenance": [{"document_id": "d1"}],
            "traceable": True,
        })
        self.assertEqual(result.provenance, [{"document_id": "d1"}])
        self.assertEqual(result.observability["intent"], "comparison")
        self.assertIn("latency_ms", result.observability)


    def test_model_registry_classifies_every_artifact(self):
        statuses = {spec.status for spec in MODEL_REGISTRY.values()}
        allowed = {
            "ACTIVE", "COMPATIBLE BUT UNUSED", "SUPERSEDED", "LEGACY/INCOMPATIBLE",
        }
        self.assertTrue(statuses <= allowed, statuses)
        active = [s for s in MODEL_REGISTRY.values() if s.loaded]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].status, "ACTIVE")
        self.assertIn("reasoning_model_v1.pt", str(active[0].artifact))
        self.assertFalse(MODEL_REGISTRY["epoch-and-step-checkpoints"].loaded)
        self.assertFalse(MODEL_REGISTRY["instruction-model-v1"].loaded)

    def test_multi_hop_trace_is_explicit_and_traceable(self):
        def contract_fn(_p, _q, current, *_a, **_k):
            return SimpleNamespace(
                answer="a", supported=True, confidence=0.9,
                answer_type="multi_hop",
                sources=[{"id": "d1#0"}, {"id": "d2#3"}],
                provenance=[{"document_id": "d1"}, {"document_id": "d2"}],
                traceable=True, conflict=False,
                evidence={"kind": "v2"}, error=None,
            )
        result = execute_runtime(
            {}, "how did X's decline affect Y?", 3,
            answer_fn=lambda *_a, **_k: {
                "answer": "a", "supported": True, "traceable": True,
                "multi_hop": True, "evidence": {"kind": "v2"},
                "runtime_plan": {"intent": "cause", "subquestions": [
                    "Why did X decline?", "How did that affect Y?",
                ]},
            },
            contract_fn=contract_fn,
            sources_fn=lambda *_a, **_k: [],
        )
        trace = result.multi_hop_trace
        self.assertIsInstance(trace, MultiHopTrace)
        self.assertEqual(trace.original_question, "how did X's decline affect Y?")
        self.assertEqual(len(trace.subquestions), 2)
        self.assertEqual(trace.final_evidence_ids, ["d1#0", "d2#3"])
        self.assertTrue(trace.final_support_decision)
        self.assertTrue(result.observability["multi_hop"])

    def test_non_grounded_mode_cannot_be_silent(self):
        for name in ("qwen-polish", "instruction-model-v1", "instruction-model-v3-v4"):
            self.assertFalse(MODEL_REGISTRY[name].grounded)


if __name__ == "__main__":
    unittest.main()
