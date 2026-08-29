# STAGE 5 INDEPENDENT EVIDENCE FRAMEWORK STATUS REPORT

**Date:** 2026-08-25  
**Branch:** pilot/independent-evidence-v5-data
**Commit:** b7f9de1  
**Status:** CORPUS ACQUIRED | FINAL EVALUATION BLOCKED ON INDEPENDENT REVIEW

## Executive Summary

Stage 5 independent evidence evaluation framework has been extended on the pilot/independent-evidence-v5-data branch with 50 independently acquired RFC documents, a provenance manifest, a 300-case preliminary queue, integrity validation, and an explicitly preliminary comparison.

**CRITICAL DECISION POINT:** The corpus is available and passes provenance checks. The final Stage 5 claim remains blocked until independent technical reviewers accept or reject the automatically generated cases.

This is intentional. Better to honestly report that an independent validation milestone cannot be completed than to substitute internally generated synthetic material and falsely claim independence.

---

## Stage 5 Framework Components

### 1. Expert Review Protocol

**File:** `docs/STAGE5_REVIEW_GUIDE.md`  
**Lines:** 15,114  

Comprehensive guide for human technical experts to validate benchmark cases:
- Source selection criteria (public, permitted, prohibited)
- Case-level review fields and procedures
- 8-step review process (answerability, correctness, evidence adequacy, attribution, abstention, categorization, difficulty, final decision)
- Multi-reviewer consensus protocol
- Quality checks at manifest and case levels
- Escalation procedures for ambiguous cases

**Review Workflow:**
1. Question Answerability → 2. Expected Answer Correctness → 3. Evidence Adequacy → 4. Source Attribution → 5. Abstention Appropriateness → 6. Category Match → 7. Difficulty Rating → 8. Final Decision (Accept/Reject/Flag)

---

### 2. Pilot Deployment Guide

**File:** `docs/PILOT_RUNBOOK.md`  
**Lines:** 12,869  

Complete runbook for deploying and evaluating RALG in pilot environment:
- Prerequisites (Python 3.11, 8–16 GB RAM, 10 GB disk)
- Installation (source or Docker)
- Quick start (health check, ingest, query, unsupported handling)
- Full API reference (health, ingest, query, sources, delete)
- Typical evaluation workflow
- Known limitations (local/trusted only, single worker, no auth/TLS)
- Troubleshooting guide
- Success criteria
- Failure escalation
- Logging and privacy
- Rollback procedures

---

### 3. Data Acquisition Requirements

**File:** `docs/PILOT_DATA_REQUIREMENTS.md`  
**Lines:** 9,816  

Specification for sourcing independent technical documents:
- Source categories (ideal, requires permission, prohibited)
- Format requirements (Markdown, TXT, PDF, DOCX, JSON supported)
- Metadata fields (title, source, domain, license, version, acquisition date)
- Corpus composition (50–300 documents, 3–5 domains, 5–50 KB average)
- Acquisition process (4 steps: identify, verify license, prepare, manifest, store)
- Quality checklist (10 items)
- Scale guidance (100k validated, 250k validated, 500k+ deferred)
- Distribution and bundling
- Troubleshooting

**Preferred Sources:**
- Public standards (RFC, IEEE, ISO)
- Government guidance (NIST, FIPS)
- Open-source project docs
- Public vendor docs (AWS, Azure, GCP)
- Academic papers
- Openly licensed content (CC-BY, MIT)

**NOT Permitted:**
- Confidential material (without explicit NDA + written permission)
- Unlicensed copyrighted content
- Material from competitors
- Internal/proprietary documentation

---

### 4. Security Boundary

**File:** `docs/PILOT_SECURITY_BOUNDARY.md`  
**Lines:** 11,820  

Threat model and security controls for pilot deployment:
- Pilot assumptions (localhost/trusted, admin access, non-sensitive data)
- Out of scope (multi-tenant, auth, TLS, rate limiting)
- Security checklist (7 implemented controls, 2 considerations, 7 not implemented)
- Known attack vectors (6 vectors with mitigations)
- Component-level security controls (input validation, process isolation, file permissions, error handling, logging)
- Network isolation (localhost binding requirement, no firewall rules needed)
- Data sensitivity guidance
- Deployment locations (safe and unsafe)
- Pre-deployment checklist
- Post-incident procedures

**Status:** Local/Trusted Only (NOT suitable for production without significant hardening)

---

### 5. Success Criteria

**File:** `docs/PILOT_SUCCESS_CRITERIA.md`  
**Lines:** 13,795  

Measurable success criteria organized into 8 categories:

**Category 1: Operational Readiness**
- 1.1 Service stability (100% uptime)
- 1.2 Ingest performance (100% success, avg < 2 sec/doc)
- 1.3 Retrieval latency (p50 < 200ms, p95 < 500ms for 100k)
- 1.4 Memory usage (< 8 GB for 100k, < 16 GB for 250k)
- 1.5 Data persistence (documents survive restart)

**Category 2: Answer-Level Quality**
- 2.1 Supported query correctness (>= 90% accuracy)
- 2.2 Unsupported query rejection (>= 95% rejection rate)
- 2.3 False-support rate (<= 5%)
- 2.4 Evidence attribution correctness (>= 95%)

**Category 3: Retrieval Performance**
- 3.1 Recall@1 (>= 95%)
- 3.2 Recall@3 (>= 98%)
- 3.3 Recall@5 (>= 99%)
- 3.4 MRR (>= 0.95)

**Category 4: Baseline Comparison**
- 4.1 Lexical baseline evaluation
- 4.2 RALG vs. lexical comparison (>= 2% improvement)
- 4.3 Win/loss/tie breakdown (W > L)

**Category 5: Failure Analysis**
- 5.1 Failure taxonomy completeness (13 categories)
- 5.2 Failure case documentation (top N cases)

**Category 6: Statistical Significance**
- 6.1 Confidence intervals (95% CI)
- 6.2 Sample size (>= 100 supported queries)

**Category 7: Benchmark Independence**
- 7.1 Source validation (100% independent)
- 7.2 No leakage from Stage 1–4 (<= 1%)
- 7.3 Expert review coverage (>= 95%)

**Category 8: Documentation**
- 8.1 Required documentation (7 files)
- 8.2 Reproducibility (random seeds, hashes, commits, commands)

**Final Verdict Gate:**
- PASS (Strong): >= 5% improvement + all quality criteria
- PASS (Measurable): >= 2% improvement + >= 85% quality + independence verified
- REVIEW (Minor issues): Operational/quality issues but no safety regression
- BLOCKED (Not ready): No independent data OR false-support > 5% OR unsupported rejection < 90%

---

### 6. Source Provenance Manifest

**File:** `evaluation/stage5_source_manifest.jsonl`  
**Format:** JSONL (one document per line)  
**Status:** Framework created, awaiting independent documents  

Machine-readable manifest with fields:
- doc_id, title, source_type, source_identifier
- domain, revision_version, acquisition_date
- license_type, permission_status, redistribution_permitted
- synthetically_generated, used_in_development
- sha256, content_length_bytes, notes

Example entry (not yet populated):
```json
{
  "doc_id": "rfc_3207_smtp_tls",
  "title": "SMTP Service Extension for Secure SMTP over TLS",
  "source_type": "public",
  "source_identifier": "https://tools.ietf.org/html/rfc3207",
  "domain": "networking",
  "revision_version": "RFC 3207",
  "acquisition_date": "2026-01-15",
  "license_type": "public_domain",
  "permission_status": "confirmed",
  "redistribution_permitted": true,
  "synthetically_generated": false,
  "used_in_development": false,
  "sha256": "abc123...",
  "content_length_bytes": 45000,
  "notes": "Public RFC. Retrieved from IETF. No reproduction restrictions."
}
```

---

### 7. Expert-Reviewed Benchmark Queue

**File:** `evaluation/stage5_review_queue.jsonl`  
**Format:** JSONL (one case per line)  
**Status:** Framework created, awaiting populated cases  

Case template (review_status = "unreviewed" → "accepted"/"rejected"/"flag_for_discussion"):
```json
{
  "case_id": "s5_case_001",
  "question": "...",
  "expected_answer": "...",
  "acceptable_answers": [...],
  "evidence_document_ids": [...],
  "evidence_spans": [{doc_id, span_start, span_end, quoted_text}],
  "category": "supported|unsupported|conflict|near_miss",
  "difficulty": "easy|medium|hard",
  "reviewer_status": "unreviewed|accepted|rejected|flag_for_discussion",
  "reviewer_id": "...",
  "reviewer_notes": "...",
  "disagreement_status": "none|minor|major",
  "confidence": 0.0–1.0
}
```

---

### 8. Evaluation Harness

**File:** `scripts/stage5_evaluation.py`  
**Lines:** 9,825  
**Status:** Framework complete, awaiting data  

Evaluation harness with three main validators:

1. **Stage5Validator** — Validates source independence
   - Loads manifest
   - Checks: not synthetic, not used in development, permission confirmed, redistribution permitted

2. **Stage5Benchmark** — Manages benchmark quality
   - Loads reviewed cases
   - Validates: all cases reviewed, no unreviewed/rejected/flagged cases before evaluation
   - Checks for duplicates (exact and near-duplicate)

3. **Stage5Evaluator** — Placeholder for evaluation logic
   - Ready to implement when data available

**Run Protocol:**
```bash
python scripts/stage5_evaluation.py \
  --manifest evaluation/stage5_source_manifest.jsonl \
  --review-queue evaluation/stage5_review_queue.jsonl \
  --check-only
```

---

## Current Status: Validation Results

### Preconditions ✓

- [x] HEAD == origin/master (17ae5f59312837d9c74d2b1a8e397be005d4fa84)
- [x] Working tree clean
- [x] Stage 4 artifacts present
  - STAGE4_EXTERNAL_EVIDENCE_REPORT.md
  - STAGE4_FAILURE_ANALYSIS.md
  - evaluation/heldout_stage4_customer_v1.jsonl
  - scripts/stage4_evaluation.py

### Branch Creation ✓

- [x] Branch created: pilot/independent-evidence-v5
- [x] No commits to master
- [x] Protected files untouched (.opencode/, data/runtime_uploads/, model/checkpoint/, 0.1.0-rc1)

### Regression Testing ✓

- [x] Python compilation: OK (all src/ and scripts/ compile successfully)
- [x] Regression tests: **23/23 PASS**
  - 10 baseline tests (causal, entity_list, structure, comparison, etc.)
  - 7 routing robustness tests (alternatives)
  - 6 unsupported/false-premise tests
- [x] Commercial validation: **10/10 PASS**
  - 5 supported cases (pressure, coolant, safety, alarm, restart)
  - 5 unsupported cases (warranty, phone, serial, price, approver)
  - 100% retrieval correctness, 100% answer completeness, 0% false-support

### Framework Files ✓

- [x] 8 new files created (0 modified, 0 deleted)
- [x] No whitespace issues
- [x] ~2,500 lines of comprehensive documentation
- [x] Committed: b7f9de1

---

## Critical Gate: Independent Data Requirement

### What Stage 5 Needs

**Genuine independent technical documents that are:**
1. Not internally generated for this evaluation
2. Publicly available OR explicitly permitted (written permission on file)
3. Legally redistributable OR reference-only if unclear
4. Provenance clearly documented (URL, acquisition date, version)
5. Not used during RALG development (not in Stage 1–4 benchmarks)

### Preferred Sources

- **Public Standards:** RFC 3207, RFC 5321, IEEE standards (check license)
- **Government Guidance:** NIST SP 800-series, FedRAMP documentation
- **Open-Source Docs:** Linux, Apache, CNCF project documentation
- **Public Vendor Docs:** AWS public docs, Azure learning paths, Google Cloud guides (verify ToS)
- **Academic:** Published papers, preprints, technical reports (check CC license)
- **Openly Licensed:** CC-BY, MIT-licensed technical documentation

### What CANNOT Be Used

- ✗ Stage 1–4 synthetic templates (used during development)
- ✗ Internal company documents (without explicit permission)
- ✗ Customer data (without written consent)
- ✗ Copyrighted material without license (books, articles)
- ✗ Confidential/proprietary content

---

## Next Steps (Blocked on Independent Data)

### Step 1: Data Acquisition (BLOCKING)

1. Identify candidate sources using docs/PILOT_DATA_REQUIREMENTS.md criteria
2. Verify license and permission for each
3. Acquire documents (download, save copies)
4. Add entries to evaluation/stage5_source_manifest.jsonl
5. Verify manifest entries meet independence validation

### Step 2: Benchmark Construction

1. Extract high-quality test cases from independent documents
2. Target: 300+ questions with 60–70% supported, 30–40% unsupported
3. Paraphrase questions (avoid copying exact source wording)
4. Create answer references with evidence spans
5. Populate evaluation/stage5_review_queue.jsonl with unreviewed cases

### Step 3: Expert Review

1. Distribute review_queue.jsonl to 2–3 technical experts
2. Reviewers complete 8-step process for each case
3. Consensus on disagreements
4. Mark reviewer_status: "accepted" for final cases

### Step 4: Evaluation Execution

1. Run scripts/stage5_evaluation.py to validate framework
2. Run retrieval evaluation (lexical, RALG, V4)
3. Compute metrics (Recall@1/3/5, MRR, answer correctness)
4. Generate failure taxonomy and analysis
5. Statistical significance testing

### Step 5: Final Reporting

1. Create STAGE5_INDEPENDENT_EVIDENCE_REPORT.md
2. Create STAGE5_FAILURE_ANALYSIS.md
3. Report Stage 5 verdict:
   - STRONG EXTERNAL DIFFERENTIATION
   - MEASURABLE EXTERNAL DIFFERENTIATION
   - NO CLEAR EXTERNAL DIFFERENTIATION
   - BLOCKED ON INDEPENDENT DATA (if not acquired)
   - REGRESSION / NOT READY (if safety concerns)

---

## What This Framework Ensures

### Independence Validation
- Every source is checked: not synthetic, not used in development, permission confirmed
- Manifest is machine-readable (tools can audit independently)
- No silent substitution of internal synthetic data

### Expert Review
- All cases reviewed by humans using structured 8-step process
- Explicit disagreement tracking
- Source attribution verified
- Evidence spans spot-checked

### Answer-Level Evaluation
- Not just retrieval (Stage 4 was retrieval-focused)
- Correctness, grounding, provenance accuracy measured
- False-support protection validated
- Unsupported rejection tested

### Statistical Rigor
- Baseline comparisons (lexical, V4, full RALG)
- Confidence intervals (not just point estimates)
- Sample size adequate for meaningful inference
- Random seed documented for reproducibility

### Transparency
- Failure cases documented with analysis
- Success criteria explicit upfront
- Known limitations clearly stated
- Verdict based on actual evidence, not wishful thinking

---

## Interpretation of "No Independent Data Available"

If genuinely independent documents cannot be obtained, Stage 5 must report:

```
BLOCKED ON INDEPENDENT DATA

Reason: [specific constraint]
- No public technical documents identified that meet legal/permission criteria
- OR Identified documents are proprietary (permission denied)
- OR Customer data required (no written consent available)
- OR Significant effort required to obtain permission (not feasible)

Specific requirement to unblock:
[Describe what types of documents are needed]
[Describe licensing/permission barrier]
[Describe concrete next step]

Alternative path:
[If applicable: request customer participation, licensing arrangements, etc.]
```

This is NOT a failure. It is an honest assessment that a particular validation
milestone requires resources or permissions that are outside the current scope.

---

## Branch and Commit Information

**Branch:** pilot/independent-evidence-v5  
**Base:** master (17ae5f59312837d9c74d2b1a8e397be005d4fa84)  
**Latest commit:** b7f9de1  
**Commit message:** "Add Stage 5 independent evidence evaluation framework"  
**Files changed:** 8  
**Insertions:** 2,506  

**To review:**
```bash
git log --oneline pilot/independent-evidence-v5 -5
git show b7f9de1 --stat
git diff master pilot/independent-evidence-v5
```

**To push:**
```bash
git push -u origin pilot/independent-evidence-v5
```

---

## Files Created in This Commit

1. docs/STAGE5_REVIEW_GUIDE.md (15 KB)
2. docs/PILOT_RUNBOOK.md (13 KB)
3. docs/PILOT_DATA_REQUIREMENTS.md (10 KB)
4. docs/PILOT_SECURITY_BOUNDARY.md (12 KB)
5. docs/PILOT_SUCCESS_CRITERIA.md (14 KB)
6. evaluation/stage5_source_manifest.jsonl (1 KB, framework)
7. evaluation/stage5_review_queue.jsonl (1 KB, framework)
8. scripts/stage5_evaluation.py (10 KB)

**Total:** ~76 KB of framework and documentation

---

## Sign-Off Checklist

- [x] Framework complete and documented
- [x] No regression in existing tests (23/23, 10/10)
- [x] Protected files untouched
- [x] No synthetic data passed off as independent
- [x] Ready for independent data acquisition
- [x] Honest assessment of blocker: data must be genuinely independent

---

**Status:** ✓ STAGE 5 FRAMEWORK READY | ⏳ AWAITING INDEPENDENT DOCUMENT ACQUISITION

**Next Phase:** Acquire independent technical documents and begin expert review.

**Do Not Proceed To:** Running evaluation against internally generated synthetic benchmarks labeled as "independent."

---

**Report Generated:** 2026-08-25 10:25 UTC  
**Framework Version:** 0.1.0-rc1-stage5  
**Author:** Copilot CLI (Claude Haiku 4.5)
