# Stage 4 External-Style Evidence Report

## Status

**MEASURED** on branch `pilot/external-evidence-v4`, based on master
`1f434bcdb2777e658d05ce6c0c467d36ce878335`. The corpus and questions are
deterministic synthetic/customer-style material, not real customer data.

## Environment and corpus

- Python 3.11 clean environment with the repository requirements installed.
- 120 synthetic documents across eight domains.
- 600 questions: 480 supported (80%) and 120 unsupported (20%).
- Categories: paraphrase, distractor, similar entity, conflict, numeric/revision,
  cross-document, near-miss unsupported, and 100 adversarial unsupported cases.
- The supported ratio is outside the requested 65–75% target because the
  adversarial set was retained as a separate red-team population; it was not
  removed to improve results.

## Integrity

**MEASURED:** exact duplicate questions 0, duplicate IDs 0, overlap with prior
evaluation questions 0, answer leakage 0, duplicate documents 0. The
near-duplicate checker found 1,738 pairs; these are template-family
similarities and remain visible rather than being silently discarded.
Generation uses a stable deterministic order and seed.

## Results

| System | Recall@1 | Recall@3 | Recall@5 | MRR | Unsupported rejection | False support | Evidence correctness | p50/p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Lexical | 96.875% | 100% | 100% | 0.9844 | 100% | 0% | 100% | 0.928/1.245 ms |
| RALG | 100% | 100% | 100% | 1.0000 | 100% | 0% | 100% | 0.398/0.685 ms |
| V4 | 100% | 100% | 100% | 1.0000 | 100% | 0% | 100% | 3.537/5.100 ms |

RALG's measured advantage over lexical retrieval is +3.125 percentage points
at Recall@1 and +0.0156 MRR, with 15 additional supported cases ranked first.
There is no Recall@3/5 advantage: both systems reach the ceiling there.
Unsupported rejection and adversarial false-support results are 100% and 0%
respectively for both systems.

## Ablations

Conflict handling, factual grounding, and provenance/evidence validation remain
**NOT ISOLATED**. No safe test-only public seams exist; production defaults
were not weakened or changed.

## Performance and operations

- **PREVIOUSLY MEASURED:** 100k retrieval p50 156.186 ms, p95 215.893 ms,
  RSS approximately 637 MB.
- **MEASURED:** Stage 4 representative retrieval remained below the values in
  the table above.
- **NOT VALIDATED:** 250k/500k scale, because available free memory was about
  6.5 GB and the requested safety gate did not justify a risky run.
- **NOT VALIDATED:** Docker runtime; the Docker daemon was unavailable.
- Existing `scripts\test_all.bat` passed, including regression and commercial
  gates. Commercial validation remained 10/10 and regression 23/23.
- Existing API hardening, provenance, persistence, lifecycle, and retrieval
  performance gates passed in the baseline run.

## Security boundary and limitations

The pilot remains local/trusted, single-worker, unauthenticated, without TLS or
tenant isolation. Process-local lifecycle locks do not establish multi-process
safety. Synthetic evidence does not establish production customer performance.

## Verdict

**MEASURABLE DIFFERENTIATION**, but not strong differentiation: RALG improves
first-result ranking on this harder corpus while Recall@3/5 still has a ceiling
effect and both systems reject unsupported cases equally well.

The next milestone is an independently authored, externally sourced or
expert-reviewed corpus with harder answer-level and provenance scoring.
