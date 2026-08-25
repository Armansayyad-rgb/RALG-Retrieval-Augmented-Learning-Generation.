# RALG Pilot Success Criteria

## Purpose

This document defines measurable success criteria for the Stage 5 independent evidence pilot evaluation.

The pilot is successful when RALG demonstrates:

1. **Technical Readiness**: System is stable and meets operational requirements
2. **Differentiation**: RALG shows measured advantage over baselines on independent evidence
3. **Quality**: Answer-level grounding is accurate and verifiable
4. **Reliability**: False-support protection works as designed

## Category 1: Operational Readiness

### Criterion 1.1: Service Stability

**Requirement:** Service runs for entire evaluation without crashes.

**Measurement:**
- Start timestamp: T0
- End timestamp: T1
- Crash count: 0
- Uptime: (T1 - T0) / (T1 - T0) = 100%

**Pass Threshold:** 100% uptime during entire pilot run

**Failure Escalation:** If crash detected, investigate root cause and file bug report

---

### Criterion 1.2: Ingest Performance

**Requirement:** All benchmark documents ingest successfully within reasonable time.

**Measurement:**
- Total documents: N
- Successful ingest: N (100%)
- Failed ingest: 0
- Average time per document: < 1 second
- Total ingest time: < 5 * N minutes

**Pass Threshold:**
- Success rate: 100%
- Average time per doc: < 2 seconds
- Total time: < 10 minutes (for 100–300 doc corpus)

**Failure Escalation:** If any document fails to ingest, investigate format/encoding and attempt fix

---

### Criterion 1.3: Retrieval Latency

**Requirement:** Query latency meets performance expectations.

**Measurement:**
- Queries run: M
- p50 (median) latency: milliseconds
- p95 (95th percentile) latency: milliseconds
- p99 (99th percentile) latency: milliseconds

**Pass Threshold (for 100k corpus):**
- p50: < 200 ms
- p95: < 500 ms

**Pass Threshold (for 250k corpus):**
- p50: < 300 ms
- p95: < 750 ms

**Failure Escalation:** If latency exceeds thresholds, document limitation and note for production planning

---

### Criterion 1.4: Memory Usage

**Requirement:** System memory usage is reasonable for corpus size.

**Measurement:**
- Peak RSS (resident set size): MB
- Corpus size: documents, bytes

**Pass Threshold:**
- 100k documents: < 8 GB
- 250k documents: < 16 GB

**Failure Escalation:** If memory exceeds threshold, scale back corpus size or investigate memory leaks

---

### Criterion 1.5: Data Persistence

**Requirement:** Indexed documents persist across restarts.

**Measurement:**
1. Ingest N documents
2. Query system, verify document count = N
3. Stop service gracefully
4. Restart service
5. Query system, verify document count = N

**Pass Threshold:** Document count matches before and after restart

**Failure Escalation:** If data lost, investigate index persistence and file I/O

---

## Category 2: Answer-Level Quality

### Criterion 2.1: Supported Query Correctness

**Requirement:** RALG returns correct answers for supported queries.

**Measurement:**
- Supported queries in benchmark: S
- Queries with correct answers: C
- Accuracy: C / S

**Pass Threshold:** >= 90% correctness

**Notes:**
- "Correct" is determined by expert reviewers using docs/STAGE5_REVIEW_GUIDE.md
- Partial credit for near-correct answers (defined per case)
- Only count queries with "accepted" reviewer status

**Failure Escalation:** If accuracy < 85%, investigate top failure cases

---

### Criterion 2.2: Unsupported Query Rejection

**Requirement:** RALG correctly rejects queries with no supporting evidence.

**Measurement:**
- Unsupported queries in benchmark: U
- Correctly rejected (returned empty, `supported: false`): R
- Rejection rate: R / U

**Pass Threshold:** >= 95%

**Failure Escalation:** If rejection rate < 90%, investigate false-support cases

---

### Criterion 2.3: False-Support Rate

**Requirement:** RALG does NOT return high-confidence answers for unsupported queries.

**Measurement:**
- Unsupported queries: U
- Queries with non-empty result: F
- False-support rate: F / U

**Pass Threshold:** <= 5% (ideally 0%)

**Failure Escalation:** If false-support rate > 5%, investigate confidence calibration and grounding

---

### Criterion 2.4: Evidence Attribution Correctness

**Requirement:** Returned evidence actually supports the answer.

**Measurement:**
- Supported queries with results: S_r
- Results with correct evidence attribution: A
- Attribution accuracy: A / S_r

**Pass Threshold:** >= 95%

**Measurement Protocol:**
- Expert reviewer reads each returned evidence span
- Verifies span actually supports claimed answer
- Marks as correct/incorrect
- (Can be automated with semantic similarity if available)

**Failure Escalation:** If attribution accuracy < 90%, investigate span selection in retriever

---

## Category 3: Retrieval Performance

### Criterion 3.1: Recall@1

**Requirement:** RALG retrieves correct document in top-1 result.

**Measurement:**
- Supported queries: S
- Top-1 result is correct: T1
- Recall@1: T1 / S

**Pass Threshold:** >= 95%

**Comparison:** Should meet or exceed baseline (lexical retrieval)

---

### Criterion 3.2: Recall@3

**Requirement:** RALG retrieves correct document in top-3 results.

**Measurement:**
- Supported queries: S
- Top-3 contains correct: T3
- Recall@3: T3 / S

**Pass Threshold:** >= 98%

**Comparison:** Should meet or exceed baseline

---

### Criterion 3.3: Recall@5

**Requirement:** RALG retrieves correct document in top-5 results.

**Measurement:**
- Supported queries: S
- Top-5 contains correct: T5
- Recall@5: T5 / S

**Pass Threshold:** >= 99%

**Comparison:** Should meet or exceed baseline

---

### Criterion 3.4: Mean Reciprocal Rank (MRR)

**Requirement:** RALG ranks relevant documents highly.

**Measurement:**
- For each query i, reciprocal rank: 1 / rank_i
- MRR = mean(1 / rank_i) for all queries

**Pass Threshold:** >= 0.95

**Comparison:** Should meet or exceed baseline

---

## Category 4: Baseline Comparison

### Criterion 4.1: Lexical Baseline Evaluation

**Requirement:** Lexical (BM25) retrieval is evaluated on same queries/corpus.

**Measurement:**
- Lexical Recall@1: L1
- Lexical Recall@3: L3
- Lexical Recall@5: L5
- Lexical MRR: L_mrr

**Pass Threshold:** Baselines computed and reported (no failure criterion)

---

### Criterion 4.2: RALG vs. Lexical Comparison

**Requirement:** RALG shows measurable differentiation on independent evidence.

**Measurement:**
- RALG Recall@1: R1
- Lexical Recall@1: L1
- Improvement: (R1 - L1) / L1 * 100%

**Pass Threshold:** >= 2% improvement at Recall@1 (relative), or >= 3 percentage points (absolute)

**Acceptable Results:**
- Strong differentiation: >= 5% improvement (relative)
- Measurable differentiation: >= 2% improvement (relative)
- No clear differentiation: < 2% improvement

**Failure Escalation:** If no differentiation, investigate whether independent corpus is sufficiently challenging

---

### Criterion 4.3: Win/Loss/Tie Breakdown

**Requirement:** Compare RALG vs. lexical at per-query level.

**Measurement:**
- Queries where RALG > Lexical (better): W (wins)
- Queries where RALG = Lexical (tied): T (ties)
- Queries where RALG < Lexical (worse): L (losses)
- Win rate: W / (W + L)

**Pass Threshold:** W > L (more wins than losses)

**Analysis:** If many losses, investigate what types of queries RALG underperforms on

---

## Category 5: Failure Analysis

### Criterion 5.1: Failure Taxonomy Completeness

**Requirement:** All failures are categorized using structured taxonomy.

**Taxonomy Categories:**
- Retrieval miss (relevant doc not in top-k)
- Wrong rank (relevant doc present but not top-1)
- Entity confusion (confused similar entities)
- Predicate confusion (wrong relationship/verb)
- Numeric confusion (wrong number/version/port)
- Stale revision (used outdated document version)
- Conflict handling (failed to resolve conflicting docs)
- Grounding failure (high-confidence wrong answer)
- Unsupported false support (returned answer for unsupported query)
- False rejection (rejected query with supporting evidence)
- Provenance mismatch (evidence doesn't support answer)
- Answer extraction failure (failed to extract answer from evidence)
- Multi-document failure (failed to combine multiple docs)

**Pass Threshold:** All failures categorized; no "unknown" category

**Measurement:** Failure count per category, representative case IDs for each

---

### Criterion 5.2: Failure Case Documentation

**Requirement:** Top N failure cases are documented with analysis.

**Measurement:**
- Total failures: F
- Documented case analysis: min(5, F)

**Content per case:**
- case_id
- query
- expected answer
- RALG result
- why it failed
- suggested fix or limitation

**Pass Threshold:** All top failures documented

---

## Category 6: Statistical Significance

### Criterion 6.1: Confidence Intervals

**Requirement:** Performance improvements are reported with confidence intervals.

**Measurement (Bootstrap Method):**
1. Take 1000 random samples (with replacement) from query results
2. Compute Recall@1 for each sample
3. Compute 95% confidence interval [L, U]
4. If interval does not cross zero, improvement is significant

**Example Result:**
- RALG Recall@1: 0.98 [95% CI: 0.96–0.99]
- Lexical Recall@1: 0.96 [95% CI: 0.94–0.98]
- Difference: +0.02 [95% CI: 0.005–0.040]
- Significant: YES (interval doesn't include 0)

**Pass Threshold:** Main findings include confidence intervals

---

### Criterion 6.2: Sample Size

**Requirement:** Sufficient queries to detect meaningful differences.

**Measurement:**
- Supported queries: >= 100 (for Recall@1 confidence)
- Unsupported queries: >= 30 (for false-support testing)

**Power Analysis:**
- Assume baseline Recall@1 = 96%
- Target detection: 3 percentage point improvement (99% vs. 96%)
- Sample size needed (alpha=0.05, beta=0.2): ~100 queries

**Pass Threshold:** >= 100 supported queries

---

## Category 7: Benchmark Independence

### Criterion 7.1: Source Validation

**Requirement:** All sources meet independence criteria.

**Measurement:**
- Total documents: N
- Verified independent: I
- Percentage: I / N

**Pass Threshold:** 100% (all sources pass independence check)

**Independence Criteria:**
- Synthetically generated: false
- Used in development: false
- Permission status: confirmed
- Redistribution permitted: true

---

### Criterion 7.2: No Leakage from Stage 1–4

**Requirement:** Benchmark cases are not copied from earlier stages.

**Measurement:**
- Stage 5 questions: N5
- Overlap with Stage 1–4: O
- Leakage rate: O / N5

**Pass Threshold:** <= 1% overlap (at most 3 questions for 300-question corpus)

**Detection Method:**
- Exact string match
- Near-duplicate (Jaro-Winkler similarity > 0.85)
- Structural similarity (same source + entity + question type)

---

### Criterion 7.3: Expert Review Coverage

**Requirement:** All benchmark cases are reviewed by human experts.

**Measurement:**
- Total cases: N
- Reviewed and accepted: A
- Coverage: A / N

**Pass Threshold:** >= 95% (at most 5% of cases may be auto-accepted due to clarity)

**Reviewer Roles:**
- Minimum 2 reviewers per case (for critical cases)
- Disagreements resolved via discussion
- Consensus documented in case notes

---

## Category 8: Document and Reporting

### Criterion 8.1: Required Documentation

**Pass Threshold:** All reports created and complete

**Required Files:**
- [ ] STAGE5_INDEPENDENT_EVIDENCE_REPORT.md
- [ ] STAGE5_FAILURE_ANALYSIS.md
- [ ] evaluation/stage5_source_manifest.jsonl
- [ ] evaluation/stage5_review_queue.jsonl
- [ ] evaluation/stage5_results.jsonl
- [ ] docs/STAGE5_REVIEW_GUIDE.md

**Report Contents:**
- Executive summary (1 page)
- Methodology (data sources, evaluation protocol)
- Results (metrics, tables, figures)
- Baseline comparisons
- Failure analysis
- Confidence intervals and significance testing
- Known limitations
- Conclusions and recommendations

---

### Criterion 8.2: Reproducibility

**Requirement:** Evaluation is reproducible by external reviewer.

**Measurement:**
- Random seeds documented: YES/NO
- Corpus versions hashed: YES/NO
- Code commits recorded: YES/NO
- Exact command lines recorded: YES/NO

**Pass Threshold:** All reproducibility elements documented

---

## Final Verdict Gate

**PASS (Strong External Differentiation):** if:
- ✓ All operational criteria (1.1–1.5) met
- ✓ All quality criteria (2.1–2.4) met >= 90%
- ✓ Recall@1 improvement >= 5% (relative) over baseline
- ✓ Benchmark independence verified (7.1–7.3)
- ✓ No regression in false-support protection (2.3 <= 2%)

**PASS (Measurable External Differentiation):** if:
- ✓ All operational criteria met
- ✓ Quality criteria (2.1–2.4) met >= 85%
- ✓ Recall@1 improvement >= 2% (relative) over baseline
- ✓ Benchmark independence verified
- ✓ No significant regression in false-support

**REVIEW (Minor Issues):** if:
- ~ Operational readiness issues (latency, memory) documented but acceptable
- ~ Quality slightly below threshold but no safety concerns
- ~ Baseline comparison inconclusive (need more data)

**BLOCKED (Not Ready):** if:
- ✗ Cannot obtain independent documents (report BLOCKED ON INDEPENDENT DATA)
- ✗ False-support rate > 5%
- ✗ Unsupported rejection < 90%
- ✗ Benchmark fails independence check
- ✗ Operational instability (crashes, data loss)

---

**Last Updated:** 2026-01-01  
**Pilot Version:** 0.1.0-rc1
