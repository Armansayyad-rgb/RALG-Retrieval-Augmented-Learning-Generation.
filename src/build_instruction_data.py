import json
import random
import re
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PROJECT_ROOT, DATA_DIR

KNOWLEDGE_FILE = PROJECT_ROOT / "indexes" / "knowledge.json"

OUTPUT_FILE = DATA_DIR / "instruction_train.jsonl"

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


def split_sentences(text):
    sentences = re.split(
        r"(?<=[.!?])\s+",
        text.strip()
    )

    return [
        s.strip()
        for s in sentences
        if 30 <= len(s.strip()) <= 350
    ]


def tokenize(text):
    return re.findall(
        r"\b[a-zA-Z][a-zA-Z0-9'-]*\b",
        text.lower(),
    )


def get_topic(sentence):
    words = [
        word
        for word in tokenize(sentence)
        if word not in STOPWORDS
        and len(word) >= 4
    ]

    counts = Counter(words)

    important = [
        word
        for word, _ in counts.most_common(3)
    ]

    if not important:
        return "this topic"

    return " ".join(important)


def build_example(chunk_text):
    sentences = split_sentences(chunk_text)

    if not sentences:
        return None

    answer = random.choice(sentences)

    topic = get_topic(answer)

    question_templates = [
        f"What does the context say about {topic}?",
        f"According to the context, what is stated about {topic}?",
        f"Explain the information about {topic} using the context.",
    ]

    question = random.choice(
        question_templates
    )

    training_text = (
        "<RESULT>\n"
        + chunk_text
        + "\n\n"
        + "<ANSWER>\n"
        + "Question: "
        + question
        + "\n"
        + "Answer: "
        + answer
        + "<EOS>"
    )

    return {
        "context": chunk_text,
        "question": question,
        "answer": answer,
        "text": training_text,
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

        # Make several examples from every chunk
        for _ in range(3):

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
        len(examples)
    )

    print(
        "Saved:",
        OUTPUT_FILE
    )

    print("\nExample:")
    print("-" * 70)

    example = examples[0]

    print("QUESTION:")
    print(example["question"])

    print("\nANSWER:")
    print(example["answer"])

    print("\nTRAINING FORMAT:")
    print(example["text"])


if __name__ == "__main__":
    main()