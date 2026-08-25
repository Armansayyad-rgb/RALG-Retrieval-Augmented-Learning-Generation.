import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = Path(
    os.environ.get(
        "RALG_TRAIN_FILE",
        PROJECT_ROOT / "data" / "train.txt",
    )
)
OUTPUT_FILE = Path(
    os.environ.get(
        "RALG_KNOWLEDGE_INDEX_FILE",
        PROJECT_ROOT / "indexes" / "knowledge.json",
    )
)

CHUNK_WORDS = 120
OVERLAP_WORDS = 25


def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_chunks(text):
    words = text.split()

    chunks = []
    start = 0
    chunk_id = 0

    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))

        chunk_text = " ".join(words[start:end])

        chunks.append({
            "id": chunk_id,
            "text": chunk_text,
            "start_word": start,
            "end_word": end,
        })

        chunk_id += 1

        if end == len(words):
            break

        start += CHUNK_WORDS - OVERLAP_WORDS

    return chunks


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(DATA_FILE)

    text = DATA_FILE.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    text = clean_text(text)

    chunks = make_chunks(text)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            chunks,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("Characters:", len(text))
    print("Words:", len(text.split()))
    print("Chunks:", len(chunks))
    print("Saved:", OUTPUT_FILE)

    if chunks:
        print("\nExample chunk:")
        print("-" * 60)
        print(chunks[0]["text"])


if __name__ == "__main__":
    main()
