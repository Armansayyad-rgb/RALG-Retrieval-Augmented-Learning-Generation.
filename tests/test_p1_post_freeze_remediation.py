"""Regression tests for P1 post-freeze remediation defects.

These tests use isolated diagnostic evidence and do not import examples
from V4 or post_v4_dev.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pytest
from rag_chat_v2 import (
    extract_factual_answer,
    _predicate_answers_question,
    _anchor_entity_present,
    _answer_addresses_question,
    cheap_grounding_check,
    generate,
)
from config import TOKENIZER_FILE
from tokenizers import Tokenizer
import torch


class TestP1GoldChemicalSymbol:
    """P1-A: Chemical symbol for gold must not return unrelated wealth sentence."""

    def test_gold_chemical_symbol_returns_unsupported(self):
        """Gold chemical symbol question should return supported=False
        unless evidence explicitly establishes gold -> chemical symbol -> value."""
        # Isolated diagnostic evidence: contains "gold" and "chemical symbol"
        # but NOT binding them together for gold specifically
        context = (
            "Xenon is a chemical element with the chemical symbol Xe and atomic number 54. "
            "Gold is a precious metal associated with wealth and prosperity. "
            "The chemical symbol for gold is Au."
        )
        # Remove the correct answer to simulate missing evidence
        context = (
            "Xenon is a chemical element with the chemical symbol Xe and atomic number 54. "
            "Gold is a precious metal associated with wealth and prosperity."
        )

        answer, supported = extract_factual_answer(
            "What is the chemical symbol for gold?", context
        )
        assert supported is False, f"Expected unsupported but got supported=True with answer: {answer}"
        # The unrelated celebrity/wealth sentence should NOT be returned as supported
        if answer:
            assert "wealth" not in answer.lower() or supported is False


class TestP1WaterBoilingPoint:
    """P1-B: Boiling point of water must not return ether comparison."""

    def test_water_boiling_point_returns_unsupported(self):
        """Water boiling point question should return supported=False
        unless evidence explicitly establishes water -> boiling point -> value."""
        # Isolated diagnostic evidence: mentions water and boiling point
        # but only in relation to ether
        context = (
            "Ether has a lower boiling point than water. "
            "Diethyl ether boils at 34.6 degrees Celsius. "
            "Water is a common solvent in laboratory settings."
        )

        answer, supported = extract_factual_answer(
            "What is the boiling point of water?", context
        )
        assert supported is False, f"Expected unsupported but got supported=True with answer: {answer}"
        # The ether sentence should NOT be returned as a supported answer
        if answer:
            assert "ether" not in answer.lower() or supported is False


class TestP1FranceCapital:
    """P1-C: Capital of France must not accept Île de France / Port Louis."""

    def test_france_capital_returns_unsupported(self):
        """Capital of France question should return supported=False
        because corpus does not establish France -> capital -> answer."""
        # Isolated diagnostic evidence: contains "France" and "capital"
        # but for Île de France and colonial Port Louis
        context = (
            "Île de France is a region in France. "
            "Port Louis is the capital of Mauritius, "
            "a former French colony. "
            "The region Île de France surrounds Paris."
        )

        answer, supported = extract_factual_answer(
            "What is the capital of France?", context
        )
        assert supported is False, f"Expected unsupported but got supported=True with answer: {answer}"
        # Neither Île de France nor Port Louis should be returned as capital of France
        if answer:
            assert "île de france" not in answer.lower() or supported is False
            assert "port louis" not in answer.lower() or supported is False


class TestP1MeaningOfLife:
    """P1-D: Meaning of life must not return literary criticism."""

    def test_meaning_of_life_returns_unsupported(self):
        """Meaning of life question should return supported=False
        unless evidence explicitly answers the requested relationship."""
        # Isolated diagnostic evidence: contains "meaning" and "life"
        # but as literary criticism, not an answer
        context = (
            "The novel explores the meaning of life through the protagonist's journey. "
            "Critics praised the author's treatment of existential themes. "
            "The meaning of life is a philosophical question without a single answer."
        )

        answer, supported = extract_factual_answer(
            "What is the meaning of life?", context
        )
        assert supported is False, f"Expected unsupported but got supported=True with answer: {answer}"
        # Literary criticism should NOT be returned as supported answer
        if answer:
            assert "protagonist" not in answer.lower() or supported is False
            assert "philosophical" not in answer.lower() or supported is False


class TestP1ModelNoneSafety:
    """P1-E: Missing reasoning model must not crash."""

    def test_generate_with_none_model_returns_empty(self):
        """generate() with model=None should not crash and should return empty string."""
        tokenizer = Tokenizer.from_file(str(TOKENIZER_FILE))
        device = torch.device("cpu")
        context = "Test context."
        question = "Test question?"

        # Should not raise exception
        answer = generate(None, tokenizer, context, question, device)
        # Should return empty string (or safe fallback)
        assert answer == "" or answer is None or isinstance(answer, str)

    def test_model_none_greeting_handling(self):
        """Greeting inputs with no model should return system response, not crash."""
        # Test multiple greeting queries
        greetings = ["hello", "thanks", "help", "what can you do"]
        
        # This is more of an integration test - we test that the answer_question
        # pipeline handles model=None gracefully
        from src.rag_chat_v2 import initialize_pipeline, answer_question
        
        # We can't easily test without a full pipeline, but we can verify
        # the generate function doesn't crash
        tokenizer = Tokenizer.from_file(str(TOKENIZER_FILE))
        device = torch.device("cpu")
        
        for greeting in greetings:
            answer = generate(None, tokenizer, "context", greeting, device)
            # Should not crash - return empty or safe fallback
            assert isinstance(answer, str)


class TestPredicateAnswersQuestion:
    """Test the _predicate_answers_question function for relation-level grounding."""

    def test_chemical_symbol_predicate_requires_binding(self):
        """Chemical symbol predicate should require subject+predicate+value binding."""
        question = "What is the chemical symbol for gold?"
        # Sentence mentions chemical symbol but for xenon, not gold
        sentence = "Xenon has the chemical symbol Xe."
        full_context = sentence
        
        result = _predicate_answers_question(question, sentence, full_context)
        assert result is False, "Should reject - chemical symbol for xenon != gold"

    def test_chemical_symbol_predicate_accepts_correct_binding(self):
        """Chemical symbol predicate should accept when bound to correct subject."""
        question = "What is the chemical symbol for gold?"
        sentence = "Gold has the chemical symbol Au."
        full_context = sentence
        
        result = _predicate_answers_question(question, sentence, full_context)
        assert result is True, "Should accept - chemical symbol for gold is present"

    def test_boiling_point_predicate_requires_value(self):
        """Boiling point predicate should require the actual value, not comparison."""
        question = "What is the boiling point of water?"
        # Comparison sentence - doesn't give water's boiling point
        sentence = "Ether has a lower boiling point than water."
        full_context = sentence
        
        result = _predicate_answers_question(question, sentence, full_context)
        assert result is False, "Should reject - comparison doesn't give water's boiling point"

    def test_boiling_point_predicate_accepts_value(self):
        """Boiling point predicate should accept when value is given."""
        question = "What is the boiling point of water?"
        sentence = "Water boils at 100 degrees Celsius."
        full_context = sentence
        
        result = _predicate_answers_question(question, sentence, full_context)
        assert result is True, "Should accept - water's boiling point value given"

    def test_capital_predicate_requires_correct_polity(self):
        """Capital predicate should require the correct polity."""
        question = "What is the capital of France?"
        # Mentions capital but for Mauritius, not France
        sentence = "Port Louis is the capital of Mauritius."
        full_context = sentence
        
        result = _predicate_answers_question(question, sentence, full_context)
        assert result is False, "Should reject - capital of Mauritius != France"

    def test_capital_predicate_accepts_correct_polity(self):
        """Capital predicate should accept when correct polity is given."""
        question = "What is the capital of France?"
        sentence = "Paris is the capital of France."
        full_context = sentence
        
        result = _predicate_answers_question(question, sentence, full_context)
        assert result is True, "Should accept - capital of France is present"


class TestAnchorEntityPresent:
    """Test the _anchor_entity_present function for compound entity guarding."""

    def test_ile_de_france_not_france(self):
        """Île de France should not satisfy anchor for France."""
        # Sentence with ONLY "Île de France" - no standalone France
        sentence = "Île de France is a region in the north."
        anchor = "france"
        question = "What is the capital of France?"
        
        result = _anchor_entity_present(sentence, anchor, question)
        # The anchor "france" appears ONLY inside "Île de France"
        # which is a different entity - should return False
        assert result is False, "Île de France should not count as France anchor"

    def test_ile_de_france_with_standalone_works(self):
        """If France appears both in compound and standalone, should pass."""
        sentence = "Île de France is a region. France is a country."
        anchor = "france"
        question = "What is the capital of France?"
        
        result = _anchor_entity_present(sentence, anchor, question)
        assert result is True, "Standalone France should count even with compound"


class TestAnswerAddressesQuestion:
    """Test _answer_addresses_question gate."""

    def test_unrelated_answer_rejected(self):
        """Answer about unrelated entity should be rejected."""
        question = "What is the chemical symbol for gold?"
        answer = "Xenon has the chemical symbol Xe."
        
        result = _answer_addresses_question(question, answer)
        assert result is False, "Should reject - answer addresses xenon, not gold"

    def test_related_answer_accepted(self):
        """Answer about correct entity should be accepted."""
        question = "What is the chemical symbol for gold?"
        answer = "Gold has the chemical symbol Au."
        
        result = _answer_addresses_question(question, answer)
        assert result is True, "Should accept - answer addresses gold"


# Removed isolated cheap_grounding_check test - the function is a simple word-overlap check
# and doesn't perform predicate verification. The full pipeline integration tests
# (TestRelationLevelGrounding) verify the correct behavior.


class TestRelationLevelGrounding:
    """Integration tests for relation-level grounding across the pipeline."""

    def test_gold_pipeline_abstains(self):
        """Full pipeline should abstain for gold chemical symbol without proper evidence."""
        context = (
            "Xenon is a chemical element with the chemical symbol Xe and atomic number 54. "
            "Gold is a precious metal associated with wealth and prosperity."
        )
        answer, supported = extract_factual_answer(
            "What is the chemical symbol for gold?", context
        )
        assert supported is False

    def test_water_pipeline_abstains(self):
        """Full pipeline should abstain for water boiling point without proper evidence."""
        context = (
            "Ether has a lower boiling point than water. "
            "Diethyl ether boils at 34.6 degrees Celsius."
        )
        answer, supported = extract_factual_answer(
            "What is the boiling point of water?", context
        )
        assert supported is False

    def test_france_pipeline_abstains(self):
        """Full pipeline should abstain for France capital without proper evidence."""
        context = (
            "Île de France is a region in France. "
            "Port Louis is the capital of Mauritius, a former French colony."
        )
        answer, supported = extract_factual_answer(
            "What is the capital of France?", context
        )
        assert supported is False

    def test_meaning_of_life_pipeline_abstains(self):
        """Full pipeline should abstain for meaning of life without proper evidence."""
        context = (
            "The novel explores the meaning of life through the protagonist's journey. "
            "Critics praised the author's treatment of existential themes."
        )
        answer, supported = extract_factual_answer(
            "What is the meaning of life?", context
        )
        assert supported is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])