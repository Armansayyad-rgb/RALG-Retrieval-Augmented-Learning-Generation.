# Third-Party Notices

This file documents third-party materials redistributed with or used by this repository, together with repository-level attribution and provenance notes. Upstream license texts and terms remain controlling. This document is not legal advice.

## 1. WikiText / Salesforce WikiText Language Modeling Corpus

- **Source:** Salesforce AI Research (`salesforce/wikitext` distribution path used by the project)
- **Paper:** Merity et al., "Pointer Sentinel Mixture Models" (arXiv:1609.07843, 2016)
- **Repository path:** `data/wikitext_v2.txt`
- **License family:** Creative Commons Attribution-ShareAlike

Repository evidence currently contains a license-version ambiguity: the Hugging Face dataset card documentation has stated CC BY-SA 4.0 while structured metadata has also identified CC BY-SA 3.0. The authoritative version applicable to the exact distributed corpus should be verified against the upstream Salesforce distribution before commercial redistribution. Attribution/share-alike obligations must be preserved in either case.

**Attribution:**

> WikiText dataset, Salesforce AI Research. Original paper: Merity, S., Xiong, C., Bradbury, J., and Socher, R., "Pointer Sentinel Mixture Models," arXiv:1609.07843 (2016). Source: https://huggingface.co/datasets/salesforce/wikitext

## 2. Qwen2.5-1.5B-Instruct (optional third-party model)

- **Source:** Qwen Team / Alibaba Cloud (`Qwen/Qwen2.5-1.5B-Instruct`)
- **License:** Apache License 2.0
- **Repository status:** weights are local/external and are not committed to Git
- **Download helpers:** `src/download_polish_llm.py`, `src/download_polish_llm_direct.py`

Qwen is a third-party optional dependency and is not a project-owned checkpoint. Its upstream Apache 2.0 license and notices apply independently.

**Attribution:**

> Qwen2.5-1.5B-Instruct, Qwen Team (Alibaba Cloud), licensed under Apache License 2.0. Source: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct

## 3. IETF RFC documents (Stage 5 evaluation corpus)

- **Source:** Internet Engineering Task Force / RFC Editor
- **Repository path:** `evaluation/stage5_documents/rfc*.txt`
- **Provenance manifest:** `evaluation/stage5_source_manifest.jsonl`
- **Rights:** governed by applicable IETF Trust Legal Provisions

Preserve the required IETF notices and attribution when redistributing these documents. Repository documentation must not describe the RFCs as project-owned or public-domain material.

## 4. Python Enhancement Proposals (Holdout V1 source material)

- **Source:** Python Software Foundation / Python community PEP repository
- **Repository paths:** PEP source artifacts used by `evaluation/holdout_v1/`
- **Purpose:** frozen historical/diagnostic evaluation source material

Preserve upstream attribution and any source-specific notices. The frozen Holdout V1 benchmark/result boundary is independent of the licensing classification and must not be rewritten or rerun for presentation.

## 5. Project-authored synthetic/development data

Project-authored evaluation and development fixtures include material under paths such as:

- `data/technical_doc_benchmark_v1.jsonl`;
- `data/technical_doc_benchmark_hard_v1.jsonl`;
- `data/stage3_customer_corpus_v1.jsonl`;
- `data/stage4_customer_corpus_v1.jsonl`;
- `data/pilot_customer_corpus_v1.jsonl`;
- `data/knowledge_extra_v1.txt`.

These are governed by the repository's current license unless a file-specific notice states otherwise. They are development/synthetic evidence and must not be represented as customer-authored or independently authored validation data.

## 6. Custom model/checkpoint artifacts

Local custom checkpoint names documented by the project include:

- `checkpoints/v2/reasoning_model_v1.pt`;
- `checkpoints/v2/instruction_model_v4.pt`;
- `checkpoints/embedding_model.pt`.

These files are not committed to Git. Although the repository contains project-authored training code, the reviewed repository does not contain sufficient immutable training records to establish a complete commercial provenance chain for every custom checkpoint (exact dataset versions/hashes, preprocessing lineage, training command/environment, and output-generation record).

**Current distribution classification:** `PROVENANCE INCOMPLETE — EXCLUDE FROM COMMERCIAL DISTRIBUTION` until the lineage is reconstructed and independently verified. Do not describe these checkpoints as commercially cleared solely because the training code is project-authored.

See `docs/IP_PROVENANCE_AND_RELEASE_BOUNDARIES.md` and `docs/DATA_RIGHTS_INVENTORY.md`.

## 7. Holdout V3 upstream source artifacts

Holdout V3 uses seven authoritative upstream technical sources committed under `evaluation/holdout_v3/sources/` with source manifests/revisions. Holdout V3 is an **authoritative-source independent blind holdout**; this label describes evaluation methodology and does not mean the upstream source licenses are uniform.

### 7.1 SQLite Write-Ahead Logging

- **Source:** SQLite documentation
- **Repository path:** `evaluation/holdout_v3/sources/sqlite_wal_mode.txt`
- **License status:** SQLite documentation/project material identified by upstream as public domain; verify any page-specific notice when redistributing.

### 7.2 PostgreSQL Routine Vacuuming

- **Source:** PostgreSQL Global Development Group
- **Repository path:** `evaluation/holdout_v3/sources/postgresql_vacuuming.txt`
- **License:** PostgreSQL License

### 7.3 Kubernetes Probes

- **Source:** Kubernetes documentation
- **Repository path:** `evaluation/holdout_v3/sources/kubernetes_probes.txt`
- **License:** CC BY 4.0

### 7.4 systemd.unit

- **Source:** systemd project
- **Repository path:** `evaluation/holdout_v3/sources/systemd_unit.txt`
- **License:** LGPL-2.1-or-later (see exact upstream source/revision record)

### 7.5 OpenTelemetry Propagators API

- **Source:** OpenTelemetry specification
- **Repository path:** `evaluation/holdout_v3/sources/otel_propagators.txt`
- **License:** Apache 2.0

### 7.6 OCI Image Layout

- **Source:** Open Container Initiative image-spec
- **Repository path:** `evaluation/holdout_v3/sources/oci_image_layout.txt`
- **License:** Apache 2.0

### 7.7 CMake Presets

- **Source:** CMake documentation / Kitware
- **Repository path:** `evaluation/holdout_v3/sources/cmake_presets.txt`
- **License:** BSD 3-Clause (see exact upstream source/revision record)

The exact canonical URLs, revisions, hashes, and acquisition records are maintained in the Holdout V3 manifests. Preserve source-specific attribution and license obligations when redistributing these artifacts.

## 8. Unresolved training artifact: `data/train.txt`

`data/train.txt` is tracked historical training/development material with incomplete repository provenance and apparent Wikipedia-derived content. No reliable repository record establishes the exact acquisition source or license chain.

**Current distribution classification:** `PROVENANCE INCOMPLETE — EXCLUDE FROM COMMERCIAL DISTRIBUTION` until provenance and rights are resolved.

## 9. Holdout V4 authoritative-source corpus

Holdout V4 uses 12 commit-pinned third-party technical documents under `evaluation/holdout_v4/sources/`. The exact upstream repositories, pinned commits, canonical URLs, acquisition timestamps, raw and normalized hashes, and project-owner source-license review status are recorded in `evaluation/holdout_v4/sources_manifest.jsonl`.

The corpus includes material from Git, Linux, Docker Docs, Prometheus, GitHub Docs, Ansible Documentation, curl, RabbitMQ, Grafana, CPython, Node.js, and The Rust Programming Language Book. These source files remain third-party artifacts under their respective upstream licenses and are not relicensed under the RALG product license.

The source-specific attribution, normalization/change disclosure, license basis, notice requirements, and redistribution boundaries are documented in `evaluation/holdout_v4/THIRD_PARTY_NOTICES.md`. Supporting review evidence is in `evaluation/holdout_v4/LICENSE_REVIEW_EVIDENCE.md` and `evaluation/holdout_v4/LICENSE_REDISTRIBUTION_REVIEW.md`.

Project-owner approval was recorded on 2026-08-31 as `APPROVED_WITH_OBLIGATIONS`. This is an engineering/compliance decision, not independent legal advice or third-party legal review. Preserve applicable complete upstream license texts, copyright/permission notices, NOTICE material, attribution, source-availability obligations, and the deterministic normalization/change disclosure when redistributing the V4 corpus.

---

*Last reviewed: 2026-08-31*
