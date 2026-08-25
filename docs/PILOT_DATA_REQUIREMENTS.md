# RALG Pilot Data Requirements

## Document Acquisition

This document specifies the types and formats of documents suitable for RALG pilot evaluation.

## Source Categories

### A: Ideal Sources (Preferred for Pilot)

**Public technical documentation** that is freely available and clearly licensed:

- **Public standards**: RFC, IEEE, ISO specifications (if openly available)
- **Government guidance**: NIST, FIPS, public agency technical documentation
- **Open-source project docs**: Apache, Linux Foundation, CNCF projects
- **Public vendor documentation**: AWS, Azure, Google Cloud (public-facing)
- **Academic technical reports**: Published papers, technical reports (check licensing)
- **Openly licensed content**: Creative Commons (CC-BY, CC-BY-SA), MIT-licensed docs

**Preferred characteristics:**

- Clearly scoped domain (e.g., cloud architecture, networking, security)
- 10–100 pages per document (not too brief, not encyclopedic)
- Multiple documents in same domain (for cross-document reasoning)
- Written in English (or provide English translation)
- Last updated within past 5 years (for relevance)
- Available via stable URL or version-controlled repo

### B: Requires Explicit Permission

Documents that have usage restrictions but may be usable with permission:

- **Private vendor documentation**: Contact vendor, request permission
- **Licensed technical content**: Verify license terms permit evaluation use
- **Customer documentation**: Requires written consent before use
- **Proprietary standards**: May require licensing or permission

**Do not use without written confirmation.**

### C: Not Suitable

- **Confidential material** (without NDA + written permission)
- **Copyrighted content without license** (books, articles without permission)
- **Private/internal documentation** (unless shared with explicit consent)
- **Material from competitors** (unless clearly licensed for use)

## Format Requirements

### Supported Input Formats

| Format | Support | Notes |
|---|---|---|
| **Markdown (.md)** | ✓ Excellent | Metadata in YAML front-matter; preferred |
| **Plain text (.txt)** | ✓ Excellent | Auto-indexed; no metadata support |
| **PDF (.pdf)** | ✓ Good | Text extraction only; embedded images not indexed |
| **DOCX (.docx)** | ✓ Fair | Requires python-docx; formatting may be lost |
| **JSON (.json)** | ✓ Good | Structured data as documents; ensure valid UTF-8 |
| **HTML (.html)** | ~ Limited | May contain scripts; sanitization recommended |
| **Images, binary** | ✗ Not supported | No OCR in pilot |
| **Encrypted PDFs** | ✗ Not supported | Require decryption before ingestion |

### Document Metadata

Documents should include metadata fields (in YAML front-matter for Markdown, or as separate JSON):

```yaml
---
title: "Document Title"
source: "Original source or vendor"
source_url: "https://... if applicable"
date_published: "2025-01-01"
date_acquired: "2026-01-01"
domain: "cloud_architecture | networking | security | etc."
version: "1.0.0"
license: "CC-BY 4.0 | MIT | Apache 2.0 | Public Domain | etc."
redistribution_permitted: true | false
synthetic: false
---
```

## Corpus Composition

### Recommended Pilot Corpus

- **Total documents**: 50–300 (smaller is better for fast iteration)
- **Average document length**: 5–50 KB
- **Domains**: 3–5 distinct technical domains
- **Languages**: English (or English translation)

### Domain Diversification

Recommend including documents from:

1. **Cloud Infrastructure** (AWS, Azure, GCP documentation)
2. **Networking** (RFC, network protocol documentation)
3. **Security** (NIST guidance, security standards)
4. **Software Architecture** (design patterns, system design)
5. **Operations** (deployment, monitoring, observability)

At least 2 documents per domain (for multi-document reasoning tests).

### Content Characteristics

Documents should:

- ✓ Contain clear, factual technical information
- ✓ Include procedures, specifications, or architectural guidance
- ✓ Have multiple sections/subsections (for retrieval difficulty variation)
- ✓ Contain numeric information (ports, versions, thresholds)
- ✓ Include cross-references (natural multi-document links)

Documents should NOT:

- ✗ Be overly marketing-heavy (focus on facts, not sales pitch)
- ✗ Be extremely dense (wall of equations/formal notation without examples)
- ✗ Be outdated/stale (prefer last updated within 5 years)
- ✗ Be proprietary/confidential (must be redistributable)

## Acquisition Process

### Step 1: Identify Candidate Sources

Use these search strategies:

1. **Public standards**: Search "RFC [topic]", "[standard] filetype:pdf site:*.gov"
2. **Public documentation**: "[Product] public documentation", "[Service] architecture guide"
3. **Open-source projects**: GitHub README + docs/, documentation sites
4. **Academic resources**: arxiv.org, ResearchGate, institutional repositories

### Step 2: Verify License and Permission

For each candidate:

1. Check source for explicit license statement
2. If license is unclear, contact author/publisher
3. Document permission in manifest (see evaluation/stage5_source_manifest.jsonl)
4. Only add to pilot if permission is confirmed

### Step 3: Prepare Documents

1. **Download or copy** source material
2. **Extract text** (if PDF; use pdftotext or similar)
3. **Add metadata** (YAML front-matter for Markdown)
4. **Normalize encoding** (ensure UTF-8)
5. **Validate format** (run through parser to check for corruption)

### Step 4: Manifest Entry

Add entry to evaluation/stage5_source_manifest.jsonl:

```json
{
  "doc_id": "aws_s3_guide_v1",
  "title": "Amazon S3 Developer Guide",
  "source_type": "public",
  "source_identifier": "https://docs.aws.amazon.com/s3/latest/dev/",
  "domain": "cloud_infrastructure",
  "revision_version": "2.0",
  "acquisition_date": "2026-01-15",
  "license_type": "CC-BY-SA-4.0",
  "permission_status": "confirmed",
  "redistribution_permitted": true,
  "synthetically_generated": false,
  "used_in_development": false,
  "sha256": "abc123...",
  "content_length_bytes": 250000,
  "notes": "Public documentation from AWS. Retrieved 2026-01-15."
}
```

### Step 5: Store Document

```bash
mkdir -p evaluation/stage5_documents/
cp source_document.md evaluation/stage5_documents/
```

## Quality Checklist

Before using a document in pilot:

- [ ] Source is publicly available OR has written permission
- [ ] License permits evaluation/research use
- [ ] Document is in a supported format (Markdown, TXT, PDF, or easily convertible)
- [ ] Document is UTF-8 encoded (or successfully converted)
- [ ] Metadata is complete (title, source, domain, license, acquisition date)
- [ ] SHA-256 hash is computed and verified
- [ ] Document is not marked as synthetic
- [ ] Document was not used in Stage 1–4 development
- [ ] Document is not identical to any other pilot document
- [ ] Document is suitable technical content (not marketing, outdated, or off-topic)

## Size and Scale Guidance

### Pilot Corpus (Recommended Starting Point)

- **50 documents**: Quick validation run (< 1 minute ingest, < 50 MB index)
- **150 documents**: Comprehensive pilot (< 5 minutes ingest, < 200 MB index)
- **300 documents**: Extended evaluation (< 15 minutes ingest, < 500 MB index)

### Scale Levels

| Documents | Disk Index | RAM | p50 Latency | Status |
|---|---|---|---|---|
| 1,000 | 5 MB | 500 MB | < 10 ms | Validated |
| 10,000 | 50 MB | 1.5 GB | < 50 ms | Validated |
| 100,000 | 500 MB | 8 GB | < 200 ms | Validated |
| 250,000 | 1.2 GB | 16 GB | < 300 ms | Validated |
| 500,000 | 2.5 GB | 32 GB | < 500 ms | Deferred |

Do not attempt 500k+ on machines with < 32 GB available RAM.

## Bundling for Distribution

If distributing pilot corpus to others:

```bash
cd evaluation/
tar -czf stage5_pilot_corpus_v1.tar.gz \
  stage5_documents/ \
  stage5_source_manifest.jsonl

# Verify integrity
tar -tzf stage5_pilot_corpus_v1.tar.gz | head
```

Include manifest in distribution so reviewers can verify source provenance.

## Troubleshooting

### Problem: "Document file not found"

**Cause:** Source URL is no longer accessible.

**Solution:** Save an archived copy via archive.org or GitHub, or contact original author for a copy.

### Problem: "Permission status unclear"

**Cause:** License is ambiguous or missing.

**Solution:** Contact the document author/publisher with this template:

> Subject: Permission to use [document title] in technical evaluation
>
> We are evaluating a retrieval system and would like to include [document name/version] in our evaluation corpus. 
> May we:
> - Store a copy internally for evaluation?
> - Include results/findings from evaluation in a technical report?
> - Share (anonymized) aggregated performance metrics?
>
> Thank you for clarifying the usage rights.

### Problem: "Document is too large" (> 50 MB)

**Solution:** Split large documents:

```bash
# For PDFs
pdftotext large_document.pdf - | split -b 1000000 - doc_part_

# For text
split -b 1000000 large_document.txt doc_part_
```

Then create separate manifest entries for each part.

## Data Retention and Cleanup

After pilot completion:

1. **Retain source manifest** (evaluation/stage5_source_manifest.jsonl): Permanent record of sources
2. **Retain result data** (evaluation/stage5_results.jsonl): For comparison/audit
3. **Optional: Retain documents**: If license permits; otherwise delete after evaluation

Document retention policy in evaluation/PILOT_DATA_RETENTION.md.

---

**Pilot Version:** 0.1.0-rc1  
**Data Format Version:** 1.0  
**Last Updated:** 2026-01-01
