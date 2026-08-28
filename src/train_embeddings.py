import json
import torch
import torch.nn.functional as F

from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from tokenizers import Tokenizer

from embedding_model import TextEmbeddingModel
from config import MODEL_CONFIG, DATA_DIR, CHECKPOINTS_DIR


DATA_FILE = DATA_DIR / "embedding_train.jsonl"

TOKENIZER_FILE = DATA_DIR / "tokenizer.json"

OUTPUT_FILE = CHECKPOINTS_DIR / "embedding_model.pt"

BATCH_SIZE = 8
EPOCHS = 20
LEARNING_RATE = 2e-4
MAX_LENGTH = 128
MARGIN = 0.2


class EmbeddingDataset(Dataset):
    def __init__(self, path):
        self.examples = []

        with path.open(
            "r",
            encoding="utf-8",
        ) as f:
            for line in f:
                self.examples.append(
                    json.loads(line)
                )

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx]


def encode_batch(
    tokenizer,
    texts,
    max_length,
):
    all_ids = []

    pad_id = tokenizer.token_to_id(
        "<PAD>"
    )

    for text in texts:
        encoded = tokenizer.encode(text)

        ids = encoded.ids[:max_length]

        if len(ids) < max_length:
            ids += [pad_id] * (
                max_length - len(ids)
            )

        all_ids.append(ids)

    input_ids = torch.tensor(
        all_ids,
        dtype=torch.long,
    )

    attention_mask = (
        input_ids != pad_id
    ).long()

    return input_ids, attention_mask


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

    dataset = EmbeddingDataset(
        DATA_FILE
    )

    print(
        "Training examples:",
        len(dataset),
    )

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    model = TextEmbeddingModel(
        vocab_size=MODEL_CONFIG[
            "vocab_size"
        ],
        max_length=MAX_LENGTH,
    ).to(device)

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=0.01,
    )

    scaler = torch.amp.GradScaler(
        "cuda"
    )

    model.train()

    for epoch in range(EPOCHS):

        total_loss = 0.0

        for batch in loader:

            queries = batch["query"]
            positives = batch["positive"]
            negatives = batch["negative"]

            q_ids, q_mask = encode_batch(
                tokenizer,
                queries,
                MAX_LENGTH,
            )

            p_ids, p_mask = encode_batch(
                tokenizer,
                positives,
                MAX_LENGTH,
            )

            n_ids, n_mask = encode_batch(
                tokenizer,
                negatives,
                MAX_LENGTH,
            )

            q_ids = q_ids.to(device)
            q_mask = q_mask.to(device)

            p_ids = p_ids.to(device)
            p_mask = p_mask.to(device)

            n_ids = n_ids.to(device)
            n_mask = n_mask.to(device)

            optimizer.zero_grad(
                set_to_none=True
            )

            with torch.autocast(
                device_type="cuda",
                dtype=torch.float16,
            ):

                q_emb = model(
                    q_ids,
                    q_mask,
                )

                p_emb = model(
                    p_ids,
                    p_mask,
                )

                n_emb = model(
                    n_ids,
                    n_mask,
                )

                positive_similarity = (
                    F.cosine_similarity(
                        q_emb,
                        p_emb,
                    )
                )

                negative_similarity = (
                    F.cosine_similarity(
                        q_emb,
                        n_emb,
                    )
                )

                loss = torch.relu(
                    MARGIN
                    - positive_similarity
                    + negative_similarity
                ).mean()

            scaler.scale(
                loss
            ).backward()

            scaler.unscale_(
                optimizer
            )

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0,
            )

            scaler.step(
                optimizer
            )

            scaler.update()

            total_loss += loss.item()

        average_loss = (
            total_loss / len(loader)
        )

        print(
            f"Epoch "
            f"{epoch + 1}/{EPOCHS} "
            f"| Loss "
            f"{average_loss:.4f}"
        )

    torch.save(
        model.state_dict(),
        OUTPUT_FILE,
    )

    print(
        "Embedding training complete."
    )

    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()
    