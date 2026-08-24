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
