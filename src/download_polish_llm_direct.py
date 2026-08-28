"""Download the Polish LLM weights via a streaming, chunked HTTP request.

Why a custom downloader (vs huggingface_hub.hf_hub_download):

The first attempt using ``hf_hub_download`` stalled for 10+ minutes
with no bytes written, even though direct HTTP requests to the same
file succeed in under a second. The exact cause isn't worth chasing
(hf_hub_download's internal metadata-fetch phase can hang on
unauthenticated, rate-limited requests). A plain ``requests.get`` with
``stream=True`` gives us:

- Predictable behaviour (we control the request and the resume logic).
- Visible progress (one line per chunk downloaded).
- Trivial resume: if the run is interrupted, just re-run; the script
  picks up at the byte offset recorded in the sidecar ``.partial`` file.

Targets ``Qwen/Qwen2.5-1.5B-Instruct`` on HuggingFace Hub and pulls
``model.safetensors`` (~3.09 GB) directly into the directory the
loader expects:
``<CHECKPOINTS_DIR>/qwen2.5-1.5b-instruct/``.

Usage:
    python download_polish_llm_direct.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from config import CHECKPOINTS_DIR  # noqa: E402

REPO_ID = "Qwen/Qwen2.5-1.5B-Instruct"
REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
FILENAME = "model.safetensors"
TARGET_DIR = Path(
    os.environ.get(
        "POLISH_LLM_DIR",
        str(CHECKPOINTS_DIR / "qwen2.5-1.5b-instruct"),
    )
).expanduser().resolve()
PARTIAL_PATH = TARGET_DIR / "model.safetensors.partial"
FINAL_PATH = TARGET_DIR / FILENAME

CHUNK_BYTES = 1 * 1024 * 1024       # 1 MB chunks (smaller = better recovery)
PROGRESS_EVERY_BYTES = 50 * 1024 * 1024  # log every 50 MB
READ_TIMEOUT_S = 60                 # per-read timeout (was 30s, too short)
MAX_CHUNK_RETRIES = 5               # retries per chunk on transient errors
RETRY_BACKOFF_S = 3                # base delay between retries


def _human_bytes(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.2f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def main() -> int:
    try:
        import requests
    except ImportError:
        print("ERROR: requests is not installed. "
              "Run: pip install requests", file=sys.stderr)
        return 1

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    url = (
        f"https://huggingface.co/{REPO_ID}/resolve/{REVISION}/{FILENAME}"
    )

    # Skip if a complete final file is already in place.
    if FINAL_PATH.exists():
        size = FINAL_PATH.stat().st_size
        if size > 3_000_000_000:
            print(f"[download] {FINAL_PATH} already present "
                  f"({_human_bytes(size)}); skipping.")
            PARTIAL_PATH.unlink(missing_ok=True)
            return 0
        print(f"[download] {FINAL_PATH} exists but is small "
              f"({_human_bytes(size)}); will redownload.")

    # Determine the byte offset to resume from.
    start_byte = 0
    if PARTIAL_PATH.exists():
        start_byte = PARTIAL_PATH.stat().st_size
        print(f"[download] resuming from byte {start_byte} "
              f"({_human_bytes(start_byte)})")

    headers = {"User-Agent": "download_polish_llm_direct/1.0"}
    if start_byte > 0:
        headers["Range"] = f"bytes={start_byte}-"

    print(f"[download] GET {url}")
    try:
        resp = requests.get(
            url, headers=headers, stream=True, timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"ERROR: HTTP request failed: {exc}", file=sys.stderr)
        return 1

    # If we asked for a range but got 200 OK, the server ignored us
    # and is sending the whole file from byte 0. Discard any partial
    # bytes in that case.
    if start_byte > 0 and resp.status_code == 200:
        print("[download] server returned 200 instead of 206; "
              "restarting from byte 0.")
        start_byte = 0
        PARTIAL_PATH.unlink(missing_ok=True)

    total_bytes = int(resp.headers.get("Content-Length", 0)) + start_byte
    print(f"[download] total: {_human_bytes(total_bytes) if total_bytes else 'unknown'}")
    print(f"[download] writing to {PARTIAL_PATH}")

    t0 = time.time()
    bytes_since_log = 0

    mode = "ab" if start_byte > 0 else "wb"
    total_written = start_byte
    next_request_offset = start_byte

    try:
        with open(PARTIAL_PATH, mode) as f:
            # Retry loop: on transient connection failure, re-issue
            # the GET with Range starting at the next byte we haven't
            # yet written. This keeps the partial file growing past
            # sporadic read timeouts and broken-pipe errors that
            # ``requests`` would otherwise surface as fatal.
            for attempt in range(1, MAX_CHUNK_RETRIES + 1):
                if next_request_offset > start_byte:
                    headers["Range"] = f"bytes={next_request_offset}-"
                    print(
                        f"[download] retry {attempt}/{MAX_CHUNK_RETRIES}: "
                        f"re-GET at byte {next_request_offset} "
                        f"({_human_bytes(next_request_offset)})",
                        flush=True,
                    )
                    resp = requests.get(
                        url, headers=headers, stream=True,
                        timeout=READ_TIMEOUT_S,
                    )
                    resp.raise_for_status()
                    if resp.status_code == 200:
                        print("[download] server returned 200 instead of "
                              "206; restarting from byte 0.")
                        next_request_offset = 0
                        f.seek(0)
                        f.truncate()
                        headers["Range"] = "bytes=0-"

                try:
                    for chunk in resp.iter_content(chunk_size=CHUNK_BYTES):
                        if not chunk:
                            continue
                        f.write(chunk)
                        total_written += len(chunk)
                        next_request_offset += len(chunk)
                        bytes_since_log += len(chunk)
                        if bytes_since_log >= PROGRESS_EVERY_BYTES:
                            bytes_since_log = 0
                            elapsed = time.time() - t0
                            if elapsed > 0:
                                speed = total_written / elapsed
                                total_str = (
                                    _human_bytes(total_bytes)
                                    if total_bytes else "?"
                                )
                                print(
                                    f"[download] {_human_bytes(total_written)} / "
                                    f"{total_str} "
                                    f"({speed / 1024 ** 2:.1f} MB/s)",
                                    flush=True,
                                )
                except (requests.RequestException,
                        ConnectionError, TimeoutError) as exc:
                    if attempt < MAX_CHUNK_RETRIES:
                        backoff = RETRY_BACKOFF_S * (2 ** (attempt - 1))
                        print(
                            f"[download] chunk loop failed at byte "
                            f"{next_request_offset} "
                            f"({_human_bytes(next_request_offset)}): "
                            f"{exc}",
                            flush=True,
                        )
                        print(
                            f"[download] backing off {backoff}s before "
                            f"retry...",
                            flush=True,
                        )
                        time.sleep(backoff)
                        continue
                    # Final attempt failed; surface the error to the
                    # outer handler.
                    raise

                # The loop completed without raising; we're done.
                break
    except KeyboardInterrupt:
        print("\n[download] interrupted by user; partial bytes retained "
              f"at {PARTIAL_PATH}. Re-run to resume.")
        return 1
    except (requests.RequestException, ConnectionError, TimeoutError) as exc:
        print(f"\nERROR: connection lost mid-download: {exc}",
              file=sys.stderr)
        print("Re-run this script to resume.", file=sys.stderr)
        return 1

    # Promote the partial to the final path on success.
    final_size = PARTIAL_PATH.stat().st_size
    if final_size < 3_000_000_000:
        print(
            f"\nERROR: downloaded artifact is suspiciously small "
            f"({final_size} bytes). Partial file retained at {PARTIAL_PATH}.",
            file=sys.stderr,
        )
        return 1
    PARTIAL_PATH.replace(FINAL_PATH)
    elapsed = time.time() - t0
    speed = final_size / elapsed if elapsed > 0 else 0
    print()
    print(f"[download] DONE: {FINAL_PATH}")
    print(f"[download] size:  {_human_bytes(final_size)}")
    print(f"[download] time:  {elapsed:.1f}s ({speed / 1024 ** 2:.1f} MB/s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
