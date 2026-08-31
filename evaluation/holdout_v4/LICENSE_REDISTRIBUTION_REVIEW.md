# Holdout V4 Source License / Redistribution Review Evidence

Status: **EVIDENCE PREPARED — HUMAN APPROVAL REQUIRED BEFORE V4 FREEZE**

This record supports the Holdout V4 source-license gate. It does not constitute legal advice and it does not fabricate a human reviewer. The source files below were selected and acquired before question authoring. The review basis is the exact upstream repository state at each V4 pinned commit.

## Review policy

For each source, verify:

1. the selected document exists at the pinned commit;
2. repository- or file-level license text grants redistribution rights;
3. file-level notices do not contradict the repository-level license basis;
4. required notices, attribution, source-license text, or change notices can be preserved in the V4 corpus/repository;
5. the V4 source remains a separately identified third-party corpus artifact and is not relicensed as RALG code.

Deterministic normalization of a source may constitute a modified/derived copy for license-compliance purposes. Where the upstream license requires preservation of notices, attribution, license text, or change notices, the frozen V4 package must retain them in the source manifest and/or a third-party notices artifact.

## 1. Git — `v4_git_gitattributes`

- Upstream: `git/git`
- Pinned commit: `c73e85354c275c9d409b26445089bc16940fc527`
- Source: `Documentation/gitattributes.adoc`
- License evidence: pinned `COPYING` states that the valid GPL version for the project is GPL version 2 unless a file explicitly says otherwise, and includes GNU GPL v2.
- File-specific exception found: none identified for the selected documentation file.
- Redistribution basis: GPL-2.0-only project terms.
- V4 obligation: keep the document identified as third-party GPL-2.0-only material; preserve copyright/license information; distribute the applicable GPLv2 text with redistributed copies; do not describe this source as covered by the RALG license.
- Proposed review disposition: **ACCEPTABLE WITH GPL-2.0-ONLY NOTICE PRESERVATION**.

## 2. Linux cgroup v2 — `v4_linux_cgroup_v2`

- Upstream: `torvalds/linux`
- Pinned commit: `cee9395acd8043be0644b25c34bfa86623f2b935`
- Source: `Documentation/admin-guide/cgroup-v2.rst`
- License evidence: pinned kernel `COPYING` states the kernel is provided under GPL-2.0 with the Linux syscall note and refers to the licensing rules. Pinned `Documentation/process/license-rules.rst` states that the `COPYING` license applies to the kernel source as a whole unless an individual file has another compatible license.
- Selected-file header: no separate SPDX identifier is present at the beginning of the selected cgroup-v2 RST file.
- Redistribution basis: repository-wide GPL-2.0 baseline applies absent a file-specific alternative. The syscall exception is not relied upon for redistribution of this documentation artifact.
- V4 obligation: identify as third-party GPL-2.0 material; preserve applicable notices and GPLv2 license text; do not relicense the source under RALG terms.
- Proposed review disposition: **ACCEPTABLE WITH GPL-2.0 NOTICE PRESERVATION**.

## 3. Docker Docs — `v4_docker_dockerfile`

- Upstream: `docker/docs`
- Pinned commit: `dbad77a00e8352f30e663bec3eeae9fb31a19b4e`
- Source: `content/manuals/build/concepts/dockerfile.md`
- License evidence: pinned root `LICENSE` is Apache License 2.0 and explicitly covers source form including documentation source.
- Selected-file exception found: none identified in the source header.
- Pinned root `NOTICE`: not present at this commit.
- Redistribution basis: Apache-2.0.
- V4 obligation: include/preserve Apache-2.0 license and upstream attribution/copyright notices that apply; mark substantive normalization changes if appropriate for the compliance record.
- Proposed review disposition: **ACCEPTABLE WITH APACHE-2.0 NOTICE PRESERVATION**.

## 4. Prometheus — `v4_prometheus_config`

- Upstream: `prometheus/prometheus`
- Pinned commit: `09fdfcd2659dd9c816e9e23c992fc161c0091757`
- Source: `docs/configuration/configuration.md`
- License evidence: pinned root `LICENSE` is Apache License 2.0.
- Selected-file exception found: none identified in the source header.
- Additional notice: pinned root `NOTICE` exists and contains Prometheus copyright/attribution and third-party notices.
- Redistribution basis: Apache-2.0.
- V4 obligation: preserve Apache-2.0 license text and the applicable contents of the upstream `NOTICE`; keep the source identified as Prometheus third-party material.
- Proposed review disposition: **ACCEPTABLE WITH APACHE-2.0 LICENSE + NOTICE PRESERVATION**.

## 5. GitHub Docs — `v4_github_actions_workflow`

- Upstream: `github/docs`
- Pinned commit: `5e0cd6082684634c7cb7852b99db179eb34313c3`
- Source: `content/actions/reference/workflows-and-actions/workflow-syntax.md`
- License evidence: pinned root `LICENSE` contains Creative Commons Attribution 4.0 International (CC-BY-4.0).
- Selected-file exception found: none identified in the selected source header.
- Redistribution basis: CC-BY-4.0 repository documentation license.
- V4 obligation: provide appropriate attribution, identify the CC-BY-4.0 license, provide a license reference/link in the third-party record, and indicate if modifications/normalization were made. Do not imply GitHub endorses RALG.
- Proposed review disposition: **ACCEPTABLE WITH CC-BY-4.0 ATTRIBUTION**.

## 6. Ansible Documentation — `v4_ansible_playbooks`

- Upstream: `ansible/ansible-documentation`
- Pinned commit: `c77ebb1b61c1b9f95d4fcc73400013c1ddadaf03`
- Source: `docs/docsite/rst/playbook_guide/playbooks_intro.rst`
- License evidence: pinned repository `COPYING` contains GNU GPL version 3.
- Selected-file exception found: none identified in the source header.
- Redistribution basis: GPL-3.0 repository terms for this documentation absent a file-specific alternative.
- V4 obligation: keep the source identified as GPL-3.0 third-party material; preserve applicable copyright/license notices; distribute GPLv3 license text with copies; make the corresponding source form available as required; do not relicense under RALG terms.
- Proposed review disposition: **ACCEPTABLE WITH GPL-3.0 NOTICE/SOURCE PRESERVATION**.

## 7. curl — `v4_curl_retries`

- Upstream: `curl/curl`
- Pinned commit: `f190aa8ecea728e6ce7fb7a6250e03df4d4eaca5`
- Source: `docs/cmdline-opts/retry.md`
- License evidence: pinned `COPYING` grants permission to use, copy, modify, and distribute for any purpose, provided the copyright notice and permission notice appear in all copies.
- Redistribution basis: curl license.
- V4 obligation: preserve the upstream copyright and permission notice in redistributed copies/third-party notices; do not use copyright-holder names for promotion without authorization.
- Proposed review disposition: **ACCEPTABLE WITH CURL COPYRIGHT/PERMISSION NOTICE**.

## 8. RabbitMQ — `v4_rabbitmq_queues`

- Upstream: `rabbitmq/rabbitmq-server`
- Pinned commit: `6108dea0c7564e2b0291d2b9b6a897288bb5e9c0`
- Source: `deps/rabbit/docs/rabbitmq-queues.8`
- File-level evidence: the selected file explicitly states that the Source Code Form is subject to Mozilla Public License 2.0 and contains a Broadcom copyright notice.
- Repository evidence: pinned `LICENSE-MPL-RabbitMQ` contains MPL 2.0.
- Redistribution basis: MPL-2.0 at the file level.
- V4 obligation: preserve the MPL notice and copyright notice; provide/access the MPL 2.0 license; keep modifications to the covered file under MPL requirements when distributing a modified Source Code Form; do not relicense this source under RALG terms.
- Proposed review disposition: **ACCEPTABLE WITH MPL-2.0 FILE-LEVEL NOTICE PRESERVATION**.

## 9. Grafana — `v4_grafana_alerting`

- Upstream: `grafana/grafana`
- Pinned commit: `43ebb8bb3119a0ab46843d833024bc4d02043b39`
- Source: `docs/sources/alerting/fundamentals/alert-rules/_index.md`
- License evidence: pinned root `LICENSE` contains GNU Affero General Public License version 3.
- Selected-file exception found: no separate license notice identified in the selected Markdown header.
- Redistribution basis used for V4 review: repository AGPL-3.0 terms in the absence of a file-specific alternative found in the selected file.
- V4 obligation: keep this document as separately identified AGPL-covered third-party source material; preserve applicable notices and AGPL license text; preserve corresponding source availability for redistributed modified source; do not relicense this source under RALG terms.
- Review caution: because this is strong copyleft and the selected file itself has no explicit header, preserve the source as a clearly separated corpus artifact and include the upstream license in the V4 third-party notice package. If public commercial redistribution of the corpus becomes material to a transaction, counsel should re-check this item.
- Proposed review disposition: **ACCEPTABLE FOR V4 BENCHMARK USE WITH AGPL-3.0 SEPARATION/NOTICE; COMMERCIAL DILIGENCE RE-CHECK RECOMMENDED**.

## 10. CPython — `v4_python_logging`

- Upstream: `python/cpython`
- Pinned commit: `686b543e1ea13f0161dc46da59770be283c3b54c`
- Source: `Doc/howto/logging.rst`
- License evidence: pinned root `LICENSE` states that Python software and documentation are licensed under Python Software Foundation License Version 2. It separately states that documentation examples/recipes/code from Python 3.8.6 onward are dual-licensed under PSF-2.0 and Zero-Clause BSD.
- Redistribution basis: PSF License Version 2 for the documentation; embedded documentation code examples may additionally use 0BSD.
- V4 obligation: retain the PSF license agreement and PSF copyright notice; if a derivative version is distributed, include a brief summary of changes as required by the PSF license. Record deterministic normalization as the change in the compliance record.
- Proposed review disposition: **ACCEPTABLE WITH PSF-2.0 NOTICE + CHANGE SUMMARY**.

## 11. Node.js — `v4_node_streams`

- Upstream: `nodejs/node`
- Pinned commit: `f2c515510d1fdef96b48d11341e63aa1fafbd033`
- Source: `doc/api/stream.md`
- License evidence: pinned root `LICENSE` grants MIT-style rights for Node.js software and associated documentation files, subject to retaining the copyright and permission notice in copies or substantial portions.
- Redistribution basis: Node.js MIT license for repository-owned documentation absent a file-specific alternative.
- V4 obligation: preserve the Node.js copyright and MIT permission notice in the third-party notice package/copies. Third-party dependency notices in the root license are not relied upon as licensing for this selected Node-owned documentation file.
- Proposed review disposition: **ACCEPTABLE WITH MIT COPYRIGHT/PERMISSION NOTICE**.

## 12. The Rust Programming Language book — `v4_rust_ownership`

- Upstream: `rust-lang/book`
- Pinned commit: `917544888a55e4da7109bdba8c88c893c0da70f4`
- Source: `src/ch04-01-what-is-ownership.md`
- License evidence: pinned repository contains both `LICENSE-MIT` and `LICENSE-APACHE` (Apache License 2.0). The MIT license expressly includes associated documentation files.
- Redistribution basis selected for V4 simplicity: MIT option.
- V4 obligation: preserve the Rust Project Developers copyright and MIT permission notice in copies/substantial portions; keep third-party identification in the source manifest/notices.
- Proposed review disposition: **ACCEPTABLE UNDER MIT OPTION WITH NOTICE PRESERVATION**.

## Overall evidence conclusion

The 12 selected V4 sources all have an identified redistribution basis at their exact pinned commits. No selected source was found to be proprietary/no-redistribution material. Several licenses impose preservation obligations that must be carried into the frozen V4 package:

- GPL-2.0-only: Git;
- GPL-2.0 baseline: Linux cgroup-v2 documentation;
- Apache-2.0: Docker Docs;
- Apache-2.0 + upstream NOTICE: Prometheus;
- CC-BY-4.0 attribution/change indication: GitHub Docs;
- GPL-3.0: Ansible Documentation;
- curl copyright/permission notice: curl;
- MPL-2.0 file-level notice: RabbitMQ;
- AGPL-3.0: Grafana;
- PSF-2.0 (+ 0BSD for applicable embedded documentation code): CPython;
- MIT: Node.js;
- MIT option selected from MIT/Apache-2.0: Rust Book.

These third-party source licenses do **not** become the RALG product license merely because the files are stored in the same repository. The V4 corpus and its normalized copies must remain clearly identified as third-party artifacts under their own licenses. Copyleft/notice obligations for the copied or modified source documents must still be honored.

## Required human gate before marking manifest entries approved

A human reviewer must confirm all of the following before `license_review_status` is changed from `PENDING_HUMAN_REVIEW`:

- [ ] I reviewed this evidence record and accept the listed license basis for all 12 pinned sources.
- [ ] I approve redistribution of the raw/normalized V4 corpus subject to the listed upstream obligations.
- [ ] I approve adding a V4 third-party notices/license artifact that preserves the required license texts, notices, attribution, and normalization/change disclosures.
- [ ] I understand that this approval is a project compliance decision and is not represented as independent legal counsel.

Human reviewer name: ____________________

Review date (UTC): ____________________

Decision: `APPROVED` / `REJECTED` / `APPROVED_WITH_CHANGES`

Notes: ____________________
