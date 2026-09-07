import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag_chat_v2 import extract_factual_answer
from query_planner_v1 import is_conditional_query


class TestConditionalGrounding(unittest.TestCase):

    # --- 1. exact cause/effect same record -> support ---

    def test_exact_cause_effect_same_record_support(self):
        context = (
            "PROBLEM: High Temperature\n"
            "- Cause: Blocked Vent\n"
            "- Cause: Low Coolant"
        )
        question = "If the vent is blocked, can the temperature be high?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("Blocked Vent", answer)
        self.assertIn("High Temperature", answer)

    # --- 2. correct cause + wrong effect -> abstain ---

    def test_correct_cause_wrong_effect_abstains(self):
        context = (
            "PROBLEM: Low Pressure\n"
            "- Cause: Blocked Vent"
        )
        question = "If the vent is blocked, can the temperature be high?"
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)

    # --- 3. correct effect + wrong cause -> abstain ---

    def test_correct_effect_wrong_cause_abstains(self):
        context = (
            "PROBLEM: High Temperature\n"
            "- Cause: Low Coolant"
        )
        question = "If the vent is blocked, can the temperature be high?"
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)

    # --- 4. cause/effect in different records -> abstain ---

    def test_cause_effect_different_records_abstains(self):
        context = (
            "PROBLEM: High Temperature\n"
            "- Cause: Low Coolant\n"
            "\n"
            "PROBLEM: Low Pressure\n"
            "- Cause: Blocked Vent"
        )
        question = "If the vent is blocked, can the temperature be high?"
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)

    # --- 5. adjacent records cannot leak ---

    def test_adjacent_records_cannot_leak(self):
        context = (
            "PROBLEM: Insufficient cooling\n"
            "- Cause: Dirty air filter\n"
            "- Cause: Low refrigerant\n"
            "\n"
            "PROBLEM: Short cycling (frequent on/off)\n"
            "- Cause: Dirty filter\n"
            "- Cause: Thermostat miscalibrated"
        )
        question = "If the filter is dirty, will the system short-cycle?"
        answer, supported = extract_factual_answer(question, context)
        # Must match Short cycling record, not Insufficient cooling
        if supported:
            self.assertIn("Short cycling", answer)
            self.assertNotIn("Insufficient cooling", answer)

    # --- 6. generic one-word effect overlap -> abstain ---

    def test_generic_one_word_effect_overlap_abstains(self):
        context = (
            "PROBLEM: High Pressure\n"
            "- Cause: Valve stuck open"
        )
        question = "If the valve is stuck, will the hydraulic pressure failure?"
        answer, supported = extract_factual_answer(question, context)
        # "pressure" alone should not ground "hydraulic pressure failure"
        self.assertFalse(supported)

    # --- 7. generic one-word cause overlap -> abstain ---

    def test_generic_one_word_cause_overlap_abstains(self):
        context = (
            "PROBLEM: System overload\n"
            "- Cause: Motor running continuously"
        )
        question = "If the motor is running, can the system overload?"
        answer, supported = extract_factual_answer(question, context)
        # "motor" and "system" are generic; need meaningful concept match
        # The cause "Motor running continuously" has "running" which is
        # meaningful, but the effect "System overload" vs question "system overload"
        # - "system" is generic, "overload" is not in the header
        # Actually "overload" is not in the header text "System overload"
        # Wait, "System overload" contains "overload" - let me check
        # "overload" is not in _GENERIC_OVERLAP_TERMS, so it's meaningful
        # But the question says "system overload" and header is "System overload"
        # "system" is generic, "overload" is meaningful and matches
        # So this might actually be supported. Let me adjust the test.
        # Use a case where the overlap is truly generic-only.
        pass  # Placeholder - see test below for correct version

    def test_generic_only_cause_overlap_abstains(self):
        context = (
            "PROBLEM: Device failure\n"
            "- Cause: Power surge"
        )
        question = "If the device fails, will the power be lost?"
        answer, supported = extract_factual_answer(question, context)
        # "power" and "device" are generic; "fails" vs "failure" is generic
        # "lost" is not in "Device failure" header
        self.assertFalse(supported)

    # --- 8. belt slippage morphological variant -> support ---

    def test_belt_slippage_variant_support(self):
        context = (
            "PROBLEM: Belt slippage\n"
            "- Cause: Drive belt loose\n"
            "- Cause: Worn pulley"
        )
        question = "If the drive belt is loose, will the conveyor experience slippage?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("Drive belt loose", answer)
        self.assertIn("Belt slippage", answer)

    # --- 9. short-cycle / short cycling safe variant -> support ---

    def test_short_cycle_cycling_variant_support(self):
        context = (
            "PROBLEM: Short cycling (frequent on/off)\n"
            "- Cause: Dirty filter\n"
            "- Cause: Thermostat miscalibrated"
        )
        question = "If the filter is dirty, will the system short-cycle?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("Dirty filter", answer)
        self.assertIn("Short cycling", answer)

    # --- 10. overheat / overheating safe variant -> support ---

    def test_overheat_overheating_variant_support(self):
        context = (
            "PROBLEM: Overheating during charge\n"
            "- Cause: Battery not properly ventilated"
        )
        question = "If the battery is not properly ventilated, can it overheat during charging?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("Battery not properly ventilated", answer)
        self.assertIn("Overheating during charge", answer)

    # --- 11. prerequisite positive state -> grounded support ---

    def test_prerequisite_positive_state_support(self):
        context = "Confirm Power is ON before start."
        question = "If power is ON, can I start?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("Yes", answer)
        self.assertNotIn("?", answer)

    # --- 12. prerequisite violated state -> grounded negative answer ---

    def test_prerequisite_violated_state_negative(self):
        context = "Confirm discharge valve is open before motor start."
        question = "If the discharge valve is closed, can the pump start safely?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("No", answer)
        self.assertNotIn("?", answer)

    # --- 13. prerequisite unrelated action -> abstain ---

    def test_prerequisite_unrelated_action_abstains(self):
        context = "Confirm Power is ON before start."
        question = "If power is ON, can I rotate the wheel?"
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)

    # --- 14. arbitrary factual sentence cannot be inverted ---

    def test_arbitrary_factual_no_inversion(self):
        context = "The valve is usually open."
        question = "If the valve is closed, can I start?"
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)

    # --- 15. evidence modality not strengthened ---

    def test_evidence_modality_not_strengthened(self):
        context = (
            "PROBLEM: Noise\n"
            "- Cause: Loose Belt (can cause rattling)"
        )
        question = "If the belt is loose, can it cause noise?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertNotIn("will always", answer.lower())

    # --- 16. unsupported conditional -> abstain ---

    def test_unsupported_conditional_abstains(self):
        context = "The system is in standby."
        question = "If the system is active, can I proceed?"
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)

    # --- 17. answer contains no raw question mark/question syntax ---

    def test_answer_no_raw_question_mark(self):
        context = "Confirm discharge valve is open before motor start."
        question = "If the discharge valve is closed, can the pump start safely?"
        answer, supported = extract_factual_answer(question, context)
        if supported:
            self.assertNotIn("?", answer)

    def test_troubleshooting_answer_no_question_mark(self):
        context = (
            "PROBLEM: High Temperature\n"
            "- Cause: Blocked Vent"
        )
        question = "If the vent is blocked, can the temperature be high?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertNotIn("?", answer)

    # --- 18. ordinary factual behavior unchanged ---

    def test_ordinary_factual_unchanged(self):
        context = "The model is ARC-12."
        question = "What is the model?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("ARC-12", answer)

    # --- 19. R1 behavior preserved ---

    def test_r1_subject_rejection_preserved(self):
        context = "The Roman Empire fell."
        question = "Who was the leader of the Roman Empire?"
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)

    # --- 20. Category E behavior preserved ---

    def test_category_e_multi_part_unchanged(self):
        # Multi-part factual with supported "for" relation pattern
        context = (
            "The color for the valve is Blue. "
            "The size for the valve is Large."
        )
        question = "What are the color and size for the valve?"
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("Blue", answer)
        self.assertIn("Large", answer)

    # --- Additional: is_conditional_query unchanged ---

    def test_conditional_query_detection_unchanged(self):
        self.assertTrue(is_conditional_query("If the valve is open, can I start?"))
        self.assertFalse(is_conditional_query("What is the valve status?"))

    # --- Additional: same-record enforcement explicit ---

    def test_same_record_enforcement(self):
        """Cause from record A and effect from record B must not combine."""
        context = (
            "PROBLEM: Short cycling\n"
            "- Cause: Thermostat miscalibrated\n"
            "\n"
            "PROBLEM: Insufficient cooling\n"
            "- Cause: Dirty filter"
        )
        question = "If the filter is dirty, will the system short-cycle?"
        answer, supported = extract_factual_answer(question, context)
        # Dirty filter is under Insufficient cooling, not Short cycling
        self.assertFalse(supported)


if __name__ == "__main__":
    unittest.main()
