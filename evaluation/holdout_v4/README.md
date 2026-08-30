# Holdout V4 Freeze Workspace

This directory implements the pre-declared `PROTOCOL.md` without executing the official blind run.

## Current state

`source_specs.json`, deterministic source acquisition, contamination checking, pre-freeze validation, freeze-manifest construction, and the guarded production evaluator are present. The official V4 result does **not** exist and must not be created until every pre-freeze gate passes.

## Required sequence

```powershell
py -3.11 evaluation\holdout_v4\download_sources.py
# Human-review each source/license entry and set license_review_status=APPROVED in sources_manifest.jsonl only after verification.
# Author the 160 source-grounded cases without running RALG on them.
py -3.11 evaluation\holdout_v4\check_contamination.py
# Complete pre_run_review.jsonl with one APPROVED record per case after source-ground-truth review.
py -3.11 evaluation\holdout_v4\pre_freeze_validate.py
py -3.11 evaluation\holdout_v4\build_freeze_manifest.py
```

After the freeze PR is merged, verify hashes again. Only then may the official evaluator be invoked once:

```powershell
py -3.11 src\holdout_v4_eval.py --execute-frozen-blind-run
```

The evaluator refuses to overwrite an existing official result.

## Hard stop

Do not run the official evaluator while source acquisition, licensing review, benchmark authoring, contamination checking, or pre-run ground-truth review is incomplete. Do not use target-system output to author or revise V4 questions.
