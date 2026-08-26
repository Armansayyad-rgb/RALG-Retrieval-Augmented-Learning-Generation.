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
| Python | 3.10 or newer on PATH, or a prepared `.venv` in the repo root |
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
# endpoints: GET /health, GET /ready, POST /ingest, POST /query, GET /documents
```

Same behavior; useful when the buyer wants to script the walkthrough.

## 5. What this demo does NOT show

- Multi-user or internet-facing deployment (no auth/TLS by design — local /
  trusted-network component)
- Scale beyond single-tenant corpora (250k/500k chunk tests deferred)
- Independent human validation of benchmark claims (Stage 6 review pending)

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| Launcher stopped but port still listening | The Gradio server is a child Python process of the PowerShell launcher. Stop it with `Get-Process python \| Where-Object Path -like '*<repo>*' \| Stop-Process` (targets only this repo's Python; never kill Docker/Desktop processes) |
| Preflight fails on missing checkpoint | Place the external model bundle under `checkpoints\` as documented; nothing is auto-downloaded |
| WebUI port busy | The launcher auto-falls-back to 7861-7870 and prints the actual URL; no action needed unless the whole range is busy |
| Pipeline init error | Verify `data\tokenizer_v2.json` exists; check `logs\` for details |
| Docker restart leaves container unhealthy | Wait up to 90 s (health timeout), then check `docker logs <container>` |
