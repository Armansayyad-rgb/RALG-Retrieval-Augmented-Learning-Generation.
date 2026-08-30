"""Regression tests for procedural grounding fix (Round 1).

Proves:
1. Procedural/instructional questions are not rejected by atomic
   subject/predicate grounding (fixes sop_005/sop_006 false rejection).
2. The PR #83 grounding guard is preserved for atomic factual claims.
3. Wrong-subject evidence still causes abstention for factual questions.
4. Wrong-predicate evidence still causes abstention for factual questions.
5. Misleading lexical overlap does not produce false-support.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class TestProceduralGroundingFix(unittest.TestCase):
    """Procedural questions must not be rejected by atomic subject/predicate split.

    The atomic subject/predicate grounding check is designed for entity-attribute
    factual claims. Applying it to procedural questions (SOPs, checklists, maintenance
    steps) causes false rejections because the evidence uses imperative verbs while
    the question uses modal passives.
    """

    def test_procedural_with_process_intent_bypasses_split(self):
        """When intent is 'process', _subject_predicate_grounded returns True."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What steps must be followed when calibrating a pressure transducer?"
        sources = [{"evidence": "Disconnect the transducer from the system."}]
        result = _subject_predicate_grounded(
            question, sources, "factual", "model", intent="process"
        )
        self.assertTrue(result, "Procedural intent should bypass atomic split")

    def test_procedural_with_imperative_evidence_bypasses_split(self):
        """Questions with procedural vocabulary bypass the atomic split."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What should be done before servicing the hydraulic pump?"
        sources = [{"evidence": "Lock out the power supply and verify zero energy state."}]
        result = _subject_predicate_grounded(
            question, sources, "factual", "model", intent="general"
        )
        self.assertTrue(result, "Procedural question should bypass atomic split")

    def test_procedural_checklist_bypasses_split(self):
        """Checklist-style questions bypass the atomic split."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What items must be inspected during the safety audit?"
        sources = [{"evidence": "Check fire extinguishers for expiration dates."}]
        result = _subject_predicate_grounded(
            question, sources, "factual", "model", intent="general"
        )
        self.assertTrue(result, "Checklist question should bypass atomic split")

    def test_procedural_maintenance_steps_bypasses_split(self):
        """Maintenance step questions bypass the atomic split."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "How should the filter element be replaced?"
        sources = [{"evidence": "Remove the old filter and install the new element."}]
        result = _subject_predicate_grounded(
            question, sources, "reasoning_model", "model", intent="general"
        )
        self.assertTrue(result, "Maintenance question should bypass atomic split")


class TestPR83GuardPreserved(unittest.TestCase):
    """The PR #83 grounding guard must still reject unsupported factual claims."""

    def test_wrong_subject_factual_rejected(self):
        """Factual question with wrong-subject evidence must be rejected."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What is the chemical formula for water?"
        sources = [{"evidence": "Carbon dioxide is a gas with formula CO2."}]
        result = _subject_predicate_grounded(
            question, sources, "factual", "model", intent="general"
        )
        self.assertFalse(result, "Wrong-subject evidence should fail grounding")

    def test_wrong_predicate_factual_rejected(self):
        """Factual question with wrong-predicate evidence must be rejected."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What is the boiling point of water?"
        sources = [{"evidence": "Water is a molecule composed of two hydrogen atoms and one oxygen atom."}]
        result = _subject_predicate_grounded(
            question, sources, "factual", "model", intent="general"
        )
        self.assertFalse(result, "Wrong-predicate evidence should fail grounding")

    def test_correct_factual_accepted(self):
        """Factual question with correct evidence should pass grounding."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What is the capital of France?"
        sources = [{"evidence": "Paris is the capital city of France."}]
        result = _subject_predicate_grounded(
            question, sources, "factual", "model", intent="general"
        )
        self.assertTrue(result, "Correct factual evidence should pass grounding")

    def test_reasoning_model_guard_preserved(self):
        """reasoning_model claims must also pass subject/predicate grounding."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What is the speed of light in vacuum?"
        sources = [{"evidence": "The speed of light in vacuum is approximately 299792458 m/s."}]
        result = _subject_predicate_grounded(
            question, sources, "reasoning_model", "model", intent="general"
        )
        self.assertTrue(result, "Correct reasoning_model evidence should pass grounding")

    def test_atomic_factual_with_modal_phrase_rejects_wrong_evidence(self):
        """Atomic factual claims with modal phrases still reject wrong evidence."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What must be the temperature for sterilization?"
        sources = [{"evidence": "The boiling point of water is 100 degrees Celsius at sea level."}]
        result = _subject_predicate_grounded(
            question, sources, "factual", "model", intent="general"
        )
        self.assertFalse(result, "Wrong evidence should fail even with modal phrase")


class TestMisleadingOverlapAbstention(unittest.TestCase):
    """Misleading lexical overlap must not produce false-support."""

    def test_overlapping_terms_different_meaning_abstain(self):
        """Shared terms with different meanings should not produce support."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What is the default port for HTTPS connections?"
        sources = [{"evidence": "The port number for agricultural exports increased significantly."}]
        result = _subject_predicate_grounded(
            question, sources, "factual", "model", intent="general"
        )
        self.assertFalse(result, "Misleading overlap should not produce support")


class TestNonFactualTypesExcluded(unittest.TestCase):
    """Non-factual answer types should bypass the atomic split entirely."""

    def test_summary_type_bypasses_split(self):
        """Summary answer types should bypass the atomic split."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What defined the political system?"
        sources = [{"evidence": "Some evidence"}]
        result = _subject_predicate_grounded(
            question, sources, "summary", "model", intent="general"
        )
        self.assertTrue(result, "Summary type should bypass atomic split")

    def test_system_type_bypasses_split(self):
        """System answer types should bypass the atomic split."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What happened?"
        sources = [{"evidence": "Some evidence"}]
        result = _subject_predicate_grounded(
            question, sources, "system", "model", intent="general"
        )
        self.assertTrue(result, "System type should bypass atomic split")

    def test_structure_type_bypasses_split(self):
        """Structure answer types should bypass the atomic split."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "How is the organization structured?"
        sources = [{"evidence": "Some evidence"}]
        result = _subject_predicate_grounded(
            question, sources, "structure", "model", intent="general"
        )
        self.assertTrue(result, "Structure type should bypass atomic split")

    def test_extractor_route_bypasses_split(self):
        """Extractor route should bypass the atomic split for non-factual types."""
        from webui.chat_handler import _subject_predicate_grounded

        question = "What is the value?"
        sources = [{"evidence": "The value is 42."}]
        result = _subject_predicate_grounded(
            question, sources, "extracted", "extractor", intent="general"
        )
        self.assertTrue(result, "Extractor route should bypass atomic split")


class TestIsProceduralQuestion(unittest.TestCase):
    """Test the _is_procedural_question helper directly."""

    def test_process_intent_is_procedural(self):
        from webui.chat_handler import _is_procedural_question
        self.assertTrue(_is_procedural_question("What is the value?", "process"))

    def test_how_to_question_is_procedural(self):
        from webui.chat_handler import _is_procedural_question
        self.assertTrue(_is_procedural_question("How do I replace the filter?", "general"))

    def test_what_steps_question_is_procedural(self):
        from webui.chat_handler import _is_procedural_question
        self.assertTrue(_is_procedural_question("What steps are required?", "general"))

    def test_factual_question_is_not_procedural(self):
        from webui.chat_handler import _is_procedural_question
        self.assertFalse(_is_procedural_question("What is the chemical formula for water?", "general"))

    def test_general_question_without_procedural_vocab_is_not_procedural(self):
        from webui.chat_handler import _is_procedural_question
        self.assertFalse(_is_procedural_question("What is the capital of France?", "general"))


if __name__ == "__main__":
    unittest.main()
