# Holdout V4 Validation Protocol

Protocol identifier: **holdout_v4_protocol_v1**  
Target benchmark identifier after freeze: **holdout_v4.0.0**

This document defines the methodology for the first fresh post-code-freeze blind evaluation of RALG. It is intentionally written and merged **before source selection, question authoring, evaluator execution, or result inspection**. The purpose is to prevent post-hoc metric, denominator, question, or acceptance-rule changes.

## 1. Objective

Holdout V4 will measure the frozen RALG system against a new authoritative-source technical-document corpus under a single-shot blind protocol. It is designed to answer four separate questions:

1. Does retrieval surface the required evidence?
2. Does the system answer supported questions correctly and with traceable evidence?
3. Does the system abstain when the corpus does not support the requested claim?
4. Does the system handle document scope, cross-document synthesis, qualification, and conflicting evidence without unsupported support?

V4 is **not** a customer study, external certification, safety certification, or proof of global accuracy.

## 2. Freeze boundary

The production system under evaluation is the post-engineering-freeze `master` lineage. No feature, retrieval, grounding, support-gate, threshold, answer-routing, API-semantic, or benchmark-specific behavior change may be made after the V4 benchmark/evaluator freeze and before the one allowed blind run.

Documentation-only or build/release-hygiene changes that cannot affect evaluation behavior may occur, but the exact evaluated commit SHA must be recorded in the result artifact.

The following frozen historical evaluations must never be rerun or rewritten as part of V4:

- Holdout V1;
- Holdout V2;
- Holdout V3.

V4 must use new artifacts and a new result path.

## 3. Evidence terminology

The permitted description after a valid run is:

> **fresh post-freeze authoritative-source blind holdout**

Do not call V4 “external validation,” “third-party validation,” “independent certification,” or “customer validation” unless the benchmark is genuinely authored/reviewed by a qualifying external party and that fact is separately documented.

## 4. Corpus requirements

V4 sources must be authoritative upstream technical documents, not project-authored summaries. Source selection must satisfy all of the following before question authoring begins:

- at least **10 technical domains**;
- at least **12 source documents** total;
- no source document copied from V1, V2, V3, Stage 5, or the Authoritative Technical Dev Set;
- no project-authored validation notes standing in for upstream documents;
- canonical upstream URL, version/tag/commit/date where available, acquisition timestamp, license/redistribution status, byte size, and SHA-256 recorded for every source;
- normalized artifact and raw acquisition artifact separated where normalization is necessary;
- deterministic normalization procedure documented;
- source license/redistribution status reviewed before the benchmark is frozen;
- sources selected before benchmark questions are authored.

Source domains should be materially different in terminology and document structure. A single vendor/product family must not dominate the corpus.

## 5. Contamination controls

Before freeze, an automated contamination report must compare V4 source identifiers, titles, URLs, question text, expected-answer text, and distinctive n-grams against prior repository evaluation/training question sets where applicable, including V1, V2, V3, Stage 5, development reliability sets, and the Authoritative Technical Dev Set.

The report must identify exact and near-duplicate overlaps. Any material question/answer overlap must be replaced **before freeze**. Once frozen, no replacement is permitted because of observed model performance.

Source overlap with generic public knowledge is not itself contamination; reuse of the same evaluation document/question/answer formulation is.

The contamination checker and its output must be committed before the blind run.

## 6. Benchmark size and fixed category distribution

V4 contains **exactly 160 cases**. The category counts are fixed by this protocol and must not change after protocol merge without creating a new protocol version before any V4 questions are authored.

| Category | Count | Primary scoring family |
|---|---:|---|
| supported_factual | 20 | answer + retrieval |
| paraphrased_supported | 20 | answer + retrieval |
| procedural | 20 | answer + retrieval |
| causal | 15 | answer + retrieval |
| cross_document | 15 | answer + retrieval |
| document_scoped | 10 | answer + retrieval |
| conflicting_evidence | 10 | conflict-specific + retrieval |
| conditional_or_qualified | 5 | qualification-specific + retrieval |
| unsupported | 20 | rejection |
| false_premise | 15 | rejection |
| misleading_overlap | 10 | rejection |
| **Total** | **160** | |

Fixed denominator families:

- **primary answer-supported:** 100 cases (`supported_factual`, `paraphrased_supported`, `procedural`, `causal`, `cross_document`, `document_scoped`);
- **conflicting-evidence:** 10 cases;
- **conditional/qualified:** 5 cases;
- **rejection:** 45 cases (`unsupported`, `false_premise`, `misleading_overlap`);
- **retrieval-supported:** 115 cases (the 100 primary answer-supported + 10 conflict + 5 qualified cases).

These denominators must appear explicitly in the evaluator and result artifact. No case may silently migrate between denominator families after freeze.

## 7. Case schema

Every frozen case must contain, at minimum:

- `case_id`;
- `category`;
- `question`;
- `expected_behavior`;
- `relevant_document_ids`;
- `answerable` boolean;
- `ground_truth_answer` or structured answer rubric where applicable;
- `required_evidence` as one or more source spans/anchors sufficient to adjudicate the answer;
- `forbidden_or_contradictory_evidence` when relevant;
- `document_scope` when the case is scoped;
- `reasoning_notes_for_reviewers` kept out of model input;
- `pre_run_review_status`.

Ground truth must be source-derived. A case is invalid if the expected answer cannot be justified directly from the frozen source corpus.

## 8. Question-authoring rules

Questions must be authored without executing the frozen RALG system on the V4 corpus. Authors may inspect source documents but may not probe the target system and then reshape questions based on its behavior.

Authoring must avoid:

- trivial title-copy questions dominating a category;
- wording copied from earlier holdouts;
- answer leakage in the question;
- ambiguous pronouns or undefined scope unless ambiguity is the deliberate phenomenon being tested;
- unsupported cases whose answer is accidentally present elsewhere in the corpus;
- false-premise cases that are actually true under a different frozen source document;
- cross-document cases that can be answered correctly from only one document;
- conflict cases where the sources do not genuinely disagree, differ by version/scope, or require qualification.

## 9. Pre-run ground-truth review

Before benchmark freeze, perform **ground-truth validation**, not model evaluation.

Reviewers see the source documents, case questions, expected behavior, expected answer/rubric, and required evidence. They do **not** see any model answer, retrieval rank, confidence, score, pass/fail indicator, or system output.

A case can enter the frozen benchmark only if the review confirms:

- the question is understandable;
- the category is correct;
- the expected behavior is well-defined;
- the required evidence exists in the cited frozen source(s), or is absent for rejection cases;
- the rubric is sufficient to adjudicate correctness;
- there is no discovered material contamination.

Any case rejected in this phase must be repaired or replaced **before freeze** and the review trail preserved.

## 10. Freeze artifacts

The V4 freeze commit must include all artifacts needed to reproduce the evaluation without changing content:

- authoritative source files and source manifest;
- benchmark JSONL containing exactly 160 reviewed cases;
- contamination checker and frozen contamination report;
- evaluator code;
- pre-freeze validation script;
- benchmark manifest containing counts and artifact hashes;
- pre-run review record;
- hash-verification script.

At freeze, record SHA-256 for at least:

- benchmark JSONL;
- source manifest;
- source corpus aggregate/deterministic manifest;
- evaluator;
- contamination report;
- pre-run review record;
- frozen evaluated code commit SHA.

The freeze manifest must state `single_shot_blind_evaluation_no_tuning_afterwards`.

## 11. One-run rule

After the freeze commit is merged and hashes verify, **exactly one official V4 evaluation run** is permitted.

The official result path must be unique, for example:

`evaluation/results/holdout_v4_blind_once.json`

If the official runner exits because of infrastructure failure before producing evaluable outputs, the incident must be documented. A rerun is permitted only if the failure is demonstrably infrastructure-only and no case-level model output or aggregate performance was exposed. If meaningful model outputs or metrics were observed, the run counts as the official run and must be preserved.

No tuning, question replacement, threshold change, evaluator-rule change, or source alteration may occur after viewing official V4 outputs.

## 12. Retrieval metrics

For the fixed 115 retrieval-supported cases, report separately:

- Recall@1;
- Recall@3;
- Recall@5;
- HitRate@1;
- HitRate@3;
- HitRate@5;
- MRR;
- exact count of cases with no required document retrieved in top 5.

For multi-document cases, Recall@K is the fraction of required relevant documents retrieved in top K. HitRate@K is 1 if at least one required relevant document appears in top K. MRR uses the rank of the first relevant document.

Report macro averages across the 115 retrieval-supported cases. Also report category-level retrieval metrics; do not replace the global denominators with cherry-picked category subsets.

## 13. Answer / support metrics

For the 100 primary answer-supported cases, report:

- supported-correct count and rate;
- supported-incorrect count and rate;
- false-rejection count and rate;
- evidence-traceable-correct count and rate;
- runtime-error count.

A supported answer is correct only when the substantive claim satisfies the ground-truth rubric **and** the evidence is sufficient for the answer under the frozen scoring rules. Unsupported but semantically plausible answers do not count as correct.

For the 45 rejection cases, report:

- correct rejection count/rate;
- false-support count/rate;
- runtime-error count.

False-support rate = false supports / 45. Correct-rejection rate = correct rejections / 45.

## 14. Conflict and qualification metrics

The 10 conflicting-evidence cases are scored separately. A correct response must identify or safely resolve the relevant conflict/scope/version distinction according to the frozen rubric rather than selecting one convenient source as unqualified truth.

Report `conflict_correct / 10`, `conflict_false_support / 10`, and `conflict_false_rejection / 10` where applicable.

The 5 conditional/qualified cases are scored separately. A correct response must preserve the required condition, exception, version, scope, or qualification.

Report `qualified_correct / 5` and failure counts by adjudication class.

Do not merge these 15 cases into the 100 primary answer denominator to improve or depress the primary rate.

## 15. Confidence intervals

Report two-sided 95% Wilson intervals for all primary binomial rates, including:

- supported-correct rate (n=100);
- correct-rejection rate (n=45);
- false-support rate (n=45);
- conflict-correct rate (n=10);
- qualified-correct rate (n=5);
- HitRate@K where represented as per-case binary success.

Small-n intervals for conflict/qualified categories must remain visible; do not present their percentages without denominators.

## 16. Post-run blind answer adjudication

After the single official run, human answer adjudication may be performed on the frozen outputs.

Reviewers may see:

- case question;
- frozen ground-truth rubric;
- relevant source material;
- model answer;
- cited/retrieved evidence needed for adjudication.

Reviewers must **not** see:

- aggregate benchmark score;
- system pass/fail label for the case;
- internal confidence used as a correctness hint;
- category-level performance summary;
- another reviewer's label before submitting their own label.

At least two independent labels should be collected for the primary answer-supported, conflict, and qualified families when feasible. Report raw agreement and Cohen's kappa where mathematically defined. Disagreements may be adjudicated by a third review step, with original labels preserved.

This post-run review may refine the **human-adjudicated report**, but it may not rewrite the machine-generated official result artifact.

## 17. Failure taxonomy

Every incorrect/rejected case in the final analysis must be assigned one or more descriptive failure classes without modifying the frozen result, such as:

- retrieval_miss;
- wrong_document;
- incomplete_multi_document_retrieval;
- unsupported_support;
- false_rejection;
- subject_grounding_failure;
- predicate_grounding_failure;
- evidence_trace_failure;
- conflict_resolution_failure;
- qualification_loss;
- scope_failure;
- answer_extraction_failure;
- runtime_error;
- evaluator_or_ground_truth_defect.

If a genuine evaluator or ground-truth defect is discovered only after the run, preserve the original official metric and issue an explicit corrected analysis alongside it. Do not silently replace the official result.

## 18. Pre-declared interpretation bands

V4 is primarily evidentiary, not a pass/fail marketing exercise. Nevertheless, the following interpretation rules are fixed in advance:

- any false-support result must be reported prominently with its denominator;
- any category with fewer than 10 cases must be described with count and CI, not percentage alone;
- retrieval success cannot be used as a substitute for answer correctness;
- zero runtime errors does not imply answer correctness;
- a strong development benchmark cannot override a weak V4 frozen result;
- a strong V4 result cannot be generalized to all domains or production deployments;
- negative results remain valid evidence and must be preserved.

No single composite score will be used as the primary headline metric.

## 19. Invalid-run conditions

The official V4 claim is invalid if any of the following occurs before or during the official run:

- benchmark/evaluator/source hashes do not match the freeze manifest;
- target code commit differs from the recorded frozen evaluation commit without a documented behavior-preserving reason accepted before outputs are viewed;
- questions were tuned after probing the target system;
- evaluator semantics changed after freeze;
- source corpus changed after freeze;
- any official result was deleted or overwritten because performance was undesirable;
- multiple completed runs were performed and the best run was selected.

An invalid run must be labeled invalid and preserved for audit; a new benchmark version, not a silent rerun, is required.

## 20. Required final report

The final V4 report must state:

- exact target code SHA;
- exact benchmark/evaluator/source/result hashes;
- environment and hardware;
- case counts and fixed denominators;
- retrieval metrics;
- answer/rejection/conflict/qualification metrics;
- confidence intervals;
- runtime errors;
- human adjudication status/agreement if completed;
- all material failures and limitations;
- whether any protocol deviation occurred;
- explicit claim boundary.

The report must not use “external,” “customer validated,” “production ready,” “zero hallucination,” or similar language unless independently supported outside this protocol.

## 21. Sequence of work

The permitted sequence is:

1. merge this protocol;
2. select/license-review authoritative sources;
3. acquire and hash sources;
4. author exactly 160 cases to the fixed distribution;
5. run contamination checks;
6. perform pre-run ground-truth review;
7. implement/finalize evaluator and pre-freeze validators without probing the target system on V4;
8. freeze all V4 artifacts and hashes in a dedicated freeze commit/PR;
9. verify frozen hashes;
10. execute the official blind evaluation exactly once;
11. commit the immutable official result;
12. perform blinded human answer adjudication;
13. publish final V4 analysis without altering the official result.

Until step 10 is completed, **no V4 performance claim exists**.
