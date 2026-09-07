"""Category D explicit causal probe — D016-D020.

Runs these cases through the exact production stack and reports
semantic correctness and gate acceptance separately.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import KNOWLEDGE_FILES, DATA_DIR
from retriever_v2 import build_index, retrieve, RuntimeChunk
from runtime_architecture import execute_runtime
from rag_chat_v2 import answer_question, initialize_pipeline
from webui.chat_handler import build_answer_contract, collect_sources


def main():
    print("Starting Category D Causal Probe (D016-D020)...")
    pipeline = initialize_pipeline(verbose=False)
    docs_dir = PROJECT_ROOT / "evaluation" / "post_v4_dev" / "docs"
    for f in sorted(docs_dir.glob("*.txt")):
        chunk = RuntimeChunk(f.read_text(encoding="utf-8"), metadata={"document_id": f.stem})
        pipeline["chunks"].append(chunk)
    index, doc_freq = build_index(pipeline["chunks"])
    pipeline["retrieval_index"] = index
    pipeline["document_frequency"] = doc_freq

    cases_file = PROJECT_ROOT / "evaluation" / "post_v4_dev" / "dev_cases.jsonl"
    cases = []
    with open(cases_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    d_cases = [c for c in cases if c["category"] == "D"]
    print(f"Found {len(d_cases)} Category D cases.")

    output_dir = PROJECT_ROOT / "evaluation" / "post_v4_dev" / "remediation_causal_probe"
    output_dir.mkdir(parents=True, exist_ok=True)

    for case in d_cases:
        case_id = case["case_id"]
        question = case["question"]
        expected_doc = case.get("expected_documents", ["Unknown"])[0]
        print(f"\nProbing {case_id}: {question}")

        exec_result = execute_runtime(
            pipeline=pipeline,
            question=question,
            top_k=5,
            answer_fn=answer_question,
            contract_fn=build_answer_contract,
            sources_fn=collect_sources,
        )

        res = {
            "case_id": case_id,
            "category": "D",
            "question": question,
            "expected_document": expected_doc,
            "supported": exec_result.supported,
            "answer": exec_result.answer,
            "answer_type": exec_result.answer_type,
            "sources": [
                s.get("document_id")
                for s in exec_result.sources
                if s.get("document_id")
            ],
            "gate_passed": exec_result.observability.get("support_gate", {}).get("passed", False) if isinstance(exec_result.observability.get("support_gate"), dict) else False,
            "gate_reasons": exec_result.observability.get("support_gate", {}).get("reasons", []) if isinstance(exec_result.observability.get("support_gate"), dict) else [],
        }

        print(f"  supported={res['supported']}, answer_type={res['answer_type']}")
        print(f"  answer: {res['answer'][:120]}...")
        print(f"  gate_passed={res['gate_passed']}")

        with open(output_dir / f"{case_id}_probe.json", "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)

    # Summary
    print("\n=== SUMMARY ===")
    for case in d_cases:
        cid = case["case_id"]
        probe_file = output_dir / f"{cid}_probe.json"
        if probe_file.exists():
            with open(probe_file) as f:
                r = json.load(f)
            print(f"{cid}: supported={r['supported']}, gate={r['gate_passed']}, type={r['answer_type']}")
            print(f"  answer: {r['answer'][:100]}")

    print(f"\nResults written to {output_dir}")


if __name__ == "__main__":
    main()
