# Stage 5 Independent Data Acquisition Status

## Current State: BLOCKED ON INDEPENDENT DOCUMENT ACQUISITION

**Decision:** Stage 5 evaluation cannot proceed without genuinely independent technical documents. All framework is in place; the blocker is data acquisition, not tooling.

---

## What Is Required

### Minimum Viable Corpus

**Size:** 50–300 documents  
**Domains:** 3–5 technical domains  
**Format:** Markdown, TXT, PDF, DOCX, or JSON  
**Quality:** 5–50 KB per document (suitable for Q&A)  

**Examples of suitable domains:**
1. Cloud Infrastructure (AWS, Azure, GCP public docs)
2. Networking (RFC, network protocols)
3. Security (NIST guidance, standards)
4. Software Architecture (design patterns, system design)
5. Operations (deployment, monitoring, observability)

### Legal Requirements

**Each document must satisfy ONE of:**

1. **Public Domain** — Explicitly public domain (government documents, expired copyright)
2. **CC-BY License** — Creative Commons Attribution (allows redistribution with attribution)
3. **MIT/Apache License** — Open-source compatible licenses
4. **Written Permission** — Written consent from copyright holder to use for evaluation
5. **Vendor License** — Public documentation explicitly permitted for evaluation (check ToS)

**CANNOT use:**
- Confidential materials (even with NDA, proprietary)
- Copyrighted content without license
- Private customer data (without explicit consent)
- Content from competitors (licensing unclear)

---

## Acquisition Strategies

### Strategy 1: RFC and Public Standards (Easiest)

**Sources:**
- RFC (Request for Comments) — All RFCs are public domain
- NIST Special Publications (NIST SP 800-series) — Government, freely redistributable
- IEEE/ISO standards — Some available free; check license

**Examples:**
- RFC 5321 (SMTP protocol) — Public domain
- RFC 3207 (SMTP TLS) — Public domain
- NIST SP 800-53 (Security controls) — Public domain

**Action:**
1. Visit https://tools.ietf.org/html/ (search for RFCs)
2. Visit https://nvlpubs.nist.gov/nistpubs/ (NIST documents)
3. Verify "public domain" claim in header
4. Download raw text
5. Add to evaluation/stage5_documents/
6. Create manifest entry

**Estimated effort:** 1–2 hours for 10–20 RFCs

---

### Strategy 2: Open-Source Project Documentation (Moderate)

**Sources:**
- Apache projects (Apache Software Foundation) — Apache 2.0 licensed
- Linux Foundation projects (Kubernetes, Prometheus, etc.) — Apache 2.0 or MIT
- CNCF projects — Typically Apache 2.0
- GitHub projects — Check LICENSE file

**Examples:**
- Kubernetes documentation (Apache 2.0)
- Docker documentation (partial CC-BY-SA)
- Prometheus documentation (CC-BY-SA)

**Action:**
1. Identify open-source projects in your domains
2. Check LICENSE file in repo root
3. If CC-BY, MIT, Apache 2.0, or similar: OK
4. If proprietary/closed: Skip
5. Export documentation (usually Markdown in /docs/)
6. Add metadata (source URL, license, version)

**Estimated effort:** 2–4 hours for 30–50 documents

---

### Strategy 3: Public Vendor Documentation (Moderate to Hard)

**Sources:**
- AWS Public Documentation (check ToS)
- Azure Learning Paths (check licensing)
- Google Cloud documentation (check licensing)
- DigitalOcean tutorials (often CC-BY or MIT)

**Caution:** Vendor ToS may restrict evaluation use. Verify explicitly.

**Action:**
1. Visit vendor's public documentation site
2. Check Terms of Service for research/evaluation use
3. If ToS permits evaluation: proceed
4. If unclear: contact vendor for written permission
5. Download/export documentation
6. Add to evaluation/stage5_documents/

**Estimated effort:** 3–6 hours (includes permission verification)

---

### Strategy 4: Academic Resources (Variable)

**Sources:**
- arXiv.org (preprints) — Check license (typically CC-BY or similar)
- ResearchGate — Check publication license
- Institutional repositories — Check open-access status
- Published papers with CC-BY license

**Action:**
1. Search academic databases for technical content in your domains
2. Prioritize open-access publications
3. Check license statement (CC-BY is ideal)
4. Download PDF or preprint
5. Extract text (if PDF)
6. Add to evaluation/stage5_documents/

**Estimated effort:** 2–4 hours for 10–20 papers

---

## Rapid Acquisition Plan (Recommend Starting Here)

**Target:** 100–150 independent documents in 1–2 working days

### Day 1: RFCs and NIST (3–4 hours)

1. Download 10–15 RFCs related to core domains (networking, protocols, security)
   - RFC 5321 (SMTP)
   - RFC 3207 (SMTP TLS)
   - RFC 5228 (Sieve Mail Filter Language)
   - RFC 7230–7235 (HTTP/1.1)
   - RFC 8200 (IPv6)
   - etc.

2. Download 10–15 NIST Special Publications
   - NIST SP 800-53 (Security controls)
   - NIST SP 800-81 (Secure DNS)
   - NIST SP 800-171 (CUI protection)
   - etc.

**Result:** ~25 documents (excellent quality, zero license concerns)

### Day 2: Open-Source Project Docs (3–4 hours)

1. Kubernetes documentation (~50 documents)
   - License: Apache 2.0 (OK to redistribute)
   - Export from: https://kubernetes.io/docs/

2. Prometheus documentation (~20 documents)
   - License: Apache 2.0 (OK)
   - Export from: https://prometheus.io/docs/

3. Docker documentation (~20 documents)
   - License: Check (partial CC-BY-SA)
   - Export from: https://docs.docker.com/

4. Linux manual pages (man-pages) (~30 documents)
   - License: GPL/CC-BY-SA (redistribution permitted)
   - Source: https://man7.org/

**Result:** ~120 documents (good variety, well-scoped)

**Total:** ~145 documents acquired in 1–2 days, all with clear license/public domain status

---

## Manifest Entry Process

For each acquired document:

```bash
# 1. Save document to evaluation/stage5_documents/
cp downloaded_doc.md evaluation/stage5_documents/

# 2. Verify encoding (UTF-8)
file -i evaluation/stage5_documents/downloaded_doc.md

# 3. Compute SHA-256
sha256sum evaluation/stage5_documents/downloaded_doc.md > doc_hash.txt

# 4. Add to manifest (evaluation/stage5_source_manifest.jsonl)
cat >> evaluation/stage5_source_manifest.jsonl << 'EOF'
{
  "doc_id": "unique_doc_id",
  "title": "Document Title",
  "source_type": "public",
  "source_identifier": "https://source_url/...",
  "domain": "networking",
  "revision_version": "3.1.0",
  "acquisition_date": "2026-01-20",
  "license_type": "public_domain",
  "permission_status": "confirmed",
  "redistribution_permitted": true,
  "synthetically_generated": false,
  "used_in_development": false,
  "sha256": "abc123...",
  "content_length_bytes": 45000,
  "notes": "Public RFC. No reproduction restrictions."
}
EOF
```

---

## Validation After Acquisition

### 1. Manifest Validation

```bash
python3.11 scripts/stage5_evaluation.py \
  --manifest evaluation/stage5_source_manifest.jsonl \
  --check-only
```

**Expected output:**
```
[1/4] Validating source independence...
✓ All N sources pass independence validation
```

If any sources fail:
- synthetically_generated: true → REJECT
- used_in_development: true → REJECT
- permission_status != "confirmed" → REJECT
- redistribution_permitted: false → REJECT

### 2. Document Integrity Check

```bash
for doc in evaluation/stage5_documents/*; do
  echo "Checking $doc..."
  file -i "$doc"  # Verify UTF-8
  wc -c "$doc"    # Check size (should be < 50 MB)
  head -c 100 "$doc"  # Check first 100 bytes for corruption
done
```

### 3. Duplicate Check

```bash
# Check for exact duplicate documents
md5sum evaluation/stage5_documents/* | sort | uniq -d

# Check for near-duplicate documents
python3.11 -c "
import os
from difflib import SequenceMatcher

docs = {}
for f in os.listdir('evaluation/stage5_documents'):
  with open(f'evaluation/stage5_documents/{f}') as fh:
    docs[f] = fh.read()

for f1, content1 in docs.items():
  for f2, content2 in docs.items():
    if f1 < f2:
      ratio = SequenceMatcher(None, content1, content2).ratio()
      if ratio > 0.85:
        print(f'{f1} <-> {f2}: {ratio:.1%} similar')
"
```

---

## Document Preparation

If documents need preprocessing:

### PDF to Text

```bash
pip install PyPDF2
python3.11 -c "
from PyPDF2 import PdfReader
with open('input.pdf', 'rb') as f:
  reader = PdfReader(f)
  for page in reader.pages:
    print(page.extract_text())
" > output.txt
```

### Markdown Metadata

Add YAML front-matter:

```markdown
---
title: "Document Title"
source: "RFC 5321"
source_url: "https://tools.ietf.org/html/rfc5321"
date_published: "2008-10"
date_acquired: "2026-01-20"
domain: "networking"
version: "1.0"
license: "public_domain"
redistribution_permitted: true
synthetic: false
---

# Document content starts here
```

---

## Permission Template (If Needed)

For unclear licenses, send this email to copyright holder:

---

**Subject:** Permission to use [document title] in technical evaluation

Dear [Author/Publisher],

We are conducting a technical evaluation of a retrieval system and would like to include [document name, version] in our evaluation corpus.

May we:
- Store a copy internally for evaluation research?
- Include aggregated findings from evaluation in a technical report?
- Share (anonymized) metrics about system performance on this content?

Please let us know if permission is granted or if you have any restrictions.

Thank you,
[Your Name]

---

## Red Flags to Avoid

1. **"We generated this internally"** — ✗ NOT independent
2. **"We used this during tuning"** — ✗ NOT independent
3. **"License is unclear"** — ✗ Verify or skip
4. **"Vendor ToS is unclear"** — ✗ Contact vendor or skip
5. **"Confidential (under NDA)"** — ✗ SKIP
6. **"Customer provided (no written consent)"** — ✗ SKIP
7. **"Copyrighted book (fair use?)"** — ✗ Legally risky; skip unless clear license

---

## Decision Point

### Before Proceeding

1. Identify 50+ documents meeting independence criteria
2. Run manifest validation (`scripts/stage5_evaluation.py --check-only`)
3. Verify all sources pass independence check (synthetic=false, used_in_development=false, permission_status=confirmed)
4. If all pass: → Proceed to benchmark construction (Step 2)
5. If any fail: → Identify additional sources or resolve permission

### If Cannot Obtain Independent Data

If after 4–8 hours of acquisition attempts, genuinely independent documents cannot be sourced:

Report to stakeholders:
```
BLOCKED ON INDEPENDENT DATA

Barrier: [specific constraint]
- No public technical documents identified that meet criteria
- OR identified documents have unclear licensing
- OR permission denied

Recommendation: [next step]
- Contact potential partners for document sharing arrangements
- Identify alternative domains with clearer licensing
- Request customer pilot participation (customer brings data)
```

This is honest and actionable. Better than pretending internal synthetic data is independent.

---

## Success Criteria: Data Acquisition

✓ 50+ documents acquired with clear provenance  
✓ All documents pass independence validation  
✓ All documents are UTF-8 encoded  
✓ No synthetic or development-used documents mixed in  
✓ Manifest entries complete and accurate  
✓ SHA-256 hashes verified  
✓ Ready for expert review and benchmark construction  

---

**Estimated Timeline:** 1–2 working days for acquisition + validation  
**Next Milestone:** Expert benchmark construction (once 50+ independent documents acquired)

**Questions?** Refer to docs/PILOT_DATA_REQUIREMENTS.md for detailed sourcing criteria.

---

**Last Updated:** 2026-08-25  
**Status:** Ready for data acquisition
