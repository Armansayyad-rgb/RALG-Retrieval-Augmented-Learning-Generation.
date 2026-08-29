# RALG Pilot Runbook

## Purpose

This runbook guides technical teams through a single-worker local pilot deployment of RALG for evaluation of retrieval-augmented grounding functionality.

**SCOPE:** Local/trusted environment only. Not suitable for production use without additional hardening.

## Prerequisites

### Environment

- Linux or macOS (Windows requires WSL2)
- Python 3.11+
- 8 GB RAM minimum (16 GB recommended for 250k+ document corpus)
- 10 GB disk space for indexes and artifacts
- Outbound network access (for model downloads on first run)

### System Access

- Local sudo/admin access (for Docker, if used)
- No authentication/TLS required for pilot

### Documents and Data

- PDF, TXT, or Markdown documents (see Supported Formats, below)
- Maximum individual document: 50 MB
- Total corpus: up to 250k documents (validated; 500k requires headroom verification)
- Document encoding: UTF-8 (strongly recommended)

### Network Requirements

- Localhost binding only (127.0.0.1:8000)
- Outbound HTTPS for model downloads
- No ingress firewall changes required

## Supported Document Formats

### Supported (Recommended)

- **Markdown (.md)**: Metadata in YAML front-matter
- **Plain text (.txt)**: Auto-indexed
- **PDF (.pdf)**: Text extraction with OCR support (if configured)

### Partially Supported (Caution)

- **DOCX** (.docx): Requires python-docx; may lose formatting
- **JSON** (.json): Structured data as documents; ensure valid UTF-8

### Not Supported

- Binary formats (images, video, audio)
- Encrypted PDFs
- RTF
- Proprietary office formats without conversion

## Installation

### Option A: Source Installation (Recommended for Development)

```bash
cd /path/to/RALG

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import src.api_server; print('OK')"
```

### Option B: Docker Installation (Recommended for Isolation)

```bash
cd /path/to/RALG

# Build image
docker build -t ralg:pilot .

# Run container
docker run \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/indexes:/app/indexes \
  --name ralg_pilot \
  ralg:pilot
```

**Note:** Docker daemon must be running. See Troubleshooting if unavailable.

## Quick Start

### 1. Start the Service

#### Source Installation

```bash
cd /path/to/RALG
source .venv/bin/activate
uvicorn src.api_server:app --host 127.0.0.1 --port 8000
```

**Expected output:**

```
INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Loaded 0 documents. Ready for ingest.
```

#### Docker Installation

```bash
docker run -p 8000:8000 -v $(pwd)/data:/app/data ralg:pilot
```

**Container should be running and ready in 15–30 seconds.**

### 2. Verify Health

```bash
curl http://127.0.0.1:8000/health
```

**Expected response (200 OK):**

```json
{
  "status": "ok"
}
```

### 3. Ingest Documents

#### Upload a single document

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "text": "# My Document\n\nKey information here.",
    "document_name": "example.md"
  }' \
  http://127.0.0.1:8000/ingest
```

**Expected response (200 OK):**

```json
{
  "document_id": "abc123...",
  "document_name": "example.md",
  "added_chunks": 1,
  "total_chunks": 1
}
```

#### Bulk ingest from directory

```bash
python src/cli_ingest.py \
  --input-dir /path/to/documents \
  --endpoint http://127.0.0.1:8000 \
  --recursive
```

### 4. Query the System

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main features?",
    "top_k": 5
  }' \
  http://127.0.0.1:8000/query
```

**Expected response:**

```json
{
  "answer": "...",
  "supported": true,
  "confidence": 0.95,
  "answer_type": "extractive",
  "sources": [
    {
      "rank": 1,
      "id": 107650,
      "preview": "Key information here.",
      "score": 12.34
    }
  ],
  "latency_ms": 234.1,
  "traceable": true,
  "conflict": false,
  "provenance": []
}
```

### 5. Verify Unsupported Query Handling

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the secret number that has never been mentioned?",
    "top_k": 5
  }' \
  http://127.0.0.1:8000/query
```

**Expected response:**

```json
{
  "answer": "I couldn't find enough reliable evidence in the current knowledge base.",
  "supported": false,
  "confidence": null,
  "answer_type": "system",
  "sources": [],
  "latency_ms": 38.0,
  "traceable": false,
  "conflict": false,
  "provenance": [],
  "error": null
}
```

## API Reference

### GET /health

Check service readiness.

**Response:**

```json
{
  "status": "ok"
}
```

---

### GET /ready

Check runtime readiness (model, tokenizer, corpus, index).

**Response (200):**

```json
{
  "ready": true,
  "model_loaded": true,
  "tokenizer_loaded": true,
  "index_loaded": true,
  "chunk_count": 100000,
  "retrieval_ready": true,
  "model_ready": true,
  "error": null
}
```

**Response (503):**

```json
{
  "ready": false,
  "model_loaded": false,
  "tokenizer_loaded": false,
  "index_loaded": false,
  "chunk_count": 0,
  "retrieval_ready": false,
  "model_ready": false,
  "error": "Runtime is not ready."
}
```

---

### POST /ingest

Ingest plain text into the running pipeline.

**Request:**

```json
{
  "text": "Your document text here...",
  "document_name": "my_doc"
}
```

**Response:**

```json
{
  "document_id": "abc123...",
  "document_name": "my_doc",
  "added_chunks": 1,
  "total_chunks": 100001
}
```

---

### POST /query

Query the system with a natural language question.

**Request:**

```json
{
  "question": "string",
  "top_k": 5,
  "include_sources": true,
  "document_ids": ["doc_id_1", "doc_id_2"]
}
```

**Response:**

```json
{
  "answer": "string",
  "supported": true,
  "confidence": 0.95,
  "answer_type": "extractive",
  "sources": [
    {
      "rank": 1,
      "id": 107650,
      "preview": "...",
      "score": 12.34
    }
  ],
  "latency_ms": 234.1,
  "traceable": true,
  "conflict": false,
  "provenance": [],
  "error": null
}
```

---

### GET /documents

List persisted runtime document metadata.

**Response:**

```json
[
  {
    "document_id": "abc123...",
    "document_name": "my_doc",
    "chunk_count": 1,
    "upload_timestamp": "2026-01-01T00:00:00Z"
  }
]
```

---

### DELETE /documents/{document_id}

Remove a persisted runtime document.

**Response:**

```json
{
  "document_id": "abc123...",
  "deleted": true,
  "chunks_removed": 1
}
```

---

## Workflow: A Typical Evaluation Session

### Step 1: Start the Service

```bash
cd /path/to/RALG
source .venv/bin/activate
uvicorn src.api_server:app --host 127.0.0.1 --port 8000 &
sleep 2
curl http://127.0.0.1:8000/health  # Verify
```

### Step 2: Prepare Documents

Place evaluation documents in a directory:

```bash
mkdir -p /tmp/evaluation_docs
cp evaluation/stage5_documents/*.md /tmp/evaluation_docs/
```

### Step 3: Ingest Documents

```bash
python src/cli_ingest.py \
  --input-dir /tmp/evaluation_docs \
  --endpoint http://127.0.0.1:8000 \
  --log-level INFO
```

**Monitor until all documents are indexed.**

### Step 4: Run Evaluation Queries

```bash
python src/evaluate_pilot.py \
  --endpoint http://127.0.0.1:8000 \
  --queries evaluation/stage5_questions.jsonl \
  --output results/pilot_evaluation.jsonl
```

### Step 5: Analyze Results

```bash
python src/analyze_results.py \
  --results results/pilot_evaluation.jsonl \
  --expected evaluation/stage5_answers.jsonl
```

### Step 6: Stop the Service

```bash
pkill -f "uvicorn src.api_server:app"
```

## Known Limitations

### Pilot Boundary

- **Local environment only**: Designed for localhost evaluation only
- **Single worker**: Process-local concurrency only; no distributed indexing
- **Optional authentication**: Bearer-token auth via `API_TOKEN` env var (unset = open)
- **No TLS**: Communication is unencrypted; use reverse proxy for TLS termination
- **No tenant isolation**: All documents are accessible from all queries
- **Synthetic evidence**: Stage 4 evaluation was on synthetic data (not production customer data)

### Scale Constraints

- **100k documents**: Fully validated (p50 retrieval ~150ms)
- **250k documents**: Validated (requires 16+ GB RAM)
- **500k+ documents**: Deferred (requires headroom verification)

### Not Supported in Pilot

- Multi-tenant isolation
- Complex document format extraction (scanned PDFs with OCR limitations)
- Real-time streaming ingestion
- High-concurrency query handling (>10 req/sec per worker)
- Distributed index replication

## Troubleshooting

### Issue: "Connection refused"

```
curl: (7) Failed to connect to 127.0.0.1 port 8000: Connection refused
```

**Solutions:**

1. Verify the service started: `ps aux | grep uvicorn`
2. Check logs: `cat logs/server.log | tail -50`
3. Restart: `pkill -f "uvicorn src.api_server:app"; sleep 2; uvicorn src.api_server:app ...`

---

### Issue: "Module not found"

```
ModuleNotFoundError: No module named 'src'
```

**Solutions:**

1. Verify Python path: `echo $PYTHONPATH`
2. Run from repository root: `cd /path/to/RALG`
3. Check venv activation: `which python` (should be `.venv/bin/python`)

---

### Issue: "Out of memory"

```
MemoryError: Unable to allocate X GiB
```

**Solutions:**

1. Reduce corpus size: `--max-docs 50000`
2. Increase available RAM: Check system memory (`free -h`)
3. Use smaller documents or split large documents

---

### Issue: Docker daemon unavailable

```
Cannot connect to Docker daemon
```

**Solutions:**

1. Start daemon: `sudo systemctl start docker` (Linux) or `open /Applications/Docker.app` (macOS)
2. Check permissions: `sudo usermod -aG docker $USER`
3. Fall back to source installation (Option A above)

---

### Issue: Ingest failing

```
{"status": "error", "message": "Invalid document format"}
```

**Solutions:**

1. Verify UTF-8 encoding: `file -i document.txt`
2. Check file size: `ls -lh document.txt` (should be < 50 MB)
3. Inspect first 100 bytes: `head -c 100 document.txt | od -c`

---

## Success Criteria: Pilot Evaluation

A successful pilot run should demonstrate:

### Functional Criteria

- ✓ Service starts and becomes ready within 30 seconds
- ✓ Ingest succeeds for 100+ documents
- ✓ Query latency is < 100 ms for p50, < 500 ms for p95
- ✓ Supported queries return results with scores
- ✓ Unsupported queries return empty results with `"supported": false`
- ✓ False-support rate is 0% (no incorrect confidence for unsupported queries)
- ✓ Restart persists documents (data survives graceful shutdown + restart)

### Performance Criteria

- ✓ Retrieval p50 < 200 ms (100k corpus)
- ✓ Retrieval p95 < 500 ms (100k corpus)
- ✓ Memory usage < 8 GB (100k corpus)

### Quality Criteria

- ✓ Recall@1 >= baseline (lexical retrieval)
- ✓ MRR >= baseline
- ✓ Unsupported rejection rate >= 95%

## Failure Escalation

If pilot evaluation fails on:

### Critical Failures (STOP)

- Service crashes on startup
- Ingest loses documents on restart
- False-support rate > 5%
- Unsupported rejection < 90%

**Action:** Do not proceed. Review logs, report issue, and request investigation.

### Non-Critical Issues (Document)

- Query latency > 500 ms (p95) on 100k corpus
- Recall@1 < baseline
- Memory usage > 16 GB

**Action:** Document limitation, include in pilot report, recommend optimization.

## Logging and Privacy

### What Is Logged

- Request duration
- Retrieval duration
- Document count
- Query supported/unsupported status
- Ingest success/failure
- Index build progress

### What Is NOT Logged

- Raw document content
- Secrets or API keys
- Full query text (logged as hash only)
- User identifiers
- Stack traces (only error types)

### Access Logs

View server logs:

```bash
tail -f logs/server.log
```

View query logs:

```bash
grep "query" logs/server.log | tail -20
```

## Rollback and Cleanup

### Stop the Service

```bash
pkill -f "uvicorn src.api_server:app"
```

### Clear Indexed Documents

```bash
rm -rf indexes/*
rm -rf data/documents/*
```

### Reset to Clean State

```bash
git checkout indexes/ data/
```

### Restore from Backup

```bash
cp backups/indexes_v1/ indexes/
```

## Next Steps After Pilot

If pilot succeeds, next milestones are:

1. **Independent Evidence Stage 5**: Evaluation on customer/expert-sourced documents
2. **Hardening**: API authentication (`API_TOKEN`), CORS policy, rate limiting, TLS termination via reverse proxy
3. **Production Deployment**: Kubernetes, distributed indexing, monitoring
4. **Customer Integration**: SDK, custom document processors, operational runbooks

## Support and Escalation

For issues during pilot:

1. Check Troubleshooting section (above)
2. Review logs: `tail -f logs/server.log`
3. Verify preconditions (Python, disk space, network)
4. If unresolved, collect:
   - Error message
   - Log excerpt
   - Reproduction steps
   - System info (`uname -a`, `python --version`, etc.)

---

**Last Updated:** 2026-01-01  
**Pilot Version:** 0.1.0-rc1  
**Supported Until:** TBD (pilot status only; not for production)
