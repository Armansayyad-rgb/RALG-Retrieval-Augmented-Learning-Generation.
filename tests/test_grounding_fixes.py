import pytest
from src.rag_chat_v2 import answer_question, _predicate_answers_question
from src.webui.chat_handler import build_answer_contract, _subject_predicate_grounded
from src.runtime_architecture import execute_runtime, unified_support_gate
from src.retriever_v2 import RuntimeChunk

# Mock pipeline for grounding tests
def create_mock_pipeline(text):
    return {
        "chunks": [RuntimeChunk(text=text, metadata={"document_id": "test_doc"})],
        "retrieval_index": {},
        "document_frequency": {},
    }

class TestDefinitionalSupport:
    def test_definition_positive(self):
        # a real definition should be supported
        question = "What is the Zephra Control Matrix?"
        evidence = "The Zephra Control Matrix is a distributed safety controller."
        # Test via _predicate_answers_question as it's the primary gate
        assert _predicate_answers_question(question, evidence, "") is True

    def test_definition_title_negative(self):
        # a title mentioning the entity should NOT be a supported definition
        question = "What is the Zephra Control Matrix?"
        evidence = "Zephra Control Matrix — Technical Market Analysis"
        assert _predicate_answers_question(question, evidence, "") is False

    def test_definition_mention_negative(self):
        # a sentence merely mentioning the entity should NOT be a supported definition
        question = "What is the Zephra Control Matrix?"
        evidence = "The Zephra Control Matrix was reviewed on Friday."
        assert _predicate_answers_question(question, evidence, "") is False

    def test_definition_partial_token_negative(self):
        # matching just a common term like "matrix" should NOT satisfy the definition
        question = "What is the Zephra Control Matrix?"
        evidence = "A matrix is a rectangular array of values."
        assert _predicate_answers_question(question, evidence, "") is False

    def test_definition_alias_positive(self):
        # "git rebase" should be supported if "rebase" is defined
        question = "What is git rebase?"
        evidence = "rebase rewrites the commit history by replaying commits on top of a different base"
        assert _predicate_answers_question(question, evidence, "") is True

class TestAttributeGrounding:
    def test_attribute_positive(self):
        # Correct subject/predicate binding
        question = "What is the lubricant in the NX-77 gearbox?"
        evidence = "The NX-77 gearbox lubricant is synthetic grade LQ-9."
        sources = [{"evidence": evidence, "score": 1.0}]
        # Factual answer type, extractor route, general intent
        assert _subject_predicate_grounded(question, sources, "factual", "extractor", "general") is True

    def test_attribute_wrong_entity(self):
        # Right attribute, wrong entity
        question = "What is the lubricant in the NX-77 gearbox?"
        evidence = "The NX-88 gearbox lubricant is synthetic grade LQ-9."
        sources = [{"evidence": evidence, "score": 1.0}]
        assert _subject_predicate_grounded(question, sources, "factual", "extractor", "general") is False

    def test_attribute_absent_attribute(self):
        # Right entity, wrong attribute
        question = "What is the lubricant in the NX-77 gearbox?"
        evidence = "The NX-77 gearbox is made of steel."
        sources = [{"evidence": evidence, "score": 1.0}]
        assert _subject_predicate_grounded(question, sources, "factual", "extractor", "general") is False

class TestFalseConflict:
    def test_no_false_conflict(self):
        # Grounding failure should NOT produce CONFLICT_RESPONSE if no contradictory evidence exists
        question = "What is the lubricant in the NX-77 gearbox?"
        # Evidence that doesn't ground the relationship
        evidence = "The NX-77 gearbox is made of steel."
        sources = [{"evidence": evidence, "score": 1.0}]

        # Mock result from answer_question
        result = {
            "answer": "The lubricant is unknown.",
            "supported": True,
            "answer_type": "factual",
            "evidence": [{"chunk": evidence, "final_score": 1.0, "chunk_index": 0}],
            "runtime_plan": {"route": "extractor", "intent": "general"}
        }

        pipeline = create_mock_pipeline(evidence)
        contract = build_answer_contract(pipeline, question, result, top_k=5)

        assert contract.conflict is False
        assert contract.answer != "I found conflicting evidence in the retrieved sources and cannot state a single settled answer."

    def test_genuine_conflict_preserved(self):
        # Genuine conflict should still be detected
        question = "What is the lubricant in the NX-77 gearbox?"
        # Two contradictory values
        evidence_left = "The NX-77 gearbox lubricant is grade A."
        evidence_right = "The NX-77 gearbox lubricant is grade B."
        sources = [
            {"evidence": evidence_left, "score": 1.0},
            {"evidence": evidence_right, "score": 1.0},
        ]

        # We can't easily mock detect_evidence_conflict as it's called inside build_answer_contract.
        # Instead we use a real pipeline and real contradictory evidence.
        # Note: build_answer_contract uses detect_evidence_conflict.

        # To trigger detect_evidence_conflict, we need the evidence to be recognized as conflicting.
        #- numeric conflict: "10 PSI" vs "20 PSI"
        #- identifier conflict: "ID-1" vs "ID-2"
        #- directive conflict: "Must open" vs "Must close"

        # Let's use numeric conflict.
        evidence_left = "The NX-77 gearbox pressure is 10 PSI."
        evidence_right = "The NX-77 gearbox pressure is 20 PSI."
        sources = [
            {"evidence": evidence_left, "score": 1.0},
            {"evidence": evidence_right, "score": 1.0},
        ]

        # Use a result that is supported
        result = {
            "answer": "The pressure is 10 PSI.",
            "supported": True,
            "answer_type": "factual",
            "evidence": [{"chunk": evidence_left, "final_score": 1.0, "chunk_index": 0}, {"chunk": evidence_right, "final_score": 1.0, "chunk_index": 1}],
            "runtime_plan": {"route": "extractor", "intent": "general"}
        }

        pipeline = create_mock_pipeline(evidence_left + " " + evidence_right)
        contract = build_answer_contract(pipeline, "What is the pressure in the NX-77 gearbox?", result, top_k=5)

        assert contract.conflict is True
        assert contract.answer == "I found conflicting evidence in the retrieved sources and cannot state a single settled answer."


class TestUnifiedSupportGateContractRejection:
    """Test that unified_support_gate respects contract.supported = False."""

    def test_contract_unsupported_rejects_even_if_raw_supported(self):
        """
        raw.supported = True
        contract.supported = False (e.g., grounding failure)
        => final supported MUST be False
        => reasons must include "contract_unsupported"
        """
        from src.runtime_architecture import ExecutionResult

        # Minimal contract-like object with supported=False
        class MockContract:
            def __init__(self):
                self.supported = False
                self.evidence = [{"chunk": "some evidence", "final_score": 1.0}]
                self.sources = [{"chunk": "some evidence", "score": 1.0}]
                self.traceable = True
                self.conflict = False
                self.provenance = [{"document_id": "test"}]

        raw = {"supported": True}
        contract = MockContract()

        gate_passed, reasons = unified_support_gate(raw, contract)

        assert gate_passed is False
        assert "contract_unsupported" in reasons
        assert "raw_unsupported" not in reasons  # raw was supported

    def test_contract_supported_does_not_cause_rejection(self):
        """
        raw.supported = True
        contract.supported = True
        with all other gate requirements satisfied
        => contract support itself must not cause rejection
        """
        class MockContract:
            def __init__(self):
                self.supported = True
                self.evidence = [{"chunk": "some evidence", "final_score": 1.0}]
                self.sources = [{"chunk": "some evidence", "score": 1.0}]
                self.traceable = True
                self.conflict = False
                self.provenance = [{"document_id": "test"}]

        raw = {"supported": True}
        contract = MockContract()

        gate_passed, reasons = unified_support_gate(raw, contract)

        assert gate_passed is True
        assert "contract_unsupported" not in reasons
        assert "raw_unsupported" not in reasons
