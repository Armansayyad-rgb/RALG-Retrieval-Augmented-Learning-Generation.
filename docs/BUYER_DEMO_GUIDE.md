# Buyer Demo Guide

**Goal:** in ~15 minutes, see RALG Engine do the three things it is built for:
grounded answering with evidence, provenance, and visible abstention on
unsupported questions — using the existing WebUI/API. Nothing here requires
paid APIs, cloud services, or bundled model binaries; the checkpoint bundle
must already be present locally (see Preflight).

---

## 1. Prerequisites (clean Windows machine)

| Requirement | Detail |
|---|---|
| OS | Windows 10/11 (PowerShell 5.1+); Docker Desktop optional |
| Python | 3.11 on PATH, or a prepared `.venv` in the repo root |
| Dependencies | `pip install -r requirements.txt` into `.venv` |
| Model bundle | `checkpoints\v2\reasoning_model_v1.pt`, `checkpoints\embedding_model.pt`, `data\tokenizer_v2.json` present locally |
| Network | localhost only |

The demo never downloads models, mutates real runtime uploads, or sends data
off-machine.

## 2. One-command start

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_buyer_demo.ps1
```

The script runs preflight checks (Python version, required files, checkpoint
paths, optional Docker availability), prints actionable failures, then starts
the Gradio WebUI. It uses port **7860** when free; if that port is occupied,
it automatically selects the first free port in the allowed range
7861-7870 and prints the **actual URL** to use. It never terminates other
processes, and fails clearly if the whole allowed range is busy.

Run only the checks:

```powershell
python scripts\buyer_demo_preflight.py --docker
```

## 3. Demo walkthrough

### Step 1 — Ingest a technical document

Use any technical PDF/TXT you have rights to display (an RFC text file works
well and matches the system's domain). Upload it in the WebUI document panel,
or via API:

```powershell
curl.exe -X POST http://127.0.0.1:8000/ingest `
  -H "Content-Type: application/json" `
  -d "{\"text\": \"<paste document text>\", \"document_name\": \"rfc-demo.txt\"}"
```

Watch: upload succeeds; the document is parsed, chunked, indexed.

### Step 2 — Ask a supported question

Ask something the ingested document answers unambiguously. For example, if
you upload an RFC that defines a protocol's transport ports (e.g. RFC 2131,
DHCP), ask:

> "Which UDP port does a DHCP server listen on for client requests?"

The answer is stated verbatim in the document ("UDP port 67"), so there is a
single defensible reference answer — no version or interpretation ambiguity.

Watch: a direct answer appears **with cited sources**, including the document
you just uploaded.

### Step 3 — Inspect the evidence/provenance trace

Expand the answer's source citations. Each shows the source document, the
supporting excerpt, and provenance metadata. This is the unified support gate:
answers are backed by identifiable evidence spans, not generated from memory.

### Step 4 — Ask an unsupported question

Ask something no ingested document answers:

> "What is the airspeed of an unladen swallow?"

or, staying technical:

> "What warranty period applies to this product?"

### Step 5 — Watch the abstention

Watch: the system visibly refuses to fabricate support. It reports that the
corpus does not contain the answer instead of producing a plausible-sounding
invention. This is the false-support gate measured at 100% unsupported
rejection / 0% false-support rate in Stage 5 (see
`docs/CLAIMS_EVIDENCE_MATRIX.md` for claim status).

### Step 6 — Show the source/evidence trace again

For the supported answer, walk through: question → retrieved evidence →
extractive/grounded answer → support decision. Every accepted answer can be
traced to specific spans in named documents.

### Step 7 — Persistence/restart (where practical)

With Docker running (`docker ps --filter ancestor=ralg-engine:latest`):

```powershell
docker restart <container_name>
# wait for health, reopen http://127.0.0.1:7860
```

The previously ingested document survives the restart (named volumes
`ralg_data` / `ralg_logs` / `ralg_checkpoints`). Without Docker, restart the
WebUI process and re-check the documents list against the local data volume.

## 4. API-only variant

```powershell
uvicorn src.api_server:app --host 127.0.0.1 --port 8000
# endpoints: GET /health, GET /ready, GET /stats, GET /documents, DELETE /documents/{document_id}, POST /ingest, POST /query
```

Same behavior; useful when the buyer wants to script the walkthrough.

## 5. Deterministic buyer-demo scenario

This section describes a reproducible technical proof path a buyer can follow
from a clean state. All commands are documented; no paid APIs, cloud services,
or auto-downloaded models are required. The checkpoint bundle must be present
locally under `checkpoints/v2/` (see Prerequisites). If the checkpoint is absent,
the demo runs in extractive/lookup mode only (no generative polishing).

### Prerequisite: demo knowledge base document

The scenario uses `data/technical_docs_sample.txt` as the ingested technical
document. This file contains 82 lines of SOP-style technical notes across
industrial domains (compressor restart, electrical panel safety, pump troubleshooting,
hydraulic press, conveyor belt, boiler, CNC, forklift battery, air dryer, packaging
machine, cooling tower, welding fume extraction, chemical mixing, emergency shower,
pallet stacker, dust collector, industrial oven, robotic cell, fire pump, generator,
dock door, water treatment, pressure vessel, cleanroom, label printer, network cabinet,
quality gauges, crane pendant, paint booth, refrigeration leak, machine guarding, hot
work permit, confined space, arc flash, lubrication route, steam trap, PLC cooling,
material hoist, torque tool, production line changeover, oil leak). It is included
in the repository and does not require separate rights or downloads.

### Step-by-step walkthrough

#### Step 1 — Start the service

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_buyer_demo.ps1
```

The script runs preflight checks (Python version, required files, checkpoint
availability, bounded port selection), prints actionable failures, then starts
the Gradio WebUI on the selected port (default 7860, or 7861-7870 fallback).
Wait for the WebUI to become available (the launcher includes a readiness probe
with up to 30s timeout).

#### Step 2 — Verify health and readiness

Once the WebUI is open, verify the service is healthy:

- Open `http://127.0.0.1:8000/health` — should return `{"status":"ok"}`
- Open `http://127.0.0.1:8000/ready` — with the model/checkpoint present and initialization healthy it returns `{"ready":true, ...}`; in extractive-only mode without the checkpoint the service still answers but `/ready` may correctly return `503` (full production readiness requires the model)
- Or via curl:
  ```powershell
  curl http://127.0.0.1:8000/health
  curl http://127.0.0.1:8000/ready
  ```

#### Step 3 — Ingest a technical document

Use the included `data/technical_docs_sample.txt` or any technical PDF/TXT you
have rights to. The upload uses the WebUI document panel or the API:

```powershell
curl.exe -X POST http://127.0.0.1:8000/ingest `
  -H "Content-Type: application/json" `
  -d "{\"text\": \"Compressor Restart SOP. Before restarting the compressor after an overheating event, the technician must confirm cooling airflow, inspect the intake filter, check for blocked vents, and wait until the housing temperature returns to the safe operating range. Restart the compressor only after the inspection is complete.\", \"document_name\": \"sop-compressor.txt\""
```

Watch: upload succeeds; the document is parsed, chunked, indexed. The KB table
in the Documents tab should show 1 document with its chunk count.

#### Step 4 — Ask a supported question

Ask a question the ingested document answers unambiguously. For example, after
uploading the SOP above:

> "What must the technician confirm before restarting the compressor after an overheating event?"

The answer is stated verbatim in the document ("confirm cooling airflow"), so
there is a single defensible reference answer — no version or interpretation
ambiguity.

Watch: a direct answer appears **with cited sources**, including the document
you just uploaded. The answer type should be "supported", and the confidence
badge should reflect the system's extractive confidence.

#### Step 5 — Inspect the evidence/provenance trace

Expand the answer's source citations. Each shows the source document, the
supporting excerpt, and provenance metadata. This is the unified support gate:
answers are backed by identifiable evidence spans, not generated from memory.

#### Step 6 — Ask an unsupported question

Ask something no ingested document answers:

> "What is the warranty period for the XYZ compressor?"

or, staying technical:

> "What warranty period applies to this product?"

#### Step 7 — Watch the abstention

Watch: the system visibly refuses to fabricate support. It reports that the
corpus does not contain the answer instead of producing a plausible-sounding
invention. This is the false-support gate: 0% false-support rate in the
development benchmark (see `docs/CLAIMS_EVIDENCE_MATRIX.md` for claim status:
PRELIMINARY for Stage 5 auto-generated cases).

#### Step 8 — Show the source/evidence trace again

For the supported answer walked in Step 4–5, review the full trace: question
→ retrieved evidence → extractive/grounded answer → support decision. Every
accepted answer can be traced to specific spans in named documents.

#### Step 9 — Document-scoped query (if supported)

Try querying with a document scope. After uploading the SOP document, select
that document's ID from the scope dropdown in the WebUI. Ask a question that
could potentially be answered by multiple documents — the system should restrict
evidence to the selected document's scope.

#### Step 10 — Persistence / restart (where practical)

If the service is running Docker Compose:

```powershell
docker restart ralg-engine
# wait for health, reopen http://127.0.0.1:7860
```

The previously ingested document survives the restart (named volume `ralg_data`).
Without Docker, restart the WebUI process and re-check the documents list against
the local data volume.

### What this scenario does NOT show

- Multi-user or internet-facing deployment (no auth/TLS by design — local /
  trusted-network component only)
- Scale beyond single-tenant corpora (single-doc demo; scale tests deferred)
- Independent human validation of benchmark claims (Stage 6 review pending)
- Production SLA or multi-tenant security guarantees

### Troubleshooting this scenario

| Symptom | Fix |
|---|---|
| Launcher stopped but port still listening | The Gradio server is a child Python process of the PowerShell launcher. Stop it with `Get-Process python | Where-Object Path -like '*RALG*' | Stop-Process` (targets only this repo's Python; never kill Docker/Desktop processes) |
| Preflight fails on missing checkpoint | Place the external model bundle under `checkpoints/v2` as documented; the demo runs in extractive mode without it |
| WebUI port busy | The launcher auto-falls-back to 7861-7870 and prints the actual URL; no action needed unless the whole range is busy |
| Pipeline init error | Verify `data/tokenizer_v2.json` exists; check `logs/` for details |
| Docker restart leaves container unhealthy | Wait up to 90 s (health timeout), then check `docker logs ralg-engine` |

### Evidence boundaries (important)

- This demo uses internally authored technical SOP text (`data/technical_docs_sample.txt`).
- Answers are grounded in the retrieved evidence spans from the uploaded document.
- Abstention behavior is verified internally; the false-support rate is 0% in the
  development regression suite (100% unsupported rejection), but this demo
  scenario is not an independent holdout validation.
- Holdout V2 (70-case blind evaluation at `evaluation/results/holdout_v2_blind_once.json`)
  is separate, frozen independent evidence. This demo does not replicate or
  replace that holdout.
- Claims about "100% accurate" are NOT made. The demo demonstrates product
  behavior (grounded answering, provenance, abstention) under controlled conditions.

## 6 — Release candidate checklist

Use this checklist to verify buyer-demo release readiness. Tick each item before
considering the demo a release candidate.

### Repository state

- [ ] Working tree is clean (`git status` — no uncommitted changes)
- [ ] No logs, caches, or temporary debug files in the repo
- [ ] No secrets or machine-specific absolute paths committed
- [ ] Exact commit SHA identified (e.g. `af1ce24`)
- [ ] Exact branch recorded (e.g. `release/buyer-demo-repro-v1` or other)
- [ ] PR created and under review (not merged)

### Dependency install

- [ ] Python 3.11 verified (`python --version`)
- [ ] Virtual environment created and activated (`.venv`)
- [ ] `pip install -r requirements.txt` completed without errors
- [ ] Optional: `pip install -r requirements-polish.txt` if Qwen polish LLM is desired
- [ ] Tokenizer `data/tokenizer_v2.json` present and readable **(required)** — the core pipeline requires this
- [ ] Checkpoint bundle `checkpoints/v2/reasoning_model_v1.pt` placed (external, license-governed) — **optional**; the demo runs in extractive/lookup mode without it; generative/polish answers require it

### Preflight

- [ ] `python scripts\buyer_demo_preflight.py` passes all checks (or documented exceptions noted)
- [ ] Port 7860-7870 availability confirmed or fallback noted
- [ ] Docker optional: `scripts\buyer_demo_preflight.py --docker` reports expected state
- [ ] No unexpected failures in preflight output

### Tests

- [ ] Relevant focused tests executed (e.g. document persistence, support gate, traceability)
- [ ] `scripts\test_all.bat` steps 5–12 pass (or known limitations documented)
- [ ] Holdout V1/V2/V3 not executed (immutable blind results preserved)
- [ ] No test modifications that weaken benchmarks or invent claims

### API startup

- [ ] Service started via `powershell -ExecutionPolicy Bypass -File scripts\run_buyer_demo.ps1`
- [ ] `/health` returns `{"status":"ok"}`
- [ ] `/ready` returns `{"ready":true, ...}` when the model/checkpoint is present and initialization is healthy (extractive-only mode without the checkpoint may correctly return `503`)
- [ ] Readiness probe completes within 30 seconds

### Health / readiness

- [ ] `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`
- [ ] `curl http://127.0.0.1:8000/ready` → `{"ready":true, ...}` when the model/checkpoint is present and initialization is healthy (extractive-only mode without the checkpoint may correctly return `503`)

### Demo execution

- [ ] Ingest a technical document (via WebUI or API)
- [ ] Ask a supported question → grounded answer with cited sources
- [ ] Ask an unsupported question → visible abstention (no fabricated support)
- [ ] Inspect evidence/provenance trace for accepted answer
- [ ] Try document-scoped query via scope dropdown
- [ ] Restart demo (Docker or process restart) → document persistence verified

### Result / evidence inspection

- [ ] Source citations visible for every accepted answer
- [ ] Provenance metadata (source document, excerpt, metadata) present
- [ ] No "external validation" claims for internally authored content

### No secrets

- [ ] No API keys, passwords, or bearer tokens in repo or environment
- [ ] No valuation/buyer strategy data or private buyer information in repo
- [ ] Config env vars are generic (no machine-specific paths)

### Documentation consistency

- [ ] `docs/BUYER_DEMO_GUIDE.md` section 5 (deterministic scenario) reviewed and consistent with behavior
- [ ] `README.md` quick-start section canonical and up to date
- [ ] `CLAIMS_EVIDENCE_MATRIX.md` status labels are correct (VERIFIED/PRELIMINARY/NOT YET VALIDATED)
- [ ] `THIRD_PARTY_NOTICES.md` third-party attribution is complete and pinned
- [ ] No wording describes the buyer demo as "independent validation"
- [ ] No claim of "100% accurate" or production SLA or multi-tenant security
- [ ] Evidence boundaries clearly distinguished: demo behavior vs. development benchmark vs. historical blind evidence

### Final sign-off

- [ ] `git diff --check` — 0 whitespace issues
- [ ] `git status` — clean working tree, only expected changes
- [ ] `python scripts\buyer_demo_preflight.py` passes or failures are documented
- [ ] PR target identified; do not merge until all above items are addressed
- [ ] Cleanup: no runtime processes left running (use Ctrl+C or taskkill on python.exe if needed); no stray data files in repo directories
