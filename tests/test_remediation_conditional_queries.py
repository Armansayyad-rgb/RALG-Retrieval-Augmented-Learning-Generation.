import unittest
from src.query_planner_v1 import build_queries

class TestRemediationConditionalQueries(unittest.TestCase):
    def test_true_positives_suppress_decomposition(self):
        """Conditional queries should preserve original but suppress decomposed variant."""
        test_cases = [
            "If the discharge valve is closed, can the pump start safely?",
            "When pressure falls below the minimum, should the controller shut down?",
            "Unless the isolation switch is open, can maintenance begin?",
            "Only when ventilation is active may charging continue.",
            "Provided that the enclosure is dry, can the panel be opened?",
        ]

        for q in test_cases:
            with self.subTest(question=q):
                result = build_queries(q)
                queries = result["queries"]

                # Must preserve original
                self.assertIn(q, queries)

                # Must NOT contain the decomposed keyword-only version
                # For "If the discharge valve is closed...", decomposition would be "discharge valve closed pump start safely"
                # We check that no query in the list consists only of the keywords extracted from the subject
                # a simple way is to check that the length of the queries list is small (usually 1 for general conditionals now)
                # Since they are 'general' intent, they only have original and the decomposed one.
                # If decomposition is suppressed, only the original remains.
                self.assertEqual(len(queries), 1, f"Expected only original query for conditional: {q}")

    def test_false_positives_preserve_decomposition(self):
        """Non-conditional queries should still be decomposed."""
        test_cases = [
            "When was the controller installed?",
            "When does the warranty expire?",
            "If available, list the model number.",
            "What is the standard operating temperature?",
        ]

        for q in test_cases:
            with self.subTest(question=q):
                result = build_queries(q)
                queries = result["queries"]

                # Must preserve original
                self.assertIn(q, queries)

                # Must contain the decomposed version (len > 1)
                self.assertGreater(len(queries), 1, f"Expected decomposed query for non-conditional: {q}")

    def test_process_routing_unchanged(self):
        """'What happens when X starts?' should still be 'process' intent and not hit general decomposition."""
        q = "What happens when the device starts?"
        result = build_queries(q)
        self.assertEqual(result["intent"], "process")
        # Process intent adds several queries, so len should be > 1
        self.assertGreater(len(result["queries"]), 1)

    def test_ordinary_general_query_unchanged(self):
        """Ordinary general queries should still be decomposed."""
        q = "What is the maximum torque of the motor?"
        result = build_queries(q)
        self.assertEqual(result["intent"], "general")
        self.assertGreater(len(result["queries"]), 1)

if __name__ == "__main__":
    unittest.main()
