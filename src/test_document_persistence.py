"""Prototype 1 runtime document persistence and lifecycle tests."""

import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from retriever_v2 import RuntimeChunk, build_index, retrieve
from webui.chat_handler import format_evidence_sources
from webui import document_processor
from webui.document_processor import (
    UploadedDocument,
    attach_documents,
    remove_uploaded_document,
    restore_persisted_documents,
)
import api_server
from api_server import QueryRequest, IngestRequest


def make_pipeline(root: Path) -> dict:
    chunks = ["static corpus survives"]
    index, frequency = build_index(chunks)
    return {
        "chunks": chunks,
        "retrieval_index": index,
        "document_frequency": frequency,
        "uploaded_docs": [],
        "runtime_persistence": True,
        "runtime_upload_dir": root,
    }


class DocumentPersistenceTests(unittest.TestCase):
    def test_restart_restore_retrieval_and_exact_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("manual.txt", Path("temporary.gradio"), ".txt",
                                   "distinctive restart pressure limit")
            attach_documents(pipeline, [doc])
            recreated = make_pipeline(root)
            restored = restore_persisted_documents(recreated)
            attach_documents(recreated, restored)
            self.assertEqual(restored[0].doc_id, doc.doc_id)
            chunk = next(c for c in recreated["chunks"] if isinstance(c, RuntimeChunk))
            self.assertEqual(chunk.metadata["document_id"], doc.doc_id)
            result = retrieve(
                "What is the distinctive restart pressure limit?",
                recreated["chunks"], recreated["retrieval_index"],
                recreated["document_frequency"],
            )
            source = format_evidence_sources(
                {"kind": "v2", "results": result}, 1
            )[0]
            self.assertEqual(source["document_id"], doc.doc_id)
            self.assertEqual(source["document_name"], "manual.txt")
            self.assertEqual(source["chunk_index"], 0)
            self.assertEqual(source["revision"], doc.revision)

    def test_two_documents_delete_one_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            first = UploadedDocument("one.txt", Path("one"), ".txt", "alpha unique")
            second = UploadedDocument("two.txt", Path("two"), ".txt", "beta unique")
            attach_documents(pipeline, [first, second])
            removed = remove_uploaded_document(pipeline, first.doc_id)
            self.assertEqual(removed, 1)
            self.assertIn("static corpus survives", pipeline["chunks"])
            self.assertTrue(any(d["document_id"] == second.doc_id for d in pipeline["uploaded_docs"]))
            recreated = make_pipeline(root)
            restored = restore_persisted_documents(recreated)
            self.assertEqual([d.doc_id for d in restored], [second.doc_id])

    def test_unknown_delete_is_safe_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = make_pipeline(Path(directory))
            before = list(pipeline["chunks"])
            self.assertEqual(remove_uploaded_document(pipeline, "missing"), 0)
            self.assertEqual(pipeline["chunks"], before)

    def test_missing_and_corrupt_entries_do_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "documents").mkdir()
            (root / "metadata.json").write_text(json.dumps([
                {"document_id": "missing", "extension": ".txt"},
                {"document_id": "bad", "extension": ".exe"},
                {"document_id": "duplicate", "extension": ".txt"},
                {"document_id": "duplicate", "extension": ".txt"},
            ]), encoding="utf-8")
            restored = restore_persisted_documents(make_pipeline(root))
            self.assertEqual(restored, [])

    def test_corrupt_registry_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.mkdir(exist_ok=True)
            (root / "metadata.json").write_text("{", encoding="utf-8")
            self.assertEqual(restore_persisted_documents(make_pipeline(root)), [])

    def test_traversal_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "documents").mkdir()
            outside = root / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            (root / "metadata.json").write_text(json.dumps([{
                "document_id": "escape", "extension": ".txt",
                "content_file": "../outside.txt",
            }]), encoding="utf-8")
            self.assertEqual(restore_persisted_documents(make_pipeline(root)), [])

    def test_registry_and_public_metadata_do_not_expose_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("safe.txt", Path(r"C:\private\safe.txt"), ".txt", "safe")
            attach_documents(pipeline, [doc])
            self.assertNotIn("path", str(pipeline["uploaded_docs"]))
            self.assertNotIn(str(root), str(pipeline["uploaded_docs"]))
            registry = (root / "metadata.json").read_text(encoding="utf-8")
            self.assertIn("documents/", registry)
            self.assertNotIn(r"C:\private", registry)

    def test_api_document_lifecycle_is_safe(self):
        pipeline = {
            "uploaded_docs": [{
                "document_id": "doc-1",
                "document_name": "safe.txt",
                "extension": ".txt",
                "chunk_count": 1,
            }],
            "chunks": [],
        }
        with patch.object(api_server, "get_pipeline", return_value=pipeline):
            listing = api_server.documents()
            self.assertEqual(listing[0]["document_id"], "doc-1")
            self.assertNotIn("path", str(listing))
            with patch.object(api_server, "remove_uploaded_document", return_value=1):
                result = api_server.delete_document("doc-1")
        self.assertTrue(result.deleted)
        self.assertNotIn("/", str(result.model_dump()))
        with self.assertRaises(api_server.HTTPException) as error:
            with patch.object(api_server, "get_pipeline", return_value={"uploaded_docs": [], "chunks": []}):
                api_server.delete_document("missing")
        self.assertEqual(error.exception.status_code, 404)

    def test_query_is_serialized_with_ingest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            pipeline["chunks"] = ["initial chunk"]
            pipeline["retrieval_index"], pipeline["document_frequency"] = build_index(pipeline["chunks"])
            doc = UploadedDocument("concurrent.txt", Path("concurrent.txt"), ".txt", "concurrent content")

            events = {"query_started": Event(), "ingest_done": Event()}

            def slow_query():
                events["query_started"].set()
                with patch.object(api_server, "get_pipeline", return_value=pipeline):
                    with patch.object(api_server, "answer_question", return_value={
                        "answer": "mock", "supported": True, "answer_type": "extractive",
                        "confidence": 1.0, "evidence": ["initial chunk"],
                    }):
                        response = api_server.query(
                            QueryRequest(question="test", top_k=1),
                            request=None,
                        )
                self.assertEqual(response.answer, "mock")

            def slow_ingest():
                events["query_started"].wait(timeout=2)
                attach_documents(pipeline, [doc])
                events["ingest_done"].set()

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(slow_query),
                    executor.submit(slow_ingest),
                ]
                for future in futures:
                    future.result(timeout=5)

            self.assertTrue(events["ingest_done"].is_set())
            self.assertIn("concurrent content", " ".join(c for c in pipeline["chunks"] if isinstance(c, str)))

    def test_query_is_serialized_with_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("delete_me.txt", Path("delete_me.txt"), ".txt", "delete me")
            attach_documents(pipeline, [doc])

            events = {"query_started": Event(), "delete_done": Event()}

            def slow_query():
                events["query_started"].set()
                with patch.object(api_server, "get_pipeline", return_value=pipeline):
                    with patch.object(api_server, "answer_question", return_value={
                        "answer": "mock", "supported": True, "answer_type": "extractive",
                        "confidence": 1.0, "evidence": ["static corpus survives"],
                    }):
                        response = api_server.query(
                            QueryRequest(question="test", top_k=1),
                            request=None,
                        )
                self.assertEqual(response.answer, "mock")

            def slow_delete():
                events["query_started"].wait(timeout=2)
                remove_uploaded_document(pipeline, doc.doc_id)
                events["delete_done"].set()

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(slow_query),
                    executor.submit(slow_delete),
                ]
                for future in futures:
                    future.result(timeout=5)

            self.assertTrue(events["delete_done"].is_set())
            self.assertNotIn(doc.doc_id, [d.get("document_id") for d in pipeline["uploaded_docs"]])

    def test_persist_document_cleans_up_on_registry_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("fail.txt", Path("fail.txt"), ".txt", "content that fails")

            def fake_persist_registry(pipeline, entries):
                raise OSError("disk full")

            with patch.object(document_processor, "_persist_registry", side_effect=fake_persist_registry):
                with self.assertRaises(OSError):
                    attach_documents(pipeline, [doc])

            content_path = root / "documents" / f"{doc.doc_id}.txt"
            self.assertFalse(content_path.exists())
            registry = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(registry, [])

    def test_atomic_write_cleans_up_temp_on_replace_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.txt"

            def fake_replace(self, target):
                raise OSError("disk full")

            with patch("pathlib.Path.replace", new=fake_replace):
                with self.assertRaises(OSError):
                    document_processor._atomic_write(path, "content")

            temp_files = list(Path(directory).glob("tmp*"))
            self.assertEqual(temp_files, [])

    def test_failed_persist_does_not_report_success(self):
        pipeline = make_pipeline(Path(tempfile.mkdtemp()))
        with patch.object(document_processor, "_persist_document", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                attach_documents(pipeline, [
                    UploadedDocument("fail.txt", Path("fail.txt"), ".txt", "fail content")
                ])

    def test_recovery_diagnostics_log_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "documents").mkdir()
            (root / "metadata.json").write_text(json.dumps([
                {"document_id": "missing", "extension": ".txt"},
                {"document_id": "bad", "extension": ".exe"},
                {"document_id": "good", "extension": ".txt", "content_file": "documents/good.txt", "document_name": "good"},
            ]), encoding="utf-8")
            (root / "documents" / "good.txt").write_text("good content", encoding="utf-8")
            pipeline = make_pipeline(root)
            with self.assertLogs("webui.document_processor", level="INFO") as cm:
                restored = restore_persisted_documents(pipeline)
            self.assertEqual(len(restored), 1)
            self.assertTrue(
                any("restored=1" in msg and "skipped=2" in msg for msg in cm.output)
            )


if __name__ == "__main__":
    unittest.main()
