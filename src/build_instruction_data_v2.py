import json
import random
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PROJECT_ROOT, DATA_DIR

KNOWLEDGE_FILE = PROJECT_ROOT / "indexes" / "knowledge.json"

OUTPUT_FILE = DATA_DIR / "instruction_train_v2.jsonl"

RANDOM_SEED = 42
EXAMPLES_PER_CHUNK = 3


def split_sentences(text):
    sentences = re.split(
        r"(?<=[.!?])\s+",
        text.strip(),
    )

    return [
        s.strip()
        for s in sentences
        if 40 <= len(s.strip()) <= 260
    ]


def make_question(answer):
    lower = answer.lower()

    # Prefer more natural question patterns where possible.
    if " is " in lower:
        subject = answer.split(" is ", 1)[0].strip()

        if 3 <= len(subject.split()) <= 12:
            return f"What is {subject}?"

    if " was " in lower:
        subject = answer.split(" was ", 1)[0].strip()

        if 3 <= len(subject.split()) <= 12:
            return f"What was {subject}?"

    # Fallback: evidence-extraction question.
    words = re.findall(
        r"\b[A-Za-z][A-Za-z0-9'-]*\b",
        answer,
    )

    useful = [
        w
        for w in words
        if len(w) >= 5
    ][:5]

    topic = " ".join(useful)

    if not topic:
        topic = "this topic"

    return (
        f"According to the context, "
        f"what information is given about {topic}?"
    )


def build_example(chunk_text):
    sentences = split_sentences(chunk_text)

    if not sentences:
        return None

    answer = random.choice(sentences)

    question = make_question(answer)

    prompt = (
        "<RESULT>\n"
        + chunk_text
        + "\n\n"
        + "<ANSWER>\n"
        + "Question: "
        + question
        + "\n"
        + "Answer:"
    )

    return {
        "prompt": prompt,
        "answer": answer,
    }


def main():
    random.seed(RANDOM_SEED)

    with KNOWLEDGE_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        chunks = json.load(f)

    examples = []

    for chunk in chunks:
        for _ in range(EXAMPLES_PER_CHUNK):
            example = build_example(
                chunk["text"]
            )

            if example is not None:
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
        "Instruction examples:",
        len(examples),
    )

    print(
        "Saved:",
        OUTPUT_FILE,
    )

    print("\nExample:")
    print("-" * 70)
    print("PROMPT:")
    print(examples[0]["prompt"])

    print("\nANSWER:")
    print(examples[0]["answer"])


if __name__ == "__main__":
    main()
    