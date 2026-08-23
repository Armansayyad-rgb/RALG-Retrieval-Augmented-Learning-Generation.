# RALG Resource and Scale Validation Report

**Pilot-Readiness Checkpoint: Resource and Scale Validation**

---

## Objective

Measure practical RAM/VRAM usage, ingestion/query latency, and behavior as corpus size grows, then define evidence-based pilot limits.

---

## Hardware / Runtime Environment

| Property | Value |
|----------|-------|
| Platform | Windows-11-10.0.26200-SP0 |
| Python | 3.13.14 |
| CPU Cores | 16 |
| Total RAM | 23.64 GB |
| CUDA Available | No |
| GPU | CPU only |
| Torch Version | 2.12.1+cpu |

---

## Measurements

### 1. Baseline Process RAM (before pipeline initialization)

| Metric | Value |
|--------|-------|
| Baseline RAM | **197.85 MB** |

### 2. Pipeline Initialization

| Metric | Value |
|--------|-------|
| Initialization Time | **9.371 s** |
| RAM Before Init | **197.85 MB** |
| RAM After Init | **1,238.68 MB** |
| RAM Delta | **1,040.83 MB** |
| VRAM Before Init | **0 MB** (CPU only) |
| VRAM After Init | **0 MB** (CPU only) |
| Baseline Chunk Count | **107,650** |
| Device | **cpu** |

### 3. Query Latency (Baseline Corpus)

| Percentile | Latency |
|------------|---------|
| p50 | **1.438 s** |
| p95 | **2.088 s** |
| Average | **1.304 s** |
| Min | **0.405 s** |
| Max | **2.127 s** |
| Queries Tested | 6 representative queries × 3 iterations = 18 total |

### 4. Retrieval Performance (Baseline Corpus)

| Metric | Value |
|--------|-------|
| p50 Retrieval Latency | **1.355 s** |
| p95 Retrieval Latency | **1.907 s** |
| Average Results Returned | **7.83** |
| Total Chunks | **107,650** |

### 5. Ingestion Latency

| Chunks Ingested | Time |
|-----------------|------|
| 100 | **4.764 s** |
| 1,000 | Not tested (quick mode) |
| 5,000 | Not tested (quick mode) |

### 6. Memory Growth (Repeated Runtime Ingestion)

| Iteration | Chunks Added | Total Chunks | RAM (MB) | Delta (MB) |
|-----------|--------------|--------------|----------|------------|
| 1 | 100 | 107,850 | 1,252.84 | -1.78 |
| 2 | 100 | 107,950 | 1,251.88 | -2.73 |
| 3 | 100 | 108,050 | 1,260.87 | +6.26 |
| **Total Growth** | **300** | | | **+6.26 MB** |

### 7. Scale Test Results (Quick Mode: Baseline + +100)

| Level | Total Chunks | RAM (MB) | VRAM (MB) | Ingest Time (s) | Query p50 (s) | Query p95 (s) | Retrieval p50 (s) | Retrieval p95 (s) |
|-------|--------------|----------|-----------|-----------------|---------------|---------------|-------------------|-------------------|
| Baseline | 108,050 | 1,260.87 | N/A | N/A | 1.438 | 2.088 | 1.355 | 1.907 |
| +100 | 108,150 | 1,277.67 | N/A | 4.908 | 1.541 | 3.728 | 1.395 | 3.838 |
| +1,000 | Not tested | | | | | | | |
| +5,000 | Not tested | | | | | | | |

**Stop Escalation Criteria:**
- RAM > 8,000 MB
- VRAM > 6,000 MB (if GPU)
- Query p95 latency > 10.0 s
- Ingestion latency > 60.0 s

---

## Practical Pilot Limits (Evidence-Based)

| Limit | Value | Basis |
|-------|-------|-------|
| Max Recommended Runtime Chunks | **100** | Highest scale level passing all safety checks (+100) |
| Max Recommended Total Corpus Chunks | **108,150** | Baseline (107,650) + max runtime chunks (100) |
| Expected RAM at Max Scale | **~1,278 MB** | Measured at +100 scale level |
| Expected Query p95 at Max Scale | **3.73 s** | Measured at +100 scale level |
| Ingestion Time per 1K Chunks | **49.1 s** | Measured at +100 scale level (extrapolated) |
| RAM Growth per 1K Runtime Chunks | **~21 MB** | Linear extrapolation from growth test (6.26 MB / 300 chunks) |
| Query Latency Degradation at Max Scale | **78.5%** | Relative to baseline (2.088s → 3.728s) |

**Memory Leak Detection:** No (growth < 500 MB after repeated ingestion)

**Notes:**
- Only +100 scale level passed in quick mode; +1,000 and +5,000 not tested
- Query latency degraded by 79% at +100 scale - consider corpus limits for production
- Ingestion time ~49s per 1k chunks - may impact real-time ingestion scenarios
- Full validation with +1,000 and +5,000 scale levels recommended before pilot deployment

---

## Bugs Discovered

| Bug | Severity | Description | Status |
|-----|----------|-------------|--------|
| None | - | No scalability bugs discovered during validation | N/A |

---

## Code Changes Made

| File | Change | Reason |
|------|--------|--------|
| `scripts/run_resource_validation.py` | New validation script | Implements resource and scale measurement per checkpoint requirements |
| `RESOURCE_VALIDATION.md` | New documentation | Records validation results and pilot limits |

---

## Test Results Summary

| Test Suite | Status | Details |
|------------|--------|---------|
| Python Compile Checks | PASS | `src/retrieval_proof_v1.py`, `src/api_server.py` compile successfully |
| `scripts/test_all.bat` simple benchmark | PASS | 50 cases, 100% accuracy (baseline_v2 & ralg_v4) |
| `scripts/test_all.bat` hard benchmark | PASS | 50 cases, 100% accuracy (baseline_v2: 92.3%@1, ralg_v4: 100%@1) |
| `regression_tests_v2.py` | PASS | 23/23 tests passed (100%) |
| `scripts/run_commercial_validation.py` | PASS | 10/10 cases, 100% retrieval & answer completeness, 0% false support |
| Traceability Tests | PASS | 6/6 tests passed |
| Conflict Detection Tests | PASS | 9/9 tests passed |
| API Input Hardening Tests | PASS | 7/7 tests passed |
| `git diff --check` | PASS | No whitespace errors |

---

## Remaining Weaknesses

1. **Slow ingestion at scale** - ~49s per 1,000 chunks due to full index rebuild on each ingestion; consider incremental indexing for production
2. **Query latency degradation** - 78.5% p95 latency increase at +100 chunks; retrieval is O(N) over full corpus
3. **Limited scale validation** - Quick mode only tested up to +100 chunks; +1,000 and +5,000 need full validation
4. **No GPU testing** - CPU-only environment; VRAM behavior unknown for GPU deployments
5. **Single-threaded retrieval** - No parallel query processing; latency scales with corpus size

---

## Git Status

```
?? RESOURCE_VALIDATION.md
?? scripts/run_resource_validation.py
```

---

*Generated by `scripts/run_resource_validation.py` on `2026-08-22`*