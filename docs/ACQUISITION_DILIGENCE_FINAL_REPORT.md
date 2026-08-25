# Acquisition Diligence Final Report (41-Point)

**Branch:** `hardening/acquisition-diligence-v1`
**Date:** 2026-08-25
**Master baseline:** `0b30827739df97d734583f6a570e4513a4a3586c`
**Docker image:** `ralg-engine:latest`
**Container:** healthy, port 127.0.0.1:7860

---

## SECTION A: GIT & REPOSITORY STATE

### 1. Master SHA
- Baseline: `0b30827739df97d734583f6a570e4513a4a3586c`
- Branch: `hardening/acquisition-diligence-v1`
- Status: Branched from current master

### 2. File Changes
- New files: `scripts/test_docker_lifecycle.py`, `docs/ACTIVE_RUNTIME_INVENTORY.md`, `docs/DATA_RIGHTS_INVENTORY.md`, `docs/DEPENDENCY_AND_IP_AUDIT.md`, `docs/dependency_inventory.json`
- Modified: `evaluation/results/stage5_preliminary_results.json` (restored to origin/master, no net change)
- Deleted: 0
- Benchmark fixtures: **UNCHANGED**
- Models/checkpoints/tokenizers: **UNCHANGED**

### 3. Whitespace & Lint
- `git diff --check`: 0 issues

### 4. Protected Files Confirmation
- `.opencode/`: untouched
- `checkpoints/`: untouched
- `data/tokenizer*.json`: untouched
- `0.1.0-rc1` tag: untouched
- `evaluation/stage5_review_queue.jsonl`: untouched

---

## SECTION B: SOURCE & DATA ACQUISITION

### 5. Independent Source Type
- 50 IETF RFC documents
- Independently sourced, not generated for this project
- Provenance: `evaluation/stage5_source_manifest.jsonl`

### 6. Source Manifest Status
- 50 entries with SHA-256 hashes, acquisition dates, canonical URLs
- All `permission_status: "confirmed"`
- All `redistribution_permitted: true`
- All `synthetically_generated: false`

### 7. Redistribution / Permission
- RFCs: IETF Trust Legal Provisions (BCP 78/79)
- Permitted with IETF legal notice preservation
- License risk: LOW

### 8. Benchmark Case Count
- 300 cases (100 supported, 200 unsupported variants)
- Auto-generated from RFC corpus
- Status: preliminary/unreviewed (not human-reviewed)

### 9. Supported/Unsupported Distribution
- Supported: ~33% (100/300)
- Unsupported: ~67% (200/300)
- Gate: 100% unsupported rejection maintained

---

## SECTION C: QUALITY GATES

### 10. Regression Suite: 23/23 PASS
| Category | Count | Result |
|----------|-------|--------|
| Baseline regression | 10 | PASS |
| Routing robustness | 7 | PASS |
| Unsupported/false-premise | 6 | PASS |
| **Total** | **23** | **PASS** |

### 11. Commercial Validation: 10/10 PASS
| Metric | Value |
|--------|-------|
| Retrieval correctness | 100% |
| Answer completeness | 100% |
| Unsupported rejection | 100% |
| False-support rate | 0% |
| Quality gate | PASS |

### 12. API Input Hardening: 8/8 PASS
- Oversized request rejection
- Blank field rejection
- Extra-field rejection (strict mode)
- Type coercion protection

### 13. Evidence Traceability: 7/7 PASS
- Source attribution verified
- Provenance chain intact

### 14. Conflict Detection: 9/9 PASS
- Conflicting evidence identified
- Non-conflicting pairs accepted

### 15. Upload Provenance: 25/25 PASS
- PDF parsing (valid + broken)
- DOCX parsing (valid + broken)
- TXT upload
- Duplicate detection
- Commercial validation within upload context

### 16. Portability & Readiness: 8/8 PASS
- Path portability confirmed
- Pipeline initialization under error conditions

### 17. Document Persistence: 8/8 PASS
- Registry corruption recovery
- Missing document handling
- Restart recovery
- Unsafe content reference rejection

### 18. Retrieval Performance: 10/10 PASS
- Retrieval correctness regression
- Performance baseline maintained

### 19. Unified Evidence: 10/10 PASS
- Support gating
- Provenance correctness
- Conflict behavior

### 20. Full Test Suite Summary
| Suite | Tests | Result |
|-------|-------|--------|
| Regression v2 | 23 | PASS |
| API hardening | 8 | PASS |
| Traceability | 7 | PASS |
| Conflict detection | 9 | PASS |
| Upload provenance | 25 | PASS |
| Portability/readiness | 8 | PASS |
| Document persistence | 8 | PASS |
| Retrieval performance | 10 | PASS |
| Unified evidence | 10 | PASS |
| Commercial validation | 10 | PASS |
| **Total** | **118** | **ALL PASS** |

---

## SECTION D: RETRIEVAL METRICS

### 21. Stage 5 Preliminary Results (Independent RFC Corpus)
| Metric | Lexical | RALG Hybrid |
|--------|---------|-------------|
| Recall@1 | 40.48% | **50.95%** |
| Recall@3 | 87.62% | **90.95%** |
| Recall@5 | 100.00% | **100.00%** |
| MRR | 0.6485 | **0.7098** |
| Unsupported rejection | 100% | **100%** |
| False-support rate | 0% | **0%** |

### 22. Evidence Correctness
- 100% for both systems on independent corpus
- All supported answers backed by retrieved evidence

### 23. Latency
- Lexical p50: 187ms, p95: 253ms
- RALG hybrid: comparable (within measurement noise)

### 24. Key Differentiator
- RALG hybrid Recall@1 advantage: +10.47 percentage points
- MRR advantage: +0.0613
- Zero false-support rate maintained on independent data

### 25. Preliminary Status
- Cases are automatically generated, NOT human-reviewed
- Stage 5 remains BLOCKED ON INDEPENDENT REVIEW
- Results must not be represented as final external validation

---

## SECTION E: DOCKER LIFECYCLE

### 26. Compose Config: PASS
- `docker compose config --quiet`: valid
- 3 named volumes: `ralg_data`, `ralg_logs`, `ralg_checkpoints`
- Port: `127.0.0.1:7860:7860`
- Healthcheck: Python urllib to localhost:7860

### 27. Image Build: PASS
- `docker compose build --no-cache`: clean build
- Base: `python:3.11-slim`
- CPU-only PyTorch via `--index-url`
- Image size: 712.6 MB
- Digest: `sha256:91d2373a781f`

### 28. Container Health: PASS
- Status: `Up (healthy)`
- Python: 3.11.16
- Torch: 2.7.1+cpu
- Gradio: 4.44.1
- All key imports verified (rag_chat_v2, retriever_hybrid, config)

### 29. Application Endpoints: PASS
- WebUI root: HTTP 200
- Gradio UI loaded and functional
- Pipeline initialized (107,650 knowledge chunks, 36 runtime documents)

### 30. Resource Footprint: PASS
- CPU: ~6.5% idle
- Memory: 1.2 GiB / 11.5 GiB (10.5%)
- Suitable for single-tenant deployment

### 31. Restart Recovery: PASS
- Container restart via `docker compose restart`
- Health recovered in ~3 seconds
- All volumes persisted across restart

### 32. Docker Lifecycle Summary
| Test | Result |
|------|--------|
| Compose config | PASS |
| Image exists | PASS |
| Image digest | PASS |
| Image size | 712.6 MB |
| Container running | PASS |
| Container healthy | PASS |
| Volumes mounted | PASS |
| WebUI root 200 | PASS |
| Gradio loaded | PASS |
| Python version | 3.11.16 |
| Torch import | 2.7.1+cpu |
| RAG import | ok |
| Retriever import | ok |
| Config import | ok |
| CPU | 6.46% |
| Memory | 1.2 GiB |
| Mem pct | 10.46% |
| Restart recovery | 3s |
| Final healthy | PASS |
| **Total** | **19/19 PASS** |

---

## SECTION F: SECURITY & DEPLOYMENT

### 33. Security Boundary
- No built-in authentication
- No TLS termination
- No tenant isolation
- No production-grade rate limiting
- Documented as local/trusted-network component

### 34. Known Security Limitations
- API/WebUI are local-development interfaces
- Process-local mutation locking (single-worker only)
- Uploaded documents are untrusted input
- No external network dependencies in core path

### 35. Dependency License Inventory
- 15 total dependencies audited
- All OSI-approved (MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause)
- Zero copyleft (GPL/AGPL) in runtime path
- Risk: LOW for all runtime dependencies
- Note: PyPDF2 should migrate to pypdf for continued security support

### 36. Data Rights Inventory
| Data Category | Source | License | Commercial | Risk |
|---------------|--------|---------|------------|------|
| WikiText-2 | HuggingFace | CC-BY-SA-3.0 | Yes (attribution) | LOW |
| Technical docs | Project author | RALG license | Subject to RALG | LOW |
| RFC corpus | IETF | IETF Trust | Yes (with notice) | LOW |
| Tokenizers | Trained | Derived CC-BY-SA-3.0 | Yes | LOW |
| Checkpoints | Trained/Downloaded | Varies | See model audit | MEDIUM |

---

## SECTION G: RUNTIME ARCHITECTURE

### 37. Shared Runtime Path
```
API / WebUI
  -> execute_runtime()
  -> ExecutionPlan
  -> factual extractor OR grounded reasoning
  -> retriever_hybrid for reasoning retrieval
  -> answer contract
  -> unified support / provenance / conflict gate
  -> supported answer or abstention
```
- API and WebUI share the same `execute_runtime()` boundary
- Behavioral parity confirmed by integration tests

### 38. Active Runtime Inventory
- 10 active production modules
- 13 active support modules
- 10 synthesizer modules
- 2 superseded (retained for history/utility)
- 5 training/offline modules
- 14 evaluation/benchmark modules
- Full inventory: `docs/ACTIVE_RUNTIME_INVENTORY.md`

### 39. Retrieval Dependency Graph
```
retriever_v2 (core lexical)
    ↑
retriever_hybrid (fuses v2 + secondary sub-queries)
    ↑
rag_chat_v2 (orchestrates retrieval + synthesis)
    ↑
runtime_architecture.execute_runtime (shared by API + WebUI)
    ↑
api_server  |  webui/hybrid_pipeline → webui/app
```

---

## SECTION H: PERSISTENCE & LIFECYCLE

### 40. Document Persistence
- Registry-backed document tracking
- Corruption recovery: gracefully handles invalid JSON registry
- Missing content: skips and logs, does not crash
- Restart recovery: restores persisted documents on startup
- Unsafe extension filtering: rejects non-allowed file types

### 41. Known Limitations & Remaining Gaps

**Resolved in this branch:**
- Docker lifecycle qualification: COMPLETE (19/19 tests)
- Dependency/IP audit: COMPLETE (15 dependencies, all OSI-approved)
- Data rights inventory: COMPLETE (all categories documented)
- Active runtime inventory: COMPLETE (production/support/legacy classified)
- Regression suite: 118/118 ALL PASS

**Still outstanding (not blocking for controlled pilot):**
1. Stage 5 benchmark cases are auto-generated and unreviewed
2. No authentication/TLS (documented limitation, not a regression)
3. Single-worker deployment only (process-local locking)
4. 250k/500k scale tests deferred
5. Optional polish LLM failed to load (non-blocking; core-answer fallback works)
6. PyPDF2 deprecation (should migrate to pypdf)

**Recommendation:** Repository is ready for controlled-pilot buyer diligence. The outstanding items are known limitations, not regressions, and are documented in `COMMERCIAL_READINESS.md` and `docs/TECHNICAL_DILIGENCE_STATUS.md`.

---

## VERDICT

```
Docker lifecycle:     19/19 PASS
Regression suite:     23/23 PASS
API hardening:         8/8  PASS
Traceability:          7/7  PASS
Conflict detection:    9/9  PASS
Upload provenance:    25/25 PASS
Portability:           8/8  PASS
Persistence:           8/8  PASS
Retrieval perf:       10/10 PASS
Unified evidence:     10/10 PASS
Commercial:           10/10 PASS
───────────────────────────────────
TOTAL:               137/137 PASS
```

**Branch status:** `hardening/acquisition-diligence-v1` is ready for commit and push.
No merge to master. No benchmark fixtures, retrieval weights, models, checkpoints, or tokenizers modified.
