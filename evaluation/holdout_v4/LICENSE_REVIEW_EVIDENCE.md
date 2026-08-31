# Holdout V4 Source License Review Evidence

Status: **MACHINE-VERIFIED EVIDENCE COMPLETE; HUMAN SIGN-OFF REQUIRED**

This record supports the Holdout V4 pre-freeze licensing gate. It does not auto-approve any source. Per the V4 protocol, `sources_manifest.jsonl` must remain `PENDING_HUMAN_REVIEW` until a real human reviewer explicitly approves each source.

The evidence below was checked against the exact upstream commit pinned by the V4 acquisition manifest.

| document_id | pinned upstream commit | verified license basis | redistribution/compliance note | human decision |
| --- | --- | --- | --- | --- |
| `v4_git_gitattributes` | `c73e85354c275c9d409b26445089bc16940fc527` | Git `COPYING`: GNU GPL version 2 applies to the project. | Redistribution is permitted subject to GPL-2.0 terms; retain the applicable license/copyright notices. | `PENDING` |
| `v4_linux_cgroup_v2` | `cee9395acd8043be0644b25c34bfa86623f2b935` | Linux licensing rules state the kernel source as a whole is GPL-2.0 unless an individual file carries a compatible different SPDX expression. | Preserve the source and applicable GPL-2.0 licensing information when redistributing the frozen document. | `PENDING` |
| `v4_docker_dockerfile` | `dbad77a00e8352f30e663bec3eeae9fb31a19b4e` | Repository `LICENSE`: Apache License 2.0. | Apache-2.0 permits reproduction/distribution subject to license, attribution/notice, and modification-marking requirements. | `PENDING` |
| `v4_prometheus_config` | `09fdfcd2659dd9c816e9e23c992fc161c0091757` | Repository `LICENSE`: Apache License 2.0. | Preserve Apache-2.0 license and applicable notices when redistributing. | `PENDING` |
| `v4_github_actions_workflow` | `5e0cd6082684634c7cb7852b99db179eb34313c3` | Repository `LICENSE`: Creative Commons Attribution 4.0 International. | Redistribution/adaptation is permitted with attribution, license reference, source link when practicable, and modification indication. | `PENDING` |
| `v4_ansible_playbooks` | `c77ebb1b61c1b9f95d4fcc73400013c1ddadaf03` | Repository `COPYING`: GNU GPL version 3. | Redistribution is permitted subject to GPLv3 requirements; retain the license/copyright notices. | `PENDING` |
| `v4_curl_retries` | `f190aa8ecea728e6ce7fb7a6250e03df4d4eaca5` | Repository `COPYING`: curl permissive license. | Use/copy/modify/distribute is permitted provided the copyright and permission notice appear in copies; do not use copyright-holder names for promotion without permission. | `PENDING` |
| `v4_rabbitmq_queues` | `6108dea0c7564e2b0291d2b9b6a897288bb5e9c0` | Repository `LICENSE`: RabbitMQ Server and tier-1/core plugins are MPL 2.0; selected file also carries the MPL-2.0 basis recorded in `source_specs.json`. | Redistribution is permitted subject to MPL-2.0 notice/source-form obligations applicable to the file. | `PENDING` |
| `v4_grafana_alerting` | `43ebb8bb3119a0ab46843d833024bc4d02043b39` | Repository `LICENSE`: GNU Affero General Public License version 3. | Preserve AGPLv3 licensing/copyright information when redistributing this repository documentation source. | `PENDING` |
| `v4_python_logging` | `686b543e1ea13f0161dc46da59770be283c3b54c` | CPython `LICENSE`: Python software and documentation are licensed under PSF License Version 2; documentation code examples from Python 3.8.6 onward are additionally dual-licensed under 0BSD. | Preserve the PSF license and copyright notice; if benchmark material reproduces code examples, retain the applicable PSF/0BSD basis. | `PENDING` |
| `v4_node_streams` | `f2c515510d1fdef96b48d11341e63aa1fafbd033` | Node.js `LICENSE`: MIT-style license applies to Node.js parts not identified as externally maintained libraries. | Preserve the copyright and permission notice in copies or substantial portions. | `PENDING` |
| `v4_rust_ownership` | `917544888a55e4da7109bdba8c88c893c0da70f4` | The Rust Book repository contains both `LICENSE-MIT` and `LICENSE-APACHE`, matching the selected source specification `MIT OR Apache-2.0`. | Redistribution is permitted under the selected applicable license; preserve the corresponding notices/terms. | `PENDING` |

## Reviewer instructions

A human reviewer must inspect this evidence and the selected source/license files, then make a real decision for every row. If approved, update the corresponding `license_review_status` in the generated `sources_manifest.jsonl` from `PENDING_HUMAN_REVIEW` to `APPROVED`. Do not use a script or model to manufacture that decision.

The strict pre-freeze validator intentionally fails any source whose `license_review_status` is not exactly `APPROVED`.

## Claim boundary

This is an engineering/compliance evidence record for the benchmark freeze process, not legal advice. It records the upstream license basis and principal redistribution conditions relevant to retaining the 12 documents as benchmark artifacts.