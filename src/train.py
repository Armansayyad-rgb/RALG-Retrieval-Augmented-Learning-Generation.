import os
import math
from pathlib import Path
import torch

from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from tokenizers import Tokenizer

from model import SmallLM
from config import CHECKPOINTS_DIR, DATA_DIR, MODEL_CONFIG, TOKENIZER_FILE


DATA_FILE = Path(os.environ.get("TRAIN_DATA_FILE", str(DATA_DIR / "train.txt")))
CHECKPOINT_DIR = Path(os.environ.get("TRAIN_CHECKPOINT_DIR", str(CHECKPOINTS_DIR)))

BATCH_SIZE = 4
SEQ_LEN = 256
EPOCHS = 3
LEARNING_RATE = 3e-4
WEIGHT_DECAY = 0.1
GRAD_ACCUM_STEPS = 4
SAVE_EVERY = 200


class TextDataset(Dataset):
    def __init__(self, token_ids, seq_len):
        self.token_ids = token_ids
        self.seq_len = seq_len

    def __len__(self):
        return max(0, (len(self.token_ids) - 1) // self.seq_len)

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1

        chunk = self.token_ids[start:end]

        x = torch.tensor(chunk[:-1], dtype=torch.long)
        y = torch.tensor(chunk[1:], dtype=torch.long)

        return x, y


def save_checkpoint(model, optimizer, step, path):
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "step": step,
        },
        path,
    )


def main():
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"

    print("Device:", device)

    tokenizer = Tokenizer.from_file(TOKENIZER_FILE)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    print("Characters:", len(text))

    encoded = tokenizer.encode(text)

    token_ids = encoded.ids

    print("Tokens:", len(token_ids))

    dataset = TextDataset(
        token_ids=token_ids,
        seq_len=SEQ_LEN,
    )

    print("Training sequences:", len(dataset))

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        drop_last=True,
        pin_memory=True,
    )

    model = SmallLM().to(device)

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    amp_enabled = device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    model.train()

    global_step = 0

    for epoch in range(EPOCHS):
        running_loss = 0.0

        optimizer.zero_grad(set_to_none=True)

        for batch_idx, (x, y) in enumerate(loader):
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            with torch.autocast(device_type=device, dtype=torch.float16,
                                enabled=amp_enabled):
                _, loss = model(x, y)

                loss = loss / GRAD_ACCUM_STEPS

            scaler.scale(loss).backward()

            if (batch_idx + 1) % GRAD_ACCUM_STEPS == 0:
                scaler.unscale_(optimizer)

                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    max_norm=1.0,
                )

                scaler.step(optimizer)
                scaler.update()

                optimizer.zero_grad(set_to_none=True)

                global_step += 1

            running_loss += loss.item() * GRAD_ACCUM_STEPS

            if batch_idx % 10 == 0:
                avg_loss = running_loss / (batch_idx + 1)

                print(
                    f"Epoch {epoch + 1}/{EPOCHS} "
                    f"| Batch {batch_idx}/{len(loader)} "
                    f"| Loss {avg_loss:.4f}"
                )

            if global_step > 0 and global_step % SAVE_EVERY == 0:
                path = os.path.join(
                    CHECKPOINT_DIR,
                    f"checkpoint_step_{global_step}.pt",
                )

                save_checkpoint(
                    model,
                    optimizer,
                    global_step,
                    path,
                )

        epoch_path = os.path.join(
            CHECKPOINT_DIR,
            f"epoch_{epoch + 1}.pt",
        )

        save_checkpoint(
            model,
            optimizer,
            global_step,
            epoch_path,
        )

        print("Saved:", epoch_path)

    final_path = os.path.join(
        CHECKPOINT_DIR,
        "final_model.pt",
    )

    torch.save(model.state_dict(), final_path)

    print("Training complete.")
    print("Final model:", final_path)


if __name__ == "__main__":
    main()