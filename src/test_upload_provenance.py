"""Focused upload limits, provenance, isolation, and compatibility checks."""

import tempfile
import unittest
import sys
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
for import_path in (PROJECT_ROOT, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from retriever_v2 import (
    INGESTED_CHUNK_BOOST,
    RuntimeChunk,
    build_index,
    retrieve,
    retrieve_candidates,
)
from src.webui.chat_handler import _format_v2_sources, _format_hybrid_sources
from src.webui.app import _format_kb_table
from src.webui.document_processor import (
    MAX_TXT_SIZE,
    UploadedDocument,
    attach_documents,
    chunk_text,
    process_uploads,
    remove_uploaded_document,
)
from config import UPLOAD_POLICY, UploadPolicy


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _ArtifactIndependentCommercialClient:
    def __init__(self, cases):
        self._cases = {case["question"]: case for case in cases}

    def post(self, path, json):
        if path == "/ingest":
            return _FakeResponse({"document_id": "synthetic"})
        case = self._cases[json["question"]]
        supported = bool(case["supported"])
        if supported:
            answer = " ".join(
                group[0] for group in case.get("required_answer_groups", [])
            )
            evidence = " ".join(case.get("required_source_terms", []))
        else:
            answer = "I couldn't find enough reliable evidence in the current knowledge base."
            evidence = ""
        return _FakeResponse({
            "answer": answer,
            "supported": supported,
            "answer_type": "synthetic",
            "sources": [{"evidence": evidence}] if evidence else [],
            "latency_ms": 0.0,
            "error": None,
        })


def make_pipeline(runtime_dir: Path) -> dict:
    return {
        "chunks": [],
        "retrieval_index": build_index([]),
        "document_frequency": {},
        "uploaded_docs": [],
        "runtime_persistence": True,
        "runtime_upload_dir": runtime_dir,
    }


class UploadProvenanceTests(unittest.TestCase):
    def test_commercial_validation_is_isolated_and_repeatable(self):
        runtime_dir = PROJECT_ROOT / "data" / "runtime_uploads"

        def snapshot(path: Path) -> dict[str, bytes]:
            if not path.exists():
                return {}
            return {
                str(item.relative_to(path)): item.read_bytes()
                for item in path.rglob("*")
                if item.is_file()
            }

        before = snapshot(runtime_dir)
        with tempfile.TemporaryDirectory() as output_dir:
            first_path = Path(output_dir) / "first.json"
            second_path = Path(output_dir) / "second.json"
            from scripts import run_commercial_validation
            dataset = json.loads(
                run_commercial_validation.DATASET.read_text(encoding="utf-8")
            )
            first_client = _ArtifactIndependentCommercialClient(dataset["cases"])
            second_client = _ArtifactIndependentCommercialClient(dataset["cases"])
            first_result = run_commercial_validation.main(
                first_path,
                pipeline_override=make_pipeline(Path(output_dir) / "runtime-one"),
                client_override=first_client,
            )
            second_result = run_commercial_validation.main(
                second_path,
                pipeline_override=make_pipeline(Path(output_dir) / "runtime-two"),
                client_override=second_client,
            )
            self.assertEqual(first_result, 0)
            self.assertEqual(second_result, 0)
            first_report = json.loads(first_path.read_text(encoding="utf-8"))
            second_report = json.loads(second_path.read_text(encoding="utf-8"))
        self.assertTrue(first_report["metrics"]["quality_gate_passed"])
        self.assertTrue(second_report["metrics"]["quality_gate_passed"])
        self.assertEqual(
            first_report["metrics"]["cases"],
            second_report["metrics"]["cases"],
        )
        deterministic_fields = (
            "id", "expected_supported", "actual_supported", "answer",
            "answer_type", "retrieval_correct", "answer_complete",
            "safely_abstained", "source_count", "error",
        )
        self.assertEqual(
            [
                {field: item[field] for field in deterministic_fields}
                for item in first_report["results"]
            ],
            [
                {field: item[field] for field in deterministic_fields}
                for item in second_report["results"]
            ],
        )
        self.assertEqual(snapshot(runtime_dir), before)

    def test_upload_size_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            for filename, limit in (
                ("large.txt", MAX_TXT_SIZE),
                ("large.pdf", 10 * 1024 * 1024),
                ("large.docx", 10 * 1024 * 1024),
            ):
                path = Path(directory) / filename
                with path.open("wb") as handle:
                    handle.seek(limit)
                    handle.write(b"x")
                parsed, errors = process_uploads({}, [str(path)])
                self.assertEqual(parsed, [])
                self.assertIn("exceeds size limit", errors[0])

    def test_extracted_text_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expanded.txt"
            path.write_text("small source", encoding="utf-8")
            with patch(
                "src.webui.document_processor.parse_file",
                return_value="x" * (5_000_000 + 1),
            ):
                parsed, errors = process_uploads({}, [str(path)])
        self.assertEqual(parsed, [])
        self.assertIn("exceeds maximum allowed length", errors[0])

    def test_unsupported_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manual.exe"
            path.write_text("content", encoding="utf-8")
            parsed, errors = process_uploads({}, [str(path)])
        self.assertEqual(parsed, [])
        self.assertIn("Unsupported file type", errors[0])

    def test_empty_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.txt"
            path.write_text(" \r\n\t", encoding="utf-8")
            parsed, errors = process_uploads({}, [str(path)])
        self.assertEqual(parsed, [])
        self.assertIn("no extractable text", errors[0])

    def test_malformed_pdf_and_docx_fail_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "broken.pdf"
            docx = Path(directory) / "broken.docx"
            pdf.write_bytes(b"not a PDF")
            docx.write_bytes(b"not a DOCX")
            parsed, errors = process_uploads({}, [str(pdf), str(docx)])
        self.assertEqual(parsed, [])
        self.assertEqual(errors, ["Unable to parse uploaded file."] * 2)

    def test_batch_size_exact_boundary_and_one_byte_over(self):
        policy = UploadPolicy(
            UPLOAD_POLICY.allowed_extensions, UPLOAD_POLICY.per_file_bytes, 8,
            UPLOAD_POLICY.max_extracted_text_chars,
            UPLOAD_POLICY.max_chunks_per_document,
            UPLOAD_POLICY.max_total_chunks_per_batch,
        )
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "one.txt"
            second = Path(directory) / "two.txt"
            first.write_bytes(b"1234")
            second.write_bytes(b"1234")
            with patch("src.webui.document_processor.UPLOAD_POLICY", policy), patch(
                "src.webui.document_processor.parse_file", return_value="text"
            ):
                parsed, errors = process_uploads({}, [str(first), str(second)])
                self.assertEqual(len(parsed), 2)
                self.assertEqual(errors, [])
                second.write_bytes(b"12345")
                parsed, errors = process_uploads({}, [str(first), str(second)])
        self.assertEqual(parsed, [])
        self.assertIn("total size limit", errors[0])

    def test_batch_chunk_overflow_is_rejected(self):
        policy = UploadPolicy(
            UPLOAD_POLICY.allowed_extensions, UPLOAD_POLICY.per_file_bytes,
            UPLOAD_POLICY.max_batch_bytes, UPLOAD_POLICY.max_extracted_text_chars,
            UPLOAD_POLICY.max_chunks_per_document, 1,
        )
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "one.txt"
            second = Path(directory) / "two.txt"
            first.write_text("one", encoding="utf-8")
            second.write_text("two", encoding="utf-8")
            chunks = [RuntimeChunk("chunk", metadata={})]
            with patch("src.webui.document_processor.UPLOAD_POLICY", policy), patch(
                "src.webui.document_processor.parse_file", return_value="text"
            ), patch(
                "src.webui.document_processor.chunk_text", return_value=chunks
            ):
                parsed, errors = process_uploads({}, [str(first), str(second)])
        self.assertEqual(parsed, [])
        self.assertIn("total chunk limit", errors[0])

    def test_attach_documents_rejects_client_bypass(self):
        policy = UploadPolicy(
            UPLOAD_POLICY.allowed_extensions, UPLOAD_POLICY.per_file_bytes,
            UPLOAD_POLICY.max_batch_bytes, UPLOAD_POLICY.max_extracted_text_chars,
            1, UPLOAD_POLICY.max_total_chunks_per_batch,
        )
        document = UploadedDocument(
            name="bypass.txt", path=Path("bypass.txt"), ext=".txt", text="text",
            chunks=[RuntimeChunk("a", metadata={}), RuntimeChunk("b", metadata={})],
        )
        with patch("src.webui.document_processor.UPLOAD_POLICY", policy):
            with self.assertRaisesRegex(ValueError, "maximum chunk"):
                attach_documents({"chunks": []}, [document], persist=False)

    def test_filename_and_path_safety(self):
        cases = (
            ("../../secret/manual.txt", "manual.txt"),
            (r"..\..\secret\manual.txt", "manual.txt"),
            (r"..\..\secret/\manual?.txt", "manual?.txt"),
            (r"C:\private\secret\manual.txt", "manual.txt"),
            ("/private/secret/manual.txt", "manual.txt"),
            (r"mixed\folder/path\manual.txt", "manual.txt"),
        )
        for raw_name, expected in cases:
            with self.subTest(raw_name=raw_name):
                document = UploadedDocument(
                    name=raw_name,
                    path=Path("manual.txt"),
                    ext=".txt",
                    text="safe content",
                )
                self.assertEqual(document.safe_display_name, expected)
                self.assertNotIn("..", document.safe_display_name)
                self.assertNotIn("\\", document.safe_display_name)
                self.assertNotIn("/", document.safe_display_name)

        for hostile_name in ("", "/", "..\\..\\"):
            with self.subTest(hostile_name=hostile_name):
                document = UploadedDocument(
                    name=hostile_name,
                    path=Path("manual.txt"),
                    ext=".txt",
                    text="safe content",
                )
                self.assertEqual(document.safe_display_name, "unnamed_document")

    def test_no_absolute_path_exposure(self):
        document = UploadedDocument(
            name="manual.txt",
            path=Path(r"C:\private\manual.txt"),
            ext=".txt",
            text="safe content",
        )
        public = document.to_dict()
        self.assertNotIn("path", public)
        self.assertNotIn("C:\\", str(public))
        self.assertNotIn("/", str(public))

    def test_provenance_survives_chunking(self):
        chunks = chunk_text(
            " ".join(["pump"] * 1_100),
            "doc-1",
            doc_name="manual.txt",
            extension=".txt",
            upload_timestamp="2026-01-01T00:00:00.000Z",
            revision="r2",
        )
        self.assertGreater(len(chunks), 1)
        for index, chunk in enumerate(chunks):
            self.assertIsInstance(chunk, RuntimeChunk)
            self.assertEqual(
                chunk.metadata,
                {
                    "document_id": "doc-1",
                    "document_name": "manual.txt",
                    "chunk_index": index,
                    "source_type": "runtime_upload",
                    "extension": ".txt",
                    "upload_timestamp": "2026-01-01T00:00:00.000Z",
                    "page_number": None,
                    "revision": "r2",
                },
            )

    def test_provenance_survives_retrieval(self):
        chunks = chunk_text(
            "pump pressure limit is 10 PSI",
            "doc-1",
            doc_name="manual.txt",
            extension=".txt",
            upload_timestamp="now",
        )
        index, frequency = build_index(chunks)
        results = retrieve("What is the pump pressure limit?", chunks, index, frequency)
        self.assertTrue(results)
        self.assertEqual(results[0]["chunk"].metadata["document_id"], "doc-1")
        source = _format_v2_sources(results, 1)[0]
        self.assertEqual(source["document_id"], "doc-1")
        self.assertEqual(source["document_name"], "manual.txt")
        self.assertEqual(source["extension"], ".txt")
        self.assertIn("upload_timestamp", source)

    def test_two_uploaded_documents_remain_distinguishable(self):
        first = UploadedDocument("one.txt", Path("one.txt"), ".txt", "alpha pump")
        second = UploadedDocument("two.txt", Path("two.txt"), ".txt", "beta pump")
        pipeline = {"chunks": [], "uploaded_docs": []}
        build = build_index([])
        pipeline["retrieval_index"], pipeline["document_frequency"] = build
        attach_documents(pipeline, [first, second])
        ids = {chunk.metadata["document_id"] for chunk in pipeline["chunks"]}
        self.assertEqual(ids, {first.doc_id, second.doc_id})
        self.assertNotEqual(first.doc_id, second.doc_id)

    def test_concurrent_uploads_preserve_registry_and_index_consistency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = {
                **make_pipeline(root),
                "chunks": ["static corpus survives"],
            }

            def upload(index):
                attach_documents(
                    pipeline,
                    [UploadedDocument(
                        f"doc-{index}.txt",
                        Path(f"doc-{index}.txt"),
                        ".txt",
                        f"unique content {index}",
                    )],
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(upload, range(8)))

            ids = [
                doc["document_id"]
                for doc in pipeline["uploaded_docs"]
            ]
            registry = json.loads(
                (root / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(ids), 8)
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(
                {doc["document_id"] for doc in registry},
                set(ids),
            )
            self.assertEqual(
                len(pipeline["chunks"]),
                len(pipeline["retrieval_index"]),
            )

    def test_concurrent_upload_and_delete_keep_registry_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            existing = UploadedDocument(
                "existing.txt", Path("existing.txt"), ".txt", "existing content"
            )
            attach_documents(pipeline, [existing])

            def upload():
                attach_documents(
                    pipeline,
                    [UploadedDocument(
                        "new.txt", Path("new.txt"), ".txt", "new content"
                    )],
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(upload)]
                futures.append(executor.submit(
                    remove_uploaded_document, pipeline, existing.doc_id
                ))
                for future in futures:
                    future.result()

            registry_text = (root / "metadata.json").read_text(encoding="utf-8")
            registry = json.loads(registry_text)
            ids = [doc["document_id"] for doc in registry]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertNotIn(existing.doc_id, ids)
            self.assertEqual(len(pipeline["chunks"]), len(pipeline["retrieval_index"]))

    def test_duplicate_document_ids_are_rejected(self):
        pipeline = make_pipeline(Path(tempfile.mkdtemp()))
        first = UploadedDocument("one.txt", Path("one.txt"), ".txt", "one")
        duplicate = UploadedDocument(
            "two.txt", Path("two.txt"), ".txt", "two", doc_id=first.doc_id
        )
        try:
            attach_documents(pipeline, [first])
            with self.assertRaisesRegex(ValueError, "Document ID"):
                attach_documents(pipeline, [duplicate])
        finally:
            import shutil
            shutil.rmtree(pipeline["runtime_upload_dir"], ignore_errors=True)

    def test_runtime_source_payload_includes_metadata(self):
        chunk = chunk_text("runtime evidence", "doc-1", doc_name="evidence.txt")[0]
        payload = _format_v2_sources(
            [{"chunk": chunk, "chunk_index": 0, "final_score": 1.0}],
            1,
        )[0]
        for field in (
            "document_id", "document_name", "chunk_index", "source_type",
            "extension", "upload_timestamp", "page_number", "revision",
        ):
            self.assertIn(field, payload)

    def test_hybrid_fallback_source_payload_includes_metadata(self):
        chunk = chunk_text(
            "runtime evidence",
            "doc-1",
            doc_name="evidence.pdf",
            extension=".pdf",
        )[0]
        payload = _format_hybrid_sources(
            [{"chunk": chunk, "chunk_index": 0, "lexical_score": 1.0}],
            1,
        )[0]
        self.assertEqual(payload["document_id"], "doc-1")
        self.assertEqual(payload["document_name"], "evidence.pdf")
        self.assertEqual(payload["extension"], ".pdf")
        self.assertEqual(payload["source_type"], "runtime_upload")

    def test_ui_document_table_uses_public_provenance_schema(self):
        row = _format_kb_table(
            [{
                "document_id": "doc-1",
                "document_name": "manual.txt",
                "extension": ".txt",
                "chunk_count": 2,
            }]
        )[0]
        self.assertEqual(row, ["manual.txt", ".txt", 2, "doc-1"])
        self.assertNotIn("C:\\", str(row))
        self.assertNotIn("path", str(row).casefold())

    def test_remove_uploaded_document_removes_only_one_document(self):
        first = UploadedDocument("one.txt", Path("one.txt"), ".txt", "alpha pump")
        second = UploadedDocument("two.txt", Path("two.txt"), ".txt", "beta pump")
        static = "static corpus"
        pipeline = {"chunks": [static], "uploaded_docs": []}
        pipeline["retrieval_index"], pipeline["document_frequency"] = build_index(
            pipeline["chunks"]
        )
        attach_documents(pipeline, [first, second])
        removed = remove_uploaded_document(pipeline, first.doc_id)
        remaining_ids = {
            chunk.metadata["document_id"]
            for chunk in pipeline["chunks"]
            if isinstance(chunk, RuntimeChunk)
        }
        self.assertEqual(removed, len(first.chunks))
        self.assertNotIn(first.doc_id, remaining_ids)
        self.assertIn(second.doc_id, remaining_ids)
        self.assertIn(static, pipeline["chunks"])

    def test_remove_nonexistent_document_does_not_mutate_pipeline(self):
        static = "static corpus"
        pipeline = {"chunks": [static], "uploaded_docs": []}
        pipeline["retrieval_index"], pipeline["document_frequency"] = build_index(
            pipeline["chunks"]
        )
        before = (
            list(pipeline["chunks"]),
            list(pipeline["retrieval_index"]),
            pipeline["document_frequency"].copy(),
            list(pipeline["uploaded_docs"]),
        )
        self.assertEqual(remove_uploaded_document(pipeline, "missing"), 0)
        self.assertEqual(pipeline["chunks"], before[0])
        self.assertEqual(pipeline["retrieval_index"], before[1])
        self.assertEqual(pipeline["document_frequency"], before[2])
        self.assertEqual(pipeline["uploaded_docs"], before[3])

    def test_runtime_boost_remains_unchanged(self):
        text = "pump pressure limit 10 PSI"
        static = [text]
        runtime = [RuntimeChunk(text, metadata={"document_id": "doc-1"})]
        static_index, static_frequency = build_index(static)
        runtime_index, runtime_frequency = build_index(runtime)
        static_score = retrieve_candidates(
            text, static, static_index, static_frequency, top_k=1
        )[0][0]
        runtime_score = retrieve_candidates(
            text, runtime, runtime_index, runtime_frequency, top_k=1
        )[0][0]
        self.assertAlmostEqual(runtime_score - static_score, INGESTED_CHUNK_BOOST)

    def test_unrelated_runtime_chunk_is_not_candidate_from_boost(self):
        chunks = [
            "pump pressure limit is 10 PSI",
            RuntimeChunk("unrelated electrical inspection procedure",
                         metadata={"document_id": "doc-2"}),
        ]
        index, frequency = build_index(chunks)
        results = retrieve_candidates(
            "What is the pump pressure limit?", chunks, index, frequency, top_k=5
        )
        self.assertEqual(
            [item[4].metadata["document_id"] for item in results
             if isinstance(item[4], RuntimeChunk)],
            [],
        )

    def test_static_corpus_behavior_remains_unchanged(self):
        chunks = ["The Roman army was organized into legions."]
        index, frequency = build_index(chunks)
        result = retrieve("How was the Roman army organized?", chunks, index, frequency)
        self.assertTrue(result)
        self.assertIs(type(result[0]["chunk"]), str)
        self.assertNotIsInstance(result[0]["chunk"], RuntimeChunk)
        self.assertNotIn("metadata", result[0])


if __name__ == "__main__":
    unittest.main()
