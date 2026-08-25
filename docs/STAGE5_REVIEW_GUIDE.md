# Stage 5 Expert Review Guide

## Purpose

This guide enables technical reviewers (customers, investors, acquirers, external auditors) to validate Stage 5 independent evidence evaluation with confidence that:

- Questions are answerable from the provided corpus
- Expected answers are factually correct
- Evidence actually supports the answer
- Source attribution is accurate
- Abstention (unsupported rejection) is appropriate
- No bias has been introduced in grading

## Independent Evidence Requirement

**CRITICAL CONSTRAINT:** Stage 5 evidence must not be internally generated synthetic material.

All source documents must be:

- **Independently authored** (not created specifically for this evaluation)
- **Publicly available OR explicitly permitted** (not confidential/private without written approval)
- **Legally redistributable** (or reference-only if redistribution is unclear)
- **Acquisition provenance clear** (URL, citation, version, acquisition date recorded)
- **Unused during RALG development** (not part of training, tuning, or Stage 1–4 benchmarks)

## Source Selection Criteria

### Preferred Sources (Low Legal/Provenance Risk)

- **Public technical standards** (RFC, IEEE, ISO specifications available under permissive terms)
- **Government technical guidance** (NIST, FIPS, public agencies; assume public domain)
- **Open-source project documentation** (Apache, Linux, CNCF, etc.; check license)
- **Academic technical reports** (published research, preprints; check licensing)
- **Public vendor technical manuals** (AWS, Azure, Google Cloud publicly available docs; check ToS)
- **Openly licensed technical content** (Creative Commons, public domain, MIT-licensed docs)
- **Public safety/maintenance procedures** (e.g., aviation maintenance, electrical safety guidance)

### Requires Explicit Permission (Medium/High Risk)

- **Private vendor documentation** (contact vendor, request permission)
- **Customer documentation** (obtain written consent before use)
- **Proprietary standards** (contact standards body; may restrict redistribution)
- **Published book excerpts** (check copyright; may require permissions letter)
- **Licensed datasets** (review license terms; may restrict commercial use)

### Not Permitted (Do Not Use)

- **Confidential/NDA material** (without explicit written approval)
- **Unlicensed copyrighted content** (without explicit permission)
- **Student/research data** (without IRB/ethics approval)
- **Material from competitors** (without licensing clarity)

## Manifest Entry Validation Checklist

Before a source is marked `permission_status: "confirmed"`, verify:

- [ ] `source_identifier` is specific (URL with stable access, full citation, or version control commit)
- [ ] `acquisition_date` is recorded (ISO 8601)
- [ ] `license_type` is stated (public domain, CC-BY, MIT, Apache, BSD, GPL, vendor-specific, etc.)
- [ ] `permission_status` is "confirmed" only if:
  - Source is public domain/government, OR
  - Source license explicitly permits redistribution, OR
  - Written permission from rights holder is on file
- [ ] `redistribution_permitted` is true only if permission confirmed above
- [ ] `synthetically_generated` is false (not internally generated)
- [ ] `used_in_development` is false (not part of Stage 1–4 or training)
- [ ] `sha256` is present (for integrity verification)
- [ ] `content_length_bytes` is realistic (not obviously truncated)

## Case-Level Review Fields

Each case in `evaluation/stage5_review_queue.jsonl` must support human review:

```json
{
  "case_id": "s5_case_001",
  "question": "What is the primary purpose of X?",
  "question_source": "document source reference",
  "expected_answer": "Factually correct reference answer",
  "acceptable_answers": [
    "exact match variant 1",
    "acceptable paraphrase",
    "alternate correct fact"
  ],
  "evidence_document_ids": ["doc_id_1", "doc_id_2"],
  "evidence_spans": [
    {
      "doc_id": "doc_id_1",
      "span_start": 150,
      "span_end": 250,
      "quoted_text": "..."
    }
  ],
  "category": "supported|unsupported|conflict|near_miss",
  "difficulty": "easy|medium|hard",
  "support_type": "single_document|multi_document|inference",
  "reviewer_status": "unreviewed|in_progress|accepted|rejected|flag_for_discussion",
  "reviewer_id": "reviewer_name_or_anonymous",
  "reviewer_notes": "Why did you accept/reject?",
  "disagreement_status": "none|minor|major",
  "confidence": 0.8
}
```

## Review Procedure

### Step 1: Question Answerability

**Question:** Can this question be answered from the provided corpus?

**Reviewer should:**
- Read the question carefully
- Check evidence spans cited in `evidence_spans`
- Determine if answer is supported
- If unsupported (correct answer), verify that "unsupported" is indeed the right verdict

**Decision:**
- Accept: Question is well-formed, answerable, and correctly classified
- Reject: Question is ambiguous, unanswerable, or misclassified

---

### Step 2: Expected Answer Correctness

**Question:** Is the stated expected answer factually correct?

**Reviewer should:**
- Compare expected answer against evidence spans
- Check against source document (retrieve from source_identifier)
- Verify no factual errors, misquotations, or misinterpretations
- Check date/version of evidence (is it stale? is there a newer version?)

**Decision:**
- Accept: Expected answer matches evidence and is factually correct
- Reject: Expected answer is wrong, outdated, or contradicted by source
- Flag: Expected answer is technically correct but needs clarification

---

### Step 3: Evidence Adequacy and Attribution

**Question:** Do the evidence spans actually support the expected answer?

**Reviewer should:**
- Retrieve each document from `evidence_document_ids`
- Check that `span_start` and `span_end` correctly delimit the supporting text
- Verify `quoted_text` matches the actual document at that position
- Check that the span is sufficient (not truncated or misleading)
- Verify no cherry-picking (full context is presented fairly)

**Decision:**
- Accept: Evidence spans directly support the answer with fair context
- Partial: Evidence supports the answer but context is tight or could be clearer
- Reject: Spans do not support the answer, or are truncated/misleading

---

### Step 4: Source Attribution and Integrity

**Question:** Is the source correctly attributed and unmodified?

**Reviewer should:**
- Verify source_identifier matches acquisition method (URL, citation, etc.)
- Check SHA-256 hash if available (ensures document wasn't modified)
- Verify acquisition_date and license_type are accurate
- If public source, confirm it's still accessible
- If private/permitted source, confirm permission is documented

**Decision:**
- Accept: Source is correctly identified, hash verified, permission confirmed
- Caution: Source is accessible but hash not verified (human spot-check OK)
- Reject: Source cannot be verified, permission unclear, or document modified

---

### Step 5: Abstention Appropriateness

**Question:** For unsupported cases, is abstention justified?

**Reviewer should:**
- Verify the question is legitimate (not malformed)
- Check that no hidden evidence exists in the corpus
- Verify the "correct" answer really cannot be inferred from any document
- Check for near-miss cases (e.g., outdated procedures, conflicting revisions)

**Decision:**
- Accept: Abstention (unsupported) is the correct verdict
- Partial: Answer could be inferred with significant reasoning (mark as inference-required)
- Reject: Evidence exists; should not be marked unsupported

---

### Step 6: Category Appropriateness

**Question:** Is the case correctly categorized?

**Categories:**

- **supported**: Single document directly answers the question
- **unsupported**: No document contains the answer; abstention is correct
- **multi_document**: Answer requires combining information from multiple documents
- **conflict**: Different documents provide conflicting answers; grounding is required
- **near_miss**: Evidence is close but not exact (outdated, similar entity, wrong revision)
- **inference**: Answer requires interpretation beyond literal text
- **adversarial**: Question designed to test false-support resistance

**Reviewer should:**
- Verify category matches the evidence structure
- Flag if category seems incorrect
- Note if category is ambiguous (could be 2+ categories)

**Decision:**
- Accept: Category is correct
- Reclassify: Suggest better category
- Flag: Multiple categories apply; needs clarification

---

### Step 7: Difficulty Assessment

**Question:** Is the difficulty rating appropriate?

**Easy:** Answer is in a single prominent location; minimal reasoning needed.  
**Medium:** Answer requires finding the right section or slight paraphrasing.  
**Hard:** Answer requires multi-document reasoning, conflict resolution, or inference.

**Reviewer should:**
- Estimate effort needed to find and formulate the answer
- Verify difficulty aligns with case complexity

**Decision:**
- Accept: Difficulty is reasonable
- Adjust: Suggest difficulty change

---

### Step 8: Final Review Decision

After all steps, reviewer indicates:

- **reviewer_status**: `accepted` | `rejected` | `flag_for_discussion`
- **reviewer_notes**: Summary of review, any issues found, reasoning
- **disagreement_status**: `none` | `minor` | `major` (if notes show concerns)
- **confidence**: 0.0–1.0 confidence in the review

---

## Consensus Protocol (Multi-Reviewer Scenarios)

If multiple reviewers review the same case:

1. Compare individual `reviewer_status` fields
2. If consensus (all `accepted` or all `rejected`): Use that verdict
3. If disagreement:
   - Flag case for discussion (`disagreement_status: "major"`)
   - Collect reviewer notes
   - Resolve via discussion or third-party review
   - Document resolution in `reviewer_notes`

---

## Quality Checks

### Manifest-Level Checks

- No duplicate doc_ids
- Every case's `evidence_document_ids` references valid manifest entries
- No source marked `synthetically_generated: true`
- No source marked `used_in_development: true`
- All publicly available sources have working URLs (spot-check 10%)
- All permitted sources have permission_status: "confirmed"

### Case-Level Checks

- No exact duplicate questions
- No near-duplicate questions from the same source (unless intentional testing)
- All `evidence_spans` have valid UTF-8 `quoted_text`
- All `span_start` and `span_end` are within document bounds
- No answer leakage (expected_answer doesn't appear in other questions' context)
- Supported/unsupported ratio is approximately 60–70% / 30–40%
- Multiple domains represented

### Reviewer Checks

- All cases eventually reach reviewer_status in {`accepted`, `rejected`, `flag_for_discussion`}
- No reviewer left all fields as null
- Reviewer notes are substantive (not empty)
- Confidence scores are reasonable (not all 0.99 or 0.01)

---

## Escalation: When to Flag for Discussion

Flag a case for discussion if:

- **Ambiguous question**: Question could mean multiple things
- **Outdated evidence**: Source is from 2015, but product has evolved significantly
- **Conflict within source**: Single document contradicts itself (different sections)
- **Partial correctness**: Expected answer is partially right but partially wrong
- **Missing context**: Evidence span is correct but requires external knowledge
- **Reviewer uncertainty**: Reviewer is not confident in their assessment (e.g., technical ambiguity)

---

## Output Format

Use `evaluation/stage5_review_queue.jsonl` (one JSON object per line).

```jsonl
{"case_id": "s5_case_001", "question": "...", "reviewer_status": "accepted", ...}
{"case_id": "s5_case_002", "question": "...", "reviewer_status": "rejected", ...}
```

Generate summary statistics:

```
Total cases: 300
Accepted: 285 (95%)
Rejected: 10 (3.3%)
Flagged for discussion: 5 (1.7%)

By category:
  supported: 210 accepted, 5 rejected, 2 flagged
  unsupported: 70 accepted, 5 rejected, 3 flagged
  conflict: 4 accepted, 0 rejected, 0 flagged
  near_miss: 1 accepted, 0 rejected, 0 flagged
```

---

## Example: Correct Review

**Case ID:** `s5_case_042`

**Question:** "What TCP port does the SMTP service use for TLS connections according to RFC 3207?"

**Expected Answer:** "Port 587 (STARTTLS) or port 465 (SMTPS); RFC 3207 specifies port 587 for STARTTLS."

**Evidence Document:** `rfc_3207_smtp_tls`

**Evidence Span:**
- doc_id: `rfc_3207_smtp_tls`
- span_start: 2450
- span_end: 2550
- quoted_text: "SMTP client implementations supporting STARTTLS MUST use port 587 by default, unless...specification."

**Reviewer Assessment:**

1. **Answerability:** ✓ Accept. Question is clear and answerable.
2. **Answer Correctness:** ✓ Accept. RFC 3207 does specify port 587; answer is factually correct.
3. **Evidence Adequacy:** ✓ Accept. Span directly supports the answer.
4. **Attribution:** ✓ Accept. RFC 3207 is public domain; source properly cited.
5. **Category:** ✓ Accept. Single-document supported case.
6. **Difficulty:** ✓ Accept. Medium difficulty (requires domain knowledge but answer is explicit).

**Decision:**
- reviewer_status: `accepted`
- reviewer_notes: "Clean case. RFC is public domain. Span is accurate and sufficient. Answer is correct per specification."
- disagreement_status: `none`
- confidence: 0.95

---

## Minimum Review Bar

A case is accepted only if:

- ✓ Question is well-formed and answerable
- ✓ Expected answer is factually correct per evidence
- ✓ Evidence spans accurately support the answer
- ✓ Source is correctly attributed
- ✓ Source permission/license is confirmed

Cases failing any criterion should be `rejected` or `flagged_for_discussion`.

---

## Non-Reviewers: How to Spot Fake Reviews

Red flags:

- All cases marked "accepted" with no flags
- No disagreements across multiple reviews
- Reviewer notes are generic ("looks good")
- High confidence (0.99+) on all cases
- All cases have identical difficulty ratings
- No time spent (reviewed 100 cases in 2 minutes)

---

## Next Steps

1. Acquire independent sources (see Acquisition Criteria above)
2. Build benchmark from those sources only
3. Send evaluation/stage5_review_queue.jsonl to reviewers
4. Reviewers independently complete the procedure above
5. Aggregate results, resolve disagreements
6. Only then run system evaluation on accepted cases
7. Report final Stage 5 verdict

If independent sources cannot be acquired, report:

```
BLOCKED ON INDEPENDENT DATA

Reason: No independent technical documents available that meet:
- Legal/permission criteria
- Provenance requirements
- Sufficient diversity/coverage

Action: [describe specific data acquisition needed]
```
