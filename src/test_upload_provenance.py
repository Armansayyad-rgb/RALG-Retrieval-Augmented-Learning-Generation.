"""Focused upload limits, provenance, isolation, and compatibility checks."""

import tempfile
import unittest
import sys
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
from src.webui.chat_handler import _format_v2_sources, _format_v4_sources
from src.webui.app import _format_kb_table
from src.webui.document_processor import (
    MAX_TXT_SIZE,
    UploadedDocument,
    attach_documents,
    chunk_text,
    process_uploads,
    remove_uploaded_document,
)


class UploadProvenanceTests(unittest.TestCase):
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

    def test_filename_and_path_safety(self):
        document = UploadedDocument(
            name=r"..\..\secret/\manual?.txt",
            path=Path(r"C:\private\secret\manual?.txt"),
            ext=".txt",
            text="safe content",
        )
        self.assertEqual(document.safe_display_name, "manual?.txt")
        self.assertNotIn("..", document.safe_display_name)
        self.assertNotIn("\\", document.safe_display_name)
        self.assertNotIn("/", document.safe_display_name)

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

    def test_v4_fallback_source_payload_includes_metadata(self):
        chunk = chunk_text(
            "runtime evidence",
            "doc-1",
            doc_name="evidence.pdf",
            extension=".pdf",
        )[0]
        payload = _format_v4_sources(
            {"results": [{"chunk": chunk, "chunk_index": 0, "final_score": 1.0}]},
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
