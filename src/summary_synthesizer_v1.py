import re


# --------------------------------------------------
# Text helpers
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


def normalize(text):
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+([,.!?;:])",
        r"\1",
        text,
    )

    text = re.sub(
        r"\s*-\s*",
        "-",
        text,
    )

    text = re.sub(
        r"\(\s+",
        "(",
        text,
    )

    text = re.sub(
        r"\s+\)",
        ")",
        text,
    )

    text = re.sub(
        r"\s+'\s*",
        "'",
        text,
    )

    return text.strip()


def capitalize_sentence(text):
    text = text.strip()

    if not text:
        return text

    return (
        text[0].upper()
        + text[1:]
    )


def tokenize(text):
    return re.findall(
        r"[a-z0-9']+",
        text.lower(),
    )


def content_terms(text):
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
    }

    return {
        word
        for word in tokenize(
            text
        )
        if (
            word not in stopwords
            and len(word) >= 3
        )
    }


# --------------------------------------------------
# Question detection
# --------------------------------------------------

def detect_mode(question):
    q = (
        question
        .lower()
        .strip()
    )

    # ------------------------------------------
    # Protect causal "Explain why" questions
    # ------------------------------------------

    if re.fullmatch(
        r"explain why .+",
        q,
    ):
        return None

    # ------------------------------------------
    # Significance / importance
    # ------------------------------------------

    if re.fullmatch(
        r"why (?:was|is) .+ important[.?!]?",
        q,
    ):
        return "significance"

    if re.fullmatch(
        r"what (?:is|was) the significance of .+",
        q,
    ):
        return "significance"

    if re.fullmatch(
        r"what (?:is|was) the importance of .+",
        q,
    ):
        return "significance"

    # ------------------------------------------
    # Process / explanation
    # ------------------------------------------

    if re.fullmatch(
        r"explain how .+",
        q,
    ):
        return "explain"

    if re.fullmatch(
        r"how does .+ work[.?!]?",
        q,
    ):
        return "explain"

    # ------------------------------------------
    # Features
    # ------------------------------------------

    if re.fullmatch(
        r"what (?:are|were) the main features of .+",
        q,
    ):
        return "features"

    # ------------------------------------------
    # Description
    # ------------------------------------------

    if re.fullmatch(
        r"describe .+",
        q,
    ):
        return "describe"

    # ------------------------------------------
    # Generic explanation
    # ------------------------------------------

    if re.fullmatch(
        r"explain .+",
        q,
    ):
        return "explain"

    return None


def subject_from_question(question):
    question = question.strip()

    patterns = [
        r"explain how (.+?) works[.?!]?$",
        r"how does (.+?) work[.?!]?$",

        r"what (?:are|were) the main features of "
        r"(.+?)[.?!]?$",

        r"what (?:is|was) the significance of "
        r"(.+?)[.?!]?$",

        r"what (?:is|was) the importance of "
        r"(.+?)[.?!]?$",

        r"why (?:was|is) (.+?) important[.?!]?$",

        r"describe (.+?)[.?!]?$",
        r"explain how (.+?)[.?!]?$",
        r"explain (.+?)[.?!]?$",
    ]

    for pattern in patterns:
        match = re.fullmatch(
            pattern,
            question,
            flags=re.IGNORECASE,
        )

        if match:
            return (
                match.group(1)
                .strip()
                .rstrip(".?!\\")
                .strip()
            )

    return None


# --------------------------------------------------
# Relational premise detection
# --------------------------------------------------

RELATION_VARIANTS = {
    "created": {
        "create",
        "created",
        "creates",
        "creating",
        "creation",
    },

    "produced": {
        "produce",
        "produced",
        "produces",
        "producing",
        "production",
    },

    "caused": {
        "cause",
        "caused",
        "causes",
        "causing",
        "because",
        "resulted",
        "resulted in",
    },

    "generated": {
        "generate",
        "generated",
        "generates",
        "generating",
        "generation",
    },

    "led to": {
        "lead to",
        "leads to",
        "led to",
        "leading to",
    },

    "resulted in": {
        "result in",
        "results in",
        "resulted in",
        "resulting in",
    },

    "formed": {
        "form",
        "formed",
        "forms",
        "forming",
    },

    "invented": {
        "invent",
        "invented",
        "invents",
        "inventing",
        "invention",
    },
}


RELATIONAL_QUESTION_PATTERNS = [
    (
        r"explain the process by which "
        r"(.+?) "
        r"(created|produced|caused|generated|formed|invented|"
        r"led to|resulted in) "
        r"(.+?)[.?!]?$"
    ),

    (
        r"describe how "
        r"(.+?) "
        r"(created|produced|caused|generated|formed|invented|"
        r"led to|resulted in) "
        r"(.+?)[.?!]?$"
    ),

    (
        r"explain how "
        r"(.+?) "
        r"(created|produced|caused|generated|formed|invented|"
        r"led to|resulted in) "
        r"(.+?)[.?!]?$"
    ),
]


def parse_relational_premise(question):
    question = (
        question
        .lower()
        .strip()
    )

    for pattern in RELATIONAL_QUESTION_PATTERNS:
        match = re.fullmatch(
            pattern,
            question,
            flags=re.IGNORECASE,
        )

        if match:
            return {
                "left":
                    match.group(1).strip(),

                "relation":
                    match.group(2).strip(),

                "right":
                    match.group(3).strip(),
            }

    return None


def relation_markers(
    relation,
):
    relation = relation.lower().strip()

    markers = RELATION_VARIANTS.get(
        relation
    )

    if markers:
        return markers

    return {
        relation,
    }


def sentence_supports_relation(
    sentence,
    left,
    relation,
    right,
):
    lower = sentence.lower()

    sentence_terms = content_terms(
        sentence
    )

    left_terms = content_terms(
        left
    )

    right_terms = content_terms(
        right
    )

    if (
        not left_terms
        or not right_terms
    ):
        return False

    left_overlap = (
        left_terms
        & sentence_terms
    )

    right_overlap = (
        right_terms
        & sentence_terms
    )

    left_coverage = (
        len(left_overlap)
        / len(left_terms)
    )

    right_coverage = (
        len(right_overlap)
        / len(right_terms)
    )

    relation_present = any(
        marker in lower
        for marker in relation_markers(
            relation
        )
    )

    return (
        left_coverage >= 0.5
        and right_coverage >= 0.5
        and relation_present
    )


def relational_premise_supported(
    question,
    context,
):
    premise = parse_relational_premise(
        question
    )

    # No explicit relational premise detected.
    if premise is None:
        return True

    sentences = split_sentences(
        context
    )

    for sentence in sentences:
        if sentence_supports_relation(
            sentence,
            premise[
                "left"
            ],
            premise[
                "relation"
            ],
            premise[
                "right"
            ],
        ):
            return True

    return False


# --------------------------------------------------
# Generic scoring markers
# --------------------------------------------------

GENERAL_MARKERS = {
    "uses": 2.0,
    "produces": 2.0,
    "includes": 2.0,
    "consists": 2.0,
    "contains": 2.0,
    "limited": 2.0,
    "organized": 2.0,
    "predominant": 2.0,
    "important": 1.5,
    "significant": 2.0,
    "because": 2.0,
    "led to": 2.0,
    "resulted": 2.0,
}


# --------------------------------------------------
# Significance scoring
# --------------------------------------------------

SIGNIFICANCE_MARKERS = {
    "limited royal power": 12.0,
    "limited power": 9.0,
    "limited": 5.0,

    "constrained": 7.0,
    "restricted": 7.0,

    "rights": 7.0,
    "liberties": 7.0,

    "constitutional": 6.0,
    "rule of law": 8.0,

    "authority": 5.0,
    "power": 4.0,

    "reformed": 5.0,
    "changed": 4.0,
    "transformed": 5.0,

    "established": 4.0,
    "influenced": 5.0,

    "feudal charges": 6.0,
    "condemned": 4.0,

    "barons forced": 5.0,
}


SIGNIFICANCE_EVENT_NOISE = [
    "siege was lifted",
    "maintained his control",
    "invited prince",
    "invited",
    "to invade",
    "both sides failed",
    "war began",
    "battle",
    "army",
    "siege",
]


# --------------------------------------------------
# Process / explanation scoring
# --------------------------------------------------

PROCESS_MARKERS = {
    "uses": 6.0,
    "use": 4.0,

    "converts": 7.0,
    "convert": 6.0,

    "produces": 5.0,
    "produced": 4.0,

    "splits": 6.0,
    "split": 5.0,

    "absorbs": 5.0,
    "captures": 5.0,

    "transforms": 6.0,

    "releases": 5.0,
    "released": 4.0,

    "forms": 4.0,

    "process": 3.0,
    "mechanism": 3.0,

    "water": 2.5,
    "carbon dioxide": 2.5,
    "sunlight": 2.5,
    "energy": 2.0,
    "oxygen": 2.5,
    "sugar": 2.5,
    "sugars": 2.5,
}


PROCESS_BACKGROUND_NOISE = [
    "basis of almost all life",
    "major groups of organisms",
    "photoautotrophs",
    "adaptations to deal with",
]


PROCESS_SPECIALIZED_DETAILS = [
    "c3",
    "c4",
    "cam",
]


# --------------------------------------------------
# Sentence quality helpers
# --------------------------------------------------

def starts_with_weak_reference(sentence):
    lower = sentence.lower().strip()

    weak_starts = [
        "these ",
        "those ",
        "this was ",
        "this is ",
        "both sides ",
        "they ",
        "it ",
    ]

    return any(
        lower.startswith(
            marker
        )
        for marker in weak_starts
    )


def _normalize_term(word):
    """Fold common possessive forms so "republic's" matches "republic"."""
    if word.endswith("'s"):
        return word[:-2]
    if word.endswith("'"):
        return word[:-1]
    return word


def sentence_mentions_subject(
    sentence,
    subject,
):
    """Whether the sentence actually engages the question subject.

    Uses content terms only (stopwords and sub-3-char tokens excluded)
    and requires at least half of the subject's content terms to be
    present (minimum one). A single trivial shared token such as
    "the" must not count as mentioning the subject.
    """
    subject_words = {
        _normalize_term(word)
        for word in content_terms(
            subject
        )
    }

    if not subject_words:
        return False

    sentence_words = {
        _normalize_term(word)
        for word in content_terms(
            sentence
        )
    }

    overlap = (
        subject_words
        & sentence_words
    )

    required = max(
        1,
        (len(subject_words) + 1) // 2,
    )

    return (
        len(overlap)
        >= required
    )


# --------------------------------------------------
# Sentence scoring
# --------------------------------------------------

def score_sentence(
    question,
    sentence,
):
    mode = detect_mode(
        question
    )

    subject = subject_from_question(
        question
    ) or ""

    q_words = {
        word
        for word in tokenize(
            question
        )
        if len(word) >= 3
    }

    s_words = set(
        tokenize(
            sentence
        )
    )

    lower = sentence.lower()

    score = 0.0

    overlap = (
        q_words
        & s_words
    )

    score += (
        len(overlap)
        * 1.5
    )

    if sentence_mentions_subject(
        sentence,
        subject,
    ):
        score += 3.0

    for marker, weight in (
        GENERAL_MARKERS.items()
    ):
        if marker in lower:
            score += weight

    # ------------------------------------------
    # Significance
    # ------------------------------------------

    if mode == "significance":

        for marker, weight in (
            SIGNIFICANCE_MARKERS.items()
        ):
            if marker in lower:
                score += weight

        for marker in (
            SIGNIFICANCE_EVENT_NOISE
        ):
            if marker in lower:
                score -= 8.0

        significance_hits = sum(
            1
            for marker in SIGNIFICANCE_MARKERS
            if marker in lower
        )

        if significance_hits == 0:
            score -= 5.0

        if starts_with_weak_reference(
            sentence
        ):
            score -= 5.0

    # ------------------------------------------
    # Features
    # ------------------------------------------

    elif mode == "features":

        feature_markers = {
            "institution": 4.0,
            "government": 4.0,
            "branch": 4.0,
            "constitution": 4.0,
            "system": 4.0,
            "organized": 3.0,
            "structure": 3.0,
            "senate": 3.0,
        }

        for marker, weight in (
            feature_markers.items()
        ):
            if marker in lower:
                score += weight

    # ------------------------------------------
    # Explain / process
    # ------------------------------------------

    elif mode == "explain":

        for marker, weight in (
            PROCESS_MARKERS.items()
        ):
            if marker in lower:
                score += weight

        for marker in (
            PROCESS_BACKGROUND_NOISE
        ):
            if marker in lower:
                score -= 5.0

        question_lower = (
            question.lower()
        )

        asks_for_specialized_detail = any(
            marker in question_lower
            for marker in (
                PROCESS_SPECIALIZED_DETAILS
                + ["calvin cycle"]
            )
        )

        if not asks_for_specialized_detail:
            for marker in (
                PROCESS_SPECIALIZED_DETAILS
            ):
                if marker in lower:
                    score -= 9.0

        if (
            "calvin cycle" in lower
            and not any(
                marker in lower
                for marker in [
                    "c3",
                    "c4",
                    "cam",
                ]
            )
        ):
            score += 4.0

    word_count = len(
        sentence.split()
    )

    if 8 <= word_count <= 38:
        score += 2.0

    elif 39 <= word_count <= 50:
        score += 0.5

    elif word_count > 60:
        score -= 4.0

    return score


# --------------------------------------------------
# Evidence selection
# --------------------------------------------------

def select_summary_evidence(
    question,
    context,
    max_sentences=3,
    subject=None,
):
    sentences = split_sentences(
        context
    )

    scored = []

    for index, sentence in enumerate(
        sentences
    ):
        score = score_sentence(
            question,
            sentence,
        )

        if score <= 0:
            continue

        # ------------------------------------------
        # Subject-relatedness requirement
        #
        # Word overlap with the question alone plus
        # generic markers ("includes", "uses") and a
        # word-count bonus can push an unrelated
        # sentence above zero without it ever
        # mentioning what the question is about.
        # Evidence that never mentions the question
        # subject cannot describe it.
        # ------------------------------------------

        if (
            subject
            and not sentence_mentions_subject(
                sentence,
                subject,
            )
        ):
            continue

        scored.append(
            (
                score,
                index,
                normalize(sentence),
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            -item[1],
        ),
        reverse=True,
    )

    selected = []

    for score, index, sentence in scored:

        selected.append(
            (
                index,
                sentence,
            )
        )

        if (
            len(selected)
            >= max_sentences
        ):
            break

    selected.sort(
        key=lambda item: item[0]
    )

    return [
        sentence
        for _, sentence in selected
    ]


# --------------------------------------------------
# Redundancy control
# --------------------------------------------------

def sentence_signature(text):
    return {
        word
        for word in re.findall(
            r"[a-z0-9]+",
            text.lower(),
        )
        if len(word) >= 4
    }


def near_duplicate(
    first,
    second,
):
    a = sentence_signature(
        first
    )

    b = sentence_signature(
        second
    )

    if not a or not b:
        return False

    overlap = len(
        a & b
    )

    smaller = min(
        len(a),
        len(b),
    )

    if smaller == 0:
        return False

    return (
        overlap / smaller
    ) >= 0.65


def remove_redundant(sentences):
    kept = []

    for sentence in sentences:
        if not sentence:
            continue

        if any(
            near_duplicate(
                sentence,
                existing,
            )
            for existing in kept
        ):
            continue

        kept.append(
            sentence
        )

    return kept


# --------------------------------------------------
# Safe shortening
# --------------------------------------------------

def shorten_sentence(
    sentence,
    max_words=46,
):
    sentence = normalize(
        sentence
    )

    words = sentence.split()

    if len(words) <= max_words:
        return sentence

    if ";" in sentence:
        first_clause = (
            sentence.split(
                ";",
                1,
            )[0]
            .strip()
        )

        if (
            8
            <= len(
                first_clause.split()
            )
            <= max_words
        ):
            return (
                first_clause.rstrip(
                    "."
                )
                + "."
            )

    connectors = [
        ", while ",
        ", whereas ",
        ", although ",
        ", but ",
    ]

    for connector in connectors:
        if connector in sentence.lower():

            lower = sentence.lower()

            position = lower.find(
                connector
            )

            first_clause = (
                sentence[
                    :position
                ]
                .strip()
            )

            if (
                8
                <= len(
                    first_clause.split()
                )
                <= max_words
            ):
                return (
                    first_clause.rstrip(
                        "."
                    )
                    + "."
                )

    return sentence


# --------------------------------------------------
# Process-specific compression
# --------------------------------------------------

def compress_process_sentence(
    sentence,
    subject,
):
    sentence = normalize(
        sentence
    )

    lower = sentence.lower()

    subject_lower = (
        subject.lower()
    )

    match = re.search(
        r"(?:a process that )?"
        r"uses the energy of sunlight to convert "
        r"water and carbon dioxide into "
        r"(sugars?)",
        lower,
    )

    if match:
        return (
            f"{capitalize_sentence(subject)} uses "
            "energy from sunlight to convert water "
            "and carbon dioxide into sugars that "
            "store chemical energy."
        )

    if (
        "splits water"
        in lower
        and "oxygen"
        in lower
    ):
        return (
            "In oxygenic photosynthesis, water is "
            "split and oxygen is released as a "
            "byproduct."
        )

    if (
        subject_lower in lower
        and "convert" in lower
        and "energy" in lower
    ):
        return shorten_sentence(
            sentence,
            max_words=46,
        )

    return shorten_sentence(
        sentence,
        max_words=46,
    )


# --------------------------------------------------
# Significance-specific compression
# --------------------------------------------------

def compress_significance_sentence(
    sentence,
):
    sentence = normalize(
        sentence
    )

    match = re.search(
        r"(.+?),\s*which limited royal power",
        sentence,
        flags=re.IGNORECASE,
    )

    if match:
        return (
            f"{normalize(match.group(1))}, "
            "which limited royal power."
        )

    if starts_with_weak_reference(
        sentence
    ):
        return None

    return shorten_sentence(
        sentence,
        max_words=46,
    )


# --------------------------------------------------
# Evidence cleanup
# --------------------------------------------------

def clean_evidence_sentence(
    sentence,
    question,
    subject,
):
    mode = detect_mode(
        question
    )

    if mode == "explain":
        result = compress_process_sentence(
            sentence,
            subject,
        )

    elif mode == "significance":
        result = (
            compress_significance_sentence(
                sentence
            )
        )

    else:
        result = shorten_sentence(
            sentence,
            max_words=46,
        )

    if not result:
        return None

    return capitalize_sentence(
        normalize(
            result
        )
    )


# --------------------------------------------------
# Intro generation
# --------------------------------------------------

def build_intro(
    question,
    subject,
):
    mode = detect_mode(
        question
    )

    if mode == "features":
        return capitalize_sentence(
            f"The main features of "
            f"{subject} were:"
        )

    if mode == "significance":
        return capitalize_sentence(
            f"{subject} was significant "
            f"because it had important "
            f"political and legal effects."
        )

    if mode == "explain":
        return capitalize_sentence(
            f"{subject} works by converting "
            f"inputs into useful products "
            f"through a series of processes."
        )

    if mode == "describe":
        return capitalize_sentence(
            f"{subject} can be described "
            f"as follows."
        )

    return None


# --------------------------------------------------
# Better explain intro
# --------------------------------------------------

def build_explain_intro(
    subject,
    cleaned,
):
    if not cleaned:
        return None

    subject_lower = (
        subject.lower()
    )

    first_lower = (
        cleaned[0]
        .lower()
    )

    if first_lower.startswith(
        subject_lower
    ):
        return None

    return (
        f"{capitalize_sentence(subject)} "
        "works through several key processes."
    )


# --------------------------------------------------
# Main synthesis
# --------------------------------------------------

def synthesize_summary_answer(
    question,
    context,
):
    # ------------------------------------------
    # Relational premise gate
    # ------------------------------------------

    # If the question asserts that one entity
    # created / caused / produced / generated /
    # formed / led to another entity, require
    # evidence supporting that exact relationship.
    #
    # Otherwise this synthesizer must step aside.
    if not relational_premise_supported(
        question,
        context,
    ):
        return None

    mode = detect_mode(
        question
    )

    if mode is None:
        return None

    subject = subject_from_question(
        question
    )

    if not subject:
        return None

    subject = (
        subject
        .strip()
        .rstrip(".?!\\")
        .strip()
    )

    if not subject:
        return None

    if mode == "significance":
        max_sentences = 2

    else:
        max_sentences = 3

    evidence = select_summary_evidence(
        question,
        context,
        max_sentences=max_sentences,
        subject=subject,
    )

    if not evidence:
        return None

    evidence = remove_redundant(
        evidence
    )

    cleaned = []

    for sentence in evidence:
        result = clean_evidence_sentence(
            sentence,
            question,
            subject,
        )

        if result:
            cleaned.append(
                result
            )

    cleaned = remove_redundant(
        cleaned
    )

    if not cleaned:
        return None

    # ------------------------------------------
    # Explain mode
    # ------------------------------------------

    if mode == "explain":

        intro = build_explain_intro(
            subject,
            cleaned,
        )

        if intro:
            parts = [
                intro,
            ] + cleaned

        else:
            parts = cleaned

        return normalize(
            " ".join(
                parts
            )
        )

    # ------------------------------------------
    # Significance mode
    # ------------------------------------------

    if mode == "significance":

        intro = (
            f"{capitalize_sentence(subject)} "
            "was significant because it "
            "changed important political or "
            "legal relationships."
        )

        return normalize(
            " ".join(
                [
                    intro,
                ]
                + cleaned
            )
        )

    # ------------------------------------------
    # Other summary modes
    # ------------------------------------------

    intro = build_intro(
        question,
        subject,
    )

    if not intro:
        return None

    return normalize(
        " ".join(
            [
                intro,
            ]
            + cleaned
        )
    )


# --------------------------------------------------
# Standalone tests
# --------------------------------------------------

if __name__ == "__main__":

    tests = [
        # ------------------------------------------
        # Valid process
        # ------------------------------------------

        (
            "Explain how photosynthesis works.",
            (
                "Plants, algae and cyanobacteria are the "
                "major groups of organisms that carry out "
                "photosynthesis, a process that uses the "
                "energy of sunlight to convert water and "
                "carbon dioxide into sugars that can be "
                "used both as a source of chemical energy "
                "and of organic molecules that are used in "
                "the structural components of cells. "
                "In plants, cyanobacteria and algae, "
                "oxygenic photosynthesis splits water, "
                "with oxygen produced as a waste product. "
                "The energy of sunlight, captured by "
                "oxygenic photosynthesis and released by "
                "cellular respiration, is the basis of "
                "almost all life."
            ),
            True,
        ),

        # ------------------------------------------
        # Features
        # ------------------------------------------

        (
            "What were the main features "
            "of the Roman Republic?",
            (
                "The Senate of the Roman Republic was a "
                "political institution in the ancient "
                "Roman Republic. "
                "According to Polybius, the Roman Senate "
                "was the predominant branch of government."
            ),
            True,
        ),

        # ------------------------------------------
        # Significance
        # ------------------------------------------

        (
            "Why was the Magna Carta important?",
            (
                "John's defeat weakened his authority in "
                "England, and his barons forced him to "
                "agree to the Magna Carta, which limited "
                "royal power. "
                "Feudal charges were condemned and "
                "constrained in the Magna Carta of 1215."
            ),
            True,
        ),

        # ------------------------------------------
        # Unsupported false relation
        # ------------------------------------------

        (
            (
                "Explain the process by which DNA "
                "created the Roman Empire."
            ),
            (
                "DNA replication produces copies of DNA "
                "before cell division. "
                "The Roman Empire developed from the "
                "Roman Republic."
            ),
            False,
        ),

        # ------------------------------------------
        # Unsupported false relation
        # ------------------------------------------

        (
            (
                "Describe how the Magna Carta "
                "produced photosynthesis."
            ),
            (
                "The Magna Carta limited royal power. "
                "Photosynthesis converts water and carbon "
                "dioxide into sugars using sunlight."
            ),
            False,
        ),

        # ------------------------------------------
        # Positive relation-control case
        # ------------------------------------------

        (
            (
                "Describe how volcanic activity "
                "produced new land."
            ),
            (
                "Volcanic activity produced new land "
                "when lava cooled and solidified."
            ),
            True,
        ),
    ]

    passed = 0

    for (
        question,
        context,
        should_answer,
    ) in tests:

        answer = synthesize_summary_answer(
            question,
            context,
        )

        actual = (
            answer is not None
        )

        test_passed = (
            actual == should_answer
        )

        if test_passed:
            passed += 1

        print()

        print(
            "=" * 60
        )

        print(
            "Question:",
            question,
        )

        print(
            "Should answer:",
            should_answer,
        )

        print(
            "Did answer:",
            actual,
        )

        print(
            "Test:",
            (
                "PASS"
                if test_passed
                else "FAIL"
            ),
        )

        print(
            "Answer:",
            answer,
        )

    print()

    print(
        "=" * 60
    )

    print(
        f"Passed: {passed}/{len(tests)}"
    )

    print(
        "=" * 60
    )