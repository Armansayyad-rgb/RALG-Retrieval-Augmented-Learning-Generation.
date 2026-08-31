# Holdout V4 Freeze Workspace

This directory implements the pre-declared `PROTOCOL.md` without executing the official blind run.

## Current state

The V4 protocol, source-selection specification, commit-pinned source acquisition, benchmark schema, exact-distribution authoring template generator, contamination checker, baseline pre-freeze validator, strict pre-freeze integrity validator, freeze-manifest builder, and guarded production evaluator are present.

The official V4 result does **not** exist and must not be created until every pre-freeze gate passes.

## Remaining pre-freeze gates

1. Acquire the 12 selected upstream documents with the commit-pinned downloader.
2. Verify each source's redistribution/license terms and record a real reviewer decision in `sources_manifest.jsonl`; do not auto-approve licensing.
3. Author exactly 160 source-grounded cases to the distribution fixed by `PROTOCOL.md`, without probing RALG on V4.
4. Perform source-ground-truth review for all 160 cases and preserve the reviewer record; do not auto-approve cases.
5. Run contamination checking and obtain `PASS`.
6. Run both pre-freeze validators and obtain `PASS`.
7. Build the immutable freeze manifest and record the target code SHA and artifact hashes.
8. Merge the freeze PR, verify hashes again, and only then execute the official blind run once.

## Preparation sequence

```powershell
py -3.11 evaluation\holdout_v4\download_sources.py
py -3.11 evaluation\holdout_v4\build_authoring_template.py
# Complete license review, benchmark authoring, and source-ground-truth review without running RALG on V4.
py -3.11 evaluation\holdout_v4\check_contamination.py
py -3.11 evaluation\holdout_v4\pre_freeze_validate.py
py -3.11 evaluation\holdout_v4\pre_freeze_integrity.py
py -3.11 evaluation\holdout_v4\build_freeze_manifest.py
```

After the freeze PR is merged and all hashes verify, the single official run is:

```powershell
py -3.11 src\holdout_v4_eval.py --execute-frozen-blind-run
```

The evaluator must refuse to overwrite an existing official result.

## Integrity rules

- Source branches/tags are resolved to immutable Git commit SHAs before acquisition.
- Raw and normalized source SHA-256 values must match the manifest.
- Required evidence anchors for answerable cases must exist verbatim in the frozen normalized source file.
- Cross-document cases require at least two relevant documents.
- Document-scoped cases require explicit scope.
- Conflict cases require contradiction/conflict annotations.
- The contamination report must match the exact benchmark hash.
- Review approval must correspond exactly to all 160 case IDs.

## Hard stop

Do not run the official evaluator while source acquisition, licensing review, benchmark authoring, contamination checking, or pre-run source-ground-truth review is incomplete. Do not use target-system output to author or revise V4 questions, and do not fabricate reviewer approvals to accelerate the freeze.
