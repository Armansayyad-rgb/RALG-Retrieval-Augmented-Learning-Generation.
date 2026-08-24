"""Correctness and work-reduction tests for the exact retrieval index."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from retriever_v2 import (  # noqa: E402
    INGESTED_CHUNK_BOOST,
    RuntimeChunk,
    build_index,
    lexical_score,
    retrieve,
    retrieve_candidates,
)
from retriever_v4 import merge_results  # noqa: E402
from rag_chat_v2 import answer_question, extract_factual_answer  # noqa: E402
from webui.document_processor import (  # noqa: E402
    UploadedDocument,
    attach_documents,
    remove_uploaded_document,
    restore_persisted_documents,
)


class RetrievalPerformanceTests(unittest.TestCase):
    def test_postings_match_previous_exact_candidate_order_and_scores(self):
        chunks = [
            "alpha beta shared evidence",
            "alpha only evidence",
            "beta only evidence",
            RuntimeChunk("runtime unrelated", metadata={"document_id": "r1"}),
            "no matching terms here",
        ]
        index, frequency = build_index(chunks)
        question = "alpha beta"

        expected = []
        for i, counts in enumerate(index):
            score = lexical_score(question, counts, frequency, len(chunks))
            if score <= 0:
                continue
            if isinstance(chunks[i], RuntimeChunk):
                score += INGESTED_CHUNK_BOOST
            if score > 0:
                expected.append((score, score - (INGESTED_CHUNK_BOOST if isinstance(chunks[i], RuntimeChunk) else 0), 0.0, i, chunks[i]))
        expected.sort(key=lambda item: (item[0], item[1]), reverse=True)
        actual = retrieve_candidates(question, chunks, index, frequency, top_k=20)
        self.assertEqual([item[3] for item in actual], [item[3] for item in expected])
        self.assertEqual([item[0] for item in actual], [item[0] for item in expected])

    def test_runtime_boost_and_provenance_survive_postings(self):
        chunk = RuntimeChunk(
            "pump pressure limit is 10 PSI",
            metadata={"document_id": "doc-1", "chunk_index": 0},
        )
        chunks = ["pump pressure limit is 10 PSI", chunk]
        index, frequency = build_index(chunks)
        results = retrieve("pump pressure limit", chunks, index, frequency)
        self.assertEqual(results[0]["chunk"], chunk)
        self.assertEqual(
            results[0]["final_score"] - retrieve(
                "pump pressure limit", chunks[:1],
                *build_index(chunks[:1]),
            )[0]["final_score"],
            INGESTED_CHUNK_BOOST,
        )
        self.assertEqual(results[0]["chunk"].metadata["document_id"], "doc-1")

    def test_unknown_terms_and_static_corpus_are_safe(self):
        chunks = ["static corpus has known evidence"]
        index, frequency = build_index(chunks)
        self.assertEqual(retrieve("zzzzzz unknown", chunks, index, frequency), [])
        self.assertEqual(len(retrieve("known evidence", chunks, index, frequency)), 1)

    def test_named_fact_cannot_borrow_support_from_adjacent_sentence(self):
        context = (
            "RC-ONLY calibration marker requires 17 kPa before service. "
            "Since 1994, Hurricane Ioke had a lower central pressure."
        )
        answer, supported = extract_factual_answer(
            "What pressure does RC-ONLY calibration marker require?",
            context,
        )
        self.assertEqual(answer, "RC-ONLY calibration marker requires 17 kPa before service")
        self.assertTrue(supported)

    def test_failed_factual_grounding_does_not_fall_through_to_generic_extractor(self):
        pipeline = {
            "device": "cpu",
            "tokenizer": None,
            "model": None,
            "chunks": ["LUMEN ARC-12 uses Vireo-22 coolant."],
            "retrieval_index": [],
            "document_frequency": {},
        }
        retrieval = {
            "kind": "v2",
            "results": [
                {
                    "chunk": pipeline["chunks"][0],
                    "chunk_index": 0,
                    "final_score": 1.0,
                }
            ],
            "context": pipeline["chunks"][0],
        }
        with patch("rag_chat_v2.runtime_plan", return_value={"intent": "general"}), \
                patch("rag_chat_v2.retrieve_v4", return_value=retrieval), \
                patch("rag_chat_v2.extract_factual_answer", return_value=(None, False)), \
                patch("rag_chat_v2.extract_answer", return_value="unrelated answer") as generic:
            result = answer_question(
                pipeline,
                "Which coolant is approved for the Lumen ARC-12?",
                verbose=False,
            )
        self.assertFalse(result["supported"])
        self.assertEqual(result["answer_type"], "system")
        generic.assert_not_called()

    def test_factual_subject_cannot_borrow_predicate_from_other_sentence(self):
        context = (
            "Newton described the Moon in his notebooks. "
            "The equipment warranty period is twelve months."
        )
        answer, supported = extract_factual_answer(
            "What is the warranty period for the moon?",
            context,
        )
        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_factual_subject_cannot_borrow_population_predicate_from_other_sentence(self):
        context = (
            "Ceres is an asteroid in the asteroid belt. "
            "Mars has a population of more than thirty million residents."
        )
        answer, supported = extract_factual_answer(
            "What is the population of Ceres?",
            context,
        )
        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_v4_duplicate_queries_are_retrieved_once(self):
        chunks = ["alpha evidence sentence with enough content"]
        index, frequency = build_index(chunks)
        with patch("retriever_v4.retrieve_v2", wraps=__import__("retriever_v2").retrieve) as mocked:
            output = merge_results(
                ["alpha evidence", " ALPHA   evidence "],
                chunks,
                index,
                frequency,
                collect_timings=True,
            )
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(len(output["results"]), 1)
        self.assertTrue(output["timings"]["queries"][1]["cache_hit"])

    def test_upload_updates_postings_and_delete_removes_them(self):
        pipeline = {"chunks": ["static evidence"], "uploaded_docs": []}
        pipeline["retrieval_index"], pipeline["document_frequency"] = build_index(pipeline["chunks"])
        doc = UploadedDocument(
            "manual.txt", Path("manual.txt"), ".txt",
            "distinct pump pressure limit evidence " * 30,
        )
        added = attach_documents(pipeline, [doc], persist=False)
        self.assertGreater(added, 0)
        self.assertTrue(retrieve("distinct pump pressure", pipeline["chunks"], pipeline["retrieval_index"], pipeline["document_frequency"]))
        self.assertEqual(remove_uploaded_document(pipeline, doc.doc_id), added)
        self.assertEqual(retrieve("distinct pump pressure", pipeline["chunks"], pipeline["retrieval_index"], pipeline["document_frequency"]), [])
        self.assertEqual(pipeline["chunks"], ["static evidence"])

    def test_persistence_rebuilds_postings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = {
                "chunks": [],
                "uploaded_docs": [],
                "runtime_persistence": True,
                "runtime_upload_dir": root,
            }
            pipeline["retrieval_index"], pipeline["document_frequency"] = build_index([])
            doc = UploadedDocument("persist.txt", root / "persist.txt", ".txt", "restart marker evidence " * 30)
            attach_documents(pipeline, [doc])
            restored = restore_persisted_documents(pipeline)
            recreated = {"chunks": [], "uploaded_docs": [], "runtime_persistence": True, "runtime_upload_dir": root}
            recreated["retrieval_index"], recreated["document_frequency"] = build_index([])
            attach_documents(recreated, restored, persist=False)
            self.assertTrue(retrieve("restart marker", recreated["chunks"], recreated["retrieval_index"], recreated["document_frequency"]))


if __name__ == "__main__":
    unittest.main()
