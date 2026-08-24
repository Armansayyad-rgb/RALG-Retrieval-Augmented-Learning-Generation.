import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import torch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import KNOWLEDGE_FILES  # noqa: E402

MAX_CONTEXT_CHARS = 900

LEXICAL_TOP_K = 20
FACTUAL_TOP_K = 120
FINAL_TOP_K = 5

# Boost applied to runtime-ingested document chunks to prefer them over static KB
INGESTED_CHUNK_BOOST = 5.0


class LexicalIndex(list):
    """Per-chunk term counts plus an exact term-to-chunk postings index."""

    def __init__(self, entries=(), postings=None, runtime_indices=()):
        super().__init__(entries)
        self.postings = postings or {}
        self.runtime_indices = list(runtime_indices)


class RuntimeChunk(str):
    """String-compatible chunk marker for explicitly ingested content.

    Accepts optional metadata dict stored in the instance for provenance.
    """
    def __new__(cls, text, metadata=None):
        obj = str.__new__(cls, text)
        obj.metadata = metadata or {}
        return obj


STOPWORDS = {
    "the", "a", "an", "and", "or", "but",
    "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "was",
    "are", "were", "be", "been",
    "what", "when", "where", "why", "how",
    "did", "does", "do",
}


# --------------------------------------------------
# Text helpers
# --------------------------------------------------

def clean_text(text):
    text = text.replace(
        "@-@",
        "-",
    )

    text = text.replace(
        "@.@",
        ".",
    )

    text = text.replace(
        "@,@",
        ",",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def words(text):
    return re.findall(
        r"[a-z0-9']+",
        text.lower(),
    )


def useful_words(text):
    return [
        word
        for word in words(
            text
        )
        if word not in STOPWORDS
        and len(word) >= 2
    ]


# --------------------------------------------------
# Chunk loading
# --------------------------------------------------

def load_chunks(paths):
    print(
        "Loading knowledge..."
    )

    if isinstance(
        paths,
        (str, Path),
    ):
        paths = [
            Path(
                paths
            )
        ]

    chunks = []

    for path in paths:
        path = Path(
            path
        )

        print(
            "Loading:",
            path,
        )

        if not path.exists():
            print(
                "WARNING: knowledge file "
                "not found:",
                path,
            )
            continue

        file_chunks = 0

        with path.open(
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as f:

            for line in f:
                line = clean_text(
                    line
                )

                if len(line) < 80:
                    continue

                sentences = re.split(
                    r"(?<=[.!?])\s+",
                    line,
                )

                current = []
                current_length = 0

                for sentence in sentences:
                    sentence = (
                        sentence.strip()
                    )

                    if not sentence:
                        continue

                    if (
                        current
                        and (
                            current_length
                            + len(sentence)
                            > MAX_CONTEXT_CHARS
                        )
                    ):
                        chunk = " ".join(
                            current
                        )

                        if len(chunk) >= 80:
                            chunks.append(
                                chunk
                            )

                            file_chunks += 1

                        current = []
                        current_length = 0

                    current.append(
                        sentence
                    )

                    current_length += (
                        len(sentence)
                        + 1
                    )

                if current:
                    chunk = " ".join(
                        current
                    )

                    if len(chunk) >= 80:
                        chunks.append(
                            chunk
                        )

                        file_chunks += 1

        print(
            "Chunks loaded from file:",
            file_chunks,
        )

    print(
        "Total knowledge chunks:",
        len(chunks),
    )

    return chunks


# --------------------------------------------------
# Lexical index
# --------------------------------------------------

def build_index(chunks):
    print(
        "Building lexical index..."
    )

    index = LexicalIndex()
    document_frequency = Counter()
    postings = {}
    runtime_indices = []

    for index_position, chunk in enumerate(chunks):
        counts = Counter(
            words(
                chunk
            )
        )

        index.append(
            counts
        )

        for word in counts:
            document_frequency[
                word
            ] += 1
            postings.setdefault(word, []).append(index_position)

        if isinstance(chunk, RuntimeChunk):
            runtime_indices.append(index_position)

    index.postings = postings
    index.runtime_indices = runtime_indices

    return (
        index,
        document_frequency,
    )


def extend_index(index, document_frequency, chunks, start_index):
    """Append new chunks to an existing exact lexical index in O(new chunks)."""
    if not isinstance(index, LexicalIndex):
        raise TypeError("index must be a LexicalIndex")
    if start_index != len(index):
        raise ValueError("start_index must match the current index length")

    for index_position, chunk in enumerate(chunks, start=start_index):
        counts = Counter(words(chunk))
        index.append(counts)
        for word in counts:
            document_frequency[word] += 1
            index.postings.setdefault(word, []).append(index_position)
        if isinstance(chunk, RuntimeChunk):
            index.runtime_indices.append(index_position)


# --------------------------------------------------
# Question parsing
# --------------------------------------------------

def subject_from_question(
    question,
):
    patterns = [
        r"when was (.+?) founded\??$",
        r"when was (.+?) established\??$",
        r"when was (.+?) born\??$",
        r"when was (.+?) released\??$",
        r"when was (.+?) published\??$",
        r"(?:who or what|what|who) "
        r"was (.+?) named after\??$",
        r"why did (.+?) fall\??$",
        r"why was (.+?) .+?\??$",
    ]

    for pattern in patterns:
        match = re.match(
            pattern,
            question.strip(),
            flags=re.IGNORECASE,
        )

        if match:
            return (
                match
                .group(1)
                .strip()
                .rstrip(".?!")
            )

    return None


def detect_factual_relation(
    question,
):
    q = question.lower().strip()

    if re.match(
        r"when was .+ born\??$",
        q,
    ):
        return "born"

    if re.match(
        r"when was .+ founded\??$",
        q,
    ):
        return "founded"

    if re.match(
        r"when was .+ established\??$",
        q,
    ):
        return "established"

    if re.match(
        r"when was .+ released\??$",
        q,
    ):
        return "released"

    if re.match(
        r"when was .+ published\??$",
        q,
    ):
        return "published"

    if "named after" in q:
        return "named_after"

    return None


# --------------------------------------------------
# Stage 1: lexical scoring
# --------------------------------------------------

@lru_cache(maxsize=1024)
def _cached_query_counts(question):
    return tuple(Counter(useful_words(question)).items())


def lexical_score(
    question,
    document_counts,
    document_frequency,
    total_documents,
    query_counts=None,
):
    if query_counts is None:
        query_counts = _cached_query_counts(question)

    score = 0.0

    for word, query_count in query_counts:

        tf = document_counts.get(
            word,
            0,
        )

        if tf == 0:
            continue

        df = document_frequency.get(
            word,
            0,
        )

        idf = (
            1.0
            + torch.log(
                torch.tensor(
                    (
                        total_documents
                        + 1
                    )
                    / (
                        df
                        + 1
                    )
                )
            ).item()
        )

        score += (
            min(
                tf,
                3,
            )
            * query_count
            * idf
        )

    return score


# --------------------------------------------------
# Relation-aware candidate bonus
# --------------------------------------------------

def factual_candidate_bonus(
    question,
    chunk,
):
    relation = detect_factual_relation(
        question
    )

    if relation is None:
        return 0.0

    subject = subject_from_question(
        question
    )

    if not subject:
        return 0.0

    c = chunk.lower()
    subject_lower = subject.lower()

    if subject_lower not in c:
        return 0.0

    bonus = 8.0

    if relation == "born":

        direct_pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,60}}"
            rf"\b(?:was\s+)?born\b"
        )

        reverse_pattern = (
            rf"\bborn\b"
            rf".{{0,60}}"
            rf"\b{re.escape(subject_lower)}\b"
        )

        if re.search(
            direct_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 40.0

        if re.search(
            reverse_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 30.0

        if re.search(
            r"\bborn\s+(?:on|in)\b",
            c,
        ):
            bonus += 2.0

        if re.search(
            r"\b(?:18|19|20)\d{2}\b",
            c,
        ):
            bonus += 2.0

    elif relation == "founded":

        direct_pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\bfounded\b"
        )

        if re.search(
            direct_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 36.0

        elif "founded" in c:
            bonus += 6.0

    elif relation == "established":

        direct_pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\bestablished\b"
        )

        if re.search(
            direct_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 36.0

        elif "established" in c:
            bonus += 6.0

    elif relation == "released":

        direct_pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\breleased\b"
        )

        if re.search(
            direct_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 36.0

        elif "released" in c:
            bonus += 6.0

    elif relation == "published":

        direct_pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\bpublished\b"
        )

        if re.search(
            direct_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 36.0

        elif "published" in c:
            bonus += 6.0

    elif relation == "named_after":

        direct_pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\bnamed after\b"
        )

        if re.search(
            direct_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 36.0

        elif "named after" in c:
            bonus += 6.0

    return bonus


# --------------------------------------------------
# Candidate search
# --------------------------------------------------

def retrieve_candidates(
    question,
    chunks,
    index,
    document_frequency,
    top_k=LEXICAL_TOP_K,
):
    total_documents = len(
        chunks
    )

    factual_relation = (
        detect_factual_relation(
            question
        )
    )

    query_counts = _cached_query_counts(question)
    query_terms = {word for word, _ in query_counts}
    postings = getattr(index, "postings", None)
    if isinstance(postings, dict):
        candidate_indices = set()
        for term in query_terms:
            candidate_indices.update(postings.get(term, ()))
        candidates = ((i, index[i]) for i in sorted(candidate_indices))
    else:
        candidates = enumerate(index)

    scored = []

    for i, document_counts in candidates:
        lexical = lexical_score(
            question,
            document_counts,
            document_frequency,
            total_documents,
            query_counts=query_counts,
        )

        factual_bonus = 0.0

        if factual_relation:
            factual_bonus = (
                factual_candidate_bonus(
                    question,
                    chunks[i],
                )
            )

        ingested_boost = (
            INGESTED_CHUNK_BOOST
            if isinstance(chunks[i], RuntimeChunk)
            else 0.0
        )

        candidate_score = (
            lexical
            + factual_bonus
            + ingested_boost
        )

        if candidate_score > 0:
            scored.append(
                (
                    candidate_score,
                    lexical,
                    factual_bonus,
                    i,
                    chunks[i],
                )
            )

    scored.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return scored[
        :top_k
    ]


# --------------------------------------------------
# Question-aware reranking
# --------------------------------------------------

def question_pattern_bonus(
    question,
    chunk,
):
    q = question.lower()
    c = chunk.lower()

    bonus = 0.0

    subject = subject_from_question(
        question
    )

    subject_lower = (
        subject.lower()
        if subject
        else None
    )

    # ------------------------------------------
    # Birth relation
    # ------------------------------------------

    if "born" in q and subject_lower:

        direct_pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,60}}"
            rf"\b(?:was\s+)?born\b"
        )

        reverse_pattern = (
            rf"\bborn\b"
            rf".{{0,60}}"
            rf"\b{re.escape(subject_lower)}\b"
        )

        if re.search(
            direct_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 30.0

        elif re.search(
            reverse_pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 20.0

    # ------------------------------------------
    # Founded
    # ------------------------------------------

    if "founded" in q and subject_lower:

        pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\bfounded\b"
        )

        if re.search(
            pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 24.0

    # ------------------------------------------
    # Established
    # ------------------------------------------

    if "established" in q and subject_lower:

        pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\bestablished\b"
        )

        if re.search(
            pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 24.0

    # ------------------------------------------
    # Released
    # ------------------------------------------

    if "released" in q and subject_lower:

        pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\breleased\b"
        )

        if re.search(
            pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 24.0

    # ------------------------------------------
    # Published
    # ------------------------------------------

    if "published" in q and subject_lower:

        pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\bpublished\b"
        )

        if re.search(
            pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 24.0

    # ------------------------------------------
    # Named after
    # ------------------------------------------

    if "named after" in q and subject_lower:

        pattern = (
            rf"\b{re.escape(subject_lower)}\b"
            rf".{{0,80}}"
            rf"\bnamed after\b"
        )

        if re.search(
            pattern,
            c,
            flags=re.IGNORECASE,
        ):
            bonus += 24.0

    # ------------------------------------------
    # Causal
    # ------------------------------------------

    if q.startswith(
        "why "
    ):
        causal_markers = [
            "because",
            "due to",
            "as a result of",
            "caused by",
            "fell after",
            "collapsed after",
        ]

        for marker in causal_markers:
            if marker in c:
                bonus += 4.0

    # ------------------------------------------
    # Subject-presence bonus
    # ------------------------------------------

    if (
        subject_lower
        and subject_lower in c
    ):
        bonus += 10.0

    return bonus


def rerank_candidates(
    question,
    candidates,
):
    reranked = []

    for candidate in candidates:

        (
            candidate_score,
            lexical,
            factual_bonus,
            index,
            chunk,
        ) = candidate

        rerank_bonus = (
            question_pattern_bonus(
                question,
                chunk,
            )
        )

        final_score = (
            candidate_score
            + rerank_bonus
        )

        reranked.append(
            {
                "chunk_index":
                    index,

                "lexical_score":
                    lexical,

                "candidate_bonus":
                    factual_bonus,

                "bonus":
                    rerank_bonus,

                "final_score":
                    final_score,

                "chunk":
                    chunk,
            }
        )

    reranked.sort(
        key=lambda item: (
            item[
                "final_score"
            ],
            item[
                "lexical_score"
            ],
        ),
        reverse=True,
    )

    return reranked


# --------------------------------------------------
# Public retrieval function
# --------------------------------------------------

def retrieve(
    question,
    chunks,
    index,
    document_frequency,
    final_top_k=FINAL_TOP_K,
):
    factual_relation = (
        detect_factual_relation(
            question
        )
    )

    if factual_relation:
        candidate_top_k = (
            FACTUAL_TOP_K
        )

    else:
        candidate_top_k = (
            LEXICAL_TOP_K
        )

    candidates = (
        retrieve_candidates(
            question,
            chunks,
            index,
            document_frequency,
            top_k=candidate_top_k,
        )
    )

    reranked = (
        rerank_candidates(
            question,
            candidates,
        )
    )

    return reranked[
        :final_top_k
    ]


# --------------------------------------------------
# Standalone test
# --------------------------------------------------

def main():
    chunks = load_chunks(
        KNOWLEDGE_FILES
    )

    (
        index,
        document_frequency,
    ) = build_index(
        chunks
    )

    while True:
        question = input(
            "\nQuery: "
        ).strip()

        if question.lower() in {
            "quit",
            "exit",
        }:
            break

        if not question:
            continue

        results = retrieve(
            question,
            chunks,
            index,
            document_frequency,
        )

        print(
            "\nTop reranked results:"
        )

        for (
            rank,
            result,
        ) in enumerate(
            results,
            start=1,
        ):
            print(
                "\n"
                + "=" * 70
            )

            print(
                f"Rank: {rank}"
                f" | Final: "
                f"{result['final_score']:.2f}"
                f" | Lexical: "
                f"{result['lexical_score']:.2f}"
                f" | Candidate bonus: "
                f"{result['candidate_bonus']:.2f}"
                f" | Rerank bonus: "
                f"{result['bonus']:.2f}"
            )

            print(
                "-" * 70
            )

            print(
                result[
                    "chunk"
                ]
            )


if __name__ == "__main__":
    main()
