# Holdout V4 Source License Review Evidence

Status: **PROJECT-OWNER REVIEW COMPLETE — APPROVED WITH PRESERVATION OBLIGATIONS**

This record supports the Holdout V4 pre-freeze licensing gate. Machine-verified evidence was prepared first, then the RALG project owner explicitly reviewed the 12-source licensing summary and approved use of the selected sources on 2026-08-31 subject to preserving the identified license, notice, attribution, source-availability, and change-disclosure obligations.

This approval is a project compliance decision. It is **not** independent legal advice, independent legal counsel, or third-party legal review.

The evidence below was checked against the exact upstream commit pinned by the V4 acquisition manifest.

| document_id | pinned upstream commit | verified license basis | redistribution/compliance note | project-owner decision |
| --- | --- | --- | --- | --- |
| `v4_git_gitattributes` | `c73e85354c275c9d409b26445089bc16940fc527` | Git `COPYING`: GNU GPL version 2 applies to the project. | Redistribution is permitted subject to GPL-2.0 terms; retain the applicable license/copyright notices. | `APPROVED` |
| `v4_linux_cgroup_v2` | `cee9395acd8043be0644b25c34bfa86623f2b935` | Linux licensing rules state the kernel source as a whole is GPL-2.0 unless an individual file carries a compatible different SPDX expression. | Preserve the source and applicable GPL-2.0 licensing information when redistributing the frozen document. | `APPROVED` |
| `v4_docker_dockerfile` | `dbad77a00e8352f30e663bec3eeae9fb31a19b4e` | Repository `LICENSE`: Apache License 2.0. | Preserve Apache-2.0 license/attribution and identify normalization as a mechanical modification. | `APPROVED` |
| `v4_prometheus_config` | `09fdfcd2659dd9c816e9e23c992fc161c0091757` | Repository `LICENSE`: Apache License 2.0; repository NOTICE exists. | Preserve Apache-2.0 license and applicable NOTICE material. | `APPROVED` |
| `v4_github_actions_workflow` | `5e0cd6082684634c7cb7852b99db179eb34313c3` | Repository `LICENSE`: Creative Commons Attribution 4.0 International. | Preserve attribution, license reference, source link where practicable, and modification indication. | `APPROVED` |
| `v4_ansible_playbooks` | `c77ebb1b61c1b9f95d4fcc73400013c1ddadaf03` | Repository `COPYING`: GNU GPL version 3. | Preserve GPLv3 licensing/notices and applicable source-availability obligations. | `APPROVED` |
| `v4_curl_retries` | `f190aa8ecea728e6ce7fb7a6250e03df4d4eaca5` | Repository `COPYING`: curl permissive license. | Preserve copyright and permission notice; do not use holder names for promotion without permission. | `APPROVED` |
| `v4_rabbitmq_queues` | `6108dea0c7564e2b0291d2b9b6a897288bb5e9c0` | Selected file carries MPL-2.0 basis and Broadcom copyright notice. | Preserve MPL notice/copyright and applicable source-form obligations for the modified normalized copy. | `APPROVED` |
| `v4_grafana_alerting` | `43ebb8bb3119a0ab46843d833024bc4d02043b39` | Repository `LICENSE`: GNU Affero General Public License version 3. | Preserve AGPLv3 license/source obligations and keep the corpus clearly separated as third-party material; commercial redistribution should receive legal diligence. | `APPROVED` |
| `v4_python_logging` | `686b543e1ea13f0161dc46da59770be283c3b54c` | CPython `LICENSE`: PSF License Version 2 for software/docs; applicable documentation code examples are additionally available under 0BSD. | Preserve PSF licensing/copyright and record deterministic normalization as a change. | `APPROVED` |
| `v4_node_streams` | `f2c515510d1fdef96b48d11341e63aa1fafbd033` | Node.js `LICENSE`: MIT-style license for Node-owned software and associated documentation. | Preserve copyright and permission notice in copies or substantial portions. | `APPROVED` |
| `v4_rust_ownership` | `917544888a55e4da7109bdba8c88c893c0da70f4` | Rust Book repository contains both `LICENSE-MIT` and `LICENSE-APACHE`; MIT option selected for V4. | Preserve Rust Project copyright and MIT permission notice. | `APPROVED` |

## Approval record

- Decision: `APPROVED_WITH_OBLIGATIONS`
- Approval date: `2026-08-31`
- Approver role: RALG project owner
- Independent legal counsel: `NO`
- Third-party reviewer: `NO`
- Manifest action: all 12 `license_review_status` values may be recorded as `APPROVED`
- Required follow-up: retain the V4 third-party notices/compliance record and all source-specific obligations through freeze and any redistribution

The corresponding `sources_manifest.jsonl` approval values record this project-owner decision. They do not claim independent external legal review.

## Claim boundary

This is an engineering/compliance evidence record for the benchmark freeze process, not legal advice. Upstream license texts and notices remain controlling. `LICENSE_REDISTRIBUTION_REVIEW.md`, the pinned source manifest, and the V4 third-party notices/compliance artifact together define the pre-freeze compliance record.