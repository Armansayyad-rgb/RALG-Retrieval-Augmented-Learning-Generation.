# Data Rights Inventory

**Branch:** `hardening/acquisition-diligence-v1`
**Date:** 2026-08-25

---

## 1. Training Data

### WikiText-2 (raw)
- **Source:** Hugging Face `wikitext` dataset (via `src/download_corpus.py`)
- **Purpose:** Pre-training corpus for BPE tokenizer construction and SmallLM training
- **Included in repo:** Yes — `data/wikitext_v2.txt` (60 MB), tracked in Git
- **License:** CC-BY-SA-3.0 (Hugging Face `wikitext` dataset default)
- **Redistribution:** Permitted with attribution
- **Commercial use:** PERMITTED with attribution
- **Risk:** LOW
- **Note:** `data/wikitext_v2_tokens.pt` (54 MB) is generated tokenization output, NOT tracked in Git (`.gitignore: data/*.pt`)

### WikiText-2 Tokenized
- **Source:** Generated from WikiText-2 raw
- **Purpose:** Pre-tokenized training input for SmallLM
- **Included in repo:** No (gitignored `*.pt`)
- **License:** Same as source (CC-BY-SA-3.0)
- **Risk:** LOW

### Embedding Training Data
- **Source:** Generated from WikiText-2
- **Purpose:** Training data for the embedding model
- **Included in repo:** No (gitignored: `data/embedding_train.jsonl`)
- **License:** Derived from CC-BY-SA-3.0 source
- **Risk:** LOW

### Instruction Training Data
- **Source:** Generated from WikiText-2
- **Purpose:** Instruction-tuning data for SmallLM
- **Included in repo:** No (gitignored: `data/instruction_train*.jsonl`, `data/reasoning_train*.jsonl`, `data/extractive_qa*.jsonl`)
- **License:** Derived from CC-BY-SA-3.0 source
- **Risk:** LOW

### Technical Documentation Samples
- **Source:** Project-authored synthetic technical documents
- **Purpose:** Benchmark and evaluation corpus for V2/V4/hybrid retrieval testing
- **Included in repo:** Yes — `data/technical_docs_sample.txt`, `data/technical_docs_hard_sample.txt`, `data/technical_doc_benchmark_v1.jsonl`, `data/technical_doc_benchmark_hard_v1.jsonl`
- **License:** Project author's copyright (same as source code)
- **Commercial use:** Subject to RALG source-available license
- **Risk:** LOW

---

## 2. Customer/Pilot Corpus (Synthetic)

### Pilot Customer Corpus
- **Source:** Synthetic, project-authored
- **Purpose:** Simulated customer documents for pilot validation
- **Included in repo:** Yes — `data/pilot_customer_corpus_v1.jsonl`
- **License:** Project author's copyright
- **Risk:** LOW

### Stage 3 Customer Corpus
- **Source:** Synthetic, project-authored
- **Purpose:** Stage 3 pilot hardening evaluation
- **Included in repo:** Yes — `data/stage3_customer_corpus_v1.jsonl`
- **License:** Project author's copyright
- **Risk:** LOW

### Stage 4 Customer Corpus
- **Source:** Synthetic, project-authored
- **Purpose:** Stage 4 external evidence evaluation
- **Included in repo:** Yes — `data/stage4_customer_corpus_v1.jsonl`
- **License:** Project author's copyright
- **Risk:** LOW

### Knowledge Extra
- **Source:** Project-authored
- **Purpose:** Additional domain knowledge for evaluation
- **Included in repo:** Yes — `data/knowledge_extra_v1.txt`
- **License:** Project author's copyright
- **Risk:** LOW

---

## 3. Stage 5 RFC Corpus

### Source Documents (50 RFCs)
- **Source:** IETF RFC Editor (https://www.rfc-editor.org)
- **Purpose:** Independent Stage 5 evaluation corpus — external validation benchmark
- **Included in repo:** Yes — `evaluation/stage5_documents/*.txt`
- **License:** IETF Trust Legal Provisions (BCP 78/79)
- **Redistribution:** Permitted with IETF legal notice
- **Commercial use:** PERMITTED with legal notice preservation
- **Provenance evidence:** `evaluation/stage5_source_manifest.jsonl` — SHA-256 hashes, acquisition dates, canonical URLs
- **Manifest integrity:** All 50 documents have SHA-256 hashes in manifest; `evaluation/stage5_review_pack/` contains review copies
- **Risk:** LOW
- **Important:** RFCs are NOT public domain. They are published under IETF Trust provisions. Redistribution requires preserving the IETF legal notice. The `stage5_source_manifest.jsonl` records the exact redistribution status for each document as `permitted_with_IETF_legal_notice`.

### Stage 5 Benchmark Cases
- **Source:** Auto-generated from RFC corpus + synthetic unsupported cases
- **Purpose:** 300-case evaluation benchmark (100 supported, 200 unsupported variants)
- **Included in repo:** Yes — `evaluation/stage5_review_queue.jsonl` (review annotations), `evaluation/results/stage5_preliminary_results.json` (evaluation results)
- **License:** Project author's copyright (auto-generated evaluation material)
- **Commercial use:** Subject to RALG source-available license
- **Risk:** LOW
- **Note:** Questions, expected answers, labels, and thresholds are evaluation infrastructure. They are NOT tuned against in this branch.

---

## 4. Held-Out Evaluation Data

### Held-Out Commercial V1
- **Source:** Synthetic, project-authored
- **Purpose:** 25-case commercial readiness validation
- **Included in repo:** Yes — `evaluation/heldout_commercial_v1.json`
- **License:** Project author's copyright
- **Risk:** LOW

### Held-Out Pilot V1
- **Source:** Synthetic, project-authored
- **Purpose:** Pilot evaluation held-out set
- **Included in repo:** Yes — `evaluation/heldout_pilot_v1.jsonl`
- **License:** Project author's copyright
- **Risk:** LOW

### Held-Out Stage 3/4 Customer
- **Source:** Synthetic, project-authored
- **Purpose:** Stage 3/4 held-out evaluation
- **Included in repo:** Yes — `evaluation/heldout_stage3_customer_v1.jsonl`, `evaluation/heldout_stage4_customer_v1.jsonl`
- **License:** Project author's copyright
- **Risk:** LOW

---

## 5. Runtime Uploads

- **Source:** User-uploaded documents at runtime
- **Purpose:** Customer documents ingested via API/WebUI
- **Included in repo:** No (gitignored: `data/runtime_uploads/`)
- **License:** User's own content — not governed by RALG license
- **Risk:** N/A (user data, not distributed)

---

## 6. Tokenizer Artifacts

### data/tokenizer.json
- **Source:** Trained on WikiText-2 by project author
- **Purpose:** BPE tokenizer vocabulary for SmallLM
- **Included in repo:** Yes (tracked in Git)
- **License:** Derived from CC-BY-SA-3.0 training data; project author's copyright on the trained artifact
- **Commercial use:** PERMITTED (trained on openly-licensed data)
- **Risk:** LOW

### data/tokenizer_v2.json
- **Source:** Trained on WikiText-2 by project author
- **Purpose:** Updated BPE tokenizer vocabulary
- **Included in repo:** Yes (tracked in Git)
- **License:** Same as above
- **Risk:** LOW

---

## 7. Model/Checkpoint Binaries

See separate section in [ACTIVE_RUNTIME_INVENTORY.md](./ACTIVE_RUNTIME_INVENTORY.md).

- No checkpoint binaries (`.pt`, `.pth`, `.safetensors`) are tracked in Git
- `checkpoints/` directory is gitignored
- Qwen2.5-1.5B-Instruct weights (`model.safetensors.partial`, 2.5 GB) are locally present but NOT in Git
- **Buyer would need to re-download** Qwen2.5-1.5B-Instruct from HuggingFace Hub (requires network access)
- Custom SmallLM checkpoints (`final_model.pt`, `epoch_*.pt`) are trained by project author on WikiText-2 — provenance established
- `PROVENANCE REQUIRES OWNER CONFIRMATION` for: custom training scripts and their outputs unless buyer verifies training pipeline

---

## 8. Provenance Summary

| Data Category | Source | In Git | License | Commercial | Risk |
|---------------|--------|--------|---------|------------|------|
| WikiText-2 raw | HuggingFace | Yes | CC-BY-SA-3.0 | Yes (attribution) | LOW |
| WikiText-2 tokens | Generated | No | CC-BY-SA-3.0 | Yes (attribution) | LOW |
| Training data | Generated | No | Derived CC-BY-SA-3.0 | Yes | LOW |
| Technical docs | Project author | Yes | RALG license | Subject to RALG | LOW |
| Customer corpora | Synthetic | Yes | RALG license | Subject to RALG | LOW |
| Stage 5 RFCs | IETF | Yes | IETF Trust | Yes (with notice) | LOW |
| Stage 5 cases | Auto-generated | Yes | RALG license | Subject to RALG | LOW |
| Held-out eval | Synthetic | Yes | RALG license | Subject to RALG | LOW |
| Runtime uploads | User | No | User's own | N/A | N/A |
| Tokenizer | Trained | Yes | Derived CC-BY-SA-3.0 | Yes | LOW |
| Checkpoints | Trained/Downloaded | No | See model audit | Varies | MEDIUM |
