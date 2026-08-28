import argparse
import json
import sys

import torch
import torch.nn.functional as F

from pathlib import Path
from tokenizers import Tokenizer

from embedding_model import TextEmbeddingModel
from config import MODEL_CONFIG, PROJECT_ROOT, DATA_DIR, CHECKPOINTS_DIR


KNOWLEDGE_FILE = PROJECT_ROOT / "indexes" / "knowledge.json"

TOKENIZER_FILE = DATA_DIR / "tokenizer.json"

MODEL_FILE = CHECKPOINTS_DIR / "embedding_model.pt"

MAX_LENGTH = 128
TOP_K = 5


def encode_text(tokenizer, text, max_length):
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


def run_query(query, tokenizer, model, chunk_embeddings, chunks, device):
    """Process a single query and print formatted semantic results."""
    if not query:
        return

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

    scores = F.cosine_similarity(
        query_embedding,
        chunk_embeddings,
        dim=1,
    )

    top_scores, top_indices = torch.topk(
        scores,
        k=min(TOP_K, len(chunks)),
    )

    print("\nTop semantic results:")

    for rank, (score, idx) in enumerate(
        zip(
            top_scores.tolist(),
            top_indices.tolist(),
        ),
        start=1,
    ):
        print("\n" + "=" * 70)

        print(
            f"Rank: {rank} "
            f"| Chunk ID: {chunks[idx]['id']} "
            f"| Similarity: {score:.4f}"
        )

        print("-" * 70)

        print(chunks[idx]["text"])


def main():
    parser = argparse.ArgumentParser(
        description="Semantic embedding search over the knowledge base."
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        help="Single query (non-interactive mode)",
    )
    args = parser.parse_args()

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
        MODEL_FILE,
        map_location=device,
        weights_only=True,
    )

    model.load_state_dict(state_dict)
    model.eval()

    print("Embedding all knowledge chunks...")

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

            emb = model(ids, mask)

            chunk_embeddings.append(
                emb.squeeze(0).cpu()
            )

    chunk_embeddings = torch.stack(
        chunk_embeddings
    )

    print("Ready.")

    # Non-interactive (batch) mode: process a single query and exit.
    if args.query is not None:
        run_query(
            args.query.strip(),
            tokenizer,
            model,
            chunk_embeddings,
            chunks,
            device,
        )
        return

    print("Type 'quit' to exit.")

    # Interactive mode.
    try:
        while True:
            query = input("\nQuery: ").strip()

            if query.lower() == "quit":
                break

            if not query:
                continue

            run_query(
                query,
                tokenizer,
                model,
                chunk_embeddings,
                chunks,
                device,
            )
    except (EOFError, KeyboardInterrupt):
        print("\n\nNo input provided. Exiting gracefully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
