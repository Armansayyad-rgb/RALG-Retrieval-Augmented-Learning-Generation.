import json
from pathlib import Path

import torch
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from tokenizers import Tokenizer

from model import SmallLM

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR, CHECKPOINTS_DIR


DATA_FILE = DATA_DIR / "instruction_train.jsonl"

TOKENIZER_FILE = DATA_DIR / "tokenizer.json"

BASE_MODEL_FILE = CHECKPOINTS_DIR / "final_model.pt"

OUTPUT_FILE = CHECKPOINTS_DIR / "instruction_model.pt"

MAX_LENGTH = 512
BATCH_SIZE = 2
GRAD_ACCUM_STEPS = 8

EPOCHS = 5
LEARNING_RATE = 5e-5
WEIGHT_DECAY = 0.01


class InstructionDataset(Dataset):
    def __init__(self, path, tokenizer):
        self.examples = []
        self.tokenizer = tokenizer

        with path.open(
            "r",
            encoding="utf-8",
        ) as f:
            for line in f:
                item = json.loads(line)

                self.examples.append(
                    item["text"]
                )

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, index):
        text = self.examples[index]

        encoded = self.tokenizer.encode(text)

        ids = encoded.ids[:MAX_LENGTH]

        return ids


def collate_batch(batch, pad_id):
    max_len = min(
        max(len(ids) for ids in batch),
        MAX_LENGTH,
    )

    inputs = []
    targets = []

    for ids in batch:
        ids = ids[:max_len]

        if len(ids) < 2:
            continue

        x = ids[:-1]
        y = ids[1:]

        target_length = max_len - 1

        x = x + [pad_id] * (
            target_length - len(x)
        )

        y = y + [-100] * (
            target_length - len(y)
        )

        inputs.append(x)
        targets.append(y)

    return (
        torch.tensor(
            inputs,
            dtype=torch.long,
        ),
        torch.tensor(
            targets,
            dtype=torch.long,
        ),
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

    pad_id = tokenizer.token_to_id(
        "<PAD>"
    )

    dataset = InstructionDataset(
        DATA_FILE,
        tokenizer,
    )

    print(
        "Instruction examples:",
        len(dataset),
    )

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        collate_fn=lambda batch: collate_batch(
            batch,
            pad_id,
        ),
        pin_memory=True,
    )

    model = SmallLM().to(device)

    base_state = torch.load(
        BASE_MODEL_FILE,
        map_location=device,
        weights_only=True,
    )

    model.load_state_dict(base_state)

    print("Loaded base model.")

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    scaler = torch.amp.GradScaler(
        "cuda"
    )

    model.train()

    global_step = 0

    for epoch in range(EPOCHS):

        running_loss = 0.0

        optimizer.zero_grad(
            set_to_none=True
        )

        for batch_index, (x, y) in enumerate(loader):

            x = x.to(
                device,
                non_blocking=True,
            )

            y = y.to(
                device,
                non_blocking=True,
            )

            with torch.autocast(
                device_type="cuda",
                dtype=torch.float16,
            ):
                _, loss = model(
                    x,
                    y,
                )

                loss = (
                    loss
                    / GRAD_ACCUM_STEPS
                )

            scaler.scale(
                loss
            ).backward()

            if (
                batch_index + 1
            ) % GRAD_ACCUM_STEPS == 0:

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

                optimizer.zero_grad(
                    set_to_none=True
                )

                global_step += 1

            running_loss += (
                loss.item()
                * GRAD_ACCUM_STEPS
            )

            if batch_index % 50 == 0:

                average_loss = (
                    running_loss
                    / (batch_index + 1)
                )

                print(
                    f"Epoch {epoch + 1}/{EPOCHS}"
                    f" | Batch {batch_index}/{len(loader)}"
                    f" | Loss {average_loss:.4f}"
                )

        print(
            f"Finished epoch {epoch + 1}"
        )

    torch.save(
        model.state_dict(),
        OUTPUT_FILE,
    )

    print(
        "Instruction tuning complete."
    )

    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()