"""Upload smoke test.

Reproduces the Q1 (reasoning-model hallucination) and Q2 (extractor silent
rejection) failures for uploaded documents, then re-verifies them after fixes.

Usage:
    PYTHONPATH=src .venv/Scripts/python.exe tools/upload_smoke.py
"""

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag_chat_v2 import (
    initialize_pipeline,
    answer_question,
)
from webui.app import handle_uploads


UPLOAD_CONTENT = (
    "The Stadtbibliothek Zarragon is a fictional municipal library "
    "in the city of Zarragon. It was founded in the year 1842 by "
    "Archivist Magnus Holzmann. The library houses a rare "
    "manuscript collection known as the Holzmann Codex, which "
    "contains 312 medieval songs written in Old Zarragonese. "
    "The Stadtbibliothek Zarragon also operates a famous "
    "astronomical clock, the Zarragon Zytglogge, which was "
    "installed in the south tower in 1903."
)


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def run() -> int:
    pipeline = initialize_pipeline()

    tmp = ROOT / f".upload_smoke_{uuid.uuid4().hex}.txt"
    tmp.write_text(UPLOAD_CONTENT, encoding="utf-8")

    try:
        section("Step 1: handle_uploads (webui path)")
        file_data = [
            {"path": str(tmp.resolve()), "orig_name": tmp.name,
             "size": tmp.stat().st_size},
        ]
        status_md, rows, _ = handle_uploads(file_data, pipeline)
        print(status_md)
        print("uploaded_docs:", pipeline.get("uploaded_docs"))
        print("chunks len:", len(pipeline["chunks"]))

        section("Q2 — factual 'when was X founded?'")
        print("(verbose=True so we see the dev instrumentation)")
        r2 = answer_question(
            pipeline,
            "When was the Stadtbibliothek Zarragon founded?",
            verbose=True,
        )
        print(f"\n-> answer_type:  {r2.get('answer_type')}")
        print(f"-> supported:    {r2.get('supported')}")
        print(f"-> answer:       {(r2.get('answer') or '')[:200]}")

        section("Q1 — reasoning 'who founded X?'")
        r1 = answer_question(
            pipeline,
            "Who founded the Stadtbibliothek Zarragon?",
            verbose=True,
        )
        print(f"\n-> answer_type:  {r1.get('answer_type')}")
        print(f"-> supported:    {r1.get('supported')}")
        print(f"-> answer:       {(r1.get('answer') or '')[:200]}")

        section("Q3 — wikitext-only baseline (should NOT regress)")
        r3 = answer_question(
            pipeline,
            "Why did the Roman Empire decline?",
            verbose=False,
        )
        print(f"-> answer_type:  {r3.get('answer_type')}")
        print(f"-> supported:    {r3.get('supported')}")
        print(f"-> answer:       {(r3.get('answer') or '')[:200]}")

        # Heuristic pass/fail.
        ok_q2 = r2.get("answer_type") == "extractor" and r2.get("supported")
        ok_q1 = not (r1.get("answer_type") == "reasoning_model"
                     and r1.get("supported"))
        ok_q3 = r3.get("answer_type") in ("causal",) and r3.get("supported")

        section("Summary")
        print(f"Q2 fixed (factual on uploaded content): {ok_q2}")
        print(f"Q1 fixed (no hallucination on upload):  {ok_q1}")
        print(f"Q3 not regressed (wikitext baseline):   {ok_q3}")
        return 0 if (ok_q2 and ok_q1 and ok_q3) else 1

    finally:
        if tmp.exists():
            tmp.unlink()


if __name__ == "__main__":
    sys.exit(run())