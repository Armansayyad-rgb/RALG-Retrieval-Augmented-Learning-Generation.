# Technical differentiation evidence

RALG's differentiator is pipeline discipline rather than a larger hosted model:
local retrieval, conditional extra retrieval for harder questions, explicit
evidence/source contracts, conservative abstention, and runtime-document
provenance. The pilot package makes those claims reproducible without changing
production rules.

## Compared evidence

`heldout_evaluation.py` runs the same 180 held-out questions through a
transparent term-overlap baseline and the current `src.retriever_v2` RALG
retriever. It records Recall@5 and latency for each path. `run_ablation.py`
captures the comparison and explicitly records that no benchmark-specific
switch or constant was changed.

## Operational evidence

The scalability probe measures index build and one query over bounded synthetic
chunk counts; larger requested levels are opt-in because hardware/RAM was not
available for a responsible default run. The concurrency soak exercises
read-only retrieval in a thread pool and reports request count, workers,
elapsed time, and errors.

All corpus content is synthetic, non-sensitive, and deterministic. These
measurements are engineering evidence only; they are not a claim of superiority
over commercial systems or a substitute for a customer-specific bake-off.
