# Stage 6 Validation Freeze Record

**Branch:** `validation/stage6-independent-review`
**Freeze date:** 2026-08-26
**Master SHA at freeze:** `60dc7cccc951bd2975cde495cc06842188f4510b` (merge of PR #52)

---

## 1. Purpose

This record fixes the exact system state **before** independent human review of
the Stage 5 benchmark begins. Its purpose is to demonstrate that human review
occurs **after** system freeze: any change to retrieval logic, model weights,
benchmark data, or evaluation scoring after this freeze invalidates the review
round and requires a re-freeze.

## 2. Frozen Runtime Architecture (state)

- Unified execution boundary: `execute_runtime()` shared by API (`api_server`)
  and WebUI (`webui/hybrid_pipeline`) — behavioral parity covered by
  `src/test_runtime_integration.py`.
- Pipeline: question routing → factual extractor OR grounded reasoning →
  evidence/provenance/support gate → supported answer or abstention.
- Architecture reference: `docs/CURRENT_ARCHITECTURE_STATUS.md`.

| Component | File | SHA-256 |
|---|---|---|
| Hybrid retriever (authoritative) | `src/retriever_hybrid.py` | `a3f74bc4a197ca8ace4880a90c7aca37c8ff12f728570898926aaa0bb92e0d66` |
| Core lexical retriever | `src/retriever_v2.py` | `b8fcc7f05ebd20f62b3dcf1b008d1346c719907987fe56c180ba41cbcdfc91b1` |
| Runtime orchestrator | `src/runtime_architecture.py` | `181de26e4f9c30e0594e14f14ed3d49bfe734d9481e922df94ee3ad3fedcf3ba` |
| RAG pipeline | `src/rag_chat_v2.py` | `fb87519aae7447f6d6a2abdc82a167d4f667f76740af50fa856748c13a6c07f2` |
| SmallLM V2 model definition | `src/model_v2.py` | `4bee6ae7f48c49363558a113e3c8d38a9978d58df480fec53bde924f8ab675c7` |

## 3. Frozen Stage 5 Dataset / Fixtures

| Artifact | SHA-256 |
|---|---|
| Benchmark cases (`evaluation/stage5_review_queue.jsonl`, 300 cases) | `9eee7e1ae634ba26cdd418b910e7334566bd60d7753d8538365effe9c9ca113d` |
| Source manifest (`evaluation/stage5_source_manifest.jsonl`, 50 RFCs) | `6c66d569c26bcb823250f785ead62bde249324d3f82201d2cc845c98a9baff0b` |
| RFC corpus (`evaluation/stage5_documents/`, 50 files, combined digest) | `2fc45bc32bc689fb7fb43b1953deb3275f5bcd1c2676a60ad628bcfc680ad023` |
| **Authoritative preliminary results** (`evaluation/results/stage5_preliminary_results.json`, hybrid run reproduced from frozen code) | `46c777158f062b9b16bde005bbc1ba84d7176d509dfe38b294e3cff8544f63e4` |
| Legacy pre-hybrid results, preserved (`evaluation/results/stage5_preliminary_results_legacy.json`) | `74acdd43eea7f7c7c9d2832f4a236d6aac402f7cffb7bf6d580211d70d6981b1` |

Dataset composition (from the Stage 5 integrity report): 300 cases
(210 supported / 90 unsupported), 50 independent IETF RFC documents, all
`synthetically_generated: false`, zero duplicate case IDs or questions.

## 4. Frozen Evaluation Tooling

| Script | SHA-256 |
|---|---|
| `scripts/stage5_preliminary_evaluation.py` | `eeb38486c958d6c4c8e87c4110e07bf57e568337bad47a5429215ae0dcb800c4` |
| `scripts/stage5_evaluation.py` | `bc732c8826669f713f95f23caabd4ada7e6f17a6ec81c6de9464626315009df9` |
| `scripts/stage5_ingest_reviews.py` (Stage 6 revision) | `2ff9ff0b173e25a1a75d32b060643ec2e8a7d3701788f8d725c0732417a07f22` |
| `scripts/stage5_review_pack.py` | `c3c0cb6b90702d6df664cc40919f4af326cbb305cf38a363d28997ad37080f03` |
| `scripts/test_docker_lifecycle.py` | `b696c412b3768dbb2764917f50c7baf5744d1856549313d6cb126f85f018ad48` |
| `scripts/stage6_review_agreement.py` (new) | `0635a206c58682645d2ec94b827dcba1da61db50651dd1c83f02f3d389cd9fce` |
| `scripts/stage6_evaluator.py` (new) | `774f704912eb171267ba10f7a2efd5c325a4141146f862780e7cc80577c539a6` |
| `scripts/buyer_demo_preflight.py` (new) | `8ff2b8f20bed4ad1bcd0979eba94f186bf68b500b708238203c759d24e1a237d` |

## 5. Frozen Stage 5 Metrics (authoritative artifact)

Source: `evaluation/results/stage5_preliminary_results.json`
(`status: "preliminary_unreviewed"`, 300 auto-generated, NOT independently
human-reviewed cases). Regenerated from frozen current code by the exact
evaluator command — the committed pre-hybrid artifact did NOT contain these
hybrid numbers (full provenance: `docs/STAGE5_EVIDENCE_HISTORY.md`).

| Metric | Lexical | RALG hybrid |
|---|---|---|
| Recall@1 | 40.48% | 50.95% |
| Recall@3 | 87.62% | 90.95% |
| Recall@5 | 100.00% | 100.00% |
| MRR | 0.6485 | 0.7098 |
| Unsupported rejection | 100% | 100% |
| False-support rate | 0% | 0% |

The legacy pre-hybrid artifact (`..._legacy.json`, RALG arm = V2 retriever:
R@1 37.14% / R@3 77.62% / R@5 92.86% / MRR 0.5863) is retained as HISTORICAL
evidence and pinned above. Both artifacts share 100% unsupported rejection
and 0% false-support.

Latency values in either artifact are machine-specific and not part of the
frozen claim set. Stage 5 was used during architecture development and is not
a pristine holdout; neither result is independent validation.

## 6. Docker Qualification State

- `scripts/test_docker_lifecycle.py`: **19/19 PASS** in the controlled local
  environment recorded in `docs/ACQUISITION_DILIGENCE_FINAL_REPORT.md`
  (Section E), image `ralg-engine:latest`, WebUI healthy on `127.0.0.1:7860`.
- Restart recovery uses `docker restart <container_name>`
  (`scripts/test_docker_lifecycle.py`, Phase 6).

## 7. Model / Checkpoint Identifier

| Artifact | Path | Identifier / size |
|---|---|---|
| Active small model checkpoint | `checkpoints/v2/reasoning_model_v1.pt` | SHA-256 `e32ac5be88e249c19e74355a8a3c352b62bf57cb03c0e6860bca8c6198f4efa3` (229,564,981 bytes) |
| Tokenizer | `data/tokenizer_v2.json` | SHA-256 `d6c21cd45cedb1d78ac476c0b3635a26c2a7c147c033e85e5151016c9d4e21de` (1,112,461 bytes) |
| Model architecture | `SmallLMV2` (`src/model_v2.py`) | vocab 7207, context 512, d_model 384, 6 heads, 8 layers |
| Optional polish LLM | `checkpoints/qwen2.5-1.5B-instruct` | Qwen2.5-1.5B-Instruct (optional; not required for demo path) |

Checkpoints and tokenizers are external to the repository bundle and are NOT
redistributed by the buyer/demo packages.

## 8. Freeze Constraints (binding from this point)

After this freeze and until a review round is formally closed:

1. **No retrieval tuning** — no changes to `retriever_hybrid`, `retriever_v2`,
   fusion/ranking logic, or index construction.
2. **No model/benchmark tuning** — no changes to checkpoints, tokenizer,
   Stage 5 questions, labels, categories, source RFCs, or expected answers.
3. **No scoring changes** — no changes to metric computation in
   `stage5_preliminary_evaluation.py` or `stage6_evaluator.py`.
4. Reviewer materials may only change via reviewer corrections captured
   through the ingestion tooling (`stage5_ingest_reviews.py`), never by
   editing fixtures directly.

Violations require a new freeze record with a new master SHA before review
results can be accepted.

## 9. Review Status at Freeze

**REVIEW INFRASTRUCTURE READY — HUMAN REVIEW PENDING.**
No genuine human-reviewed result file exists yet. Nothing in this repository
may be described as independently validated until real reviewer artifacts are
ingested through the Stage 6 tooling.
