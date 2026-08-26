# Human Review Runbook (Stage 5/6)

How to actually perform a manual human review of the Stage 5 benchmark.
Nothing here requires writing code; you fill in forms and run one command per
step. Status as of this branch: **HUMAN REVIEW PENDING** — no completed
reviewer file exists yet.

---

## 0. What exists already

| Piece | Path |
|---|---|
| Review queue (300 cases) | `evaluation/stage5_review_queue.jsonl` |
| Blind reviewer pack (no model outputs) | `evaluation/stage5_review_pack/full_review.jsonl` (300) and `pilot_review.jsonl` (75, deterministic seed 5202025: 38 supported / 37 unsupported) |
| Answer-sheet template | `evaluation/stage5_review_template.csv` |
| Ingestion + freeze tooling | `scripts/stage5_ingest_reviews.py` |
| Agreement/kappa tooling | `scripts/stage6_review_agreement.py` |
| Post-review evaluator | `scripts/stage6_evaluator.py` |
| Full procedure detail | `docs/STAGE6_HUMAN_REVIEW_GUIDE.md`, `docs/STAGE5_REVIEW_GUIDE.md` |

## 1. Pick your review mode

- **Pilot:** the fixed 75 cases in `pilot_review.jsonl` (~2.5–5 hours).
- **Full:** all 300 cases in `full_review.jsonl` (~10–20 hours).

Both packs are blind: no RALG score, lexical score, ranking output, model
confidence, or pass/fail outcome is present.

## 2. Fill in the answer sheet

1. Copy `evaluation/stage5_review_template.csv` to
   `evaluation/reviewer_submissions/<your-label>.csv` (create the folder).
2. Open the pack (`pilot_review.jsonl`) side by side with the CSV.
3. For each case, read `question`, `claimed_supported`,
   `proposed_reference_answer`, and `evidence_excerpt`; consult the cited RFC
   via `canonical_source_url` when needed.
4. Record one row per case:
   - `case_id` — exactly as in the pack
   - six yes/no check columns (answerable, support label correct, reference
     answer correct, evidence supports answer, attribution correct, question
     clear)
   - `difficulty` — your independent judgment
   - `accept_reject` — exactly one of `accept`, `reject`, `ambiguous`,
     `invalid_case`
   - `corrected_answer` / `corrected_evidence` — optional fixes
   - `reviewer_notes` — substantive reasoning required
   - `reviewer_id` — your assigned label, identical on every row

**Safe resume:** work in any order across multiple sittings; just keep adding
rows to your own CSV. Do not create two files for the same reviewer label.

## 3. Submit / ingest

```powershell
.venv\Scripts\python.exe scripts\stage5_ingest_reviews.py ingest `
    --input evaluation\reviewer_submissions\<your-label>.csv `
    --reviewer-label <your-label> `
    --output evaluation\results\stage5_reviewed_<your-label>.jsonl
```

The ingestion step rejects and explains:
- missing schema fields or incomplete decisions
- duplicate rows for the same case ID
- unknown case IDs
- unrecognized labels (only accept / reject / ambiguous / invalid_case)
- partial rounds, unless you explicitly pass `--allow-partial`

The original Stage 5 queue is never modified; ingestion writes a new artifact.

## 4. Second reviewer (optional but recommended)

Repeat steps 1–3 independently with a different `reviewer_id`. Then merge and
compute agreement:

```powershell
.venv\Scripts\python.exe scripts\stage5_ingest_reviews.py merge `
    --reviewer-a <a-artifact>.jsonl --reviewer-b <b-artifact>.jsonl `
    --output evaluation\results\stage5_reviewed_merged.jsonl `
    --disagreements evaluation\results\stage6_disagreement_queue.jsonl

.venv\Scripts\python.exe scripts\stage6_review_agreement.py `
    --reviewer-a <a-artifact>.jsonl --reviewer-b <b-artifact>.jsonl
```

Raw agreement % and Cohen's kappa are reported (kappa is explicitly reported
as undefined when its marginals make it so). Disagreements go to an
adjudication queue; resolve them out-of-band and record decisions in notes.

## 5. Freeze the reviewed benchmark

Only after every case has an explicit decision:

```powershell
.venv\Scripts\python.exe scripts\stage5_ingest_reviews.py freeze `
    --reviewed-benchmark evaluation\results\stage5_reviewed_merged.jsonl
```

This writes `evaluation/stage5_final_benchmark.jsonl` plus a manifest with
hashes, reviewer IDs, and the production commit SHA.

## 6. Evaluate only human-approved cases

```powershell
.venv\Scripts\python.exe scripts\stage6_evaluator.py `
    --reviewed evaluation\results\stage5_reviewed_merged.jsonl
```

Output: `evaluation/results/stage6_human_review_results.json`. Only cases
approved by EVERY supplied reviewer are scored. The authoritative frozen
Stage 5 preliminary baseline is never mutated by this step.

## 7. Rules

- Never look at model outputs for these cases while reviewing.
- Never invent labels or copy another reviewer's decisions.
- One reviewer label = one person; do not merge two people's work under one ID.
