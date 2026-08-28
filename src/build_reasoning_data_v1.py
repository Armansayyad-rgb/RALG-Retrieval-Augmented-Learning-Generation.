import json
import random
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR


SOURCE_FILE = DATA_DIR / "wikitext_v2.txt"

OUTPUT_FILE = DATA_DIR / "reasoning_train_v1.jsonl"

RANDOM_SEED = 42
MAX_EXAMPLES = 8000


def clean_text(text):
    text = text.replace("@-@", "-")
    text = text.replace("@.@", ".")
    text = text.replace("@,@", ",")

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


def clean_fragment(text):
    text = text.strip(" ,.;:-")

    if len(text) < 8:
        return None

    if len(text) > 220:
        return None

    return text


def make_why_example(sentence):
    sentence = sentence.strip()

    if not 35 <= len(sentence) <= 450:
        return None

    # -----------------------------------
    # X because Y
    # -----------------------------------

    match = re.match(
        r"^(.{10,220}?) because (.{10,220}?)(?:[.;]|$)",
        sentence,
        flags=re.IGNORECASE,
    )

    if match:
        effect = clean_fragment(
            match.group(1)
        )

        cause = clean_fragment(
            match.group(2)
        )

        if effect and cause:
            return {
                "question":
                    f"Why {effect.rstrip('?')}?",
                "answer":
                    f"Because {cause}.",
                "type":
                    "because",
            }

    # -----------------------------------
    # X due to Y
    # -----------------------------------

    match = re.match(
        r"^(.{10,220}?) due to (.{10,220}?)(?:[.;]|$)",
        sentence,
        flags=re.IGNORECASE,
    )

    if match:
        effect = clean_fragment(
            match.group(1)
        )

        cause = clean_fragment(
            match.group(2)
        )

        if effect and cause:
            return {
                "question":
                    f"Why {effect.rstrip('?')}?",
                "answer":
                    f"It was due to {cause}.",
                "type":
                    "due_to",
            }

    # -----------------------------------
    # X as a result of Y
    # -----------------------------------

    match = re.match(
        r"^(.{10,220}?) as a result of (.{10,220}?)(?:[.;]|$)",
        sentence,
        flags=re.IGNORECASE,
    )

    if match:
        effect = clean_fragment(
            match.group(1)
        )

        cause = clean_fragment(
            match.group(2)
        )

        if effect and cause:
            return {
                "question":
                    f"Why {effect.rstrip('?')}?",
                "answer":
                    f"It happened as a result of {cause}.",
                "type":
                    "result_of",
            }

    # -----------------------------------
    # X was caused by Y
    # -----------------------------------

    match = re.match(
        r"^(.{10,220}?) was caused by (.{10,220}?)(?:[.;]|$)",
        sentence,
        flags=re.IGNORECASE,
    )

    if match:
        event = clean_fragment(
            match.group(1)
        )

        cause = clean_fragment(
            match.group(2)
        )

        if event and cause:
            return {
                "question":
                    f"What caused {event}?",
                "answer":
                    cause,
                "type":
                    "caused_by",
            }

    return None


def make_context(sentences, index):
    start = max(
        0,
        index - 1,
    )

    end = min(
        len(sentences),
        index + 2,
    )

    context = " ".join(
        sentences[start:end]
    )

    return context[:1400]


def main():
    random.seed(
        RANDOM_SEED
    )

    print(
        "Reading corpus..."
    )

    raw_text = SOURCE_FILE.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    examples = []

    for line in raw_text.splitlines():
        line = clean_text(line)

        if len(line) < 40:
            continue

        sentences = [
            clean_text(sentence)
            for sentence in split_sentences(line)
            if clean_text(sentence)
        ]

        for index, sentence in enumerate(
            sentences
        ):
            qa = make_why_example(
                sentence
            )

            if qa is None:
                continue

            context = make_context(
                sentences,
                index,
            )

            # Answer content should come from context.
            answer_words = [
                word.lower()
                for word in re.findall(
                    r"[A-Za-z0-9']+",
                    qa["answer"],
                )
                if len(word) > 3
            ]

            if answer_words:
                overlap = sum(
                    1
                    for word in answer_words
                    if word in context.lower()
                )

                if (
                    overlap
                    / len(answer_words)
                    < 0.6
                ):
                    continue

            prompt = (
                "<RESULT>\n"
                f"{context}\n\n"
                "<ANSWER>\n"
                f"Question: {qa['question']}\n"
                "Answer:"
            )

            examples.append(
                {
                    "context":
                        context,
                    "question":
                        qa["question"],
                    "answer":
                        qa["answer"],
                    "type":
                        qa["type"],
                    "prompt":
                        prompt,
                }
            )

            if (
                len(examples)
                >= MAX_EXAMPLES
            ):
                break

        if (
            len(examples)
            >= MAX_EXAMPLES
        ):
            break

    # Remove duplicate question-answer pairs.
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

    counts = {}

    for example in examples:
        qa_type = example["type"]

        counts[qa_type] = (
            counts.get(
                qa_type,
                0,
            )
            + 1
        )

    print(
        "Reasoning examples:",
        len(examples),
    )

    print(
        "\nTypes:"
    )

    for name, count in sorted(
        counts.items()
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

    for example in examples[:15]:
        print(
            "\nCONTEXT:"
        )
        print(
            example["context"]
        )

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

        print(
            "-" * 70
        )


if __name__ == "__main__":
    main()