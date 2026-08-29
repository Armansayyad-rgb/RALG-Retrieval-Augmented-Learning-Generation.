# Security

RALG Engine is designed for local and private document workflows. This document
describes the single-tenant deployment security profile for the hardening branch.

## Threat Model

| Asset | Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| API endpoints | Unauthorized access to query/ingest functions | Medium (high if exposed publicly) | Data exfiltration, unintended document modification | Optional bearer-token authentication via `API_TOKEN` env var; localhost-only by default |
| Document storage | Path traversal, unsafe filename execution | Low (with sanitization) | Remote code execution, data leakage | `_sanitize_display_name`, document ID validation, path confinement checks |
| Uploaded content | Malformed PDFs/DOCX with embedded macros | Medium | Host compromise | Lazy-imported parsers only; extensions strictly limited to .txt/.pdf/.docx |
| API body size | Denial-of-service via oversized requests | Medium | Resource exhaustion | `RequestSizeLimitMiddleware` with `MAX_API_REQUEST_BYTES = 1MB`; `UPLOAD_POLICY.max_batch_bytes = 50MB` |
| Rate abuse | Automated repeated queries/ingest | Medium | Resource exhaustion | Simple in-process rate safeguard (60 requests/min/IP) active only when `API_TOKEN` is set |
| Error disclosure | Stack traces or filesystem paths leaked to clients | Low (already handled) | Information leakage | Sanitized 500/422 responses; full details logged server-side only via `_LOGGER.exception()` |
| CORS misconfiguration | Wildcard origins with credentials | High (if not configured) | Cross-origin data exposure | CORS disabled by default; must set `CORS_ORIGINS` explicitly for production use |
| Secret exposure | `API_TOKEN` or other secrets committed to source | Low (human error) | Credential leakage | `API_TOKEN` must be set via environment variable; never committed to source |

## Supported Deployment Profile

### Single-tenant deployment security profile

This RALG Engine deployment is **single-tenant** only. There is no tenant isolation,
user authentication (beyond optional bearer token), or multi-tenant data segregation.

#### Local development mode (default, no configuration required)

- `API_TOKEN` env var unset → all endpoints open, no authentication required
- `WEBUI_HOST` defaults to `127.0.0.1` → Gradio local-only
- `CORS_ORIGINS` not set → CORS middleware not added (avoids unsafe wildcard creds)
- `API_TOKEN` can be set for local testing of auth flow

#### Remote / production deployment

- `API_TOKEN` env var **must be set** to a secret value → all endpoints except `/health`
  and `/ready` require `Authorization: Bearer <token>`
- `CORS_ORIGINS` env var **must be set** to a comma-separated list of allowed origins
  (e.g., `https://example.com,https://app.example.com`)
- `CORS_CREDENTIALS` may be set to `1` only when `CORS_ORIGINS` is explicitly set
  to specific origins (never `*` with credentials)
- `WEBUI_HOST` should be set to `127.0.0.1` or a specific host IP, NOT exposed
  to `0.0.0.0` on public networks without reverse proxy TLS termination
- Reverse proxy (nginx, traefik, etc.) must handle TLS termination
- All environment variables should be injected via the deployment platform (Docker
  secrets, Kubernetes ConfigMaps, systemd envfiles, etc.) — never hardcoded

#### Docker / docker-compose deployment

- Set `API_TOKEN` via environment override in `docker-compose.yml` or container
  runtime — NOT in the Dockerfile
- Set `CORS_ORIGINS` via environment override if exposing the Gradio UI beyond
  localhost
- `WEBUI_HOST=0.0.0.0` is acceptable inside a container network when coupled
  with reverse proxy TLS, but is NOT a security control itself

### What is NOT supported

- **Multi-tenant isolation**: No user-level data segregation. All documents live
  in a shared runtime space.
- **Enterprise authentication**: Only optional bearer-token via `API_TOKEN`. No
  LDAP, OAuth2, OpenID Connect, or JWT validation beyond exact string comparison.
- **TLS provisioning**: RALG does not provide TLS. A reverse proxy (nginx,
  Traefik, Caddy) must terminate TLS before traffic reaches RALG.
- **Distributed rate limiting**: The rate safeguard is single-process only; a
  distributed system requires external middleware (e.g., Redis-based limiting),
  which is out of scope for this prototype.
- **Content sanitization of retrieved text**: RALG does not sanitize or validate
  the content of retrieved documents beyond basic text extraction. Extracted text
  may contain malicious code, links, or metadata.

## reverse proxy / TLS recommendation

- Always deploy RALG Engine behind a reverse proxy that handles TLS termination.
- The reverse proxy should:
  - Terminate HTTPS connections
  - Forward authenticated requests to RALG on `127.0.0.1:8000`
  - Add security headers (HSTS, CSP) if not handled elsewhere
  - Enforce request size limits at the proxy level as a defense-in-depth measure
  - Log inbound request metadata (not RALG's responsibility)
- If no reverse proxy is used, bind `WEBUI_HOST` to `127.0.0.1` only and expose
  only the API (`uvicorn src.api_server:app --host 127.0.0.1 --port 8000`) through
  your chosen infrastructure's networking model.

## secret configuration

- `API_TOKEN`: Set this environment variable to a strong random string to enable
  bearer-token authentication on all non-health/ready endpoints.
  - Example: `export API_TOKEN="$(openssl rand -hex 32)"`
  - Never commit this value to source control or Dockerfiles
  - If unset, all endpoints remain open for local-development compatibility
- `CORS_ORIGINS`: Comma-separated list of allowed origins for production deployments.
  - Example: `export CORS_ORIGINS="https://ralg.example.com"`
  - Do not use `*` when `CORS_CREDENTIALS` is enabled
- `CORS_CREDENTIALS`: Set to `1` only when `CORS_ORIGINS` is a list of specific
  trusted origins. Default is `0` (disabled).
- `CORS_METHODS`: Comma-separated list of allowed HTTP methods. Default:
  `GET,POST,PUT,DELETE,OPTIONS`.
- `CORS_HEADERS`: Comma-separated list of allowed headers. Default:
  `Authorization,Content-Type`.
- All other environment variables (`DATA_DIR`, `WEBUI_HOST`, `WEBUI_PORT`,
  `RUNTIME_UPLOAD_DIR`) follow the existing env-var contract from `config.py`.

## local-only development mode

When running locally for development:

```bash
# No auth required, localhost-only Gradio UI
uvicorn src.api_server:app --host 127.0.0.1 --port 8000

# Or via docker-compose (development)
# WEBUI_HOST defaults to 127.0.0.1
```

Security checklist for production deployment:

- [ ] `API_TOKEN` is set to a strong random value and injected via the deployment
  platform (NOT committed to source)
- [ ] `CORS_ORIGINS` is set to specific trusted origins (never `*` with credentials)
- [ ] `CORS_CREDENTIALS` is `1` only when `CORS_ORIGINS` is explicitly configured
- [ ] Reverse proxy (nginx, Traefik, Caddy) is placed in front of RALG with TLS
  termination
- [ ] `WEBUI_HOST` is set to `127.0.0.1` or a specific internal host IP
- [ ] Document upload size limits are enforced at the reverse proxy level as
  defense-in-depth (complementary to `MAX_API_REQUEST_BYTES` and `UPLOAD_POLICY`)
- [ ] Log directories (`logs/`) are not web-accessible
- [ ] Model checkpoints (`checkpoints/`) are not served over HTTP
- [ ] Regular dependency vulnerability scanning is performed
- [ ] /health and /ready endpoints do not expose sensitive internal details
- [ ] Error responses do not leak stack traces or filesystem paths to clients
- [ ] The `api_server.py` security headers middleware is active on all responses
- [ ] Rate safeguard is active (automatically when `API_TOKEN` is set)
- [ ] Backup and retention policies for uploaded documents and logs are defined
- [ ] No placeholder/holdout benchmark data is present in production data directories