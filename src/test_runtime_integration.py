"""Integration tests: API and WebUI both flow through execute_runtime and
the authoritative hybrid retrieval path.

These tests are dependency-light: heavy callables are stubbed, and the
retrieval delegation is proven functionally against a tiny in-memory
corpus.
"""

import sys
import types
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from runtime_architecture import execute_runtime  # noqa: E402


def _contract_from(result):
    from types import SimpleNamespace
    return SimpleNamespace(
        answer=result.get("answer", ""),
        supported=result.get("supported", False),
        confidence=result.get("confidence"),
        answer_type=result.get("answer_type", "unknown"),
        sources=result.get("sources", []),
        provenance=result.get("provenance", []),
        traceable=result.get("traceable", False),
        conflict=result.get("conflict", False),
        evidence=result.get("evidence"),
        error=None,
    )


class ApiUsesExecuteRuntimeTests(unittest.TestCase):
    """1. The API query endpoint goes through execute_runtime."""

    def test_api_query_routes_through_execute_runtime(self):
        import api_server

        calls = []

        def fake_execute(pipeline, question, top_k, **kwargs):
            calls.append({"pipeline": pipeline, "question": question,
                          "top_k": top_k, **kwargs})
            return types.SimpleNamespace(
                answer="a", supported=True, confidence=0.9,
                answer_type="extracted", sources=[], provenance=[],
                traceable=True, conflict=False, plan=None, raw={},
                evidence=None, error=None,
                observability={"latency_ms": 0.0},
                multi_hop_trace=None,
            )

        original = api_server.execute_runtime
        original_pipeline = api_server._PIPELINE
        api_server.execute_runtime = fake_execute
        api_server._PIPELINE = {"marker": True}
        try:
            response = api_server.query(
                api_server.QueryRequest(question="What is X?", top_k=3)
            )
        finally:
            api_server.execute_runtime = original
            api_server._PIPELINE = original_pipeline

        self.assertEqual(response.supported, True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["question"], "What is X?")
        # Same shared contract/source functions as the WebUI (parity).
        from webui.chat_handler import build_answer_contract, collect_sources
        self.assertIs(calls[0]["contract_fn"], build_answer_contract)
        self.assertIs(calls[0]["sources_fn"], collect_sources)


class WebUIUsesExecuteRuntimeTests(unittest.TestCase):
    """2. The WebUI chat turn goes through the same execute_runtime."""

    def test_chat_turn_routes_through_execute_runtime(self):
        import webui.chat_handler as chat_handler

        calls = []
        real_execute = chat_handler.execute_runtime

        def fake_execute(pipeline, question, top_k, **kwargs):
            calls.append({"question": question, "top_k": top_k, **kwargs})
            return real_execute(
                pipeline, question, top_k,
                answer_fn=lambda *_a, **_k: {
                    "answer": "generator", "supported": True,
                    "traceable": True,
                    "evidence": {"kind": "hybrid", "results": [{
                        "chunk": "The generator must reach stable voltage.",
                        "chunk_index": 0, "lexical_score": 1.0,
                        "full_question_coverage": 0.8,
                    }]},
                    "runtime_plan": {"intent": "general"},
                },
                contract_fn=chat_handler.build_answer_contract,
                sources_fn=lambda *_a, **_k: [],
            )

        chat_handler.execute_runtime = fake_execute
        try:
            turn = chat_handler.chat_turn({}, "What is X?", 3)
        finally:
            chat_handler.execute_runtime = real_execute

        self.assertEqual(len(calls), 1)
        self.assertEqual(turn["answer"], "generator")
        self.assertTrue(turn["supported"])
        self.assertIn("observability", turn)
        # API/UI parity: identical injected functions.
        import api_server
        import inspect
        api_src = inspect.getsource(api_server.query)
        self.assertIn("execute_runtime", api_src)
        self.assertIs(chat_handler.answer_question, __import__(
            "rag_chat_v2", fromlist=["answer_question"]).answer_question)


class HybridAuthoritativeRetrievalTests(unittest.TestCase):
    """3/5/13. One authoritative hybrid retrieval path; no bypass."""

    def test_retrieve_for_reasoning_delegates_to_hybrid(self):
        import rag_chat_v2
        import retriever_hybrid

        chunks = [
            "The alpha router must forward packets within 10 milliseconds.",
            "Kiln serial numbers are printed on the rear panel label.",
            "Packets exceeding the MTU must be fragmented before transit.",
        ]

        seen_calls = []
        real = rag_chat_v2.retrieve_hybrid

        def spy(*args, **kwargs):
            seen_calls.append(True)
            return real(*args, **kwargs)

        rag_chat_v2.retrieve_hybrid = spy
        try:
            index, df = __import__("retriever_v2").build_index(chunks)
            retrieval = rag_chat_v2.retrieve_for_reasoning(
                "What must routers do with oversized packets?",
                chunks, index, df,
            )
        finally:
            rag_chat_v2.retrieve_hybrid = real

        self.assertTrue(seen_calls, "hybrid retriever was not called")
        self.assertIsNotNone(retrieval)
        self.assertTrue(retrieval["results"])
        self.assertEqual(retrieval["best"]["chunk"], retrieval["results"][0]["chunk"])
        self.assertTrue(retrieval["context"])

    def test_reasoning_evidence_is_marked_hybrid(self):
        import rag_chat_v2

        chunks = [
            "The generator must reach stable voltage before load is applied.",
            "Water treatment chemicals are stored separately from fuel.",
        ]
        index, df = __import__("retriever_v2").build_index(chunks)
        retrieval = rag_chat_v2.retrieve_for_reasoning(
            "When is load applied to the generator?", chunks, index, df,
        )
        self.assertIsNotNone(retrieval)
        self.assertEqual(retrieval["retriever"], "hybrid")

    def test_collect_sources_falls_back_to_hybrid_not_v4(self):
        import webui.chat_handler as chat_handler

        source = Path(chat_handler.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from retriever_v4", source)
        self.assertNotIn("retrieve_v4_fn", source)
        self.assertIn("retrieve_hybrid_fn", source)

    def test_no_duplicate_routing_decision_in_one_turn(self):
        answer_calls = []
        source_calls = []

        def answer_fn(_p, _q, **_k):
            answer_calls.append(1)
            return {
                "answer": "grounded",
                "supported": True,
                "traceable": True,
                "evidence": {"kind": "hybrid", "results": [{"chunk": "c"}]},
                "runtime_plan": {"intent": "general"},
            }

        def contract_fn(_p, _q, result, *_a, **_k):
            return _contract_from({**result, "traceable": True})

        def sources_fn(*_a, **_k):
            source_calls.append(1)
            return []

        execution = execute_runtime(
            {}, "question", 3,
            answer_fn=answer_fn,
            contract_fn=contract_fn,
            sources_fn=sources_fn,
        )
        self.assertEqual(len(answer_calls), 1)
        self.assertEqual(len(source_calls), 0)
        self.assertTrue(execution.supported)


class SupportGateAbstentionTests(unittest.TestCase):
    """6-9. The unified support gate stays authoritative."""

    @staticmethod
    def _run(raw, sources=None, provenance=None, conflict=False):
        def answer_fn(_p, _q, **_k):
            return raw

        def contract_fn(_p, _q, result, *_a, **_k):
            ns = _contract_from(result)
            ns.sources = sources if sources is not None else result.get("sources", [])
            ns.provenance = (
                provenance if provenance is not None
                else result.get("provenance", [])
            )
            ns.conflict = conflict
            return ns

        def sources_fn(*_a, **_k):
            return sources or []

        return execute_runtime(
            {}, "question", 3,
            answer_fn=answer_fn,
            contract_fn=contract_fn,
            sources_fn=sources_fn,
        )

    def test_conflicting_evidence_abstains(self):
        raw = {
            "answer": "42 volts", "supported": True, "traceable": True,
            "evidence": {"kind": "hybrid"}, "runtime_plan": {"intent": "general"},
        }
        execution = self._run(raw, conflict=True)
        self.assertFalse(execution.supported)
        self.assertTrue(execution.conflict)

    def test_missing_provenance_abstains(self):
        raw = {
            "answer": "42 volts", "supported": True, "traceable": True,
            "runtime_plan": {"intent": "general"},
        }
        execution = self._run(raw, provenance=[])
        self.assertFalse(execution.supported)

    def test_unsupported_query_abstains(self):
        raw = {
            "answer": "guess", "supported": False,
            "evidence": {"kind": "hybrid"}, "runtime_plan": {"intent": "general"},
        }
        execution = self._run(raw)
        self.assertFalse(execution.supported)
        self.assertIn("abstained", execution.observability)
        self.assertTrue(execution.observability["abstained"])


class HybridProvenanceTests(unittest.TestCase):
    """10. Provenance survives the hybrid retrieval path."""

    def test_hybrid_sources_carry_provenance_metadata(self):
        from webui.chat_handler import format_evidence_sources
        from retriever_v2 import RuntimeChunk

        chunk = RuntimeChunk("Generator load steps follow stable voltage.")
        chunk.metadata = {
            "document_id": "doc-1", "document_name": "manual.txt",
            "chunk_index": 4, "page_number": 2, "source_type": "upload",
            "extension": ".txt", "upload_timestamp": 123, "revision": 0,
        }
        evidence = {
            "kind": "hybrid",
            "results": [{
                "chunk": chunk, "chunk_index": 4,
                "lexical_score": 3.2, "origin": "full_question",
                "full_question_coverage": 0.9,
            }],
        }
        sources = format_evidence_sources(evidence, 5)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["document_id"], "doc-1")
        self.assertEqual(sources[0]["chunk_index"], 4)
        self.assertGreater(sources[0]["score"], 0)


class HybridQualityNotBypassedTests(unittest.TestCase):
    """13. Production modules must not wire a second grounded retriever."""

    def test_api_and_webui_do_not_import_retriever_v4(self):
        for module in ("api_server", "webui.chat_handler", "webui.hybrid_pipeline"):
            source = (SRC / f"{module.replace('.', '/')}.py").read_text(encoding="utf-8")
            self.assertNotIn("retriever_v4", source, module)

    def test_rag_chat_v2_reasoning_path_has_single_retrieval_entry(self):
        source = (SRC / "rag_chat_v2.py").read_text(encoding="utf-8")
        self.assertNotIn("retrieve_v4(", source)
        self.assertIn("retrieve_hybrid(", source)


if __name__ == "__main__":
    unittest.main()
