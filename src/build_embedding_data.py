import json
import random
import re
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PROJECT_ROOT, DATA_DIR

KNOWLEDGE_FILE = PROJECT_ROOT / "indexes" / "knowledge.json"

OUTPUT_FILE = DATA_DIR / "embedding_train.jsonl"

RANDOM_SEED = 42

STOPWORDS = {
    "the", "a", "an", "and", "or", "but",
    "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "was",
    "are", "were", "be", "been", "being",
    "that", "this", "these", "those",
    "it", "its", "they", "their", "them",
    "he", "she", "his", "her",
    "which", "who", "what", "when", "where",
    "has", "have", "had", "do", "does",
    "did", "not", "also", "into", "than",
}


def tokenize(text):
    return re.findall(
        r"\b[a-zA-Z][a-zA-Z0-9'-]*\b",
        text.lower(),
    )


def make_query(text, max_words=8):
    words = [
        word
        for word in tokenize(text)
        if word not in STOPWORDS
        and len(word) > 2
    ]

    counts = Counter(words)

    important = [
        word
        for word, _ in counts.most_common(max_words)
    ]

    return " ".join(important)


def main():
    random.seed(RANDOM_SEED)

    with KNOWLEDGE_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        chunks = json.load(f)

    examples = []

    for i, chunk in enumerate(chunks):

        query = make_query(
            chunk["text"]
        )

        if not query:
            continue

        # Pick a different chunk as negative.
        negative_index = i

        while negative_index == i:
            negative_index = random.randrange(
                len(chunks)
            )

        negative_chunk = chunks[
            negative_index
        ]

        example = {
            "query": query,
            "positive": chunk["text"],
            "negative": negative_chunk["text"],
        }

        examples.append(example)

    random.shuffle(examples)

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        for example in examples:

            f.write(
                json.dumps(
                    example,
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(
        "Training examples:",
        len(examples),
    )

    print(
        "Saved:",
        OUTPUT_FILE,
    )

    print("\nExample:")
    print(
        json.dumps(
            examples[0],
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
    