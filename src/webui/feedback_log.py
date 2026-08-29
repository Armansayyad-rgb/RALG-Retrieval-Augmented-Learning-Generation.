"""Append-only feedback logger.

Records thumbs up / down votes for assistant answers in
``logs/webui_feedback.jsonl`` (one JSON object per line). Each row carries
enough context to compute evaluation metrics later: timestamp, the user's
question, the assistant's answer, the intent / answer type / confidence
reported by the pipeline, and the vote value (``+1`` for thumbs up,
``-1`` for thumbs down).

Design constraints:

- Append-only: never rewrite existing rows.
- Atomic write per line so a crash mid-write cannot corrupt the log.
- Schema versioned (``schema_version=1``) so future migrations are cheap.
- No PII beyond what the user typed; we do not log IP, user-agent, etc.
- Privacy mode controlled by RALG_FEEDBACK_LOG_ENABLED (default: enabled).
  When disabled, feedback is not persisted. When enabled, raw text is
  replaced with safe hashes and evidence text is stripped.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from webui.config import FEEDBACK_LOG


SCHEMA_VERSION = 1
_FEEDBACK_ENABLED = os.getenv("RALG_FEEDBACK_LOG_ENABLED", "1") == "1"


def _safe_text_hash(text: str) -> str:
    if not text:
        return "empty"
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:8]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    """Append a single JSON object to ``path``.

    We open the destination in append mode so concurrent writers (the
    webui is single-process, but a debugger running alongside is not)
    extend rather than truncate. ``flush`` + ``os.fsync`` make sure the
    kernel hands the bytes to disk before we return — that way a crash
    immediately after a vote does not lose the row.
    """
    _ensure_parent(path)
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def log_feedback(
    vote: int,
    *,
    question: str,
    answer: str,
    intent: str = "",
    answer_type: str = "",
    confidence: float | None = None,
    supported: bool | None = None,
    sources: list[dict] | None = None,
    extra: dict[str, Any] | None = None,
    log_path: Path | None = None,
) -> Path | None:
    """Append one feedback row.

    Parameters
    ----------
    vote
        ``+1`` for thumbs up, ``-1`` for thumbs down. Any other value is
        normalised to ``0`` (a neutral record).
    question, answer
        Echoed back from the chat bubble.
    intent, answer_type, confidence, supported
        Pipeline metadata for the answer.
    sources
        Optional list of source dicts (already JSON-serialisable).
    extra
        Optional bag of additional fields to persist.

    Returns
    -------
    Path | None
        The log file path that was written, or None if logging is disabled.
    """
    if not _FEEDBACK_ENABLED:
        return None

    if vote not in (-1, 0, 1):
        vote = 0

    safe_sources = []
    for source in (sources or []):
        safe = dict(source)
        safe.pop("evidence", None)
        safe_sources.append(safe)

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "vote": vote,
        "question": _safe_text_hash(question),
        "answer": _safe_text_hash(answer),
        "intent": intent,
        "answer_type": answer_type,
        "confidence": confidence,
        "supported": supported,
        "sources": safe_sources,
    }
    if extra:
        record["extra"] = extra

    target = Path(log_path) if log_path else FEEDBACK_LOG
    _atomic_append_jsonl(target, record)
    return target


__all__ = ["log_feedback", "SCHEMA_VERSION"]
