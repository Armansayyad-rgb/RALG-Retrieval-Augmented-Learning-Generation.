"""Tests for the full-question-first hybrid retriever."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import retriever_hybrid
from retriever_hybrid import (
    MAX_SECONDARY_QUERIES,
    decompose_question,
    retrieve,
)
from retriever_v2 import build_index


CHUNKS = [
    "The kiln serial number is printed on the rear panel label near the exhaust vent.",
    "Router devices MUST forward packets within ten milliseconds under normal load.",
    "Oversized packets exceeding the MTU MUST be fragmented before transmission begins.",
    "Annual safety inspection certificates expire twelve months after the issue date.",
    "Pressure valves require calibration every six months by a certified technician.",
]


def _index():
    return build_index(CHUNKS)


class FullQuestionProtectionTests(unittest.TestCase):
    def test_full_question_top_candidate_is_protected(self):
        index, frequency = _index()
        results = retrieve(
            "Where is the kiln serial number printed on the panel?",
            CHUNKS,
            index,
            frequency,
        )
        self.assertTrue(results)
        self.assertEqual(results[0]["chunk_index"], 0)

    def test_secondary_candidate_cannot_displace_strong_primary(self):
        """A subquery-only candidate with zero full-question coverage must
        rank behind every protected primary candidate regardless of any
        heuristic advantage inside its own sub-query result set."""
        index, frequency = _index()
        question = "kiln serial number label"
        real_retrieve = retriever_hybrid.retrieve_v2

        def fake_retrieve(query, chunks, idx, df, final_top_k=10):
            base = real_retrieve(query, chunks, idx, df, final_top_k=final_top_k)
            if query != question:
                # Sub-query pass returns an unrelated chunk with an inflated score.
                inflated = [dict(row) for row in base]
                inflated.insert(0, {
                    "chunk_index": 3,
                    "final_score": 10_000.0,
                    "lexical_score": 10_000.0,
                    "chunk": CHUNKS[3],
                })
                return inflated
            return base

        with patch.object(retriever_hybrid, "retrieve_v2", side_effect=fake_retrieve):
            with patch.object(
                retriever_hybrid,
                "idf_weighted_coverage",
                wraps=retriever_hybrid.idf_weighted_coverage,
            ):
                results = retrieve(question, CHUNKS, index, frequency)
        origins_top = [row["origin"] for row in results]
        self.assertIn("full_question", origins_top)
        self.assertEqual(results[0]["origin"], "full_question")


class BoundedSecondaryTests(unittest.TestCase):
    def test_no_secondary_pass_for_well_covered_query(self):
        index, frequency = _index()
        with patch.object(
            retriever_hybrid, "retrieve_v2", wraps=retriever_hybrid.retrieve_v2
        ) as mocked:
            retrieve(
                "How often do pressure valves require calibration?",
                CHUNKS,
                index,
                frequency,
            )
        self.assertEqual(mocked.call_count, 1)

    def test_secondary_passes_are_bounded(self):
        index, frequency = _index()
        calls = []
        real_retrieve = retriever_hybrid.retrieve_v2

        def counting_retrieve(query, chunks, idx, df, final_top_k=10):
            calls.append(query)
            return real_retrieve(
                query, chunks, idx, df, final_top_k=final_top_k
            )

        with patch.object(retriever_hybrid, "retrieve_v2", side_effect=counting_retrieve):
            # A long multi-clause question that cannot be well covered.
            retrieve(
                "Router devices forward packets quickly, and oversized packets "
                "are fragmented, whereas certificates expire after twelve months",
                CHUNKS,
                index,
                frequency,
            )
        total_calls = len(calls) - 1  # minus the single full-question pass
        self.assertLessEqual(total_calls, MAX_SECONDARY_QUERIES)

    def test_decompose_returns_bounded_general_clauses(self):
        clauses = decompose_question(
            "Routers forward packets, and valves need calibration; also labels exist"
        )
        self.assertLessEqual(len(clauses), MAX_SECONDARY_QUERIES)


class DeterminismAndIdentityTests(unittest.TestCase):
    def test_ranking_is_deterministic(self):
        index, frequency = _index()
        first = retrieve("serial number kiln panel", CHUNKS, index, frequency)
        second = retrieve("serial number kiln panel", CHUNKS, index, frequency)
        self.assertEqual(first, second)

    def test_provenance_identity_retained(self):
        index, frequency = _index()
        results = retrieve("packet fragmentation MTU requirement", CHUNKS, index, frequency)
        self.assertTrue(results)
        for row in results:
            self.assertEqual(row["chunk"], CHUNKS[row["chunk_index"]])
            self.assertIn("origin", row)
            self.assertIn(row["origin"], ("full_question", "subquery"))

    def test_deduplication_of_shared_candidates(self):
        index, frequency = _index()
        results = retrieve(
            "Router devices forward packets, and packets are fragmented",
            CHUNKS,
            index,
            frequency,
        )
        indices = [row["chunk_index"] for row in results]
        self.assertEqual(len(indices), len(set(indices)))

    def test_empty_corpus_returns_empty(self):
        index, frequency = build_index([])
        self.assertEqual(retrieve("anything", [], index, frequency), [])


class LatencyGuardTests(unittest.TestCase):
    def test_single_pass_latency_guard(self):
        index, frequency = _index()
        start = time.perf_counter()
        for _ in range(20):
            retrieve("pressure valve calibration schedule", CHUNKS, index, frequency)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 20
        self.assertLess(elapsed_ms, 50.0)


if __name__ == "__main__":
    unittest.main()
