# Stage 6 Human Review Guide

**Audience:** independent technical reviewers who have never seen the RALG
codebase. You are reviewing a **benchmark**, not a system: your job is to
decide whether each benchmark case is well-posed and correctly labeled. You
will not see, and must not consider, what any retrieval system did with these
questions.

This guide supersedes nothing; `docs/STAGE5_REVIEW_GUIDE.md` remains the
detailed source-selection and provenance reference. This document is the
operational how-to for the Stage 6 review round.

---

## 1. What you receive

A blind review pack under `evaluation/stage5_review_pack/`:

| File | Contents |
|---|---|
| `full_review.jsonl` | All 300 cases |
| `pilot_review.jsonl` | Deterministic 75-case pilot (seed 5202025; 38 supported / 37 unsupported) |
| `review_pack_manifest.json` | Audit summary of the pack |

Plus `evaluation/stage5_review_template.csv`, the answer sheet.

Each case shows only:

- `case_id`
- `question`
- `claimed_supported` — the label you are asked to verify (true/false)
- `proposed_reference_answer` — for supported cases
- `evidence_excerpt` — quoted span from the cited RFC
- `document_title`, `rfc_number`, `canonical_source_url` — provenance
- `difficulty`
- an empty `review` block for your decisions

**Blinding guarantee:** the pack contains no RALG score, no lexical score, no
system ranking output, no model confidence, and no pass/fail outcome for any
retrieval system. A automated blinding check
(`scripts/stage5_review_blinding_check.py`) enforces this before every
release of the pack. If you discover any leaked performance information,
report it — the round is compromised.

## 2. Your task per case

Consult the original RFC (from `canonical_source_url`) whenever the excerpt is
insufficient. Do not use general web knowledge as evidence; the corpus is the
50 RFCs in the Stage 5 manifest only.

### Supported case (`claimed_supported: true`) — check all five

1. **Is the expected evidence/source correct?** Does the cited RFC actually
   contain the relevant material?
2. **Does the evidence support the expected answer?** Is the excerpt
   verbatim-faithful and sufficient (not truncated or misleading)?
3. **Is the question answerable from the supplied corpus?**
4. **Is the expected answer materially correct?** Factually accurate per the
   RFC, including version/revision nuance.
5. **Ambiguity/problem flag** — note anything unclear, dual-interpretable,
   or stale.

### Unsupported case (`claimed_supported: false`) — check all three

1. **Is the question genuinely unsupported by the corpus?** Check that none
   of the 50 RFCs answers it.
2. **Would a grounded system reasonably be expected to abstain?** If the
   answer requires outside knowledge, "unsupported" is correct.
3. **Ambiguity/problem flag** — e.g., near-miss questions where related
   material exists but does not answer the question.

### What you must NOT do

- Ask what RALG, or any baseline, answered.
- Infer the "intended" verdict from case ordering or difficulty labels.
- Discuss cases with other reviewers before all reviews are submitted.

## 3. Explicit reviewer labels

Fill `accept_reject` with exactly one of:

| Label | Meaning |
|---|---|
| `accept` | Case is well-posed and correctly labeled (all checks above pass) |
| `reject` | Case fails one or more checks (wrong label, wrong answer, bad evidence, bad attribution) |
| `ambiguous` | Case cannot be judged cleanly; defensible multiple readings |
| `invalid_case` | Case is broken (empty question, unanswerable, malformed, wrong document) |

Only `accept` marks a case approved. `reject`, `ambiguous`, and
`invalid_case` all exclude the case from downstream evaluation while keeping
it in the audit trail.

Additional fields:

- Per-check yes/no columns (`answerable_yes_no`,
  `expected_support_correct`, `reference_answer_correct`,
  `evidence_supports_answer`, `source_attribution_correct`, `question_clear`)
- `corrected_answer` / `corrected_evidence` — optional corrections if a case
  is nearly right (use with `accept` only if the fix is trivial; otherwise
  `reject`)
- `reviewer_notes` — required substance; "looks fine" is not a review
- `reviewer_id` — must match your assigned anonymous label exactly

## 4. Procedure

1. Receive your assigned reviewer label and the review pack.
2. Work independently. Do not share intermediate judgments.
3. Record one row per case in a copy of `stage5_review_template.csv`.
4. Submit the completed CSV to the repository maintainer **without** prior
   discussion with other reviewers.

Partial submissions are accepted only when explicitly flagged: ingestion
refuses to silently record an incomplete round (the operator must pass
`--allow-partial`). Duplicate rows for one case ID, unknown case IDs, missing
fields, and unrecognized labels are rejected outright — the tool will point
at the exact problem row.

## 5. What happens to your review

```
CSV submission
  -> stage5_ingest_reviews.py ingest     (schema/duplicate/unknown/label checks)
  -> [second reviewer repeats]           (independent)
  -> stage5_ingest_reviews.py merge      (per-case comparison)
  -> stage6_review_agreement.py          (raw agreement + Cohen's kappa + adjudication queue)
  -> adjudication of disagreements       (documented, separate from reviewers)
  -> stage5_ingest_reviews.py freeze     (frozen reviewed benchmark + manifest)
  -> stage6_evaluator.py                 (metrics on human-approved subset only)
```

With two or more reviewers the tooling reports raw agreement percentage and
Cohen's kappa over outcome labels (with an explicit statement when kappa is
mathematically undefined), plus a disagreement queue for adjudication. With a
single reviewer, the report states that limitation instead of inventing
agreement statistics.

The original Stage 5 fixtures are never modified; every stage writes new
artifacts. The evaluator writes only
`evaluation/results/stage6_human_review_results.json` and refuses to emit
metrics until at least one genuinely ingested human-reviewed artifact exists.

## 6. Time expectations

Roughly 2–4 minutes per case if you verify excerpts against the source RFCs:
about 2.5–5 hours for the 75-case pilot, roughly 10–20 hours for the full 300.
The pilot is a stratified deterministic sample, deliberately not the easiest
cases.
