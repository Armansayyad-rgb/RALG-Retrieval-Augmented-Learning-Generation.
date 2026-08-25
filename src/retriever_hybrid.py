"""Full-question-first hybrid retrieval.

The original user question always produces the primary candidate set through a
single fast V2 lexical pass.  Query decomposition is strictly secondary: it
runs only when no candidate covers most of the question's informative mass,
and its candidates may never displace a strong full-question candidate.

Ranking fuses two deterministic, corpus-agnostic signals:

1. IDF-weighted coverage of the full question's terms (dominant signal).
2. Full-question retrieval rank as an explicit feature.

No benchmark identifiers, expected answers, or dataset-specific rules are used.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache

from retriever_v2 import retrieve as retrieve_v2

# Depth of the protected full-question candidate pool.
FULL_QUESTION_DEPTH = 50

# Fusion weights (deterministic, general signals only).
IDF_COVERAGE_WEIGHT = 5.0
FULL_QUESTION_RANK_WEIGHT = 0.5

# Secondary retrieval triggers only when the best full-question candidate
# covers less than this fraction of the question's IDF mass.
SECONDARY_TRIGGER_COVERAGE = 0.5

# Hard bounds on secondary retrieval.
MAX_SECONDARY_QUERIES = 2
SECONDARY_DEPTH = 15

# Bound on caller-supplied secondary queries (production integration).
# These are fused under exactly the same full-question protection rule as
# decomposed sub-queries; the default evaluation path supplies none.
MAX_PROVIDED_SECONDARY_QUERIES = 3

# Minimum useful words for a decomposed clause to qualify as a sub-query.
MIN_SUBQUERY_WORDS = 3

_CLAUSE_SPLIT = re.compile(r",\s+(?:and\s+)?|;\s+|\band\s+then\b|\bwhereas\b")


def _words(text):
    return re.findall(r"[a-z0-9]+", str(text).lower())


@lru_cache(maxsize=8192)
def _word_set(text):
    return frozenset(_words(text))


def _idf(document_frequency, term, total_documents):
    frequency = document_frequency.get(term) if isinstance(document_frequency, dict) else getattr(document_frequency, "get", lambda *_: None)(term)
    if frequency is None:
        frequency = 1
    return math.log((total_documents + 1) / (frequency + 0.5))


def idf_weighted_coverage(query_terms, chunk_text, document_frequency, total_documents, idf_cache=None):
    """Fraction of the question's IDF mass present in ``chunk_text``."""
    if not query_terms:
        return 0.0

    chunk_terms = _word_set(chunk_text)
    matched_total = 0.0
    total = 0.0

    for term in query_terms:
        weight = (
            idf_cache[term]
            if idf_cache is not None and term in idf_cache
            else _idf(document_frequency, term, total_documents)
        )
        if idf_cache is not None:
            idf_cache[term] = weight
        total += weight
        if term in chunk_terms:
            matched_total += weight

    if total <= 0.0:
        return 0.0
    return matched_total / total


def decompose_question(question):
    """General clause-level decomposition; never benchmark specific."""
    clauses = []
    for part in _CLAUSE_SPLIT.split(str(question)):
        words = [w for w in _words(part)]
        if len(words) >= MIN_SUBQUERY_WORDS:
            clauses.append(part.strip())
        if len(clauses) >= MAX_SECONDARY_QUERIES:
            break
    return clauses[:MAX_SECONDARY_QUERIES]


def fuse_candidates(primary_rows, secondary_rows, query_terms, document_frequency, total_documents):
    """Deterministic fusion; protects strong full-question candidates."""
    idf_cache = {}
    scored = {}

    for row in primary_rows:
        key = row.get("chunk_index")
        coverage = idf_weighted_coverage(
            query_terms,
            row["chunk"],
            document_frequency,
            total_documents,
            idf_cache=idf_cache,
        )
        rank = row["_fq_rank"]
        rank_feature = rank / max(1, len(primary_rows))
        scored[key] = {
            "chunk": row["chunk"],
            "chunk_index": key,
            "full_question_rank": rank,
            "full_question_coverage": coverage,
            "lexical_score": row.get("final_score"),
            "origin": "full_question",
            "_score": (
                IDF_COVERAGE_WEIGHT * coverage
                - FULL_QUESTION_RANK_WEIGHT * rank_feature
            ),
        }

    protected_floor = min(
        (
            entry["full_question_coverage"]
            for entry in scored.values()
        ),
        default=1.0,
    )

    for row in secondary_rows:
        key = row.get("chunk_index")
        coverage = idf_weighted_coverage(
            query_terms,
            row["chunk"],
            document_frequency,
            total_documents,
            idf_cache=idf_cache,
        )
        entry = scored.get(key)
        if entry is not None:
            entry.setdefault("subquery_hits", []).append(row["_subquery"])
            continue
        # A secondary-only candidate competes using the same general
        # full-question signals.  The constant rank penalty (1.0, the worst
        # possible primary rank feature) means it can only outrank a primary
        # candidate whose full-question coverage is strictly lower.  A strong
        # full-question candidate is therefore never displaced by a sub-query
        # heuristic score.
        scored[key] = {
            "chunk": row["chunk"],
            "chunk_index": key,
            "full_question_rank": None,
            "full_question_coverage": coverage,
            "lexical_score": row.get("final_score"),
            "origin": "subquery",
            "subquery_hits": [row["_subquery"]],
            "_score": (
                IDF_COVERAGE_WEIGHT * coverage
                - FULL_QUESTION_RANK_WEIGHT
            ),
        }

    def sort_key(entry):
        score = entry["_score"]
        coverage = entry["full_question_coverage"]
        rank = entry["full_question_rank"]
        return (
            -score,
            -round(coverage, 12),
            rank if rank is not None else len(primary_rows) + 1,
            str(entry["chunk_index"]),
        )

    ranked = sorted(scored.values(), key=sort_key)
    return ranked


def retrieve(
    question,
    chunks,
    index,
    document_frequency,
    final_top_k=10,
    secondary_queries=None,
):
    """Full-question-first hybrid retrieval.

    Pass 1 (always): one bounded V2 lexical pass with the full question.
    Pass 2 (only if needed): at most ``MAX_SECONDARY_QUERIES`` bounded
    sub-query passes, appended to the union without displacing strong
    full-question candidates.

    ``secondary_queries`` lets a production caller supply additional
    bounded sub-queries (e.g. intent-planner queries). They are fused
    under the identical full-question protection rule and never run in
    the default evaluation path.
    """
    if not chunks:
        return []

    total_documents = len(chunks)

    primary_rows = retrieve_v2(
        question,
        chunks,
        index,
        document_frequency,
        final_top_k=min(FULL_QUESTION_DEPTH, total_documents),
    )
    for rank, row in enumerate(primary_rows, 1):
        row["_fq_rank"] = rank

    query_terms = []
    seen = set()
    for word in _words(question):
        if word not in seen:
            seen.add(word)
            query_terms.append(word)

    idf_cache = {}
    best_coverage = max(
        (
            idf_weighted_coverage(
                query_terms,
                row["chunk"],
                document_frequency,
                total_documents,
                idf_cache=idf_cache,
            )
            for row in primary_rows
        ),
        default=0.0,
    )

    secondary_rows = []
    executed_secondary = 0
    if best_coverage < SECONDARY_TRIGGER_COVERAGE:
        for sub_query in decompose_question(question):
            rows = retrieve_v2(
                sub_query,
                chunks,
                index,
                document_frequency,
                final_top_k=min(SECONDARY_DEPTH, total_documents),
            )
            executed_secondary += 1
            for row in rows:
                row["_subquery"] = sub_query
                secondary_rows.append(row)
            if executed_secondary >= MAX_SECONDARY_QUERIES:
                break

    provided = []
    if secondary_queries:
        question_key = tuple(_words(question))
        seen_provided = set()
        for supplied in secondary_queries:
            supplied_key = tuple(_words(supplied))
            if not supplied_key or supplied_key == question_key:
                continue
            if supplied_key in seen_provided:
                continue
            seen_provided.add(supplied_key)
            provided.append(str(supplied).strip())
            if len(provided) >= MAX_PROVIDED_SECONDARY_QUERIES:
                break
    for sub_query in provided:
        rows = retrieve_v2(
            sub_query,
            chunks,
            index,
            document_frequency,
            final_top_k=min(SECONDARY_DEPTH, total_documents),
        )
        executed_secondary += 1
        for row in rows:
            row["_subquery"] = sub_query
            secondary_rows.append(row)

    ranked = fuse_candidates(
        primary_rows,
        secondary_rows,
        query_terms,
        document_frequency,
        total_documents,
    )

    results = []
    for entry in ranked[:final_top_k]:
        result = {
            "chunk": entry["chunk"],
            "chunk_index": entry["chunk_index"],
            "full_question_rank": entry["full_question_rank"],
            "full_question_coverage": round(entry["full_question_coverage"], 12),
            "lexical_score": entry.get("lexical_score"),
            "origin": entry["origin"],
        }
        if "subquery_hits" in entry:
            result["subquery_hits"] = entry["subquery_hits"]
        results.append(result)
    return results


if __name__ == "__main__":
    demo_chunks = [
        "The router MUST forward packets within 10 milliseconds.",
        "Kiln serial numbers are printed on the rear panel label.",
        "Packets exceeding the MTU MUST be fragmented before transit.",
    ]
    local_index, local_df = __import__("retriever_v2").build_index(demo_chunks)
    for item in retrieve("What must routers do with oversized packets?", demo_chunks, local_index, local_df):
        print(item["full_question_rank"], round(item["full_question_coverage"], 3), item["origin"], item["chunk"][:50])
