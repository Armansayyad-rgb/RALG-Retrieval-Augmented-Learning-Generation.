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


DATA_FILE = DATA_DIR / "instruction_train_v2.jsonl"

TOKENIZER_FILE = DATA_DIR / "tokenizer.json"

BASE_MODEL_FILE = CHECKPOINTS_DIR / "final_model.pt"

OUTPUT_FILE = CHECKPOINTS_DIR / "instruction_model_v2.pt"

MAX_LENGTH = 512
BATCH_SIZE = 2
GRAD_ACCUM_STEPS = 8

EPOCHS = 5
LEARNING_RATE = 5e-5
WEIGHT_DECAY = 0.01


class InstructionDataset(Dataset):
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

    def __getitem__(self, index):
        return self.examples[index]


def build_training_example(
    tokenizer,
    prompt,
    answer,
):
    bos_id = tokenizer.token_to_id("<BOS>")
    eos_id = tokenizer.token_to_id("<EOS>")

    prompt_ids = tokenizer.encode(prompt).ids
    answer_ids = tokenizer.encode(answer).ids

    # Remove automatically inserted BOS/EOS.
    prompt_ids = [
        token_id
        for token_id in prompt_ids
        if token_id not in (bos_id, eos_id)
    ]

    answer_ids = [
        token_id
        for token_id in answer_ids
        if token_id not in (bos_id, eos_id)
    ]

    # Reserve room for:
    # BOS + answer + final EOS
    max_prompt_length = (
        MAX_LENGTH
        - len(answer_ids)
        - 2
    )

    if max_prompt_length < 1:
        answer_ids = answer_ids[
            : MAX_LENGTH - 2
        ]
        max_prompt_length = 1

    # Keep the END of long prompts because it contains
    # <ANSWER>, Question:, and Answer:
    prompt_ids = prompt_ids[
        -max_prompt_length:
    ]

    full_ids = (
        [bos_id]
        + prompt_ids
        + answer_ids
        + [eos_id]
    )

    input_ids = full_ids[:-1]
    labels = full_ids[1:]

    # Number of input tokens before the answer begins.
    answer_start = (
        1 + len(prompt_ids)
    )

    # Ignore prompt loss.
    for i in range(
        min(
            answer_start - 1,
            len(labels),
        )
    ):
        labels[i] = -100

    return input_ids, labels

def collate_batch(
    batch,
    tokenizer,
):
    pad_id = tokenizer.token_to_id("<PAD>")

    processed = [
        build_training_example(
            tokenizer,
            item["prompt"],
            item["answer"],
        )
        for item in batch
    ]

    max_len = max(
        len(x[0])
        for x in processed
    )

    inputs = []
    labels = []

    for input_ids, target_ids in processed:

        pad_amount = (
            max_len
            - len(input_ids)
        )

        input_ids = (
            input_ids
            + [pad_id] * pad_amount
        )

        target_ids = (
            target_ids
            + [-100] * pad_amount
        )

        inputs.append(input_ids)
        labels.append(target_ids)

    return (
        torch.tensor(
            inputs,
            dtype=torch.long,
        ),
        torch.tensor(
            labels,
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

    dataset = InstructionDataset(
        DATA_FILE
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
            tokenizer,
        ),
        pin_memory=True,
    )

    model = SmallLM().to(device)

    base_state = torch.load(
        BASE_MODEL_FILE,
        map_location=device,
        weights_only=True,
    )

    model.load_state_dict(
        base_state
    )

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

    for epoch in range(EPOCHS):

        running_loss = 0.0

        optimizer.zero_grad(
            set_to_none=True
        )

        for batch_index, (
            x,
            y,
        ) in enumerate(loader):

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
        "Answer-only instruction tuning complete."
    )

    print(
        "Saved:",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()