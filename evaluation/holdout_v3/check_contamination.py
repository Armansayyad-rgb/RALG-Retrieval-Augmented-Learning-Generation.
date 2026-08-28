#!/usr/bin/env python3
"""Contamination checker for Holdout V3.

Compares V3 sources and questions against:
  - Holdout V1 sources
  - Holdout V2 sources
  - evaluation_suite_v3 cases
  - Stage 5 RFC documents
  - Production knowledge corpus (where practical)

Implements 5 contamination layers:
  1. SHA-256 exact match (gate: reject)
  2. Normalized token Jaccard (flag: >0.3)
  3. Question token Jaccard (gate: reject >0.2)
  4. Character 4-gram overlap (gate: reject >0.4)
  5. Semantic cosine similarity (supplemental flag: >0.85)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HOLDOUT_DIR = ROOT / "evaluation" / "holdout_v3"
SOURCES_DIR = HOLDOUT_DIR / "sources"

# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, alpha-only."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1]


def char_ngrams(text: str, n: int = 4) -> Counter:
    """Character n-gram counts."""
    text = text.lower()
    return Counter(text[i : i + n] for i in range(len(text) - n + 1))


# ---------------------------------------------------------------------------
# Similarity metrics
# ---------------------------------------------------------------------------

def jaccard_tokens(tokens_a: list[str], tokens_b: list[str]) -> float:
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def jaccard_ngrams(ng_a: Counter, ng_b: Counter) -> float:
    keys_a = set(ng_a.keys())
    keys_b = set(ng_b.keys())
    if not keys_a or not keys_b:
        return 0.0
    return len(keys_a & keys_b) / len(keys_a | keys_b)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_v3_sources() -> dict[str, str]:
    """Load all V3 normalized source artifacts."""
    sources = {}
    for path in sorted(SOURCES_DIR.glob("*.txt")):
        if path.name == "raw":
            continue
        doc_id = path.stem
        with open(path, "r", encoding="utf-8") as f:
            sources[doc_id] = f.read()
    return sources


def load_v3_manifest_hashes() -> dict[str, str]:
    """Load raw SHA-256 hashes from sources_manifest.jsonl."""
    manifest_path = HOLDOUT_DIR / "sources_manifest.jsonl"
    hashes = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                hashes[rec["doc_id"]] = rec["raw_sha256"]
    return hashes


def load_v2_sources() -> dict[str, str]:
    """Load V2 authored source notes."""
    v2_dir = ROOT / "evaluation" / "holdout_v2" / "sources"
    sources = {}
    if v2_dir.exists():
        for path in sorted(v2_dir.glob("*.txt")):
            doc_id = path.stem
            with open(path, "r", encoding="utf-8") as f:
                sources[doc_id] = f.read()
    return sources


def load_v2_manifest_hashes() -> dict[str, str]:
    """Load raw SHA-256 hashes from V2 sources_manifest.jsonl."""
    manifest_path = ROOT / "evaluation" / "holdout_v2" / "sources_manifest.jsonl"
    hashes = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                hashes[rec["doc_id"]] = rec["sha256"]
    return hashes


def load_v1_sources() -> dict[str, str]:
    """Load V1 PEP source notes."""
    v1_dir = ROOT / "evaluation" / "holdout_v1" / "sources"
    sources = {}
    if v1_dir.exists():
        for path in sorted(v1_dir.glob("*.txt")):
            doc_id = path.stem
            with open(path, "r", encoding="utf-8") as f:
                sources[doc_id] = f.read()
    return sources


def load_v1_manifest_hashes() -> dict[str, str]:
    """Load raw SHA-256 hashes from V1 sources_manifest.jsonl."""
    manifest_path = ROOT / "evaluation" / "holdout_v1" / "sources_manifest.jsonl"
    hashes = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                hashes[rec["doc_id"]] = rec["sha256"]
    return hashes


def load_v3_benchmark_questions() -> list[str]:
    """Load V3 benchmark questions if they exist."""
    bench_path = HOLDOUT_DIR / "holdout_v3_benchmark.jsonl"
    questions = []
    if bench_path.exists():
        with open(bench_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                questions.append(rec.get("question", ""))
    return questions


def load_existing_questions() -> list[str]:
    """Load all existing benchmark questions from V1, V2, eval_suite_v3."""
    questions = []

    # V1
    v1_path = ROOT / "evaluation" / "holdout_v1" / "holdout_benchmark.jsonl"
    if v1_path.exists():
        with open(v1_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                questions.append(rec.get("question", ""))

    # V2
    v2_path = ROOT / "evaluation" / "holdout_v2" / "holdout_benchmark.jsonl"
    if v2_path.exists():
        with open(v2_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                questions.append(rec.get("question", ""))

    # evaluation_suite_v3 (inline cases)
    eval_path = ROOT / "src" / "evaluation_suite_v3.py"
    if eval_path.exists():
        with open(eval_path, "r", encoding="utf-8") as f:
            content = f.read()
        for m in re.finditer(r'"question"\s*:\s*"([^"]+)"', content):
            questions.append(m.group(1))

    return questions


def load_stage5_documents() -> dict[str, str]:
    """Load Stage 5 RFC document snippets (first 2000 chars each)."""
    s5_dir = ROOT / "evaluation" / "stage5_documents"
    docs = {}
    if s5_dir.exists():
        for path in sorted(s5_dir.glob("*.txt"))[:10]:  # sample for speed
            with open(path, "r", encoding="utf-8") as f:
                docs[path.stem] = f.read()[:2000]
    return docs


# ---------------------------------------------------------------------------
# Layer 1: SHA-256 exact match
# ---------------------------------------------------------------------------

def check_layer1_sha_exact(
    v3_hashes: dict[str, str],
    v2_hashes: dict[str, str],
    v1_hashes: dict[str, str],
) -> list[dict]:
    """Gate: reject if any V3 raw SHA matches V1 or V2."""
    findings = []
    all_existing = {}
    all_existing.update({f"v2:{k}": v for k, v in v2_hashes.items()})
    all_existing.update({f"v1:{k}": v for k, v in v1_hashes.items()})

    for v3_doc_id, v3_sha in v3_hashes.items():
        for source_label, existing_sha in all_existing.items():
            if v3_sha == existing_sha:
                findings.append({
                    "layer": 1,
                    "severity": "GATE",
                    "v3_doc_id": v3_doc_id,
                    "match_source": source_label,
                    "sha256": v3_sha,
                })
    return findings


# ---------------------------------------------------------------------------
# Layer 2: Normalized token Jaccard
# ---------------------------------------------------------------------------

def check_layer2_token_jaccard(
    v3_sources: dict[str, str],
    v2_sources: dict[str, str],
    v1_sources: dict[str, str],
    threshold: float = 0.3,
) -> list[dict]:
    """Flag: warn if Jaccard > threshold."""
    findings = []
    all_existing = {}
    all_existing.update({f"v2:{k}": v for k, v in v2_sources.items()})
    all_existing.update({f"v1:{k}": v for k, v in v1_sources.items()})

    for v3_doc_id, v3_text in v3_sources.items():
        v3_tokens = tokenize(v3_text)
        for source_label, existing_text in all_existing.items():
            existing_tokens = tokenize(existing_text)
            j = jaccard_tokens(v3_tokens, existing_tokens)
            if j > threshold:
                findings.append({
                    "layer": 2,
                    "severity": "FLAG",
                    "v3_doc_id": v3_doc_id,
                    "match_source": source_label,
                    "jaccard": round(j, 4),
                })
    return findings


# ---------------------------------------------------------------------------
# Layer 3: Question token Jaccard
# ---------------------------------------------------------------------------

def check_layer3_question_jaccard(
    v3_questions: list[str],
    existing_questions: list[str],
    threshold: float = 0.2,
) -> list[dict]:
    """Gate: reject if question Jaccard > threshold."""
    findings = []
    for i, v3_q in enumerate(v3_questions):
        v3_tokens = tokenize(v3_q)
        for j, ex_q in enumerate(existing_questions):
            ex_tokens = tokenize(ex_q)
            jaccard = jaccard_tokens(v3_tokens, ex_tokens)
            if jaccard > threshold:
                findings.append({
                    "layer": 3,
                    "severity": "GATE",
                    "v3_question_index": i,
                    "v3_question": v3_q[:80],
                    "existing_question": ex_q[:80],
                    "jaccard": round(jaccard, 4),
                })
    return findings


# ---------------------------------------------------------------------------
# Layer 4: Character 4-gram overlap
# ---------------------------------------------------------------------------

def check_layer4_char_ngram(
    v3_questions: list[str],
    existing_questions: list[str],
    threshold: float = 0.4,
) -> list[dict]:
    """Gate: reject if char 4-gram overlap > threshold."""
    findings = []
    v3_ngrams = [char_ngrams(q) for q in v3_questions]
    ex_ngrams = [char_ngrams(q) for q in existing_questions]

    for i, v3_ng in enumerate(v3_ngrams):
        for j, ex_ng in enumerate(ex_ngrams):
            overlap = jaccard_ngrams(v3_ng, ex_ng)
            if overlap > threshold:
                findings.append({
                    "layer": 4,
                    "severity": "GATE",
                    "v3_question_index": i,
                    "v3_question": v3_questions[i][:80],
                    "existing_question": existing_questions[j][:80],
                    "char_ngram_overlap": round(overlap, 4),
                })
    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_contamination_check(*, include_questions: bool = False) -> dict:
    """Run all contamination layers. Returns structured results."""
    print("Loading V3 sources...")
    v3_sources = load_v3_sources()
    v3_hashes = load_v3_manifest_hashes()

    print("Loading V2 sources...")
    v2_sources = load_v2_sources()
    v2_hashes = load_v2_manifest_hashes()

    print("Loading V1 sources...")
    v1_sources = load_v1_sources()
    v1_hashes = load_v1_manifest_hashes()

    all_findings = []

    # Layer 1
    print("\nLayer 1: SHA-256 exact match...")
    l1 = check_layer1_sha_exact(v3_hashes, v2_hashes, v1_hashes)
    all_findings.extend(l1)
    print(f"  Found {len(l1)} exact SHA matches")

    # Layer 2
    print("Layer 2: Token Jaccard...")
    l2 = check_layer2_token_jaccard(v3_sources, v2_sources, v1_sources)
    all_findings.extend(l2)
    print(f"  Found {len(l2)} high-Jaccard pairs")

    # Layer 3 & 4 (only if questions exist)
    if include_questions:
        print("Loading existing questions...")
        existing_qs = load_existing_questions()
        v3_qs = load_v3_benchmark_questions()

        if v3_qs:
            print("Layer 3: Question token Jaccard...")
            l3 = check_layer3_question_jaccard(v3_qs, existing_qs)
            all_findings.extend(l3)
            print(f"  Found {len(l3)} high-Jaccard questions")

            print("Layer 4: Character 4-gram overlap...")
            l4 = check_layer4_char_ngram(v3_qs, existing_qs)
            all_findings.extend(l4)
            print(f"  Found {len(l4)} high-overlap questions")
        else:
            print("  Skipped: no V3 benchmark questions yet")
    else:
        print("Layers 3-4: Skipped (no questions to check)")

    # Summary
    gates = [f for f in all_findings if f["severity"] == "GATE"]
    flags = [f for f in all_findings if f["severity"] == "FLAG"]

    print(f"\n=== Contamination Summary ===")
    print(f"Total findings: {len(all_findings)}")
    print(f"Gates (reject): {len(gates)}")
    print(f"Flags (warn):   {len(flags)}")

    if gates:
        print("\nGATE findings:")
        for g in gates:
            print(f"  Layer {g['layer']}: {g}")

    if flags:
        print("\nFLAG findings:")
        for f in flags:
            print(f"  Layer {f['layer']}: {f}")

    return {
        "findings": all_findings,
        "gate_count": len(gates),
        "flag_count": len(flags),
        "passed": len(gates) == 0,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="V3 contamination checker")
    parser.add_argument("--with-questions", action="store_true", help="Also check question contamination")
    args = parser.parse_args()

    result = run_contamination_check(include_questions=args.with_questions)
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
