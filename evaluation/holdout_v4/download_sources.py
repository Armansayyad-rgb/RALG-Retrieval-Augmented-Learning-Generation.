from __future__ import annotations

import hashlib
import json
import pathlib
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
SPECS = ROOT / "source_specs.json"
RAW_DIR = ROOT / "sources" / "raw"
NORM_DIR = ROOT / "sources" / "normalized"
MANIFEST = ROOT / "sources_manifest.jsonl"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


def main() -> None:
    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    acquired = datetime.now(timezone.utc).isoformat()

    for src in specs["sources"]:
        doc_id = src["document_id"]
        req = urllib.request.Request(src["raw_url"], headers={"User-Agent": "RALG-Holdout-V4/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
            final_url = response.geturl()
        normalized = normalize(raw)

        raw_path = RAW_DIR / f"{doc_id}.raw"
        norm_path = NORM_DIR / f"{doc_id}.txt"
        raw_path.write_bytes(raw)
        norm_path.write_bytes(normalized)

        rows.append({
            **src,
            "acquired_at_utc": acquired,
            "resolved_url": final_url,
            "raw_path": raw_path.relative_to(ROOT).as_posix(),
            "normalized_path": norm_path.relative_to(ROOT).as_posix(),
            "raw_bytes": len(raw),
            "normalized_bytes": len(normalized),
            "raw_sha256": sha256_bytes(raw),
            "normalized_sha256": sha256_bytes(normalized),
            "normalization": "UTF-8 decode; CRLF/CR to LF; exactly one terminal newline if absent",
            "license_review_status": "PENDING_HUMAN_REVIEW"
        })

    MANIFEST.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    print(f"acquired {len(rows)} sources -> {MANIFEST}")


if __name__ == "__main__":
    main()
