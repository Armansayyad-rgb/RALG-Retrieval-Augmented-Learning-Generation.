import logging
import re

import torch
from tokenizers import Tokenizer

from log_helper import setup_logging

from config import (  # noqa: E402
    LOGS_DIR,
    TOKENIZER_FILE,
    MODEL_FILE,
    KNOWLEDGE_FILES,
    MAX_INPUT_TOKENS,
    MAX_NEW_TOKENS,
    CONFIDENCE_THRESHOLD,
    RUNTIME_UPLOAD_DIR,
)

# Backwards-compatible alias: callers historically used ``LOG_DIR``.
LOG_DIR = LOGS_DIR

logger = setup_logging(
    log_dir=LOG_DIR,
    log_name="rag_chat",
)

from model_v2 import SmallLMV2
from extractor_v1 import extract_answer
from router_v1 import route_question
from confidence_v1 import extraction_confidence

# --- Factual QA detection (cheap, heuristic-based) ---
FACTUAL_STARTS = (
    "who ",
    "when ",
    "where ",
    "what ",
    "which ",
    "how long ",
)


def is_factual_question(question):
    """Check if a question is a factual QA question (who, when, where, what, which)."""
    q = question.strip().lower()
    for start in FACTUAL_STARTS:
        if q.startswith(start):
            return True
    return False


def has_multi_hop_followup(question):
    """Cheap structural check: returns True only when the question
    visibly combines two information needs via an explicit follow-up
    sub-clause joined with "and" (or a similar connector).

    This is intentionally stricter than a plain keyword list. The
    markers here identify a SECOND information need
    ("what followed?", "what happened?", "what were the consequences?",
    "what came next?", "afterward?", etc.) that is joined to a primary
    causal/effect/change clause.

    Single-clause questions such as:

        "Why did the Roman Empire decline?"
        "What effects did the Industrial Revolution have?"
        "How did the Black Death change European society?"
        "What is the structure of DNA?"

    do NOT match here, because they only carry ONE information need.

    Genuine multi-hop questions such as:

        "What caused the fall of the Roman Empire and what followed?"
        "What led to X and what happened afterward?"
        "How did X change Y and what were the consequences?"
        "What caused the Industrial Revolution and what came next?"

    DO match here. The check is purely substring-based and adds no
    new model, dependency, or inference cost.
    """
    q = question.strip().lower()

    # Follow-up interrogatives / continuations that signal a SECOND
    # information need. Cheap substring match — no new model.
    followup_markers = (
        "what followed",
        "what happens",
        "what happened",
        "what was the result",
        "what were the consequences",
        "what were the effects",
        "what came next",
        "what came after",
        "what then",
        "what resulted",
        "what changed",
        "what was the aftermath",
        "what were the aftermath",
        "afterward",
        "afterwards",
        "after that",
        "as a result",
        "and what effect",
        "its consequences",
        "its effects",
        "its aftermath",
        "the consequences",
        "the effects",
        "the aftermath",
        "effects of",
    )

    # Two-clause follow-up joined by " and " / " or ".
    for connector in (" and ", " or "):
        if connector not in q:
            continue
        tail = q.split(connector, 1)[1]
        if any(marker in tail for marker in followup_markers):
            return True

    # Single-clause causal/effect questions that ASK ABOUT an
    # effect on / influence over / impact on / change in a SECOND
    # subject carry two linked information needs (cause-of-X and
    # effect-on-Y). The question cannot be answered from a single
    # retrieval focused only on the cause subject.
    #
    # Examples that MUST be flagged as multi-hop:
    # - "How did X's decline affect the development of Y?"
    # - "How did X influence the development of Y?"
    # - "What were the effects of X on Y?"
    # - "What impact did X have on Y?"
    # - "How did X change Y?"
    #
    # Pure single-subject questions such as:
    # - "How did photosynthesis convert sunlight to energy?"
    # - "What effects did the Industrial Revolution have?"
    # do NOT match — they only reference one subject.
    second_subject_intent_markers = (
        # effect-on / influence-on / impact-on / change-in
        " affect the ",
        " affect ",
        " influences the ",
        " influence the ",
        " influence ",
        " influenced the ",
        " impacted ",
        " impact on ",
        " change in ",
        " changed ",
        " shaped ",
        " transform ",
        " lead to changes in ",
        " affect the development of ",
        " influence the development of ",
        " shape the development of ",
        " influence the emergence of ",
        " affect the evolution of ",
        " effects on ",
        " effect on ",
        " impact on ",
        " influence on ",
        " consequences for ",
        " consequences to ",
    )

    # The "what were the effects of X on Y?" pattern needs special
    # handling — the "effect" noun itself is the marker, not just
    # a verb. Trigger when both "effects of" and an "on <subject>"
    # tail are present (the "on" phrase indicates a second subject).
    if (
        "effects of" in q
        and " on " in q
    ):
        # Avoid single-subject forms like "What effects did X have?"
        # which use "on" only as a preposition-relative construction.
        # An explicit " on " followed by content (not "on the") signals
        # a second information need.
        on_idx = q.rfind(" on ")
        tail = q[on_idx + 4:].strip().rstrip("?.!")
        # Heuristic: a second subject phrase carries at least one
        # distinctive word longer than 3 chars.
        if any(
            len(word) > 3
            for word in tail.split()
            if word
            not in {"the", "a", "an", "of", "and", "for", "with", "to"}
        ):
            return True

    # The "what impact did X have on Y?" pattern.
    if (
        "impact" in q
        and " on " in q
    ):
        return True

    # The "how did X ... affect/influence ... Y" pattern.
    if any(marker in q for marker in second_subject_intent_markers):
        return True

    return False


def is_multi_hop_question(question, plan=None):
    """Check if a question likely requires multi-hop reasoning.

    Uses a cheap structural check. A specialized semantic intent in the
    plan does NOT automatically suppress multi-hop — a question can
    legitimately combine a specialized intent (cause / effect / change)
    with a follow-up sub-clause that requires a second retrieval pass.

    Single-clause questions with a specialized intent continue to flow
    to their specialized synthesizer with 1 retrieval pass, exactly as
    before. Genuine two-clause questions are flagged for a max of 2
    retrieval passes while preserving the specialized intent.
    """
    # Cheap structural check — independent of the plan.
    return has_multi_hop_followup(question)


def decompose_multi_hop_question(question):
    """Split a genuine two-concept transition question into its two
    information needs.

    Returns ``(concept_a, concept_b)`` or ``None``.

    The check is GENERIC and structural: the requested answer requires
    a relationship/transition between TWO distinct concepts
    (a cause subject and an effect target), so a single retrieval pass
    focused on the question as a whole cannot supply evidence for both
    sides. It is deliberately NOT a keyword list ("how did" / "effects
    of") — those also appear in single-intent questions. It only fires
    when the question explicitly names a second, distinct concept via a
    relational bridge.

    Recognized generic bridges:

    - "How did X's decline/fall/collapse affect Y?"
    - "How did X influence/affect/shape the development of Y?"
    - "What were the effects of X on Y?"
    - "What impact did X have on Y?"

    Two-clause follow-ups ("X and what followed") are handled by the
    caller's "and"-split, so they do not need patterns here.
    """
    q = re.sub(
        r"\s+",
        " ",
        question.strip(),
    )

    patterns = [
        # "How did X's decline affect the development of Y?"
        re.compile(
            r"^(?:how|why)\s+did\s+"
            r"(.+?)(?:'s|’s)\s+"
            r"(?:decline|fall|collapse|weakening)\s+"
            r"(?:affect|affected|influenced|influence|impact|"
            r"shaped|shape|transform|transformed)\s+"
            r"(.+?)[?.!]*$",
            re.IGNORECASE,
        ),
        # "How did X influence/affect/shape the development of Y?"
        re.compile(
            r"^(?:how|why)\s+did\s+"
            r"(.+?)\s+"
            r"(?:affect|affected|influenced|influence|impact|"
            r"shaped|shape|transform|transformed|changed|change)\s+"
            r"(?:the\s+)?"
            r"(?:development|evolution|emergence|rise)\s+of\s+"
            r"(.+?)[?.!]*$",
            re.IGNORECASE,
        ),
        # "What were the effects/consequences/impact of X on Y?"
        re.compile(
            r"^(?:what|what were|what are|what was|what is)\s+"
            r"(?:the\s+)?(?:effects|consequences|impact|influence)\s+"
            r"of\s+(.+?)\s+on\s+(.+?)[?.!]*$",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:
        match = pattern.fullmatch(q)
        if not match:
            continue
        concept_a = match.group(1).strip().rstrip("?.!")
        concept_b = match.group(2).strip().rstrip("?.!")
        if concept_a and concept_b:
            return concept_a, concept_b

    return None


def _clean_second_concept(text, concept_a=None):
    """Normalize a second-concept phrase for use as a retrieval query.

    If concept_a is provided, contextualize the second concept by
    prepending relevant subject terms to avoid vague queries like
    "what followed?" which return noise.
    """
    text = re.sub(
        r"\s+",
        " ",
        text.strip(),
    )
    text = re.sub(
        r"^(?:the|a|an)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = text.strip()

    # If second concept is too vague, try to contextualize it
    if concept_a and len(text.split()) <= 3:
        # Extract key subject terms from concept_a (nouns, proper nouns)
        concept_a_words = re.findall(r'\b[A-Z][a-z]+\b|\b\w{5,}\b', concept_a)
        if concept_a_words:
            # Take first 2-3 meaningful terms from concept_a
            subject_terms = [w for w in concept_a_words[:3] if len(w) > 3]
            if subject_terms:
                return f"{' '.join(subject_terms)} {text}"

    return text


_INFLECTION_SUFFIX = re.compile(r"(?:s|es|ed|ing|'s)?\b")
_TERM_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _term_variants(term):
    """Light morphological variants of a question term.

    Questions inflect differently from evidence prose ("verified" vs
    "verify", "draining" vs "drain"). Variants only WIDEN boundary-safe
    matching to regular inflections; derived-but-different words
    ("press"/"pressure") still never match.
    """
    variants = {term}
    if len(term) > 4 and term.endswith("ied"):
        variants.add(term[:-3] + "y")
    if len(term) > 4 and term.endswith("ed"):
        variants.add(term[:-2])
    if len(term) > 5 and term.endswith("ing"):
        variants.add(term[:-3])
        variants.add(term[:-3] + "e")
    if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
        variants.add(term[:-1])
    return variants


def _contains_term(haystack_lower, term):
    """Word-boundary-aware term containment with light inflection tolerance.

    Matches regular plural/verb inflections ("pumps", "founded",
    "presses") but NOT unrelated derivations or accidental substrings:
    "rate" no longer matches "accurate", "age" no longer matches
    "pages", and "press" no longer matches "pressure". Establishing
    predicate or subject support requires the term to appear as a
    real token in the evidence, not merely as a character run inside
    an unrelated word.
    """
    key = str(term)
    pattern = _TERM_PATTERN_CACHE.get(key)
    if pattern is None:
        alternatives = "|".join(
            re.escape(variant) for variant in sorted(_term_variants(key))
        )
        pattern = re.compile(
            r"\b(?:" + alternatives + r")" + _INFLECTION_SUFFIX.pattern
        )
        _TERM_PATTERN_CACHE[key] = pattern
    return pattern.search(haystack_lower) is not None


def cheap_grounding_check(answer, context):
    """
    Check if important entities/dates/numbers in the answer appear in the retrieved context.
    Uses normalized string matching - no extra LLM call.
    Returns True if the answer is well-grounded in the context.
    """
    if not answer or not context:
        return False

    a = answer.strip().lower()
    c = context.lower()

    # Extract potential entities/dates/numbers from answer:
    # 1. Date patterns (year numbers)
    import re as _re
    date_pattern = r"\b(19|20)\d{2}\b"
    all_dates = _re.findall(date_pattern, a)
    date_nums = [d[0]+d[1] for d in all_dates]

    # Check for year numbers in context
    for y in date_nums:
        if y in c:
            return True

    # 2. Check if any word in the answer (longer than 3 chars) appears in context
    answer_words = [w for w in a.split() if len(w) > 3]
    for word in answer_words:
        if _contains_term(c, word):
            return True

    # 3. Last resort: normalized substring check
    if a in c:
        return True

    return False


def _split_sentences(context):
    """Split a context blob into sentences.

    Handles both ". " (joined evidence sentences) and "\\n"
    (aggregated multi-chunk context) separators. Splitting on
    periods alone would glue the whole aggregated context into one
    giant "sentence" and break sentence-anchored extraction.
    """
    import re as _re

    return [
        s.strip()
        for s in _re.split(r"\.\s+|\n+", context)
        if s.strip()
    ]


# ==================================================
# Post-answer question-addressed check
#
# After an answer is generated, verify that the answer
# actually engages with the question's key content
# terms. This catches false-support cases where the
# evidence contains keyword overlap but the answer
# doesn't address the full question (e.g. cross-domain
# mashups like "compressor lockout steps for DNA
# replication" where the answer mentions lockout but
# ignores DNA entirely).
# ==================================================

_GENERIC_ANSWER_TERMS = frozenset({
    "what", "which", "how", "when", "where", "who",
    "why", "does", "did", "do", "is", "are", "was",
    "were", "the", "a", "an", "and", "or", "but",
    "for", "of", "to", "in", "on", "with", "at",
    "by", "from", "as", "be", "been", "being",
    "have", "has", "had", "must", "should", "can",
    "could", "would", "will", "may", "might",
    "require", "requires", "required", "need",
    "needs", "step", "steps", "procedure",
    "procedures", "process", "system", "method",
    "check", "checks", "checking", "done",
    "before", "after", "during", "while",
    "safety", "maintenance", "operation",
    "describe", "explain", "list", "name",
    "identify", "compare", "contrast", "define",
    "give", "tell", "show", "provide", "state",
})


_NAMED_PHRASE_IN_QUESTION = re.compile(
    r"\b(?:[A-Z0-9][A-Za-z0-9'-]*\s+){1,}"
    r"[A-Z0-9][A-Za-z0-9'-]*\b"
)


def _question_named_phrases(question):
    """Named multi-token entities explicitly present in the question."""
    phrases = []
    for match in _NAMED_PHRASE_IN_QUESTION.finditer(question or ""):
        # Product/model identifiers often appear as scoped context for
        # concise attribute questions ("Which coolant is approved for
        # the Lumen ARC-12?"). The answer may correctly be just the
        # attribute value, so do not require those identifier phrases to
        # be restated here. The separate "for X" gate below still
        # handles full-subject questions where X is the asked-about
        # subject.
        if re.search(r"\d|-", match.group(0)):
            continue
        terms = [
            t.lower()
            for t in re.findall(r"[A-Za-z0-9]{3,}", match.group(0))
            if t.lower() not in _GENERIC_ANSWER_TERMS
        ]
        if len(terms) >= 2:
            phrases.append(terms)
    return phrases


def _answer_addresses_question(question, answer):
    """Check whether the answer engages with the question's main subject.

    Extracts the question's primary subject (the core noun phrase) and
    verifies it appears in the answer.  For cross-domain mashups where
    the question combines unrelated concepts (e.g. "compressor lockout
    steps for DNA replication"), the subject ("DNA replication") will
    not appear in an answer that only discusses compressor lockout.

    Returns False only when the answer completely misses the question's
    subject matter.
    """
    if not answer or not question:
        return True

    q_lower = question.lower()
    a_lower = answer.lower()

    # Extract content terms from the question.
    q_terms = [
        t for t in re.findall(r"[a-z0-9]{3,}", q_lower)
        if t not in _GENERIC_ANSWER_TERMS
    ]

    if not q_terms:
        return True

    # Named entities in the question must not disappear from the
    # answer. This catches cross-concept mashups such as "Magna Carta
    # compressor maintenance" where the answer only discusses the
    # maintenance half and never addresses Magna Carta.
    for phrase_terms in _question_named_phrases(question):
        if not all(
            _contains_term(a_lower, term)
            for term in phrase_terms
        ):
            return False

    # --- "for X" subject gate ---
    # Extract the subject after "for" — the entity being asked about.
    # E.g. "compressor lockout steps for DNA replication" → subject
    # is "dna replication".  The answer must mention it.
    for_match = re.search(
        r"\bfor\s+([a-z0-9\s]+)", q_lower,
    )
    if for_match:
        pre_for = q_lower[:for_match.start()]
        subject_for_markers = (
            "step",
            "steps",
            "procedure",
            "procedures",
            "process",
            "system",
            "systems",
            "configuration",
            "stages",
        )
        enforce_for_subject = any(
            _contains_term(pre_for, marker)
            for marker in subject_for_markers
        )
        for_subject = for_match.group(1).strip()
        for_terms = [
            t for t in re.findall(r"[a-z0-9]{3,}", for_subject)
            if t not in _GENERIC_ANSWER_TERMS
        ]
        if enforce_for_subject and for_terms and not all(
            _contains_term(a_lower, t) for t in for_terms
        ):
            return False

    # --- Restatement gate ---
    # If the answer's first sentence is just restating the question
    # (all question content terms present but the sentence ends with
    # a restatement pattern like "can be described as follows"), the
    # answer provides no real information and should be rejected.
    first_sentence = re.split(r"[.;]", a_lower)[0].strip()
    if first_sentence:
        q_in_first = sum(
            1 for t in q_terms
            if _contains_term(first_sentence, t)
        )
        restatement_patterns = (
            "can be described as follows",
            "is as follows",
            "are as follows",
            "is described as follows",
            "are described as follows",
        )
        if (
            q_in_first == len(q_terms)
            and len(q_terms) >= 3
            and any(
                p in first_sentence
                for p in restatement_patterns
            )
        ):
            return False

    # --- Adjacent bigram gate (weakened) ---
    # Only allow a bigram match if the answer also covers at
    # least one term from outside that bigram.  This prevents
    # "compressor lockout" matching while "DNA replication" is
    # completely absent.
    if len(q_terms) >= 2:
        for i in range(len(q_terms) - 1):
            bigram = {q_terms[i], q_terms[i + 1]}
            if all(_contains_term(a_lower, t) for t in bigram):
                # Require at least one additional term outside
                # the bigram to also appear.
                other_terms = [
                    t for j, t in enumerate(q_terms)
                    if j != i and j != i + 1
                ]
                if not other_terms or any(
                    _contains_term(a_lower, t)
                    for t in other_terms
                ):
                    return True

    # Fallback: at least one content term from the question must
    # appear in the answer.  Cross-domain mashups are already
    # caught by the "for X" subject gate above; this only needs
    # to reject answers with zero topical overlap.
    matched = sum(1 for t in q_terms if _contains_term(a_lower, t))
    return matched >= 1


# ==================================================
# Generic predicate/relevance gate
#
# For factual questions, the question contains an entity
# AND a predicate (the relation being asked). A retrieved
# sentence that mentions the entity but does NOT support
# the predicate is a false-premise trap: e.g. a Ceres
# astronomical symbol does NOT support "chemical symbol for
# unobtainium"; "Atlantis" appearing in a tidal-wave story
# does NOT support "capital of Atlantis".
#
# This gate is deterministic, lexical-only, and adds no
# new model, verifier, or reranker. It rejects only when
# (a) the question contains a known predicate AND
# (b) the candidate sentence mentions the entity BUT does
#     not carry any predicate-aligned vocabulary.
# ==================================================

PREDICATE_LEXICON = {
    # chemistry: atomic number / symbol / formula.
    # The vocab here is INTENTIONAL narrow — only the actual
    # symbol/formula/atomic-number phrases. A sentence saying
    # "Unobtainium is a hypothetical element" mentions the
    # word "element" generically but does NOT provide a
    # chemical symbol. The narrow vocab keeps the gate from
    # accepting such false-premise evidence.
    "chemical symbol": (
        "chemical symbol", "atomic symbol", "symbol is",
        "symbol:", "symbolised", "symbolized",
    ),
    "chemical formula": (
        "chemical formula", "molecular formula",
        "formula is", "formula:",
    ),
    "atomic number": (
        "atomic number", "element number",
        "atomic number is", "atomic number:",
    ),
    # geography: capital / population / located
    "capital": (
        "capital of", "capital is", "capital city of",
        "capital city is", "seat of government",
        "seat of power",
    ),
    "population": (
        "population", "inhabitants", "residents",
        "people lived", "people live",
    ),
    "located": (
        "located in", "situated in", "lies in",
        "country of", "region of",
    ),
    # biology / anatomy
    "habitat": (
        "habitat", "native to", "inhabits",
    ),
    "species": (
        "scientific name", "binomial", "genus",
        "classified as",
    ),
    # history / governance
    "king": (
        "king of", "monarch of", "reigned over",
        "sovereign of",
    ),
    "queen": (
        "queen of", "monarch of", "reigned over",
    ),
    "president": (
        "president of", "head of state",
    ),
    "prime minister": (
        "prime minister of", "head of government",
    ),
    "language": (
        "official language", "language spoken",
        "languages spoken",
    ),
    "currency": (
        "official currency", "monetary unit",
        "national currency",
    ),
    # invented / discovered / written / signed
    "invented": (
        "invented by", "inventor of",
    ),
    "discovered": (
        "discovered by", "discoverer of",
        "discovery of",
    ),
    "signed": (
        "signed by", "ratified by",
        "signature of",
    ),
    "published": (
        "published by", "publisher of",
    ),
    "wrote": (
        "written by", "authored by", "author of",
        "written by",
    ),
    "born": (
        "born on", "was born", "birth date",
        "date of birth",
    ),
    "died": (
        "died on", "death of", "passed away",
        "date of death",
    ),
    "founded": (
        "founded by", "founder of", "cofounded by",
    ),
    # events
    "began": (
        "began on", "started on", "commenced on",
    ),
    "ended": (
        "ended on", "concluded on",
    ),
    # misc
    "cause of death": (
        "cause of death", "killed by", "assassinated",
    ),
    "purpose": (
        "purpose of", "used for",
    ),
    "color": (
        "color is", "colour is",
    ),
}


def _extract_predicate(question):
    """Return the predicate vocabulary list for a question, or [].

    Cheap substring scan against the question text. Multi-word
    predicates are matched longest-first so "chemical symbol"
    beats "symbol" if both are present.
    """
    q = question.lower()
    keys = sorted(
        PREDICATE_LEXICON.keys(),
        key=len,
        reverse=True,
    )
    for key in keys:
        if key in q:
            return list(
                PREDICATE_LEXICON[key]
            )
    return []


def _extract_question_predicate_terms(question):
    """Return meaningful attribute terms from a factual question."""
    match = re.match(
        r"^\s*(?:what|which)\s+(?:is|was|are|were)\s+(?:the\s+)?"
        r"(.+?)\s+(?:for|of|in|on|at)\s+.+?[?.]?\s*$",
        question,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    ignored = {
        "what", "which", "is", "was", "are", "were", "the",
        "a", "an", "for", "of", "in", "on", "at", "and", "to",
    }
    return [
        token
        for token in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", match.group(1).lower())
        if token not in ignored and len(token) > 2
    ]


def _predicate_answers_question(
    question,
    candidate_sentence,
    full_context,
):
    """Generic evidence relevance gate.

    Returns True when:
    - the question has no recognizable predicate (nothing to gate
      against — fall back to cheap grounding), OR
    - the candidate sentence carries predicate-aligned vocabulary,
      OR
    - the candidate sentence carries an actual answer-shape (a year
      for a "when" question, a capitalized name for a "who"
      question, etc.).

    Returns False only when the question carries a clear predicate
    AND none of the above hold — i.e. the entity appears, but the
    candidate sentence is about a different property of that
    entity (the Atlantis tidal-wave / Ceres-asteroid case).
    """
    q = question.lower()
    candidate_low = candidate_sentence.lower()

    # Calculation requests need evidence for a calculation method in the
    # candidate sentence itself, not just topical nouns elsewhere nearby.
    if re.search(r"\b(?:calculate|calculation|computed?|determine)\b", q):
        calculation_vocab = (
            "calculate", "calculated", "calculates", "calculation",
            "compute", "computed", "computes", "computation",
            "determine", "determined", "determines", "multiply",
            "multiplied", "divide", "divided", "formula", "equation",
            "ratio", "sum", "subtract", "add",
        )
        has_calculation_evidence = any(
            _contains_term(candidate_low, term)
            for term in calculation_vocab
        )
        if not has_calculation_evidence:
            return False

    predicate_vocab = _extract_predicate(question)

    if not predicate_vocab:
        predicate_terms = _extract_question_predicate_terms(question)
        if predicate_terms:
            return all(
                _contains_term(candidate_sentence.lower(), term)
                for term in predicate_terms
            )
        # No recognizable predicate — nothing to gate.
        return True

    # The predicate must be grounded in the candidate sentence ITSELF.
    # A predicate that merely appears somewhere else in the retrieved
    # context must NOT accept this sentence — otherwise a sentence
    # about a different property of the entity passes the gate
    # (e.g. an Atlantis evacuation scene accepted for a capital-city
    # question because "capital city" appears in a neighboring
    # sentence).
    if any(
        (_contains_term(candidate_low, vocab) if " " not in vocab
         else vocab in candidate_low)
        for vocab in predicate_vocab
    ):
        return True

    # Answer-shape heuristics: if the candidate sentence contains
    # something that looks like an actual answer to this kind of
    # question (e.g. a year for "when"), accept it.
    if q.startswith("when "):
        if re.search(
            r"\b(1\d{3}|2\d{3})\b",
            candidate_sentence,
        ):
            return True
    if q.startswith("where "):
        # Place-like capitalized tokens present.
        if re.search(
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
            candidate_sentence,
        ):
            return True

    return False


_PROPER_NOUN_PHRASE = re.compile(
    r"\b[A-Z][A-Za-z0-9'-]*"
    r"(?:\s+(?:of|the|de)?\s*[A-Z][A-Za-z0-9'-]*)*"
)


def _anchor_entity_present(sentence, anchor, question):
    """Generic compound-entity guard for subject anchoring.

    Returns False only when the anchor word occurs exclusively inside a
    longer capitalized proper-noun compound that the question does not
    itself name — e.g. the question asks about "Australia" but the
    sentence only mentions "Western Australia". The anchor then refers
    to a different (more specific) entity than the one asked about.

    Standalone occurrences of the anchor, occurrences inside compounds
    the question also names, and lowercase (non-proper) uses all count
    as present.
    """
    anchor_low = str(anchor).strip().lower()
    if not anchor_low:
        return True

    sentence_low = sentence.lower()

    total_occurrences = len(
        re.findall(
            r"\b" + re.escape(anchor_low) + r"\b",
            sentence_low,
        )
    )
    if total_occurrences == 0:
        return False

    in_matching_compound = 0
    in_compound = 0

    for match in _PROPER_NOUN_PHRASE.finditer(sentence):
        tokens = [
            token.lower()
            for token in match.group(0).split()
        ]
        core = [
            token
            for token in tokens
            if token not in {"of", "the", "de"}
        ]
        if anchor_low not in core:
            continue
        in_compound += 1
        if len(core) == 1 or " ".join(core) in question.lower():
            in_matching_compound += 1

    standalone = total_occurrences - in_compound

    return standalone > 0 or in_matching_compound > 0


def _named_fact_anchors_match(question, candidate_sentence):
    """Return whether a named operational fact is grounded, or None.

    The check applies only when the question contains an explicit
    hyphenated/alphanumeric identifier.  Such questions need both that
    identifier and a requested attribute in the same evidence sentence.
    """
    identifiers = {
        token.lower()
        for token in re.findall(
            r"\b(?:[A-Z][A-Za-z0-9]*-[A-Za-z0-9-]+|[A-Z]+\d+[A-Za-z0-9-]*)\b",
            question,
            flags=re.IGNORECASE,
        )
    }
    if not identifiers:
        return None

    ignored = {
        "what", "which", "how", "long", "is", "are", "was", "were",
        "the", "a", "an", "for", "of", "to", "in", "on", "at", "and",
        "be", "must", "should", "after", "before", "current", "do", "does",
        "did", "done", "require", "requires", "required", "need", "needs",
    }
    requested_terms = [
        token
        for token in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", question.lower())
        if token not in ignored and token not in identifiers and len(token) > 2
    ]
    if not requested_terms:
        return None

    low = candidate_sentence.lower()
    return (
        any(_contains_term(low, term) for term in requested_terms[:2])
        and any(_contains_term(low, identifier) for identifier in identifiers)
    )


# --------------------------------------------------
# SOP section extraction
# --------------------------------------------------

# Section headers recognized in the compressor SOP and similar
# procedural documents.
_SOP_SECTIONS = {
    "before starting": [
        "before starting",
        "before beginning",
        "prior to starting",
        "prior to beginning",
        "pre-start",
        "lockout",
        "tagout",
        "loto",
        "safety step",
        "electrical panel",
        "de-energize",
    ],
    "inspection": [
        "inspection",
        "inspect",
        "checking",
        "check",
    ],
    "lubrication": [
        "lubrication",
        "lubricate",
        "oil",
    ],
    "restart": [
        "restart",
        "restarting",
        "start-up",
        "startup",
    ],
}

_SOP_SECTION_HEADERS = {
    "before starting": (
        "before starting",
        "before beginning",
        "prior to starting",
        "prior to beginning",
        "pre-start",
    ),
    "inspection": (
        "inspection",
    ),
    "lubrication": (
        "lubrication",
    ),
    "restart": (
        "restart",
        "restarting",
        "start-up",
        "startup",
    ),
}

# False-premise safety keywords: if the question asserts a
# dangerous action is REQUIRED, it has a false premise.
_FALSE_PREMISE_SAFETY = [
    "bypassing lockout",
    "bypass lockout",
    "skip lockout",
    "bypassing tagout",
    "bypass tagout",
    "skip tagout",
    "without lockout",
    "without tagout",
    "no lockout",
    "no tagout",
]


_FALSE_PREMISE_ACTION_VERBS = (
    "require",
    "requires",
    "required",
    "must",
    "should",
    "need",
    "needs",
    "needed",
)


def _has_false_required_safety_action(question):
    """Detect questions asserting a required bypass of safety controls."""
    q_low = str(question or "").lower()
    if not q_low:
        return False
    if not any(verb in q_low for verb in _FALSE_PREMISE_ACTION_VERBS):
        return False
    return any(_fp in q_low for _fp in _FALSE_PREMISE_SAFETY)


def _extract_sop_section(question, chunk):
    """Extract the relevant section from an SOP document.

    Identifies which section the question targets by matching
    section keywords, then collects all bullet items under that
    section header.  Returns the concatenated section text or
    None if no section matches.
    """
    q_low = question.lower()

    # False-premise safety gate: questions that assert a dangerous
    # action is required have a false premise.
    if _has_false_required_safety_action(question):
        return None

    # Identify the target section.
    _target_section = None
    for _section, _keywords in _SOP_SECTIONS.items():
        for _kw in _keywords:
            if _contains_term(q_low, _kw):
                _target_section = _section
                break
        if _target_section:
            break

    if _target_section is None:
        return None

    # Parse the chunk into sections.  Sections may be separated
    # by newlines or by numbered markers ("1.", "2.", etc.) on
    # a single line.
    import re as _re_sop

    # Normalize: split on section-number boundaries.
    parts = _re_sop.split(
        r"(?=\b\d+\.?\s+[A-Z])", chunk,
    )

    _section_text = None
    for _part in parts:
        _part_stripped = _part.strip()
        _header_low = _part_stripped[:120].lower()
        for _kw in _SOP_SECTION_HEADERS.get(
            _target_section, (_target_section,)
        ):
            if _contains_term(_header_low, _kw):
                _section_text = _part_stripped
                break
        if _section_text:
            break

    if not _section_text:
        return None

    # Extract bullet items (lines starting with "-" or after
    # section header text).
    _items = []
    _lines = _re_sop.split(r"(?:^|\s)-\s+", _section_text)
    for _line in _lines[1:]:
        _l = _line.strip().rstrip(".")
        if _l and not _l.upper() == _l:
            _items.append(_l)

    if not _items:
        return None

    return "; ".join(_items)


def extract_factual_answer(question, context):
    """
    Extract a factual answer from context for who/when/where/what/which questions.
    Uses simple pattern matching and extractor_v1 where possible.
    Returns (answer, supported) tuple.
    """
    if not context:
        return None, False

    q = question.strip().lower()

    if _has_false_required_safety_action(question):
        return None, False

    # Try the existing extractor first
    extracted = extract_answer(question, context)
    if extracted:
        if cheap_grounding_check(extracted, context):
            # Generic predicate relevance gate: if the question
            # has a clear predicate and the extracted answer does
            # not actually address it, treat as unsupported.
            if not _predicate_answers_question(
                question, extracted, context
            ):
                extracted = None
            elif (
                not (
                    extracted.isupper()
                    and len(extracted.split()) <= 8
                )
                and _named_fact_anchors_match(question, extracted) is not False
            ):
                return extracted, True

    # Fallback: pattern-based extraction for common factual patterns
    if q.startswith("when "):
        import re as _re

        # The year must be anchored to the question. Grabbing the first
        # 19xx/20xx anywhere in the context produces false positives
        # (e.g. a 2005 survey year for "When was Albert Einstein born?",
        # whose birth year is absent from the corpus). Accept a year only
        # if its sentence also mentions the question's temporal-relation
        # word (born / founded / signed / published / ...) or, when the
        # question carries no such word, the question's subject phrase.
        relation_words = {
            "born", "birth", "founded", "found", "established", "signed",
            "released", "published", "wrote", "written", "built", "created",
            "died", "death", "began", "started", "introduced", "invented",
            "discovered", "completed", "opened", "elected", "became",
            "constructed", "ruled", "reigned", "won", "joined", "left",
            "ended", "occurred", "happened",
        }
        q_words = set(q.replace("?", " ").split())
        q_relations = q_words & relation_words
        subject = _re.sub(
            r"^(when\s+(was|were|is|are|did|does|do)\s+)",
            "",
            q,
        ).rstrip("?. ")

        sentences = _split_sentences(context)
        for s in sentences:
            match = _re.search(
                r"\b(1\d{3}|2\d{3})\b",
                s,
            )
            if not match:
                continue
            low = s.lower()
            if q_relations:
                # A relation word alone ("invented", "founded") is not
                # enough: the year must also be anchored to the question
                # SUBJECT, otherwise any sentence mentioning the verb
                # donates its year to an unrelated question.
                subject_core_words = [
                    w
                    for w in subject.split()
                    if (
                        w not in relation_words
                        and len(w) > 2
                        and w
                        not in {
                            "the", "a", "an", "and", "of", "in",
                            "on", "for", "to", "was", "were",
                            "is", "are", "did", "does", "do",
                        }
                    )
                ]
                if subject_core_words and not any(
                    _contains_term(low, w)
                    for w in subject_core_words
                ):
                    continue
                if any(
                    r in low
                    for r in q_relations
                ):
                    if not _predicate_answers_question(
                        question, s, s
                    ):
                        continue
                    return match.group(0), True
            elif subject and subject in low:
                if not _predicate_answers_question(
                    question, s, s
                ):
                    continue
                return match.group(0), True
        return None, False

    if q.startswith("who "):
        import re as _re

        # "Who" questions need the ANSWER person to be tied to the
        # question's object AND (when present) its action verb. Grabbing
        # the first capitalized word of any sentence produces noise
        # ("Responding", "Lennon" for "Who wrote the Communist Manifesto?"
        # when the corpus only has an unrelated Lennon quote). Accept a
        # name only from a sentence that references the object phrase and,
        # if the question names an action, that action verb.
        action_verbs = (
            "wrote", "write", "written", "authored", "author",
            "invented", "discovered", "founded", "created", "composed",
            "painted", "built", "designed", "developed", "established",
            "led", "defeated", "composed", "directed", "starred",
        )
        action_match = _re.match(
            r"^who\s+(" + "|".join(action_verbs) + r")\s+(.*)$",
            q,
        )
        if action_match:
            action = action_match.group(1)
            object_phrase = action_match.group(2)
        else:
            action = None
            object_phrase = _re.sub(r"^who\s+", "", q).rstrip("?. ")
        object_phrase = object_phrase.rstrip("?. ")

        # Distinctive object phrase with leading article stripped, e.g.
        # "the Communist Manifesto" -> "communist manifesto". Matching on
        # the phrase (not individual words) avoids false hits such as a
        # sentence about the "Communist Party" for a Manifesto question.
        object_key = _re.sub(
            r"^(the|a|an)\s+",
            "",
            object_phrase,
        ).strip().lower()
        object_words = set(object_key.split())
        skip_words = {
            "the", "in", "during", "after", "before", "when", "while",
            "even", "although", "once", "from", "this", "that", "however",
            "responding", "against", "around", "among",
        }
        sentences = _split_sentences(context)
        for s in sentences:
            low = s.lower()
            if object_key not in low:
                continue
            if (
                action is not None
                and not _contains_term(low, action)
            ):
                continue
            for name in _re.findall(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
                s,
            ):
                first = name.split()[0].lower()
                if first in skip_words:
                    continue
                if object_words.intersection(
                    name.lower().split()
                ):
                    continue
                if (
                    2 <= len(name.split()) <= 4
                    and len(name) > 3
                ):
                    if not _predicate_answers_question(
                        question, s, s
                    ):
                        continue
                    return name, True
        return None, False

    if q.startswith("what is ") or q.startswith("what was "):
        import re as _re

        # "What is/was X?" answers should reference X. Grabbing the first
        # sentence of the context produces false answers (a Snow White
        # passage for "What is the population of Narnia?"). Require at
        # least one distinctive word of the question's subject in the
        # candidate sentence.
        subject = _re.sub(
            r"^what\s+(is|was|are|were)\s+",
            "",
            q,
        ).rstrip("?. ")
        subject_words = {
            w
            for w in subject.split()
            if len(w) > 3
            and w
            not in {
                "what", "is", "was", "are", "were", "the", "a", "an",
                "of", "and", "for", "with",
            }
        }
        subject_anchor = subject.split()[-1] if subject.split() else ""
        sentences = _split_sentences(context)
        for s in sentences:
            if not subject_words:
                if not _predicate_answers_question(
                    question, s, s
                ):
                    continue
                if _named_fact_anchors_match(question, s) is False:
                    continue
                return s, True
            low = s.lower()
            if (
                any(
                    _contains_term(low, w)
                    for w in subject_words
                )
                and _anchor_entity_present(
                    s,
                    subject_anchor,
                    question,
                )
            ):
                if not _predicate_answers_question(
                    question, s, s
                ):
                    continue
                if _named_fact_anchors_match(question, s) is False:
                    continue
                return s, True
        # No sentence survived the compound-entity/subject anchor checks.
        # Fall through to the generic operational branch below, which can
        # still ground identifier-less attribute questions on windowed
        # term evidence instead of hard-abstaining here.

    if q.startswith("where "):
        locations = ["italy", "england", "france", "london", "rome", "paris"]
        for loc in locations:
            if loc in context.lower():
                if not _predicate_answers_question(
                    question, loc, context
                ):
                    continue
                return loc, True

    # General operational and procedural facts often use forms such as
    # "What purge pressure...", "Which coolant...", "What must be done
    # before starting X?", or "How should Y be verified?" rather than
    # "What is...". Accept a complete evidence sentence only when it is
    # grounded in the question: either an explicit identifier plus
    # requested attribute (legacy path), or — for identifier-less
    # questions — at least TWO distinct question terms matching the
    # sentence's topical window, with the returned sentence itself
    # carrying at least one matched term. The two-tier anchor prevents
    # an unrelated sentence about a phone number or price from being
    # treated as support.
    if q.startswith(("what ", "which ", "how ")):
        sentences = _split_sentences(context)
        identifiers = {
            token.lower()
            for token in re.findall(
                r"\b(?:[A-Z][A-Za-z0-9]*-[A-Za-z0-9-]+|[A-Z]+\d+[A-Za-z0-9-]*)\b",
                question,
                flags=re.IGNORECASE,
            )
        }
        ignored = {
            "what", "which", "how", "long", "is", "are", "was", "were",
            "the", "a", "an", "for", "of", "to", "in", "on", "at", "and",
            "be", "must", "should", "after", "before", "current", "do",
            "does", "did", "require", "requires", "required", "need",
            "needs",
        }
        terms = [
            token
            for token in re.findall(
                r"[a-z0-9]+(?:-[a-z0-9]+)?", question.lower()
            )
            if token not in ignored
            and token not in identifiers
            and len(token) > 2
        ]
        candidates = []
        for index, sentence in enumerate(sentences):
            if sentence.isupper() and len(sentence.split()) <= 8:
                continue
            evidence_window = " ".join(
                sentences[max(0, index - 3): index + 4]
            )
            anchors = _named_fact_anchors_match(question, evidence_window)
            if anchors is False:
                continue
            low = sentence.lower()
            matched_terms = sum(
                1 for term in terms if _contains_term(low, term)
            )
            score = 3 * matched_terms
            if any(
                _contains_term(low, identifier)
                for identifier in identifiers
            ):
                score += 1
            if identifiers:
                # Legacy identifier-anchored behavior.
                if anchors is None:
                    continue
                candidates.append((score, -index, sentence))
            else:
                # Identifier-less procedural/attribute questions: the
                # WINDOW must confirm the topic (>= 2 distinct matched
                # terms) and the SENTENCE itself must carry >= 1 term,
                # otherwise an incidental word would donate support.
                window_matched = sum(
                    1
                    for term in terms
                    if _contains_term(evidence_window.lower(), term)
                )
                if window_matched < 2 or matched_terms < 1:
                    continue
                # Entity-anchored counting: a question term that occurs
                # ONLY inside a longer proper-noun compound the question
                # does not name ("Guinea" via "Papua New Guinea") does
                # not count as a match.
                valid_matches = sum(
                    1
                    for term in terms
                    if _contains_term(low, term)
                    and _anchor_entity_present(sentence, term, question)
                )
                if valid_matches < 1:
                    continue
                # Compound-entity guard: for entity-asking question forms
                # ("what is/was X", "which X"), the question's primary
                # entity (last content word) must be properly anchored
                # in the sentence — not absent or buried inside a larger
                # compound the question doesn't name (e.g. "moon"
                # missing entirely, or "Australia" inside "Western
                # Australia").  Procedural forms ("how") skip this
                # guard because the last content word is typically a
                # verb ("checked", "verified") that legitimately may
                # not appear in the evidence.
                entity_anchor = terms[-1] if terms else ""
                if entity_anchor and q.startswith(
                    ("what is ", "what was ", "which ")
                ):
                    if not _anchor_entity_present(
                        sentence, entity_anchor, question
                    ):
                        continue
                if not _predicate_answers_question(
                    question, sentence, evidence_window
                ):
                    continue
                candidates.append((score, -index, sentence))
        eligible = [
            candidate
            for candidate in candidates
            if identifiers or candidate[0] >= 6
        ]
        if eligible:
            _, _, sentence = max(eligible)
            return sentence, True

    return None, False

from reasoning_confidence_v1 import (
    reasoning_support_confidence,
)

from retriever_v2 import (
    load_chunks as load_chunks_v2,
    build_index as build_index_v2,
    retrieve as retrieve_v2,
)

from retriever_v4 import (
    aggregate_results,
    build_adaptive_query_plan,
)

from retriever_hybrid import (
    retrieve as retrieve_hybrid,
)

from query_planner_v1 import (
    build_queries,
)

from comparison_planner_v1 import (
    build_comparison_queries,
)

from comparison_retrieval_v1 import (
    retrieve_comparison,
)

from comparison_confidence_v1 import (
    score_comparison,
)

from comparison_synthesizer_v1 import (
    synthesize_comparison,
)

from causal_synthesizer_v1 import (
    synthesize_causal_answer,
)

from change_synthesizer_v1 import (
    synthesize_change_answer,
)

from effect_synthesizer_v1 import (
    synthesize_effect_answer,
)

from entity_list_synthesizer_v1 import (
    synthesize_entity_list_answer,
)

from structure_synthesizer_v1 import (
    synthesize_structure_answer,
)

from summary_synthesizer_v1 import (
    synthesize_summary_answer,
)


# All project paths and tunables are imported from the root config
# module at the top of this file. See
# ``from config import`` near the imports above.


# --------------------------------------------------
# General text helpers
# --------------------------------------------------

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "at",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "they",
    "their",
    "them",
    "he",
    "she",
    "his",
    "her",
    "what",
    "when",
    "where",
    "why",
    "how",
    "did",
    "does",
    "do",
    "has",
    "have",
    "had",
}


def normalize_text(text):
    text = text.lower()

    text = re.sub(
        r"[^a-z0-9']+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def tokenize(text):
    return re.findall(
        r"[a-z0-9']+",
        text.lower(),
    )


def useful_terms(text):
    return [
        word
        for word in tokenize(
            text
        )
        if (
            word not in STOPWORDS
            and len(word) >= 3
        )
    ]


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


def clean_relation_entity(text):
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    text = text.rstrip(
        "?.!"
    )

    text = re.sub(
        r"^(?:the process by which)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


# --------------------------------------------------
# Generation
# --------------------------------------------------

def generate(
    model,
    tokenizer,
    context,
    question,
    device,
):
    prompt = (
        "<RESULT>\n"
        f"{context}\n\n"
        "<ANSWER>\n"
        f"Question: {question}\n"
        "Answer:"
    )

    encoded = tokenizer.encode(
        prompt
    )

    token_ids = encoded.ids

    bos_id = tokenizer.token_to_id(
        "<BOS>"
    )

    eos_id = tokenizer.token_to_id(
        "<EOS>"
    )

    pad_id = tokenizer.token_to_id(
        "<PAD>"
    )

    special_ids = {
        token_id
        for token_id in [
            bos_id,
            eos_id,
            pad_id,
        ]
        if token_id is not None
    }

    token_ids = [
        token_id
        for token_id in token_ids
        if token_id not in special_ids
    ]

    token_ids = token_ids[
        -(MAX_INPUT_TOKENS - 1):
    ]

    if bos_id is not None:
        token_ids = (
            [bos_id]
            + token_ids
        )

    if not token_ids:
        return ""

    x = torch.tensor(
        [token_ids],
        dtype=torch.long,
        device=device,
    )

    generated = []

    model.eval()

    with torch.no_grad():

        for _ in range(
            MAX_NEW_TOKENS
        ):
            model_input = x[
                :,
                -MAX_INPUT_TOKENS:
            ]

            logits, _ = model(
                model_input
            )

            next_logits = logits[
                0,
                -1,
                :
            ]

            next_token = torch.argmax(
                next_logits,
                dim=-1,
            ).item()

            if (
                eos_id is not None
                and next_token == eos_id
            ):
                break

            generated.append(
                next_token
            )

            next_tensor = torch.tensor(
                [[next_token]],
                dtype=torch.long,
                device=device,
            )

            x = torch.cat(
                [
                    x,
                    next_tensor,
                ],
                dim=1,
            )

    if not generated:
        return ""

    answer = tokenizer.decode(
        generated,
        skip_special_tokens=True,
    )

    return answer.strip()


def stream_generate(
    model,
    tokenizer,
    context,
    question,
    device,
    max_new_tokens: int | None = None,
    chunk_size: int = 4,
):
    """Streaming variant of :func:`generate`.

    Yields the answer one chunk at a time (default 4 tokens per chunk)
    so callers — typically the Gradio UI — can render partial output
    without waiting for the full answer to finish.

    The generation loop is identical to ``generate()``; the only
    difference is that each decoded chunk is yielded as soon as it is
    produced. ``chunk_size`` controls how many tokens to accumulate
    before yielding; a small chunk size gives finer-grained updates
    at the cost of more Python overhead per step.

    Stops early on EOS, on empty input, or after ``max_new_tokens``
    tokens (defaults to the module-level ``MAX_NEW_TOKENS``).
    """
    cap = max_new_tokens if max_new_tokens is not None else MAX_NEW_TOKENS

    prompt = (
        "<RESULT>\n"
        f"{context}\n\n"
        "<ANSWER>\n"
        f"Question: {question}\n"
        "Answer:"
    )

    encoded = tokenizer.encode(prompt)
    token_ids = encoded.ids

    bos_id = tokenizer.token_to_id("<BOS>")
    eos_id = tokenizer.token_to_id("<EOS>")
    pad_id = tokenizer.token_to_id("<PAD>")

    special_ids = {
        token_id
        for token_id in [bos_id, eos_id, pad_id]
        if token_id is not None
    }

    token_ids = [
        token_id
        for token_id in token_ids
        if token_id not in special_ids
    ]
    token_ids = token_ids[-(MAX_INPUT_TOKENS - 1):]

    if bos_id is not None:
        token_ids = [bos_id] + token_ids

    if not token_ids:
        return

    x = torch.tensor([token_ids], dtype=torch.long, device=device)

    buffer: list[int] = []

    model.eval()

    with torch.no_grad():
        for _ in range(cap):
            model_input = x[:, -MAX_INPUT_TOKENS:]
            logits, _ = model(model_input)
            next_logits = logits[0, -1, :]
            next_token = torch.argmax(next_logits, dim=-1).item()

            if eos_id is not None and next_token == eos_id:
                break

            buffer.append(next_token)

            if len(buffer) >= chunk_size:
                yield tokenizer.decode(
                    buffer, skip_special_tokens=True
                )
                buffer = []

            next_tensor = torch.tensor(
                [[next_token]], dtype=torch.long, device=device,
            )
            x = torch.cat([x, next_tensor], dim=1)

    if buffer:
        yield tokenizer.decode(buffer, skip_special_tokens=True)


# --------------------------------------------------
# Extracted-answer formatting
# --------------------------------------------------

def format_extracted_answer(
    question,
    answer,
):
    q = question.lower().strip()

    a = (
        answer
        .strip()
        .replace(
            " - ",
            "-",
        )
    )

    a = re.sub(
        r"\s+",
        " ",
        a,
    )

    # ------------------------------------------
    # Birth
    # ------------------------------------------

    match = re.match(
        r"when was (.+?) born\??$",
        question,
        flags=re.IGNORECASE,
    )

    if match:
        subject = (
            match.group(1)
            .strip()
        )

        if re.fullmatch(
            r"\d{4}",
            a,
        ):
            return (
                f"{subject} was born "
                f"in {a}."
            )

        return (
            f"{subject} was born on "
            f"{a.rstrip('.')}."
        )

    # ------------------------------------------
    # Founded
    # ------------------------------------------

    match = re.match(
        r"when was (.+?) founded\??$",
        question,
        flags=re.IGNORECASE,
    )

    if match:
        subject = (
            match.group(1)
            .strip()
        )

        return (
            f"{subject} was founded in "
            f"{a.rstrip('.')}."
        )

    # ------------------------------------------
    # Established
    # ------------------------------------------

    match = re.match(
        r"when was (.+?) established\??$",
        question,
        flags=re.IGNORECASE,
    )

    if match:
        subject = (
            match.group(1)
            .strip()
        )

        return (
            f"{subject} was established in "
            f"{a.rstrip('.')}."
        )

    # ------------------------------------------
    # Released
    # ------------------------------------------

    match = re.match(
        r"when was (.+?) released\??$",
        question,
        flags=re.IGNORECASE,
    )

    if match:
        subject = (
            match.group(1)
            .strip()
        )

        return (
            f"{subject} was released in "
            f"{a.rstrip('.')}."
        )

    # ------------------------------------------
    # Published
    # ------------------------------------------

    match = re.match(
        r"when was (.+?) published\??$",
        question,
        flags=re.IGNORECASE,
    )

    if match:
        subject = (
            match.group(1)
            .strip()
        )

        return (
            f"{subject} was published in "
            f"{a.rstrip('.')}."
        )

    # ------------------------------------------
    # Named after
    # ------------------------------------------

    match = re.match(
        r"(?:who or what|what|who) "
        r"was (.+?) named after\??$",
        question,
        flags=re.IGNORECASE,
    )

    if match:
        subject = (
            match.group(1)
            .strip()
        )

        return (
            f"{subject} was named after "
            f"{a.rstrip('.')}."
        )

    # ------------------------------------------
    # Why / causal
    # ------------------------------------------

    if q.startswith(
        "why "
    ):

        if a.lower().startswith(
            (
                "because ",
                "it was due to ",
                "it happened as a result of ",
            )
        ):
            return (
                a
                if a.endswith(".")
                else a + "."
            )

        match = re.match(
            r"why did (.+?) fall\??$",
            question,
            flags=re.IGNORECASE,
        )

        if match:
            subject = (
                match.group(1)
                .strip()
            )

            cause = a.rstrip(
                "."
            )

            if cause.lower().startswith(
                "first "
            ):
                cause = cause[6:]

            return (
                f"{subject} fell after "
                f"{cause}."
            )

    # ------------------------------------------
    # What caused X?
    # ------------------------------------------

    match = re.match(
        r"what caused (.+?)\??$",
        question,
        flags=re.IGNORECASE,
    )

    if match:
        event = (
            match.group(1)
            .strip()
        )

        return (
            f"{event} was caused by "
            f"{a.rstrip('.')}."
        )

    return (
        a
        if a.endswith(".")
        else a + "."
    )


# --------------------------------------------------
# Standard helpers
# --------------------------------------------------

def unsupported_answer():
    return (
        "I couldn't find enough reliable "
        "evidence in the current knowledge base."
    )


def build_system_result(
    result,
    answer=None,
):
    if answer is None:
        answer = unsupported_answer()

    result[
        "answer_type"
    ] = "system"

    result[
        "answer"
    ] = answer

    result[
        "supported"
    ] = False

    return result


def comparison_unsupported_answer(
    comparison_result,
    confidence,
):
    left_name = (
        comparison_result[
            "plan"
        ][
            "left_entity"
        ]
    )

    right_name = (
        comparison_result[
            "plan"
        ][
            "right_entity"
        ]
    )

    left_ok = (
        confidence[
            "left"
        ][
            "sufficient"
        ]
    )

    right_ok = (
        confidence[
            "right"
        ][
            "sufficient"
        ]
    )

    if (
        left_ok
        and not right_ok
    ):
        return (
            f"I found enough evidence about "
            f"{left_name}, but not enough "
            f"reliable evidence about "
            f"{right_name} in the current "
            f"knowledge base."
        )

    if (
        right_ok
        and not left_ok
    ):
        return (
            f"I found enough evidence about "
            f"{right_name}, but not enough "
            f"reliable evidence about "
            f"{left_name} in the current "
            f"knowledge base."
        )

    return (
        "I couldn't find enough reliable "
        "evidence for both sides of this "
        "comparison."
    )


# ==================================================
# ASSERTED RELATION / PREMISE VALIDATION
# ==================================================

RELATION_MARKERS = {
    "cause": [
        "cause",
        "caused",
        "causes",
        "because",
        "due to",
        "resulted in",
        "led to",
        "lead to",
    ],

    "create": [
        "create",
        "created",
        "creates",
        "produce",
        "produced",
        "produces",
        "generate",
        "generated",
        "generates",
        "form",
        "formed",
        "forms",
        "establish",
        "established",
        "establishes",
    ],

    "limit": [
        "limit",
        "limited",
        "limits",
        "restrict",
        "restricted",
        "restricts",
        "constrain",
        "constrained",
        "constrains",
    ],

    "function_as": [
        "functioned as",
        "functions as",
        "function as",
        "acted as",
        "acts as",
        "served as",
        "serves as",
    ],

    "structure_as": [
        "structured as",
        "structure as",
        "organized as",
        "organised as",
        "modeled as",
        "modelled as",
        "structure of",
    ],

    # --------------------------------------------------
    # V3 cross-domain asserted actions
    # --------------------------------------------------

    "govern": [
        "govern",
        "governed",
        "governs",
        "governing",
    ],

    "organize": [
        "organize",
        "organized",
        "organizes",
        "organizing",
        "organise",
        "organised",
        "organises",
        "organising",
        "establish",
        "established",
        "establishes",
    ],

    "operate_as": [
        "operate as",
        "operated as",
        "operates as",
        "operating as",
    ],

    "replicate": [
        "replicate",
        "replicated",
        "replicates",
        "replicating",
        "replication",
    ],

    "separate": [
        "separate",
        "separated",
        "separates",
        "separating",
    ],

    "overthrow": [
        "overthrow",
        "overthrew",
        "overthrows",
        "overthrown",
        "overthrowing",
    ],

    "sign": [
        "sign",
        "signed",
        "signs",
        "signing",
    ],

    "invent": [
        "invent",
        "invented",
        "invents",
        "inventing",
    ],

    "perform": [
        "perform",
        "performed",
        "performs",
        "performing",
    ],

    "split": [
        "split",
        "splits",
        "splitting",
        "divide",
        "divided",
        "divides",
        "dividing",
    ],

    "describe_as": [
        " as ",
        "is a",
        "was a",
    ],
}


def extract_asserted_relation(
    question,
):
    """
    Detect a question that ASSERTS a relationship between
    two concepts.

    This is intentionally stricter than ordinary intent
    detection. The goal is to catch questions such as:

        "How did DNA create the Roman Empire?"
        "Explain how photosynthesis organized the Roman army."
        "Describe DNA as a political institution of the Roman Republic."

    Ordinary single-subject questions such as:

        "Why did the Roman Empire decline?"
        "How was the Roman army organized?"
        "How does photosynthesis work?"

    do not match and therefore do not require this extra gate.
    """

    q = re.sub(
        r"\s+",
        " ",
        question.strip(),
    )

    patterns = [
        # ------------------------------------------
        # Explicit cause
        # ------------------------------------------

        (
            "cause",
            r"^why did (.+?) cause "
            r"(.+?)[?.!]*$",
        ),

        (
            "cause",
            r"^how did (.+?) cause "
            r"(.+?)[?.!]*$",
        ),

        (
            "cause",
            r"^(?:explain|describe) how (.+?) caused "
            r"(.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # Creation / production / generation
        # ------------------------------------------

        (
            "create",
            r"^how did (.+?) (?:create|produce|generate|form|establish|"
            r"establishes|established) "
            r"(.+?)[?.!]*$",
        ),

        (
            "create",
            r"^(?:explain|describe) how (.+?) "
            r"(?:create|creates|created|produce|produces|produced|"
            r"generate|generates|generated|form|forms|formed|"
            r"establish|establishes|established) "
            r"(.+?)[?.!]*$",
        ),

        (
            "create",
            r"^(?:explain|describe) the process by which "
            r"(.+?) (?:created|produced|generated|formed) "
            r"(.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # Limitation / restriction
        # ------------------------------------------

        (
            "limit",
            r"^(?:describe|explain) how (.+?) "
            r"(?:limited|restricted|constrained) "
            r"(.+?)[?.!]*$",
        ),

        (
            "limit",
            r"^how did (.+?) "
            r"(?:limit|restrict|constrain) "
            r"(.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # X functioned / acted / served as Y
        # ------------------------------------------

        (
            "function_as",
            r"^(?:explain|describe) how (.+?) "
            r"(?:functioned|acted|served) as "
            r"(.+?)[?.!]*$",
        ),

        (
            "function_as",
            r"^how did (.+?) "
            r"(?:function|act|serve) as "
            r"(.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # X operated as Y
        # ------------------------------------------

        (
            "operate_as",
            r"^(?:explain|describe) how (.+?) "
            r"(?:operated|operates|operate) as "
            r"(.+?)[?.!]*$",
        ),

        (
            "operate_as",
            r"^how did (.+?) operate as "
            r"(.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # Structure / identity-as assertions
        # ------------------------------------------

        (
            "structure_as",
            r"^(?:describe|explain) the structure of "
            r"(.+?) as (.+?)[?.!]*$",
        ),

        (
            "structure_as",
            r"^(?:describe|explain) how (.+?) was "
            r"(?:structured|organized|organised) as "
            r"(.+?)[?.!]*$",
        ),

        # Catches false-premise structure questions such as
        # "How did the Roman Empire establish the structure of DNA?"
        (
            "structure_as",
            r"^how did (.+?) establish the structure of "
            r"(.+?)[?.!]*$",
        ),

        (
            "structure_as",
            r"^how did (.+?) (?:create|build|form) the structure of "
            r"(.+?)[?.!]*$",
        ),

        # Catches adversarial identity/metaphor claims such as
        # "Describe the Roman Empire as a stage of mitosis."
        # and "Describe DNA as a political institution ...".
        (
            "describe_as",
            r"^describe (.+?) as (.+?)[?.!]*$",
        ),

        (
            "describe_as",
            r"^explain (.+?) as (.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # Governance / organization
        # ------------------------------------------

        (
            "govern",
            r"^(?:describe|explain) how (.+?) "
            r"(?:governed|governs|govern) "
            r"(.+?)[?.!]*$",
        ),

        (
            "govern",
            r"^how did (.+?) govern "
            r"(.+?)[?.!]*$",
        ),

        (
            "organize",
            r"^(?:describe|explain) how (.+?) "
            r"(?:organized|organised|organizes|organises|organize|organise|"
            r"establish|establishes|established) "
            r"(.+?)[?.!]*$",
        ),

        (
            "organize",
            r"^how did (.+?) "
            r"(?:organize|organise|establish|established) "
            r"(.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # Replication / separation
        # ------------------------------------------

        (
            "replicate",
            r"^(?:describe|explain) how (.+?) "
            r"(?:replicated|replicates|replicate) "
            r"(.+?)[?.!]*$",
        ),

        (
            "replicate",
            r"^how did (.+?) replicate "
            r"(.+?)[?.!]*$",
        ),

        (
            "separate",
            r"^(?:describe|explain) how (.+?) "
            r"(?:separated|separates|separate) "
            r"(.+?)[?.!]*$",
        ),

        (
            "separate",
            r"^how did (.+?) separate "
            r"(.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # Overthrow / sign / invent / perform / split
        # ------------------------------------------

        (
            "overthrow",
            r"^why did (.+?) overthrow "
            r"(.+?)[?.!]*$",
        ),

        (
            "overthrow",
            r"^how did (.+?) overthrow "
            r"(.+?)[?.!]*$",
        ),

        (
            "overthrow",
            r"^what caused (.+?) to overthrow "
            r"(.+?)[?.!]*$",
        ),

        (
            "sign",
            r"^(?:why|how) did (.+?) sign "
            r"(.+?)[?.!]*$",
        ),

        (
            "invent",
            r"^(?:explain|describe) (?:why|how) (.+?) "
            r"(?:invented|invents|invent) "
            r"(.+?)[?.!]*$",
        ),

        (
            "perform",
            r"^(?:explain|describe) (?:why|how) (.+?) "
            r"(?:performed|performs|perform) "
            r"(.+?)[?.!]*$",
        ),

        (
            "split",
            r"^(?:explain|describe) how (.+?) "
            r"(?:split|splits) "
            r"(.+?)[?.!]*$",
        ),

        (
            "split",
            r"^how did (.+?) split "
            r"(.+?)[?.!]*$",
        ),

        (
            "split",
            r"^why did (.+?) divide "
            r"(.+?)[?.!]*$",
        ),

        (
            "split",
            r"^how did (.+?) divide "
            r"(.+?)[?.!]*$",
        ),

        (
            "split",
            r"^(?:explain|describe) how (.+?) "
            r"(?:divide|divides|divided) "
            r"(.+?)[?.!]*$",
        ),

        # ------------------------------------------
        # Additional why-form asserted relations
        # ------------------------------------------

        (
            "create",
            r"^why did (.+?) "
            r"(?:create|produce|generate|form|establish|established) "
            r"(.+?)[?.!]*$",
        ),

        (
            "invent",
            r"^why did (.+?) "
            r"(?:invent|discover|develop) "
            r"(.+?)[?.!]*$",
        ),

        (
            "limit",
            r"^why did (.+?) "
            r"(?:limit|restrict|constrain) "
            r"(.+?)[?.!]*$",
        ),

        (
            "organize",
            r"^why did (.+?) "
            r"(?:organize|organise) "
            r"(.+?)[?.!]*$",
        ),

        (
            "split",
            r"^why did (.+?) split "
            r"(.+?)[?.!]*$",
        ),

        (
            "separate",
            r"^why did (.+?) separate "
            r"(.+?)[?.!]*$",
        ),

        (
            "replicate",
            r"^why did (.+?) replicate "
            r"(.+?)[?.!]*$",
        ),

        (
            "cause",
            r"^why did (.+?) "
            r"(?:lead|cause) "
            r"(.+?)[?.!]*$",
        ),
    ]

    for relation, pattern in patterns:
        match = re.fullmatch(
            pattern,
            q,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        source = clean_relation_entity(
            match.group(1)
        )

        target = clean_relation_entity(
            match.group(2)
        )

        if (
            not source
            or not target
        ):
            continue

        return {
            "relation":
                relation,

            "source":
                source,

            "target":
                target,
        }

    return None


def term_coverage(
    required_terms,
    sentence_terms,
):
    required_terms = set(
        required_terms
    )

    sentence_terms = set(
        sentence_terms
    )

    if not required_terms:
        return 0.0

    return (
        len(
            required_terms
            & sentence_terms
        )
        / len(
            required_terms
        )
    )


def relation_sentence_support(
    sentence,
    relation_info,
):
    sentence_normalized = normalize_text(
        sentence
    )

    sentence_terms = useful_terms(
        sentence
    )

    source_terms = useful_terms(
        relation_info[
            "source"
        ]
    )

    target_terms = useful_terms(
        relation_info[
            "target"
        ]
    )

    if (
        not source_terms
        or not target_terms
    ):
        return False

    source_coverage = term_coverage(
        source_terms,
        sentence_terms,
    )

    target_coverage = term_coverage(
        target_terms,
        sentence_terms,
    )

    # Require meaningful evidence for BOTH sides
    # of the asserted relation in the SAME sentence.
    # This prevents evidence about only one side from
    # being mistaken for evidence of the relationship.
    if source_coverage < 0.60:
        return False

    if target_coverage < 0.60:
        return False

    relation = relation_info[
        "relation"
    ]

    markers = RELATION_MARKERS.get(
        relation,
        [],
    )

    # "describe_as" uses the word "as" as a relational
    # bridge. normalize_text removes punctuation but keeps
    # spaces, so use token-aware checks rather than the
    # literal " as " marker stored above.
    if relation == "describe_as":
        words = sentence_normalized.split()

        if "as" not in words:
            return False

        return True

    marker_found = any(
        marker in sentence_normalized
        for marker in markers
    )

    return marker_found


def validate_asserted_relation(
    question,
    context,
):
    relation_info = (
        extract_asserted_relation(
            question
        )
    )

    # No asserted cross-concept relation:
    # no extra premise gate required.
    if relation_info is None:
        return {
            "required":
                False,

            "supported":
                True,

            "relation":
                None,

            "source":
                None,

            "target":
                None,

            "supporting_sentence":
                None,
        }

    for sentence in split_sentences(
        context
    ):
        if relation_sentence_support(
            sentence,
            relation_info,
        ):
            return {
                "required":
                    True,

                "supported":
                    True,

                "relation":
                    relation_info[
                        "relation"
                    ],

                "source":
                    relation_info[
                        "source"
                    ],

                "target":
                    relation_info[
                        "target"
                    ],

                "supporting_sentence":
                    sentence,
            }

    return {
        "required":
            True,

        "supported":
            False,

        "relation":
            relation_info[
                "relation"
            ],

        "source":
            relation_info[
                "source"
            ],

        "target":
            relation_info[
                "target"
            ],

        "supporting_sentence":
            None,
    }


# ==================================================
# INTENT-CANONICAL QUESTION HELPERS
# ==================================================

def canonical_question_for_intent(
    question,
    plan,
):
    """
    Return the canonical question produced by the
    query planner whenever possible.

    rag_chat_v2 should not independently reconstruct
    paraphrase normalization when query_planner_v1
    has already done that work.
    """

    if not plan:
        return question

    canonical_question = (
        plan.get(
            "canonical_question"
        )
        or ""
    ).strip()

    intent = (
        plan.get(
            "intent",
            "general",
        )
        or "general"
    )

    subject = (
        plan.get(
            "subject",
            "",
        )
        or ""
    ).strip()

    if (
        not subject
        or intent == "general"
    ):
        return question

    # Guard: when extract_subject falls through with no real
    # match, it returns clean_subject(q) — the entire question.
    # Building a synthetic canonical from that creates garbage
    # (e.g. "Why did Why did the Roman Empire fall in 2020
    # decline?") which parse_causal_question happily matches.
    # Detect this and fall through to the original question.
    _q_stripped = (
        question.strip().rstrip(".?!")
        .lower()
    )
    _s_stripped = (
        subject.strip().rstrip(".?!")
        .lower()
    )
    if _s_stripped == _q_stripped or (
        _q_stripped.startswith(_s_stripped)
        and len(_s_stripped) > len(_q_stripped) * 0.8
    ):
        return question

    # Guard: subjects that still contain infinitive phrases
    # ("to be discovered", "to happen") or agent phrases
    # ("signed by Napoleon") indicate extract_subject fell
    # through with the question frame intact.  A real entity
    # name like "the Roman Empire" never contains " to " or
    # " by " in this position.
    if (
        " to " in _s_stripped
        or " by " in _s_stripped
    ):
        return question

    # Guard: subjects starting with question words indicate
    # extract_subject fell through (e.g. "why the Roman
    # Republic had a President" from "Explain why ...").
    if _s_stripped.split()[0] in (
        "why", "what", "how", "when",
        "where", "who", "which",
    ):
        return question

    # Use the plan's canonical if it looks valid; otherwise
    # construct from the (now-guarded) subject.
    if canonical_question:
        _cq_low = canonical_question.lower()
        _dup = _cq_low.count("why did ") > 1 or (
            _cq_low.count("what caused ") > 1
        ) or (
            _cq_low.count("how did ") > 1
        )
        if not _dup:
            return canonical_question

    if intent == "cause":
        return (
            f"Why did {subject} decline?"
        )

    if intent == "change":
        return (
            f"How did {subject} "
            f"change over time?"
        )

    if intent == "effect":
        return (
            f"What were the effects of "
            f"{subject}?"
        )

    if intent == "structure":
        return (
            f"What is the structure of "
            f"{subject}?"
        )

    if intent == "process":
        return (
            f"Explain how {subject} works."
        )

    if intent == "features":
        return (
            f"What were the main features "
            f"of {subject}?"
        )

    if intent == "significance":
        return (
            f"What is the significance of "
            f"{subject}?"
        )

    if intent == "entity_list":
        return (
            f"Who were the key figures of "
            f"{subject}?"
        )

    return question


# --------------------------------------------------
# Retrieval wrappers
# --------------------------------------------------

def retrieve_for_extractor(
    question,
    chunks,
    retrieval_index,
    document_frequency,
):
    results = retrieve_v2(
        question,
        chunks,
        retrieval_index,
        document_frequency,
    )

    if not results:
        return None

    return results[0]


def retrieve_for_reasoning(
    question,
    chunks,
    retrieval_index,
    document_frequency,
    *,
    document_ids=None,
):
    """Authoritative grounded retrieval for the reasoning route.

    Delegates candidate ranking to the validated full-question-first
    hybrid retriever (``retriever_hybrid``), then reuses the V4
    intent-aware evidence aggregation so downstream synthesizers and the
    unified support gate keep working unchanged. There is exactly one
    production retrieval architecture: Stage 5 evaluation, API and WebUI
    all flow through this hybrid path.
    """
    plan = build_queries(question)

    # Specialized synthesizers depend on intent-marker evidence. Supply
    # the existing generic planner queries as bounded secondary candidates;
    # the hybrid fusion still protects strong full-question candidates, so
    # ranking remains authoritative and deterministic.
    intent = str(plan.get("intent") or "general")
    secondary_queries = []
    if intent not in {"general", "comparison"}:
        adaptive_plan = build_adaptive_query_plan(plan)
        secondary_queries = [
            query for query in adaptive_plan.get("primary", []) if query
        ][:3]

    # One authoritative hybrid call per pass. The candidate POOL for
    # sentence-level evidence aggregation is deliberately deeper than the
    # displayed top-10 so marker-bearing chunks remain reachable; the fused
    # ordering itself (and therefore sources/Stage 5 parity) is unchanged.
    ranked = retrieve_hybrid(
        question,
        chunks,
        retrieval_index,
        document_frequency,
        final_top_k=40,
        secondary_queries=secondary_queries,
        document_ids=document_ids,
    )

    if not ranked:
        return None

    context = aggregate_results(question, plan, ranked)

    return {
        "plan": plan,
        "results": ranked,
        "best": ranked[0],
        "context": context,
        "retriever": "hybrid",
    }


# --------------------------------------------------
# Pipeline initialization
# --------------------------------------------------

def _select_execution_device(
):
    """Select CUDA only when it is genuinely usable, else fall back to CPU.

    ``torch.cuda.is_available()`` can report True while no device is actually
    usable (observed in the field: ``is_available() == True`` while
    ``device_count() == 0``), which previously made pipeline initialization
    fail while loading the checkpoint onto "cuda". Require a real,
    inspectable device with nonzero memory before choosing CUDA.
    """
    try:
        if (
            torch.cuda.is_available()
            and torch.cuda.device_count() > 0
        ):
            properties = torch.cuda.get_device_properties(0)
            if properties is not None and getattr(
                properties,
                "total_memory",
                0,
            ) > 0:
                return "cuda"
    except Exception:
        logger.warning(
            "CUDA device inspection failed; falling back to CPU",
            exc_info=True,
        )
    return "cpu"


def initialize_pipeline(
    verbose=True,
):
    logger.info(
        "Initializing rag_chat pipeline"
    )

    device = _select_execution_device()

    logger.info(
        "Pipeline device selected: %s",
        device,
    )

    if verbose:
        print(
            "Device:",
            device,
        )

    try:
        tokenizer = Tokenizer.from_file(
            str(
                TOKENIZER_FILE
            )
        )
    except Exception as exc:
        logger.error(
            "Failed to load tokenizer from %s",
            TOKENIZER_FILE,
            exc_info=True,
        )
        raise

    model = SmallLMV2().to(
        device
    )

    try:
        state_dict = torch.load(
            MODEL_FILE,
            map_location=device,
            weights_only=True,
        )
    except Exception as exc:
        logger.error(
            "Failed to load model checkpoint from %s",
            MODEL_FILE,
            exc_info=True,
        )
        raise

    model.load_state_dict(
        state_dict
    )

    model.eval()

    logger.info(
        "Reasoning V1 model loaded from %s",
        MODEL_FILE,
    )

    if verbose:
        print(
            "Reasoning V1 model loaded."
        )

    try:
        chunks = load_chunks_v2(
            KNOWLEDGE_FILES
        )
    except Exception as exc:
        logger.error(
            "Failed to load knowledge chunks",
            exc_info=True,
        )
        raise

    logger.info(
        "Loaded %d knowledge chunks",
        len(chunks),
    )

    try:
        (
            retrieval_index,
            document_frequency,
        ) = build_index_v2(
            chunks
        )
    except Exception as exc:
        logger.error(
            "Failed to build retrieval index",
            exc_info=True,
        )
        raise

    logger.info(
        "Retrieval index built (chunks=%d)",
        len(chunks),
    )

    pipeline = {
        "device": device,
        "tokenizer": tokenizer,
        "model": model,
        "chunks": chunks,
        "retrieval_index": retrieval_index,
        "document_frequency": document_frequency,
        "uploaded_docs": [],
        "runtime_persistence": True,
        "runtime_upload_dir": RUNTIME_UPLOAD_DIR,
    }
    from webui.document_processor import attach_documents, restore_persisted_documents
    restored = restore_persisted_documents(pipeline)
    if restored:
        attach_documents(pipeline, restored, persist=False)
        logger.info("Restored %d runtime documents", len(restored))

    logger.info(
        "Pipeline initialization complete"
    )

    return pipeline


# ==================================================
# RUNTIME INTENT PLANNING
# ==================================================

PLANNED_REASONING_INTENTS = {
    "cause",
    "change",
    "effect",
    "structure",
    "process",
    "features",
    "significance",
    "entity_list",
    "comparison",
}


def runtime_plan(
    question,
):
    """
    Build the semantic plan BEFORE the legacy router.

    This prevents route_question() from incorrectly
    sending recognized reasoning/paraphrase questions
    into the extractor route.
    """

    try:
        plan = build_queries(
            question
        )

    except Exception:
        plan = {
            "intent":
                "general",

            "subject":
                "",

            "canonical_question":
                None,

            "comparison_subjects":
                None,

            "queries":
                [question],
        }

    if not isinstance(
        plan,
        dict,
    ):
        plan = {
            "intent":
                "general",

            "subject":
                "",

            "canonical_question":
                None,

            "comparison_subjects":
                None,

            "queries":
                [question],
        }

    # --------------------------------------------------
    # Comparison planner is also allowed to upgrade
    # a query to comparison even when the general
    # query planner misses a wording variant.
    # --------------------------------------------------

    try:
        comparison_plan = (
            build_comparison_queries(
                question
            )
        )
    except Exception:
        comparison_plan = None

    if comparison_plan is not None:

        left = (
            comparison_plan.get(
                "left_entity"
            )
            or ""
        ).strip()

        right = (
            comparison_plan.get(
                "right_entity"
            )
            or ""
        ).strip()

        if left and right:
            plan[
                "intent"
            ] = "comparison"

            plan[
                "subject"
            ] = (
                f"{left} vs {right}"
            )

            plan[
                "comparison_subjects"
            ] = (
                left,
                right,
            )

            plan[
                "canonical_question"
            ] = (
                "What are the differences "
                f"between {left} and {right}?"
            )

    # The semantic plan owns routing. The legacy router is consulted only
    # for otherwise-unclassified questions, preserving extractor behavior
    # without allowing a second routing decision downstream.
    intent = (plan.get("intent") or "general").strip()
    if intent in PLANNED_REASONING_INTENTS:
        plan["route"] = "model"
    else:
        try:
            plan["route"] = route_question(question)
        except Exception:
            logger.exception("Legacy fallback routing failed")
            plan["route"] = "model"
        if plan["route"] not in {"extractor", "model"}:
            plan["route"] = "model"

    return plan


def should_force_reasoning(
    plan,
):
    if not plan:
        return False

    intent = (
        plan.get(
            "intent",
            "general",
        )
        or "general"
    )

    return (
        intent
        in PLANNED_REASONING_INTENTS
    )


# ==================================================
# SINGLE-QUESTION PROCESSOR
# ==================================================

def answer_question(
    pipeline,
    question,
    verbose=True,
    *,
    document_ids=None,
):
    logger.info(
        "Question received: %s",
        question,
    )

    try:
        return _answer_question_impl(
            pipeline,
            question,
            verbose,
            document_ids=document_ids,
        )
    except Exception as exc:
        logger.error(
            "Unhandled error while answering question: %r",
            question,
            exc_info=True,
        )
        raise


def _answer_question_impl(
    pipeline,
    question,
    verbose=True,
    *,
    document_ids=None,
):
    device = pipeline[
        "device"
    ]

    tokenizer = pipeline[
        "tokenizer"
    ]

    model = pipeline[
        "model"
    ]

    chunks = pipeline[
        "chunks"
    ]

    retrieval_index = pipeline[
        "retrieval_index"
    ]

    document_frequency = pipeline[
        "document_frequency"
    ]

    # ==================================================
    # SEMANTIC PLAN FIRST
    # ==================================================

    plan = runtime_plan(
        question
    )

    planned_intent = (
        plan.get(
            "intent",
            "general",
        )
        or "general"
    )

    canonical_question = (
        canonical_question_for_intent(
            question,
            plan,
        )
    )

    logger.debug(
        "Semantic plan: intent=%s subject=%r",
        planned_intent,
        plan.get("subject"),
    )

    # runtime_plan is the sole authoritative routing decision.
    route = plan.get("route", "model")

    logger.debug(
        "Routing decision: router=%s planned_intent=%s "
        "effective_route=%s",
        route,
        planned_intent,
        route,
    )

    if verbose:
        print(
            "\nRouter:",
            route,
        )

        print(
            "Planned intent:",
            planned_intent,
        )

        print(
            "Planned subject:",
            plan.get(
                "subject"
            ),
        )

        print(
            "Canonical question:",
            canonical_question,
        )

    result = {
        "question":
            question,

        "router":
            route,

        "mode":
            None,

        "retriever":
            None,

        "answer_type":
            None,

        "answer":
            None,

        "supported":
            False,

        "evidence":
            None,

        "runtime_plan":
            plan,

        "canonical_question":
            canonical_question,
    }

    # ==================================================
    # ASSERTED RELATION DETECTION
    # ==================================================

    asserted_relation = (
        extract_asserted_relation(
            question
        )
    )

    result[
        "asserted_relation"
    ] = asserted_relation

    # ==================================================
    # EARLY PREMISE VALIDATION
    #
    # Critical fix:
    # Explicit cross-concept relations are checked
    # before extractor output can be accepted.
    # ==================================================

    if asserted_relation is not None:

        premise_retrieval = (
            retrieve_for_reasoning(
                question,
                chunks,
                retrieval_index,
                document_frequency,
                document_ids=document_ids,
            )
        )

        if premise_retrieval is None:
            result[
                "premise_validation"
            ] = {
                "required":
                    True,

                "supported":
                    False,

                "relation":
                    asserted_relation[
                        "relation"
                    ],

                "source":
                    asserted_relation[
                        "source"
                    ],

                "target":
                    asserted_relation[
                        "target"
                    ],

                "supporting_sentence":
                    None,
            }

            result = build_system_result(
                result
            )

            if verbose:
                print(
                    "\nPremise validation: "
                    "UNSUPPORTED"
                )

                print(
                    "\nSystem:",
                    result["answer"],
                )

            return result

        premise_context = (
            premise_retrieval.get(
                "context",
                "",
            )
            or ""
        )

        premise_validation = (
            validate_asserted_relation(
                question,
                premise_context,
            )
        )
        result[
            "evidence"
        ] = {
            "kind": "hybrid",
            "results": premise_retrieval.get("results", []),
            "context": premise_context,
        }

        result[
            "premise_validation"
        ] = premise_validation

        if verbose:
            print(
                "\nAsserted relation:"
            )

            print(
                "Relation:",
                premise_validation.get(
                    "relation"
                ),
            )

            print(
                "Source:",
                premise_validation.get(
                    "source"
                ),
            )

            print(
                "Target:",
                premise_validation.get(
                    "target"
                ),
            )

            print(
                "Supported:",
                premise_validation.get(
                    "supported"
                ),
            )

        if not premise_validation[
            "supported"
        ]:
            result = build_system_result(
                result
            )

            if verbose:
                print(
                    "\nSystem:",
                    result["answer"],
                )

            return result

    # ==================================================
    # EXTRACTOR ROUTE
    # ==================================================

    if route == "extractor":

        best_result = (
            retrieve_for_extractor(
                question,
                chunks,
                retrieval_index,
                document_frequency,
            )
        )

        logger.debug(
            "Extractor retrieval: hits=%d",
            1 if best_result is not None else 0,
        )

        result[
            "retriever"
        ] = "V2"

        if best_result is None:
            result = build_system_result(
                result
            )

            if verbose:
                print(
                    "\nSystem:",
                    result["answer"],
                )

            return result

        context = best_result[
            "chunk"
        ]

        result[
            "context"
        ] = context

        result[
            "evidence"
        ] = {
            "kind": "v2",
            "results": [best_result],
            "context": context,
        }

        result[
            "retrieval_score"
        ] = best_result.get(
            "final_score",
            0.0,
        )

        # --- Factual QA path (conditional, lightweight) ---
        if is_factual_question(question):
            factual_answer, supported = extract_factual_answer(
                question,
                context,
            )

            if factual_answer is not None and supported:
                result[
                    "answer"
                ] = factual_answer
                result[
                    "answer_type"
                ] = "factual"
                result[
                    "supported"
                ] = True
                result[
                    "confidence"
                ] = extraction_confidence(
                    question,
                    context,
                    factual_answer,
                )

                if verbose:
                    print(
                        "\nFactual answer:",
                        factual_answer,
                    )

                    print(
                        "\nSupported by evidence grounding check",
                    )

                if not _answer_addresses_question(
                    question, factual_answer,
                ):
                    result = build_system_result(
                        result,
                    )
                    return result

                return result

            # Factual answers must pass the dedicated grounding path. The
            # generic extractor can otherwise turn an unrelated sentence
            # with overlapping attribute words into a supported answer.
            result = build_system_result(result)
            if verbose:
                print(
                    "\nSystem:",
                    result["answer"],
                )
            return result

        extracted = extract_answer(
            question,
            context,
        )

        if not extracted:
            result = build_system_result(
                result
            )

            if verbose:
                print(
                    "\nSystem:",
                    result["answer"],
                )

            return result

        confidence = (
            extraction_confidence(
                question,
                context,
                extracted,
            )
        )

        result[
            "confidence"
        ] = confidence

        if verbose:
            print(
                "\nExtraction confidence:",
                f"{confidence:.2f}",
            )

        if (
            confidence
            < CONFIDENCE_THRESHOLD
        ):
            result = build_system_result(
                result
            )

            if verbose:
                print(
                    "\nSystem:",
                    result["answer"],
                )

            return result

        answer = format_extracted_answer(
            question,
            extracted,
        )

        result[
            "answer_type"
        ] = "extractor"

        result[
            "answer"
        ] = answer

        result[
            "supported"
        ] = True

        logger.info(
            "Answer generated (extractor): %s",
            answer,
        )

        if verbose:
            print(
                "\nExtractor:",
                answer,
            )

        return result

    # ==================================================
    # COMPARISON ROUTE
    # ==================================================

    comparison_plan = None

    if planned_intent == "comparison":

        comparison_subjects = (
            plan.get(
                "comparison_subjects"
            )
        )

        if comparison_subjects:
            left, right = (
                comparison_subjects
            )

            comparison_plan = {
                "left_entity":
                    left,

                "right_entity":
                    right,

                "left_query":
                    left,

                "right_query":
                    right,
            }

        else:
            comparison_plan = (
                build_comparison_queries(
                    question
                )
            )

    if comparison_plan is not None:

        result[
            "mode"
        ] = "comparison"

        if verbose:
            print(
                "\nMode: comparison"
            )

        comparison_query = (
            canonical_question
            if canonical_question
            else question
        )

        comparison_result = (
            retrieve_comparison(
                comparison_query,
                chunks,
                retrieval_index,
                document_frequency,
                document_ids=document_ids,
            )
        )

        logger.debug(
            "Comparison retrieval: hits=%s",
            (
                "yes"
                if comparison_result is not None
                else "no"
            ),
        )

        if comparison_result is None:
            result = build_system_result(
                result
            )

            if verbose:
                print(
                    "\nSystem:",
                    result["answer"],
                )

            return result

        comparison_confidence = (
            score_comparison(
                comparison_result
            )
        )

        result[
            "comparison_confidence"
        ] = comparison_confidence

        left_score = (
            comparison_confidence[
                "left"
            ][
                "score"
            ]
        )

        right_score = (
            comparison_confidence[
                "right"
            ][
                "score"
            ]
        )

        if verbose:
            print(
                "\nComparison confidence:"
            )

            print(
                "Left:",
                f"{left_score:.2f}",
            )

            print(
                "Right:",
                f"{right_score:.2f}",
            )

        if not comparison_confidence[
            "sufficient"
        ]:
            answer = (
                comparison_unsupported_answer(
                    comparison_result,
                    comparison_confidence,
                )
            )

            result = build_system_result(
                result,
                answer=answer,
            )

            if verbose:
                print(
                    "\nSystem:",
                    result["answer"],
                )

            return result

        comparison_context = (
            comparison_result[
                "context"
            ]
        )

        result[
            "context"
        ] = comparison_context

        result[
            "evidence"
        ] = {
            "kind": "comparison",
            "left": comparison_result.get("left", {}),
            "right": comparison_result.get("right", {}),
            "context": comparison_context,
        }

        if verbose:
            print(
                "\n--- Comparison evidence ---\n"
            )

            print(
                comparison_context
            )

        answer = synthesize_comparison(
            comparison_query,
            comparison_result,
        )

        if not answer:
            result = build_system_result(
                result
            )

            if verbose:
                print(
                    "\nSystem:",
                    result["answer"],
                )

            return result

        result[
            "answer_type"
        ] = "comparison"

        result[
            "answer"
        ] = answer

        result[
            "supported"
        ] = True

        logger.info(
            "Answer generated (comparison): %s",
            answer,
        )

        if verbose:
            print(
                "\nComparison synthesizer:",
                answer,
            )

        return result

    # ==================================================
    # NORMAL REASONING ROUTE
    # ==================================================

    retrieval = retrieve_for_reasoning(
        question,
        chunks,
        retrieval_index,
        document_frequency,
        document_ids=document_ids,
    )

    # A scoped query with no eligible matching document is unsupported. Keep
    # an explicit empty evidence envelope so the runtime contract cannot ask
    # the unscoped fallback source collector to search the global corpus.
    if retrieval is None:
        result["retriever"] = "HYBRID"
        result["evidence"] = {
            "kind": "hybrid",
            "results": [],
            "context": "",
        }
        result = build_system_result(result)
        if verbose:
            print("\nSystem:", result["answer"])
        return result

    result[
        "retriever"
    ] = "HYBRID"

    retrieval_chunk_count = 0
    retrieval_passes = 1
    if (
        retrieval is not None
        and isinstance(
            retrieval.get("results"),
            list,
        )
    ):
        retrieval_chunk_count = len(
            retrieval["results"]
        )

    evidence_results = list(
        (retrieval or {}).get("results", [])
    )

    logger.debug(
        "Reasoning retrieval (hybrid): chunks=%d",
        retrieval_chunk_count,
    )

    # Extract best result before multi-hop detection. A scoped query with
    # no matching runtime document returns no retrieval object; treat that
    # as unsupported rather than falling through to global/static evidence.
    best_result = (retrieval or {}).get("best")

    # CRITICAL: prefer the AGGREGATED context produced by the hybrid
    # retriever's evidence aggregation.
    # best_result is a ranked chunk item and does NOT carry a ``context``
    # key — ``best_result.get("context")`` returns "" and would zero out
    # the entire reasoning pipeline.
    # The aggregated evidence (joined top evidence sentences) lives at
    # ``retrieval["context"]``. Fall back to ``best_result["chunk"]`` if
    # for some reason the aggregated context is unavailable.
    aggregated_context = (retrieval or {}).get("context") or ""

    # --- Multi-hop detection and conditional 2-pass ---
    # Only for genuine multi-hop questions (two explicit information
    # needs): at most 1 extra retrieval pass with decomposed subqueries.
    # Default: 1 pass.
    # A specialized semantic intent is preserved — a multi-hop question
    # keeps its intent (cause / effect / change) and still flows to its
    # specialized synthesizer after the second retrieval pass.
    multi_hop = is_multi_hop_question(question, plan)

    if multi_hop and retrieval is not None and best_result is not None:
        # Decompose into 2 subqueries: isolate the two question components.
        q = question.strip()
        subqueries = []

        # Generic structural decomposition first: the question asks for a
        # relationship/transition between TWO distinct concepts
        # ("X's decline affected Y", "effects of X on Y", ...). The second
        # concept gets its own retrieval pass.
        decomposed = decompose_multi_hop_question(q)
        if decomposed is not None:
            concept_a, concept_b = decomposed
            concept_b = _clean_second_concept(concept_b, concept_a)
            if concept_a and concept_b:
                subqueries = [
                    concept_a,
                    concept_b,
                ]

        if len(subqueries) < 2:
            # Fall back to " and " / " or " two-clause follow-ups.
            if " and " in q.lower():
                parts = q.lower().split(" and ", 1)
                subqueries = [p.strip() for p in parts]
                # Contextualize second subquery with first subquery's subject
                if len(subqueries) == 2:
                    subqueries[1] = _clean_second_concept(subqueries[1], subqueries[0])
            elif " or " in q.lower():
                parts = q.lower().split(" or ", 1)
                subqueries = [p.strip() for p in parts]
                if len(subqueries) == 2:
                    subqueries[1] = _clean_second_concept(subqueries[1], subqueries[0])
            else:
                # Generic multi-hop decomposition: try to split on key connectors
                for connector in [" because ", " since ", " as a result "]:
                    if connector in q.lower():
                        parts = q.lower().split(connector, 1)
                        subqueries = [p.strip() for p in parts]
                        if len(subqueries) == 2:
                            subqueries[1] = _clean_second_concept(subqueries[1], subqueries[0])
                        break

        if len(subqueries) >= 2:
            # Perform second retrieval pass with second subquery
            try:
                extra_retrieval = retrieve_for_reasoning(
                    subqueries[1],
                    chunks,
                    retrieval_index,
                    document_frequency,
                    document_ids=document_ids,
                )
                retrieval_passes = 2
                if extra_retrieval is not None and extra_retrieval.get("results"):
                    evidence_results.extend(
                        extra_retrieval.get("results", [])
                    )
                    # Merge evidence from both passes
                    extra_context = extra_retrieval.get("context") or ""
                    if extra_context:
                        # Concatenate the two aggregated contexts.
                        reasoning_context = (aggregated_context + "\n" + extra_context).strip()
                    else:
                        reasoning_context = aggregated_context

                    result[
                        "evidence"
                    ] = {
                        "kind": "hybrid",
                        "results": evidence_results,
                        "context": reasoning_context,
                    }
                else:
                    reasoning_context = aggregated_context
            except Exception:
                # If extra retrieval fails, fall through to single-pass behavior
                reasoning_context = aggregated_context
                retrieval_passes = 1
        else:
            reasoning_context = aggregated_context
            retrieval_passes = 1
    else:
        reasoning_context = aggregated_context

    # Preserve the complete retrieval evidence that fed every downstream
    # answer path, including single-pass V4 and multi-hop reasoning.
    result[
        "evidence"
    ] = {
        "kind": "hybrid",
        "results": evidence_results,
        "context": reasoning_context,
    }

    # The ranked result list can contain a complete, high-quality document
    # chunk even when the compact aggregated context selected a neighboring
    # sentence. For named factual questions, add only chunks that satisfy
    # the same identifier/attribute grounding check; unrelated chunks cannot
    # weaken the unsupported-answer gate.
    if is_factual_question(question):
        grounded_chunks = []
        for item in (retrieval or {}).get("results", []):
            chunk = item.get("chunk", "") if isinstance(item, dict) else ""
            if chunk and _named_fact_anchors_match(question, chunk):
                grounded_chunks.append(chunk)
        if grounded_chunks:
            reasoning_context = (
                "\n".join(grounded_chunks) + "\n" + reasoning_context
            ).strip()

    # --- SOP section-first extraction ---
    # When the question targets a specific section of a procedural
    # document, extract from the correct section of the FULL chunk
    # *before* the generic factual path.  The generic path operates
    # on the aggregated reasoning_context (a sentence summary) and
    # routinely picks sentences from the wrong SOP section.
    if (
        planned_intent == "general"
        and is_factual_question(question)
    ):
        for _ev_item in evidence_results:
            if not isinstance(_ev_item, dict):
                continue
            _ev_chunk = _ev_item.get("chunk", "")
            if not _ev_chunk or len(_ev_chunk) < 100:
                continue
            _ev_low = _ev_chunk.lower()
            if not (
                "sop" in _ev_low
                or "standard operating procedure" in _ev_low
                or "lockout/tagout" in _ev_low
                or "before starting" in _ev_low
            ):
                continue
            _sec_ans = _extract_sop_section(
                question, _ev_chunk,
            )
            if _sec_ans:
                _sec_parts = [
                    p.strip().casefold()
                    for p in _sec_ans.split(";")
                    if p.strip()
                ]
                _chunk_low = _ev_chunk.casefold()
                if _sec_parts and all(
                    _p in _chunk_low for _p in _sec_parts
                ):
                    result["answer"] = _sec_ans
                    result["answer_type"] = "factual"
                    result["supported"] = True
                    result["confidence"] = (
                        extraction_confidence(
                            question, _ev_chunk,
                            _sec_ans,
                        )
                    )
                    result["context"] = _ev_chunk
                    if verbose:
                        print(
                            "\nFactual answer"
                            " (SOP section early):",
                            _sec_ans,
                        )
                    if not _answer_addresses_question(
                        question, _sec_ans,
                    ):
                        result = build_system_result(
                            result,
                        )
                        return result
                    return result

    # --- Factual QA path (conditional, lightweight) ---
    # Only for questions with NO specialized reasoning intent.
    # Specialized intents (cause / change / effect / comparison /
    # structure / ...) keep flowing to their deterministic
    # synthesizers below. Guarding on ``planned_intent == "general"``
    # prevents the earlier regression where the who/when/where/what
    # heuristic short-circuited ~70% of benchmark questions. Pure
    # factual questions that route to the reasoning path still get
    # the cheap evidence-grounded extraction instead of the 20M
    # reasoning model (which hallucinates on them).
    if (
        planned_intent == "general"
        and (
            is_factual_question(question)
            or question.strip().lower().startswith("how ")
        )
    ):
        factual_answer, supported = extract_factual_answer(
            question,
            reasoning_context,
        )

        if (
            factual_answer is not None
            and supported
        ):
            named_question = _named_fact_anchors_match(question, question) is not None
            evidence_text = "\n".join(
                str(item.get("chunk", ""))
                for item in evidence_results
                if isinstance(item, dict)
                and (
                    not named_question
                    or _named_fact_anchors_match(
                        question,
                        str(item.get("chunk", "")),
                    )
                )
            )
            if (
                not evidence_text
                or factual_answer.casefold() not in evidence_text.casefold()
            ):
                factual_answer, supported = None, False

        if (
            factual_answer is not None
            and supported
        ):
            result[
                "answer"
            ] = factual_answer

            result[
                "answer_type"
            ] = "factual"

            result[
                "supported"
            ] = True

            result[
                "confidence"
            ] = extraction_confidence(
                question,
                reasoning_context,
                factual_answer,
            )

            result[
                "multi_hop"
            ] = multi_hop

            result[
                "retrieval_passes"
            ] = retrieval_passes

            if verbose:
                print(
                    "\nFactual answer:",
                    factual_answer,
                )

                print(
                    "\nSupported by evidence grounding check",
                )

            if not _answer_addresses_question(
                question, factual_answer,
            ):
                result = build_system_result(
                    result,
                )
                return result

            return result

        # A pure factual question the extractor could not ground.
        # Do NOT fall through to the 20M reasoning model here — it
        # hallucinates nonsense like "It was due to the Romanism."
        # for "When was the Magna Carta signed?".  But DO fall
        # through to the deterministic synthesizers below (summary,
        # structure, etc.) which can handle multi-step or procedural
        # questions that the factual extractor cannot condense into
        # a single sentence.
        result[
            "context"
        ] = reasoning_context

        result[
            "multi_hop"
        ] = multi_hop

        result[
            "retrieval_passes"
        ] = retrieval_passes

        # Runtime-document full-chunk fallback: the aggregated
        # context may be too weak for multi-step SOP questions
        # (e.g. "What are the restart steps after maintenance?")
        # because the aggregation only picks a few top sentences.
        # When evidence has a high-scoring chunk whose FULL content
        # contains the answer, extract from it.
        if not reasoning_context.strip():
            reasoning_context = ""

        for _item in evidence_results:
            if not isinstance(_item, dict):
                continue
            _chunk = _item.get("chunk", "")
            if not _chunk or len(_chunk) < 100:
                continue
            _chunk_low = _chunk.lower()
            _is_procedural = (
                "sop" in _chunk_low
                or "standard operating procedure" in _chunk_low
                or "lockout/tagout" in _chunk_low
                or "before starting" in _chunk_low
            )
            if not _is_procedural:
                continue

            # Section-level extraction for SOP documents: identify
            # which section the question targets and collect all
            # items under that section header.
            _section_answer = (
                _extract_sop_section(question, _chunk)
            )
            if _section_answer:
                # Ground-check: the extracted section text must
                # actually appear in the evidence chunk.
                if (
                    _section_answer.casefold()
                    not in _chunk.casefold()
                ):
                    continue
                result["answer"] = _section_answer
                result["answer_type"] = "factual"
                result["supported"] = True
                result["confidence"] = (
                    extraction_confidence(
                        question, _chunk,
                        _section_answer,
                    )
                )
                result["context"] = _chunk
                if verbose:
                    print(
                        "\nFactual answer"
                        " (SOP section):",
                        _section_answer,
                    )
                if not _answer_addresses_question(
                    question, _section_answer,
                ):
                    result = build_system_result(
                        result,
                    )
                    return result
                return result

            _fa, _fs = extract_factual_answer(
                question, _chunk,
            )
            if _fa and _fs:
                result["answer"] = _fa
                result["answer_type"] = "factual"
                result["supported"] = True
                result["confidence"] = (
                    extraction_confidence(
                        question, _chunk, _fa,
                    )
                )
                result["context"] = _chunk
                if verbose:
                    print(
                        "\nFactual answer"
                        " (runtime chunk):",
                        _fa,
                    )
                if not _answer_addresses_question(
                    question, _fa,
                ):
                    result = build_system_result(
                        result,
                    )
                    return result
                return result

        # Factual extractor and SOP fallback both failed for a
        # non-procedural question.  Return unsupported rather than
        # falling through to deterministic synthesizers which need
        # a tokenizer (may be None in test mocks) and would
        # hallucinate on questions the extractor already rejected.
        result = build_system_result(result)

        if verbose:
            print(
                "\nSystem:",
                result["answer"],
            )

        return result

    best_result = retrieval.get(
        "best"
    )

    result[
        "multi_hop"
    ] = multi_hop

    result[
        "retrieval_passes"
    ] = retrieval_passes

    def _display_type(
        answer_type,
    ):
        """Report answers produced for detected multi-hop questions as
        answer_type="multi_hop".

        The deterministic intent synthesizers still generate the
        content (a multi-hop question keeps its cause/effect/change
        intent). Only the reported type changes, so consumers that
        expect a "multi_hop" type for genuine two-information-need
        questions (e.g. the V4 benchmark) can classify them correctly.
        """
        if multi_hop:
            return "multi_hop"
        return answer_type

    retrieval_plan = (
        retrieval.get(
            "plan",
            {}
        )
        or {}
    )

    # Prefer the plan computed before routing.
    #
    # Retriever V4's returned plan is retained for
    # diagnostics, but the runtime plan is the primary
    # semantic decision because it already prevented
    # incorrect extractor routing.

    effective_plan = (
        plan
        if (
            plan
            and plan.get(
                "intent",
                "general",
            ) != "general"
        )
        else retrieval_plan
    )

    result[
        "retrieval_plan"
    ] = effective_plan

    result[
        "retriever_plan_raw"
    ] = retrieval_plan

    if best_result is None:
        result = build_system_result(
            result
        )

        if verbose:
            print(
                "\nSystem:",
                result["answer"],
            )

        return result

    result[
        "context"
    ] = reasoning_context

    result[
        "retrieval_score"
    ] = best_result.get(
        "merged_score",
        0.0,
    )

    if verbose:
        print(
            "\nRetriever: V4"
        )

        print(
            "\nIntent:",
            effective_plan.get(
                "intent"
            ),
        )

        print(
            "Subject:",
            effective_plan.get(
                "subject"
            ),
        )

        print(
            "\nBest retrieval score:",
            f"{result['retrieval_score']:.2f}",
        )

        print(
            "\n--- Aggregated evidence ---\n"
        )

        print(
            reasoning_context
        )

    if not reasoning_context.strip():
        result = build_system_result(
            result
        )

        if verbose:
            print(
                "\nSystem:",
                result["answer"],
            )

        return result

    # ==================================================
    # SECOND PREMISE CHECK
    #
    # Defensive check before any deterministic
    # synthesizer can accept the question.
    # ==================================================

    premise_validation = (
        validate_asserted_relation(
            question,
            reasoning_context,
        )
    )

    result[
        "premise_validation"
    ] = premise_validation

    if (
        premise_validation[
            "required"
        ]
        and not premise_validation[
            "supported"
        ]
    ):
        result = build_system_result(
            result
        )

        if verbose:
            print(
                "\nPremise validation: "
                "UNSUPPORTED"
            )

            print(
                "\nSystem:",
                result["answer"],
            )

        return result

    # ==================================================
    # CANONICALIZE PARAPHRASED INTENT
    # ==================================================

    canonical_question = (
        canonical_question_for_intent(
            question,
            effective_plan,
        )
    )

    result[
        "canonical_question"
    ] = canonical_question

    intent = (
        effective_plan.get(
            "intent",
            "general",
        )
        or "general"
    )

    if verbose:
        if (
            canonical_question
            != question
        ):
            print(
                "\nCanonical question:",
                canonical_question,
            )

    # ==================================================
    # INTENT-FIRST DETERMINISTIC SYNTHESIS
    # ==================================================

    # ------------------------------------------
    # Causal
    # ------------------------------------------

    if intent == "cause":

        answer = synthesize_causal_answer(
            canonical_question,
            reasoning_context,
            original_question=question,
        )

        if answer:
            result[
                "answer_type"
            ] = _display_type("causal")

            result[
                "answer"
            ] = answer

            result[
                "supported"
            ] = True

            logger.info(
                "Answer generated (causal): %s",
                answer,
            )

            if verbose:
                print(
                    "\nCausal synthesizer:",
                    answer,
                )

            return result

    # ------------------------------------------
    # Change
    # ------------------------------------------

    elif intent == "change":

        answer = synthesize_change_answer(
            canonical_question,
            reasoning_context,
        )

        if answer:
            result[
                "answer_type"
            ] = _display_type("change")

            result[
                "answer"
            ] = answer

            result[
                "supported"
            ] = True

            logger.info(
                "Answer generated (change): %s",
                answer,
            )

            if verbose:
                print(
                    "\nChange synthesizer:",
                    answer,
                )

            return result

    # ------------------------------------------
    # Effect
    # ------------------------------------------

    elif intent == "effect":

        answer = synthesize_effect_answer(
            canonical_question,
            reasoning_context,
        )

        if answer:
            result[
                "answer_type"
            ] = _display_type("effect")

            result[
                "answer"
            ] = answer

            result[
                "supported"
            ] = True

            logger.info(
                "Answer generated (effect): %s",
                answer,
            )

            if verbose:
                print(
                    "\nEffect synthesizer:",
                    answer,
                )

            return result

    # ------------------------------------------
    # Entity list
    # ------------------------------------------

    elif intent == "entity_list":

        answer = (
            synthesize_entity_list_answer(
                canonical_question,
                reasoning_context,
            )
        )

        if answer:
            result[
                "answer_type"
            ] = _display_type("entity_list")

            result[
                "answer"
            ] = answer

            result[
                "supported"
            ] = True

            logger.info(
                "Answer generated (entity_list): %s",
                answer,
            )

            if verbose:
                print(
                    "\nEntity-list synthesizer:",
                    answer,
                )

            return result

    # ------------------------------------------
    # Structure
    # ------------------------------------------

    elif intent == "structure":

        answer = (
            synthesize_structure_answer(
                canonical_question,
                reasoning_context,
            )
        )

        if answer:
            result[
                "answer_type"
            ] = _display_type("structure")

            result[
                "answer"
            ] = answer

            result[
                "supported"
            ] = True

            logger.info(
                "Answer generated (structure): %s",
                answer,
            )

            if verbose:
                print(
                    "\nStructure synthesizer:",
                    answer,
                )

            return result

    # ------------------------------------------
    # Process / significance / features
    #
    # These are handled by summary synthesizer.
    # ------------------------------------------

    elif intent in {
        "process",
        "significance",
        "features",
    }:

        answer = (
            synthesize_summary_answer(
                canonical_question,
                reasoning_context,
            )
        )

        if answer:
            result[
                "answer_type"
            ] = _display_type("summary")

            result[
                "answer"
            ] = answer

            result[
                "supported"
            ] = True

            logger.info(
                "Answer generated (summary): %s",
                answer,
            )

            if verbose:
                print(
                    "\nSummary synthesizer:",
                    answer,
                )

            return result

    # ==================================================
    # ORIGINAL-WORDING DETERMINISTIC FALLBACK
    #
    # Keeps compatibility with existing behavior.
    # ==================================================

    causal_answer = (
        synthesize_causal_answer(
            question,
            reasoning_context,
        )
    )

    if causal_answer:
        result[
            "answer_type"
        ] = _display_type("causal")

        result[
            "answer"
        ] = causal_answer

        result[
            "supported"
        ] = True

        logger.info(
            "Answer generated (causal-fallback): %s",
            causal_answer,
        )

        if verbose:
            print(
                "\nCausal synthesizer:",
                causal_answer,
            )

        return result

    # When the causal synthesizer could not match the question
    # (e.g. false-premise questions with temporal modifiers),
    # do NOT fall through to the reasoning model which would
    # hallucinate an answer.  Return unsupported instead.
    if intent == "cause":
        result = build_system_result(result)

        if verbose:
            print(
                "\nSystem:",
                result["answer"],
            )

        return result

    change_answer = (
        synthesize_change_answer(
            question,
            reasoning_context,
        )
    )

    if change_answer:
        result[
            "answer_type"
        ] = _display_type("change")

        result[
            "answer"
        ] = change_answer

        result[
            "supported"
        ] = True

        logger.info(
            "Answer generated (change-fallback): %s",
            change_answer,
        )

        if verbose:
            print(
                "\nChange synthesizer:",
                change_answer,
            )

        return result

    effect_answer = (
        synthesize_effect_answer(
            question,
            reasoning_context,
        )
    )

    if effect_answer:
        result[
            "answer_type"
        ] = _display_type("effect")

        result[
            "answer"
        ] = effect_answer

        result[
            "supported"
        ] = True

        logger.info(
            "Answer generated (effect-fallback): %s",
            effect_answer,
        )

        if verbose:
            print(
                "\nEffect synthesizer:",
                effect_answer,
            )

        return result

    entity_list_answer = (
        synthesize_entity_list_answer(
            question,
            reasoning_context,
        )
    )

    if entity_list_answer:
        result[
            "answer_type"
        ] = _display_type("entity_list")

        result[
            "answer"
        ] = entity_list_answer

        result[
            "supported"
        ] = True

        logger.info(
            "Answer generated (entity_list-fallback): %s",
            entity_list_answer,
        )

        if verbose:
            print(
                "\nEntity-list synthesizer:",
                entity_list_answer,
            )

        return result

    structure_answer = (
        synthesize_structure_answer(
            question,
            reasoning_context,
        )
    )

    if structure_answer:
        result[
            "answer_type"
        ] = _display_type("structure")

        result[
            "answer"
        ] = structure_answer

        result[
            "supported"
        ] = True

        logger.info(
            "Answer generated (structure-fallback): %s",
            structure_answer,
        )

        if verbose:
            print(
                "\nStructure synthesizer:",
                structure_answer,
            )

        return result

    summary_answer = (
        synthesize_summary_answer(
            question,
            reasoning_context,
        )
    )

    if summary_answer:
        result[
            "answer_type"
        ] = _display_type("summary")

        result[
            "answer"
        ] = summary_answer

        result[
            "supported"
        ] = True

        logger.info(
            "Answer generated (summary-fallback): %s",
            summary_answer,
        )

        if verbose:
            print(
                "\nSummary synthesizer:",
                summary_answer,
            )

        if not _answer_addresses_question(
            question, summary_answer,
        ):
            result = build_system_result(
                result,
            )
            return result

        return result

    # ==================================================
    # GENERIC REASONING SUPPORT GATE
    # ==================================================

    reasoning_support = (
        reasoning_support_confidence(
            question=question,
            context=reasoning_context,
            retrieval_score=result.get(
                "retrieval_score",
                0.0,
            ),
        )
    )

    if not isinstance(
        reasoning_support,
        dict,
    ):
        reasoning_support = {
            "score":
                0.0,

            "sufficient":
                False,

            "term_coverage":
                0.0,

            "supporting_sentences":
                0,

            "best_sentence_overlap":
                0.0,

            "matched_terms":
                [],
        }

    result[
        "reasoning_support"
    ] = reasoning_support

    support_score = reasoning_support.get(
        "score",
        0.0,
    )

    term_coverage = reasoning_support.get(
        "term_coverage",
        0.0,
    )

    supporting_sentences = (
        reasoning_support.get(
            "supporting_sentences",
            0,
        )
    )

    best_sentence_overlap = (
        reasoning_support.get(
            "best_sentence_overlap",
            0.0,
        )
    )

    matched_terms = reasoning_support.get(
        "matched_terms",
        [],
    )

    sufficient = bool(
        reasoning_support.get(
            "sufficient",
            False,
        )
    )

    if verbose:
        print(
            "\nReasoning fallback support:"
        )

        print(
            "Score:",
            f"{support_score:.2f}",
        )

        print(
            "Coverage:",
            f"{term_coverage:.2f}",
        )

        print(
            "Supporting sentences:",
            supporting_sentences,
        )

        print(
            "Best sentence overlap:",
            f"{best_sentence_overlap:.2f}",
        )

        print(
            "Matched terms:",
            matched_terms,
        )

    if not sufficient:
        result = build_system_result(
            result
        )

        if verbose:
            print(
                "\nSystem:",
                result["answer"],
            )

        return result

    # ==================================================
    # GENERIC REASONING MODEL
    # ==================================================

    answer = generate(
        model,
        tokenizer,
        reasoning_context,
        question,
        device,
    )

    if not answer:
        result = build_system_result(
            result
        )

        if verbose:
            print(
                "\nSystem:",
                result["answer"],
            )

        return result

    result[
        "answer_type"
    ] = _display_type("reasoning_model")

    result[
        "answer"
    ] = answer

    result[
        "supported"
    ] = True

    logger.info(
        "Answer generated (reasoning_model): %s",
        answer,
    )

    if verbose:
        print(
            "\nReasoning model:",
            answer,
        )

    if not _answer_addresses_question(
        question, answer,
    ):
        result = build_system_result(
            result,
        )
        return result

    return result


# --------------------------------------------------
# Startup display
# --------------------------------------------------

def print_system_info():
    print(
        "\nHybrid retrieval enabled:"
    )

    print(
        "Extractor route -> Retriever V2"
    )

    print(
        "Reasoning route -> Retriever V4"
    )

    print(
        "Asserted relations -> "
        "early premise validation gate"
    )

    print(
        "Causal reasoning -> "
        "Retriever V4 + causal synthesizer"
    )

    print(
        "Change reasoning -> "
        "Retriever V4 + change synthesizer"
    )

    print(
        "Effect reasoning -> "
        "Retriever V4 + effect synthesizer"
    )

    print(
        "Entity-list reasoning -> "
        "Retriever V4 + entity-list synthesizer"
    )

    print(
        "Structure reasoning -> "
        "Retriever V4 + structure synthesizer"
    )

    print(
        "Summary reasoning -> "
        "Retriever V4 + summary synthesizer"
    )

    print(
        "Paraphrases -> "
        "V4 intent canonicalization"
    )

    print(
        "Comparison route -> "
        "adaptive dual retrieval "
        "+ confidence gate "
        "+ deterministic synthesizer"
    )

    print(
        "Generic reasoning fallback -> "
        "V4 support gate + reasoning model"
    )

    print(
        "\nKnowledge sources:"
    )

    for path in KNOWLEDGE_FILES:
        print(
            "-",
            path,
        )


# --------------------------------------------------
# Interactive main
# --------------------------------------------------

def main():
    pipeline = initialize_pipeline(
        verbose=True,
    )

    print_system_info()

    print(
        "\nSystem ready."
    )

    print(
        "Type 'quit' to exit."
    )

    while True:
        question = input(
            "\nYou: "
        ).strip()

        if question.lower() in {
            "quit",
            "exit",
        }:
            break

        if not question:
            continue

        answer_question(
            pipeline,
            question,
            verbose=True,
        )


if __name__ == "__main__":
    main()
