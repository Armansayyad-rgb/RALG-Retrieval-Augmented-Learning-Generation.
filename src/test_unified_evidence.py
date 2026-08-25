"""Focused tests for the shared API/UI answer and evidence contract."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
for import_path in (PROJECT_ROOT, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import api_server
from retriever_v2 import RuntimeChunk, build_index
from webui.document_processor import chunk_text
from webui.chat_handler import (
    build_answer_contract,
    format_evidence_sources,
)
from webui.hybrid_pipeline import route_through_hybrid


def runtime_chunk(text, document_id="doc-1", name="manual.txt"):
    return RuntimeChunk(
        text,
        metadata={
            "document_id": document_id,
            "document_name": name,
            "chunk_index": 0,
            "source_type": "runtime_upload",
            "extension": ".txt",
            "upload_timestamp": "2026-01-01T00:00:00.000Z",
            "page_number": None,
            "revision": None,
        },
    )


def v2_evidence(chunk):
    return {
        "kind": "v2",
        "results": [{"chunk": chunk, "chunk_index": 0, "final_score": 10.0}],
        "context": str(chunk),
    }


def pipeline():
    chunks = ["static corpus text"]
    index, frequency = build_index(chunks)
    return {
        "chunks": chunks,
        "retrieval_index": index,
        "document_frequency": frequency,
    }


class UnifiedEvidenceTests(unittest.TestCase):
    def test_api_ui_semantic_parity_for_supported_factual_query(self):
        chunk = runtime_chunk("The pump pressure limit is 10 PSI.")
        result = {
            "answer": "The pump pressure limit is 10 PSI.",
            "supported": True,
            "confidence": 0.9,
            "answer_type": "factual",
            "runtime_plan": {"intent": "general"},
            "evidence": v2_evidence(chunk),
        }
        with patch.object(api_server, "get_pipeline", return_value=pipeline()), patch.object(
            api_server, "answer_question", return_value=result
        ), patch.object(
            api_server, "collect_sources", side_effect=AssertionError("unexpected retrieval")
        ):
            api_payload = api_server.query(
                api_server.QueryRequest(question="What is the pump pressure limit?")
            ).model_dump()
        with patch(
            "webui.hybrid_pipeline.answer_question", return_value=result
        ), patch(
            "webui.hybrid_pipeline.collect_sources",
            side_effect=AssertionError("unexpected retrieval"),
        ):
            ui_turn = route_through_hybrid(
                pipeline(), "What is the pump pressure limit?", None
            )
        self.assertEqual(api_payload["supported"], ui_turn.supported)
        self.assertEqual(api_payload["answer_type"], ui_turn.answer_type)
        self.assertEqual(api_payload["traceable"], ui_turn.traceable)
        self.assertEqual(api_payload["conflict"], ui_turn.conflict)
        self.assertEqual(api_payload["sources"], ui_turn.sources)

    def test_api_ui_parity_for_unsupported_query(self):
        result = {
            "answer": "I couldn't find enough reliable evidence.",
            "supported": False,
            "confidence": None,
            "answer_type": "system",
            "runtime_plan": {"intent": "general"},
            "evidence": None,
        }
        fallback = []
        with patch.object(api_server, "get_pipeline", return_value=pipeline()), patch.object(
            api_server, "answer_question", return_value=result
        ), patch.object(api_server, "collect_sources", return_value=fallback):
            api_payload = api_server.query(
                api_server.QueryRequest(question="What is an unknown fact?")
            ).model_dump()
        with patch("webui.hybrid_pipeline.answer_question", return_value=result), patch(
            "webui.hybrid_pipeline.collect_sources", return_value=fallback
        ):
            ui_turn = route_through_hybrid(
                pipeline(), "What is an unknown fact?", None
            )
        self.assertEqual(api_payload["supported"], ui_turn.supported)
        self.assertEqual(api_payload["answer_type"], ui_turn.answer_type)
        self.assertEqual(api_payload["traceable"], ui_turn.traceable)
        self.assertEqual(api_payload["sources"], ui_turn.sources)

    def test_api_ui_parity_for_conflicting_evidence(self):
        left = runtime_chunk("The pump pressure limit is 10 PSI.", "doc-a", "a.txt")
        right = runtime_chunk("The pump pressure limit is 20 PSI.", "doc-b", "b.txt")
        evidence = {
            "kind": "hybrid",
            "results": [
                {"chunk": left, "chunk_index": 0, "lexical_score": 10.0},
                {"chunk": right, "chunk_index": 1, "lexical_score": 9.0},
            ],
            "context": f"{left}\n{right}",
        }
        result = {
            "answer": "The pump pressure limit is 10 PSI.",
            "supported": True,
            "confidence": 0.9,
            "answer_type": "factual",
            "runtime_plan": {"intent": "general"},
            "evidence": evidence,
        }
        with patch.object(api_server, "get_pipeline", return_value=pipeline()), patch.object(
            api_server, "answer_question", return_value=result
        ):
            api_payload = api_server.query(
                api_server.QueryRequest(
                    question="What is the pump pressure limit?", top_k=2
                )
            ).model_dump()
        with patch("webui.hybrid_pipeline.answer_question", return_value=result):
            ui_turn = route_through_hybrid(
                pipeline(), "What is the pump pressure limit?", None, top_k=2
            )
        self.assertFalse(api_payload["supported"])
        self.assertEqual(api_payload["answer_type"], "conflict")
        self.assertEqual(api_payload["conflict"], ui_turn.conflict)
        self.assertEqual(api_payload["sources"], ui_turn.sources)

    def test_exact_evidence_is_returned_from_answer_result(self):
        chunk = runtime_chunk("The pump pressure limit is 10 PSI.")
        result = {
            "answer": "The pump pressure limit is 10 PSI.",
            "supported": True,
            "answer_type": "factual",
            "evidence": v2_evidence(chunk),
        }
        contract = build_answer_contract(
            pipeline(), "What is the pump pressure limit?", result, 1
        )
        self.assertIs(contract.evidence, result["evidence"])
        self.assertEqual(contract.sources[0]["evidence"], str(chunk))

    def test_no_second_retrieval_for_citation_reconstruction(self):
        chunk = runtime_chunk("The pump pressure limit is 10 PSI.")
        result = {
            "answer": "The pump pressure limit is 10 PSI.",
            "supported": True,
            "answer_type": "factual",
            "evidence": v2_evidence(chunk),
        }
        with patch.object(api_server, "get_pipeline", return_value=pipeline()), patch.object(
            api_server, "answer_question", return_value=result
        ), patch.object(
            api_server, "collect_sources", side_effect=AssertionError("retrieval repeated")
        ):
            response = api_server.query(
                api_server.QueryRequest(question="What is the pump pressure limit?")
            )
        self.assertTrue(response.traceable)

    def test_polished_answer_cannot_be_supported_without_traceable_evidence(self):
        chunk = runtime_chunk("The pump pressure limit is 10 PSI.")
        result = {
            "answer": "The pump pressure limit is 10 PSI.",
            "supported": True,
            "answer_type": "factual",
            "runtime_plan": {"intent": "cause"},
            "evidence": v2_evidence(chunk),
        }
        polish = Mock()
        polish.is_ready.return_value = True
        with patch("webui.hybrid_pipeline.answer_question", return_value=result), patch(
            "webui.hybrid_pipeline.polish_hybrid_answer",
            return_value="The moon orbits Earth every month.",
        ):
            turn = route_through_hybrid(
                pipeline(), "Why is the pump limit important?", polish
            )
        self.assertEqual(turn.mode, "polish_hybrid")
        self.assertFalse(turn.supported)
        self.assertFalse(turn.traceable)

    def test_runtime_provenance_survives_shared_pipeline(self):
        chunk = runtime_chunk("The pump pressure limit is 10 PSI.")
        contract = build_answer_contract(
            pipeline(),
            "What is the pump pressure limit?",
            {
                "answer": "The pump pressure limit is 10 PSI.",
                "supported": True,
                "answer_type": "factual",
                "evidence": v2_evidence(chunk),
            },
            1,
        )
        self.assertEqual(contract.provenance[0]["document_id"], "doc-1")
        self.assertEqual(contract.provenance[0]["document_name"], "manual.txt")

    def test_hybrid_fallback_evidence_remains_attached(self):
        chunk = runtime_chunk("The pump pressure limit is 10 PSI.", name="manual.pdf")
        evidence = {
            "kind": "hybrid",
            "results": [{"chunk": chunk, "chunk_index": 0, "lexical_score": 4.0}],
            "context": str(chunk),
        }
        sources = format_evidence_sources(evidence, 1)
        self.assertEqual(sources[0]["document_id"], "doc-1")
        self.assertEqual(sources[0]["document_name"], "manual.pdf")
        self.assertEqual(sources[0]["evidence"], str(chunk))

    def test_static_source_behavior_remains_unchanged(self):
        evidence = {
            "kind": "v2",
            "results": [
                {"chunk": "static corpus text", "chunk_index": 0, "final_score": 1.0}
            ],
        }
        source = format_evidence_sources(evidence, 1)[0]
        self.assertEqual(source["evidence"], "static corpus text")
        self.assertNotIn("document_id", source)
        self.assertNotIn("metadata", source)

    def test_no_absolute_path_exposure(self):
        chunk = chunk_text(
            "The pump pressure limit is 10 PSI.",
            "doc-1",
            doc_name=r"C:\private\manual.pdf",
        )[0]
        source = format_evidence_sources(v2_evidence(chunk), 1)[0]
        self.assertNotIn("path", source)
        self.assertNotIn("C:\\", str(source))
        self.assertNotIn("/", str(source))


if __name__ == "__main__":
    unittest.main()
