import json
import random
import re
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR


INPUT_FILE = DATA_DIR / "reasoning_train_v1.jsonl"

OUTPUT_FILE = DATA_DIR / "reasoning_train_v1_clean.jsonl"

RANDOM_SEED = 42


def balanced_symbols(text):
    pairs = [
        ("(", ")"),
        ("[", "]"),
        ('"', '"'),
    ]

    for left, right in pairs:
        if left == right:
            if text.count(left) % 2 != 0:
                return False
        else:
            if text.count(left) != text.count(right):
                return False

    return True


def looks_bad_question(question):
    q = question.strip()

    if len(q) < 15 or len(q) > 260:
        return True

    if not q.endswith("?"):
        return True

    bad_starts = [
        "Why [",
        "Why (",
        "Why ,",
        "Why and ",
        "Why but ",
        "Why because ",
    ]

    if any(
        q.lower().startswith(start.lower())
        for start in bad_starts
    ):
        return True

    bad_endings = [
        " and?",
        " but?",
        " or?",
        ",?",
    ]

    if any(
        q.lower().endswith(ending)
        for ending in bad_endings
    ):
        return True

    if not balanced_symbols(q):
        return True

    # Reject very clause-heavy questions.
    if q.count(",") > 4:
        return True

    return False


def looks_bad_answer(answer):
    a = answer.strip()

    if len(a) < 8 or len(a) > 260:
        return True

    if not balanced_symbols(a):
        return True

    if a.count(",") > 5:
        return True

    bad_endings = [
        ", and",
        ", but",
        ", or",
        " and",
        " but",
        " or",
    ]

    lower = a.lower().rstrip(". ")

    if any(
        lower.endswith(ending)
        for ending in bad_endings
    ):
        return True

    return False


def answer_supported_by_context(answer, context):
    answer_words = [
        word.lower()
        for word in re.findall(
            r"[A-Za-z0-9']+",
            answer,
        )
        if len(word) >= 4
    ]

    if not answer_words:
        return False

    context_lower = context.lower()

    overlap = sum(
        1
        for word in answer_words
        if word in context_lower
    )

    return (
        overlap / len(answer_words)
        >= 0.75
    )


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

            question = example["question"]
            answer = example["answer"]
            context = example["context"]

            if looks_bad_question(question):
                continue

            if looks_bad_answer(answer):
                continue

            if not answer_supported_by_context(
                answer,
                context,
            ):
                continue

            examples.append(example)

    # Remove duplicate QA pairs
    unique = {}

    for example in examples:
        key = (
            example["question"].lower(),
            example["answer"].lower(),
        )

        if key not in unique:
            unique[key] = example

    examples = list(
        unique.values()
    )

    random.shuffle(
        examples
    )

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
        "Clean reasoning examples:",
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