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

    # WikiText-style spaced hyphens:
    # "non - Roman" -> "non-Roman"
    text = re.sub(
        r"\s*-\s*",
        "-",
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


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being",
    "by", "did", "do", "does", "for", "from", "had", "has",
    "have", "how", "in", "into", "is", "it", "of", "on", "or",
    "the", "to", "was", "were", "what", "when", "where",
    "which", "who", "why", "with",
}


def content_terms(text):
    """Content terms (lowercase, non-stopword, length >= 3)."""
    return {
        word
        for word in re.findall(
            r"[a-z0-9']+",
            text.lower(),
        )
        if (
            word not in _STOPWORDS
            and len(word) >= 3
        )
    }


def sentence_shares_subject_terms(
    sentence,
    subject,
):
    """Generic subject-relatedness check.

    A causal answer may only be built from sentences that share at
    least one content term with the question subject. Causal marker
    vocabulary ("because", "declined", ...) alone is NOT relatedness —
    without this anchor, an unrelated sentence carrying a causal
    marker gets templated into an answer for a completely different
    subject.
    """
    subject_terms = content_terms(
        subject
    )

    if not subject_terms:
        # No extractable subject terms — nothing to require.
        return True

    sentence_terms = content_terms(
        sentence
    )

    return bool(
        subject_terms
        & sentence_terms
    )


# --------------------------------------------------
# Question parsing
# --------------------------------------------------

def parse_causal_question(question):
    """
    Returns:

        {
            "subject": "...",
            "relation": "decline",
        }

    or None if the question is not a supported
    causal form.
    """

    question = (
        question
        .strip()
    )

    patterns = [
        # ------------------------------------------
        # Why did X ...
        # ------------------------------------------

        (
            r"why did (.+?) decline[.?!]?$",
            "decline",
        ),
        (
            r"why did (.+?) collapse[.?!]?$",
            "collapse",
        ),
        (
            r"why did (.+?) weaken[.?!]?$",
            "weaken",
        ),
        (
            r"why did (.+?) fail[.?!]?$",
            "fail",
        ),
        (
            r"why did (.+?) fall[.?!]?$",
            "fall",
        ),
        (
            r"why did (.+?) end[.?!]?$",
            "end",
        ),

        # ------------------------------------------
        # What caused X to ...
        # ------------------------------------------

        (
            r"what caused (.+?) to decline[.?!]?$",
            "decline",
        ),
        (
            r"what caused (.+?) to collapse[.?!]?$",
            "collapse",
        ),
        (
            r"what caused (.+?) to weaken[.?!]?$",
            "weaken",
        ),
        (
            r"what caused (.+?) to fail[.?!]?$",
            "fail",
        ),
        (
            r"what caused (.+?) to fall[.?!]?$",
            "fall",
        ),
        (
            r"what caused (.+?) to end[.?!]?$",
            "end",
        ),

        # ------------------------------------------
        # What led to ...
        # ------------------------------------------

        (
            r"what led to (?:the )?decline of (.+?)[.?!]?$",
            "decline",
        ),
        (
            r"what led to (?:the )?collapse of (.+?)[.?!]?$",
            "collapse",
        ),
        (
            r"what led to (?:the )?fall of (.+?)[.?!]?$",
            "fall",
        ),

        # ------------------------------------------
        # What factors contributed to ...
        # ------------------------------------------

        (
            r"what factors contributed to "
            r"(?:the )?decline of (.+?)[.?!]?$",
            "decline",
        ),
        (
            r"what factors contributed to "
            r"(?:the )?collapse of (.+?)[.?!]?$",
            "collapse",
        ),
        (
            r"what factors contributed to "
            r"(?:the )?fall of (.+?)[.?!]?$",
            "fall",
        ),
    ]

    for pattern, relation in patterns:
        match = re.fullmatch(
            pattern,
            question,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        subject = (
            match.group(1)
            .strip()
            .rstrip(".?!")
        )

        if not subject:
            continue

        return {
            "subject":
                subject,

            "relation":
                relation,
        }

    return None


def subject_from_question(question):
    parsed = parse_causal_question(
        question
    )

    if parsed is None:
        return None

    return parsed[
        "subject"
    ]


# --------------------------------------------------
# Cause scoring
# --------------------------------------------------

DIRECT_CAUSAL_PATTERNS = [
    (
        r"\bbecause of\b",
        10.0,
    ),
    (
        r"\bbecause\b",
        9.0,
    ),
    (
        r"\bdue to\b",
        9.0,
    ),
    (
        r"\bcaused by\b",
        9.0,
    ),
    (
        r"\bfell after\b",
        8.0,
    ),
    (
        r"\bcollapsed after\b",
        8.0,
    ),
    (
        r"\bdeclined because\b",
        10.0,
    ),
    (
        r"\bwas overrun\b",
        7.0,
    ),
    (
        r"\bwas defeated\b",
        6.0,
    ),
]


CAUSE_MARKERS = {
    "decline": 2.0,
    "declined": 2.5,
    "collapse": 2.0,
    "collapsed": 2.5,
    "fall": 1.5,
    "fell": 2.0,
    "weaken": 1.5,
    "weakened": 2.0,
    "failed": 2.0,
    "ended": 1.5,

    "military": 2.0,
    "army": 1.5,
    "troops": 1.5,
    "overrun": 3.0,
    "invading": 2.5,
    "invasion": 2.5,
    "defeat": 2.5,
    "defeated": 3.0,
    "revolt": 2.5,

    "territorial": 2.5,
    "territory": 1.5,
    "provinces": 1.5,

    "economic": 2.0,
    "economy": 2.0,

    "political": 1.5,
    "leadership": 1.5,
    "government": 1.5,

    "nationalist": 2.0,
    "nationalism": 2.0,

    "pressure": 1.5,
    "crisis": 1.5,
}


def score_sentence(sentence):
    lower = sentence.lower()

    score = 0.0

    for pattern, weight in (
        DIRECT_CAUSAL_PATTERNS
    ):
        if re.search(
            pattern,
            lower,
        ):
            score += weight

    for marker, weight in (
        CAUSE_MARKERS.items()
    ):
        if marker in lower:
            score += weight

    word_count = len(
        sentence.split()
    )

    if 8 <= word_count <= 45:
        score += 1.0

    elif 46 <= word_count <= 60:
        score += 0.2

    elif word_count > 60:
        score -= 3.0

    return score


# --------------------------------------------------
# Clause extraction
# --------------------------------------------------

def extract_because_clause(sentence):
    patterns = [
        r"\bbecause of (.+?)(?:\.|$)",
        r"\bbecause (.+?)(?:\.|$)",
        r"\bdue to (.+?)(?:\.|$)",
        r"\bcaused by (.+?)(?:\.|$)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            sentence,
            flags=re.IGNORECASE,
        )

        if match:
            return normalize(
                match.group(1)
            )

    return None


def extract_after_clause(sentence):
    patterns = [
        r"\bfell after (.+?)(?:\.|$)",
        r"\bcollapsed after (.+?)(?:\.|$)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            sentence,
            flags=re.IGNORECASE,
        )

        if match:
            return normalize(
                match.group(1)
            )

    return None


# --------------------------------------------------
# Evidence selection
# --------------------------------------------------

def rank_sentences(context):
    sentences = split_sentences(
        context
    )

    scored = []

    for index, sentence in enumerate(
        sentences
    ):
        score = score_sentence(
            sentence
        )

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

    return scored


def select_causal_evidence(
    context,
    max_sentences=3,
):
    ranked = rank_sentences(
        context
    )

    selected = []

    for score, _, sentence in ranked:
        if score <= 0:
            continue

        selected.append(
            sentence
        )

        if (
            len(selected)
            >= max_sentences
        ):
            break

    return selected


# --------------------------------------------------
# Theme detection
# --------------------------------------------------

THEMES = [
    (
        "military pressure",
        [
            "military",
            "army",
            "troops",
            "overrun",
            "invading",
            "invasion",
            "defeat",
            "defeated",
            "war",
        ],
    ),
    (
        "territorial losses",
        [
            "territorial",
            "territory",
            "provinces",
            "lost provinces",
        ],
    ),
    (
        "economic problems",
        [
            "economic",
            "economy",
            "financial",
        ],
    ),
    (
        "political instability",
        [
            "political",
            "revolt",
            "leadership",
            "government",
        ],
    ),
    (
        "nationalist movements",
        [
            "nationalist",
            "nationalism",
        ],
    ),
]


def detect_themes(sentences):
    text = " ".join(
        sentences
    ).lower()

    found = []

    for label, markers in THEMES:
        if any(
            marker in text
            for marker in markers
        ):
            found.append(
                label
            )

    return found


def join_naturally(items):
    if not items:
        return ""

    if len(items) == 1:
        return items[0]

    if len(items) == 2:
        return (
            f"{items[0]} and {items[1]}"
        )

    return (
        ", ".join(
            items[:-1]
        )
        + f", and {items[-1]}"
    )


# --------------------------------------------------
# Relation wording
# --------------------------------------------------

def relation_past_tense(relation):
    mapping = {
        "decline":
            "declined",

        "collapse":
            "collapsed",

        "weaken":
            "weakened",

        "fail":
            "failed",

        "fall":
            "fell",

        "end":
            "ended",
    }

    return mapping.get(
        relation,
        "declined",
    )


def build_relation_answer(
    subject,
    relation,
    connector,
    cause,
):
    verb = relation_past_tense(
        relation
    )

    cause = (
        cause
        .strip()
        .rstrip(".")
    )

    if connector == "because":
        answer = (
            f"{subject} {verb} because of "
            f"{cause}."
        )

    elif connector == "after":
        answer = (
            f"{subject} {verb} after "
            f"{cause}."
        )

    else:
        answer = (
            f"{subject} {verb} because of "
            f"{cause}."
        )

    return capitalize_sentence(
        normalize(
            answer
        )
    )


def _sentence_contains_term(sentence_lower, term):
    """Boundary-safe term match with light inflection tolerance."""
    variants = {term}
    if len(term) > 4 and term.endswith("ed"):
        variants.add(term[:-2])
    if len(term) > 5 and term.endswith("ing"):
        variants.add(term[:-3])
        variants.add(term[:-3] + "e")
    if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
        variants.add(term[:-1])
    alternatives = "|".join(
        re.escape(variant) for variant in sorted(variants)
    )
    return re.search(
        r"\b(?:" + alternatives + r")(?:s|es|ed|ing|'s)?\b",
        sentence_lower,
    ) is not None


def _shares_stem(first, second):
    """Crude stem sharing for morphological variants (decline/declined)."""
    if not first or not second:
        return False
    shorter = first if len(first) <= len(second) else second
    longer = second if shorter is first else first
    return longer.startswith(shorter[: max(4, len(shorter) - 1)])


# Interrogative-frame vocabulary: these words carry the QUESTION FORM,
# not a premise modifier, and must never count as focus terms.
_FRAME_TERMS = {
    "cause", "caused", "causes", "lead", "leads", "led",
    "contribute", "contributes", "contributed", "factor", "factors",
    "result", "resulted", "results", "due", "happen", "happened",
    "explain", "describe", "reason", "reasons",
}


def _premise_focus_terms(question, subject, relation):
    """Content terms the question asserts BEYOND subject and relation.

    A causal question may embed additional premise modifiers — a year
    ("fall in 2020"), an agent ("signed by Napoleon"), an extra
    attribute ("had a President"). Evidence that merely describes the
    subject's general history does NOT support those specific premises;
    at least one focus term must appear in the evidence sentence.
    """
    question_terms = {
        term
        for term in content_terms(question or "")
        if term not in _FRAME_TERMS
    }
    subject_terms = content_terms(subject or "")
    relation_terms = content_terms(relation or "")

    extra = set()
    for term in question_terms:
        if term in subject_terms:
            continue
        if any(
            _shares_stem(term, rel)
            for rel in relation_terms
        ):
            continue
        # Also strip terms that are causal-verb synonyms of the
        # relation.  "fall" and "decline" are not morphological
        # variants but both appear in CAUSE_MARKERS as relation
        # verbs — stripping one when the other is the parsed relation
        # prevents "fall" from surviving as a false-focus term.
        if term in CAUSE_MARKERS and relation in CAUSE_MARKERS:
            continue
        extra.add(term)
    return extra


_ANAPHORIC_STARTS = (
    "he ", "she ", "it ", "they ", "this ", "these ", "those ",
)


def _unsafe_cause_clause(clause):
    """Detect cause clauses that cannot stand alone as an explanation.

    A clause beginning with an unresolved pronoun ("he assumed the
    title of king") is anaphoric — it borrows its subject from earlier
    discourse and would be templated into a nonsense answer. Clauses
    containing stray parenthesis fragments are likewise truncated
    text rather than a self-contained cause.
    """
    lowered = clause.strip().lower()
    if not lowered:
        return True
    if any(
        lowered.startswith(start)
        for start in _ANAPHORIC_STARTS
    ):
        return True
    return "(" in clause or ")" in clause


# --------------------------------------------------
# Main synthesis
# --------------------------------------------------

def synthesize_causal_answer(
    question,
    context,
    original_question=None,
):
    parsed = parse_causal_question(
        question
    )

    if parsed is None:
        return None

    subject = parsed[
        "subject"
    ]

    relation = parsed[
        "relation"
    ]

    evidence = select_causal_evidence(
        context,
        max_sentences=3,
    )

    if not evidence:
        return None

    # ------------------------------------------
    # Subject-relatedness filter
    #
    # Every piece of causal evidence must share
    # at least one content term with the question
    # subject. A sentence that merely carries a
    # causal marker ("because", "declined") but
    # never mentions the subject cannot explain
    # the subject.
    # ------------------------------------------

    evidence = [
        sentence
        for sentence in evidence
        if sentence_shares_subject_terms(
            sentence,
            subject,
        )
    ]

    if not evidence:
        return None

    # ------------------------------------------
    # Premise-focus filter
    #
    # If the question asserts premise modifiers beyond the subject
    # and relation (a year, an agent, an extra attribute), every
    # piece of causal evidence must address at least one of them.
    # Otherwise the synthesizer would happily "explain" a false
    # premise from generic subject history.
    # ------------------------------------------

    focus_terms = _premise_focus_terms(
        question,
        subject,
        relation,
    )
    if original_question:
        focus_terms |= _premise_focus_terms(
            original_question,
            subject,
            relation,
        )

    if focus_terms:
        evidence = [
            sentence
            for sentence in evidence
            if any(
                _sentence_contains_term(sentence.lower(), term)
                for term in focus_terms
            )
        ]

    if not evidence:
        return None

    # ------------------------------------------
    # Highest priority:
    # explicit because/due-to clause
    # ------------------------------------------

    for sentence in evidence:
        because_clause = (
            extract_because_clause(
                sentence
            )
        )

        if because_clause and not _unsafe_cause_clause(
            because_clause
        ):
            return build_relation_answer(
                subject,
                relation,
                "because",
                because_clause,
            )

    # ------------------------------------------
    # Second priority:
    # explicit fall/collapse-after clause
    # ------------------------------------------

    for sentence in evidence:
        after_clause = extract_after_clause(
            sentence
        )

        if after_clause:
            cause = after_clause

            if cause.lower().startswith(
                "first "
            ):
                cause = cause[6:]

            return build_relation_answer(
                subject,
                relation,
                "after",
                cause,
            )

    # ------------------------------------------
    # Multi-cause synthesis
    # ------------------------------------------

    themes = detect_themes(
        evidence
    )

    if themes:
        return build_relation_answer(
            subject,
            relation,
            "because",
            join_naturally(
                themes
            ),
        )

    # ------------------------------------------
    # Safe extractive fallback
    # ------------------------------------------

    best = evidence[0]

    return capitalize_sentence(
        normalize(
            best
        )
    )


# --------------------------------------------------
# Standalone tests
# --------------------------------------------------

if __name__ == "__main__":

    context = (
        "Many theories have been advanced in way of "
        "explanation for decline of the Roman Empire. "
        "Militarily, however, the Empire finally fell "
        "after first being overrun by various non-Roman "
        "peoples and then having its heart in Italy "
        "seized by Germanic troops in a revolt. "
        "The Roman capital had moved to Ravenna, and "
        "the Empire had lost many of its former provinces."
    )

    tests = [
        "Why did the Roman Empire decline?",
        "What caused the Roman Empire to decline?",
        "What led to the decline of the Roman Empire?",
        "What factors contributed to the decline of the Roman Empire?",
    ]

    for question in tests:
        print()

        print(
            "Question:",
            question,
        )

        answer = synthesize_causal_answer(
            question,
            context,
        )

        print(
            "Answer:",
            answer,
        )