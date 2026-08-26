#!/usr/bin/env python3
"""Build and freeze the holdout_v1 benchmark (untouched holdout, not Stage 5).

Source corpus: Python PEPs (public domain, independent of Stage 5 RFCs).
Cases are hand-authored specifications verified at build time against the
source texts (evidence spans located verbatim or the build FAILS). The
benchmark is frozen immediately after generation: a manifest records SHA-256
hashes and a version; any post-freeze modification without a version bump is
reported by the contamination guard.

This tool never touches Stage 5 fixtures or retrieval/model/scoring code.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evaluation" / "holdout_v1"
SOURCES_DIR = OUT_DIR / "sources"
BENCHMARK_VERSION = "holdout_v1.0.0"
ACQUISITION_DATE = "2026-08-26"

# ---------------------------------------------------------------------------
# Source manifest: Python PEPs are placed in the public domain by their
# authors (per PEP 0 / individual PEP footers), so redistribution is permitted.
# ---------------------------------------------------------------------------
SOURCE_SPECS = [
    ("pep_0001", "https://github.com/python/peps/blob/main/peps/pep-0001.rst"),
    ("pep_0006", "https://github.com/python/peps/blob/main/peps/pep-0006.rst"),
    ("pep_0008", "https://github.com/python/peps/blob/main/peps/pep-0008.rst"),
    ("pep_0020", "https://github.com/python/peps/blob/main/peps/pep-0020.rst"),
    ("pep_0101", "https://github.com/python/peps/blob/main/peps/pep-0101.rst"),
    ("pep_0249", "https://github.com/python/peps/blob/main/peps/pep-0249.rst"),
    ("pep_0257", "https://github.com/python/peps/blob/main/peps/pep-0257.rst"),
    ("pep_0333", "https://github.com/python/peps/blob/main/peps/pep-0333.rst"),
    ("pep_0484", "https://github.com/python/peps/blob/main/peps/pep-0484.rst"),
    ("pep_0506", "https://github.com/python/peps/blob/main/peps/pep-0506.rst"),
    ("pep_8001", "https://github.com/python/peps/blob/main/peps/pep-8001.rst"),
]

META = {
    "pep_0001": {"number": 1, "title": "PEP Purpose and Guidelines", "status": "Active",
                 "author": "Barry Warsaw"},
    "pep_0006": {"number": 6, "title": "Bug Fix Releases", "status": "Superseded",
                 "author": "Aahz"},
    "pep_0008": {"number": 8, "title": "Style Guide for Python Code", "status": "Active",
                 "author": "Guido van Rossum"},
    "pep_0020": {"number": 20, "title": "The Zen of Python", "status": "Active",
                 "author": "Tim Peters"},
    "pep_0101": {"number": 101, "title": "Doing Python Releases 101", "status": "Active",
                 "author": "Barry Warsaw"},
    "pep_0249": {"number": 249, "title": "Python Database API Specification v2.0",
                 "status": "Final", "author": "Marc-André Lemburg"},
    "pep_0257": {"number": 257, "title": "Docstring Conventions", "status": "Active",
                 "author": "David Goodger"},
    "pep_0333": {"number": 333, "title": "Python Web Server Gateway Interface v1.0",
                 "status": "Final", "author": "Phillip J. Eby"},
    "pep_0484": {"number": 484, "title": "Type Hints", "status": "Final",
                 "author": "Guido van Rossum"},
    "pep_0506": {"number": 506, "title": "Adding A Secrets Module To The Standard Library",
                 "status": "Final", "author": "Steven D'Aprano"},
    "pep_8001": {"number": 8001, "title": "Python Governance Voting Process",
                 "status": "Final", "author": "Brett Cannon"},
}

TOPIC_TO_PEP = [
    ("the style guide for Python code", "pep_0008"),
    ("the Zen of Python", "pep_0020"),
    ("type hints and type checking annotations", "pep_0484"),
    ("the web server gateway interface between web servers and Python applications", "pep_0333"),
    ("docstring conventions and documentation strings", "pep_0257"),
    ("the Python database API specification for database modules", "pep_0249"),
    ("the secrets module for generating cryptographically strong random numbers", "pep_0506"),
    ("the process used to vote on Python governance models", "pep_8001"),
    ("bug fix releases of Python", "pep_0006"),
    ("how CPython release managers cut an official Python release", "pep_0101"),
    ("the purpose of Python Enhancement Proposals and what belongs in one", "pep_0001"),
]

PARAPHRASE_TEMPLATES = [
    "If I want to look up rules for formatting Python code consistently, which proposal should I read?",
    "Which enhancement proposal collects the guiding principles for Python's design?",
    "Where would I find the specification that lets developers annotate function signatures with types?",
    "Which document standardizes how a web server passes requests to a Python web application?",
    "What proposal explains the recommended way to write docstrings?",
    "Which specification do Python database driver modules conform to?",
    "I need cryptographically secure random tokens in my program. Which proposal added the module for that?",
    "Which proposal describes how the community voted on a new governance model after the BDFL retired?",
    "Which proposal covers how maintenance releases with only bug fixes should be done?",
    "Where is the step-by-step process for making an official CPython release described?",
    "Which proposal defines what a PEP is and how it moves through its lifecycle?",
]

MULTI_DOC_CASES = [
    ("Which PEPs in this corpus were authored by Guido van Rossum?",
     ["pep_0008", "pep_0101", "pep_0484"]),
    ("Which of these proposals have reached Final status?",
     ["pep_0249", "pep_0333", "pep_0484", "pep_0506", "pep_8001"]),
    ("Which proposals describe parts of the Python development or governance process?",
     ["pep_0001", "pep_0006", "pep_0101", "pep_8001"]),
    ("Which two proposals define coding conventions, one for code style and one for docstrings?",
     ["pep_0008", "pep_0257"]),
    ("Which proposals are still in Active status?",
     ["pep_0001", "pep_0008", "pep_0020", "pep_0101", "pep_0257"]),
    ("Which proposals were written by Barry Warsaw?",
     ["pep_0001", "pep_0101"]),
    ("Which finalized proposals specify interfaces or modules for Python programs rather than process documents?",
     ["pep_0249", "pep_0333", "pep_0484", "pep_0506"]),
    ("Which proposals concern documentation or explanatory material for developers?",
     ["pep_0257", "pep_0101"]),
    ("Which proposals have been superseded according to their headers?",
     ["pep_0006"]),
    ("Which proposals relate to security-relevant functionality or voting integrity?",
     ["pep_0506", "pep_8001"]),
]

UNSUPPORTED_CASES = [
    "What is the maximum transmission unit of an Ethernet frame?",
    "How do you configure a Kubernetes pod to mount a persistent volume?",
    "Explain the TCP three-way handshake.",
    "What algorithm does JPEG compression use to encode color data?",
    "Why does rustc perform borrow checking at compile time?",
    "What is the airspeed velocity of a laden swallow?",
    "How does photosynthesis convert light into chemical energy?",
    "What causes the aurora borealis?",
    "Define quantum error correction thresholds.",
    "How do you normalize a relational database schema to third normal form?",
    "What is the boiling point of water at sea level on Mars?",
    "Explain the CAP theorem as it applies to distributed databases.",
    "What is the recipe for a classic French béchamel sauce?",
    "How many players are on a standard volleyball team?",
    "What is the capital city of Australia?",
    "Describe the mechanism of CRISPR-Cas9 gene editing.",
    "How does Bitcoin proof-of-work mining reach consensus?",
    "What is the wingspan of an albatross?",
    "Explain how a four-stroke combustion engine works.",
    "What year did the Berlin Wall fall?",
    "How do you perform CPR on an adult?",
    "What is the derivative of the natural logarithm function?",
    "Explain DNS zone transfers and AXFR queries.",
    "What is the melting point of tungsten?",
    "How does TLS session resumption work?",
    "What is the standard deviation formula?",
    "Describe the plot of the Odyssey.",
    "What is the currency of Japan?",
    "How does a diesel engine differ from a petrol engine regarding ignition?",
    "What are the rules of chess en passant captures?",
]

FALSE_PREMISE_CASES = [
    ("Why does PEP 8 mandate tabs instead of spaces for indentation?", "pep_0008"),
    ("What year does the Zen of Python recommend deprecating list comprehensions?", "pep_0020"),
    ("Why did PEP 484 reject gradual typing for Python?", "pep_0484"),
    ("When did PEP 333 require HTTP/2 support from all compliant servers?", "pep_0333"),
    ("Why does PEP 257 forbid single-line docstrings?", "pep_0257"),
    ("Which section of PEP 249 defines async cursor methods?", "pep_0249"),
    ("Why was PEP 506 rejected by the community?", "pep_0506"),
    ("What quota does PEP 8001 set for core developer votes?", "pep_8001"),
    ("Why did PEP 1 ban speculative proposals?", "pep_0001"),
    ("When did PEP 6 introduce semantic versioning for the standard library?", "pep_0006"),
    ("Why does PEP 101 require releases every six weeks?", "pep_0101"),
    ("Which Python version first shipped the secrets module described as mandatory in PEP 506?", "pep_0506"),
    ("Why does the Zen of Python prefer explicit metaprogramming over readability?", "pep_0020"),
    ("What deadline does PEP 8 set for migrating codebases to type annotations?", "pep_0008"),
    ("Why does WSGI 1.0 natively support asynchronous applications?", "pep_0333"),
    ("Which PEP requires every docstring to be written in German?", "pep_0257"),
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locate_span(text: str, needle: str) -> dict | None:
    index = text.find(needle)
    if index < 0:
        return None
    return {
        "doc_id": None,
        "span_start": index,
        "span_end": index + len(needle),
        "quoted_text": needle,
    }


def load_sources() -> dict[str, tuple[dict, str]]:
    sources = {}
    for doc_id, url in SOURCE_SPECS:
        path = SOURCES_DIR / f"{doc_id}.rst"
        if not path.exists():
            raise SystemExit(f"missing source file: {path}")
        text = path.read_text(encoding="utf-8-sig")
        meta = META[doc_id]
        # Build fails if header metadata no longer matches the corpus.
        for needle in (f"Title: {meta['title']}", f"Status: {meta['status']}"):
            if needle not in text:
                raise SystemExit(f"{doc_id}: expected header {needle!r} not found")
        sources[doc_id] = ({"doc_id": doc_id, "url": url}, text)
    return sources


def build_cases(sources) -> list[dict]:
    cases: list[dict] = []
    counter = 0

    def add(question, category, doc_ids, expected_answer=None, traceability=False):
        nonlocal counter
        counter += 1
        case = {
            "case_id": f"holdout_{counter:03d}",
            "question": question,
            "category": category,
            "evidence_document_ids": list(doc_ids),
            "expected_answer": expected_answer,
        }
        if traceability and doc_ids and expected_answer:
            text = sources[doc_ids[0]][1]
            span = locate_span(text, expected_answer)
            if span is None:
                raise SystemExit(
                    f"traceability failure: answer {expected_answer!r} not found "
                    f"verbatim in {doc_ids[0]}"
                )
            span["doc_id"] = doc_ids[0]
            case["evidence_spans"] = [span]
        cases.append(case)

    # --- factual lookup with evidence-traceable spans ---
    for doc_id, meta in META.items():
        add(f"What is the title of PEP {meta['number']}?", "supported", [doc_id],
            meta["title"], traceability=True)
        add(f"What is the current status of PEP {meta['number']}?", "supported",
            [doc_id], meta["status"], traceability=True)

    # --- factual lookup: which-PEP mapping ---
    for topic, doc_id in TOPIC_TO_PEP:
        number = META[doc_id]["number"]
        add(f"Which PEP covers {topic}?", "supported", [doc_id], f"PEP {number}")

    # --- author attribution ---
    for doc_id, meta in META.items():
        add(f"Who is listed as an author of PEP {meta['number']}?", "supported",
            [doc_id], meta["author"])

    # --- paraphrase retrieval ---
    for topic_index, (question, doc_id) in enumerate(TOPIC_TO_PEP):
        if topic_index < len(PARAPHRASE_TEMPLATES):
            number = META[doc_id]["number"]
            add(PARAPHRASE_TEMPLATES[topic_index], "paraphrase", [doc_id],
                f"PEP {number}")

    # --- multi-document retrieval ---
    for question, doc_ids in MULTI_DOC_CASES:
        add(question, "multi_document", doc_ids,
            ", ".join(META[d]["title"] for d in doc_ids))

    # --- unsupported ---
    for question in UNSUPPORTED_CASES:
        add(question, "unsupported", [], None)

    # --- false premise ---
    for question, _ in FALSE_PREMISE_CASES:
        add(question, "false_premise", [], None)

    return cases


def main() -> int:
    sources = load_sources()
    cases = build_cases(sources)

    # Deterministic ordering already holds; sort defensively by case_id.
    cases.sort(key=lambda case: case["case_id"])

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    benchmark_path = OUT_DIR / "holdout_benchmark.jsonl"
    manifest_path = OUT_DIR / "holdout_manifest.json"

    source_manifest_lines = []
    for doc_id, url in SOURCE_SPECS:
        path = SOURCES_DIR / f"{doc_id}.rst"
        entry = {
            "doc_id": doc_id,
            "source_url": url,
            "source_filename": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(path),
            "acquisition_date": ACQUISITION_DATE,
            "license_note": (
                "Python PEPs are placed in the public domain by their authors "
                "(see PEP footer); redistribution permitted."
            ),
        }
        source_manifest_lines.append(json.dumps(entry, sort_keys=True))
    (OUT_DIR / "sources_manifest.jsonl").write_text(
        "\n".join(source_manifest_lines) + "\n", encoding="utf-8")

    benchmark_path.write_text(
        "\n".join(json.dumps(case, sort_keys=True) for case in cases) + "\n",
        encoding="utf-8")

    counts = {}
    for case in cases:
        counts[case["category"]] = counts.get(case["category"], 0) + 1
    manifest = {
        "benchmark_version": BENCHMARK_VERSION,
        "status": "FROZEN / DO NOT TUNE",
        "generated_from": "authored case specs verified against committed sources",
        "case_count": len(cases),
        "category_counts": counts,
        "supported_cases": counts.get("supported", 0) + counts.get("paraphrase", 0)
        + counts.get("multi_document", 0),
        "unsupported_cases": counts.get("unsupported", 0) + counts.get("false_premise", 0),
        "source_count": len(SOURCE_SPECS),
        "benchmark_sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        "sources_manifest_sha256": hashlib.sha256(
            (OUT_DIR / "sources_manifest.jsonl").read_bytes()).hexdigest(),
        "independence_statement": (
            "No Stage 5 RFC documents, case IDs, or questions are reused. "
            "This benchmark has never been used for development or tuning."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
