"""Bridge between Gradio callbacks and the rag_chat_v2 pipeline.

The CLI pipeline returns a result dictionary but does not expose the
retrieved chunks to the caller. ``chat_handler`` re-runs the same
retrieval functions to populate a ``sources`` list for the UI, so the
backend file is left untouched.
"""

from __future__ import annotations

import re
from typing import Any

from rag_chat_v2 import answer_question
from retriever_v2 import retrieve as retrieve_v2_fn, RuntimeChunk
from retriever_v4 import retrieve as retrieve_v4_fn


_TRACEABILITY_STOPWORDS = {
    "about", "after", "again", "also", "around", "because", "been",
    "being", "between", "both", "could", "does", "each", "from", "has",
    "have", "into", "more", "most", "other", "over", "same", "some",
    "such", "than", "that", "their", "there", "these", "they", "this",
    "those", "through", "under", "were", "which", "while", "with",
    "would", "your", "what", "when", "where", "who", "why", "how",
    "answer", "following", "several", "important", "ways", "main", "was",
    "are", "and", "the", "for", "not", "but", "its", "all", "can", "also",
    "is", "to", "of", "in", "on", "at", "be", "as", "by", "or",
}
_CONFLICT_ACTION_OPPOSITES = {
    "open": "close", "close": "open", "start": "stop", "stop": "start",
    "enable": "disable", "disable": "enable", "connect": "disconnect",
    "disconnect": "connect", "install": "remove", "remove": "install",
    "increase": "decrease", "decrease": "increase", "raise": "lower",
    "lower": "raise", "attach": "detach", "detach": "attach",
}
_CONFLICT_NUMBER_RE = re.compile(
    r"(?<![\w-])(?P<value>\d+(?:\.\d+)?)(?:\s*(?P<unit>[a-z%°][a-z0-9%°/-]*))?",
    re.IGNORECASE,
)
_CONFLICT_IDENTIFIER_RE = re.compile(
    r"\b(?:[A-Z][A-Z0-9]*(?:[-/][A-Z0-9]+)+|[A-Z]{2,}\d+[A-Z0-9]*)\b"
)
_CONFLICT_DIRECTIVE_RE = re.compile(
    r"\b(?P<polarity>must|should|required to|need to|do not|don't|never|avoid|"
    r"prohibited|only)\b(?P<action>.{0,90})",
    re.IGNORECASE,
)
_CONFLICT_ATTRIBUTE_TERMS = {
    "amount", "date", "duration", "identifier", "limit", "number", "period",
    "pressure", "price", "quantity", "revision", "serial", "temperature",
    "time", "value", "version", "voltage", "warranty", "year",
}
_CONFLICT_IDENTIFIER_ATTRIBUTE_TERMS = {
    "asset", "document", "identifier", "installed", "model", "revision",
    "serial", "terminal", "unit", "version",
}
CONFLICT_RESPONSE = (
    "I found conflicting evidence in the retrieved sources and cannot state "
    "a single settled answer."
)


def _traceability_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", (text or "").casefold())
        if token not in _TRACEABILITY_STOPWORDS
    }


def evidence_overlap(answer: str, sources: list[dict]) -> int:
    """Count distinct content terms shared by an answer and its previews."""
    answer_terms = _traceability_terms(answer)
    source_terms = _traceability_terms(
        " ".join(
            str(source.get("evidence") or source.get("preview", ""))
            for source in sources
        )
    )
    return len(answer_terms & source_terms)


def is_traceable_support(answer: str, supported: bool, sources: list[dict]) -> bool:
    """Require source presence and meaningful lexical evidence for support."""
    if not supported or not answer.strip() or not sources:
        return False
    required_terms = 1 if len(_traceability_terms(answer)) <= 4 else 2
    return evidence_overlap(answer, sources) >= required_terms


def _source_evidence(source: dict) -> str:
    return str(source.get("evidence") or source.get("preview") or "")


def _relevant_source_pairs(question: str, sources: list[dict]) -> list[tuple[str, str]]:
    if len(sources) < 2:
        return []
    scored = [source.get("score") for source in sources]
    numeric_scores = [float(score) for score in scored if isinstance(score, (int, float))]
    if numeric_scores:
        floor = max(numeric_scores) * 0.7
        selected = [
            _source_evidence(source)
            for source in sources
            if isinstance(source.get("score"), (int, float))
            and float(source["score"]) >= floor
        ]
    else:
        selected = [_source_evidence(source) for source in sources]
    question_terms = _traceability_terms(question)
    pairs = []
    for index, left in enumerate(selected):
        left_terms = _traceability_terms(left)
        if not question_terms.intersection(left_terms):
            continue
        for right in selected[index + 1 :]:
            right_terms = _traceability_terms(right)
            if question_terms.intersection(right_terms):
                pairs.append((left, right))
    return pairs


def _context_terms(text: str, start: int, end: int) -> set[str]:
    window = text[max(0, start - 90) : min(len(text), end + 90)]
    return _traceability_terms(window)


def _numeric_conflict(left: str, right: str) -> bool:
    left_values = [
        (match.group("value"), (match.group("unit") or "").casefold(),
         _context_terms(left, match.start(), match.end()))
        for match in _CONFLICT_NUMBER_RE.finditer(left)
    ]
    right_values = [
        (match.group("value"), (match.group("unit") or "").casefold(),
         _context_terms(right, match.start(), match.end()))
        for match in _CONFLICT_NUMBER_RE.finditer(right)
    ]
    for left_value, left_unit, left_context in left_values:
        for right_value, right_unit, right_context in right_values:
            if left_value == right_value or left_unit != right_unit:
                continue
            shared_context = left_context & right_context
            if len(shared_context) < 2:
                continue
            if left_unit and left_unit not in {"ad", "bc"}:
                return True
            if shared_context & _CONFLICT_ATTRIBUTE_TERMS:
                return True
    return False


def _identifier_conflict(left: str, right: str) -> bool:
    left_matches = list(_CONFLICT_IDENTIFIER_RE.finditer(left))
    right_matches = list(_CONFLICT_IDENTIFIER_RE.finditer(right))
    left_ids = {match.group().casefold() for match in left_matches}
    right_ids = {match.group().casefold() for match in right_matches}
    differing_left = left_ids - right_ids
    differing_right = right_ids - left_ids
    if not differing_left or not differing_right:
        return False
    left_context = set().union(
        *(_context_terms(left, match.start(), match.end())
          for match in left_matches
          if match.group().casefold() in differing_left)
    )
    right_context = set().union(
        *(_context_terms(right, match.start(), match.end())
          for match in right_matches
          if match.group().casefold() in differing_right)
    )
    return bool(
        left_context
        & right_context
        & _CONFLICT_IDENTIFIER_ATTRIBUTE_TERMS
    )


def _directive_conflict(left: str, right: str) -> bool:
    left_directives = []
    right_directives = []
    for text, target in ((left, left_directives), (right, right_directives)):
        for match in _CONFLICT_DIRECTIVE_RE.finditer(text):
            polarity = match.group("polarity").casefold()
            action_terms = _traceability_terms(match.group("action"))
            target.append((polarity, action_terms))
    for left_polarity, left_action in left_directives:
        for right_polarity, right_action in right_directives:
            if not left_action or not right_action:
                continue
            shared_action = left_action & right_action
            opposite_action = any(
                _CONFLICT_ACTION_OPPOSITES.get(term) in right_action
                for term in left_action
                if term in _CONFLICT_ACTION_OPPOSITES
            )
            action_verbs = set(_CONFLICT_ACTION_OPPOSITES)
            shared_object = (left_action & right_action) - action_verbs
            negative_polarities = {"do not", "don't", "never", "avoid"}
            opposite_polarity = (
                (left_polarity in negative_polarities)
                != (right_polarity in negative_polarities)
            )
            if (opposite_action and len(shared_object) >= 2) or (
                shared_action and opposite_polarity
            ):
                return True
    return False


def detect_evidence_conflict(question: str, sources: list[dict]) -> bool:
    """Detect materially conflicting claims among high-relevance evidence."""
    for left, right in _relevant_source_pairs(question, sources):
        if _numeric_conflict(left, right):
            return True
        if _identifier_conflict(left, right):
            return True
        if _directive_conflict(left, right):
            return True
    return False


def _format_v2_sources(results: list[dict], limit: int) -> list[dict]:
    """Normalize retriever_v2 chunks into a UI-friendly shape.

    For runtime-uploaded chunks (RuntimeChunk instances), provenance
    metadata fields are added directly to the source dict.
    """
    sources = []
    for rank, r in enumerate(results[:limit], start=1):
        chunk = r.get("chunk", "")
        entry = {
            "rank": rank,
            "id": r.get("chunk_index"),
            "preview": (chunk or "")[:240],
            "evidence": chunk or "",
            "score": round(float(r.get("final_score", 0.0)), 3),
        }
        # Enrich with provenance for runtime-uploaded chunks
        if isinstance(chunk, RuntimeChunk) and getattr(chunk, "metadata", None):
            meta = chunk.metadata
            entry["document_id"] = meta.get("document_id")
            entry["document_name"] = meta.get("document_name")
            entry["chunk_index"] = meta.get("chunk_index")
            entry["page_number"] = meta.get("page_number")
            entry["source_type"] = meta.get("source_type")
            entry["extension"] = meta.get("extension")
            entry["upload_timestamp"] = meta.get("upload_timestamp")
            entry["revision"] = meta.get("revision")
        sources.append(entry)
    return sources


def _format_v4_sources(retrieval: dict, limit: int) -> list[dict]:
    """Normalize retriever_v4 results into a UI-friendly shape."""
    chunks = (retrieval or {}).get("results") or []
    sources = []
    for rank, c in enumerate(chunks[:limit], start=1):
        chunk = c.get("chunk", "")
        entry = {
            "rank": rank,
            "id": c.get("chunk_index"),
            "preview": (chunk or "")[:240],
            "evidence": chunk or "",
            "score": round(float(c.get("final_score", 0.0)), 3),
        }
        if isinstance(chunk, RuntimeChunk) and getattr(chunk, "metadata", None):
            meta = chunk.metadata
            entry["document_id"] = meta.get("document_id")
            entry["document_name"] = meta.get("document_name")
            entry["chunk_index"] = meta.get("chunk_index")
            entry["page_number"] = meta.get("page_number")
            entry["source_type"] = meta.get("source_type")
            entry["extension"] = meta.get("extension")
            entry["upload_timestamp"] = meta.get("upload_timestamp")
            entry["revision"] = meta.get("revision")
        sources.append(entry)
    return sources


def collect_sources(
    pipeline: dict,
    question: str,
    top_k: int,
    answer: str | None = None,
) -> list[dict]:
    """Run the V2 extractor retriever to grab source chunks.

    The extractor path is the cheapest retrieval that produces
    ``chunk_index``/``final_score`` pairs and matches the chunks that
    surface as citations in the answer. If nothing matches, falls
    back to the V4 reasoning retriever.
    """
    chunks = pipeline["chunks"]
    idx = pipeline["retrieval_index"]
    df = pipeline["document_frequency"]

    try:
        v2_hits = retrieve_v2_fn(
            question, chunks, idx, df, final_top_k=top_k
        )
        if v2_hits:
            v2_sources = _format_v2_sources(v2_hits, top_k)
            if answer is None or is_traceable_support(answer, True, v2_sources):
                return v2_sources
        else:
            v2_sources = []
    except Exception:
        v2_sources = []

    try:
        v4 = retrieve_v4_fn(
            question, chunks, idx, df,
            final_top_k=top_k,
        )
        if v4 and v4.get("results"):
            v4_sources = _format_v4_sources(v4, top_k)
            if answer is None or is_traceable_support(answer, True, v4_sources):
                return v4_sources
    except Exception:
        pass

    return v2_sources


def chat_turn(
    pipeline: dict,
    question: str,
    top_k: int,
) -> dict[str, Any]:
    """Run one Q&A turn and return UI-ready fields.

    Returned keys:

    - question      the user input (echoed for the caller)
    - answer        assistant text from the pipeline
    - confidence    float | None
    - supported     bool
    - answer_type   str
    - intent        str
    - sources       list of {rank, id, preview, score}
    - error         str | None  (set on unexpected failure)
    """
    if not question or not question.strip():
        return {
            "question": question,
            "answer": "Please enter a question.",
            "confidence": None,
            "supported": False,
            "answer_type": "empty",
            "intent": "general",
            "sources": [],
            "error": None,
        }

    try:
        result = answer_question(pipeline, question.strip(), verbose=False)
    except Exception as exc:  # defensive — surface to UI instead of crashing
        return {
            "question": question,
            "answer": (
                "Sorry, something went wrong while answering. "
                "Please try again."
            ),
            "confidence": None,
            "supported": False,
            "answer_type": "error",
            "intent": "general",
            "sources": [],
            "error": repr(exc),
        }

    plan = result.get("runtime_plan") or {}
    intent = plan.get("intent") or "general"

    sources = collect_sources(pipeline, question, top_k, answer=result.get("answer", ""))
    supported = is_traceable_support(
        str(result.get("answer", "")), bool(result.get("supported", False)), sources
    )
    conflict = supported and detect_evidence_conflict(question, sources)

    confidence = result.get("confidence")
    if isinstance(confidence, (int, float)):
        confidence = float(confidence)
    else:
        confidence = None

    return {
        "question": question,
        "answer": CONFLICT_RESPONSE if conflict else result.get("answer", ""),
        "confidence": confidence,
        "supported": False if conflict else supported,
        "answer_type": "conflict" if conflict else result.get("answer_type", "unknown"),
        "intent": intent,
        "sources": sources,
        "error": None,
    }


def format_sources_markdown(sources: list[dict]) -> str:
    """Render a sources list as a small markdown block for the chat bubble.

    Kept compact: one line per source with the score and a short
    snippet. Long snippets are truncated with an ellipsis so a long
    sources list does not dominate the answer bubble.
    """
    if not sources:
        return ""
    lines = ["", "<details><summary>**Sources**</summary>", ""]
    for s in sources:
        snippet = s.get("preview", "").strip().replace("\n", " ")
        if len(snippet) > 160:
            snippet = snippet[:160].rstrip() + "..."
        lines.append(
            f"- `[{s['rank']}]` chunk **{s.get('id')}** "
            f"(score {s.get('score')}): {snippet}"
        )
    lines.append("")
    lines.append("</details>")
    return "\n".join(lines)
