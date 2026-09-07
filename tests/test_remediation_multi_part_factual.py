import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag_chat_v2 import answer_question, extract_factual_answer
from retriever_v2 import RuntimeChunk, build_index


def _pipeline_from_chunks(chunks):
    runtime_chunks = [
        RuntimeChunk(
            text,
            metadata={
                "document_id": document_id,
                "document_name": document_id,
                "chunk_index": index,
                "source_type": "runtime_upload",
            },
        )
        for index, (document_id, text) in enumerate(chunks)
    ]
    index, doc_freq = build_index(runtime_chunks)
    return {
        "device": "cpu",
        "tokenizer": None,
        "model": None,
        "chunks": runtime_chunks,
        "retrieval_index": index,
        "document_frequency": doc_freq,
        "uploaded_docs": [],
        "runtime_persistence": False,
        "runtime_upload_dir": None,
    }


class MultiPartFactualRemediationTests(unittest.TestCase):

    def test_two_facts_same_document_different_sections_supported(self):
        question = (
            "What are the operating pressure and coolant type for the Lyra valve?"
        )
        context = (
            "Section A - Pressure. The operating pressure for the Lyra valve "
            "is 42 kilopascals.\n"
            "Section B - Cooling. The coolant type for the Lyra valve is "
            "amber glycol."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertTrue(supported)
        self.assertIn("42 kilopascals", answer.lower())
        self.assertIn("amber glycol", answer.lower())

    def test_two_facts_each_individually_grounded_survive_composition(self):
        question = (
            "What are the seal material and firmware channel for the Orin pump?"
        )
        context = (
            "The seal material for the Orin pump is blue ceramic. "
            "The firmware channel for the Orin pump is delta-ring."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertTrue(supported)
        self.assertIn("seal material", answer.lower())
        self.assertIn("blue ceramic", answer.lower())
        self.assertIn("firmware channel", answer.lower())
        self.assertIn("delta-ring", answer.lower())

    def test_first_fact_present_second_fact_absent_abstains(self):
        question = (
            "What are the operating pressure and calibration interval "
            "for the Lyra valve?"
        )
        context = (
            "The operating pressure for the Lyra valve is 42 kilopascals. "
            "The Lyra valve appears in the maintenance index."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_two_facts_different_chunks_preserve_supporting_provenance(self):
        question = (
            "What are the operating pressure and coolant type for the Lyra valve?"
        )
        pipeline = _pipeline_from_chunks([
            (
                "lyra_manual",
                "Pressure section. The operating pressure for the Lyra valve "
                "is 42 kilopascals.",
            ),
            (
                "lyra_manual",
                "Cooling section. The coolant type for the Lyra valve is "
                "amber glycol.",
            ),
        ])

        result = answer_question(pipeline, question, verbose=False)

        self.assertTrue(result["supported"])
        self.assertIn("42 kilopascals", result["answer"].lower())
        self.assertIn("amber glycol", result["answer"].lower())
        evidence_text = "\n".join(
            item.get("chunk", "")
            for item in result["evidence"]["results"]
            if isinstance(item, dict)
        ).lower()
        self.assertIn("operating pressure", evidence_text)
        self.assertIn("coolant type", evidence_text)

    def test_distractor_document_not_part_of_composed_answer(self):
        question = (
            "What are the operating pressure and coolant type for the Lyra valve?"
        )
        context = (
            "The operating pressure for the Lyra valve is 42 kilopascals. "
            "The coolant type for the Lyra valve is amber glycol. "
            "The Lyra valve travel poster mentions silver beaches."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertTrue(supported)
        self.assertNotIn("silver beaches", answer.lower())

    def test_single_fact_question_remains_supported(self):
        question = "What is the operating pressure for the Lyra valve?"
        context = (
            "The operating pressure for the Lyra valve is 42 kilopascals."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertTrue(supported)
        self.assertEqual(
            "the operating pressure for the lyra valve is 42 kilopascals",
            answer.lower().rstrip("."),
        )

    def test_subject_only_distractor_cannot_satisfy_requested_attributes(self):
        question = (
            "What are the operating pressure and coolant type for the Lyra valve?"
        )
        context = (
            "The Lyra valve is a compact device in the north cabinet. "
            "The operating pressure for the Lyra valve is 42 kilopascals."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_unsupported_conjunction_abstains(self):
        question = (
            "What are the reset code and standby current for the Mavo relay?"
        )
        context = (
            "The Mavo relay reset log was reviewed by the technician. "
            "The standby label for the Mavo relay is printed in green."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_qualifier_preservation(self):
        question = (
            "What are the maximum standby current and approved storage "
            "temperature for the Mavo relay?"
        )
        context = (
            "The maximum standby current for the Mavo relay is 8 milliamps. "
            "The approved storage temperature for the Mavo relay is "
            "5 degrees Celsius."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertTrue(supported)
        self.assertIn("maximum standby current", answer.lower())
        self.assertIn("approved storage temperature", answer.lower())

    def test_completeness_all_required_subclaims_present(self):
        question = (
            "What are the gasket color, boot mode, and service port "
            "for the Nilo sensor?"
        )
        context = (
            "The gasket color for the Nilo sensor is violet. "
            "The boot mode for the Nilo sensor is guarded-start. "
            "The service port for the Nilo sensor is port 731."
        )

        answer, supported = extract_factual_answer(question, context)

        self.assertTrue(supported)
        for expected in ("violet", "guarded-start", "port 731"):
            self.assertIn(expected, answer.lower())


if __name__ == "__main__":
    unittest.main()
