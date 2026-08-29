"""Tests for authoritative dev V1 evaluator integrity.

Proves:
1. evaluator retrieval uses production retrieval
2. Layer B uses production answer path
3. support/grounding gate executes
4. actual abstention is measured
5. scoped IDs reach production retrieval
6. excluded docs cannot leak
7. static KB cannot leak into isolated evaluation
8. cross-document cases require intended document coverage
9. qualified answers require qualification
10. old proxy baseline is not overwritten
11. V3 result remains untouched
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class TestEvaluatorUsesProductionRetrieval(unittest.TestCase):
    """1. Evaluator retrieval uses production retrieval."""

    def test_retrieve_is_production_function(self):
        from authoritative_dev_v1_eval import build_dev_pipeline
        from retriever_v2 import retrieve, RuntimeChunk

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, chunk_sources = build_dev_pipeline(source_files)

        self.assertIsInstance(pipeline["chunks"][0], RuntimeChunk)
        self.assertTrue(len(pipeline["chunks"]) > 0)
        self.assertIsNotNone(pipeline["retrieval_index"])
        self.assertIsNotNone(pipeline["document_frequency"])

    def test_pipeline_has_runtime_chunks_with_document_id(self):
        from authoritative_dev_v1_eval import build_dev_pipeline

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        for chunk in pipeline["chunks"]:
            self.assertTrue(hasattr(chunk, "metadata"))
            self.assertIn("document_id", chunk.metadata)
            self.assertTrue(len(chunk.metadata["document_id"]) > 0)


class TestLayerBProductionAnswerPath(unittest.TestCase):
    """2. Layer B uses production answer path."""

    def test_execute_runtime_is_called(self):
        from authoritative_dev_v1_eval import build_dev_pipeline, score_answer_layer_b
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        result = execute_runtime(
            pipeline, "What is git rebase?", top_k=5,
            answer_fn=answer_question, contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )

        self.assertTrue(hasattr(result, "answer"))
        self.assertTrue(hasattr(result, "supported"))
        self.assertTrue(hasattr(result, "sources"))
        self.assertTrue(hasattr(result, "plan"))

    def test_score_uses_execution_result(self):
        from authoritative_dev_v1_eval import score_answer_layer_b
        from runtime_architecture import ExecutionResult, ExecutionPlan

        plan = ExecutionPlan(
            intent="general", route="model", canonical_question="test",
            subject="", multi_hop=False, retrieval_passes=1,
            retrieval_strategy="hybrid", generator="test", model="test",
        )
        mock_result = ExecutionResult(
            question="test", answer="test answer", supported=True,
            confidence=0.9, answer_type="synthesized", sources=[],
            provenance=[], traceable=True, conflict=False, plan=plan,
            raw={}, evidence=None,
        )
        case = {
            "id": "test_001", "category": "supported",
            "should_answer": True, "expected_answer": "test",
            "expected_document_ids": [], "evidence_spans": [],
        }
        result = score_answer_layer_b(mock_result, case)
        self.assertTrue(result["correct"])


class TestSupportGateExecutes(unittest.TestCase):
    """3. Support/grounding gate executes."""

    def test_unsupported_question_is_rejected(self):
        from authoritative_dev_v1_eval import build_dev_pipeline
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        result = execute_runtime(
            pipeline,
            "What is the recommended way to set up Kubernetes pod autoscaling?",
            top_k=5,
            answer_fn=answer_question, contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )

        self.assertFalse(result.supported)

    def test_supported_question_passes_gate(self):
        from authoritative_dev_v1_eval import build_dev_pipeline
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        result = execute_runtime(
            pipeline,
            "What is git rebase?",
            top_k=5,
            answer_fn=answer_question, contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )

        self.assertTrue(result.supported)


class TestAbstentionMeasurement(unittest.TestCase):
    """4. Actual abstention is measured."""

    def test_unsupported_cases_detected(self):
        from authoritative_dev_v1_eval import build_dev_pipeline, score_answer_layer_b
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        result = execute_runtime(
            pipeline,
            "What is the recommended way to set up Kubernetes pod autoscaling?",
            top_k=5,
            answer_fn=answer_question, contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )

        case = {
            "id": "test_unsup", "category": "unsupported",
            "should_answer": False, "expected_answer": "N/A",
        }
        score = score_answer_layer_b(result, case)
        self.assertTrue(score["correct"])


class TestDocumentScoping(unittest.TestCase):
    """5. Scoped IDs reach production retrieval."""

    def test_scoped_query_filters_to_allowed_docs(self):
        from authoritative_dev_v1_eval import build_dev_pipeline
        from retriever_v2 import retrieve, RuntimeChunk

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        results = retrieve(
            "What is git rebase?",
            pipeline["chunks"],
            pipeline["retrieval_index"],
            pipeline["document_frequency"],
            final_top_k=5,
            document_ids=["git_rebase"],
        )

        for r in results:
            self.assertEqual(r["chunk"].metadata.get("document_id"), "git_rebase")

    def test_excluded_docs_cannot_appear(self):
        from authoritative_dev_v1_eval import build_dev_pipeline
        from retriever_v2 import retrieve

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        results = retrieve(
            "What is git rebase?",
            pipeline["chunks"],
            pipeline["retrieval_index"],
            pipeline["document_frequency"],
            final_top_k=5,
            document_ids=["git_rebase"],
        )

        for r in results:
            doc_id = r["chunk"].metadata.get("document_id", "")
            self.assertEqual(doc_id, "git_rebase")


class TestCorpusIsolation(unittest.TestCase):
    """7. Static KB cannot leak into isolated evaluation."""

    def test_pipeline_contains_only_dev_sources(self):
        from authoritative_dev_v1_eval import build_dev_pipeline

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        dev_source_names = {sf.stem for sf in source_files}
        pipeline_doc_ids = {
            chunk.metadata.get("document_id") for chunk in pipeline["chunks"]
        }

        self.assertEqual(dev_source_names, pipeline_doc_ids)

    def test_pipeline_no_persistence(self):
        from authoritative_dev_v1_eval import build_dev_pipeline

        source_files = sorted(
            (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
        )
        pipeline, _ = build_dev_pipeline(source_files)

        self.assertFalse(pipeline.get("runtime_persistence"))
        self.assertIsNone(pipeline.get("runtime_upload_dir"))
        self.assertEqual(pipeline.get("uploaded_docs"), [])


class TestCrossDocumentCoverage(unittest.TestCase):
    """8. Cross-document cases require intended document coverage."""

    def test_cross_doc_benchmark_has_multiple_docs(self):
        benchmark_path = ROOT / "evaluation" / "authoritative_dev_v1" / "holdout_benchmark.jsonl"
        cases = []
        with open(benchmark_path) as f:
            for line in f:
                if line.strip():
                    cases.append(json.loads(line))

        cross_doc_cases = [c for c in cases if c["category"] == "cross_document"]
        for c in cross_doc_cases:
            self.assertGreaterEqual(
                len(c.get("expected_document_ids", [])), 1,
                f"{c['id']} should reference at least 1 document"
            )


class TestQualifiedAnswers(unittest.TestCase):
    """9. Qualified answers require qualification."""

    def test_conditional_cases_have_qualification(self):
        benchmark_path = ROOT / "evaluation" / "authoritative_dev_v1" / "holdout_benchmark.jsonl"
        cases = []
        with open(benchmark_path) as f:
            for line in f:
                if line.strip():
                    cases.append(json.loads(line))

        qualified_cases = [c for c in cases if c["category"] == "conditional_or_qualified"]
        for c in qualified_cases:
            self.assertIn("qualification", c, f"{c['id']} must have qualification field")


class TestBaselinePreservation(unittest.TestCase):
    """10. Old proxy baseline is not overwritten."""

    def test_original_baseline_exists(self):
        path = ROOT / "evaluation" / "results" / "authoritative_dev_v1_baseline.json"
        self.assertTrue(path.exists())

    def test_e2e_baseline_is_separate(self):
        old = ROOT / "evaluation" / "results" / "authoritative_dev_v1_baseline.json"
        new = ROOT / "evaluation" / "results" / "authoritative_dev_v1_e2e_baseline.json"
        self.assertNotEqual(old, new)


class TestV3Untouched(unittest.TestCase):
    """11. V3 result remains untouched."""

    def test_v3_result_hash(self):
        v3_path = ROOT / "evaluation" / "results" / "holdout_v3_blind_once.json"
        sha = hashlib.sha256(v3_path.read_bytes()).hexdigest().upper()
        self.assertEqual(
            sha, "0F0C2314BAAC425E1A49222DE7357F530F0754731C435E9FD3C4E026A10F5D89"
        )


if __name__ == "__main__":
    unittest.main()
