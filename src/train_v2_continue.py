import time
import os
from pathlib import Path

import torch
from torch.optim import AdamW

from model_v2 import SmallLMV2
from config import CHECKPOINTS_DIR, DATA_DIR


TOKEN_CACHE = Path(os.environ.get(
    "TOKEN_CACHE", str(DATA_DIR / "wikitext_v2_tokens.pt")
))

CHECKPOINT_DIR = Path(os.environ.get(
    "TRAIN_CHECKPOINT_DIR", str(CHECKPOINTS_DIR / "v2")
))

RESUME_FILE = CHECKPOINT_DIR / "step_500.pt"


SEQ_LEN = 256
MICRO_BATCH_SIZE = 1
GRAD_ACCUM_STEPS = 16

LEARNING_RATE = 3e-4
MIN_LEARNING_RATE = 3e-5
WEIGHT_DECAY = 0.1

# Continue until total optimizer step 3000
TARGET_STEP = 3000

SAVE_EVERY = 250
LOG_EVERY = 10


def get_lr(step):
    # We're continuing from an already-warmed-up model.
    start_decay_step = 500

    if step <= start_decay_step:
        return LEARNING_RATE

    progress = (
        step - start_decay_step
    ) / max(
        1,
        TARGET_STEP - start_decay_step,
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


def get_batch(tokens, device):
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

        x_list.append(chunk[:-1])
        y_list.append(chunk[1:])

    x = torch.stack(x_list).to(
        device,
        non_blocking=True,
    )

    y = torch.stack(y_list).to(
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
        f"\nSaved checkpoint: {path}"
    )


def main():
    if not torch.cuda.is_available():
        import warnings
        warnings.warn(
            "CUDA GPU not detected - training will be slow on CPU. "
            "Continuing with CPU training.",
            UserWarning,
        )

    device = "cuda" if torch.cuda.is_available() else "cpu"

    print("Device:", device)

    print("Loading token cache...")

    tokens = torch.load(
        TOKEN_CACHE,
        weights_only=True,
    )

    print(
        "Corpus tokens:",
        f"{len(tokens):,}",
    )

    model = SmallLMV2().to(device)

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        betas=(0.9, 0.95),
        eps=1e-8,
        weight_decay=WEIGHT_DECAY,
    )

    amp_enabled = device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    print(
        "Loading checkpoint:",
        RESUME_FILE,
    )

    checkpoint = torch.load(
        RESUME_FILE,
        map_location=device,
        weights_only=False,
    )

    model.load_state_dict(
        checkpoint["model"]
    )

    optimizer.load_state_dict(
        checkpoint["optimizer"]
    )

    scaler.load_state_dict(
        checkpoint["scaler"]
    )

    start_step = checkpoint["step"]

    print(
        "Resuming from step:",
        start_step,
    )

    model.train()

    start_time = time.time()

    for step in range(
        start_step + 1,
        TARGET_STEP + 1,
    ):

        optimizer.zero_grad(
            set_to_none=True
        )

        total_loss = 0.0

        for _ in range(
            GRAD_ACCUM_STEPS
        ):
            x, y = get_batch(
                tokens,
                device,
            )

            with torch.autocast(device_type=device, dtype=torch.float16,
                                enabled=amp_enabled):
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

            total_loss += loss.item()

        scaler.unscale_(
            optimizer
        )

        grad_norm = (
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0,
            )
        )

        lr = get_lr(step)

        for group in optimizer.param_groups:
            group["lr"] = lr

        scaler.step(
            optimizer
        )

        scaler.update()

        avg_loss = (
            total_loss
            / GRAD_ACCUM_STEPS
        )

        if (
            step % LOG_EVERY == 0
            or step == start_step + 1
        ):
            elapsed = (
                time.time()
                - start_time
            )

            new_steps = (
                step - start_step
            )

            tokens_processed = (
                new_steps
                * GRAD_ACCUM_STEPS
                * MICRO_BATCH_SIZE
                * SEQ_LEN
            )

            tok_per_sec = (
                tokens_processed
                / max(elapsed, 1e-6)
            )

            allocated = torch.cuda.memory_allocated() / 1024**3 if amp_enabled else 0
            reserved = torch.cuda.memory_reserved() / 1024**3 if amp_enabled else 0

            print(
                f"Step {step}/{TARGET_STEP}"
                f" | Loss {avg_loss:.4f}"
                f" | LR {lr:.6f}"
                f" | Grad {float(grad_norm):.3f}"
                f" | {tok_per_sec:.0f} tok/s"
                f" | VRAM {allocated:.2f} GB"
                f" / {reserved:.2f} GB reserved"
            )

        if step % SAVE_EVERY == 0:
            save_checkpoint(
                model,
                optimizer,
                scaler,
                step,
            )

    final_file = (
        CHECKPOINT_DIR
        / "final_model_v2_3000.pt"
    )

    torch.save(
        model.state_dict(),
        final_file,
    )

    print("\nTraining complete.")
    print(
        "Final model:",
        final_file,
    )


if __name__ == "__main__":
    main()
