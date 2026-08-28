import json
import random
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR


SOURCE_FILE = DATA_DIR / "wikitext_v2.txt"

OUTPUT_FILE = DATA_DIR / "instruction_train_v3.jsonl"

RANDOM_SEED = 42
MAX_EXAMPLES = 10000


def clean_text(text):
    text = text.replace("@-@", "-")
    text = text.replace("@.@", ".")
    text = text.replace("@,@", ",")

    text = re.sub(
        r"^\s*=+\s*(.*?)\s*=+\s*$",
        r"\1",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def split_sentences(text):
    return re.split(
        r"(?<=[.!?])\s+",
        text,
    )


def clean_subject(text):
    text = text.strip(" ,.;:-")

    if len(text) < 2:
        return None

    if len(text) > 150:
        return None

    words = text.split()

    if not 1 <= len(words) <= 15:
        return None

    bad_words = {
        "he",
        "she",
        "it",
        "they",
        "their",
        "his",
        "her",
        "this",
        "that",
        "these",
        "those",
        "there",
        "previously",
        "lying",
        "which",
        "who",
    }

    lower_words = {
        word.lower().strip(" ,.;:")
        for word in words
    }

    if lower_words & bad_words:
        return None

    # Reject long clause-like subjects
    if text.count(",") > 1:
        return None

    return text


def clean_answer(text):
    text = text.strip(" ,.;:-")

    if len(text) < 2:
        return None

    if len(text) > 150:
        return None

    return text


def make_qa(sentence):
    sentence = sentence.strip()

    if not 25 <= len(sentence) <= 400:
        return None

    # X was born in YEAR
    m = re.match(
        r"^(.{2,120}?) was born in "
        r"((?:1[0-9]{3}|20[0-9]{2}))"
        r"(?:[ ,.;]|$)",
        sentence,
        re.IGNORECASE,
    )

    if m:
        subject = clean_subject(m.group(1))
        answer = clean_answer(m.group(2))

        if subject and answer:
            return {
                "question": f"When was {subject} born?",
                "answer": answer,
                "type": "born_year",
            }

    # X was born on DATE
    m = re.match(
        r"^(.{2,120}?) was born on "
        r"([A-Za-z]+ \d{1,2} ,? "
        r"(?:1[0-9]{3}|20[0-9]{2}))"
        r"(?:[ ,.;]|$)",
        sentence,
        re.IGNORECASE,
    )

    if m:
        subject = clean_subject(m.group(1))
        answer = clean_answer(m.group(2))

        if subject and answer:
            return {
                "question": f"When was {subject} born?",
                "answer": answer,
                "type": "born_date",
            }

    # X was founded/established in YEAR
    m = re.match(
        r"^(.{2,120}?) was "
        r"(founded|established) in "
        r"((?:1[0-9]{3}|20[0-9]{2}))"
        r"(?:[ ,.;]|$)",
        sentence,
        re.IGNORECASE,
    )

    if m:
        subject = clean_subject(m.group(1))
        action = m.group(2).lower()
        answer = clean_answer(m.group(3))

        if subject and answer:
            return {
                "question":
                    f"When was {subject} {action}?",
                "answer": answer,
                "type": "founded_year",
            }

    # X is the capital of Y
    m = re.match(
        r"^(.{2,100}?) is the capital of "
        r"(.{2,100}?)(?:[.;]|$)",
        sentence,
        re.IGNORECASE,
    )

    if m:
        subject = clean_subject(m.group(1))
        answer = clean_answer(m.group(2))

        if (
            subject
            and answer
            and len(answer.split()) <= 12
        ):
            return {
                "question":
                    f"What is {subject} the capital of?",
                "answer": answer,
                "type": "capital",
            }

    # X was released in YEAR
    m = re.match(
        r"^(.{2,120}?) was released in "
        r"((?:1[0-9]{3}|20[0-9]{2}))"
        r"(?:[ ,.;]|$)",
        sentence,
        re.IGNORECASE,
    )

    if m:
        subject = clean_subject(m.group(1))
        answer = clean_answer(m.group(2))

        if subject and answer:
            return {
                "question":
                    f"When was {subject} released?",
                "answer": answer,
                "type": "release_year",
            }

    return None


def make_context(sentences, index):
    start = max(0, index - 1)
    end = min(len(sentences), index + 2)

    context = " ".join(
        sentences[start:end]
    )

    return context[:1200]


def main():
    random.seed(RANDOM_SEED)

    print("Reading corpus...")

    raw_text = SOURCE_FILE.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    examples = []

    ALLOWED_TYPES = {
        "born_year",
        "born_date",
        "founded_year",
        "release_year",
        "capital",
    }

    for line in raw_text.splitlines():
        line = clean_text(line)

        if len(line) < 30:
            continue

        sentences = [
            clean_text(s)
            for s in split_sentences(line)
            if clean_text(s)
        ]

        for index, sentence in enumerate(sentences):
            qa = make_qa(sentence)

            if qa is None:
                continue

            if qa["type"] not in ALLOWED_TYPES:
                continue

            context = make_context(
                sentences,
                index,
            )

            # Answer must literally appear
            # inside the supplied context.
            if (
                qa["answer"].lower()
                not in context.lower()
            ):
                continue

            prompt = (
                "<RESULT>\n"
                f"{context}\n\n"
                "<ANSWER>\n"
                f"Question: {qa['question']}\n"
                "Answer:"
            )

            example = {
                "context": context,
                "question": qa["question"],
                "answer": qa["answer"],
                "type": qa["type"],
                "prompt": prompt,
            }

            examples.append(example)

            if len(examples) >= MAX_EXAMPLES:
                break

        if len(examples) >= MAX_EXAMPLES:
            break

    # Remove duplicate QA pairs
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

    print(
        "Clean instruction examples:",
        len(examples),
    )

    print("\nExample types:")

    final_counts = {}

    for example in examples:
        example_type = example["type"]

        final_counts[example_type] = (
            final_counts.get(
                example_type,
                0,
            )
            + 1
        )

    for name, count in sorted(
        final_counts.items()
    ):
        print(
            f"  {name}: {count}"
        )

    print(
        "\nSaved:",
        OUTPUT_FILE,
    )

    print(
        "\n----- SAMPLE EXAMPLES -----"
    )

    for example in examples[:10]:
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