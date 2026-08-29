"""Fault-injection tests for transactional ingest and delete."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from retriever_v2 import build_index
from webui import document_processor
from webui.document_processor import (
    UploadedDocument,
    attach_documents,
    remove_uploaded_document,
    restore_persisted_documents,
)


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


class IngestRollbackTests(unittest.TestCase):
    def test_ingest_persistence_failure_restores_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("fail.txt", Path("fail.txt"), ".txt", "fail content")

            def fake_persist_registry(pipeline, entries):
                raise OSError("disk full")

            with patch.object(document_processor, "_persist_registry", side_effect=fake_persist_registry):
                with self.assertRaises(OSError):
                    attach_documents(pipeline, [doc])

            self.assertEqual(pipeline["chunks"], ["static corpus survives"])
            self.assertEqual(len(pipeline["retrieval_index"]), 1)
            self.assertEqual(pipeline["uploaded_docs"], [])
            self.assertFalse((root / "documents" / f"{doc.doc_id}.txt").exists())

    def test_extend_failure_after_mutation_restores_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("extend.txt", Path("extend.txt"), ".txt", "extend content")

            original_extend = document_processor.extend_index_v2
            call_count = [0]

            def fake_extend(index, frequency, chunks, start_index):
                call_count[0] += 1
                if call_count[0] == 1:
                    index.append({"extend": 1})
                    raise ValueError("extend boom")
                original_extend(index, frequency, chunks, start_index)

            with patch.object(document_processor, "extend_index_v2", side_effect=fake_extend):
                with self.assertRaises(ValueError):
                    attach_documents(pipeline, [doc])

            self.assertEqual(pipeline["chunks"], ["static corpus survives"])
            self.assertEqual(len(pipeline["retrieval_index"]), 1)
            self.assertEqual(pipeline["uploaded_docs"], [])

    def test_build_failure_restores_document_frequency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("build.txt", Path("build.txt"), ".txt", "build content")
            pipeline["retrieval_index"] = []
            pipeline["document_frequency"] = {}

            with patch.object(document_processor, "build_index_v2", side_effect=RuntimeError("build boom")):
                with self.assertRaises(RuntimeError):
                    attach_documents(pipeline, [doc])

            self.assertEqual(pipeline["chunks"], ["static corpus survives"])
            self.assertEqual(pipeline["retrieval_index"], [])
            self.assertEqual(dict(pipeline["document_frequency"]), {})
            self.assertEqual(pipeline["uploaded_docs"], [])

    def test_pre_existing_content_restored_on_ingest_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            original = UploadedDocument("orig.txt", Path("orig.txt"), ".txt", "original content")
            attach_documents(pipeline, [original])

            replacement = UploadedDocument("new.txt", Path("new.txt"), ".txt", "new content")

            def fake_persist_registry(pipeline, entries):
                raise OSError("disk full")

            with patch.object(document_processor, "_persist_registry", side_effect=fake_persist_registry):
                with self.assertRaises(OSError):
                    attach_documents(pipeline, [replacement])

            content_path = root / "documents" / f"{original.doc_id}.txt"
            self.assertTrue(content_path.exists())
            self.assertEqual(content_path.read_text(encoding="utf-8"), "original content")
            self.assertFalse((root / "documents" / f"{replacement.doc_id}.txt").exists())
            registry = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(len(registry), 1)
            self.assertEqual(registry[0]["document_id"], original.doc_id)

    def test_new_content_cleanup_on_persist_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("new.txt", Path("new.txt"), ".txt", "new content")

            def fake_persist_registry(pipeline, entries):
                raise OSError("disk full")

            with patch.object(document_processor, "_persist_registry", side_effect=fake_persist_registry):
                with self.assertRaises(OSError):
                    attach_documents(pipeline, [doc])

            content_path = root / "documents" / f"{doc.doc_id}.txt"
            self.assertFalse(content_path.exists())

    def test_restart_sees_pre_ingest_state_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            original = UploadedDocument("orig.txt", Path("orig.txt"), ".txt", "original content")
            attach_documents(pipeline, [original])

            failing_doc = UploadedDocument("fail.txt", Path("fail.txt"), ".txt", "fails")

            def fake_persist_registry(pipeline, entries):
                raise OSError("disk full")

            with patch.object(document_processor, "_persist_registry", side_effect=fake_persist_registry):
                with self.assertRaises(OSError):
                    attach_documents(pipeline, [failing_doc])

            recreated = make_pipeline(root)
            restored = restore_persisted_documents(recreated)
            self.assertEqual([d.doc_id for d in restored], [original.doc_id])
            self.assertEqual(len(restored), 1)

    def test_multi_doc_ingest_is_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            first = UploadedDocument("first.txt", Path("first.txt"), ".txt", "first content")
            second = UploadedDocument("second.txt", Path("second.txt"), ".txt", "second content")

            original_persist = document_processor._persist_document

            def fake_persist_document(pipeline, doc):
                if doc.doc_id == second.doc_id:
                    raise OSError("disk full on second")
                original_persist(pipeline, doc)

            with patch.object(document_processor, "_persist_document", side_effect=fake_persist_document):
                with self.assertRaises(OSError):
                    attach_documents(pipeline, [first, second])

            self.assertEqual(pipeline["chunks"], ["static corpus survives"])
            self.assertEqual(pipeline["uploaded_docs"], [])
            self.assertFalse((root / "documents" / f"{first.doc_id}.txt").exists())
            self.assertFalse((root / "documents" / f"{second.doc_id}.txt").exists())
            registry = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(registry, [])


class DeleteRollbackTests(unittest.TestCase):
    def test_delete_build_failure_restores_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("del.txt", Path("del.txt"), ".txt", "delete me")
            attach_documents(pipeline, [doc])

            with patch.object(document_processor, "build_index_v2", side_effect=RuntimeError("build boom")):
                with self.assertRaises(RuntimeError):
                    remove_uploaded_document(pipeline, doc.doc_id)

            self.assertIn("delete me", pipeline["chunks"])
            self.assertEqual(len(pipeline["uploaded_docs"]), 1)
            self.assertTrue((root / "documents" / f"{doc.doc_id}.txt").exists())

    def test_delete_registry_failure_restores_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("del.txt", Path("del.txt"), ".txt", "delete me")
            attach_documents(pipeline, [doc])

            def fake_persist_registry(pipeline, entries):
                raise OSError("disk full")

            with patch.object(document_processor, "_persist_registry", side_effect=fake_persist_registry):
                with self.assertRaises(OSError):
                    remove_uploaded_document(pipeline, doc.doc_id)

            self.assertIn("delete me", pipeline["chunks"])
            self.assertEqual(len(pipeline["uploaded_docs"]), 1)
            self.assertTrue((root / "documents" / f"{doc.doc_id}.txt").exists())
            registry = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(len(registry), 1)

    def test_delete_unlink_failure_restores_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("del.txt", Path("del.txt"), ".txt", "delete me")
            attach_documents(pipeline, [doc])

            def fake_unlink(self, missing_ok=False):
                raise OSError("cannot delete")

            with patch.object(Path, "unlink", new=fake_unlink):
                with self.assertRaises(OSError):
                    remove_uploaded_document(pipeline, doc.doc_id)

            self.assertIn("delete me", pipeline["chunks"])
            self.assertEqual(len(pipeline["uploaded_docs"]), 1)
            self.assertTrue((root / "documents" / f"{doc.doc_id}.txt").exists())

    def test_complete_memory_and_index_restoration_on_delete_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chunks = ["static corpus survives", "runtime chunk one", "runtime chunk two"]
            index, frequency = build_index(chunks)
            pipeline = {
                "chunks": list(chunks),
                "retrieval_index": index,
                "document_frequency": frequency,
                "uploaded_docs": [{"document_id": "doc-1", "document_name": "one.txt"}],
                "runtime_persistence": True,
                "runtime_upload_dir": root,
            }
            doc = UploadedDocument("del.txt", Path("del.txt"), ".txt", "delete me")
            attach_documents(pipeline, [doc])

            expected_chunks = list(chunks) + ["delete me"]
            expected_uploaded = [{"document_id": "doc-1", "document_name": "one.txt"}, {"document_id": doc.doc_id, "document_name": "del.txt", "extension": ".txt", "chunk_count": 1, "upload_timestamp": doc.upload_timestamp, "source_type": "runtime_upload", "revision": None}]

            with patch.object(document_processor, "build_index_v2", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    remove_uploaded_document(pipeline, doc.doc_id)

            self.assertEqual(pipeline["chunks"], expected_chunks)
            self.assertEqual(len(pipeline["retrieval_index"]), len(index))
            self.assertEqual(pipeline["retrieval_index"].postings, index.postings)
            self.assertEqual(pipeline["retrieval_index"].runtime_indices, index.runtime_indices)
            self.assertEqual(dict(pipeline["document_frequency"]), dict(frequency))
            self.assertEqual(pipeline["uploaded_docs"], expected_uploaded)

    def test_restart_sees_pre_delete_state_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = make_pipeline(root)
            doc = UploadedDocument("del.txt", Path("del.txt"), ".txt", "delete me")
            attach_documents(pipeline, [doc])

            with patch.object(document_processor, "build_index_v2", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    remove_uploaded_document(pipeline, doc.doc_id)

            recreated = make_pipeline(root)
            restored = restore_persisted_documents(recreated)
            self.assertEqual([d.doc_id for d in restored], [doc.doc_id])


if __name__ == "__main__":
    unittest.main()
