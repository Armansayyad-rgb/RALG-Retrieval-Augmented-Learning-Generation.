"""Tests for WebUI document scoping handoff.

Verifies that the scope selector value is correctly threaded from
the Gradio UI layer into the chat pipeline.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

SRC = str(Path(__file__).resolve().parent)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from webui.app import respond, _document_choices  # noqa: E402
from webui.hybrid_pipeline import HybridTurn  # noqa: E402


def _make_turn(answer="test answer", **kwargs):
    return HybridTurn(
        question="test",
        answer=answer,
        mode=kwargs.get("mode", "rag_only"),
        intent=kwargs.get("intent", "general"),
        answer_type=kwargs.get("answer_type", "summary"),
        confidence=kwargs.get("confidence", 0.8),
        supported=kwargs.get("supported", True),
        sources=kwargs.get("sources", []),
        error=kwargs.get("error"),
    )


class TestDocumentChoices(unittest.TestCase):
    """_document_choices builds a list of document_id strings."""

    def test_empty_docs(self):
        self.assertEqual(_document_choices([]), [])

    def test_with_docs(self):
        docs = [
            {"document_id": "aaa", "document_name": "a.txt"},
            {"document_id": "bbb", "document_name": "b.txt"},
        ]
        self.assertEqual(_document_choices(docs), ["aaa", "bbb"])

    def test_skips_missing_id(self):
        docs = [
            {"document_id": "aaa", "document_name": "a.txt"},
            {"document_name": "no-id.txt"},
        ]
        self.assertEqual(_document_choices(docs), ["aaa"])


class TestRespondScopeHandoff(unittest.TestCase):
    """respond() passes document_ids to route_through_hybrid correctly."""

    @patch("webui.app.route_through_hybrid")
    def test_scope_none_passes_none(self, mock_route):
        mock_route.return_value = _make_turn()
        respond("hello", [], 5, 0.5, {}, None, scope_document_id=None)
        call_kwargs = mock_route.call_args
        self.assertIsNone(call_kwargs.kwargs.get("document_ids"))

    @patch("webui.app.route_through_hybrid")
    def test_scope_selected_passes_list(self, mock_route):
        mock_route.return_value = _make_turn()
        respond("hello", [], 5, 0.5, {}, None, scope_document_id="doc-123")
        call_kwargs = mock_route.call_args
        self.assertEqual(call_kwargs.kwargs.get("document_ids"), ["doc-123"])

    @patch("webui.app.route_through_hybrid")
    def test_scope_empty_string_passes_none(self, mock_route):
        mock_route.return_value = _make_turn()
        respond("hello", [], 5, 0.5, {}, None, scope_document_id="")
        call_kwargs = mock_route.call_args
        self.assertIsNone(call_kwargs.kwargs.get("document_ids"))

    @patch("webui.app.route_through_hybrid")
    def test_scope_all_documents_passes_none(self, mock_route):
        mock_route.return_value = _make_turn()
        respond("hello", [], 5, 0.5, {}, None, scope_document_id="All documents")
        call_kwargs = mock_route.call_args
        self.assertIsNone(call_kwargs.kwargs.get("document_ids"))


if __name__ == "__main__":
    unittest.main()
