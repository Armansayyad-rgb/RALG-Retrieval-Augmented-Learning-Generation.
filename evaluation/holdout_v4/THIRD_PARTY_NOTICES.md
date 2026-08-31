# Holdout V4 Third-Party Source Notices and Compliance Record

Status: **PRE-FREEZE COMPLIANCE RECORD — PROJECT-OWNER APPROVED WITH OBLIGATIONS**

Holdout V4 redistributes 12 pinned third-party technical documents under `evaluation/holdout_v4/sources/`. These files are benchmark corpus artifacts, not RALG-owned source code, and they remain governed by their respective upstream licenses. The RALG source-available product license does not replace or override those upstream terms.

The authoritative provenance, resolved commit SHA, canonical URL, raw/normalized SHA-256 values, and acquisition timestamp for every document are recorded in `sources_manifest.jsonl`. The licensing evidence and approval record are in `LICENSE_REVIEW_EVIDENCE.md` and `LICENSE_REDISTRIBUTION_REVIEW.md`.

## Normalization disclosure

Every normalized V4 source is a deterministic mechanical transformation of its pinned raw source: UTF-8 decoding, CRLF/CR conversion to LF, and exactly one terminal newline if absent. No substantive wording is intentionally edited. Where an upstream license requires modification/change disclosure, this paragraph is the V4 change notice. Raw copies are retained alongside normalized copies so the exact acquired source remains available.

## Source-specific notices

### 1. Git — gitattributes documentation

- V4 ID: `v4_git_gitattributes`
- Upstream: `git/git`
- Pinned commit: `c73e85354c275c9d409b26445089bc16940fc527`
- Selected file: `Documentation/gitattributes.adoc`
- License basis: GNU GPL version 2 (`GPL-2.0-only` project basis unless a file-specific exception applies)
- Compliance: preserve applicable GPLv2 license/copyright information and source availability for redistributed source-form material.

### 2. Linux — Control Group v2 documentation

- V4 ID: `v4_linux_cgroup_v2`
- Upstream: `torvalds/linux`
- Pinned commit: `cee9395acd8043be0644b25c34bfa86623f2b935`
- Selected file: `Documentation/admin-guide/cgroup-v2.rst`
- License basis: Linux kernel GPL-2.0 baseline; no separate SPDX expression was identified in the selected RST header during review.
- Compliance: preserve applicable GPLv2 licensing/copyright information and source availability.

### 3. Docker Docs — Dockerfile concepts

- V4 ID: `v4_docker_dockerfile`
- Upstream: `docker/docs`
- Pinned commit: `dbad77a00e8352f30e663bec3eeae9fb31a19b4e`
- Selected file: `content/manuals/build/concepts/dockerfile.md`
- License basis: Apache License 2.0
- Compliance: preserve the Apache-2.0 license and attribution requirements; normalization is disclosed above. No root NOTICE file was identified at the reviewed pinned repository state.

### 4. Prometheus — configuration reference

- V4 ID: `v4_prometheus_config`
- Upstream: `prometheus/prometheus`
- Pinned commit: `09fdfcd2659dd9c816e9e23c992fc161c0091757`
- Selected file: `docs/configuration/configuration.md`
- License basis: Apache License 2.0
- Compliance: preserve the Apache-2.0 license and applicable upstream NOTICE material. Literal examples inside the documentation, including example credentials, are upstream text and are not RALG secrets.

### 5. GitHub Docs — workflow syntax

- V4 ID: `v4_github_actions_workflow`
- Upstream: `github/docs`
- Pinned commit: `5e0cd6082684634c7cb7852b99db179eb34313c3`
- Selected file: `content/actions/reference/workflows-and-actions/workflow-syntax.md`
- License basis: Creative Commons Attribution 4.0 International (`CC-BY-4.0`)
- Compliance: provide attribution, identify the license, retain a source link where practicable, and indicate the deterministic normalization described above. No endorsement by GitHub is implied.

### 6. Ansible Documentation — playbook guide

- V4 ID: `v4_ansible_playbooks`
- Upstream: `ansible/ansible-documentation`
- Pinned commit: `c77ebb1b61c1b9f95d4fcc73400013c1ddadaf03`
- Selected file: `docs/docsite/rst/playbook_guide/playbooks_intro.rst`
- License basis: GNU GPL version 3
- Compliance: preserve GPLv3 licensing/copyright information and applicable source-availability obligations.

### 7. curl — retry option documentation

- V4 ID: `v4_curl_retries`
- Upstream: `curl/curl`
- Pinned commit: `f190aa8ecea728e6ce7fb7a6250e03df4d4eaca5`
- Selected file: `docs/cmdline-opts/retry.md`
- License basis: curl permissive license
- Compliance: preserve the upstream copyright and permission notice in redistributed copies; do not use copyright-holder names for promotion without permission.

### 8. RabbitMQ — queue management tools

- V4 ID: `v4_rabbitmq_queues`
- Upstream: `rabbitmq/rabbitmq-server`
- Pinned commit: `6108dea0c7564e2b0291d2b9b6a897288bb5e9c0`
- Selected file: `deps/rabbit/docs/rabbitmq-queues.8`
- License basis: Mozilla Public License 2.0 (`MPL-2.0`) stated for the selected file; Broadcom copyright notice applies.
- Compliance: retain MPL-2.0 and copyright notices and satisfy applicable Source Code Form obligations for the normalized modified copy.

### 9. Grafana — alerting documentation

- V4 ID: `v4_grafana_alerting`
- Upstream: `grafana/grafana`
- Pinned commit: `43ebb8bb3119a0ab46843d833024bc4d02043b39`
- Selected file: `docs/sources/alerting/fundamentals/alert-rules/_index.md`
- License basis used for this review: GNU Affero General Public License version 3 (`AGPL-3.0` repository basis; no selected-file alternative was identified)
- Compliance: preserve applicable AGPL licensing/source obligations and keep this corpus artifact separately identified as third-party material. Re-check with qualified counsel before material public commercial redistribution.

### 10. CPython — Logging HOWTO

- V4 ID: `v4_python_logging`
- Upstream: `python/cpython`
- Pinned commit: `686b543e1ea13f0161dc46da59770be283c3b54c`
- Selected file: `Doc/howto/logging.rst`
- License basis: Python Software Foundation License Version 2; applicable documentation code examples/recipes from the relevant Python era are additionally available under 0BSD.
- Compliance: preserve PSF copyright/license information and the normalization/change disclosure above.

### 11. Node.js — stream documentation

- V4 ID: `v4_node_streams`
- Upstream: `nodejs/node`
- Pinned commit: `f2c515510d1fdef96b48d11341e63aa1fafbd033`
- Selected file: `doc/api/stream.md`
- License basis: MIT-style Node.js license for repository-owned software and associated documentation
- Compliance: preserve the copyright and permission notice in copies or substantial portions.

### 12. The Rust Programming Language Book — ownership chapter

- V4 ID: `v4_rust_ownership`
- Upstream: `rust-lang/book`
- Pinned commit: `917544888a55e4da7109bdba8c88c893c0da70f4`
- Selected file: `src/ch04-01-what-is-ownership.md`
- License basis: MIT OR Apache-2.0; the V4 compliance decision selects the MIT option.
- Compliance: preserve the Rust Project copyright and MIT permission notice.

## Distribution boundary

The descriptions above are an engineering compliance record, not a substitute for the complete controlling upstream license texts. Any distribution bundle containing the V4 source corpus must retain the applicable complete upstream license text, copyright/permission notices, NOTICE material where required, source availability obligations where applicable, attribution, and the normalization/change disclosure. Upstream terms control if this summary differs from them.

Project-owner approval was recorded on 2026-08-31 as `APPROVED_WITH_OBLIGATIONS`. Independent legal counsel and third-party legal review were not performed.