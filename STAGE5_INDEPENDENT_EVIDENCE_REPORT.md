# Stage 5 Independent Evidence Report

**Status:** Preliminary corpus acquisition complete; final evaluation blocked on independent review.

## Corpus and provenance

The Stage 5 corpus contains 50 verbatim RFC Editor text documents authored by the Internet Engineering Task Force across four domains: networking standards, application protocols, cybersecurity, and systems operations. Each manifest entry records the canonical URL, acquisition date (2026-08-25), the publication-date IETF Trust Legal Provisions (BCP 78/79) basis, redistribution status, SHA-256, local identifier, and explicit independence declaration. This is not a public-domain claim: the RFC legal notices require retention of legends and notices, which the verbatim files retain.

`evaluation/results/stage5_integrity_report.json` reports zero duplicate IDs, URLs, or hashes; zero unmanifested files; zero detectable overlap with prior evaluation questions; and no provenance or integrity errors. No document is synthetic or marked as used in RALG development. No documents were excluded after acquisition.

## Benchmark status

The queue contains 300 cases: 210 supported and 90 unsupported. All 300 are explicitly marked `reviewer_status: "unreviewed"` and `review_origin: "automatically_generated"`. No expert reviewer, organization, approval, or customer participation is claimed. Consequently, these cases are not eligible for a final Stage 5 claim under the review protocol.

## Preliminary retrieval comparison

The untouched production retrieval code was run without changing thresholds. Results are diagnostic only and must not be presented as externally validated performance:

| System | Recall@1 | Recall@3 | Recall@5 | MRR | Unsupported rejection | False support | Evidence correctness | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Lexical | 40.48% | 87.62% | 100.00% | 0.6485 | 100.00% | 0.00% | 100.00% | 187.08 | 252.90 |
| RALG | 37.14% | 77.62% | 92.86% | 0.5863 | 100.00% | 0.00% | 92.86% | 6.76 | 7.37 |

The preliminary result shows the lexical baseline ahead on rank-1, rank-3, rank-5, MRR, and evidence-hit rate, while RALG is substantially faster. It is not evidence of differentiation because the benchmark has not received independent human review.

## Final determination

**FINAL STAGE 5 VERDICT: BLOCKED ON INDEPENDENT REVIEW**

Independent, legally usable documents were acquired successfully. The remaining required gate is independent technical review of the generated cases, followed by correction or rejection of unsuitable cases and a rerun against the accepted benchmark. The preliminary result provides evidence against assuming an advantage for RALG.

Security boundary remains unchanged: local/trusted prototype, single-worker recommendation, no production authentication, TLS, or multitenancy. Stage 1–4 fixtures, thresholds, runtime uploads, checkpoints, tokenizer/model artifacts, `.opencode/`, and tag `0.1.0-rc1` were not modified.
