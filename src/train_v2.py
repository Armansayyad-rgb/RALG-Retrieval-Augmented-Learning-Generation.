import os
import time
from pathlib import Path

import torch
from torch.optim import AdamW
from tokenizers import Tokenizer

from model_v2 import SmallLMV2

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA_DIR, CHECKPOINTS_DIR


DATA_FILE = DATA_DIR / "wikitext_v2.txt"

TOKENIZER_FILE = DATA_DIR / "tokenizer_v2.json"

CHECKPOINT_DIR = CHECKPOINTS_DIR / "v2"

TOKEN_CACHE = DATA_DIR / "wikitext_v2_tokens.pt"


# RTX 3050 6GB-safe starting settings
SEQ_LEN = 256
MICRO_BATCH_SIZE = 1

# 16 micro-batches = effective batch of 4096 tokens
GRAD_ACCUM_STEPS = 16

LEARNING_RATE = 3e-4
MIN_LEARNING_RATE = 3e-5

WEIGHT_DECAY = 0.1
WARMUP_STEPS = 50

# Start with 500 optimizer updates.
# We can increase this after checking speed/VRAM/loss.
MAX_STEPS = 500

SAVE_EVERY = 100
LOG_EVERY = 10


def get_lr(step):
    if step < WARMUP_STEPS:
        return (
            LEARNING_RATE
            * (step + 1)
            / WARMUP_STEPS
        )

    progress = (
        step - WARMUP_STEPS
    ) / max(
        1,
        MAX_STEPS - WARMUP_STEPS,
    )

    progress = min(
        max(progress, 0.0),
        1.0,
    )

    cosine = 0.5 * (
        1.0
        + torch.cos(
            torch.tensor(
                progress * 3.1415926535
            )
        ).item()
    )

    return (
        MIN_LEARNING_RATE
        + cosine
        * (
            LEARNING_RATE
            - MIN_LEARNING_RATE
        )
    )


def load_tokens(tokenizer):
    if TOKEN_CACHE.exists():
        print(
            "Loading cached tokens:",
            TOKEN_CACHE,
        )

        return torch.load(
            TOKEN_CACHE,
            weights_only=True,
        )

    print(
        "Reading training corpus..."
    )

    text = DATA_FILE.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    print(
        "Characters:",
        len(text),
    )

    print(
        "Tokenizing corpus..."
    )

    encoded = tokenizer.encode(
        text
    )

    tokens = torch.tensor(
        encoded.ids,
        dtype=torch.int32,
    )

    torch.save(
        tokens,
        TOKEN_CACHE,
    )

    print(
        "Token cache saved:",
        TOKEN_CACHE,
    )

    return tokens


def get_batch(
    tokens,
    device,
):
    max_start = (
        len(tokens)
        - SEQ_LEN
        - 1
    )

    starts = torch.randint(
        0,
        max_start,
        (MICRO_BATCH_SIZE,),
    )

    x_list = []
    y_list = []

    for start in starts.tolist():
        chunk = tokens[
            start:
            start + SEQ_LEN + 1
        ].long()

        x_list.append(
            chunk[:-1]
        )

        y_list.append(
            chunk[1:]
        )

    x = torch.stack(
        x_list
    ).to(
        device,
        non_blocking=True,
    )

    y = torch.stack(
        y_list
    ).to(
        device,
        non_blocking=True,
    )

    return x, y


def save_checkpoint(
    model,
    optimizer,
    scaler,
    step,
):
    path = (
        CHECKPOINT_DIR
        / f"step_{step}.pt"
    )

    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scaler": scaler.state_dict(),
            "step": step,
        },
        path,
    )

    print(
        "\nSaved checkpoint:",
        path,
    )


def main():
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA GPU was not detected."
        )

    device = "cuda"

    CHECKPOINT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "GPU:",
        torch.cuda.get_device_name(0),
    )

    print(
        "VRAM GB:",
        round(
            torch.cuda.get_device_properties(
                0
            ).total_memory
            / 1024**3,
            2,
        ),
    )

    tokenizer = (
        Tokenizer.from_file(
            str(TOKENIZER_FILE)
        )
    )

    tokens = load_tokens(
        tokenizer
    )

    print(
        "Corpus tokens:",
        f"{len(tokens):,}",
    )

    print(
        "Approx corpus sequences:",
        f"{len(tokens) // SEQ_LEN:,}",
    )

    model = SmallLMV2().to(
        device
    )

    total_params = sum(
        p.numel()
        for p in model.parameters()
    )

    print(
        "Model parameters:",
        f"{total_params:,}",
    )

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        betas=(0.9, 0.95),
        eps=1e-8,
        weight_decay=WEIGHT_DECAY,
    )

    scaler = torch.amp.GradScaler(
        "cuda"
    )

    model.train()

    optimizer.zero_grad(
        set_to_none=True
    )

    start_time = time.time()

    for step in range(
        1,
        MAX_STEPS + 1,
    ):

        accumulated_loss = 0.0

        for _ in range(
            GRAD_ACCUM_STEPS
        ):

            x, y = get_batch(
                tokens,
                device,
            )

            with torch.autocast(
                device_type="cuda",
                dtype=torch.float16,
            ):

                _, loss = model(
                    x,
                    y,
                )

                scaled_loss = (
                    loss
                    / GRAD_ACCUM_STEPS
                )

            scaler.scale(
                scaled_loss
            ).backward()

            accumulated_loss += (
                loss.item()
            )

        scaler.unscale_(
            optimizer
        )

        grad_norm = (
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=1.0,
            )
        )

        lr = get_lr(
            step - 1
        )

        for group in (
            optimizer.param_groups
        ):
            group["lr"] = lr

        scaler.step(
            optimizer
        )

        scaler.update()

        optimizer.zero_grad(
            set_to_none=True
        )

        average_loss = (
            accumulated_loss
            / GRAD_ACCUM_STEPS
        )

        if (
            step == 1
            or step % LOG_EVERY == 0
        ):

            elapsed = (
                time.time()
                - start_time
            )

            tokens_processed = (
                step
                * GRAD_ACCUM_STEPS
                * MICRO_BATCH_SIZE
                * SEQ_LEN
            )

            tokens_per_second = (
                tokens_processed
                / max(elapsed, 1e-6)
            )

            allocated = (
                torch.cuda.memory_allocated()
                / 1024**3
            )

            reserved = (
                torch.cuda.memory_reserved()
                / 1024**3
            )

            print(
                f"Step {step}/{MAX_STEPS}"
                f" | Loss {average_loss:.4f}"
                f" | LR {lr:.6f}"
                f" | Grad {float(grad_norm):.3f}"
                f" | {tokens_per_second:.0f} tok/s"
                f" | VRAM {allocated:.2f} GB"
                f" / {reserved:.2f} GB reserved"
            )

        if (
            step % SAVE_EVERY == 0
        ):
            save_checkpoint(
                model,
                optimizer,
                scaler,
                step,
            )

    final_file = (
        CHECKPOINT_DIR
        / "final_model_v2.pt"
    )

    torch.save(
        model.state_dict(),
        final_file,
    )

    print(
        "\nTraining complete."
    )

    print(
        "Final model:",
        final_file,
    )


if __name__ == "__main__":
    main()