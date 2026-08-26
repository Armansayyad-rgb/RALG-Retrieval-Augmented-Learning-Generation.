"""Generalization regression set for the unified support gate.

Derived from the false-support failure modes observed in the frozen
holdout_v1 baseline (unsupported questions accepted as supported):

- causal-marker sentences templated into answers for an unrelated
  subject (causal synthesizer never required subject relatedness);
- summary-synthesizer evidence selected on generic word overlap and
  sentence-length bonuses without ever mentioning the question
  subject;
- factual "what is/was" anchoring that accepts a compound proper-noun
  mismatch ("Western Australia" for a question about "Australia").

This set lives OUTSIDE evaluation/holdout_v1, which stays frozen.
Every unsupported/adversarial case is paired with supported controls
so over-refusal is detected. Cases are unit-level: each carries its
own evidence context, so no model load or index build is needed.
"""

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
for import_path in (PROJECT_ROOT, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from causal_synthesizer_v1 import synthesize_causal_answer
from summary_synthesizer_v1 import synthesize_summary_answer
from rag_chat_v2 import (
    _anchor_entity_present,
    _contains_term,
    extract_factual_answer,
)

DEV_SET = (
    PROJECT_ROOT / "evaluation" / "dev_support_gate_v1.jsonl"
)


def load_cases():
    with open(DEV_SET, encoding="utf-8") as handle:
        return [
            json.loads(line)
            for line in handle
            if line.strip()
        ]


def case_supported(case):
    """Evaluate one dev-set case through the production support logic."""
    mode = case["mode"]
    question = case["question"]
    context = case["context"]

    if mode == "causal":
        return synthesize_causal_answer(question, context) is not None
    if mode.startswith("summary"):
        return synthesize_summary_answer(question, context) is not None
    if mode.startswith("factual"):
        _, supported = extract_factual_answer(question, context)
        return bool(supported)
    raise AssertionError(f"unknown mode {mode}")


class SupportGateGeneralizationTests(unittest.TestCase):
    def test_dev_set_matches_expectations(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 10)
        failures = []
        for case in cases:
            actual = case_supported(case)
            if actual != bool(case["expect_supported"]):
                failures.append(
                    f"{case['case_id']} ({case['failure_mode']}): "
                    f"expected supported={case['expect_supported']}, "
                    f"got {actual}"
                )
        self.assertEqual(
            failures, [], "support-gate generalization regressions"
        )

    def test_unsupported_and_control_mix_present(self):
        cases = load_cases()
        categories = {case["category"] for case in cases}
        self.assertIn("unsupported", categories)
        self.assertIn("supported_control", categories)

    def test_causal_requires_subject_relatedness(self):
        answer = synthesize_causal_answer(
            "Why did the Byzantine navy adopt Greek fire?",
            "The committee rejected the proposal because of "
            "unresolved border disputes.",
        )
        self.assertIsNone(answer)

    def test_summary_requires_subject_mention(self):
        answer = synthesize_summary_answer(
            "Explain how TLS session resumption works.",
            "Another session of work lasted to 4:15 near CBS Studios.",
        )
        self.assertIsNone(answer)

    def test_anchor_guard_compound_mismatch_rejected(self):
        sentence = (
            "It is located near Perth, the capital of Western Australia."
        )
        self.assertFalse(
            _anchor_entity_present(sentence, "australia",
                                   "What is the capital city of Australia?")
        )

    def test_anchor_guard_allows_question_named_compound(self):
        sentence = (
            "Perth is the capital of Western Australia."
        )
        self.assertTrue(
            _anchor_entity_present(sentence, "australia",
                                   "What is the capital of Western Australia?")
        )

    def test_anchor_guard_allows_standalone_anchor(self):
        sentence = "Canberra is Australia's purpose-built capital."
        self.assertTrue(
            _anchor_entity_present(sentence, "australia",
                                   "What is the capital city of Australia?")
        )

    def test_contains_term_rejects_substring_collision(self):
        self.assertFalse(_contains_term("recording accurate measurements", "rate"))
        self.assertFalse(_contains_term("four vellum pages", "age"))

    def test_contains_term_rejects_derived_word(self):
        self.assertFalse(_contains_term("pressure equipment capacity", "press"))
        self.assertFalse(_contains_term("the inventor of the device", "invented"))

    def test_contains_term_allows_inflections_and_boundaries(self):
        self.assertTrue(_contains_term("the growth rate of bamboo", "rate"))
        self.assertTrue(_contains_term("pumps and valves", "pump"))
        self.assertTrue(_contains_term("it was founded in 1912", "founded"))
        self.assertTrue(_contains_term("manuscript's age", "age"))


if __name__ == "__main__":
    unittest.main()
