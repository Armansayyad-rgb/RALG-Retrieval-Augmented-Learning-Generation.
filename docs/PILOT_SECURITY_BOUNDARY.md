# RALG Pilot Security Boundary

## Scope: Pilot Is Local/Trusted Only

**CRITICAL:** RALG pilot is NOT suitable for production use or untrusted networks.

This document defines the security boundary and known limitations.

## Threat Model

### Pilot Assumptions

- **Network**: localhost/trusted LAN only
- **Users**: Trusted team members with shell access
- **Admin access**: Assumed available (for Docker, privileged operations)
- **Data**: Non-sensitive evaluation data only
- **Uptime**: Pilot may be restarted/stopped without warning

### Out of Scope (Pilot Does NOT Address)

- Multi-tenant isolation
- Authentication/authorization
- Encryption in transit (TLS/HTTPS)
- Encryption at rest
- Rate limiting / DoS protection
- Secret/credential management
- Audit logging for compliance
- High availability / redundancy

## Security Checklist: Pilot Deployment

### ✓ Safeguards Implemented

- [ ] Service binds to localhost only (127.0.0.1, not 0.0.0.0)
- [ ] Single worker process (no parallel workers exposed)
- [ ] No TLS/HTTPS required (assumes trusted network); reverse proxy recommended for production
- [ ] Input validation for document upload (filename, size, encoding)
- [ ] Path traversal protection (document IDs are sanitized)
- [ ] Malformed file rejection (invalid JSON, corrupt PDFs)
- [ ] Resource limits (document size cap, max corpus size)
- [ ] Graceful error responses (no stack traces to clients)
- [ ] Request body size limit (`MAX_API_REQUEST_BYTES = 1 MB`)
- [ ] Security headers on all responses (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`)
- [ ] Optional bearer-token authentication (`API_TOKEN` env var)
- [ ] Process-local rate limiting when `API_TOKEN` is set (60 req/min/IP)
- [ ] CORS disabled by default; explicit `CORS_ORIGINS` required for production browser access

### ⚠ Considerations (May Need Hardening Before Production)

- [ ] Process-local only (no multi-process safety)
- [ ] Authentication optional (all endpoints open when `API_TOKEN` is unset)
- [ ] No audit logging (limited operational visibility)
- [ ] Logs may contain request metadata (queries, doc IDs)
- [ ] Loose file permissions (indexes world-readable if deployed to shared system)
- [ ] Rate limiting is process-local only (not distributed)

### ✗ NOT Implemented in Pilot

- [ ] TLS/HTTPS encryption
- [ ] Multi-tenant isolation
- [ ] Role-based access control
- [ ] Encryption at rest
- [ ] Distributed/multi-worker deployment
- [ ] Secrets management
- [ ] Compliance logging (SOC 2, HIPAA, etc.)
- [ ] Intrusion detection
- [ ] DDoS mitigation
- [ ] Distributed rate limiting

## Known Attack Vectors

### Vector 1: Oversized Document Upload

**Threat:** Attacker uploads extremely large file to exhaust disk/memory.

**Current Mitigation:** 50 MB per-document limit enforced.

**Residual Risk:** HIGH (limit may not be sufficient for all environments)

**Mitigation for Production:** Disk quota per worker, rate limiting, quotas per API key.

---

### Vector 2: Malformed File Injection

**Threat:** Attacker uploads corrupted PDF, JSON, or executable to crash indexer.

**Current Mitigation:** Format validation, safe error handling, process isolation.

**Residual Risk:** MEDIUM (fuzzing not performed; edge cases possible)

**Mitigation for Production:** Sandboxed file processing, fuzzing, containment layer.

---

### Vector 3: Path Traversal

**Threat:** Attacker crafts malicious filename (e.g., `../../etc/passwd`) to access files outside document directory.

**Current Mitigation:** Document ID sanitization; only alphanumeric + underscore allowed.

**Residual Risk:** LOW (current validation is strict)

**Mitigation for Production:** Further restrict characters; use random UUIDs for doc IDs.

---

### Vector 4: Resource Exhaustion

**Threat:** Attacker sends thousands of queries to exhaust CPU/memory.

**Current Mitigation:** Process-local rate limit (60 req/min/IP) active when `API_TOKEN` is set; request body capped at 1 MB.

**Residual Risk:** MEDIUM (localhost trusted; rate limit is not distributed)

**Mitigation for Production:** Per-IP rate limiting, request queuing, circuit breaker, distributed limit via reverse proxy.

---

### Vector 5: Information Disclosure

**Threat:** Attacker queries system to extract sensitive information from indexed documents.

**Current Mitigation:** Assumes all documents are non-sensitive pilot data.

**Residual Risk:** HIGH (no access control; all documents globally accessible)

**Mitigation for Production:** User authentication, document-level access control, audit logging.

---

### Vector 6: Unencrypted Data in Transit

**Threat:** Attacker on local network intercepts queries/results in plaintext HTTP.

**Current Mitigation:** Assumes localhost/trusted network only.

**Residual Risk:** MEDIUM (unencrypted over LAN)

**Mitigation for Production:** TLS 1.3, certificate validation, end-to-end encryption.

---

## Security Controls by Component

### Input Validation

| Component | Input | Validation | Status |
|---|---|---|---|
| Document upload | Filename | Alphanumeric + underscore + dot only | ✓ Implemented |
| Document content | File content | Format-specific parsing (JSON/PDF/Markdown) | ✓ Implemented |
| Document size | File size | Max 50 MB per file | ✓ Implemented |
| Query | Query string | Sanitized before logging (hash only) | ✓ Implemented |
| API parameters | JSON fields | Type checking, range validation | ✓ Implemented |

### Process Isolation

- Single worker process (no fork/spawn)
- Process runs as regular user (not root; verify with `ps -aux | grep api`)
- Working directory isolated (indexes/, data/ only)
- No shell execution (`os.system`, `subprocess.shell=True` not used; verify with `grep -r "shell=True" src/`)

### File System Permissions

```bash
# Check that indexes/data are not world-writable
ls -la indexes/ data/
# Should show: drwxr-xr-x (755) or more restrictive
```

### Error Handling

- Errors are generic (no stack traces to clients)
- Validation failures return 400 Bad Request (not 500)
- Internal errors logged locally but not exposed
- Exceptions caught and sanitized before response

Example safe error response:

```json
{
  "error": "Invalid document format",
  "details": null
}
```

Example unsafe error response (DO NOT DO THIS):

```json
{
  "error": "KeyError: 'title'",
  "traceback": "File /app/src/ingest.py line 45 in parse_document..."
}
```

### Logging

**Safe to log:**
- Request duration
- Document count
- Supported/unsupported status
- Ingest success/failure
- Error type (not traceback)

**NOT safe to log:**
- Raw query text (log hash instead: `hashlib.sha256(query.encode()).hexdigest()`)
- Full document content
- API keys or secrets
- User identifiers
- Stack traces
- File paths (use relative paths only)

**Log redaction example:**

```python
# UNSAFE
logger.info(f"Query: {query}")

# SAFE
import hashlib
query_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
logger.info(f"Query (hash): {query_hash}")
```

## Network Isolation

### Localhost Binding (Required)

Verify service binds to 127.0.0.1 only:

```bash
# Start service
uvicorn src.api_server:app --host 127.0.0.1 --port 8000

# In another terminal, verify
netstat -tlnp | grep 8000
# Expected: tcp  0  0  127.0.0.1:8000  ...

# NOT acceptable:
# tcp  0  0  0.0.0.0:8000  ...  (binds to all interfaces)
```

### No Ingress Firewall Rules Required

Because localhost binding is enforced, the service is only accessible from:
- The local machine itself
- Docker container (if deployed in container)

No special firewall rules or network configuration needed.

### Shared Machine Concern

If deployed on a shared/multi-user system:

```bash
# Check who can access the socket
ls -la /var/run/ralg/  # or wherever socket lives

# Should be restricted to single user
# Use: umask 0077 or chmod 700
```

## Data Sensitivity

### Non-Sensitive Data (Safe for Pilot)

- Public technical documentation (RFC, AWS docs, etc.)
- Open-source project guides
- Evaluation test questions and answers
- Aggregated performance metrics
- System metadata (document counts, latency histograms)

### Sensitive Data (DO NOT USE IN PILOT)

- Private customer data
- Confidential business information
- Personal information (names, emails, PII)
- Security credentials (API keys, passwords)
- Proprietary algorithms or trade secrets
- Copyrighted material without permission

If you accidentally ingest sensitive data, immediately:

1. Stop the service: `pkill -f "uvicorn src.api_server:app"`
2. Delete indexes: `rm -rf indexes/*`
3. Delete data: `rm -rf data/documents/*`
4. Review logs for exposure: `grep "sensitive_term" logs/`
5. Verify deletion: `git status` should show no uncommitted sensitive files

## Deployment Location

### Safe Deployment Locations

- ✓ Local developer machine (development only)
- ✓ Isolated test lab (air-gapped or restricted network)
- ✓ Docker container (with localhost port exposed to localhost only)
- ✓ Internal evaluation server (on private network, admin access only)

### Unsafe Deployment Locations

- ✗ Public cloud (without additional hardening: TLS, auth, rate limiting)
- ✗ Multi-tenant shared hosting
- ✗ Exposed to untrusted networks
- ✗ Production systems without security review

## Pre-Deployment Checklist

Run before starting pilot:

```bash
#!/bin/bash
set -e

echo "Security pre-flight checklist..."

# Check localhost binding
if grep -r "0.0.0.0" src/ >/dev/null; then
  echo "ERROR: Found binding to 0.0.0.0. Must bind to 127.0.0.1"
  exit 1
fi

# Check for shell execution
if grep -r "shell=True" src/ >/dev/null; then
  echo "ERROR: Found shell=True in subprocess calls. Must use safer alternatives"
  exit 1
fi

# Check for hardcoded secrets
if grep -rE "password|api_key|secret" src/ | grep -v "test" | grep -v "example" >/dev/null; then
  echo "WARNING: Found potential hardcoded secrets. Verify they are test data only."
fi

# Check file permissions
if [ -d indexes ] && [ "$(stat -c %a indexes)" != "755" ]; then
  echo "WARNING: indexes/ directory has unusual permissions. Verify as expected."
fi

echo "✓ Pre-flight checks passed"
```

## Post-Incident: If Breach Suspected

If you suspect unauthorized access or data exposure:

1. **STOP immediately**: `pkill -f "uvicorn src.api_server:app"`
2. **Preserve logs**: `cp logs/server.log logs/incident_$(date +%s).log`
3. **Disable network access**: Unplug network cable or disable network interface
4. **Review logs for access**: `grep -E "query|ingest|delete" logs/incident_*.log`
5. **Assess damage**: What documents were accessible? For how long?
6. **Notify stakeholders**: Report incident to relevant team/leadership
7. **Clean and rebuild**: `rm -rf indexes/ data/` and restart fresh

## Compliance Notes

### This Pilot Is NOT Compliant With

- SOC 2 (no audit logging, no access control)
- HIPAA (no encryption, multi-tenant isolation)
- PCI DSS (no authentication, no encryption)
- GDPR (no data deletion tracking, no access control)
- FedRAMP (no authorized deployment, no continuous monitoring)

**DO NOT use pilot for regulated data (health, financial, government).**

### Path to Production Hardening

If RALG proceeds from pilot to production:

1. **Phase 1:** Add TLS, basic authentication, rate limiting
2. **Phase 2:** Add audit logging, data deletion tracking, encryption at rest
3. **Phase 3:** Add multi-worker deployment, distributed coordination
4. **Phase 4:** Security review by external auditor
5. **Phase 5:** Formal compliance certification (SOC 2, etc.)

Each phase requires threat modeling, code review, and penetration testing.

---

## Contact

For security issues in pilot:

- Document the issue in evaluation/SECURITY_INCIDENT_LOG.md (internal use only)
- Do NOT publicly disclose pilot security issues
- Contact security team for guidance on remediation

---

**Pilot Security Status:** Local/Trusted Only  
**Production Readiness:** NOT READY (requires significant hardening)  
**Last Reviewed:** 2026-01-01  
**Next Review:** Before production deployment
