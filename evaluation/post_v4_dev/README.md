# RALG Engine Post-V4 Development Diagnostic Suite

## Overview

This directory contains a fresh set of 55 synthetic diagnostic cases for the RALG Engine post-V4 remediation. These cases are designed to independently exercise architectural failure classes without using any V4 source documents or adapting V4 cases.

**Total cases:** 55
**Categories:** 11 (5 cases each)
**Directory:** evaluation/post_v4_dev/

## Categories

| Category | Code | Description |
|----------|------|-------------|
| A | Direct supported factual | Direct factual questions with supported answers |
| B | Paraphrased supported | Paraphrased variants of factual questions |
| C | Procedural | Procedural/step-by-step questions |
| D | Causal/explanation | Causal relationship questions |
| E | Cross-document synthesis | Questions requiring synthesis across documents |
| F | Document-scoped retrieval | Retrieval scoped to specific document IDs |
| G | Conflicting evidence/version distinction | Questions with conflicting evidence across versions |
| H | Conditional/qualified statements | "If X then Y" type questions |
| I | Unsupported question rejection | Questions that should be rejected as unsupported |
| J | False-premise rejection | Questions based on false premises |
| K | Misleading lexical-overlap rejection | Questions where keyword overlap is misleading |

## Case Structure

Each case in `dev_cases.jsonl` contains:
- `case_id`: Stable identifier (e.g., `post_v4_dev_001`)
- `category`: One of the 11 categories above
- `question`: The diagnostic question
- `expected_behavior`: Whether the expected outcome is `supported` or `unsupported`
- `answer`: The expected answer (if supported)
- `answer_type`: The type of answer (factual, procedural, causal, etc.)
- `expected_documents`: Document(s) expected to provide the answer
- `retrieval_check`: Deterministic check description for validation

## Documents

The suite uses 5 fictional but internally consistent documentation sources:
- `pump_controller_manual.txt` - Industrial pump controller operation
- `conveyor_controller_manual.txt` - Warehouse conveyor controller operation
- `hvac_controller_manual.txt` - HVAC maintenance controller operation
- `battery_monitor_manual.txt` - Battery monitoring unit operation
- `machine_safety_procedures.txt` - General machine safety procedures

All documents are located in `evaluation/post_v4_dev/docs/`.

## Running the Diagnostic

See `run_diagnostic.py` for the diagnostic runner that:
1. Loads ONLY the fresh post_v4_dev docs
2. Exercises the real production runtime
3. Never imports or reads Holdout V4
4. Records results for every case including case_id, class, supported, answer, answer_type, retrieved document IDs, source/evidence output, latency, and runtime error if any

## Validation

Before running, validate:
- Exactly 55 cases
- Exactly 5 per category
- Unique case IDs
- All referenced dev documents exist
- No path references evaluation/holdout_v4
- No V4 source/domain names in the new corpus/cases