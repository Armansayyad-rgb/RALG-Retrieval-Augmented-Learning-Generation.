import json
import random
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR


INPUT_FILE = DATA_DIR / "extractive_qa_v4.jsonl"

OUTPUT_FILE = DATA_DIR / "extractive_qa_v4_clean.jsonl"

ALLOWED_TYPES = {
    "born_year",
    "born_date",
    "founded_year",
    "established_year",
    "published_year",
    "release_year",
    "named_after",
}

RANDOM_SEED = 42


def main():
    random.seed(RANDOM_SEED)

    examples = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            example = json.loads(line)

            if example["type"] not in ALLOWED_TYPES:
                continue

            # Safety check: answer must be
            # an exact substring of context.
            if (
                example["answer"].lower()
                not in example["context"].lower()
            ):
                continue

            examples.append(example)

    # Remove duplicate question/answer pairs.
    unique = {}

    for example in examples:
        key = (
            example["question"].lower(),
            example["answer"].lower(),
        )

        if key not in unique:
            unique[key] = example

    examples = list(unique.values())

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

    counts = Counter(
        example["type"]
        for example in examples
    )

    print(
        "Clean examples:",
        len(examples),
    )

    print("\nTypes:")

    for qa_type, count in sorted(
        counts.items()
    ):
        print(
            f"  {qa_type}: {count}"
        )

    print(
        "\nSaved:",
        OUTPUT_FILE,
    )

    print(
        "\n----- RANDOM QUALITY CHECK -----"
    )

    sample_size = min(
        20,
        len(examples),
    )

    for example in random.sample(
        examples,
        sample_size,
    ):
        print("\nCONTEXT:")
        print(example["context"])

        print(
            "\nQUESTION:",
            example["question"],
        )

        print(
            "ANSWER:",
            example["answer"],
        )

        print(
            "TYPE:",
            example["type"],
        )

        print("-" * 70)


if __name__ == "__main__":
    main()