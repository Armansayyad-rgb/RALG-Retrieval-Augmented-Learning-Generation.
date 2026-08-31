# Holdout V4 Source License / Redistribution Review Evidence

Status: **PROJECT-OWNER APPROVED — COMPLIANCE OBLIGATIONS MUST BE PRESERVED BEFORE V4 FREEZE**

Project-owner approval was explicitly given in the continuation conversation on 2026-08-31 after presentation of the 12-source review evidence. This is a project compliance approval, not independent legal advice or third-party legal review.

The source files below were selected and acquired before question authoring. The review basis is the exact upstream repository state at each V4 pinned commit.

## Review policy

For each source, verify:

1. the selected document exists at the pinned commit;
2. repository- or file-level license text grants redistribution rights;
3. file-level notices do not contradict the repository-level license basis;
4. required notices, attribution, source-license text, or change notices can be preserved in the V4 corpus/repository;
5. the V4 source remains a separately identified third-party corpus artifact and is not relicensed as RALG code.

Deterministic normalization of a source may constitute a modified/derived copy for license-compliance purposes. Where the upstream license requires preservation of notices, attribution, license text, or change notices, the frozen V4 package must retain them in the source manifest and/or a third-party notices artifact.

## Reviewed sources and dispositions

| # | V4 document | Upstream / pinned commit | License basis | Disposition / required preservation |
|---|---|---|---|---|
| 1 | `v4_git_gitattributes` | `git/git@c73e85354c275c9d409b26445089bc16940fc527` | GPL-2.0-only project `COPYING`; no selected-file exception identified | Approved; preserve GPLv2 license/copyright and third-party identity |
| 2 | `v4_linux_cgroup_v2` | `torvalds/linux@cee9395acd8043be0644b25c34bfa86623f2b935` | Kernel GPL-2.0 baseline; no separate SPDX header in selected RST | Approved; preserve GPLv2 license/notices and third-party identity |
| 3 | `v4_docker_dockerfile` | `docker/docs@dbad77a00e8352f30e663bec3eeae9fb31a19b4e` | Apache-2.0 root `LICENSE`; no file exception identified | Approved; preserve Apache-2.0 license/attribution; disclose normalization changes as appropriate |
| 4 | `v4_prometheus_config` | `prometheus/prometheus@09fdfcd2659dd9c816e9e23c992fc161c0091757` | Apache-2.0 root `LICENSE` plus root `NOTICE` | Approved; preserve Apache-2.0 license and applicable NOTICE material |
| 5 | `v4_github_actions_workflow` | `github/docs@5e0cd6082684634c7cb7852b99db179eb34313c3` | CC-BY-4.0 root `LICENSE`; no file exception identified | Approved; attribution, license reference and change indication required; no endorsement implication |
| 6 | `v4_ansible_playbooks` | `ansible/ansible-documentation@c77ebb1b61c1b9f95d4fcc73400013c1ddadaf03` | GPL-3.0 repository `COPYING`; no file exception identified | Approved; preserve GPLv3 license/notices and source availability obligations |
| 7 | `v4_curl_retries` | `curl/curl@f190aa8ecea728e6ce7fb7a6250e03df4d4eaca5` | curl permissive `COPYING` | Approved; preserve copyright and permission notice; no promotional use of holder names |
| 8 | `v4_rabbitmq_queues` | `rabbitmq/rabbitmq-server@6108dea0c7564e2b0291d2b9b6a897288bb5e9c0` | Selected file explicitly MPL-2.0; repository MPL license present | Approved; preserve MPL notice/copyright and MPL requirements for modified Source Code Form |
| 9 | `v4_grafana_alerting` | `grafana/grafana@43ebb8bb3119a0ab46843d833024bc4d02043b39` | AGPL-3.0 root `LICENSE`; no file-specific alternative identified | Approved for V4 benchmark use with separation/notice; preserve AGPL text/source obligations; commercial diligence re-check recommended |
| 10 | `v4_python_logging` | `python/cpython@686b543e1ea13f0161dc46da59770be283c3b54c` | PSF License Version 2 for software/docs; applicable doc code also 0BSD | Approved; preserve PSF license/copyright and record normalization/change summary |
| 11 | `v4_node_streams` | `nodejs/node@f2c515510d1fdef96b48d11341e63aa1fafbd033` | MIT-style Node license for repository-owned software/docs | Approved; preserve copyright and MIT permission notice |
| 12 | `v4_rust_ownership` | `rust-lang/book@917544888a55e4da7109bdba8c88c893c0da70f4` | MIT OR Apache-2.0; MIT option selected for V4 | Approved under MIT option; preserve Rust Project copyright/permission notice |

## Evidence notes

- Git pinned `COPYING` identifies GPL version 2 as the valid project GPL version unless explicitly stated otherwise.
- Linux pinned `COPYING` and `Documentation/process/license-rules.rst` establish the repository GPL-2.0 baseline and file-level SPDX rules. The selected cgroup-v2 RST does not present a separate SPDX expression in its header.
- Docker and Prometheus pinned root licenses contain Apache License 2.0. Docker has no root `NOTICE` at the selected pinned commit; Prometheus does have a root `NOTICE`, which must be carried into the compliance package.
- GitHub Docs pinned root license is CC-BY-4.0.
- Ansible Documentation pinned `COPYING` is GPL version 3.
- curl pinned `COPYING` grants use/copy/modify/distribute rights subject to retaining its copyright and permission notice.
- RabbitMQ selected file itself contains an MPL-2.0 notice and Broadcom copyright notice.
- Grafana pinned root license is AGPL version 3. The selected documentation file has no separate license header identified, so the conservative repository-license basis is used.
- CPython pinned `LICENSE` explicitly says Python software and documentation are under PSF License Version 2 and notes the additional 0BSD option for applicable documentation examples/recipes/code.
- Node pinned `LICENSE` grants MIT-style rights for software and associated documentation files.
- Rust Book pinned repository contains both `LICENSE-MIT` and `LICENSE-APACHE`; MIT is selected as the simpler V4 redistribution option.

## Overall conclusion

All 12 selected V4 sources have an identified redistribution basis at their exact pinned commits. No selected source was found to be proprietary/no-redistribution material. Their upstream licenses do **not** become the RALG product license merely because the files are stored in the same repository. Raw and normalized V4 corpus artifacts remain third-party material under their respective licenses.

Before V4 freeze, the repository must contain a V4 third-party notices/compliance artifact preserving the applicable license texts/notices/attribution/change disclosures, and `sources_manifest.jsonl` must record the completed project-owner review without claiming independent legal review.

## Approval record

- Decision: `APPROVED_WITH_OBLIGATIONS`
- Approval date: `2026-08-31`
- Approver role: RALG project owner
- Approval mechanism: explicit approval in project continuation conversation after review evidence was presented
- Independent legal counsel: `NO`
- Third-party reviewer: `NO`
- Required follow-up: preserve all per-source obligations in the V4 third-party notices/compliance package before artifact freeze
