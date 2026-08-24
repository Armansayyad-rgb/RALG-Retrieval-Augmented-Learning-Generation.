"""Prototype 1 runtime document persistence and lifecycle tests."""

import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from retriever_v2 import RuntimeChunk, build_index, retrieve
from webui.chat_handler import format_evidence_sources
from webui.document_processor import (
    UploadedDocument,
    attach_documents,
    remove_uploaded_document,
    restore_persisted_documents,
)
import api_server


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


if __name__ == "__main__":
    unittest.main()
