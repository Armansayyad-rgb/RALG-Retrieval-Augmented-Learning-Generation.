"""Document upload pipeline for the Gradio web UI.

Parses uploaded PDFs, DOCX, and TXT files, splits them into chunks using
the same logic as the static knowledge base, and merges the new chunks
into the running pipeline's retrieval index.

Design notes:

- We avoid hard dependencies on PyPDF2/python-docx by lazy-importing them
  only when the corresponding file type is uploaded. This keeps the
  basic chat UI working even if those packages are not installed.
- Chunk sizes mirror ``retriever_v2.load_chunks`` so retrieval scoring
  behaves identically on uploaded and built-in content.
- Index rebuild is O(N) over the full chunk list. For the demo corpus
  (~107k chunks) this is ~1s; well within an acceptable UI delay.

Provenance limitations (this checkpoint):

- page_number is always None. The current PDF/DOCX parsers do not
  preserve page boundaries during text extraction.  A future checkpoint
  may enhance page-level provenance.
- revision is always None. Real document versioning will be added later.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import uuid


from retriever_v2 import RuntimeChunk, build_index as build_index_v2


_LOGGER = logging.getLogger(__name__)

SUPPORTED_EXTS = {".txt", ".pdf", ".docx"}

# Upload size limits (bytes)
MAX_TXT_SIZE = 1 * 1024 * 1024   # 1 MiB
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MiB
MAX_DOCX_SIZE = 10 * 1024 * 1024  # 10 MiB
# Maximum extracted text length (characters)
MAX_EXTRACTED_TEXT_LEN = 5_000_000  # ~5 MiB of text

# Maximum length for a sanitized display filename
_MAX_DISPLAY_NAME_LEN = 200


def _size_limit(path: Path) -> int:
    """Return the size limit for a given file based on its extension."""
    ext = path.suffix.lower()
    if ext == ".txt":
        return MAX_TXT_SIZE
    if ext == ".pdf":
        return MAX_PDF_SIZE
    if ext == ".docx":
        return MAX_DOCX_SIZE
    return 0


def _sanitize_display_name(raw_name: str) -> str:
    """Produce a safe display filename from an untrusted raw name.

    - Extracts the basename (strips directory components).
    - Strips control characters.
    - Replaces path-traversal components.
    - Truncates to a reasonable length.
    - Never returns an empty string.
    """
    # Extract basename using both os.path and manual split for cross-platform
    name = os.path.basename(raw_name)
    # Also handle forward slashes on Windows
    if "/" in name:
        name = name.rsplit("/", 1)[-1]

    # Strip control characters (categories Cc, Cf)
    name = "".join(
        ch for ch in name
        if unicodedata.category(ch) not in ("Cc", "Cf")
    )

    # Remove any remaining path-traversal components
    name = name.replace("..", "").replace("~", "")

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()

    # Truncate
    if len(name) > _MAX_DISPLAY_NAME_LEN:
        name = name[:_MAX_DISPLAY_NAME_LEN]

    # Fallback
    if not name:
        name = "unnamed_document"

    return name


@dataclass
class UploadedDocument:
    """Record of a single uploaded file with provenance metadata."""

    name: str
    path: Path
    ext: str
    text: str
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    chunks: list[RuntimeChunk] = field(default_factory=list)
    chunk_count: int = 0
    upload_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
    source_type: str = "runtime_upload"
    revision: str | None = None

    @property
    def safe_display_name(self) -> str:
        """Sanitized filename safe for public/API/UI display."""
        return _sanitize_display_name(self.name)

    def to_dict(self) -> dict:
        """Public-facing document summary.  No absolute paths."""
        return {
            "document_id": self.doc_id,
            "document_name": self.safe_display_name,
            "extension": self.ext,
            "chunk_count": self.chunk_count,
            "upload_timestamp": self.upload_timestamp,
            "source_type": self.source_type,
            "revision": self.revision,
        }


def _read_text(path: Path) -> str:
    """Plain TXT reader."""
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    """PDF reader using PyPDF2 (lazy import)."""
    from PyPDF2 import PdfReader  # type: ignore

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n\n".join(parts)


def _read_docx(path: Path) -> str:
    """DOCX reader using python-docx (lazy import)."""
    from docx import Document as DocxDocument  # type: ignore

    doc = DocxDocument(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs)


def parse_file(path: Path) -> str:
    """Dispatch a single file to the right parser."""
    ext = path.suffix.lower()
    if ext == ".txt":
        return _read_text(path)
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".docx":
        return _read_docx(path)
    raise ValueError(f"Unsupported file type: {ext}")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"\s+")
# Approximate chunk size in words; matches the mean chunk size produced by
# retriever_v2.load_chunks (~120 words/sentence, ~5 sentences per chunk).
_CHUNK_WORDS = 500
_OVERLAP_WORDS = 50


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WORD_RE.sub(" ", text)
    return text.strip()


def chunk_text(
    text: str,
    doc_id: str,
    *,
    doc_name: str = "",
    extension: str = ".txt",
    upload_timestamp: str = "",
    revision: str | None = None,
    chunk_words: int = _CHUNK_WORDS,
    overlap: int = _OVERLAP_WORDS,
) -> list[RuntimeChunk]:
    """Split text into overlapping word-window chunks with full provenance.

    Each returned ``RuntimeChunk`` carries a ``metadata`` dict containing:

    - document_id
    - document_name
    - chunk_index  (0-based, deterministic for identical input)
    - source_type  ("runtime_upload")
    - extension
    - upload_timestamp
    - page_number  (always None for this checkpoint)
    - revision     (always None unless explicitly provided)

    Args:
        text: The raw text to chunk.
        doc_id: Unique identifier for the source document.
        doc_name: Human-readable document name (sanitized for display).
        extension: File extension of the original document.
        upload_timestamp: ISO-8601 UTC timestamp of the upload.
        revision: Optional revision/version string.
        chunk_words: Approximate number of words per chunk.
        overlap: Number of overlapping words between consecutive chunks.
    """
    text = _normalize_text(text)
    if not text:
        return []

    safe_name = _sanitize_display_name(doc_name) if doc_name else "unnamed"

    def _make_chunk(piece: str, idx: int) -> RuntimeChunk:
        return RuntimeChunk(piece, metadata={
            "document_id": doc_id,
            "document_name": safe_name,
            "chunk_index": idx,
            "source_type": "runtime_upload",
            "extension": extension,
            "upload_timestamp": upload_timestamp,
            "page_number": None,
            "revision": revision,
        })

    words = text.split(" ")
    if len(words) <= chunk_words:
        return [_make_chunk(text, 0)]

    step = max(1, chunk_words - overlap)
    chunks: list[RuntimeChunk] = []
    idx = 0
    for start in range(0, len(words), step):
        piece_words = words[start : start + chunk_words]
        if not piece_words:
            break
        piece = " ".join(piece_words)
        chunks.append(_make_chunk(piece, idx))
        idx += 1
        if start + chunk_words >= len(words):
            break
    return chunks


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

def _is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTS


def attach_documents(
    pipeline: dict,
    uploaded: list[UploadedDocument],
) -> int:
    """Merge uploaded chunks into the pipeline's chunks list and rebuild the index.

    Returns the total number of new chunks added.
    """
    new_chunks: list[RuntimeChunk] = []
    for doc in uploaded:
        if not doc.chunks:
            doc.chunks = chunk_text(
                doc.text,
                doc.doc_id,
                doc_name=doc.name,
                extension=doc.ext,
                upload_timestamp=doc.upload_timestamp,
                revision=doc.revision,
            )
        new_chunks.extend(doc.chunks)
        doc.chunk_count = len(doc.chunks)
    if not new_chunks:
        return 0

    # retriever_v2 expects a list of RuntimeChunk objects.
    pipeline["chunks"].extend(new_chunks)
    pipeline["retrieval_index"], pipeline["document_frequency"] = build_index_v2(
        pipeline["chunks"]
    )

    # Track uploads in the pipeline so the UI can list them.
    pipeline.setdefault("uploaded_docs", []).extend(
        [d.to_dict() for d in uploaded]
    )

    return len(new_chunks)


def remove_uploaded_document(pipeline: dict, document_id: str) -> int:
    """Remove all RuntimeChunk objects belonging to the given document_id.

    - Removes only chunks whose ``metadata["document_id"]`` exactly matches.
    - Leaves static corpus chunks untouched.
    - Leaves other uploaded documents untouched.
    - Rebuilds the lexical index and updates ``pipeline["uploaded_docs"]``.
    - Returns the number of chunks removed.
    - If ``document_id`` is not found, returns 0 without modifying pipeline.
    """
    chunks = pipeline.get("chunks", [])

    # Identify chunks to remove
    to_keep = []
    removed_count = 0
    for chunk in chunks:
        meta = getattr(chunk, "metadata", None)
        if (
            isinstance(meta, dict)
            and meta.get("document_id") == document_id
        ):
            removed_count += 1
        else:
            to_keep.append(chunk)

    if removed_count == 0:
        return 0

    pipeline["chunks"] = to_keep
    pipeline["retrieval_index"], pipeline["document_frequency"] = build_index_v2(
        to_keep
    )

    # Remove from uploaded_docs tracking
    uploaded_docs = pipeline.get("uploaded_docs", [])
    pipeline["uploaded_docs"] = [
        d for d in uploaded_docs
        if d.get("document_id") != document_id
    ]

    return removed_count


def process_uploads(
    pipeline: dict,
    file_paths: Iterable[str],
) -> tuple[list[UploadedDocument], list[str]]:
    """Parse a batch of uploaded files, return (parsed, errors).

    The pipeline is not modified here; call ``attach_documents`` after this
    step when the user explicitly confirms the upload.
    """
    parsed: list[UploadedDocument] = []
    errors: list[str] = []

    for raw in file_paths:
        path = Path(raw)
        if not path.exists():
            errors.append(f"Not found: {_sanitize_display_name(raw)}")
            continue
        if not _is_supported(path):
            errors.append(f"Unsupported file type: {_sanitize_display_name(path.name)}")
            continue
        # Size check
        size_limit = _size_limit(path)
        if size_limit and path.stat().st_size > size_limit:
            errors.append(
                f"File {_sanitize_display_name(path.name)} exceeds size limit "
                f"for {path.suffix.lower()} ({size_limit} bytes)"
            )
            continue

        # Parse file content — generic client error, details to logs only
        try:
            text = parse_file(path)
        except Exception:
            _LOGGER.exception("Failed to parse uploaded file: %s", path.name)
            errors.append(f"Unable to parse uploaded file.")
            continue

        # Empty or overly large extracted text check
        if not text.strip():
            errors.append(f"File {_sanitize_display_name(path.name)} contains no extractable text.")
            continue
        if len(text) > MAX_EXTRACTED_TEXT_LEN:
            errors.append(
                f"Extracted text from {_sanitize_display_name(path.name)} "
                f"exceeds maximum allowed length."
            )
            continue

        doc = UploadedDocument(
            name=path.name,
            path=path,
            ext=path.suffix.lower(),
            text=text,
        )
        parsed.append(doc)

    return parsed, errors
