import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

DEV_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "authoritative_dev_v1"
SOURCES_DIR = DEV_DIR / "sources"
BENCHMARK = DEV_DIR / "holdout_benchmark.jsonl"
MANIFEST = DEV_DIR / "manifest.json"


class TestBenchmarkStructure(unittest.TestCase):
    def test_exactly_160_cases(self):
        cases = []
        with open(BENCHMARK) as f:
            for line in f:
                if line.strip():
                    cases.append(json.loads(line))
        self.assertEqual(len(cases), 160)

    def test_unique_ids(self):
        ids = []
        with open(BENCHMARK) as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    ids.append(c["id"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_category_distribution(self):
        counts = {}
        with open(BENCHMARK) as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    cat = c["category"]
                    counts[cat] = counts.get(cat, 0) + 1
        expected = {"supported": 25, "paraphrased": 20, "procedural": 20,
                    "causal": 15, "cross_document": 15, "document_scoped": 10,
                    "unsupported": 20, "false_premise": 15, "misleading_overlap": 10,
                    "conditional_or_qualified": 10}
        self.assertEqual(counts, expected)

    def test_valid_source_ids(self):
        valid_ids = {f.stem for f in SOURCES_DIR.glob("*.txt")}
        with open(BENCHMARK) as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    for doc_id in c.get("expected_document_ids", []):
                        self.assertIn(doc_id, valid_ids, f"Invalid source ID: {doc_id}")


class TestSources(unittest.TestCase):
    def test_all_sources_present(self):
        sources = [f.stem for f in SOURCES_DIR.glob("*.txt")]
        self.assertEqual(len(sources), 12)

    def test_all_sources_produce_chunks(self):
        from src.retriever_v2 import load_chunks
        for f in sorted(SOURCES_DIR.glob("*.txt")):
            chunks = load_chunks(f)
            self.assertGreater(len(chunks), 0, f"{f.name} produced 0 chunks")

    def test_source_hashes_match_manifest(self):
        import hashlib
        manifest_lines = []
        with open(DEV_DIR / "sources_manifest.jsonl") as f:
            for line in f:
                if line.strip():
                    manifest_lines.append(json.loads(line))
        for entry in manifest_lines:
            path = SOURCES_DIR / entry["filename"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(actual, entry["sha256"], f"Hash mismatch for {entry['filename']}")


class TestEvidencSpans(unittest.TestCase):
    def test_evidence_spans_exist_in_source(self):
        import re
        sources_text = {}
        for f in SOURCES_DIR.glob("*.txt"):
            sources_text[f.stem] = f.read_text(encoding="utf-8", errors="ignore").lower()
        with open(BENCHMARK) as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    for doc_id in c.get("expected_document_ids", []):
                        if doc_id in sources_text:
                            for span in c.get("evidence_spans", []):
                                normalized_span = " ".join(span.lower().split())
                                normalized_source = " ".join(sources_text[doc_id].split())
                                self.assertIn(
                                    normalized_span, normalized_source,
                                    f"Evidence span not found in {doc_id}: {span[:60]}..."
                                )


class TestContamination(unittest.TestCase):
    def test_no_exact_duplicates_with_v2(self):
        v2_questions = set()
        p = Path(__file__).resolve().parent.parent / "evaluation" / "holdout_v2" / "holdout_benchmark.jsonl"
        if p.exists():
            with open(p) as f:
                for line in f:
                    if line.strip():
                        c = json.loads(line)
                        v2_questions.add(c.get("question", "").lower().strip())
        with open(BENCHMARK) as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    q = c.get("question", "").lower().strip()
                    self.assertNotIn(q, v2_questions, f"Duplicate with V2: {c['id']}")

    def test_no_exact_duplicates_with_v3(self):
        v3_questions = set()
        p = Path(__file__).resolve().parent.parent / "evaluation" / "holdout_v3" / "holdout_v3_benchmark.jsonl"
        if p.exists():
            with open(p) as f:
                for line in f:
                    if line.strip():
                        c = json.loads(line)
                        v3_questions.add(c.get("question", "").lower().strip())
        with open(BENCHMARK) as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    q = c.get("question", "").lower().strip()
                    self.assertNotIn(q, v3_questions, f"Duplicate with V3: {c['id']}")


class TestManifest(unittest.TestCase):
    def test_manifest_exists(self):
        self.assertTrue(MANIFEST.exists())

    def test_manifest_fields(self):
        with open(MANIFEST) as f:
            m = json.load(f)
        self.assertEqual(m["benchmark_version"], "authoritative_dev_v1.0.0")
        self.assertEqual(m["case_count"], 160)
        self.assertEqual(m["source_count"], 12)


if __name__ == "__main__":
    unittest.main()
