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

from __future__ import annotations

import sys
import time
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_chat_v2 import answer_question, initialize_pipeline  # noqa: E402
from config import DATA_DIR  # noqa: E402
from webui.chat_handler import (  # noqa: E402
    CONFLICT_RESPONSE,
    collect_sources,
    detect_evidence_conflict,
    is_traceable_support,
)
from webui.document_processor import (
    UploadedDocument,
    chunk_text,
    attach_documents,
)  # noqa: E402

MAX_API_REQUEST_BYTES = 1 * 1024 * 1024
MAX_INGEST_TEXT_CHARS = 500_000
MAX_DOCUMENT_NAME_CHARS = 255
MAX_QUESTION_CHARS = 4_096
_SAFE_INTERNAL_ERROR = "Request processing failed."
_LOGGER = logging.getLogger(__name__)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryRequest(StrictRequest):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_CHARS)
    top_k: int = Field(default=5, ge=1, le=20)
    include_sources: bool = True

    @field_validator("question")
    @classmethod
    def question_must_have_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class QueryResponse(BaseModel):
    answer: str
    supported: bool
    confidence: float | None
    answer_type: str
    sources: list[dict[str, Any]]
    latency_ms: float
    error: str | None = None


class IngestRequest(StrictRequest):
    text: str = Field(..., min_length=1, max_length=MAX_INGEST_TEXT_CHARS)
    document_name: str | None = Field(default=None, max_length=MAX_DOCUMENT_NAME_CHARS)

    @field_validator("text")
    @classmethod
    def text_must_have_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value

    @field_validator("document_name")
    @classmethod
    def document_name_must_have_content(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("document_name must not be blank")
        return value


class IngestResponse(BaseModel):
    document_name: str
    added_chunks: int
    total_chunks: int


class StatsResponse(BaseModel):
    device: str
    model_loaded: bool
    chunk_count: int
    knowledge_files: list[str]
    uptime_seconds: float


app = FastAPI(
    title="RALG Engine API",
    version="0.1.0",
    description="Local evidence-grounded question answering API.",
)


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
                        await self._reject(scope, send)
                        return
                except ValueError:
                    await self._reject(scope, send, status_code=400, message="Invalid request.")
                    return

        messages = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    await self._reject(scope, send)
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
        status_code: int = 413,
        message: str = "Request body too large.",
    ) -> None:
        response = JSONResponse(status_code=status_code, content={"error": message})
        await response(scope, None, send)


app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_API_REQUEST_BYTES)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "Invalid request."})


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    _LOGGER.exception("Unhandled API error", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": _SAFE_INTERNAL_ERROR})

_PIPELINE: dict[str, Any] | None = None
_START_TIME = time.perf_counter()


def get_pipeline() -> dict[str, Any]:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = initialize_pipeline()
    return _PIPELINE


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    started = time.perf_counter()
    pipeline = get_pipeline()

    try:
        result = answer_question(
            pipeline,
            request.question.strip(),
            verbose=False,
        )
        # Grounding and conflict checks must not depend on whether the caller
        # chooses to display sources. Collect evidence internally, then omit it
        # from the response when include_sources=False.
        grounding_sources = collect_sources(
            pipeline,
            request.question.strip(),
            request.top_k,
            answer=str(result.get("answer", "")),
        )

        confidence = result.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = None

        answer = str(result.get("answer", ""))
        supported = is_traceable_support(
            answer, bool(result.get("supported", False)), grounding_sources
        )
        conflict = supported and detect_evidence_conflict(
            request.question.strip(), grounding_sources
        )
        if conflict:
            answer = CONFLICT_RESPONSE
            supported = False
            confidence = None

        return QueryResponse(
            answer=answer,
            supported=supported,
            confidence=float(confidence) if confidence is not None else None,
            answer_type="conflict" if conflict else str(result.get("answer_type", "unknown")),
            sources=grounding_sources if request.include_sources else [],
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    except Exception:
        _LOGGER.exception("Query processing failed")
        return QueryResponse(
            answer="",
            supported=False,
            confidence=None,
            answer_type="error",
            sources=[],
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            error=_SAFE_INTERNAL_ERROR,
        )


@app.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    """Ingest plain text content into the running pipeline.

    Chunks the text using the same logic as the static knowledge base,
    merges chunks into the pipeline, and rebuilds the retrieval index.
    """
    pipeline = get_pipeline()

    doc_name = request.document_name or f"doc_{int(time.time())}"
    doc = UploadedDocument(
        name=doc_name,
        path=Path(doc_name),
        ext=".txt",
        text=request.text,
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

    return IngestResponse(
        document_name=doc.safe_display_name,
        added_chunks=added,
        total_chunks=len(pipeline.get("chunks", [])),
    )
