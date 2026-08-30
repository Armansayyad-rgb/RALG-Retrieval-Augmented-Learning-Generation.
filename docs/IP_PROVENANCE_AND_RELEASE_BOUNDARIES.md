# IP Provenance and Release Boundaries

This document records repository-level provenance and distribution boundaries for technical diligence and release preparation. It is an engineering record, not legal advice.

## 1. Source-code ownership record

Repository history reviewed to date shows commits authored under the project owner's Git identity, with no detected external source-code contributors in the reviewed history. This supports a simple contributor chain for the current codebase, subject to independent legal verification if required for a transaction or commercial license.

The repository was initially published under the MIT License and was later relicensed under the RALG Source-Available Non-Commercial License v1.0. Rights already granted under earlier published license versions are not retroactively revoked. Any exclusivity analysis must therefore distinguish current code/assets from rights granted on earlier revisions.

## 2. Current license boundary

The current repository license permits non-commercial use, modification, and redistribution subject to its terms and requires separate permission for commercial use. It is source-available and is not represented as OSI-approved open source.

A commercial license, IP assignment, or acquisition agreement must be documented separately from the public repository license. Patent, warranty, indemnity, exclusivity, and assignment terms require legal review rather than inference from repository metadata.

## 3. Assets excluded from commercial release until provenance is resolved

The following assets must not be included in a commercial distribution package unless their provenance and applicable rights are independently resolved and documented:

- `data/train.txt` — apparent Wikipedia-derived text with incomplete repository provenance and no reliable source/license chain.
- Custom model checkpoints whose exact training lineage cannot be reconstructed from immutable training logs, dataset/version pins, and build records, including any locally stored `reasoning_model_v1.pt`, `instruction_model_v4.pt`, `embedding_model.pt`, or similarly named custom checkpoints.
- Any generated derivative artifact whose only provenance assertion depends on one of the unresolved assets above.

These exclusions do not imply that the runtime source code itself is unusable. They define what must be omitted from a release/disclosure package until evidence is available.

## 4. Third-party and dataset boundaries

`data/wikitext_v2.txt` is derived from Salesforce WikiText material. Repository records currently show ambiguity between CC BY-SA 3.0 metadata and CC BY-SA 4.0 documentation. Distribution must preserve attribution and the exact applicable license version should be confirmed against the authoritative upstream source before commercial redistribution.

IETF RFCs, Holdout V3 upstream documents, Qwen optional model assets, and other third-party materials remain governed by their respective upstream terms and notices. `THIRD_PARTY_NOTICES.md` and source manifests are the repository-level attribution index; those notices do not replace the upstream licenses.

## 5. Custom checkpoint provenance standard

A custom checkpoint may be classified as commercially releasable only when the repository or transaction data room can establish, at minimum:

1. exact training script and commit;
2. exact training-data sources and versions/hashes;
3. preprocessing/tokenizer lineage;
4. training command/configuration and environment;
5. output checksum;
6. identity of the person/entity that performed the training; and
7. confirmation that all input licenses permit the intended distribution/use.

Until those records exist, the checkpoint is classified as **PROVENANCE INCOMPLETE — EXCLUDE FROM COMMERCIAL DISTRIBUTION**.

## 6. Release-package rule

A release or diligence package should contain only assets classified as one of:

- `PROJECT-OWNED / PROVENANCE ESTABLISHED`;
- `THIRD-PARTY / REDISTRIBUTION PERMITTED WITH NOTICE`; or
- `REFERENCE-ONLY / NOT REDISTRIBUTED`.

Anything classified as `PROVENANCE INCOMPLETE`, `LICENSE VERSION UNRESOLVED`, or `EXCLUDE FROM COMMERCIAL DISTRIBUTION` must be omitted from the distributable package and listed explicitly in the release manifest.

## 7. Legal-review items

The following are deliberately left for qualified counsel or transaction documentation rather than being resolved by code changes:

- effect of prior MIT grants on exclusivity;
- final commercial/source-available license language;
- whether an explicit patent grant is appropriate;
- commercial assignment/license mechanics;
- dataset/share-alike obligations for specific derivative artifacts;
- representations and warranties regarding model-training provenance; and
- contributor/CLA policy for future external contributors.

## 8. Engineering freeze boundary

This provenance cleanup does not alter retrieval, grounding, API behavior, evaluation thresholds, frozen Holdout V1/V2/V3 artifacts, or benchmark outcomes. Legal/IP documentation must preserve negative evidence and historical license facts rather than rewriting them for presentation.
