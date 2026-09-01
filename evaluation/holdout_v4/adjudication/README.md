# Holdout V4 Blinded Human Adjudication

This directory contains **post-run analysis tooling only** for the immutable official Holdout V4 result. It must not modify `evaluation/results/holdout_v4_blind_once.json`.

Protocol authority: `evaluation/holdout_v4/PROTOCOL.md`, especially sections 13–17 and 20–21.

## Scope

Human answer adjudication covers the frozen 115 non-rejection cases:

- 100 primary answer-supported cases;
- 10 conflicting-evidence cases;
- 5 conditional/qualified cases.

The 45 rejection cases retain the official machine rejection accounting; they are not included in the two-reviewer packet requirement.

## Blinding

Reviewer packets may contain the case question, frozen ground-truth rubric, relevant source/evidence material, model answer, and retrieved/cited evidence needed for judgment.

Reviewer packets generated here deliberately omit:

- aggregate benchmark scores;
- machine pass/fail decisions;
- the result `supported` flag;
- answer type;
- internal confidence;
- retrieval scores and ranks;
- latency;
- category-level performance summaries;
- the other reviewer's labels.

Reviewers A and B must complete their labels independently. Neither reviewer should inspect the official aggregate result, the other reviewer's label file, or any derived performance summary before finishing their own labels.

## Generate packets

From repository root:

```powershell
py -3.11 evaluation\holdout_v4\adjudication\generate_blinded_packets.py
```

The generator first verifies the official result byte hash against:

`fad3c3baf73d192fa4fb7b21fa891fa0d6a3a29bd1c52009175a480adcadde23`

If the hash differs, generation aborts. Do not bypass this check; investigate and document the discrepancy first.

Generated files are written to:

`evaluation/holdout_v4/adjudication/generated/`

The generator uses exclusive creation and will refuse to overwrite an existing packet or label file. This preserves the initial review materials and labels.

## Label fields

Each reviewer receives a blank label file keyed by `case_id` with these fields:

- `substantive_correct`: `true`, `false`, or `null` when genuinely indeterminate;
- `evidence_sufficient`: `true`, `false`, or `null`;
- `evidence_traceable`: `true`, `false`, or `null`;
- `conflict_or_qualification_handling`: use `"correct"`, `"incorrect"`, `"not_applicable"`, or `"unclear"`;
- `reviewer_notes`: short source-grounded explanation, especially for any negative/unclear judgment.

A supported answer is ultimately correct only if its substantive claim satisfies the frozen rubric and its evidence is sufficient. Conflict cases must safely identify/resolve the relevant conflict/scope/version distinction. Qualified cases must preserve the required condition/exception/version/scope/qualification.

## Independence and reconciliation

At least two independent labels should be collected when feasible. Preserve both original label files unchanged after submission. Only after both are complete should agreement, Cohen's kappa (where defined), disagreement lists, third-step adjudication, final human metrics, and failure taxonomy be produced.

A disagreement may be resolved in a separate adjudication file. Never edit either reviewer's submitted labels to manufacture agreement.

## Failure taxonomy

Final incorrect/rejected cases should receive one or more protocol-defined descriptive classes where applicable:

`retrieval_miss`, `wrong_document`, `incomplete_multi_document_retrieval`, `unsupported_support`, `false_rejection`, `subject_grounding_failure`, `predicate_grounding_failure`, `evidence_trace_failure`, `conflict_resolution_failure`, `qualification_loss`, `scope_failure`, `answer_extraction_failure`, `runtime_error`, `evaluator_or_ground_truth_defect`.

Any discovered evaluator/ground-truth defect must be reported alongside the immutable official result; it must not silently rewrite that result.
