#!/usr/bin/env python3
"""Generate and validate candidate replacement unsupported questions.

Checks candidates against ALL existing tracked questions (V1, V2, eval_suite).
Verifies candidates are unsupported by all 7 V3 authoritative source documents.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HOLDOUT_DIR = ROOT / "evaluation" / "holdout_v3"
SOURCES_DIR = HOLDOUT_DIR / "sources"

# ─── Tokenization / similarity ───────────────────────────────────

def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1]

def jaccard_tokens(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

def char_ngrams(text: str, n: int = 4):
    from collections import Counter
    return Counter(text.lower()[i:i+n] for i in range(len(text.lower()) - n + 1))

def jaccard_ngrams(a, b) -> float:
    ka, kb = set(a.keys()), set(b.keys())
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


def normalize_question(text: str) -> str:
    return " ".join(tokenize(text))

# ─── Load all existing questions ─────────────────────────────────

def load_all_existing_questions() -> list[dict]:
    """Return every question in tracked evaluation, development, and regression data."""
    questions = []

    for path in sorted((ROOT / "evaluation").rglob("*")):
        if path.suffix not in {".json", ".jsonl"} or "holdout_v3" in path.parts:
            continue
        try:
            if path.suffix == ".jsonl":
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                records = [json.loads(path.read_text(encoding="utf-8"))]
        except (OSError, json.JSONDecodeError):
            continue
        for record_index, record in enumerate(records):
            for question in extract_questions(record):
                questions.append({
                    "source": str(path.relative_to(ROOT)),
                    "case_id": f"record-{record_index}",
                    "question": question,
                })

    for path in sorted((ROOT / "src").glob("evaluation_suite_*.py")):
        questions.extend(load_python_questions(path))
    for path in sorted((ROOT / "src").glob("regression_tests_*.py")):
        questions.extend(load_python_questions(path))

    return questions


def extract_questions(value) -> list[str]:
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "question" and isinstance(child, str):
                found.append(child)
            else:
                found.extend(extract_questions(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(extract_questions(child))
    return found


def load_python_questions(path: Path) -> list[dict]:
    """Extract literal question fields without executing benchmark code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return []
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "question":
                try:
                    question = ast.literal_eval(value)
                except (ValueError, TypeError):
                    continue
                if isinstance(question, str):
                    found.append({
                        "source": str(path.relative_to(ROOT)),
                        "case_id": "literal",
                        "question": question,
                    })
    return found

# ─── Load V3 sources for unsupported verification ────────────────

def load_v3_sources() -> dict[str, str]:
    sources = {}
    for path in sorted(SOURCES_DIR.glob("*.txt")):
        if path.name == "raw":
            continue
        sources[path.stem] = path.read_text(encoding="utf-8")
    return sources


def content_tokens(text: str) -> list[str]:
    return [token for token in tokenize(text) if len(token) >= 4]


def unsupported_by_all_sources(question: str, v3_sources: dict[str, str]) -> tuple[bool, dict[str, list[str]]]:
    """Reject a candidate if a distinctive three-token phrase appears in any source."""
    q_tokens = content_tokens(question)
    phrases = [" ".join(q_tokens[i:i + 3]) for i in range(len(q_tokens) - 2)]
    findings = {}
    for doc_id, text in v3_sources.items():
        source_tokens = set(content_tokens(text))
        matched = [phrase for phrase in phrases if phrase.split()[0] in source_tokens
                   and phrase in " ".join(content_tokens(text))]
        findings[doc_id] = matched
    return not any(findings.values()), findings

# ─── Candidate questions (3-4 per slot) ──────────────────────────

CANDIDATES = {
    "v3_071": [
        "What is the RTT variance calculation in TCP cubic congestion control?",
        "What is the RTT variance formula used by TCP cubic?",
        "How does TCP cubic compute its RTT variance estimate?",
    ],
    "v3_072": [
        "How does a PLC ladder logic scan cycle execute outputs?",
        "What is the scan cycle order in a PLC ladder logic program?",
        "How does a programmable controller execute ladder diagram rungs?",
    ],
    "v3_073": [
        "Which NIST SP 800-53 control requires immutable audit logs?",
        "What NIST 800-53 control mandates write-once audit records?",
        "Which NIST control addresses tamper-resistant audit trails?",
    ],
    "v3_074": [
        "What is the RISC-V compressed instruction encoding for C.JR?",
        "How is the C.JR instruction encoded in RISC-V compressed format?",
        "What binary encoding does RISC-V assign to the C.JR opcode?",
        "What bit pattern represents the C.JR instruction in RISC-V 16-bit format?",
    ],
    "v3_075": [
        "How does an MRI T2-weighted sequence differentiate tissue types?",
        "What mechanism allows T2-weighted MRI to distinguish tissues?",
        "How does T2 weighting in MRI produce contrast between tissues?",
    ],
    "v3_076": [
        "What is the NEC ampacity derating factor for 3 conductors in conduit?",
        "How does the NEC specify ampacity derating for multiple conductors?",
        "What derating factor does the NEC require for 3 wires in a conduit?",
    ],
    "v3_077": [
        "How does a PID controller compute derivative windup prevention?",
        "What method prevents integral windup in a PID control loop?",
        "How does anti-windup work in a proportional-integral-derivative controller?",
    ],
    "v3_078": [
        "What is the default lease duration for a DHCPv6 IA_NA option?",
        "How long does a DHCPv6 IA_NA lease last by default?",
        "What is the standard DHCPv6 address assignment lease time?",
        "What is the default valid lifetime assigned by a DHCPv6 server?",
        "How long is a DHCPv6 non-temporary address lease valid by default?",
    ],
    "v3_079": [
        "Which ICAO phraseology clears an aircraft for visual approach?",
        "What ICAO radiotelephony phrase is used for visual approach clearance?",
        "How does ATC phrase a visual approach clearance under ICAO rules?",
    ],
    "v3_080": [
        "How does a centrifugal pump calculate net positive suction head?",
        "What is the formula for NPSH available in a centrifugal pump?",
        "How is net positive suction head determined for a centrifugal pump?",
    ],
}

# ─── Check each candidate ────────────────────────────────────────

def check_candidate(question: str, existing: list[dict], v3_sources: dict[str, str]) -> dict:
    """Check a single candidate question against all existing questions and V3 sources."""
    result = {
        "question": question,
        "exact_match": False,
        "high_token_sim": False,
        "high_char_sim": False,
        "shared_stem": False,
        "same_domain": False,
        "unsupported_by_v3": True,
        "source_matches": {},
        "findings": [],
    }

    q_tokens = tokenize(question)
    q_ngrams = char_ngrams(question)

    # Check against all existing questions
    for ex in existing:
        ex_tokens = tokenize(ex["question"])
        jaccard = jaccard_tokens(q_tokens, ex_tokens)

        # Exact duplicate
        if normalize_question(question) == normalize_question(ex["question"]):
            result["exact_match"] = True
            result["findings"].append(f"EXACT_DUPLICATE vs {ex['source']}:{ex['case_id']} (Jaccard=1.0)")
            continue

        # High token similarity
        if jaccard > 0.5:
            result["high_token_sim"] = True
            result["findings"].append(f"HIGH_TOKEN_SIM vs {ex['source']}:{ex['case_id']} (Jaccard={jaccard:.4f})")

        # Character 4-gram overlap
        ex_ngrams = char_ngrams(ex["question"])
        ng_overlap = jaccard_ngrams(q_ngrams, ex_ngrams)
        if ng_overlap > 0.5:
            result["high_char_sim"] = True
            result["findings"].append(f"HIGH_CHAR_SIM vs {ex['source']}:{ex['case_id']} (ngram={ng_overlap:.4f})")

        # Shared generic stem detection
        stems = ["what is the", "how does a", "how does an", "what is the default",
                 "which", "how do you", "what is the recommended"]
        q_stem = " ".join(q_tokens[:3]) if len(q_tokens) >= 3 else " ".join(q_tokens)
        ex_stem = " ".join(ex_tokens[:3]) if len(ex_tokens) >= 3 else " ".join(ex_tokens)
        if q_stem == ex_stem and jaccard < 0.5:
            result["shared_stem"] = True
            result["findings"].append(f"SHARED_STEM with {ex['source']}:{ex['case_id']} (stem='{q_stem}', Jaccard={jaccard:.4f})")

        # Same domain overlap (high similarity but not exact)
        if 0.35 < jaccard <= 0.5:
            result["same_domain"] = True
            result["findings"].append(f"SAME_DOMAIN vs {ex['source']}:{ex['case_id']} (Jaccard={jaccard:.4f})")

    result["unsupported_by_v3"], result["source_matches"] = unsupported_by_all_sources(question, v3_sources)
    for doc_id, matches in result["source_matches"].items():
        if matches:
            result["findings"].append(f"POTENTIALLY_SUPPORTED by {doc_id}: {matches}")

    return result

# ─── Main ────────────────────────────────────────────────────────

def main():
    print("Loading all existing questions...")
    existing = load_all_existing_questions()
    print(f"  Loaded {len(existing)} existing evaluation/dev/regression questions")

    print("Loading V3 source documents...")
    v3_sources = load_v3_sources()
    print(f"  Loaded {len(v3_sources)} V3 source documents")

    print("\n" + "=" * 70)
    print("CANDIDATE VALIDATION RESULTS")
    print("=" * 70)

    selected = {}
    all_rejected = 0
    all_accepted = 0

    for case_id, candidates in CANDIDATES.items():
        print(f"\n--- {case_id} ---")
        best = None
        for i, cand in enumerate(candidates):
            result = check_candidate(cand, existing, v3_sources)
            status = "REJECTED" if (result["exact_match"] or result["high_token_sim"] or result["high_char_sim"] or not result["unsupported_by_v3"]) else "ACCEPTED"

            if status == "REJECTED":
                print(f"  [{i+1}] REJECTED: {cand}")
                for f in result["findings"]:
                    if "EXACT" in f or "HIGH_TOKEN" in f or "HIGH_CHAR" in f or "POTENTIALLY" in f:
                        print(f"       -> {f}")
                all_rejected += 1
            else:
                print(f"  [{i+1}] ACCEPTED: {cand}")
                if result["shared_stem"]:
                    print(f"       NOTE: shares generic stem (not contamination)")
                if result["same_domain"]:
                    for f in result["findings"]:
                        if "SAME_DOMAIN" in f:
                            print(f"       NOTE: {f}")
                if best is None:
                    best = cand
                all_accepted += 1

        if best:
            selected[case_id] = best
            print(f"  >>> SELECTED: {best}")
        else:
            print(f"  >>> NO ACCEPTABLE CANDIDATE for {case_id}!")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Candidates tested: {all_rejected + all_accepted}")
    print(f"  Rejected: {all_rejected}")
    print(f"  Accepted: {all_accepted}")
    print(f"  Selected: {len(selected)}")

    if len(selected) < 10:
        print("\nWARNING: Not enough acceptable candidates!")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("FINAL SELECTED QUESTIONS")
    print("=" * 70)
    for cid in sorted(selected.keys()):
        print(f"  {cid}: {selected[cid]}")

    # Verify no exact matches in final selection
    print("\n" + "=" * 70)
    print("FINAL EXACT-MATCH VERIFICATION")
    print("=" * 70)
    selected_items = list(selected.items())
    for cid, q in selected_items:
        q_tokens = tokenize(q)
        for ex in existing:
            ex_tokens = tokenize(ex["question"])
            j = jaccard_tokens(q_tokens, ex_tokens)
            if normalize_question(q) == normalize_question(ex["question"]):
                print(f"  FAIL: {cid} is EXACT MATCH vs {ex['source']}:{ex['case_id']}")
                sys.exit(1)
            if j > 0.5:
                print(f"  WARN: {cid} high similarity ({j:.4f}) vs {ex['source']}:{ex['case_id']}: {ex['question'][:60]}")
        for other_cid, other_q in selected_items:
            if cid >= other_cid:
                continue
            other_tokens = tokenize(other_q)
            if normalize_question(q) == normalize_question(other_q):
                print(f"  FAIL: {cid} duplicates selected {other_cid}")
                sys.exit(1)
            if (jaccard_tokens(q_tokens, other_tokens) > 0.5
                    or jaccard_ngrams(char_ngrams(q), char_ngrams(other_q)) > 0.5):
                print(f"  FAIL: {cid} is too similar to selected {other_cid}")
                sys.exit(1)
    print("  All 10 selected questions: 0 exact matches, 0 high-similarity matches")
    print("  PASS")

    # Write output for use by author_benchmark.py replacement
    out_path = HOLDOUT_DIR / "replacement_questions.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
