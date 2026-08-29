"""Minimal local API server for RALG Engine.

Run from the project root:

    uvicorn src.api_server:app --host 127.0.0.1 --port 8000

Then query:

    curl -X POST http://127.0.0.1:8000/query \
      -H "Content-Type: application/json" \
      -d "{\"question\":\"What safety step is required before opening the electrical panel?\",\"top_k\":5}"

Ingest text:

    curl -X POST http://127.0.0.1:8000/ingest \
      -H "Content-Type: application/json" \
      -d '{"text":"Your document text here...","document_name":"my_doc"}'

Check stats:

    curl http://127.0.0.1:8000/stats

Health check:

    curl http://127.0.0.1:8000/health
"""

import os
import re
import sys
import time
import uuid
import logging
import hmac
import hashlib
from pathlib import Path
from threading import RLock, Lock
from typing import Any, Optional

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import runtime_guard
runtime_guard.enforce_python_311()

from rag_chat_v2 import answer_question, initialize_pipeline  # noqa: E402
from config import DATA_DIR  # noqa: E402
from webui.chat_handler import (  # noqa: E402
    build_answer_contract,
    collect_sources,
)
from runtime_architecture import execute_runtime  # noqa: E402
from webui.document_processor import (
    UploadedDocument,
    chunk_text,
    attach_documents,
    remove_uploaded_document,
    has_uploaded_document,
    _LIFECYCLE_LOCK,
)  # noqa: E402

_MAX_API_REQUEST_BYTES = 1 * 1024 * 1024
MAX_INGEST_TEXT_CHARS = 500_000
MAX_DOCUMENT_NAME_CHARS = 255
MAX_QUESTION_CHARS = 4_096
_SAFE_INTERNAL_ERROR = "Request processing failed."
_LOGGER = logging.getLogger(__name__)

# Public constant for request size limit (used by tests and middleware)
MAX_API_REQUEST_BYTES = _MAX_API_REQUEST_BYTES
MAX_DOCUMENT_ID_CHARS = 255

# Shared document-identifier safety check.
# Rejects empty/whitespace-only, path-traversal (".."), slash/backslash
# path-like values, control characters, and over-long values. Does NOT
# require the id to currently exist. Used by both the DELETE route and the
# document_ids query validator so the rules never diverge.
def _is_valid_document_id(value: str) -> bool:
    if not value or not value.strip():
        return False
    if len(value) > MAX_DOCUMENT_ID_CHARS:
        return False
    if ".." in value or "/" in value or "\\" in value:
        return False
    if any(ord(ch) < 0x20 for ch in value):
        return False
    return True


# Rate-limiting state (thread-safe, process-local)
_request_counts: dict[str, list[float]] = {}
_rate_lock = Lock()


def _safe_question_meta(question: str) -> str:
    length = len(question)
    digest = hashlib.sha256(question.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"len={length} hash={digest}"


def _client_ip(request: Request) -> str:
    client = request.scope.get("client")
    if isinstance(client, tuple):
        return client[0]
    return str(client) if client else "unknown"


def _log_security_event(status_code: int, request: Request, detail: str) -> None:
    ip = _client_ip(request)
    request_id = getattr(request.state, "request_id", "unknown")
    _LOGGER.warning(
        "security_event status=%d request_id=%s client_ip=%s detail=%s",
        status_code, request_id, ip, detail,
    )


# ---------------------------------------------------------------------------
# RequestSizeLimitMiddleware — from master; reject oversized API bodies before
# JSON parsing or model work.
# ---------------------------------------------------------------------------

class RequestSizeLimitMiddleware:
    """Reject oversized API bodies before JSON parsing or model work."""

    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        for key, value in scope.get("headers", []):
            if key == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        req = Request(scope)
                        await self._reject(scope, send, request=req)
                        return
                except ValueError:
                    req = Request(scope)
                    await self._reject(scope, send, request=req, status_code=400, message="Invalid request.")
                    return

        messages = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    req = Request(scope)
                    await self._reject(scope, send, request=req)
                    return
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break

        async def replay() -> dict:
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(
        scope: dict,
        send: Any,
        request: Request | None = None,
        status_code: int = 413,
        message: str = "Request body too large.",
    ) -> None:
        if status_code == 413 and request is not None:
            _log_security_event(413, request, "oversized_body")
        response = JSONResponse(status_code=status_code, content={"error": message})
        await response(scope, None, send)


app = FastAPI(
    title="RALG Engine API",
    version="0.1.0",
    description="Local evidence-grounded question answering API.",
)

app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_API_REQUEST_BYTES)


# ---------------------------------------------------------------------------
# CORS middleware — configured via environment variables; no wildcard creds default
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = (
    os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
)
CORS_CREDENTIALS: bool = os.getenv("CORS_CREDENTIALS", "0") == "1"
CORS_METHODS: list[str] = os.getenv(
    "CORS_METHODS", "GET,POST,PUT,DELETE,OPTIONS"
).split(",")
CORS_HEADERS: list[str] = os.getenv("CORS_HEADERS", "Authorization,Content-Type").split(",")

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=CORS_CREDENTIALS,
        allow_methods=CORS_METHODS,
        allow_headers=CORS_HEADERS,
    )
# When CORS_ORIGINS is empty we deliberately do NOT add the middleware,
# avoiding a default unsafe wildcard credential configuration.
# Deployments that need CORS should set the CORS_ORIGINS environment variable.


# ---------------------------------------------------------------------------
# Optional API authentication (single-tenant bearer token)
# Set API_TOKEN env var to require bearer token on all non-health/ready endpoints.
# When unset, all endpoints work as before (local-development compatibility).
# ---------------------------------------------------------------------------
API_TOKEN = os.getenv("API_TOKEN")

# Constant-time token comparison helper
_configured_token = API_TOKEN


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryRequest(StrictRequest):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_CHARS)
    top_k: int = Field(default=5, ge=1, le=20)
    include_sources: bool = True
    document_ids: Optional[list[str]] = Field(default=None, max_length=10)

    @field_validator("question")
    @classmethod
    def question_must_have_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value

    @field_validator("document_ids")
    @classmethod
    def document_ids_must_be_valid(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value
        for document_id in value:
            if not _is_valid_document_id(document_id):
                raise ValueError("document_ids contains an invalid identifier")
        return value


class QueryResponse(BaseModel):
    answer: str
    supported: bool
    confidence: Optional[float] = None
    answer_type: str
    sources: list[dict[str, Any]]
    latency_ms: float
    traceable: bool = False
    conflict: bool = False
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class IngestRequest(StrictRequest):
    text: str = Field(..., min_length=1, max_length=MAX_INGEST_TEXT_CHARS)
    document_name: Optional[str] = Field(default=None, max_length=MAX_DOCUMENT_NAME_CHARS)

    @field_validator("text")
    @classmethod
    def text_must_have_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value

    @field_validator("document_name")
    @classmethod
    def document_name_must_have_content(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("document_name must not be blank")
        return value


class IngestResponse(BaseModel):
    document_id: str
    document_name: str
    added_chunks: int
    total_chunks: int


class DocumentDeleteResponse(BaseModel):
    document_id: str
    deleted: bool
    chunks_removed: int


class StatsResponse(BaseModel):
    device: str
    model_loaded: bool
    chunk_count: int
    knowledge_files: list[str]
    uptime_seconds: float


# ---------------------------------------------------------------------------
# RequestValidationError handler — from master; sanitized 422 response
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "Invalid request."})


# ---------------------------------------------------------------------------
# Internal error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    _LOGGER.exception("Unhandled API error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": _SAFE_INTERNAL_ERROR})


# ---------------------------------------------------------------------------
# Security headers middleware — always active on every response
# FIX: call_next must receive the incoming Request, not a fresh Response()
# ---------------------------------------------------------------------------

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:
    """Add security hardening headers to every HTTP response."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# X-Request-ID correlation — generate when absent, validate caller-supplied IDs
# ---------------------------------------------------------------------------

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _safe_request_id(value: str) -> str:
    if not value or len(value) > 64 or _CONTROL_CHARS_RE.search(value):
        return str(uuid.uuid4())
    return value


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:
    raw_id = request.headers.get("X-Request-ID", "")
    safe_id = _safe_request_id(raw_id)
    request.state.request_id = safe_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = safe_id
    return response


# ---------------------------------------------------------------------------
# Simple in-process rate-limiting safeguard (active only when API_TOKEN set)
# ---------------------------------------------------------------------------

async def _rate_limit_check(scope: dict, max_requests: int = 60, window_sec: int = 60) -> bool:
    """Best-effort single-process rate safeguard.

    Only activated when API_TOKEN is configured. When API_TOKEN is absent
    (local-development mode) every request is allowed.
    """
    if not API_TOKEN:
        return True
    client_host = scope.get("client", None)
    if client_host is None:
        return True
    client_ip = client_host[0] if isinstance(client_host, tuple) else str(client_host)
    now = time.time()
    window = _request_counts.get(client_ip, [])
    # Drop timestamps outside the window
    window = [ts for ts in window if now - ts < window_sec]
    if len(window) >= max_requests:
        return False
    with _rate_lock:
        window = [ts for ts in _request_counts.get(client_ip, []) if now - ts < window_sec]
        if len(window) >= max_requests:
            return False
        window.append(now)
        _request_counts[client_ip] = window
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next) -> Response:
    if request.url.path in ("/health", "/ready"):
        return await call_next(request)
    if not await _rate_limit_check(request.scope):
        _log_security_event(429, request, "rate_limit_exceeded")
        return JSONResponse(status_code=429, content={"error": "Rate limit exceeded."})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Bearer token authentication check for single-tenant deployment
# ---------------------------------------------------------------------------

def _bearer_token_check(request: Request) -> Optional[JSONResponse]:
    """Check bearer token authorization.

    Returns None if authentication passes (or is disabled).
    Returns a JSONResponse with 401 if authentication fails.

    - When API_TOKEN is unset: no check; returns None (local-development mode).
    - When API_TOKEN is set: requires valid Bearer token; returns 401 on failure.
    Uses constant-time comparison for the token value.
    """

    # If no API_TOKEN configured, local-development mode: all requests allowed
    if not API_TOKEN:
        return None

    # API_TOKEN is set: extract and validate bearer token
    auth_header = request.headers.get("authorization")
    if not auth_header:
        _log_security_event(401, request, "missing_auth_header")
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized. API token required."},
        )

    if not auth_header.lower().startswith("bearer "):
        _log_security_event(401, request, "invalid_auth_scheme")
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized. API token required."},
        )

    token = auth_header[len("Bearer "):]
    if not hmac.compare_digest(token, API_TOKEN):
        _log_security_event(401, request, "invalid_token")
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized. Invalid API token."},
        )

    # Token is valid
    return None


# ---------------------------------------------------------------------------
# Route: /health — always public, no auth required
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Route: /ready — always public, no auth required
# ---------------------------------------------------------------------------

@app.get("/ready")
def ready() -> JSONResponse:
    """Report whether the initialized runtime can safely serve queries."""
    try:
        pipeline = get_pipeline()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "model_loaded": False,
                "tokenizer_loaded": False,
                "index_loaded": False,
                "chunk_count": 0,
                "retrieval_ready": False,
                "model_ready": False,
                "error": "Pipeline initialization failed.",
            },
        )

    model_loaded = pipeline.get("model") is not None
    tokenizer_loaded = pipeline.get("tokenizer") is not None
    index_loaded = (
        pipeline.get("retrieval_index") is not None
        and pipeline.get("document_frequency") is not None
    )
    chunk_count = len(pipeline.get("chunks", []) or [])
    retrieval_ready = bool(index_loaded and chunk_count > 0)
    model_ready = bool(model_loaded and tokenizer_loaded)
    ready_state = bool(retrieval_ready and model_ready and not _INIT_ERROR)
    payload = {
        "ready": ready_state,
        "model_loaded": model_loaded,
        "tokenizer_loaded": tokenizer_loaded,
        "index_loaded": index_loaded,
        "chunk_count": chunk_count,
        "retrieval_ready": retrieval_ready,
        "model_ready": model_ready,
        "error": None if ready_state else "Runtime is not ready.",
    }
    return JSONResponse(status_code=200 if ready_state else 503, content=payload)


# ---------------------------------------------------------------------------
# Route: /stats — public (no auth required), rate-limited when API_TOKEN active
# ---------------------------------------------------------------------------

@app.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    pipeline = get_pipeline()
    knowledge_files = [
        p.name for p in DATA_DIR.glob("*.txt")
    ] if DATA_DIR.exists() else []
    return StatsResponse(
        device=pipeline.get("device", "unknown"),
        model_loaded=pipeline.get("model") is not None,
        chunk_count=len(pipeline.get("chunks", [])),
        knowledge_files=knowledge_files,
        uptime_seconds=round(time.perf_counter() - _START_TIME, 2),
    )


# ---------------------------------------------------------------------------
# Route: /documents — protected when API_TOKEN active; document_id validated
# FIX: inject FastAPI Request explicitly
# ---------------------------------------------------------------------------

@app.get("/documents", response_model=list[dict[str, Any]])
def documents(request: Request = None) -> list[dict[str, Any]]:
    """List safe public metadata for runtime-uploaded documents."""
    if request is not None:
        error = _bearer_token_check(request)
        if error:
            return error
    return [
        {key: value for key, value in doc.items() if key != "path"}
        for doc in get_pipeline().get("uploaded_docs", [])
        if isinstance(doc, dict)
    ]


@app.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(document_id: str, request: Request = None) -> DocumentDeleteResponse:
    """Delete one runtime document and its persisted content."""
    if not _is_valid_document_id(document_id):
        return JSONResponse(status_code=400, content={"error": "Invalid document ID."})
    if request is not None:
        error = _bearer_token_check(request)
        if error:
            return error

    request_id = getattr(request.state, "request_id", "unknown") if request else "unknown"
    started = time.perf_counter()
    pipeline = get_pipeline()
    known = has_uploaded_document(pipeline, document_id)
    if not known:
        return JSONResponse(status_code=404, content={"error": "Document not found."})
    removed = remove_uploaded_document(pipeline, document_id)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    _LOGGER.info(
        "lifecycle_delete request_id=%s document_id=%s chunks_removed=%d latency_ms=%.2f",
        request_id, document_id, removed, latency_ms,
    )
    return DocumentDeleteResponse(
        document_id=document_id, deleted=True, chunks_removed=removed
    )


# ---------------------------------------------------------------------------
# Route: /query — protected when API_TOKEN active
# FIX: separate payload model from Request auth parameter
# ---------------------------------------------------------------------------

@app.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, request: Request = None) -> QueryResponse:
    if request is not None:
        error = _bearer_token_check(request)
        if error:
            return error

    request_id = getattr(request.state, "request_id", "unknown") if request else "unknown"
    question_meta = _safe_question_meta(payload.question.strip())
    scope_count = len(payload.document_ids) if payload.document_ids else 0
    started = time.perf_counter()
    pipeline = get_pipeline()

    try:
        with _LIFECYCLE_LOCK:
            execution = execute_runtime(
                pipeline,
                payload.question.strip(),
                payload.top_k,
                answer_fn=answer_question,
                contract_fn=build_answer_contract,
                sources_fn=collect_sources,
                document_ids=payload.document_ids,
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        _LOGGER.info(
            "lifecycle_query request_id=%s question=%s top_k=%d scope_count=%d latency_ms=%.2f supported=%s answer_type=%s conflict=%s",
            request_id, question_meta, payload.top_k, scope_count,
            latency_ms, execution.supported, execution.answer_type, execution.conflict,
        )

        return QueryResponse(
            answer=execution.answer,
            supported=execution.supported,
            confidence=execution.confidence,
            answer_type=execution.answer_type,
            sources=execution.sources if payload.include_sources else [],
            latency_ms=execution.observability["latency_ms"],
            traceable=execution.traceable,
            conflict=execution.conflict,
            provenance=execution.provenance,
            error=execution.error,
        )

    except Exception:
        _LOGGER.exception("Query processing failed")
        return JSONResponse(
            status_code=500,
            content={"error": _SAFE_INTERNAL_ERROR},
        )


# ---------------------------------------------------------------------------
# Route: /ingest — protected when API_TOKEN active
# FIX: separate payload model from Request auth parameter
# ---------------------------------------------------------------------------

@app.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest, request: Request = None) -> IngestResponse:
    if request is not None:
        error = _bearer_token_check(request)
        if error:
            return error

    request_id = getattr(request.state, "request_id", "unknown") if request else "unknown"
    started = time.perf_counter()
    pipeline = get_pipeline()

    doc_name = payload.document_name or f"doc_{int(time.time())}"
    doc = UploadedDocument(
        name=doc_name,
        path=Path(doc_name),
        ext=".txt",
        text=payload.text,
    )

    doc.chunks = chunk_text(
        doc.text,
        doc.doc_id,
        doc_name=doc.name,
        extension=doc.ext,
        upload_timestamp=doc.upload_timestamp,
        revision=doc.revision,
    )
    doc.chunk_count = len(doc.chunks)

    added = attach_documents(pipeline, [doc])
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    _LOGGER.info(
        "lifecycle_ingest request_id=%s document_id=%s added_chunks=%d latency_ms=%.2f",
        request_id, doc.doc_id, added, latency_ms,
    )

    return IngestResponse(
        document_id=doc.doc_id,
        document_name=doc.safe_display_name,
        added_chunks=added,
        total_chunks=len(pipeline.get("chunks", [])),
    )


# ---------------------------------------------------------------------------
# Pipeline globals and helpers
# ---------------------------------------------------------------------------

_PIPELINE: dict[str, Any] | None = None
_INIT_ERROR: Exception | None = None
_PIPELINE_LOCK = RLock()
_START_TIME = time.perf_counter()


def get_pipeline() -> dict[str, Any]:
    global _PIPELINE, _INIT_ERROR
    with _PIPELINE_LOCK:
        if _PIPELINE is None:
            if _INIT_ERROR is not None:
                raise RuntimeError("Pipeline initialization previously failed.")
            try:
                _PIPELINE = initialize_pipeline()
            except Exception as exc:
                _INIT_ERROR = exc
                _LOGGER.exception("Pipeline initialization failed")
                raise
    return _PIPELINE