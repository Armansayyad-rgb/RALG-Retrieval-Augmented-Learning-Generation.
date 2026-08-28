"""Generalization regression set for the unified support gate.

Derived from the false-support failure modes observed in the frozen
holdout_v1 baseline (unsupported questions accepted as supported):

- causal-marker sentences templated into answers for an unrelated
  subject (causal synthesizer never required subject relatedness);
- summary-synthesizer evidence selected on generic word overlap and
  sentence-length bonuses without ever mentioning the question
  subject;
- factual "what is/was" anchoring that accepts a compound proper-noun
  mismatch ("Western Australia" for a question about "Australia").

This set lives OUTSIDE evaluation/holdout_v1, which stays frozen.
Every unsupported/adversarial case is paired with supported controls
so over-refusal is detected. Cases are unit-level: each carries its
own evidence context, so no model load or index build is needed.
"""

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
for import_path in (PROJECT_ROOT, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from causal_synthesizer_v1 import (
    synthesize_causal_answer,
    _unsafe_cause_clause,
    _premise_focus_terms,
)
from summary_synthesizer_v1 import synthesize_summary_answer
from rag_chat_v2 import (
    _anchor_entity_present,
    _has_false_required_safety_action,
    _extract_sop_section,
    _contains_term,
    extract_factual_answer,
)
from retriever_v2 import (
    RuntimeChunk,
    retrieve_candidates,
    _procedural_query,
    _chunk_is_procedural,
    procedural_runtime_boost,
    PROCEDURAL_RUNTIME_BOOST,
    PROCEDURAL_RUNTIME_BOOST_CAP,
    INGESTED_CHUNK_BOOST,
    LEXICAL_TOP_K,
)

DEV_SET = (
    PROJECT_ROOT / "evaluation" / "dev_support_gate_v1.jsonl"
)


def load_cases():
    with open(DEV_SET, encoding="utf-8") as handle:
        return [
            json.loads(line)
            for line in handle
            if line.strip()
        ]


def case_supported(case):
    """Evaluate one dev-set case through the production support logic."""
    mode = case["mode"]
    question = case["question"]
    context = case["context"]

    if mode == "causal":
        return synthesize_causal_answer(question, context) is not None
    if mode.startswith("summary"):
        return synthesize_summary_answer(question, context) is not None
    if mode.startswith("factual"):
        _, supported = extract_factual_answer(question, context)
        return bool(supported)
    raise AssertionError(f"unknown mode {mode}")


class SupportGateGeneralizationTests(unittest.TestCase):
    def test_dev_set_matches_expectations(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 10)
        failures = []
        for case in cases:
            actual = case_supported(case)
            if actual != bool(case["expect_supported"]):
                failures.append(
                    f"{case['case_id']} ({case['failure_mode']}): "
                    f"expected supported={case['expect_supported']}, "
                    f"got {actual}"
                )
        self.assertEqual(
            failures, [], "support-gate generalization regressions"
        )

    def test_unsupported_and_control_mix_present(self):
        cases = load_cases()
        categories = {case["category"] for case in cases}
        self.assertIn("unsupported", categories)
        self.assertIn("supported_control", categories)

    def test_causal_requires_subject_relatedness(self):
        answer = synthesize_causal_answer(
            "Why did the Byzantine navy adopt Greek fire?",
            "The committee rejected the proposal because of "
            "unresolved border disputes.",
        )
        self.assertIsNone(answer)

    def test_summary_requires_subject_mention(self):
        answer = synthesize_summary_answer(
            "Explain how TLS session resumption works.",
            "Another session of work lasted to 4:15 near CBS Studios.",
        )
        self.assertIsNone(answer)

    def test_anchor_guard_compound_mismatch_rejected(self):
        sentence = (
            "It is located near Perth, the capital of Western Australia."
        )
        self.assertFalse(
            _anchor_entity_present(sentence, "australia",
                                   "What is the capital city of Australia?")
        )

    def test_anchor_guard_allows_question_named_compound(self):
        sentence = (
            "Perth is the capital of Western Australia."
        )
        self.assertTrue(
            _anchor_entity_present(sentence, "australia",
                                   "What is the capital of Western Australia?")
        )

    def test_anchor_guard_allows_standalone_anchor(self):
        sentence = "Canberra is Australia's purpose-built capital."
        self.assertTrue(
            _anchor_entity_present(sentence, "australia",
                                   "What is the capital city of Australia?")
        )

    def test_contains_term_rejects_substring_collision(self):
        self.assertFalse(_contains_term("recording accurate measurements", "rate"))
        self.assertFalse(_contains_term("four vellum pages", "age"))

    def test_contains_term_rejects_derived_word(self):
        self.assertFalse(_contains_term("pressure equipment capacity", "press"))
        self.assertFalse(_contains_term("the inventor of the device", "invented"))

    def test_contains_term_allows_inflections_and_boundaries(self):
        self.assertTrue(_contains_term("the growth rate of bamboo", "rate"))
        self.assertTrue(_contains_term("pumps and valves", "pump"))
        self.assertTrue(_contains_term("it was founded in 1912", "founded"))
        self.assertTrue(_contains_term("manuscript's age", "age"))

    def test_identifierless_procedural_supported(self):
        ctx = (
            "Before starting compressor maintenance, verify the oil "
            "level through the sight glass on the crankcase. The oil "
            "level should be between the minimum and maximum marks."
        )
        _, supported = extract_factual_answer(
            "How should the compressor oil level be checked?", ctx
        )
        self.assertTrue(supported)

    def test_identifierless_procedural_unsupported(self):
        ctx = (
            "The printing press was invented around 1440 and changed "
            "European publishing forever."
        )
        _, supported = extract_factual_answer(
            "How should the compressor oil level be checked?", ctx
        )
        self.assertFalse(supported)

    def test_identifierless_procedural_what_must_be_done(self):
        ctx = (
            "Before starting compressor maintenance, verify the oil "
            "level through the sight glass on the crankcase. Lockout-"
            "tagout procedures must be completed to ensure safety."
        )
        _, supported = extract_factual_answer(
            "What must be done before starting compressor maintenance?",
            ctx,
        )
        self.assertTrue(supported)

    def test_premise_focus_rejects_temporal_modifier(self):
        ctx = (
            "The Roman Empire fell in 476 AD when the last Western "
            "emperor was deposed."
        )
        answer = synthesize_causal_answer(
            "Why did the Roman Empire fall in 2020?", ctx
        )
        self.assertIsNone(answer)

    def test_premise_focus_rejects_discovery_year(self):
        ctx = (
            "Watson and Crick discovered the DNA double helix structure "
            "in 1953 using X-ray crystallography data."
        )
        answer = synthesize_causal_answer(
            "What caused the DNA double helix to be discovered in 1800?",
            ctx,
        )
        self.assertIsNone(answer)

    def test_premise_focus_allows_legitimate_causal(self):
        ctx = (
            "Many theories have been advanced for decline of the Roman "
            "Empire. The Empire finally fell after being overrun by "
            "various non-Roman peoples."
        )
        answer = synthesize_causal_answer(
            "Why did the Roman Empire decline?", ctx
        )
        self.assertIsNotNone(answer)

    def test_anaphoric_cause_clause_rejected(self):
        answer = synthesize_causal_answer(
            "Why did the company fail?",
            "The committee rejected the proposed treaty because of "
            "unresolved border disputes. He assumed the role of CEO "
            "after the previous executive resigned.",
        )
        self.assertIsNone(answer)

    def test_anaphoric_clause_guard_rejects_pronoun_start(self):
        self.assertTrue(_unsafe_cause_clause("he assumed the role"))
        self.assertTrue(_unsafe_cause_clause("She signed the treaty"))
        self.assertTrue(_unsafe_cause_clause("it was decided by the board"))

    def test_anaphoric_clause_guard_rejects_parentheses(self):
        self.assertTrue(_unsafe_cause_clause("poor management (see note)"))
        self.assertTrue(_unsafe_cause_clause("excessive debt (unaudited)"))

    def test_anaphoric_clause_guard_allows_clean_clause(self):
        self.assertFalse(
            _unsafe_cause_clause("poor financial management and excessive debt")
        )
        self.assertFalse(
            _unsafe_cause_clause("the board failed to approve the budget")
        )

    def test_premise_focus_frame_words_stripped(self):
        focus = _premise_focus_terms(
            "What caused the Roman Empire to decline?",
            "the Roman Empire",
            "decline",
        )
        self.assertNotIn("caused", focus)
        self.assertEqual(focus, set())

    def test_premise_focus_identifies_temporal_modifier(self):
        focus = _premise_focus_terms(
            "Why did the Roman Empire fall in 2020?",
            "the Roman Empire",
            "fall",
        )
        self.assertIn("2020", focus)

    # ------------------------------------------
    # Procedural retrieval regressions
    # ------------------------------------------
    #
    # These cover the bounded procedural-runtime boost in
    # retriever_v2.procedural_runtime_boost.  The boost must:
    #   1. Fire for a generic inspection-phase query against a
    #      runtime-ingested procedural SOP, so sop_005-style
    #      generic phrases actually retrieve the right chunk.
    #   2. Fire for LOTO/restart procedural controls (sop_001 /
    #      sop_002 style).
    #   3. NOT fire when an unrelated runtime upload is matched
    #      by a procedural question — static-KB relevance must
    #      still win on lexical coverage.
    #   4. NOT fire on static-KB-only questions (boost gated on
    #      RuntimeChunk so static docs get zero boost).

    def _build_minimal_index(self, chunks):
        """Build a real LexicalIndex over the supplied chunks."""
        from retriever_v2 import LexicalIndex, build_index
        index, document_frequency = build_index(list(chunks))
        return index, document_frequency

    def test_procedural_boost_fires_on_runtime_sop_for_inspection_query(
        self,
    ):
        """A generic 'inspection phase' query against a runtime SOP
        chunk must receive the bounded procedural boost.
        """
        sop_chunk = RuntimeChunk(
            "Inspection phase: check the oil level through the "
            "sight glass, inspect belts for wear, examine the "
            "intake filter, and verify all electrical connections "
            "are tight before continuing the maintenance procedure.",
            metadata={"provenance": "runtime", "doc": "sop_runtime.md"},
        )
        boost = procedural_runtime_boost(
            "What must be checked during the inspection phase?",
            sop_chunk,
        )
        self.assertEqual(boost, PROCEDURAL_RUNTIME_BOOST)

    def test_procedural_boost_fires_for_loto_restart_queries(self):
        """Restart and LOTO procedural controls must also fire
        the boost — these are the most safety-critical procedural
        questions and must never be silently demoted.
        """
        loto_chunk = RuntimeChunk(
            "Before starting any compressor maintenance, lockout "
            "and tagout all energy isolation points. Verify zero "
            "voltage at the disconnect, then bleed the receiver "
            "to atmospheric pressure before opening the panel.",
        )
        restart_chunk = RuntimeChunk(
            "Restart steps after compressor maintenance: remove "
            "all LOTO devices, re-energize the main disconnect, "
            "perform an unloaded start, and monitor oil pressure "
            "for the first 10 minutes.",
        )
        self.assertEqual(
            procedural_runtime_boost(
                "What must be done before starting compressor "
                "maintenance?",
                loto_chunk,
            ),
            PROCEDURAL_RUNTIME_BOOST,
        )
        self.assertEqual(
            procedural_runtime_boost(
                "What are the restart steps after compressor "
                "maintenance?",
                restart_chunk,
            ),
            PROCEDURAL_RUNTIME_BOOST,
        )

    def test_procedural_boost_zero_for_unrelated_runtime_upload(self):
        """An unrelated runtime upload that mentions generic
        English tokens (not procedural vocabulary) must receive
        zero boost — the procedural gate requires the CHUNK itself
        to be recognisably procedural.
        """
        unrelated_chunk = RuntimeChunk(
            "The Roman Empire fell in 476 AD when the last Western "
            "emperor was deposed. Germanic tribes seized control of "
            "Italy and the imperial administration collapsed.",
        )
        self.assertEqual(
            procedural_runtime_boost(
                "What must be checked during the inspection phase?",
                unrelated_chunk,
            ),
            0.0,
        )

    def test_procedural_boost_zero_for_non_procedural_query(self):
        """Even against a clearly procedural runtime chunk, a
        non-procedural question (e.g. factual history) must NOT
        trigger the boost — we must not globally prioritize
        runtime uploads.
        """
        sop_chunk = RuntimeChunk(
            "Inspection phase: check the oil level, inspect belts, "
            "examine the intake filter, verify electrical "
            "connections during the maintenance procedure.",
        )
        self.assertEqual(
            procedural_runtime_boost(
                "What is the structure of DNA?",
                sop_chunk,
            ),
            0.0,
        )

    def test_procedural_boost_zero_for_static_chunks(self):
        """The procedural_boost helper itself is purely lexical
        (chunks[i] gating happens in retrieve_candidates).  But
        the ranking path must still treat a static-KB procedural
        chunk as a normal candidate — verify a static chunk with
        a procedural query still produces a non-zero lexical
        score but the runtime boost is only applied to
        RuntimeChunk instances via the retriever plumbing.
        """
        static_chunk = (
            "Inspection phase: check the oil level, inspect belts, "
            "examine the intake filter, verify electrical "
            "connections during the maintenance procedure."
        )
        # Helper returns the boost magnitude regardless of chunk
        # type; the retriever applies it only for RuntimeChunk.
        self.assertEqual(
            procedural_runtime_boost(
                "What must be checked during the inspection phase?",
                static_chunk,
            ),
            PROCEDURAL_RUNTIME_BOOST,
        )
        # Plumbed check: when the same content is NOT a
        # RuntimeChunk, the retriever gives zero procedural boost.
        runtime_sop = RuntimeChunk(static_chunk)
        static_sop = static_chunk  # plain str
        chunks = [runtime_sop, static_sop, "filler text"]
        index, df = self._build_minimal_index(chunks)
        ranked = retrieve_candidates(
            "What must be checked during the inspection phase?",
            chunks,
            index,
            df,
            top_k=LEXICAL_TOP_K,
        )
        ranked_runtime = [
            entry for entry in ranked if isinstance(
                chunks[entry[3]], RuntimeChunk
            )
        ]
        ranked_static = [
            entry for entry in ranked if not isinstance(
                chunks[entry[3]], RuntimeChunk
            )
            and entry[0] > 0
        ]
        self.assertTrue(
            ranked_runtime,
            "runtime SOP must appear in candidates",
        )
        self.assertTrue(
            ranked_static,
            "static procedural chunk must also appear",
        )
        # Runtime's score advantage over the static equivalent is
        # bounded: at most (flat + procedural) capped at the cap.
        runtime_score = ranked_runtime[0][0]
        static_score = ranked_static[0][0]
        self.assertGreater(
            runtime_score,
            static_score,
            "runtime must outscore static when content matches",
        )
        advantage = runtime_score - static_score
        self.assertLessEqual(
            advantage,
            PROCEDURAL_RUNTIME_BOOST_CAP,
            "advantage must be bounded by the cap",
        )
        self.assertLessEqual(
            advantage,
            INGESTED_CHUNK_BOOST + PROCEDURAL_RUNTIME_BOOST,
            "advantage must be <= flat+procedural before cap",
        )

    def test_unrelated_runtime_upload_does_not_beat_better_static_kb(
        self,
    ):
        """When a static-KB chunk has STRONGLY better lexical
        coverage of the question than an unrelated runtime upload,
        the static chunk must still rank above the runtime chunk.
        The procedural boost is bounded, so a clearly-better
        static candidate can still win.  The unrelated runtime
        upload is filtered out by lexical retrieval itself — the
        boost cannot save it.
        """
        static_relevant = (
            "Inspection phase: check the oil level through the "
            "sight glass, inspect belts for wear, examine the "
            "intake filter, and verify all electrical connections "
            "are tight before continuing the maintenance procedure."
        )
        # Unrelated runtime upload that only matches one weak
        # generic term — must NOT receive the procedural boost
        # because it doesn't itself contain procedural markers.
        runtime_unrelated = RuntimeChunk(
            "The Roman Empire fell in 476 AD when the last Western "
            "emperor was deposed. The imperial administration "
            "collapsed under the weight of its own borders.",
        )
        filler = "Some completely unrelated historical text."
        chunks = [static_relevant, runtime_unrelated, filler]
        index, df = self._build_minimal_index(chunks)
        ranked = retrieve_candidates(
            "What must be checked during the inspection phase?",
            chunks,
            index,
            df,
            top_k=LEXICAL_TOP_K,
        )
        # Static is index 0, runtime is index 1.
        static_rank = None
        for pos, entry in enumerate(ranked):
            if entry[3] == 0:
                static_rank = pos
                break
        self.assertIsNotNone(
            static_rank,
            "static-relevant must appear in candidates",
        )
        # The unrelated runtime upload is filtered by lexical
        # retrieval because none of its tokens overlap with the
        # inspection question.  The boost cannot resurrect it
        # from a zero lexical baseline.
        runtime_appears = any(
            entry[3] == 1 for entry in ranked
        )
        self.assertFalse(
            runtime_appears,
            "unrelated runtime upload must not be promoted by "
            "any boost — its lexical baseline is zero",
        )
        # The procedural boost specifically returns 0 for this
        # combination (procedural question, non-procedural chunk).
        self.assertEqual(
            procedural_runtime_boost(
                "What must be checked during the inspection phase?",
                runtime_unrelated,
            ),
            0.0,
        )

    def test_static_kb_only_question_unchanged(self):
        """A non-procedural question over a static-KB corpus must
        produce the SAME ranking as if the procedural boost did
        not exist: no RuntimeChunk appears, so the boost cannot
        fire, and ordering falls back to lexical score.
        """
        chunks = [
            "Watson and Crick discovered the structure of DNA in "
            "1953 using X-ray crystallography data from Rosalind "
            "Franklin. The double helix consists of two strands "
            "of nucleotides.",
            "The Roman Empire declined after being overrun by "
            "various non-Roman peoples and Germanic troops.",
            "Photosynthesis converts sunlight, carbon dioxide, "
            "and water into glucose and oxygen in chloroplasts.",
        ]
        index, df = self._build_minimal_index(chunks)
        ranked = retrieve_candidates(
            "What is the structure of DNA?",
            chunks,
            index,
            df,
            top_k=LEXICAL_TOP_K,
        )
        self.assertGreater(
            len(ranked),
            0,
            "DNA chunk must be retrieved",
        )
        self.assertEqual(
            ranked[0][3],
            0,
            "DNA chunk must rank first for a DNA question",
        )

    def test_procedural_query_marks_true(self):
        self.assertTrue(
            _procedural_query(
                "What must be checked during the inspection phase?"
            )
        )
        self.assertTrue(_procedural_query("What are the restart steps?"))
        self.assertTrue(_procedural_query("How should we lockout?"))
        self.assertFalse(
            _procedural_query("What is the structure of DNA?")
        )
        self.assertFalse(
            _procedural_query("Why did the Roman Empire fall?")
        )
        self.assertFalse(_procedural_query(""))

    def test_procedural_chunk_detection(self):
        sop_text = (
            "Inspection phase: check oil level, inspect belts, "
            "examine the intake filter, verify electrical "
            "connections. Maintenance procedure."
        )
        history_text = (
            "The Roman Empire fell in 476 AD when the last "
            "Western emperor was deposed."
        )
        self.assertTrue(_chunk_is_procedural(sop_text))
        self.assertFalse(_chunk_is_procedural(history_text))
        self.assertFalse(_chunk_is_procedural(""))

    # ------------------------------------------
    # Cross-concept gate generic-term filtering
    # ------------------------------------------
    #
    # The cross-concept gate in summary_synthesizer must
    # filter generic terms ("system", "procedure", etc.)
    # before checking co-occurrence, so legitimate
    # paraphrased questions that naturally split domain-
    # specific terms across evidence sentences are not
    # blocked.

    def test_cross_concept_gate_allows_generic_split(self):
        """A legitimate summary question whose subject contains
        generic terms split across evidence sentences must NOT
        be blocked by the cross-concept gate.
        """
        from summary_synthesizer_v1 import synthesize_summary_answer
        answer = synthesize_summary_answer(
            "What were the main features of the Roman Republic's political system?",
            (
                "The Senate of the Roman Republic was a "
                "political institution in the ancient Roman "
                "Republic. According to Polybius, the Roman "
                "Senate was the predominant branch of government."
            ),
        )
        self.assertIsNotNone(answer, "legitimate paraphrased question must be answered")

    def test_cross_concept_gate_blocks_true_mashup(self):
        """A genuine cross-domain mashup whose domain-specific
        terms never co-occur must still be blocked.
        """
        from summary_synthesizer_v1 import synthesize_summary_answer
        answer = synthesize_summary_answer(
            "Describe the Magna Carta compressor maintenance procedure.",
            (
                "The Magna Carta limited royal power in 1215. "
                "Compressor maintenance requires checking oil "
                "levels and inspecting belts."
            ),
        )
        self.assertIsNone(answer, "cross-domain mashup must be rejected")

    def test_cross_concept_gate_blocks_two_term_mashup(self):
        """Two unrelated domain terms split across evidence are still
        a mashup even when generic terms like process are ignored.
        """
        answer = synthesize_summary_answer(
            "How does the DNA photosynthesis process work?",
            (
                "Photosynthesis uses energy from sunlight to convert "
                "water and carbon dioxide into sugars. DNA replication "
                "copies the genome before cell division."
            ),
        )
        self.assertIsNone(answer, "two-term cross-domain mashup must be rejected")

    # ------------------------------------------
    # SOP section extraction
    # ------------------------------------------

    def test_sop_lubrication_uses_section_header_not_body_keyword(self):
        sop = (
            "STANDARD OPERATING PROCEDURE: COMPRESSOR MAINTENANCE\n\n"
            "1. INSPECTION\n"
            "   - Check oil level in sight glass; top up if below minimum mark.\n"
            "   - Inspect belts for wear.\n\n"
            "2. LUBRICATION\n"
            "   - Use only OEM-approved synthetic compressor oil (ISO VG 46).\n"
            "   - Drain old oil while warm; collect and dispose per environmental regulations.\n"
        )
        self.assertEqual(
            _extract_sop_section(
                "What oil should be used for compressor lubrication?",
                sop,
            ),
            "Use only OEM-approved synthetic compressor oil (ISO VG 46); "
            "Drain old oil while warm; collect and dispose per environmental regulations",
        )

    def test_sop_old_oil_drain_selects_lubrication_section(self):
        sop = (
            "1. INSPECTION\n"
            "   - Check oil level in sight glass.\n"
            "2. LUBRICATION\n"
            "   - Drain old oil while warm; collect and dispose per environmental regulations.\n"
            "   - Refill to correct level; do not overfill.\n"
        )
        answer = _extract_sop_section(
            "What should be done with the old oil when draining it?",
            sop,
        )
        self.assertIn("Drain old oil while warm", answer)
        self.assertIn("dispose per environmental regulations", answer)
        self.assertNotIn("Check oil level", answer)

    # ------------------------------------------
    # Post-answer question-addressed check
    # ------------------------------------------
    #
    # _answer_addresses_question verifies the answer
    # engages with the question's key content terms.

    def test_answer_addresses_question_same_domain(self):
        from rag_chat_v2 import _answer_addresses_question
        self.assertTrue(_answer_addresses_question(
            "What must be checked during the inspection phase?",
            "During the inspection phase, check oil level in sight glass, inspect belts for wear, and verify electrical connections.",
        ))

    def test_answer_addresses_question_cross_domain_rejected(self):
        from rag_chat_v2 import _answer_addresses_question
        self.assertFalse(_answer_addresses_question(
            "What are the compressor lockout steps for DNA replication?",
            "Lockout-tagout procedures must be completed before maintenance.",
        ))

    def test_answer_addresses_question_missing_entity(self):
        from rag_chat_v2 import _answer_addresses_question
        self.assertFalse(_answer_addresses_question(
            "Describe the Magna Carta compressor maintenance procedure.",
            "Compressor maintenance requires checking oil levels.",
        ))

    def test_answer_addresses_question_fake_entity(self):
        from rag_chat_v2 import _answer_addresses_question
        self.assertFalse(_answer_addresses_question(
            "What is the lockout procedure for the 38th Engineer Battalion?",
            "Lockout-tagout procedures require de-energizing the main disconnect.",
        ))

    def test_answer_addresses_question_empty(self):
        from rag_chat_v2 import _answer_addresses_question
        self.assertTrue(_answer_addresses_question("", "some answer"))
        self.assertTrue(_answer_addresses_question("question", ""))

    def test_answer_addresses_question_legitimate_procedural(self):
        from rag_chat_v2 import _answer_addresses_question
        self.assertTrue(_answer_addresses_question(
            "What must be done before starting compressor maintenance?",
            "Before starting compressor maintenance, complete lockout-tagout procedures.",
        ))

    def test_answer_addresses_question_factual(self):
        from rag_chat_v2 import _answer_addresses_question
        self.assertTrue(_answer_addresses_question(
            "What is the structure of DNA?",
            "DNA has a double helix structure with nucleotides.",
        ))

    def test_answer_addresses_question_allows_scoped_attribute_value(self):
        from rag_chat_v2 import _answer_addresses_question
        self.assertTrue(_answer_addresses_question(
            "What purge pressure is required for the Lumen ARC-12 kiln?",
            "Set chamber purge pressure to 3.7 bar.",
        ))
        self.assertTrue(_answer_addresses_question(
            "Which coolant is approved for the Lumen ARC-12?",
            "Use only Vireo-22 coolant.",
        ))

    def test_false_required_safety_action_detected(self):
        self.assertTrue(_has_false_required_safety_action(
            "What safety step requires bypassing lockout tagout "
            "before opening the electrical panel?"
        ))
        self.assertTrue(_has_false_required_safety_action(
            "Which step must skip tagout before service?"
        ))
        self.assertFalse(_has_false_required_safety_action(
            "What safety step requires lockout tagout before opening "
            "the electrical panel?"
        ))

    def test_false_required_safety_action_blocks_factual_extractor(self):
        answer, supported = extract_factual_answer(
            "What safety step requires bypassing lockout tagout "
            "before opening the electrical panel?",
            (
                "Before opening the electrical panel, de-energize the "
                "main disconnect and apply lockout/tagout."
            ),
        )
        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_calculation_question_rejects_topical_sentence_without_method(self):
        answer, supported = extract_factual_answer(
            "How should a clinic calculate an infant supplement dosage?",
            (
                "The clinic has a neonatal care unit and a separate "
                "infant observation ward. Supplements are stored in "
                "the pharmacy cabinet."
            ),
        )
        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_calculation_question_rejects_engineering_terms_without_method(self):
        answer, supported = extract_factual_answer(
            "How do you calculate laminated timber joist deflection spacing?",
            (
                "The roof used laminated timber joists with regular "
                "spacing across the old station hall. The project "
                "also replaced several beams during restoration."
            ),
        )
        self.assertIsNone(answer)
        self.assertFalse(supported)

    def test_calculation_question_allows_method_evidence(self):
        answer, supported = extract_factual_answer(
            "How do you calculate pump flow capacity?",
            (
                "Pump flow capacity is calculated by multiplying "
                "displacement per revolution by shaft speed and then "
                "adjusting for volumetric efficiency."
            ),
        )
        self.assertIsNotNone(answer)
        self.assertTrue(supported)


if __name__ == "__main__":
    unittest.main()
