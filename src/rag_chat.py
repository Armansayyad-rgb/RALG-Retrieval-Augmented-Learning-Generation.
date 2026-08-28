import json
import re
from collections import Counter
from pathlib import Path

import torch
import torch.nn.functional as F
from tokenizers import Tokenizer

from model import SmallLM
from embedding_model import TextEmbeddingModel
from config import MODEL_CONFIG, PROJECT_ROOT, DATA_DIR, CHECKPOINTS_DIR


KNOWLEDGE_FILE = PROJECT_ROOT / "indexes" / "knowledge.json"

TOKENIZER_FILE = DATA_DIR / "tokenizer.json"

LM_FILE = CHECKPOINTS_DIR / "instruction_model_v2.pt"

EMBEDDING_MODEL_FILE = CHECKPOINTS_DIR / "embedding_model.pt"

MAX_LENGTH = 128
TOP_K = 1

KEYWORD_WEIGHT = 0.7
EMBEDDING_WEIGHT = 0.3

MAX_NEW_TOKENS = 100
TEMPERATURE = 0.7
TOP_K_SAMPLE = 30


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


def normalize(values):
    minimum = min(values)
    maximum = max(values)

    if maximum == minimum:
        return [0.0 for _ in values]

    return [
        (v - minimum) / (maximum - minimum)
        for v in values
    ]

def encode_for_embedding(
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
def generate(
    model,
    tokenizer,
    prompt,
    device,
):
    encoded = tokenizer.encode(prompt)
    token_ids = encoded.ids

    eos_id = tokenizer.token_to_id("<EOS>")
    bos_id = tokenizer.token_to_id("<BOS>")

    if token_ids and token_ids[-1] == eos_id:
        token_ids = token_ids[:-1]

    x = torch.tensor(
        [token_ids],
        dtype=torch.long,
        device=device,
    )

    # Remember where the prompt ends
    prompt_length = x.shape[1]

    model.eval()

    with torch.no_grad():
        for _ in range(MAX_NEW_TOKENS):

            x_input = x[
                :,
                -model.context_length:
            ]

            logits, _ = model(x_input)

            logits = (
                logits[:, -1, :]
                / TEMPERATURE
            )

            k = min(
                TOP_K_SAMPLE,
                logits.size(-1),
            )

            values, _ = torch.topk(
                logits,
                k,
            )

            cutoff = values[
                :, -1
            ].unsqueeze(-1)

            logits = torch.where(
                logits < cutoff,
                torch.full_like(
                    logits,
                    float("-inf"),
                ),
                logits,
            )

            probs = torch.softmax(
                logits,
                dim=-1,
            )

            next_token = torch.multinomial(
                probs,
                num_samples=1,
            )

            x = torch.cat(
                [x, next_token],
                dim=1,
            )

            if next_token.item() == eos_id:
                break

    # ONLY take tokens generated after the prompt
    output_ids = x[
        0,
        prompt_length:
    ].tolist()

    output_ids = [
        token_id
        for token_id in output_ids
        if token_id not in (
            bos_id,
            eos_id,
        )
    ]

    return tokenizer.decode(
        output_ids
    )

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

    print(
        "Loaded knowledge chunks:",
        len(chunks),
    )

    embedding_model = TextEmbeddingModel(
        vocab_size=MODEL_CONFIG["vocab_size"],
        max_length=MAX_LENGTH,
    ).to(device)

    embedding_state = torch.load(
        EMBEDDING_MODEL_FILE,
        map_location=device,
        weights_only=True,
    )

    embedding_model.load_state_dict(
        embedding_state
    )

    embedding_model.eval()

    print("Building semantic index...")

    chunk_embeddings = []

    with torch.no_grad():
        for chunk in chunks:

            ids, mask = encode_for_embedding(
                tokenizer,
                chunk["text"],
                MAX_LENGTH,
            )

            ids = ids.to(device)
            mask = mask.to(device)

            emb = embedding_model(
                ids,
                mask,
            )

            chunk_embeddings.append(
                emb.squeeze(0).cpu()
            )

    chunk_embeddings = torch.stack(
        chunk_embeddings
    )

    language_model = SmallLM().to(device)

    lm_state = torch.load(
        LM_FILE,
        map_location=device,
        weights_only=True,
    )

    language_model.load_state_dict(
        lm_state
    )

    language_model.eval()

    print("System ready.")
    print("Type 'quit' to exit.")

    while True:

        query = input("\nYou: ").strip()

        if query.lower() == "quit":
            break

        if not query:
            continue

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

        ids, mask = encode_for_embedding(
            tokenizer,
            query,
            MAX_LENGTH,
        )

        ids = ids.to(device)
        mask = mask.to(device)

        with torch.no_grad():

            query_embedding = (
                embedding_model(
                    ids,
                    mask,
                ).cpu()
            )

        raw_embedding_scores = (
            F.cosine_similarity(
                query_embedding,
                chunk_embeddings,
                dim=1,
            ).tolist()
        )

        embedding_scores = normalize(
            raw_embedding_scores
        )

        combined = []

        for i, chunk in enumerate(chunks):

            score = (
                KEYWORD_WEIGHT
                * keyword_scores[i]
                +
                EMBEDDING_WEIGHT
                * embedding_scores[i]
            )

            combined.append(
                (
                    score,
                    chunk,
                )
            )

        combined.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        best_chunks = [
            item[1]
            for item in combined[:TOP_K]
        ]

        context = "\n\n".join(
            chunk["text"]
            for chunk in best_chunks
        )

        prompt = (
            "<RESULT>\n"
            + context
            + "\n\n"
            + "<ANSWER>\n"
            + "Question: "
            + query
            + "\nAnswer:"
        )

        print("\nRetrieved context:")
        print("-" * 60)

        for i, chunk in enumerate(
            best_chunks,
            start=1,
        ):
            print(
                f"[{i}] "
                + chunk["text"][:300]
                + "..."
            )

        answer = generate(
            language_model,
            tokenizer,
            prompt,
            device,
        )

        print("\nModel:")
        print(answer)


if __name__ == "__main__":
    main()