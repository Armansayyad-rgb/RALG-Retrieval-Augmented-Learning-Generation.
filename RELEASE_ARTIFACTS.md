# Release Artifacts

Historical release identity: **Prototype 1 RC1 (`0.1.0-rc1`)**. Current release preparation must distinguish runtime requirements from redistribution clearance.

| Artifact | Runtime / repository role | Distribution classification |
|---|---|---|
| `data/tokenizer_v2.json` | Active tokenizer artifact | Project-generated; upstream-data license review required before commercial redistribution |
| `checkpoints/v2/reasoning_model_v1.pt` | Optional/local model-backed answer artifact; not tracked in Git | **PROVENANCE INCOMPLETE — EXCLUDE FROM COMMERCIAL DISTRIBUTION** until training lineage is reconstructed |
| `data/wikitext_v2.txt` | Tracked knowledge/training artifact | Third-party CC BY-SA material; exact license version must be verified and obligations preserved |
| `data/knowledge_extra_v1.txt` | Project-authored tracked knowledge artifact | Governed by repository license |
| `data/train.txt` | Historical training/development material; not required by active production runtime | **PROVENANCE INCOMPLETE — EXCLUDE FROM COMMERCIAL DISTRIBUTION** |
| `data/runtime_uploads/` | Generated runtime persistence | User-provided runtime data; not a release input and not redistributed by default |
| `logs/` | Generated operational/validation output | Generated/local; not a release input |

## Release-package rule

A commercial, diligence, or transaction package must not assume that every tracked or locally available artifact is cleared for redistribution. The release manifest must explicitly exclude unresolved assets and preserve all required third-party notices.

Canonical provenance controls:

- `docs/IP_PROVENANCE_AND_RELEASE_BOUNDARIES.md`
- `docs/DATA_RIGHTS_INVENTORY.md`
- `THIRD_PARTY_NOTICES.md`

Frozen Holdout V1/V2/V3 artifacts are evidence records and must not be modified, rerun, or reformatted to improve presentation during release preparation.

The supported deployment target is Python 3.11. Dependency reproducibility for the current deployment profile is defined by `requirements.lock.txt`; developer installation remains documented separately in the repository setup instructions.
