import argparse
import json
import re
import sys
from pathlib import Path
from collections import Counter

import os
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PROJECT_ROOT

INDEX_FILE = PROJECT_ROOT / "indexes" / "knowledge.json"
TOP_K = 5


def tokenize(text):
    return re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())


def score_chunk(query_tokens, chunk_text):
    chunk_tokens = tokenize(chunk_text)
    counts = Counter(chunk_tokens)

    score = 0

    for token in query_tokens:
        score += counts[token]

    return score


def search(query, chunks, top_k=TOP_K):
    query_tokens = tokenize(query)

    scored = []

    for chunk in chunks:
        score = score_chunk(
            query_tokens,
            chunk["text"],
        )

        if score > 0:
            scored.append(
                (
                    score,
                    chunk["id"],
                    chunk["text"],
                )
            )

    scored.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    return scored[:top_k]


def run_query(query, chunks):
    """Process a single query and print formatted results."""
    if not query:
        return

    results = search(query, chunks)

    if not results:
        print("\nNo matching chunks found.")
        return

    print("\nTop results:")

    for rank, (score, chunk_id, text) in enumerate(
        results,
        start=1,
    ):
        print("\n" + "=" * 70)
        print(
            f"Rank: {rank} | "
            f"Chunk ID: {chunk_id} | "
            f"Score: {score}"
        )
        print("-" * 70)
        print(text)


def main():
    parser = argparse.ArgumentParser(
        description="Keyword-based knowledge search."
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        help="Single query (non-interactive mode)",
    )
    args = parser.parse_args()

    if not INDEX_FILE.exists():
        raise FileNotFoundError(INDEX_FILE)

    with INDEX_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        chunks = json.load(f)

    print("Loaded chunks:", len(chunks))

    # Non-interactive (batch) mode: process a single query and exit.
    if args.query is not None:
        run_query(args.query.strip(), chunks)
        return

    print("Type 'quit' to exit.")

    # Interactive mode.
    try:
        while True:
            query = input("\nQuery: ").strip()

            if query.lower() == "quit":
                break

            if not query:
                continue

            run_query(query, chunks)
    except (EOFError, KeyboardInterrupt):
        print("\n\nNo input provided. Exiting gracefully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
