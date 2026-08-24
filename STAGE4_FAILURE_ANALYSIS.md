# Stage 4 Failure Analysis

The full per-case machine-readable output is in `logs/stage4_evaluation.json`.

## Observed failures

RALG had no supported retrieval failures and no unsupported false-support
failures in the 600-case run. Therefore there are no RALG failure IDs to
classify for this corpus.

The lexical baseline ranked 15 supported cases below rank 1 while still
recovering all supported answers by rank 3. Representative IDs are:
`s4-100`, `s4-106`, `s4-137`, `s4-178`, and `s4-220`.

These are ranking failures caused by misleading lexical overlap between
distractors and the requested entity/revision predicate. They are retrieval
and ranking failures, not grounding or rejection failures. No architecture
change is required to explain the measured RALG result; broader evidence is
required before treating it as a general claim.

## Category interpretation

All supported categories (paraphrase, distractor, similar entity, conflict,
numeric/revision, and cross-document) achieved 100% Recall@5 and evidence
correctness for both evaluated systems. Unsupported near-miss and adversarial
categories achieved 100% rejection and 0% false support for both systems.
This uniform result is a limitation: category-level separation is visible in
the corpus design but not yet in aggregate Recall@5.

## Ablation status

Conflict handling, factual grounding, and provenance/evidence validation are
**NOT ISOLATED**. They are coupled to the current production pipeline and no
safe test-only switches were introduced.

## Required follow-up

Use expert-reviewed questions with independently authored distractors and
answer-level provenance judgments. Preserve the current benchmark and report
all failures rather than filtering cases based on system performance.
