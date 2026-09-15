from unittest.mock import patch

import pytest
from config import TOKENIZER_FILE
from runtime_architecture import execute_runtime
from tokenizers import Tokenizer
import rag_chat_v2 as rag
from retriever_v2 import RuntimeChunk, build_index
from webui.chat_handler import build_answer_contract, collect_sources
from webui.chat_handler import detect_evidence_conflict


def run_production(question, passages):
    chunks = [RuntimeChunk(text, metadata={"document_id": "fictional", "chunk_index": i}) for i, text in enumerate(passages)]
    index, frequency = build_index(chunks)
    pipeline = {"device": "cpu", "model": None, "tokenizer": Tokenizer.from_file(str(TOKENIZER_FILE)), "chunks": chunks, "retrieval_index": index, "document_frequency": frequency}
    return execute_runtime(pipeline, question, answer_fn=rag.answer_question, contract_fn=build_answer_contract, sources_fn=collect_sources)


def test_broad_explanation_uses_production_synthesis():
    question = "what is the research in Zerion explain it to me in detail"
    passages = [
        "Research in Zerion investigates crystal stability through repeated thermal trials.",
        "Research in Zerion compares acoustic measurements with optical measurements to detect crystal defects.",
    ]
    with patch.object(rag, "synthesize_summary_answer", wraps=rag.synthesize_summary_answer) as synthesis:
        result = run_production(question, passages)
    assert synthesis.called
    assert synthesis.call_args.args[0] == "Explain the research in Zerion."
    assert result.supported, result.observability
    assert result.traceable
    assert "crystal" in result.answer.lower()
    assert "detail" not in result.plan.subject.lower()


@pytest.mark.parametrize("question", [
    "what is the research in Zerion explain in detail",
    "what is the research in Zerion explain it in detail",
    "tell me about the research in Zerion",
    "describe in detail the research in Zerion",
])
def test_presentation_phrasing_does_not_become_subject_anchor(question):
    result = run_production(question, ["Research in Zerion investigates crystal stability through thermal trials."])
    assert "detail" not in result.plan.subject.lower()
    assert result.supported


def test_unsupported_broad_explanation_abstains():
    result = run_production("what is the research in Zerion explain it to me in detail", ["Velora manufactures wooden furniture."])
    assert not result.supported


def test_misleading_overlap_abstains():
    result = run_production("what is the research in Zerion explain it to me in detail", ["Zerion sells furniture to laboratories.", "Research in Velora investigates crystal stability."])
    assert not result.supported


@pytest.mark.parametrize("question,passage", [
    ("What is the Zephra Control Matrix?", "Zephra Control Matrix — Technical Market Analysis"),
    ("What is the lubricant in the NX-77 gearbox?", "The NX-88 gearbox lubricant is synthetic grade LQ-9."),
])
def test_existing_definition_and_wrong_entity_negatives(question, passage):
    assert not run_production(question, [passage]).supported


def test_contract_supported_gate_remains_authoritative():
    result = run_production("what is the research in Zerion explain it to me in detail", ["Research in Zerion investigates crystal stability through thermal trials."])
    assert result.supported
    assert result.observability["support_gate"]


def test_identical_evidence_does_not_conflict():
    text = "The RALG research report was published in 2026."
    sources = [{"evidence": text, "score": 1.0}, {"evidence": text, "score": 1.0}]
    assert not detect_evidence_conflict("what is the research in RALG", sources)


def test_research_reference_identifiers_do_not_conflict():
    sources = [
        {"evidence": "SURE-RAG evaluates evidence sufficiency for grounded generation.", "score": 1.0},
        {"evidence": "Patent US20240346256A1 describes retrieval augmented generation using a model.", "score": 1.0},
    ]
    assert not detect_evidence_conflict("what is the research in RALG", sources)


def test_competing_serial_identifiers_conflict():
    sources = [
        {"evidence": "The ZX-4 controller serial number is SN-A17.", "score": 1.0},
        {"evidence": "The ZX-4 controller serial number is SN-B92.", "score": 1.0},
    ]
    assert detect_evidence_conflict("what is the serial number of the ZX-4 controller", sources)


def test_competing_numeric_values_conflict():
    sources = [
        {"evidence": "The ZX-4 controller pressure is 10 PSI.", "score": 1.0},
        {"evidence": "The ZX-4 controller pressure is 20 PSI.", "score": 1.0},
    ]
    assert detect_evidence_conflict("what is the pressure of the ZX-4 controller", sources)


def test_unrelated_numeric_values_do_not_conflict():
    sources = [
        {"evidence": "The ZX-4 controller pressure is 10 PSI and was tested in 2026.", "score": 1.0},
        {"evidence": "The ZX-4 controller has 20 maintenance records.", "score": 1.0},
    ]
    assert not detect_evidence_conflict("what is the research on the ZX-4 controller", sources)
