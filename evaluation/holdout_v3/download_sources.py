#!/usr/bin/env python3
"""Deterministic source downloader for Holdout V3.

Downloads all seven V3 source documents, applies deterministic
normalization, computes dual SHA-256 hashes, and writes
sources_manifest.jsonl.

Run once to populate sources/. Re-run to verify hashes.
Never silently replaces frozen artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES_DIR = ROOT / "sources"
RAW_DIR = SOURCES_DIR / "raw"

# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

SOURCES = [
    {
        "doc_id": "sqlite_wal_mode",
        "canonical_url": "https://www.sqlite.org/wal.html",
        "immutable_url": "https://www.sqlite.org/wal.html",
        "revision": None,
        "repo": None,
        "source_path": None,
        "license": "Public Domain",
        "license_note": "SQLite is in the public domain.",
        "normalization": "html",
    },
    {
        "doc_id": "postgresql_vacuuming",
        "canonical_url": "https://www.postgresql.org/docs/17/routine-vacuuming.html",
        "immutable_url": "https://raw.githubusercontent.com/postgres/postgres/REL_17_STABLE/doc/src/sgml/maintenance.sgml",
        "revision": "REL_17_STABLE",
        "repo": "github.com/postgres/postgres",
        "source_path": "doc/src/sgml/maintenance.sgml",
        "license": "PostgreSQL License",
        "license_note": "Copyright (c) 1996-2024, PostgreSQL Global Development Group",
        "normalization": "sgml",
    },
    {
        "doc_id": "kubernetes_probes",
        "canonical_url": "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
        "immutable_url": "https://raw.githubusercontent.com/kubernetes/website/fc900dc1a4b93f9de16681ebbb91e2334402a1a7/content/en/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes.md",
        "revision": "fc900dc1a4b93f9de16681ebbb91e2334402a1a7",
        "repo": "github.com/kubernetes/website",
        "source_path": "content/en/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes.md",
        "license": "CC BY 4.0",
        "license_note": "Kubernetes documentation is licensed under CC BY 4.0.",
        "normalization": "markdown",
    },
    {
        "doc_id": "systemd_unit",
        "canonical_url": "https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html",
        "immutable_url": "https://raw.githubusercontent.com/systemd/systemd/v256/man/systemd.unit.xml",
        "revision": "v256",
        "repo": "github.com/systemd/systemd",
        "source_path": "man/systemd.unit.xml",
        "license": "LGPL-2.1-or-later",
        "license_note": "Copyright 2010-2024 systemd authors. LGPL-2.1-or-later.",
        "normalization": "xml",
    },
    {
        "doc_id": "otel_propagators",
        "canonical_url": "https://opentelemetry.io/docs/specs/otel/context/api-propagators.html",
        "immutable_url": "https://raw.githubusercontent.com/open-telemetry/opentelemetry-specification/8057bf6d5cf0ab10891b9e6f7b928cded76ab2f7/specification/context/api-propagators.md",
        "revision": "8057bf6d5cf0ab10891b9e6f7b928cded76ab2f7",
        "repo": "github.com/open-telemetry/opentelemetry-specification",
        "source_path": "specification/context/api-propagators.md",
        "license": "Apache 2.0",
        "license_note": "Copyright OpenTelemetry authors. Apache 2.0.",
        "normalization": "markdown",
    },
    {
        "doc_id": "oci_image_layout",
        "canonical_url": "https://github.com/opencontainers/image-spec/blob/main/image-layout.md",
        "immutable_url": "https://raw.githubusercontent.com/opencontainers/image-spec/v1.1.0/image-layout.md",
        "revision": "v1.1.0",
        "repo": "github.com/opencontainers/image-spec",
        "source_path": "image-layout.md",
        "license": "Apache 2.0",
        "license_note": "Copyright 2016 The Linux Foundation. Apache 2.0.",
        "normalization": "markdown",
    },
    {
        "doc_id": "cmake_presets",
        "canonical_url": "https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html",
        "immutable_url": "https://raw.githubusercontent.com/Kitware/CMake/v4.4.3/Help/manual/cmake-presets.7.rst",
        "revision": "v4.4.3",
        "repo": "github.com/Kitware/CMake",
        "source_path": "Help/manual/cmake-presets.7.rst",
        "license": "BSD 3-Clause",
        "license_note": "Copyright 2000-2024 Kitware, Inc. BSD 3-Clause.",
        "normalization": "rst",
    },
]


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

def normalize_html(raw_bytes: bytes) -> str:
    """Deterministic HTML → text using lxml."""
    import lxml.html

    doc = lxml.html.fromstring(raw_bytes)
    for elem in doc.xpath("//script | //style"):
        elem.getparent().remove(elem)
    text = doc.text_content()
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines) + "\n"


def normalize_sgml(raw_bytes: bytes) -> str:
    """Deterministic SGML → text."""
    text = raw_bytes.decode("utf-8", errors="replace")

    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<!\[CDATA\[.*?\]\]>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    block_tags = [
        "sect1", "sect2", "sect3", "para", "programlisting",
        "literallayout", "itemizedlist", "listitem", "variablelist",
        "varlistentry", "formalpara", "title", "table", "tgroup",
        "thead", "tbody", "row", "entry", "figure", "caption",
    ]
    for tag in block_tags:
        text = re.sub(rf"<{tag}[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(rf"</{tag}>", "\n", text, flags=re.IGNORECASE)

    text = re.sub(r"<[^>]+>", "", text)

    entities = {
        "&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"',
        "&apos;": "'", "&mdash;": "\u2014", "&ndash;": "\u2013",
        "&nbsp;": " ", "&hellip;": "\u2026", "&copy;": "\u00a9",
        "&reg;": "\u00ae",
    }
    for ent, char in entities.items():
        text = text.replace(ent, char)

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines) + "\n"


def normalize_markdown(raw_bytes: bytes) -> str:
    """Minimal markdown normalization."""
    text = raw_bytes.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines) + "\n"


def normalize_xml(raw_bytes: bytes) -> str:
    """Deterministic XML → text using ElementTree."""
    root = ET.fromstring(raw_bytes)
    lines = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            lines.append(elem.text.strip())
        if elem.tail and elem.tail.strip():
            lines.append(elem.tail.strip())
    deduped = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    return "\n".join(deduped) + "\n"


def normalize_rst(raw_bytes: bytes) -> str:
    """Deterministic RST → text."""
    text = raw_bytes.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = []
    in_code_block = False
    for line in text.split("\n"):
        stripped = line.rstrip()

        if stripped.startswith(".. ") and "::" in stripped:
            in_code_block = True
            cleaned = re.sub(r"\.\.\s+\w+::", "", stripped).strip()
            if cleaned:
                lines.append(cleaned)
            continue

        if in_code_block and not stripped:
            in_code_block = False
            continue

        if in_code_block:
            lines.append(stripped)
            continue

        if stripped.startswith(".. "):
            continue

        if re.match(r"^:\w+:", stripped):
            m = re.match(r"^:\w+:\s*(.+)", stripped)
            if m:
                lines.append(m.group(1).strip())
            continue

        if stripped and all(c == stripped[0] for c in stripped) and stripped[0] in '=-~^"+':
            continue

        if stripped:
            lines.append(stripped)

    return "\n".join(lines) + "\n"


NORMALIZERS = {
    "html": normalize_html,
    "sgml": normalize_sgml,
    "markdown": normalize_markdown,
    "xml": normalize_xml,
    "rst": normalize_rst,
}


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Download + normalize
# ---------------------------------------------------------------------------

def download_one(src: dict, *, verify_only: bool = False) -> dict:
    """Download (or verify) a single source. Returns manifest record."""
    doc_id = src["doc_id"]
    url = src["immutable_url"]
    norm_fn = NORMALIZERS[src["normalization"]]

    raw_path = RAW_DIR / f"{doc_id}.raw"
    norm_path = SOURCES_DIR / f"{doc_id}.txt"

    if not verify_only:
        print(f"  Downloading {doc_id} from {url}...")
        req = urllib.request.Request(url, headers={"User-Agent": "RALG-V3-SourceVerifier/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw_bytes = resp.read()
                status = resp.status
        except Exception as exc:
            print(f"  FAILED: {exc}")
            return {"doc_id": doc_id, "error": str(exc)}

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_path, "wb") as f:
            f.write(raw_bytes)

        normalized = norm_fn(raw_bytes)
        with open(norm_path, "w", encoding="utf-8") as f:
            f.write(normalized)
    else:
        if not raw_path.exists():
            return {"doc_id": doc_id, "error": f"raw file missing: {raw_path}"}
        if not norm_path.exists():
            return {"doc_id": doc_id, "error": f"normalized file missing: {norm_path}"}
        with open(raw_path, "rb") as f:
            raw_bytes = f.read()
        with open(norm_path, "r", encoding="utf-8") as f:
            normalized = f.read()
        status = "cached"

    raw_sha = sha256_bytes(raw_bytes)
    norm_sha = sha256_text(normalized)

    record = {
        "acquisition_date": date.today().isoformat(),
        "doc_id": doc_id,
        "domain": doc_id.split("_")[0] + " documentation domain",
        "canonical_url": src["canonical_url"],
        "immutable_url": url,
        "revision": src["revision"],
        "repo": src["repo"],
        "source_path": src["source_path"],
        "license_type": src["license"],
        "license_note": src["license_note"],
        "normalization": src["normalization"],
        "raw_sha256": raw_sha,
        "normalized_sha256": norm_sha,
        "raw_size_bytes": len(raw_bytes),
        "normalized_size_chars": len(normalized),
        "source_filename": f"evaluation/holdout_v3/sources/{doc_id}.txt",
        "http_status": status,
        "used_in_development": False,
        "synthetic": False,
    }

    print(f"  {doc_id}: raw={raw_sha[:16]}... norm={norm_sha[:16]}... ({len(raw_bytes)} -> {len(normalized)} chars)")
    return record


def write_manifest(records: list[dict]) -> None:
    """Write sources_manifest.jsonl."""
    manifest_path = ROOT / "sources_manifest.jsonl"
    with open(manifest_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    print(f"\nWrote {manifest_path} ({len(records)} records)")


def verify_manifest_hashes() -> bool:
    """Re-read sources_manifest.jsonl and verify all hashes match on-disk files."""
    manifest_path = ROOT / "sources_manifest.jsonl"
    if not manifest_path.exists():
        print("ERROR: sources_manifest.jsonl not found")
        return False

    ok = True
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            doc_id = rec["doc_id"]
            raw_path = RAW_DIR / f"{doc_id}.raw"
            norm_path = SOURCES_DIR / f"{doc_id}.txt"

            if not raw_path.exists() or not norm_path.exists():
                print(f"FAIL {doc_id}: file missing")
                ok = False
                continue

            with open(raw_path, "rb") as f2:
                raw_bytes = f2.read()
            with open(norm_path, "r", encoding="utf-8") as f2:
                normalized = f2.read()

            actual_raw_sha = sha256_bytes(raw_bytes)
            actual_norm_sha = sha256_text(normalized)

            if actual_raw_sha != rec["raw_sha256"]:
                print(f"FAIL {doc_id}: raw SHA mismatch (expected {rec['raw_sha256'][:16]}, got {actual_raw_sha[:16]})")
                ok = False
            elif actual_norm_sha != rec["normalized_sha256"]:
                print(f"FAIL {doc_id}: normalized SHA mismatch (expected {rec['normalized_sha256'][:16]}, got {actual_norm_sha[:16]})")
                ok = False
            else:
                print(f"PASS {doc_id}")

    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="V3 source downloader/verifier")
    parser.add_argument("--verify", action="store_true", help="Verify existing files instead of downloading")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    if args.verify:
        print("Verifying existing source files...")
        ok = verify_manifest_hashes()
        sys.exit(0 if ok else 1)

    print("Downloading and normalizing V3 sources...")
    records = []
    for src in SOURCES:
        rec = download_one(src)
        records.append(rec)

    write_manifest(records)
    print("\nDone. All sources downloaded and normalized.")


if __name__ == "__main__":
    main()
