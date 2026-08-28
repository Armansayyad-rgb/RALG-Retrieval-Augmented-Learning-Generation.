import json
import math
import re
from collections import Counter
from pathlib import Path

import torch
import torch.nn.functional as F
from tokenizers import Tokenizer

from embedding_model import TextEmbeddingModel
from config import MODEL_CONFIG, PROJECT_ROOT, DATA_DIR, CHECKPOINTS_DIR


KNOWLEDGE_FILE = PROJECT_ROOT / "indexes" / "knowledge.json"

TOKENIZER_FILE = DATA_DIR / "tokenizer.json"

EMBEDDING_MODEL_FILE = CHECKPOINTS_DIR / "embedding_model.pt"

MAX_LENGTH = 128
TOP_K = 5

KEYWORD_WEIGHT = 0.7
EMBEDDING_WEIGHT = 0.3


def tokenize_words(text):
    return re.findall(
        r"\b[a-zA-Z0-9]+\b",
        text.lower(),
    )


def keyword_score(query, text):
    query_tokens = tokenize_words(query)
    text_tokens = tokenize_words(text)

    counts = Counter(text_tokens)

    score = 0.0

    for token in query_tokens:
        score += counts[token]

    return score


def encode_text(
    tokenizer,
    text,
    max_length,
):
    pad_id = tokenizer.token_to_id("<PAD>")

    ids = tokenizer.encode(text).ids[:max_length]

    if len(ids) < max_length:
        ids += [pad_id] * (
            max_length - len(ids)
        )

    input_ids = torch.tensor(
        [ids],
        dtype=torch.long,
    )

    attention_mask = (
        input_ids != pad_id
    ).long()

    return input_ids, attention_mask


def normalize(values):
    if not values:
        return []

    minimum = min(values)
    maximum = max(values)

    if maximum == minimum:
        return [0.0 for _ in values]

    return [
        (value - minimum)
        / (maximum - minimum)
        for value in values
    ]


def main():
    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("Device:", device)

    tokenizer = Tokenizer.from_file(
        str(TOKENIZER_FILE)
    )

    with KNOWLEDGE_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        chunks = json.load(f)

    model = TextEmbeddingModel(
        vocab_size=MODEL_CONFIG["vocab_size"],
        max_length=MAX_LENGTH,
    ).to(device)

    state_dict = torch.load(
        EMBEDDING_MODEL_FILE,
        map_location=device,
        weights_only=True,
    )

    model.load_state_dict(state_dict)
    model.eval()

    print("Embedding knowledge chunks...")

    chunk_embeddings = []

    with torch.no_grad():
        for chunk in chunks:
            ids, mask = encode_text(
                tokenizer,
                chunk["text"],
                MAX_LENGTH,
            )

            ids = ids.to(device)
            mask = mask.to(device)

            emb = model(
                ids,
                mask,
            )

            chunk_embeddings.append(
                emb.squeeze(0).cpu()
            )

    chunk_embeddings = torch.stack(
        chunk_embeddings
    )

    print("Hybrid retriever ready.")
    print("Type 'quit' to exit.")

    while True:
        query = input("\nQuery: ").strip()

        if query.lower() == "quit":
            break

        if not query:
            continue

        # Keyword scores
        raw_keyword_scores = [
            keyword_score(
                query,
                chunk["text"],
            )
            for chunk in chunks
        ]

        keyword_scores = normalize(
            raw_keyword_scores
        )

        # Embedding score
        ids, mask = encode_text(
            tokenizer,
            query,
            MAX_LENGTH,
        )

        ids = ids.to(device)
        mask = mask.to(device)

        with torch.no_grad():
            query_embedding = model(
                ids,
                mask,
            ).cpu()

        raw_embedding_scores = (
            F.cosine_similarity(
                query_embedding,
                chunk_embeddings,
                dim=1,
            )
            .tolist()
        )

        embedding_scores = normalize(
            raw_embedding_scores
        )

        combined = []

        for i, chunk in enumerate(chunks):

            final_score = (
                KEYWORD_WEIGHT
                * keyword_scores[i]
                +
                EMBEDDING_WEIGHT
                * embedding_scores[i]
            )

            combined.append(
                (
                    final_score,
                    keyword_scores[i],
                    embedding_scores[i],
                    chunk,
                )
            )

        combined.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        print("\nTop hybrid results:")

        for rank, item in enumerate(
            combined[:TOP_K],
            start=1,
        ):
            (
                final_score,
                keyword_component,
                embedding_component,
                chunk,
            ) = item

            print("\n" + "=" * 70)

            print(
                f"Rank: {rank} "
                f"| Chunk ID: {chunk['id']} "
                f"| Final: {final_score:.4f} "
                f"| Keyword: {keyword_component:.4f} "
                f"| Embedding: {embedding_component:.4f}"
            )

            print("-" * 70)

            print(chunk["text"])


if __name__ == "__main__":
    main()