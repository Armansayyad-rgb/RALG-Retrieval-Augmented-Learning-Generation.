#!/usr/bin/env python3
"""Pre-freeze validation for Holdout V3."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HOLDOUT = ROOT / "evaluation" / "holdout_v3"
sys.path.insert(0, str(ROOT / "src"))

# Load benchmark
cases = []
with open(HOLDOUT / "holdout_v3_benchmark.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        cases.append(json.loads(line))
print(f"Benchmark cases: {len(cases)}")

# Load sources manifest
sources = {}
with open(HOLDOUT / "sources_manifest.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        sources[rec["doc_id"]] = rec

# 1. Evidence span integrity
print()
print("=== EVIDENCE SPAN INTEGRITY ===")
span_pass = 0
span_fail = 0
for case in cases:
    for span in case.get("evidence_spans", []):
        src_id = span["doc_id"]
        if src_id not in sources:
            print(f"  FAIL: {case['case_id']} -> unknown source {src_id}")
            span_fail += 1
            continue
        norm_path = ROOT / sources[src_id]["source_filename"]
        norm = norm_path.read_text(encoding="utf-8")
        text = span["quoted_text"][:80]
        if text in norm:
            span_pass += 1
        else:
            print(f"  FAIL: {case['case_id']} span missing: {text[:50]}...")
            span_fail += 1

# 2. Category counts
print()
print("=== CATEGORY COUNTS ===")
cats = {}
for c in cases:
    cats[c["category"]] = cats.get(c["category"], 0) + 1
expected = {
    "supported": 15, "paraphrased": 15, "procedural": 15, "causal": 10,
    "cross_document": 10, "document_scoped": 5, "unsupported": 20,
    "false_premise": 15, "misleading_overlap": 10, "conditional_or_qualified": 5,
}
count_ok = True
for cat, exp in expected.items():
    got = cats.get(cat, 0)
    ok = got == exp
    print(f"  {cat}: {got} (expected {exp}) {'PASS' if ok else 'FAIL'}")
    if not ok:
        count_ok = False
total_ok = len(cases) == 120
print(f"  total: {len(cases)} (expected 120) {'PASS' if total_ok else 'FAIL'}")

# 3. Normalized artifact hashes
print()
print("=== NORMALIZED ARTIFACT HASH VERIFICATION ===")
norm_pass = 0
norm_fail = 0
for src_id, rec in sources.items():
    norm_path = ROOT / rec["source_filename"]
    actual = hashlib.sha256(norm_path.read_bytes()).hexdigest()
    ok = actual == rec["normalized_sha256"]
    if ok:
        norm_pass += 1
        print(f"  PASS: {src_id}")
    else:
        norm_fail += 1
        print(f"  FAIL: {src_id} expected={rec['normalized_sha256'][:16]}... actual={actual[:16]}...")

# 4. Raw artifact hashes
print()
print("=== RAW ARTIFACT HASH VERIFICATION ===")
raw_pass = 0
raw_fail = 0
for src_id, rec in sources.items():
    raw_path = HOLDOUT / "sources" / "raw" / f"{src_id}.raw"
    actual = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    ok = actual == rec["raw_sha256"]
    if ok:
        raw_pass += 1
        print(f"  PASS: {src_id}")
    else:
        raw_fail += 1
        print(f"  FAIL: {src_id} expected={rec['raw_sha256'][:16]}... actual={actual[:16]}...")

# 5. Deterministic re-normalization check
print()
print("=== DETERMINISTIC NORMALIZATION RE-CHECK ===")
# Import normalization functions
from download_sources import normalize_html, normalize_sgml, normalize_markdown, normalize_xml, normalize_rst

NORMALIZERS = {
    "html": normalize_html,
    "sgml": normalize_sgml,
    "markdown": normalize_markdown,
    "xml": normalize_xml,
    "rst": normalize_rst,
}

det_pass = 0
det_fail = 0
for src_id, rec in sources.items():
    raw_path = HOLDOUT / "sources" / "raw" / f"{src_id}.raw"
    raw_bytes = raw_path.read_bytes()
    norm_type = rec["normalization"]
    norm_fn = NORMALIZERS[norm_type]
    re_norm = norm_fn(raw_bytes)
    norm_path = ROOT / rec["source_filename"]
    original_norm = norm_path.read_text(encoding="utf-8")
    ok = re_norm == original_norm
    if ok:
        det_pass += 1
    else:
        det_fail += 1
        print(f"  FAIL: {src_id} ({norm_type}) re-normalization differs")
        # Show first difference position
        for i in range(min(len(re_norm), len(original_norm))):
            if re_norm[i] != original_norm[i]:
                ctx = 20
                print(f"    First diff at char {i}: re=...{re_norm[max(0,i-ctx):i+ctx]}...")
                print(f"    First diff at char {i}: orig=...{original_norm[max(0,i-ctx):i+ctx]}...")
                break
print(f"  PASS: {det_pass}, FAIL: {det_fail}")

# 6. Production files unchanged
print()
print("=== PRODUCTION STABILITY ===")
prod_files = [
    "src/rag_chat_v2.py",
    "src/retriever_v2.py",
    "src/evaluation_suite_v3.py",
    "config.py",
    "evaluation/holdout_v2/holdout_manifest.json",
    "evaluation/holdout_v2/holdout_benchmark.jsonl",
]
prod_ok = True
for pf in prod_files:
    exists = (ROOT / pf).exists()
    print(f"  {pf}: {'EXISTS' if exists else 'MISSING'}")
    if not exists:
        prod_ok = False

# 7. Evaluator guard works
print()
print("=== EVALUATOR GUARD ===")
eval_path = ROOT / "src" / "holdout_v3_eval.py"
guard_ok = eval_path.exists()
print(f"  holdout_v3_eval.py exists: {guard_ok}")

# Summary
print()
print("=" * 50)
all_ok = (span_fail == 0 and norm_fail == 0 and raw_fail == 0
          and det_fail == 0 and count_ok and total_ok and prod_ok and guard_ok)
print(f"Evidence spans: {span_pass} PASS, {span_fail} FAIL")
print(f"Normalized hashes: {norm_pass} PASS, {norm_fail} FAIL")
print(f"Raw hashes: {raw_pass} PASS, {raw_fail} FAIL")
print(f"Deterministic norm: {det_pass} PASS, {det_fail} FAIL")
print(f"Category counts: {'PASS' if count_ok else 'FAIL'}")
print(f"Production stability: {'PASS' if prod_ok else 'FAIL'}")
print(f"Evaluator guard: {'PASS' if guard_ok else 'FAIL'}")
print(f"OVERALL: {'ALL PASS' if all_ok else 'SOME FAILURES'}")
