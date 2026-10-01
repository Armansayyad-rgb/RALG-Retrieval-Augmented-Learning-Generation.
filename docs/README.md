# Documentation Guide

RALG keeps implementation behavior, demonstration procedure, evidence status, and release diligence in separate documents so they cannot be accidentally conflated.

## Start here

1. [README](../README.md) — product boundary, architecture summary, quick start, and public claim limits.
2. [Current Production Architecture](CURRENT_ARCHITECTURE_STATUS.md) — authoritative runtime architecture and data flow.
3. [Demo Guide](DEMO_GUIDE.md) — reproducible local demonstration and evaluator walkthrough.
4. [Claims / Evidence Matrix](CLAIMS_EVIDENCE_MATRIX.md) — conservative source of truth for what can and cannot be claimed.
5. [Release Readiness](RELEASE_READINESS.md) — consolidated remaining technical, evaluation, security, reproducibility, and IP/data gates.
6. [IP Provenance and Release Boundaries](IP_PROVENANCE_AND_RELEASE_BOUNDARIES.md) — commercial/IP limitations.
7. [Data Rights Inventory](DATA_RIGHTS_INVENTORY.md) — data provenance and rights status.
8. [Third-Party Notices](../THIRD_PARTY_NOTICES.md) — third-party attribution and licensing.

## Evidence rule

When documentation describes a benchmark, always identify its evidence class and preserve its denominator, corpus, methodology, and limitations. Frozen blind results are immutable. Post-freeze engineering fixes require fresh evaluation before a new global correctness claim.

## Current documentation status

The architecture and README were refreshed in PR #104. This documentation follow-up reconciles the demonstration guide with the current optional-checkpoint/readiness behavior and adds a single release-readiness view for technical diligence.
