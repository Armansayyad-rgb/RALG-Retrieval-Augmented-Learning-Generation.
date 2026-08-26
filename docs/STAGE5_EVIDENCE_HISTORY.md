# Stage 5 Evidence History

**Status of BOTH results:** PRELIMINARY / UNREVIEWED. Neither result is
independent human validation. Stage 5 human review is still pending
(see `docs/STAGE6_HUMAN_REVIEW_GUIDE.md`).

---

## 1. Legacy (pre-hybrid) result — HISTORICAL

- **Artifact:** `evaluation/results/stage5_preliminary_results_legacy.json`
  - SHA-256: `74acdd43eea7f7c7c9d2832f4a236d6aac402f7cffb7bf6d580211d70d6981b1`
  - Preserved byte-for-byte from the artifact committed at `2a3341d`
    ("Acquire independent Stage 5 evidence corpus", 2026-08-25 11:28 IST).
- **Implementation period:** the evaluator's "ralg" arm routed through
  `retriever_v2.retrieve()` — i.e., the core V2 lexical retriever was being
  compared against a term-overlap lexical baseline, before the hybrid
  retriever existed.
- **Metrics (RALG arm):**

| Metric | Value |
|---|---|
| Recall@1 | 37.14% |
| Recall@3 | 77.62% |
| Recall@5 | 92.86% |
| MRR | 0.5863 |
| Unsupported rejection | 100% |
| False-support rate | 0% |

(Lexical baseline: R@1 40.48% / R@3 87.62% / R@5 100% / MRR 0.6485.)

## 2. Why both artifacts exist

The Stage 5 benchmark was acquired early and used as the measuring stick
while the retrieval architecture was still being developed:

1. `27d3c7f` introduced the full-question-first hybrid retriever for Stage 5.
2. `42eb90e` ("route evaluator through V4 hybrid pipeline") fixed the
   evaluator to import `retrieve()` from `retriever_hybrid` instead of
   `retriever_v2`, so the "ralg" arm measured the actual hybrid path.
3. The regenerated output of that fixed evaluator was reported in narrative
   documents but never committed; only the pre-hybrid artifact remained in
   the repo, creating an apparent contradiction between docs and evidence.

## 3. Current (hybrid) result — AUTHORITATIVE, still preliminary

- **Artifact:** `evaluation/results/stage5_preliminary_results.json`
  - SHA-256: `46c777158f062b9b16bde005bbc1ba84d7176d509dfe38b294e3cff8544f63e4`
  - Regenerated from the frozen current code (master `60dc7cc` lineage,
    branch `validation/stage6-independent-review`) with the evaluator exactly
    as defined — no tuning, no fixture changes.
- **Implementation:** `retriever_hybrid` (full-question-first fusion over
  `retriever_v2`), the single authoritative runtime retrieval path since
  `91c322a`.
- **Metrics (RALG hybrid):**

| Metric | Value |
|---|---|
| Recall@1 | 50.95% |
| Recall@3 | 90.95% |
| Recall@5 | 100.00% |
| MRR | 0.7098 |
| Unsupported rejection | 100% |
| False-support rate | 0% |

Lexical baseline reproduced identically to the legacy run:
R@1 40.48% / R@3 87.62% / R@5 100% / MRR 0.6485, rejection 100%, false
support 0%.

Latency values differ between runs (machine/timing-specific) and are not part
of the claim set.

## 4. Reproduction command

```
.venv\Scripts\python.exe scripts\stage5_preliminary_evaluation.py
```

(writes `evaluation/results/stage5_preliminary_results.json`; pass
`--output <path>` to write elsewhere). Ranked-recall metrics are deterministic
given frozen fixtures + code; latency is not.

## 5. Benchmark fixtures used by both runs

| Fixture | SHA-256 |
|---|---|
| `evaluation/stage5_review_queue.jsonl` (300 cases) | `9eee7e1ae634ba26cdd418b910e7334566bd60d7753d8538365effe9c9ca113d` |
| `evaluation/stage5_source_manifest.jsonl` (50 RFCs) | `6c66d569c26bcb823250f785ead62bde249324d3f82201d2cc845c98a9baff0b` |
| `evaluation/stage5_documents/` (50 files, combined digest) | `2fc45bc32bc689fb7fb43b1953deb3275f5bcd1c2676a60ad628bcfc680ad023` |

Identical across legacy and current runs. No question, label, RFC, manifest
entry, or expected answer changed at any point in this reconciliation.

## 6. Important caveat

Stage 5 was used during architecture development (the hybrid retriever was
built and iterated against these cases). It is therefore **not a pristine
final holdout set**, and neither result here is independent human validation.
Independent human review remains pending; see the Stage 6 freeze record and
review guide.
