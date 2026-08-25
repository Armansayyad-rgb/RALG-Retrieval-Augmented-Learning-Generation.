import os
from pathlib import Path

import torch
from tokenizers import Tokenizer

from model_v2 import SmallLMV2


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKENIZER_FILE = Path(
    os.environ.get(
        "TOKENIZER_FILE",
        PROJECT_ROOT / "data" / "tokenizer_v2.json",
    )
)
MODEL_FILE = Path(
    os.environ.get(
        "MODEL_FILE",
        PROJECT_ROOT / "checkpoints" / "v2" / "final_model_v2_3000.pt",
    )
)

MAX_NEW_TOKENS = 120
TEMPERATURE = 0.8
TOP_K = 40


def generate(model, tokenizer, prompt, device):
    eos_id = tokenizer.token_to_id("<EOS>")
    bos_id = tokenizer.token_to_id("<BOS>")

    token_ids = tokenizer.encode(prompt).ids

    # Remove automatic EOS before generation
    if token_ids and token_ids[-1] == eos_id:
        token_ids = token_ids[:-1]

    x = torch.tensor(
        [token_ids],
        dtype=torch.long,
        device=device,
    )

    prompt_length = x.shape[1]

    model.eval()

    with torch.no_grad():
        for _ in range(MAX_NEW_TOKENS):
            x_input = x[:, -model.context_length:]

            logits, _ = model(x_input)

            logits = logits[:, -1, :] / TEMPERATURE

            k = min(TOP_K, logits.size(-1))

            top_values, _ = torch.topk(
                logits,
                k,
            )

            cutoff = top_values[:, -1].unsqueeze(-1)

            logits = torch.where(
                logits < cutoff,
                torch.full_like(
                    logits,
                    float("-inf"),
                ),
                logits,
            )

            probabilities = torch.softmax(
                logits,
                dim=-1,
            )

            next_token = torch.multinomial(
                probabilities,
                num_samples=1,
            )

            x = torch.cat(
                [x, next_token],
                dim=1,
            )

            if next_token.item() == eos_id:
                break

    new_tokens = x[
        0,
        prompt_length:
    ].tolist()

    new_tokens = [
        token_id
        for token_id in new_tokens
        if token_id not in (
            bos_id,
            eos_id,
        )
    ]

    return tokenizer.decode(new_tokens)


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

    model = SmallLMV2().to(device)

    state = torch.load(
        MODEL_FILE,
        map_location=device,
        weights_only=True,
    )

    model.load_state_dict(state)
    model.eval()

    print("V2 model loaded.")
    print("Type 'quit' to exit.")

    while True:
        prompt = input("\nPrompt: ").strip()

        if prompt.lower() == "quit":
            break

        if not prompt:
            continue

        output = generate(
            model,
            tokenizer,
            prompt,
            device,
        )

        print("\nModel:", output)


if __name__ == "__main__":
    main()
