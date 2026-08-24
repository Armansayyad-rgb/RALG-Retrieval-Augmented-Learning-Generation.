import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import KNOWLEDGE_FILES  # noqa: E402

from retriever_v2 import (
    load_chunks,
    build_index,
    retrieve as retrieve_v2,
)


KNOWLEDGE_FILE = KNOWLEDGE_FILES[0]

FINAL_TOP_K = 8
MAX_EVIDENCE_SENTENCES = 6
MAX_AGGREGATE_CHARS = 2200


STOPWORDS = {
    "the", "a", "an", "and", "or", "but",
    "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "was",
    "are", "were", "be", "been", "being",
    "that", "this", "these", "those",
    "it", "its", "they", "their", "them",
    "he", "she", "his", "her",
    "what", "when", "where", "why", "how",
    "did", "does", "do", "has", "have",
    "had",
}


# --------------------------------------------------
# Sentence helpers
# --------------------------------------------------

def split_sentences(text):
    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            text.strip(),
        )
        if sentence.strip()
    ]


def tokenize(text):
    return re.findall(
        r"[a-z0-9']+",
        text.lower(),
    )


def useful_words(text):
    return [
        word
        for word in tokenize(text)
        if word not in STOPWORDS
        and len(word) >= 3
    ]


def normalize_sentence(text):
    text = text.lower()

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# --------------------------------------------------
# Question type detection
# --------------------------------------------------

def is_effect_question(question):
    q = question.lower()

    patterns = [
        r"\bwhat were the effects of\b",
        r"\bwhat was the effect of\b",
        r"\bwhat were the consequences of\b",
        r"\bwhat was the consequence of\b",
        r"\bwhat happened after\b",
        r"\bwhat resulted from\b",
        r"\bwhat did .+ lead to\b",
        r"\bhow did .+ affect\b",
        r"\bwhat was the impact of\b",
    ]

    return any(
        re.search(
            pattern,
            q,
        )
        for pattern in patterns
    )


def is_change_question(question):
    q = question.lower()

    patterns = [
        r"\bhow did .+ change over time\b",
        r"\bhow did .+ change\b",
        r"\bhow did .+ develop\b",
        r"\bhow did .+ evolve\b",
        r"\bwhat changed about\b",
    ]

    return any(
        re.search(
            pattern,
            q,
        )
        for pattern in patterns
    )


# --------------------------------------------------
# Effect-aware scoring
# --------------------------------------------------

EFFECT_MARKERS = {
    "as a result": 8.0,
    "resulted in": 8.0,
    "resulting in": 7.0,
    "led to": 8.0,
    "leading to": 7.0,

    "consequence": 6.0,
    "consequences": 6.0,
    "effect": 5.0,
    "effects": 5.0,
    "impact": 5.0,

    "after": 2.5,
    "following": 2.5,
    "thereafter": 3.0,
    "after 410": 3.0,

    "became": 3.0,
    "came under": 6.0,

    "lost": 4.0,
    "loss": 3.0,
    "provinces": 2.5,
    "former provinces": 5.0,
    "territories": 2.5,

    "fragmented": 5.0,
    "fragmentation": 5.0,
    "divided": 4.0,
    "division": 4.0,

    "replaced": 4.0,
    "kingdoms": 6.0,
    "barbarian kingdoms": 8.0,

    "no longer": 5.0,
    "no longer part": 7.0,

    "without possession": 5.0,

    "declined": 2.5,
    "weakened": 2.5,
    "collapsed": 2.5,

    "moved": 2.0,
    "shifted": 2.0,

    "control": 2.0,
    "power": 2.0,

    "germanic": 2.5,
    "much of western europe": 3.0,
}


CHANGE_MARKERS = {
    "transitioned": 6.0,
    "became": 4.0,

    "organized": 4.0,
    "reorganized": 4.0,

    "expanded": 3.0,
    "grew": 3.0,

    "declined": 3.0,
    "weakened": 3.0,
    "lost": 4.0,

    "moved": 2.5,
    "shifted": 2.5,

    "came under": 4.0,
    "conquered": 3.0,
}


def effect_score(sentence):
    s = sentence.lower()

    score = 0.0

    for marker, weight in (
        EFFECT_MARKERS.items()
    ):
        if marker in s:
            score += weight

    strong_patterns = [
        (
            r"\bas a result\b",
            5.0,
        ),
        (
            r"\bresulted in\b",
            6.0,
        ),
        (
            r"\bled to\b",
            6.0,
        ),
        (
            r"\bcame under\b",
            4.0,
        ),
        (
            r"\bafter .+ became\b",
            4.0,
        ),
        (
            r"\bafter .+ lost\b",
            4.0,
        ),
    ]

    for pattern, weight in strong_patterns:
        if re.search(
            pattern,
            s,
        ):
            score += weight

    return score


def change_score(sentence):
    s = sentence.lower()

    score = 0.0

    for marker, weight in (
        CHANGE_MARKERS.items()
    ):
        if marker in s:
            score += weight

    return score


# --------------------------------------------------
# Sentence scoring
# --------------------------------------------------

def score_sentence(
    question,
    sentence,
    chunk_rank,
):
    q_words = set(
        useful_words(question)
    )

    s_words = set(
        useful_words(sentence)
    )

    if not s_words:
        return 0.0

    score = 0.0

    overlap = (
        q_words
        & s_words
    )

    score += (
        len(overlap)
        * 3.0
    )

    q = question.lower()
    s = sentence.lower()

    # Prefer higher-ranked chunks.
    score += max(
        0.0,
        3.0
        - (
            (chunk_rank - 1)
            * 0.5
        ),
    )

    # ------------------------------------------
    # Extractive-style bonuses
    # ------------------------------------------

    if "born" in q:
        if re.search(
            r"\bwas born (?:on|in)\b",
            s,
        ):
            score += 10.0

    if "founded" in q:
        if re.search(
            r"\bwas founded in\b",
            s,
        ):
            score += 10.0

    if "established" in q:
        if re.search(
            r"\bwas established in\b",
            s,
        ):
            score += 10.0

    if "released" in q:
        if re.search(
            r"\bwas released in\b",
            s,
        ):
            score += 10.0

    if "published" in q:
        if re.search(
            r"\bwas published in\b",
            s,
        ):
            score += 10.0

    if "named after" in q:
        if "was named after" in s:
            score += 10.0

    # ------------------------------------------
    # Causal question bonuses
    # ------------------------------------------

    if q.startswith("why "):
        causal_markers = [
            "because",
            "due to",
            "as a result of",
            "caused by",
            "fell after",
            "collapsed after",
            "overrun",
            "revolt",
            "decline",
            "sack",
            "invading",
        ]

        for marker in causal_markers:
            if marker in s:
                score += 3.0

    # ------------------------------------------
    # Change question bonuses
    # ------------------------------------------

    if is_change_question(
        question
    ):
        score += change_score(
            sentence
        )

    # ------------------------------------------
    # Effect / consequence bonuses
    # ------------------------------------------

    if is_effect_question(
        question
    ):
        score += effect_score(
            sentence
        )

        strong_aftermath_patterns = [
            r"\bno longer part of\b",
            r"\bcame under .+ kingdoms\b",
            r"\bwithout possession of\b",
            r"\blost .+ provinces\b",
            r"\bformer provinces\b",
            r"\bincreasingly germanic\b",
        ]

        for pattern in (
            strong_aftermath_patterns
        ):
            if re.search(
                pattern,
                s,
            ):
                score += 8.0

        # Penalize sentences that mostly explain
        # the fall rather than its consequences.
        cause_only_markers = [
            "fell after",
            "was overrun",
            "invading",
            "revolt",
        ]

        consequence_markers = [
            "after",
            "following",
            "result",
            "led to",
            "became",
            "lost",
            "came under",
            "fragmented",
            "divided",
            "kingdoms",
            "provinces",
            "no longer",
            "former provinces",
            "increasingly germanic",
        ]

        cause_only = any(
            marker in s
            for marker in cause_only_markers
        )

        has_consequence = any(
            marker in s
            for marker in consequence_markers
        )

        if (
            cause_only
            and not has_consequence
        ):
            score -= 5.0

    # ------------------------------------------
    # Generic quality penalties
    # ------------------------------------------

    if len(overlap) == 0:
        score -= 2.0

    if len(sentence) < 25:
        score -= 1.0

    word_count = len(
        sentence.split()
    )

    if word_count > 70:
        score -= 2.0

    return score


# --------------------------------------------------
# Build ranked sentence pool
# --------------------------------------------------

def collect_sentences(
    question,
    results,
):
    seen = set()
    candidates = []

    for chunk_rank, result in enumerate(
        results,
        start=1,
    ):
        chunk = result[
            "chunk"
        ]

        for sentence_index, sentence in enumerate(
            split_sentences(
                chunk
            )
        ):
            normalized = normalize_sentence(
                sentence
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            score = score_sentence(
                question,
                sentence,
                chunk_rank,
            )

            candidates.append(
                {
                    "score":
                        score,

                    "chunk_rank":
                        chunk_rank,

                    "sentence_index":
                        sentence_index,

                    "sentence":
                        sentence,
                }
            )

    return candidates


# --------------------------------------------------
# Evidence aggregation
# --------------------------------------------------

def aggregate_results(
    question,
    results,
    max_sentences=MAX_EVIDENCE_SENTENCES,
    max_chars=MAX_AGGREGATE_CHARS,
):
    if not results:
        return ""

    candidates = collect_sentences(
        question,
        results,
    )

    candidates.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True,
    )

    selected = []

    total_chars = 0

    for item in candidates:
        if item["score"] <= 0:
            continue

        sentence = item[
            "sentence"
        ]

        extra_chars = (
            len(sentence) + 1
        )

        if (
            selected
            and total_chars + extra_chars
            > max_chars
        ):
            continue

        selected.append(
            item
        )

        total_chars += extra_chars

        if (
            len(selected)
            >= max_sentences
        ):
            break

    # For effect/change questions,
    # preserve relevance ranking.
    if not (
        is_effect_question(
            question
        )
        or is_change_question(
            question
        )
    ):
        selected.sort(
            key=lambda item: (
                item[
                    "chunk_rank"
                ],
                item[
                    "sentence_index"
                ],
            )
        )

    return "\n".join(
        item["sentence"]
        for item in selected
    )


# --------------------------------------------------
# Public V3 retrieval
# --------------------------------------------------

def retrieve(
    question,
    chunks,
    index,
    document_frequency,
    final_top_k=FINAL_TOP_K,
):
    results = retrieve_v2(
        question,
        chunks,
        index,
        document_frequency,
        final_top_k=final_top_k,
    )

    if not results:
        return {
            "results": [],
            "best": None,
            "context": "",
        }

    context = aggregate_results(
        question,
        results,
    )

    return {
        "results":
            results,

        "best":
            results[0],

        "context":
            context,
    }


# --------------------------------------------------
# Standalone test
# --------------------------------------------------

def main():
    chunks = load_chunks(
        KNOWLEDGE_FILE
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

        retrieval = retrieve(
            question,
            chunks,
            index,
            document_frequency,
        )

        if not retrieval[
            "results"
        ]:
            print(
                "\nNo results."
            )
            continue

        print(
            "\n--- TOP RESULTS ---"
        )

        for rank, result in enumerate(
            retrieval["results"],
            start=1,
        ):
            print(
                f"\nRank {rank}"
                f" | Final "
                f"{result['final_score']:.2f}"
            )

            print(
                result["chunk"]
            )

        print(
            "\n--- RANKED EVIDENCE ---\n"
        )

        print(
            retrieval["context"]
        )


if __name__ == "__main__":
    main()