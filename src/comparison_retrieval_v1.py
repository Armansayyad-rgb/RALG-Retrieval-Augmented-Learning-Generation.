import re
import time
from pathlib import Path

from retriever_v2 import (
    retrieve as retrieve_v2,
)

from comparison_planner_v1 import (
    build_comparison_queries,
)


# --------------------------------------------------
# Retrieval configuration
# --------------------------------------------------

PER_QUERY_TOP_K = 6

MAX_SIDE_RESULTS = 8
MAX_SIDE_SENTENCES = 5

# Adaptive retrieval controls.
MIN_PRIMARY_QUERIES = 3

MIN_UNIQUE_RESULTS = 3
MIN_EVIDENCE_SENTENCES = 2

MIN_ENTITY_SENTENCES = 2


# --------------------------------------------------
# Text helpers
# --------------------------------------------------

def split_sentences(text):
    if not text:
        return []

    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            text.strip(),
        )
        if sentence.strip()
    ]


def normalize_text(text):
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


def tokenize(text):
    return re.findall(
        r"[a-z0-9']+",
        text.lower(),
    )


# --------------------------------------------------
# Entity helpers
# --------------------------------------------------

def entity_terms(entity):
    entity = normalize_text(
        entity
    )

    if not entity:
        return []

    terms = [
        entity,
    ]

    words = entity.split()

    if (
        len(words) >= 2
        and words[-1] in {
            "empire",
            "kingdom",
            "republic",
            "state",
        }
    ):
        shorter = " ".join(
            words[:-1]
        )

        if shorter:
            terms.append(
                shorter
            )

    return terms


def text_mentions_entity(
    text,
    entity,
):
    normalized = normalize_text(
        text
    )

    return any(
        term in normalized
        for term in entity_terms(
            entity
        )
    )


# --------------------------------------------------
# Side-specific adaptive query planning
# --------------------------------------------------

def build_side_query_plan(entity):
    entity = entity.strip()

    lower = entity.lower()

    # ==========================================
    # MITOSIS
    # ==========================================

    if lower == "mitosis":

        primary = [
            "mitosis",
            "mitosis produces two daughter cells",
            "mitosis diploid identical cells",
        ]

        fallback = [
            "mitosis chromosomes daughter cells",
            (
                "mitosis prophase metaphase "
                "anaphase telophase"
            ),
            "mitosis cell division",
        ]

    # ==========================================
    # MEIOSIS
    # ==========================================

    elif lower == "meiosis":

        primary = [
            "meiosis",
            "meiosis haploid four cells",
            "meiosis chromosomes gametes",
        ]

        fallback = [
            "meiosis cell division",
            (
                "meiosis homologous chromosomes "
                "crossing over"
            ),
            (
                "meiosis two divisions "
                "genetic variation"
            ),
        ]

    # ==========================================
    # GENERIC COMPARISON ENTITY
    # ==========================================

    else:

        primary = [
            entity,
            f"{entity} characteristics",
            f"{entity} features",
        ]

        fallback = [
            f"{entity} structure",
            f"{entity} process",
        ]

    # ------------------------------------------
    # Deduplicate
    # ------------------------------------------

    seen = set()

    clean_primary = []
    clean_fallback = []

    for query in primary:
        key = query.lower().strip()

        if not key:
            continue

        if key in seen:
            continue

        seen.add(
            key
        )

        clean_primary.append(
            query.strip()
        )

    for query in fallback:
        key = query.lower().strip()

        if not key:
            continue

        if key in seen:
            continue

        seen.add(
            key
        )

        clean_fallback.append(
            query.strip()
        )

    return {
        "primary":
            clean_primary,

        "fallback":
            clean_fallback,

        "all":
            (
                clean_primary
                + clean_fallback
            ),
    }


def build_side_queries(entity):
    """
    Backward-compatible helper.

    Returns the complete query plan.
    """

    plan = build_side_query_plan(
        entity
    )

    return plan[
        "all"
    ]


# --------------------------------------------------
# Sentence scoring
# --------------------------------------------------

def score_side_sentence(
    sentence,
    entity,
):
    lower = sentence.lower()

    score = 0.0

    entity_words = {
        word
        for word in tokenize(
            entity
        )
        if len(word) >= 3
    }

    sentence_words = {
        word
        for word in tokenize(
            sentence
        )
        if len(word) >= 3
    }

    overlap = (
        entity_words
        & sentence_words
    )

    score += (
        len(overlap)
        * 5.0
    )

    if text_mentions_entity(
        sentence,
        entity,
    ):
        score += 7.0

    entity_lower = entity.lower()

    # ==========================================
    # Mitosis
    # ==========================================

    if entity_lower == "mitosis":

        markers = {
            "mitosis": 6.0,

            "cell division": 4.0,

            "daughter cells": 5.0,

            "chromosome": 3.0,
            "chromosomes": 3.0,

            "prophase": 3.0,
            "metaphase": 3.0,
            "anaphase": 3.0,
            "telophase": 3.0,

            "two daughter cells": 6.0,

            "identical": 4.0,

            "diploid": 3.0,
        }

        for marker, weight in (
            markers.items()
        ):
            if marker in lower:
                score += weight

        if "meiosis" in lower:
            score -= 3.0

    # ==========================================
    # Meiosis
    # ==========================================

    elif entity_lower == "meiosis":

        markers = {
            "meiosis": 6.0,

            "cell division": 4.0,

            "gamete": 4.0,
            "gametes": 4.0,

            "haploid": 5.0,

            "homologous": 4.0,

            "crossing over": 5.0,

            "recombination": 4.0,

            "two divisions": 5.0,

            "four cells": 5.0,
            "four daughter cells": 6.0,

            "genetic variation": 5.0,

            "chromosome": 3.0,
            "chromosomes": 3.0,
        }

        for marker, weight in (
            markers.items()
        ):
            if marker in lower:
                score += weight

        if "mitosis" in lower:
            score -= 3.0

    # ==========================================
    # Generic entity
    # ==========================================

    else:

        generic_markers = [
            "feature",
            "features",

            "structure",

            "organized",

            "process",

            "function",

            "used",

            "produces",

            "contains",

            "consists",

            "divided",
        ]

        for marker in generic_markers:
            if marker in lower:
                score += 2.0

    # ------------------------------------------
    # Sentence length
    # ------------------------------------------

    word_count = len(
        sentence.split()
    )

    if 8 <= word_count <= 45:
        score += 1.0

    elif word_count > 70:
        score -= 3.0

    return score


# --------------------------------------------------
# Adaptive evidence measurement
# --------------------------------------------------

def count_entity_evidence_sentences(
    merged,
    entity,
):
    """
    Count unique sentences that directly mention
    the entity and have positive evidence score.
    """

    seen = set()

    count = 0

    for item in merged.values():

        chunk = item.get(
            "chunk",
            "",
        )

        for sentence in split_sentences(
            chunk
        ):
            if not text_mentions_entity(
                sentence,
                entity,
            ):
                continue

            key = normalize_text(
                sentence
            )

            if not key:
                continue

            if key in seen:
                continue

            seen.add(
                key
            )

            score = score_side_sentence(
                sentence,
                entity,
            )

            if score <= 0:
                continue

            count += 1

    return count


def side_evidence_sufficient(
    merged,
    entity,
):
    """
    Conservative early-stop gate.

    We only stop after the primary query stage
    when there are multiple unique retrieved
    chunks AND multiple usable entity-linked
    sentences.
    """

    unique_results = len(
        merged
    )

    if (
        unique_results
        < MIN_UNIQUE_RESULTS
    ):
        return False

    evidence_sentences = (
        count_entity_evidence_sentences(
            merged,
            entity,
        )
    )

    if (
        evidence_sentences
        < MIN_EVIDENCE_SENTENCES
    ):
        return False

    return True


# --------------------------------------------------
# Merge a retrieval result into side evidence
# --------------------------------------------------

def merge_query_results(
    merged,
    results,
    entity,
    query,
    query_rank,
):
    accepted_results = 0

    for result_rank, result in enumerate(
        results,
        start=1,
    ):
        chunk = result[
            "chunk"
        ]

        # Chunk must directly mention this side.
        if not text_mentions_entity(
            chunk,
            entity,
        ):
            continue

        key = normalize_text(
            chunk
        )

        if not key:
            continue

        accepted_results += 1

        base_score = result.get(
            "final_score",
            0.0,
        )

        query_bonus = max(
            0.0,
            3.0
            - (
                (query_rank - 1)
                * 0.4
            ),
        )

        rank_bonus = max(
            0.0,
            2.0
            - (
                (result_rank - 1)
                * 0.3
            ),
        )

        combined = (
            base_score
            + query_bonus
            + rank_bonus
        )

        if key not in merged:

            merged[
                key
            ] = {
                "chunk":
                    chunk,

                "best_score":
                    combined,

                "base_score":
                    base_score,

                "query_hits":
                    1,

                "queries":
                    [
                        query
                    ],
            }

        else:

            item = merged[
                key
            ]

            item[
                "query_hits"
            ] += 1

            if query not in item[
                "queries"
            ]:
                item[
                    "queries"
                ].append(
                    query
                )

            if (
                combined
                > item[
                    "best_score"
                ]
            ):
                item[
                    "best_score"
                ] = combined

            if (
                base_score
                > item[
                    "base_score"
                ]
            ):
                item[
                    "base_score"
                ] = base_score

    return accepted_results


# --------------------------------------------------
# Execute one retrieval query
# --------------------------------------------------

def execute_side_query(
    query,
    query_rank,
    entity,
    chunks,
    index,
    document_frequency,
    merged,
    document_ids=None,
):
    retrieval_start = (
        time.perf_counter()
    )

    results = retrieve_v2(
        query,
        chunks,
        index,
        document_frequency,
        final_top_k=PER_QUERY_TOP_K,
        document_ids=document_ids,
    )

    retrieval_elapsed = (
        time.perf_counter()
        - retrieval_start
    )

    merge_start = (
        time.perf_counter()
    )

    accepted_results = (
        merge_query_results(
            merged,
            results,
            entity,
            query,
            query_rank,
        )
    )

    merge_elapsed = (
        time.perf_counter()
        - merge_start
    )

    return {
        "query":
            query,

        "retrieval":
            retrieval_elapsed,

        "merge":
            merge_elapsed,

        "returned":
            len(
                results
            ),

        "accepted":
            accepted_results,
    }


# --------------------------------------------------
# Side retrieval
# --------------------------------------------------

def retrieve_side(
    entity,
    chunks,
    index,
    document_frequency,
    collect_timings=False,
    document_ids=None,
):
    side_start = (
        time.perf_counter()
    )

    # ------------------------------------------
    # Query planning
    # ------------------------------------------

    planning_start = (
        time.perf_counter()
    )

    query_plan = (
        build_side_query_plan(
            entity
        )
    )

    planning_elapsed = (
        time.perf_counter()
        - planning_start
    )

    primary_queries = query_plan[
        "primary"
    ]

    fallback_queries = query_plan[
        "fallback"
    ]

    all_queries = query_plan[
        "all"
    ]

    merged = {}

    executed_queries = []

    query_timings = []

    retrieval_total = 0.0
    merge_total = 0.0

    query_rank = 0

    # ==========================================
    # PRIMARY STAGE
    # ==========================================

    for query in primary_queries:

        query_rank += 1

        timing = execute_side_query(
            query,
            query_rank,
            entity,
            chunks,
            index,
            document_frequency,
            merged,
            document_ids=document_ids,
        )

        executed_queries.append(
            query
        )

        retrieval_total += (
            timing[
                "retrieval"
            ]
        )

        merge_total += (
            timing[
                "merge"
            ]
        )

        if collect_timings:
            timing[
                "stage"
            ] = "primary"

            query_timings.append(
                timing
            )

    # ------------------------------------------
    # Evidence check
    # ------------------------------------------

    evidence_sufficient = (
        side_evidence_sufficient(
            merged,
            entity,
        )
    )

    fallback_used = False

    # ==========================================
    # FALLBACK STAGE
    # ==========================================

    if not evidence_sufficient:

        fallback_used = True

        for query in fallback_queries:

            query_rank += 1

            timing = execute_side_query(
                query,
                query_rank,
                entity,
                chunks,
                index,
                document_frequency,
                merged,
                document_ids=document_ids,
            )

            executed_queries.append(
                query
            )

            retrieval_total += (
                timing[
                    "retrieval"
                ]
            )

            merge_total += (
                timing[
                    "merge"
                ]
            )

            if collect_timings:
                timing[
                    "stage"
                ] = "fallback"

                query_timings.append(
                    timing
                )

            # ----------------------------------
            # Adaptive early stop
            # ----------------------------------

            if side_evidence_sufficient(
                merged,
                entity,
            ):
                break

    # ------------------------------------------
    # Final evidence statistics
    # ------------------------------------------

    final_evidence_sentences = (
        count_entity_evidence_sentences(
            merged,
            entity,
        )
    )

    # ------------------------------------------
    # Final ranking
    # ------------------------------------------

    ranking_start = (
        time.perf_counter()
    )

    results = list(
        merged.values()
    )

    for item in results:

        multi_query_bonus = min(
            5.0,
            (
                item[
                    "query_hits"
                ]
                - 1
            )
            * 1.0,
        )

        item[
            "merged_score"
        ] = (
            item[
                "best_score"
            ]
            + multi_query_bonus
        )

    results.sort(
        key=lambda item: (
            item[
                "merged_score"
            ],

            item[
                "query_hits"
            ],

            item[
                "base_score"
            ],
        ),
        reverse=True,
    )

    ranking_elapsed = (
        time.perf_counter()
        - ranking_start
    )

    total_elapsed = (
        time.perf_counter()
        - side_start
    )

    output = {
        "entity":
            entity,

        # Executed queries only.
        "queries":
            executed_queries,

        # Full plan for diagnostics.
        "planned_queries":
            all_queries,

        "primary_queries":
            primary_queries,

        "fallback_queries":
            fallback_queries,

        "fallback_used":
            fallback_used,

        "evidence_sufficient":
            side_evidence_sufficient(
                merged,
                entity,
            ),

        "evidence_sentences":
            final_evidence_sentences,

        "results":
            results[
                :MAX_SIDE_RESULTS
            ],
    }

    if collect_timings:

        output[
            "timings"
        ] = {
            "planning":
                planning_elapsed,

            "retrieval":
                retrieval_total,

            "merge":
                merge_total,

            "ranking":
                ranking_elapsed,

            "total":
                total_elapsed,

            "queries":
                query_timings,

            "planned_query_count":
                len(
                    all_queries
                ),

            "executed_query_count":
                len(
                    executed_queries
                ),

            "fallback_used":
                fallback_used,

            "evidence_sentences":
                final_evidence_sentences,
        }

    return output


# --------------------------------------------------
# Build side context
# --------------------------------------------------

def build_side_context(
    side_result,
    max_sentences=MAX_SIDE_SENTENCES,
):
    entity = side_result[
        "entity"
    ]

    candidates = []

    seen = set()

    for chunk_rank, item in enumerate(
        side_result[
            "results"
        ],
        start=1,
    ):
        chunk = item[
            "chunk"
        ]

        for sentence_index, sentence in enumerate(
            split_sentences(
                chunk
            )
        ):
            if not text_mentions_entity(
                sentence,
                entity,
            ):
                continue

            key = normalize_text(
                sentence
            )

            if not key:
                continue

            if key in seen:
                continue

            seen.add(
                key
            )

            score = score_side_sentence(
                sentence,
                entity,
            )

            score += max(
                0.0,
                2.5
                - (
                    (chunk_rank - 1)
                    * 0.3
                ),
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

    candidates.sort(
        key=lambda item: (
            item[
                "score"
            ],

            -item[
                "chunk_rank"
            ],
        ),
        reverse=True,
    )

    selected = []

    for candidate in candidates:

        if (
            candidate[
                "score"
            ]
            <= 0
        ):
            continue

        selected.append(
            candidate
        )

        if (
            len(
                selected
            )
            >= max_sentences
        ):
            break

    if not selected:
        return ""

    return "\n".join(
        item[
            "sentence"
        ]
        for item in selected
    )


# --------------------------------------------------
# Public comparison retrieval
# --------------------------------------------------

def retrieve_comparison(
    question,
    chunks,
    index,
    document_frequency,
    collect_timings=False,
    document_ids=None,
):
    total_start = (
        time.perf_counter()
    )

    # ------------------------------------------
    # Comparison planning
    # ------------------------------------------

    planning_start = (
        time.perf_counter()
    )

    plan = build_comparison_queries(
        question
    )

    planning_elapsed = (
        time.perf_counter()
        - planning_start
    )

    if plan is None:
        return None

    left_entity = plan[
        "left_entity"
    ]

    right_entity = plan[
        "right_entity"
    ]

    # ------------------------------------------
    # Left retrieval
    # ------------------------------------------

    left_result = retrieve_side(
        left_entity,
        chunks,
        index,
        document_frequency,
        collect_timings=collect_timings,
        document_ids=document_ids,
    )

    # ------------------------------------------
    # Right retrieval
    # ------------------------------------------

    right_result = retrieve_side(
        right_entity,
        chunks,
        index,
        document_frequency,
        collect_timings=collect_timings,
        document_ids=document_ids,
    )

    if (
        not left_result[
            "results"
        ]
        or not right_result[
            "results"
        ]
    ):
        return None

    # ------------------------------------------
    # Context construction
    # ------------------------------------------

    context_start = (
        time.perf_counter()
    )

    left_context = build_side_context(
        left_result,
        max_sentences=MAX_SIDE_SENTENCES,
    )

    right_context = build_side_context(
        right_result,
        max_sentences=MAX_SIDE_SENTENCES,
    )

    context_elapsed = (
        time.perf_counter()
        - context_start
    )

    if (
        not left_context.strip()
        or not right_context.strip()
    ):
        return None

    # ------------------------------------------
    # Final structured context
    # ------------------------------------------

    assembly_start = (
        time.perf_counter()
    )

    structured_context = (
        "SIDE A:\n"
        f"{left_entity}\n\n"
        f"{left_context}\n\n"
        "SIDE B:\n"
        f"{right_entity}\n\n"
        f"{right_context}"
    )

    assembly_elapsed = (
        time.perf_counter()
        - assembly_start
    )

    result = {
        "plan":
            plan,

        "left_query_original":
            left_entity,

        "right_query_original":
            right_entity,

        # Actual queries executed.
        "left_query_expanded":
            left_result[
                "queries"
            ],

        "right_query_expanded":
            right_result[
                "queries"
            ],

        # Full query plans.
        "left_query_plan":
            left_result[
                "planned_queries"
            ],

        "right_query_plan":
            right_result[
                "planned_queries"
            ],

        "left":
            left_result,

        "right":
            right_result,

        "left_context":
            left_context,

        "right_context":
            right_context,

        "context":
            structured_context,
    }

    if collect_timings:

        result[
            "timings"
        ] = {
            "planning":
                planning_elapsed,

            "left":
                left_result.get(
                    "timings",
                    {},
                ),

            "right":
                right_result.get(
                    "timings",
                    {},
                ),

            "context_building":
                context_elapsed,

            "assembly":
                assembly_elapsed,

            "total":
                (
                    time.perf_counter()
                    - total_start
                ),
        }

    return result


# --------------------------------------------------
# Performance display
# --------------------------------------------------

def print_side_performance(
    label,
    side,
):
    print(
        f"\n{label} total: "
        f"{side['total']:.4f}s"
    )

    print(
        f"{label} planning: "
        f"{side['planning']:.4f}s"
    )

    print(
        f"{label} retrieval: "
        f"{side['retrieval']:.4f}s"
    )

    print(
        f"{label} merge/filter: "
        f"{side['merge']:.4f}s"
    )

    print(
        f"{label} ranking: "
        f"{side['ranking']:.4f}s"
    )

    print(
        f"{label} queries planned: "
        f"{side['planned_query_count']}"
    )

    print(
        f"{label} queries executed: "
        f"{side['executed_query_count']}"
    )

    print(
        f"{label} fallback used: "
        f"{side['fallback_used']}"
    )

    print(
        f"{label} evidence sentences: "
        f"{side['evidence_sentences']}"
    )

    print(
        f"\n{label} query timings:"
    )

    for item in side[
        "queries"
    ]:
        print(
            f"  [{item['stage']:<8}] "
            f"{item['retrieval']:.4f}s "
            f"| merge={item['merge']:.4f}s "
            f"| returned={item['returned']} "
            f"| accepted={item['accepted']} "
            f"| {item['query']}"
        )


def print_performance(
    result,
):
    timings = result.get(
        "timings"
    )

    if not timings:
        return

    print(
        "\n--- PERFORMANCE ---\n"
    )

    print(
        f"Planning: "
        f"{timings['planning']:.4f}s"
    )

    print_side_performance(
        "Left",
        timings[
            "left"
        ],
    )

    print_side_performance(
        "Right",
        timings[
            "right"
        ],
    )

    print(
        f"\nContext building: "
        f"{timings['context_building']:.4f}s"
    )

    print(
        f"Assembly: "
        f"{timings['assembly']:.4f}s"
    )

    print(
        f"Total comparison retrieval: "
        f"{timings['total']:.4f}s"
    )


# --------------------------------------------------
# Standalone test
# --------------------------------------------------

if __name__ == "__main__":

    from retriever_v2 import (
        load_chunks,
        build_index,
    )

    KNOWLEDGE_FILES = [
        Path(
            r"C:\AI-Project\data\wikitext_v2.txt"
        ),
        Path(
            r"C:\AI-Project\data\knowledge_extra_v1.txt"
        ),
    ]

    print(
        "\nLoading adaptive comparison "
        "retrieval system...\n"
    )

    initialization_start = (
        time.perf_counter()
    )

    chunks = load_chunks(
        KNOWLEDGE_FILES
    )

    (
        index,
        document_frequency,
    ) = build_index(
        chunks
    )

    initialization_elapsed = (
        time.perf_counter()
        - initialization_start
    )

    print(
        f"\nInitialization time: "
        f"{initialization_elapsed:.3f}s"
    )

    print(
        "\nType 'quit' to exit."
    )

    while True:

        question = input(
            "\nComparison query: "
        ).strip()

        if question.lower() in {
            "quit",
            "exit",
        }:
            break

        if not question:
            continue

        result = retrieve_comparison(
            question,
            chunks,
            index,
            document_frequency,
            collect_timings=True,
        )

        if result is None:

            print(
                "\nCould not build "
                "comparison evidence."
            )

            continue

        print(
            "\n--- COMPARISON PLAN ---"
        )

        print(
            "Left:",
            result[
                "plan"
            ][
                "left_entity"
            ],
        )

        print(
            "Right:",
            result[
                "plan"
            ][
                "right_entity"
            ],
        )

        # ------------------------------------------
        # Planned queries
        # ------------------------------------------

        print(
            "\n--- LEFT QUERY PLAN ---"
        )

        for query in result[
            "left_query_plan"
        ]:
            print(
                "-",
                query,
            )

        print(
            "\n--- RIGHT QUERY PLAN ---"
        )

        for query in result[
            "right_query_plan"
        ]:
            print(
                "-",
                query,
            )

        # ------------------------------------------
        # Actually executed queries
        # ------------------------------------------

        print(
            "\n--- LEFT EXECUTED QUERIES ---"
        )

        for query in result[
            "left_query_expanded"
        ]:
            print(
                "-",
                query,
            )

        print(
            "\n--- RIGHT EXECUTED QUERIES ---"
        )

        for query in result[
            "right_query_expanded"
        ]:
            print(
                "-",
                query,
            )

        # ------------------------------------------
        # Evidence
        # ------------------------------------------

        print(
            "\n--- LEFT FILTERED EVIDENCE ---\n"
        )

        print(
            result[
                "left_context"
            ]
        )

        print(
            "\n--- RIGHT FILTERED EVIDENCE ---\n"
        )

        print(
            result[
                "right_context"
            ]
        )

        print(
            "\n--- STRUCTURED CONTEXT ---\n"
        )

        print(
            result[
                "context"
            ]
        )

        print_performance(
            result
        )
