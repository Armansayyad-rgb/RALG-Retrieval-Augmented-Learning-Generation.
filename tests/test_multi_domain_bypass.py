import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag_chat_v2 import extract_factual_answer

class TestMultiDomainBypass(unittest.TestCase):

    def test_unrelated_domains_same_chunk_reject(self):
        question = "What is the voltage for the battery and the temperature for the DNA replication?"
        context = "The voltage for the battery is 12V. DNA replication is a biological process."
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)
        self.assertIsNone(answer)

    def test_unrelated_domains_cross_binding_reject(self):
        question = "What is the voltage for the battery and the temperature for the DNA replication?"
        context = "The voltage for the battery is 12V. The temperature is 37C. DNA replication is a biological process."
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)
        self.assertIsNone(answer)

    def test_valid_same_domain_multi_part_support(self):
        question = "What are the voltage and temperature for the battery?"
        context = "The voltage for the battery is 12V. The temperature for the battery is 25C."
        answer, supported = extract_factual_answer(question, context)
        self.assertTrue(supported)
        self.assertIn("12v", answer.lower())
        self.assertIn("25c", answer.lower())

    def test_missing_entity_binding_one_subclaim_reject(self):
        question = "What are the voltage and temperature for the battery?"
        context = "The voltage for the battery is 12V. The temperature is 25C."
        # "25C" is present, but not bound to "battery".
        answer, supported = extract_factual_answer(question, context)
        self.assertFalse(supported)
        self.assertIsNone(answer)

if __name__ == "__main__":
    unittest.main()
