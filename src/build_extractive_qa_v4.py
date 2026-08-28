import json
import random
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR


SOURCE_FILE = DATA_DIR / "wikitext_v2.txt"

OUTPUT_FILE = DATA_DIR / "extractive_qa_v4.jsonl"

RANDOM_SEED = 42
MAX_EXAMPLES = 20000


def clean_text(text):
    text = text.replace("@-@", "-")
    text = text.replace("@.@", ".")
    text = text.replace("@,@", ",")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def split_sentences(text):
    return re.split(
        r"(?<=[.!?])\s+",
        text,
    )


def clean_subject(text):
    text = text.strip(" ,.;:-")

    if len(text) < 2 or len(text) > 120:
        return None

    words = text.split()

    if not 1 <= len(words) <= 14:
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
        "which",
        "who",
        "previously",
        "following",
        "lying",
    }

    lower_words = {
        w.lower().strip(" ,.;:")
        for w in words
    }

    if lower_words & bad_words:
        return None

    if text.count(",") > 1:
        return None

    return text


def clean_answer(text):
    text = text.strip(" ,.;:-")

    if len(text) < 1 or len(text) > 120:
        return None

    return text


def make_qa(sentence):
    sentence = sentence.strip()

    if not 25 <= len(sentence) <= 400:
        return None

    patterns = [
        # born in year
        (
            r"^(.{2,120}?) was born in "
            r"((?:1[0-9]{3}|20[0-9]{2}))"
            r"(?:[ ,.;]|$)",
            lambda s, a:
                f"When was {s} born?",
            "born_year",
        ),

        # born on full date
        (
            r"^(.{2,120}?) was born on "
            r"([A-Za-z]+ \d{1,2} ,? "
            r"(?:1[0-9]{3}|20[0-9]{2}))"
            r"(?:[ ,.;]|$)",
            lambda s, a:
                f"When was {s} born?",
            "born_date",
        ),

        # founded
        (
            r"^(.{2,120}?) was founded in "
            r"((?:1[0-9]{3}|20[0-9]{2}))"
            r"(?:[ ,.;]|$)",
            lambda s, a:
                f"When was {s} founded?",
            "founded_year",
        ),

        # established
        (
            r"^(.{2,120}?) was established in "
            r"((?:1[0-9]{3}|20[0-9]{2}))"
            r"(?:[ ,.;]|$)",
            lambda s, a:
                f"When was {s} established?",
            "established_year",
        ),

        # released
        (
            r"^(.{2,120}?) was released in "
            r"((?:1[0-9]{3}|20[0-9]{2}))"
            r"(?:[ ,.;]|$)",
            lambda s, a:
                f"When was {s} released?",
            "release_year",
        ),

        # published
        (
            r"^(.{2,120}?) was published in "
            r"((?:1[0-9]{3}|20[0-9]{2}))"
            r"(?:[ ,.;]|$)",
            lambda s, a:
                f"When was {s} published?",
            "published_year",
        ),

        # opened
        (
            r"^(.{2,120}?) opened in "
            r"((?:1[0-9]{3}|20[0-9]{2}))"
            r"(?:[ ,.;]|$)",
            lambda s, a:
                f"When did {s} open?",
            "opened_year",
        ),

        # population
        (
            r"^(.{2,120}?) had a population of "
            r"([0-9][0-9,\. ]*)"
            r"(?:[.;]|$)",
            lambda s, a:
                f"What population did {s} have?",
            "population",
        ),

        # capital
        (
            r"^(.{2,100}?) is the capital of "
            r"(.{2,100}?)(?:[.;]|$)",
            lambda s, a:
                f"What is {s} the capital of?",
            "capital",
        ),

        # located in — stricter answer length
        (
            r"^(.{2,100}?) is located in "
            r"([A-Z][A-Za-z0-9' .\-]{1,80})"
            r"(?:[.;]|$)",
            lambda s, a:
                f"Where is {s} located?",
            "location",
        ),

        # named after
        (
            r"^(.{2,100}?) was named after "
            r"(.{2,100}?)(?:[.;]|$)",
            lambda s, a:
                f"Who or what was {s} named after?",
            "named_after",
        ),
    ]

    for pattern, question_builder, qa_type in patterns:
        m = re.match(
            pattern,
            sentence,
            re.IGNORECASE,
        )

        if not m:
            continue

        subject = clean_subject(
            m.group(1)
        )

        answer = clean_answer(
            m.group(2)
        )

        if not subject or not answer:
            continue

        if qa_type == "location":
            if len(answer.split()) > 10:
                continue

        if qa_type == "population":
            if len(answer) > 30:
                continue

        question = question_builder(
            subject,
            answer,
        )

        return {
            "question": question,
            "answer": answer,
            "type": qa_type,
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

    return context[:1200]


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

        if len(line) < 30:
            continue

        sentences = [
            clean_text(s)
            for s in split_sentences(line)
            if clean_text(s)
        ]

        for index, sentence in enumerate(
            sentences
        ):
            qa = make_qa(
                sentence
            )

            if qa is None:
                continue

            context = make_context(
                sentences,
                index,
            )

            # Critical validation:
            # answer must literally be present.
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

            examples.append(
                {
                    "context": context,
                    "question": qa["question"],
                    "answer": qa["answer"],
                    "type": qa["type"],
                    "prompt": prompt,
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

    # Deduplicate
    unique = {}

    for example in examples:
        key = (
            example[
                "question"
            ].lower(),
            example[
                "answer"
            ].lower(),
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

    print(
        "Extractive QA examples:",
        len(examples),
    )

    counts = {}

    for example in examples:
        t = example["type"]

        counts[t] = (
            counts.get(t, 0) + 1
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

    for example in examples[:12]:
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
            "CONTEXT:",
            example["context"],
        )

        print(
            "-" * 70
        )


if __name__ == "__main__":
    main()