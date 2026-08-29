#!/usr/bin/env python3
"""Contamination checker for Holdout V3 — classified output.

Compares V3 sources and questions against:
  - Holdout V1 sources/questions
  - Holdout V2 sources/questions
  - evaluation_suite_v3 cases

Implements 5 contamination layers:
  1. SHA-256 exact match (gate: reject)
  2. Normalized token Jaccard (flag: >0.3)
  3. Question classification: EXACT_DUPLICATE / HIGH_TOKEN_SIMILARITY /
     HIGH_CHAR_SIMILARITY / SHARED_GENERIC_STEM / SAME_DOMAIN_OVERLAP / CLEAN
  4. Character 4-gram overlap (classified, not flat threshold)

Generic question stems alone are not contamination.
Exact/high-similarity findings gate freeze readiness.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HOLDOUT_DIR = ROOT / "evaluation" / "holdout_v3"
SOURCES_DIR = HOLDOUT_DIR / "sources"

# Generic stems that do NOT constitute contamination
GENERIC_STEMS = {
    "what is the", "how does a", "how does an", "what is the default",
    "which", "how do you", "what is the recommended", "what are the",
    "how does", "what does", "why does", "can", "is the", "are the",
    "what was", "how is", "what is", "how did", "what were",
}

# V3 domain-specific terms (for same-domain detection)
V3_DOMAIN_WORDS = {
    "sqlite", "wal", "vacuum", "postgresql", "postgres", "kubernetes",
    "k8s", "pod", "probe", "systemd", "unit", "directive",
    "opentelemetry", "otel", "propagator", "context", "carrier",
    "oci", "image", "layout", "blob", "manifest",
    "cmake", "preset", "build", "configure", "checkpoint",
    "liveness", "readiness", "startup", "inject", "extract",
    "wants", "requires", "conflicts", "autovacuum", "specifiers",
    "traceparent", "tracestate", "index.json", "wal-index",
}


# ---------------------------------------------------------------------------
# Tokenization / similarity
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1]


def char_ngrams(text: str, n: int = 4) -> Counter:
    return Counter(text.lower()[i:i+n] for i in range(len(text.lower()) - n + 1))


def jaccard_tokens(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def jaccard_ngrams(a: Counter, b: Counter) -> float:
    ka, kb = set(a.keys()), set(b.keys())
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


def get_stem(tokens: list[str], n: int = 3) -> str:
    """Return the first n tokens as a stem string."""
    return " ".join(tokens[:n]) if len(tokens) >= n else " ".join(tokens)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_v3_sources() -> dict[str, str]:
    sources = {}
    for path in sorted(SOURCES_DIR.glob("*.txt")):
        if path.name == "raw":
            continue
        sources[path.stem] = path.read_text(encoding="utf-8")
    return sources


def load_v3_manifest_hashes() -> dict[str, str]:
    manifest_path = HOLDOUT_DIR / "sources_manifest.jsonl"
    hashes = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                hashes[rec["doc_id"]] = rec["raw_sha256"]
    return hashes


def load_v2_sources() -> dict[str, str]:
    v2_dir = ROOT / "evaluation" / "holdout_v2" / "sources"
    sources = {}
    if v2_dir.exists():
        for path in sorted(v2_dir.glob("*.txt")):
            sources[path.stem] = path.read_text(encoding="utf-8")
    return sources


def load_v2_manifest_hashes() -> dict[str, str]:
    manifest_path = ROOT / "evaluation" / "holdout_v2" / "sources_manifest.jsonl"
    hashes = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                hashes[rec["doc_id"]] = rec["sha256"]
    return hashes


def load_v1_sources() -> dict[str, str]:
    v1_dir = ROOT / "evaluation" / "holdout_v1" / "sources"
    sources = {}
    if v1_dir.exists():
        for path in sorted(v1_dir.glob("*.txt")):
            sources[path.stem] = path.read_text(encoding="utf-8")
    return sources


def load_v1_manifest_hashes() -> dict[str, str]:
    manifest_path = ROOT / "evaluation" / "holdout_v1" / "sources_manifest.jsonl"
    hashes = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                hashes[rec["doc_id"]] = rec["sha256"]
    return hashes


def load_v3_benchmark_questions() -> list[str]:
    bench_path = HOLDOUT_DIR / "holdout_v3_benchmark.jsonl"
    questions = []
    if bench_path.exists():
        with open(bench_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                questions.append(rec.get("question", ""))
    return questions


def load_existing_questions() -> list[dict]:
    """Load all existing questions with source metadata."""
    from generate_replacements import load_all_existing_questions
    return load_all_existing_questions()


# ---------------------------------------------------------------------------
# Layer 1: SHA-256 exact match
# ---------------------------------------------------------------------------

def check_layer1_sha_exact(
    v3_hashes: dict[str, str],
    v2_hashes: dict[str, str],
    v1_hashes: dict[str, str],
) -> list[dict]:
    findings = []
    all_existing = {}
    all_existing.update({f"v2:{k}": v for k, v in v2_hashes.items()})
    all_existing.update({f"v1:{k}": v for k, v in v1_hashes.items()})

    for v3_doc_id, v3_sha in v3_hashes.items():
        for source_label, existing_sha in all_existing.items():
            if v3_sha == existing_sha:
                findings.append({
                    "layer": 1,
                    "classification": "EXACT_DUPLICATE",
                    "severity": "GATE",
                    "v3_doc_id": v3_doc_id,
                    "match_source": source_label,
                    "sha256": v3_sha,
                })
    return findings


# ---------------------------------------------------------------------------
# Layer 2: Normalized token Jaccard (source text)
# ---------------------------------------------------------------------------

def check_layer2_token_jaccard(
    v3_sources: dict[str, str],
    v2_sources: dict[str, str],
    v1_sources: dict[str, str],
    threshold: float = 0.3,
) -> list[dict]:
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
                    "classification": "HIGH_SOURCE_SIMILARITY",
                    "severity": "FLAG",
                    "v3_doc_id": v3_doc_id,
                    "match_source": source_label,
                    "jaccard": round(j, 4),
                })
    return findings


# ---------------------------------------------------------------------------
# Layer 3-4: Question classification
# ---------------------------------------------------------------------------

def classify_question_pair(
    v3_q: str, v3_tokens: list[str], v3_ng: Counter,
    ex_q: str, ex_tokens: list[str], ex_ng: Counter,
) -> dict | None:
    """Classify the relationship between a V3 question and an existing question.

    Returns None if CLEAN (no concerning overlap).
    Returns a dict with classification and details otherwise.
    """
    jaccard = jaccard_tokens(v3_tokens, ex_tokens)
    ng_overlap = jaccard_ngrams(v3_ng, ex_ng)

    # EXACT_DUPLICATE: Jaccard = 1.0
    if normalize_question(v3_q) == normalize_question(ex_q):
        return {
            "classification": "EXACT_DUPLICATE",
            "severity": "GATE",
            "jaccard": round(jaccard, 4),
            "char_ngram": round(ng_overlap, 4),
        }

    # HIGH_TOKEN_SIMILARITY: Jaccard > 0.5
    if jaccard > 0.5:
        return {
            "classification": "HIGH_TOKEN_SIMILARITY",
            "severity": "GATE",
            "jaccard": round(jaccard, 4),
            "char_ngram": round(ng_overlap, 4),
        }

    # HIGH_CHAR_SIMILARITY: char 4-gram > 0.5
    if ng_overlap > 0.5:
        return {
            "classification": "HIGH_CHAR_SIMILARITY",
            "severity": "GATE",
            "jaccard": round(jaccard, 4),
            "char_ngram": round(ng_overlap, 4),
        }

    # Check for shared generic stem
    v3_stem = get_stem(v3_tokens)
    ex_stem = get_stem(ex_tokens)
    shared_stem = v3_stem == ex_stem and v3_stem in GENERIC_STEMS

    # Check for same-domain overlap (moderate similarity + domain terms)
    v3_domain = [w for w in v3_tokens if w in V3_DOMAIN_WORDS]
    ex_domain = [w for w in ex_tokens if w in V3_DOMAIN_WORDS]
    domain_overlap = set(v3_domain) & set(ex_domain)

    if shared_stem and jaccard < 0.5:
        return {
            "classification": "SHARED_GENERIC_STEM",
            "severity": "INFO",
            "jaccard": round(jaccard, 4),
            "char_ngram": round(ng_overlap, 4),
            "stem": v3_stem,
        }

    if domain_overlap and 0.2 < jaccard <= 0.5:
        return {
            "classification": "SAME_DOMAIN_OVERLAP",
            "severity": "REVIEW",
            "jaccard": round(jaccard, 4),
            "char_ngram": round(ng_overlap, 4),
            "shared_domain_terms": sorted(domain_overlap),
        }

    # Moderate overlap without domain terms or shared stem
    if jaccard > 0.3 or ng_overlap > 0.4:
        return {
            "classification": "MODERATE_OVERLAP",
            "severity": "REVIEW",
            "jaccard": round(jaccard, 4),
            "char_ngram": round(ng_overlap, 4),
        }

    return None  # CLEAN


def check_question_classification(
    v3_questions: list[str],
    existing_questions: list[dict],
) -> list[dict]:
    """Classify all V3 vs existing question pairs."""
    findings = []
    v3_tokenized = [(q, tokenize(q), char_ngrams(q)) for q in v3_questions]

    for i, (v3_q, v3_tokens, v3_ng) in enumerate(v3_tokenized):
        for ex in existing_questions:
            ex_tokens = tokenize(ex["question"])
            ex_ng = char_ngrams(ex["question"])
            result = classify_question_pair(v3_q, v3_tokens, v3_ng, ex["question"], ex_tokens, ex_ng)
            if result:
                result["layer"] = 3
                result["v3_question_index"] = i
                result["v3_question"] = v3_q[:80]
                result["existing_source"] = ex["source"]
                result["existing_case_id"] = ex["case_id"]
                result["existing_question"] = ex["question"][:80]
                findings.append(result)

    return findings


def normalize_question(text: str) -> str:
    return " ".join(tokenize(text))


def check_internal_question_duplicates(v3_questions: list[str]) -> list[dict]:
    findings = []
    for i, question in enumerate(v3_questions):
        for j in range(i):
            other = v3_questions[j]
            jaccard = jaccard_tokens(tokenize(question), tokenize(other))
            ngram = jaccard_ngrams(char_ngrams(question), char_ngrams(other))
            if normalize_question(question) == normalize_question(other):
                classification, severity = "EXACT_DUPLICATE", "GATE"
            elif jaccard > 0.5:
                classification, severity = "HIGH_TOKEN_SIMILARITY", "GATE"
            elif ngram > 0.5:
                classification, severity = "HIGH_CHAR_SIMILARITY", "GATE"
            else:
                continue
            findings.append({
                "layer": 3,
                "classification": classification,
                "severity": severity,
                "v3_question_index": i,
                "v3_question": question,
                "existing_source": "V3",
                "existing_case_id": f"index-{j}",
                "existing_question": other,
                "jaccard": round(jaccard, 4),
                "char_ngram": round(ngram, 4),
            })
    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_contamination_check(*, include_questions: bool = False) -> dict:
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
    print("Layer 2: Source token Jaccard...")
    l2 = check_layer2_token_jaccard(v3_sources, v2_sources, v1_sources)
    all_findings.extend(l2)
    print(f"  Found {len(l2)} high-Jaccard source pairs")

    # Layers 3-4: Question classification
    classified = {"EXACT_DUPLICATE": 0, "HIGH_TOKEN_SIMILARITY": 0,
                  "HIGH_CHAR_SIMILARITY": 0, "SHARED_GENERIC_STEM": 0,
                  "SAME_DOMAIN_OVERLAP": 0, "MODERATE_OVERLAP": 0, "CLEAN": 0}
    gates = []
    reviews = []
    infos = []

    if include_questions:
        print("Loading existing questions...")
        existing_qs = load_existing_questions()
        v3_qs = load_v3_benchmark_questions()

        if v3_qs:
            print("Layers 3-4: Question classification...")
            l3 = check_question_classification(v3_qs, existing_qs)
            l3.extend(check_internal_question_duplicates(v3_qs))
            all_findings.extend(l3)

            for f in l3:
                cls = f["classification"]
                classified[cls] = classified.get(cls, 0) + 1
                if f["severity"] == "GATE":
                    gates.append(f)
                elif f["severity"] == "REVIEW":
                    reviews.append(f)
                elif f["severity"] == "INFO":
                    infos.append(f)

            # Count CLEAN V3 questions (no findings)
            flagged_indices = set(f["v3_question_index"] for f in l3)
            classified["CLEAN"] = len(v3_qs) - len(flagged_indices)
        else:
            print("  Skipped: no V3 benchmark questions yet")
    else:
        print("Layers 3-4: Skipped (no questions to check)")

    # Summary
    gate_count = len([f for f in all_findings if f.get("severity") == "GATE"])
    flag_count = len([f for f in all_findings if f.get("severity") == "FLAG"])

    print(f"\n{'=' * 70}")
    print("CONTAMINATION CLASSIFICATION SUMMARY")
    print(f"{'=' * 70}")
    print(f"Layer 1 (SHA-256): {len(l1)} exact matches")
    print(f"Layer 2 (source Jaccard): {len(l2)} high-similarity pairs")
    print()
    print("Question classification:")
    for cls, count in sorted(classified.items()):
        label = cls
        if cls == "EXACT_DUPLICATE":
            label += " (GATE — must be 0)"
        elif cls == "HIGH_TOKEN_SIMILARITY":
            label += " (GATE — must be 0)"
        elif cls == "HIGH_CHAR_SIMILARITY":
            label += " (GATE — must be 0)"
        elif cls == "SHARED_GENERIC_STEM":
            label += " (not contamination)"
        elif cls == "SAME_DOMAIN_OVERLAP":
            label += " (review)"
        elif cls == "CLEAN":
            label += " (no concern)"
        print(f"  {label}: {count}")

    if gates:
        print(f"\nGATE findings ({len(gates)}):")
        for g in gates:
            print(f"  [{g['classification']}] V3 Q{g['v3_question_index']+1}: \"{g['v3_question']}\"")
            print(f"    vs {g['existing_source']}:{g['existing_case_id']}: \"{g['existing_question']}\"")
            print(f"    Jaccard={g['jaccard']}, ngram={g['char_ngram']}")

    if reviews:
        print(f"\nREVIEW findings ({len(reviews)}):")
        for r in reviews:
            extra = ""
            if "shared_domain_terms" in r:
                extra = f" shared_domain={r['shared_domain_terms']}"
            elif "stem" in r:
                extra = f" stem='{r['stem']}'"
            print(f"  [{r['classification']}] V3 Q{r['v3_question_index']+1}: \"{r['v3_question']}\"")
            print(f"    vs {r['existing_source']}:{r['existing_case_id']}: \"{r['existing_question']}\"")
            print(f"    Jaccard={r['jaccard']}, ngram={r['char_ngram']}{extra}")

    if infos:
        print(f"\nINFO findings ({len(infos)} — shared generic stems, not contamination):")
        # Group by stem
        by_stem: dict[str, int] = {}
        for info in infos:
            stem = info.get("stem", "unknown")
            by_stem[stem] = by_stem.get(stem, 0) + 1
        for stem, count in sorted(by_stem.items()):
            print(f"  Stem \"{stem}\": {count} questions share this pattern")

    # Determine pass/fail
    has_gates = gate_count > 0 or len(l1) > 0 or len(l2) > 0

    print(f"\n{'=' * 70}")
    if has_gates:
        print("VERDICT: FAIL — gate findings present")
    else:
        print("VERDICT: PASS — 0 exact duplicates, 0 high-similarity, 0 high-char-overlap")
    print(f"{'=' * 70}")

    return {
        "findings": all_findings,
        "gate_count": gate_count,
        "flag_count": flag_count,
        "classified": classified,
        "passed": not has_gates,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="V3 contamination checker (classified)")
    parser.add_argument("--with-questions", action="store_true",
                        help="Also check question contamination with classification")
    args = parser.parse_args()

    result = run_contamination_check(include_questions=args.with_questions)
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
