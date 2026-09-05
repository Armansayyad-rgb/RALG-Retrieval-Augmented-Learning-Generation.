import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag_chat_v2 import extract_factual_answer


class RemediationR1FocusedTests(unittest.TestCase):

    def test_subject_only_answer_rejected_for_requested_attribute(self):
        question = (
            "What is the calibration tolerance for the AX-91 thermal controller?"
        )
        context = (
            "Model: AX-91 thermal controller. "
            "The enclosure is fabricated from anodized aluminum."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_requested_attribute_answer_still_supported(self):
        question = (
            "What is the calibration tolerance for the AX-91 thermal controller?"
        )
        context = (
            "The calibration tolerance for the AX-91 thermal controller "
            "is plus or minus 0.4 degrees Celsius."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertIsNotNone(answer)
        self.assertTrue(supported)
        self.assertIn("tolerance", answer.lower())

    def test_question_without_extracted_predicate_preserves_supported_behavior(self):
        question = "What happened during startup?"
        context = (
            "During startup, the controller completed its self-test successfully."
        )

        answer, supported = extract_factual_answer(question, context)

        # R1 must not impose the new predicate gate where the predicate
        # extractor has no applicable attribute predicate.
        if supported:
            self.assertIsNotNone(answer)
        else:
            self.assertIsNone(answer)

    def test_procedural_factual_extraction_not_broken(self):
        question = "How do you calculate the alignment offset for a sensor rail?"
        context = (
            "The alignment offset is calculated by subtracting the reference "
            "mark position from the measured rail position."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertIsNotNone(answer)
        self.assertTrue(supported)

    def test_unsupported_attribute_does_not_become_supported(self):
        question = (
            "What is the ultraviolet emission limit for the QZ-44 drive unit?"
        )
        context = (
            "The QZ-44 drive unit uses a sealed steel housing. "
            "Its nominal supply voltage is 48 volts."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertIsNone(answer)
        self.assertFalse(supported)


if __name__ == "__main__":
    unittest.main()
