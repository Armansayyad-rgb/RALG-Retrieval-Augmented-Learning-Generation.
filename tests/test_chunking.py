import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.retriever_v2 import load_chunks, MAX_CONTEXT_CHARS

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TestShortLineProse(unittest.TestCase):
    def test_short_line_document_produces_chunks(self):
        path = FIXTURES / "short_line_prose.txt"
        chunks = load_chunks(path)
        self.assertGreater(len(chunks), 0)

    def test_content_is_preserved(self):
        path = FIXTURES / "short_line_prose.txt"
        chunks = load_chunks(path)
        combined = " ".join(chunks).lower()
        self.assertIn("write-ahead logging", combined)
        self.assertIn("wal", combined)


class TestMarkdownHeadings(unittest.TestCase):
    def test_headings_produce_chunks(self):
        path = FIXTURES / "markdown_headings.txt"
        chunks = load_chunks(path)
        self.assertGreater(len(chunks), 0)

    def test_heading_content_preserved(self):
        path = FIXTURES / "markdown_headings.txt"
        chunks = load_chunks(path)
        combined = " ".join(chunks).lower()
        self.assertIn("configuration guide", combined)
        self.assertIn("connection pool", combined)


class TestBulletList(unittest.TestCase):
    def test_bullet_list_produces_chunks(self):
        path = FIXTURES / "bullet_list.txt"
        chunks = load_chunks(path)
        self.assertGreater(len(chunks), 0)

    def test_bullet_items_preserved(self):
        path = FIXTURES / "bullet_list.txt"
        chunks = load_chunks(path)
        combined = " ".join(chunks).lower()
        self.assertIn("prerequisites", combined)
        self.assertIn("installation steps", combined)


class TestNumberedProcedures(unittest.TestCase):
    def test_procedures_produce_chunks(self):
        path = FIXTURES / "numbered_procedures.txt"
        chunks = load_chunks(path)
        self.assertGreater(len(chunks), 0)

    def test_step_content_preserved(self):
        path = FIXTURES / "numbered_procedures.txt"
        chunks = load_chunks(path)
        combined = " ".join(chunks).lower()
        self.assertIn("deployment procedure", combined)
        self.assertIn("rollback procedure", combined)


class TestConfigContent(unittest.TestCase):
    def test_config_produces_chunks(self):
        path = FIXTURES / "config_content.txt"
        chunks = load_chunks(path)
        self.assertGreater(len(chunks), 0)

    def test_config_sections_preserved(self):
        path = FIXTURES / "config_content.txt"
        chunks = load_chunks(path)
        combined = " ".join(chunks).lower()
        self.assertIn("server", combined)
        self.assertIn("database", combined)
        self.assertIn("cache", combined)


class TestLongProse(unittest.TestCase):
    def test_long_prose_produces_chunks(self):
        path = FIXTURES / "long_prose.txt"
        chunks = load_chunks(path)
        self.assertGreater(len(chunks), 0)

    def test_long_prose_multiple_chunks(self):
        path = FIXTURES / "long_prose.txt"
        chunks = load_chunks(path)
        self.assertGreater(len(chunks), 1)


class TestTinyDocument(unittest.TestCase):
    def test_tiny_document_produces_chunk(self):
        path = FIXTURES / "tiny_document.txt"
        chunks = load_chunks(path)
        self.assertGreater(len(chunks), 0)

    def test_tiny_content_preserved(self):
        path = FIXTURES / "tiny_document.txt"
        chunks = load_chunks(path)
        combined = " ".join(chunks).lower()
        self.assertIn("ok", combined)


class TestEmptyDocument(unittest.TestCase):
    def test_empty_document_produces_no_chunks(self):
        path = FIXTURES / "empty_document.txt"
        chunks = load_chunks(path)
        self.assertEqual(len(chunks), 0)


class TestChunkSize(unittest.TestCase):
    def test_no_chunk_exceeds_max_context(self):
        path = FIXTURES / "long_prose.txt"
        chunks = load_chunks(path)
        for chunk in chunks:
            self.assertLessEqual(
                len(chunk),
                MAX_CONTEXT_CHARS + 200,
                f"Chunk exceeds max size: {len(chunk)} chars",
            )


class TestProvenance(unittest.TestCase):
    def test_chunks_are_strings(self):
        path = FIXTURES / "short_line_prose.txt"
        chunks = load_chunks(path)
        for chunk in chunks:
            self.assertIsInstance(chunk, str)

    def test_chunks_are_non_empty(self):
        path = FIXTURES / "short_line_prose.txt"
        chunks = load_chunks(path)
        for chunk in chunks:
            self.assertGreater(len(chunk), 0)


class TestV3Sources(unittest.TestCase):
    def test_all_sources_produce_chunks(self):
        project_root = Path(__file__).resolve().parent.parent
        sources = [
            "sqlite_wal_mode",
            "cmake_presets",
            "kubernetes_probes",
            "oci_image_layout",
            "otel_propagators",
            "postgresql_vacuuming",
            "systemd_unit",
        ]
        for source in sources:
            path = (
                project_root
                / "evaluation"
                / "holdout_v3"
                / "sources"
                / f"{source}.txt"
            )
            chunks = load_chunks(path)
            self.assertGreater(
                len(chunks),
                0,
                f"{source} produced 0 chunks",
            )


class TestRetrievalAfterIndexing(unittest.TestCase):
    def test_short_line_content_retrievable(self):
        from src.retriever_v2 import build_index, retrieve

        path = FIXTURES / "short_line_prose.txt"
        chunks = load_chunks(path)
        index, df = build_index(chunks)
        results = retrieve(
            "Write-Ahead Logging",
            chunks,
            index,
            df,
            final_top_k=3,
        )
        self.assertGreater(len(results), 0)
        combined = " ".join(
            r["chunk"] for r in results
        ).lower()
        self.assertIn("wal", combined)


if __name__ == "__main__":
    unittest.main()
