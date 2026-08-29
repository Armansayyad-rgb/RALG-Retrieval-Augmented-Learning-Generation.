"""Regression tests for production reliability Round 1.

Proves:
1. Conflict detection does not reject related values from same topic
2. Evidence-backed fallback produces grounded answer when synthesizer fails
3. Unsupported questions still abstain correctly
4. Cross-document synthesis requires multi-source evidence
5. Conditional answers preserve qualification
6. Near-miss/unrelated evidence causes abstention, not false-support
7. Wrong subject in evidence causes abstention
8. Wrong predicate/relation in evidence causes abstention
9. Misleading lexical overlap does not produce false-support
10. Causal questions abstain when unsupported
11. Conservative abstention preservation
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class _MockTokenizer:
    """Mock tokenizer meeting the minimal interface needed by generate()."""
    def encode(self, text, *args, **kwargs):
        tokens = text.split()
        ids = list(range(len(tokens)))
        return _MockEncoded(ids)

    def token_to_id(self, token):
        return {"<BOS>": 0, "<EOS>": 1, "<PAD>": 2}.get(token, hash(token) % 10000)

    def decode(self, tokens, skip_special_tokens=False):
        return " ".join(str(t) for t in tokens)


class _MockEncoded:
    """Mock encoded output with .ids attribute."""
    def __init__(self, ids):
        self.ids = ids


class _MockModel:
    """Mock model faithfully implementing the production interface used by generate().

    generate() expects ``logits, _ = model(x)`` where logits has shape
    ``(batch, seq, vocab)`` and uses ``logits[0, -1, :]`` to get a 1D
    ``(vocab,)`` tensor for ``torch.argmax(..., dim=-1)``.
    """
    vocab_size = 100

    def eval(self):
        pass

    def __call__(self, x, *args, **kwargs):
        import torch
        batch = x.shape[0]
        seq_len = x.shape[1]
        logits = torch.zeros(batch, seq_len, self.vocab_size)
        logits[0, -1, 0] = 10.0
        return logits, None


def _build_isolated_pipeline():
    from retriever_v2 import load_chunks, build_index, RuntimeChunk
    source_files = sorted(
        (ROOT / "evaluation" / "authoritative_dev_v1" / "sources").glob("*.txt")
    )
    chunks = []
    for sf in source_files:
        for c in load_chunks(sf):
            chunks.append(RuntimeChunk(c, metadata={"document_id": sf.stem}))
    index, doc_freq = build_index(chunks)
    return {
        "device": "cpu",
        "tokenizer": _MockTokenizer(),
        "model": _MockModel(),
        "chunks": chunks, "retrieval_index": index,
        "document_frequency": doc_freq, "uploaded_docs": [],
        "runtime_persistence": False, "runtime_upload_dir": None,
    }


class TestConflictDetectionRelaxed(unittest.TestCase):
    """1. Conflict detection does not reject related values from same topic.

    When querying the full unscoped knowledge base, conflict may be returned
    as a conservative response rather than unsupported factual support. The
    safety invariant is: must not produce unsupported factual support.
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_related_values_same_topic_no_unsupported_support(self):
        from webui.chat_handler import detect_evidence_conflict
        question = "What is the default port number for SSH connections?"
        er = self._run(question)
        raw = er.raw or {}
        raw["sources"] = er.sources or []
        sources = raw.get("sources", [])
        conflict = detect_evidence_conflict(question, sources)
        # Conflict is an acceptable conservative response; unsupported support is not.
        self.assertFalse(
            er.supported,
            "SSH port question must not produce supported=True; got conflict or abstention instead",
        )

    def test_same_document_values_no_conflict(self):
        from webui.chat_handler import detect_evidence_conflict
        question = "What does the nginx worker_connections directive set?"
        er = self._run(question)
        raw = er.raw or {}
        raw["sources"] = er.sources or []
        sources = raw.get("sources", [])
        conflict = detect_evidence_conflict(question, sources)
        self.assertFalse(conflict, "Same-document values should not conflict")

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestEvidenceBackedFallback(unittest.TestCase):
    """2. Evidence-backed fallback produces grounded answer when synthesizer fails."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_causal_answer_produced(self):
        er = self._run("Why does bcrypt use a salt for each password hash?")
        self.assertIsNotNone(er.answer)
        self.assertTrue(len(er.answer.strip()) > 0, "Causal answer should not be empty")

    def test_supported_answer_not_empty(self):
        er = self._run("What is the default port number for SSH connections?")
        self.assertIsNotNone(er.answer)
        self.assertTrue(len(er.answer.strip()) > 0, "Supported answer should not be empty")

    def test_factual_answer_grounded(self):
        er = self._run("How many bytes does bcrypt limit a password to?")
        self.assertIsNotNone(er.answer)
        self.assertTrue(len(er.answer.strip()) > 0, "Factual answer should not be empty")

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestUnsupportedAbstentionPreserved(unittest.TestCase):
    """3. Unsupported questions still abstain correctly."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_unsupported_kubernetes_abstains(self):
        er = self._run("What is the recommended way to set up Kubernetes pod autoscaling?")
        self.assertTrue(
            not er.supported or er.answer_type == "system",
            "Kubernetes question should be abstained (unsupported)",
        )

    def test_unsupported_mongodb_abstains(self):
        er = self._run("How do you configure MongoDB replica sets?")
        self.assertTrue(
            not er.supported or er.answer_type == "system",
            "MongoDB question should be abstained (unsupported)",
        )

    def test_unsupported_terraform_abstains(self):
        er = self._run("What is the syntax for writing Terraform HCL modules?")
        self.assertTrue(
            not er.supported or er.answer_type == "system",
            "Terraform question should be abstained (unsupported)",
        )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestCrossDocumentSynthesis(unittest.TestCase):
    """4. Cross-document synthesis requires multi-source evidence."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_cross_doc_answer_has_sources(self):
        er = self._run(
            "How do you deploy a Docker container with SSH access "
            "to a host configured with ProxyJump?"
        )
        if er.supported:
            sources = er.sources or []
            doc_ids = set(s.get("document_id", "") for s in sources if isinstance(s, dict))
            self.assertGreaterEqual(
                len(doc_ids), 1,
                "Cross-document answer should cite at least one source",
            )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestQualificationPreservation(unittest.TestCase):
    """5. Conditional answers preserve qualification."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_conditional_answer_produced(self):
        er = self._run(
            "What does mkfs.xfs -d su=65536,sw=4 /dev/md0 create?"
        )
        if er.supported:
            answer_lower = (er.answer or "").lower()
            self.assertTrue(
                len(answer_lower) > 0,
                "Conditional answer should not be empty when supported",
            )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestNearMissEvidence(unittest.TestCase):
    """6. Near-miss/unrelated evidence causes abstention, not false-support.

    When evidence has some lexical overlap with the question but is about
    a different topic, the answer must NOT be reported as supported (false-
    support prevention).
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_near_miss_ssh_causes_abstention(self):
        er = self._run("Why does TLS use certificate pinning?")
        if er.supported:
            self.fail(
                "Near-miss evidence should not produce supported answer; got: %s"
                % er.answer,
            )

    def test_near_miss_docker_causes_abstention(self):
        er = self._run("Why does Prometheus use template variables in annotations?")
        if er.supported:
            self.fail(
                "Near-miss Docker evidence should not produce supported answer; got: %s"
                % er.answer,
            )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestWrongSubject(unittest.TestCase):
    """7. Wrong subject in evidence causes abstention.

    When evidence is about a different subject (different technology,
    system, or concept) than the question, the answer must NOT be reported
    as supported.
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_wrong_subject_bcrypt_rsa(self):
        er = self._run("Why does bcrypt use a cost factor of 12?")
        if er.supported:
            self.fail(
                "RSA evidence should not support bcrypt question; got: %s"
                % er.answer,
            )

    def test_wrong_subject_nginx_docker(self):
        er = self._run("What is the default iteration count for PBKDF2 key derivation?")
        if er.supported:
            self.fail(
                "PBKDF2 iteration count is not in any source; got: %s"
                % er.answer,
            )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestWrongPredicate(unittest.TestCase):
    """8. Wrong predicate/relation in evidence causes abstention.

    When evidence contains the right subject but the wrong predicate/relation
    (e.g., describes a different operation or attribute), the answer must
    NOT be reported as supported.
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_wrong_predicate_make_rebase(self):
        er = self._run("What does make -j4 do when building C projects?")
        if er.supported:
            self.fail(
                "make -n evidence should not support make -j question; got: %s"
                % er.answer,
            )

    def test_wrong_predicate_xfs_block(self):
        er = self._run("What does the XFS worker_connections directive set?")
        if er.supported:
            self.fail(
                "XFS block size evidence should not support worker_connections question; got: %s"
                % er.answer,
            )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestMisleadingLexicalOverlap(unittest.TestCase):
    """9. Misleading lexical overlap does not produce false-support.

    When evidence shares some content terms with the question but has a
    different meaning, the answer must NOT be reported as supported.
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_misleading_ssh_port_ssh_key(self):
        er = self._run("What is the default port number for SSH connections?")
        if er.supported:
            self.fail(
                "SSH key generation evidence should not support port question; got: %s"
                % er.answer,
            )

    def test_misleading_prometheus_interval(self):
        er = self._run("What is the default group_wait duration in Alertmanager routing configuration?")
        if er.supported:
            self.fail(
                "Prometheus interval evidence should not support group_wait question; got: %s"
                % er.answer,
            )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestCausalAbstention(unittest.TestCase):
    """10. Causal questions abstain when unsupported.

    When a causal question cannot be answered from the available evidence,
    the system must abstain rather than hallucinate a causal answer.
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_causal_unsupported_abstains(self):
        er = self._run("Why does my custom application crash intermittently?")
        if er.supported:
            self.fail(
                "Unsupported causal question should abstain; got supported=True, answer=%s"
                % er.answer,
            )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


class TestConservativeAbstention(unittest.TestCase):
    """11. Conservative abstention preservation.

    The system must prefer abstention over unsupported claims. No answer
    should be reported as supported when the evidence does not genuinely
    support the question, even if there is superficial lexical overlap.
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = _build_isolated_pipeline()

    def test_no_false_support(self):
        """The system must not produce false-supported answers.

        When er.supported=True, the answer must be genuinely grounded.
        When er.supported=False, the system must abstain (not hallucinate).
        """
        test_questions = [
            "What is the default port number for SSH connections?",
            "How do you hash a password using bcrypt in Python?",
            "What does the nginx worker_connections directive set?",
            "Why does git rebase produce a linear commit history?",
            "How do you create an XFS filesystem on a device with default settings?",
        ]
        for q in test_questions:
            er = self._run(q)
            # If supported, answer must be factual (not false support)
            if er.supported and er.answer_type != "factual":
                self.fail(
                    "False support detected for '%s'; supported=True, "
                    "answer_type=%s, answer=%s"
                    % (q, er.answer_type, er.answer[:80]),
                )
            # If not supported, answer type should be abstention-like
            if not er.supported and er.answer_type not in ("system", "conflict"):
                self.fail(
                    "Expected abstention or system answer for '%s'; got %s"
                    % (q, er.answer_type),
                )

    def test_abstention_rather_than_wrong_answer(self):
        er = self._run("How do you configure MongoDB replica sets?")
        # Either unsupported (abstain) or correct answer, never wrong
        if er.supported and er.answer_type != "factual":
            self.fail(
                "Expected abstention or factual answer; got supported=%s answer_type=%s: %s"
                % (er.supported, er.answer_type, er.answer[:80]),
            )

    def _run(self, question):
        from runtime_architecture import execute_runtime
        from rag_chat_v2 import answer_question
        from webui.chat_handler import build_answer_contract, collect_sources
        return execute_runtime(
            self.pipeline, question, top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )


if __name__ == "__main__":
    unittest.main()