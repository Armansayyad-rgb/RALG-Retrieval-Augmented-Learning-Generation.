import os
from pathlib import Path

from datasets import load_dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = Path(
    os.environ.get(
        "RALG_WIKITEXT_OUTPUT",
        PROJECT_ROOT / "data" / "wikitext_v2.txt",
    )
)

TARGET_CHARS = 60_000_000  # roughly enough for a first serious run


def main():
    print("Loading WikiText-103...")

    dataset = load_dataset(
        "Salesforce/wikitext",
        "wikitext-103-raw-v1",
        split="train",
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    total_chars = 0
    kept_lines = 0

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        for row in dataset:
            text = row["text"].strip()

            if not text:
                continue

            f.write(text + "\n")

            total_chars += len(text)
            kept_lines += 1

            if total_chars >= TARGET_CHARS:
                break

    print("Saved:", OUTPUT_FILE)
    print("Characters:", total_chars)
    print("Lines:", kept_lines)
    print(
        "Approx size MB:",
        round(
            OUTPUT_FILE.stat().st_size
            / 1024**2,
            2,
        ),
    )


if __name__ == "__main__":
    main()
