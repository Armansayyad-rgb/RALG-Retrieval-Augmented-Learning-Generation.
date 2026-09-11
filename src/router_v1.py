import re


# --------------------------------------------------
# Extractive question patterns
# --------------------------------------------------

EXTRACTIVE_PATTERNS = [
    # Birth
    r"\bwhen\s+(?:was|is)\s+.+\s+born\b",

    # Founded / established / opened
    r"\bwhen\s+was\s+.+\s+founded\b",
    r"\bwhen\s+was\s+.+\s+established\b",
    r"\bwhen\s+(?:was|did)\s+.+\s+open(?:ed)?\b",

    # Released / published
    r"\bwhen\s+was\s+.+\s+released\b",
    r"\bwhen\s+was\s+.+\s+published\b",

    # Named after
    r"\bwho\s+(?:or\s+what\s+)?was\s+.+\s+named\s+after\b",
    r"\bwhat\s+was\s+.+\s+named\s+after\b",

    # Location
    r"\bwhere\s+is\s+.+\s+located\b",

    # Capital
    r"\bwhat\s+is\s+.+\s+the\s+capital\s+of\b",
    r"\bwhat\s+is\s+the\s+capital\s+of\b",

    # Population
    r"\bwhat\s+is\s+the\s+population\s+of\b",

    # What year / date
    r"\bwhat\s+year\b",

    # Direct event-cause extraction.
    #
    # Important:
    # "What caused X to decline?"
    # is protected by ANALYTICAL_PATTERNS below,
    # so it will not reach this rule.
    r"\bwhat\s+caused\s+.+\b",

    # Narrow "why was" causal questions.
    #
    # Analytical forms such as:
    #   Why was the Magna Carta important?
    # are protected by ANALYTICAL_PATTERNS first.
    r"\bwhy\s+was\s+.+\b",
]


# --------------------------------------------------
# Broad analytical / reasoning patterns
# --------------------------------------------------

ANALYTICAL_PATTERNS = [
    # ------------------------------------------
    # Why did X ...
    # ------------------------------------------

    r"\bwhy\s+did\s+.+\s+decline\b",
    r"\bwhy\s+did\s+.+\s+collapse\b",
    r"\bwhy\s+did\s+.+\s+rise\b",
    r"\bwhy\s+did\s+.+\s+change\b",
    r"\bwhy\s+did\s+.+\s+grow\b",
    r"\bwhy\s+did\s+.+\s+expand\b",
    r"\bwhy\s+did\s+.+\s+weaken\b",
    r"\bwhy\s+did\s+.+\s+fail\b",

    # ------------------------------------------
    # What caused X to ...
    # ------------------------------------------

    r"\bwhat\s+caused\s+.+\s+to\s+decline\b",
    r"\bwhat\s+caused\s+.+\s+to\s+collapse\b",
    r"\bwhat\s+caused\s+.+\s+to\s+rise\b",
    r"\bwhat\s+caused\s+.+\s+to\s+change\b",
    r"\bwhat\s+caused\s+.+\s+to\s+grow\b",
    r"\bwhat\s+caused\s+.+\s+to\s+expand\b",
    r"\bwhat\s+caused\s+.+\s+to\s+weaken\b",
    r"\bwhat\s+caused\s+.+\s+to\s+fail\b",

    # ------------------------------------------
    # Significance / importance
    # ------------------------------------------

    r"\bwhy\s+was\s+.+\s+important\b",
    r"\bwhy\s+is\s+.+\s+important\b",

    r"\bwhat\s+is\s+the\s+significance\s+of\b",
    r"\bwhat\s+was\s+the\s+significance\s+of\b",

    r"\bwhat\s+is\s+the\s+importance\s+of\b",
    r"\bwhat\s+was\s+the\s+importance\s+of\b",

    # ------------------------------------------
    # Explain
    # ------------------------------------------

    r"\bexplain\s+why\b",
    r"\bexplain\s+how\b",

    # ------------------------------------------
    # Comparison
    # ------------------------------------------

    r"\bcompare\b",
    r"\bcontrast\b",

    r"\bwhat\s+(?:is|are)\s+the\s+"
    r"differences?\s+between\b",

    r"\bhow\s+are\s+.+\s+different\b",

    # ------------------------------------------
    # Change / process / broad how
    # ------------------------------------------

    r"\bhow\s+did\s+.+\b",
    r"\bhow\s+does\s+.+\b",

    # ------------------------------------------
    # Structure / description
    # ------------------------------------------

    r"\bdescribe\s+how\s+.+\b",
]


# --------------------------------------------------
# Special direct causal extractor patterns
# --------------------------------------------------

EXTRACTIVE_WHY_PATTERNS = [
    # Existing working example:
    # Why did the Roman Empire fall?
    r"\bwhy\s+did\s+.+\s+fall\b",

    # Other direct event-style questions
    r"\bwhy\s+did\s+.+\s+end\b",
]


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def normalize_question(question):
    question = question.strip()

    question = re.sub(
        r"\s+",
        " ",
        question,
    )

    return question


def matches_any(
    question,
    patterns,
):
    for pattern in patterns:
        if re.search(
            pattern,
            question,
            flags=re.IGNORECASE,
        ):
            return True

    return False


# --------------------------------------------------
# Route checks
# --------------------------------------------------

def is_analytical_question(question):
    question = normalize_question(
        question
    )

    return matches_any(
        question,
        ANALYTICAL_PATTERNS,
    )


def is_extractive_question(question):
    question = normalize_question(
        question
    )

    # ------------------------------------------
    # Analytical route has priority.
    # ------------------------------------------

    if is_analytical_question(
        question
    ):
        return False

    # ------------------------------------------
    # Known direct causal forms can still use
    # extractor_v1.
    # ------------------------------------------

    if matches_any(
        question,
        EXTRACTIVE_WHY_PATTERNS,
    ):
        return True

    return matches_any(
        question,
        EXTRACTIVE_PATTERNS,
    )


# --------------------------------------------------
# Public router
# --------------------------------------------------

def route_question(question):
    """
    Returns the component that should get
    the first attempt at answering.
    """

    if is_extractive_question(
        question
    ):
        return "extractor"

    return "model"


# --------------------------------------------------
# Standalone tests
# --------------------------------------------------

if __name__ == "__main__":

    tests = [
        # ------------------------------------------
        # Extractive
        # ------------------------------------------

        "When was John McCain born?",
        "When was Microsoft founded?",
        "When was the album released?",
        "Where is Paris located?",
        "Who was Little Nellie named after?",
        "What is the population of London?",

        "Why was Kaua'i chosen over Mexico?",
        "What caused the Lock Haven flood?",

        # ------------------------------------------
        # Existing direct causal extractor
        # ------------------------------------------

        "Why did the Roman Empire fall?",

        # ------------------------------------------
        # Analytical causal
        # ------------------------------------------

        "Why did the Roman Empire decline?",
        "Why did the Ottoman Empire collapse?",
        "Why did Rome expand?",

        "What caused the Roman Empire to decline?",
        "What caused the Ottoman Empire to collapse?",

        # ------------------------------------------
        # Change
        # ------------------------------------------

        "How did the Roman Empire change?",
        "How did the Roman Empire evolve?",

        # ------------------------------------------
        # Significance
        # ------------------------------------------

        "Why was the Magna Carta important?",
        "Why is photosynthesis important?",
        "What is the significance of the Magna Carta?",

        # ------------------------------------------
        # Explanation
        # ------------------------------------------

        "Explain why the sky is blue.",
        "Explain how photosynthesis works.",

        # ------------------------------------------
        # Structure
        # ------------------------------------------

        "Describe how the Roman army was organized.",

        # ------------------------------------------
        # Comparison
        # ------------------------------------------

        "Compare Mars and Earth.",
        "What are the differences between mitosis and meiosis?",
        "How are mitosis and meiosis different?",

        # ------------------------------------------
        # Generic
        # ------------------------------------------

        "Tell me about India.",
    ]

    for question in tests:
        route = route_question(
            question
        )

        print(
            f"{route:10} | {question}"
        )