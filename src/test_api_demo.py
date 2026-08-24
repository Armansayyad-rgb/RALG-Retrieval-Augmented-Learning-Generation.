#!/usr/bin/env python3
"""Test script for RALG Engine API.

Assumes the server is already running on http://127.0.0.1:8000

Run:
    python src/test_api_demo.py
"""

import sys
import json
import atexit
import httpx

BASE_URL = "http://127.0.0.1:8000"

# Short compressor SOP for testing ingestion
COMPRESSOR_SOP = """
STANDARD OPERATING PROCEDURE: COMPRESSOR MAINTENANCE

1. BEFORE STARTING
   - De-energize the compressor unit at the main disconnect.
   - Verify zero voltage with a calibrated tester on all three phases.
   - Apply lockout/tagout (LOTO) per site procedure.
   - Allow system pressure to bleed to zero; confirm gauges read 0 PSI.

2. INSPECTION
   - Check oil level in sight glass; top up if below minimum mark.
   - Inspect belts for cracks, glazing, or excessive wear; replace if needed.
   - Verify belt tension: 1/2 inch deflection at center span under thumb pressure.
   - Clean intake filter; replace if clogged or damaged.
   - Check all electrical connections for tightness and signs of overheating.

3. LUBRICATION
   - Use only OEM-approved synthetic compressor oil (ISO VG 46).
   - Drain old oil while warm; collect and dispose per environmental regulations.
   - Refill to correct level; do not overfill.

4. RESTART
   - Remove LOTO devices.
   - Re-energize at main disconnect.
   - Start compressor; verify unloaded start (no pressure load).
   - Monitor for unusual vibration, noise, or temperature rise for 10 minutes.
   - Log all readings in maintenance register.
"""

def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

def print_json(data: dict):
    print(json.dumps(data, indent=2))


def main():
    print_section("RALG Engine API Demo Test")
    print(f"Base URL: {BASE_URL}")

    # 1. /health
    print_section("1. GET /health")
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        r.raise_for_status()
        print(f"Status: {r.status_code}")
        print_json(r.json())
    except httpx.ConnectError:
        print("ERROR: Cannot connect to server.")
        print("Start it with: uvicorn src.api_server:app --host 127.0.0.1 --port 8000")
        sys.exit(1)

    # 2. /stats
    print_section("2. GET /stats")
    r = httpx.get(f"{BASE_URL}/stats", timeout=5)
    r.raise_for_status()
    print(f"Status: {r.status_code}")
    initial_stats = r.json()
    print_json(initial_stats)

    # 3. /ingest
    print_section("3. POST /ingest (compressor SOP)")
    ingest_payload = {
        "text": COMPRESSOR_SOP,
        "document_name": "compressor_maintenance_sop"
    }
    r = httpx.post(f"{BASE_URL}/ingest", json=ingest_payload, timeout=30)
    r.raise_for_status()
    print(f"Status: {r.status_code}")
    ingest_result = r.json()
    print_json(ingest_result)
    assert ingest_result["document_id"]
    # Keep the demo repeatable: remove its persisted runtime document on exit.
    def cleanup_demo_document():
        try:
            httpx.delete(
                f"{BASE_URL}/documents/{ingest_result['document_id']}", timeout=10
            )
        except httpx.HTTPError:
            pass
    atexit.register(cleanup_demo_document)
    assert ingest_result["added_chunks"] > 0
    assert ingest_result["total_chunks"] == (
        initial_stats["chunk_count"] + ingest_result["added_chunks"]
    )

    # 4. /query - question answered by the ingested SOP
    print_section("4. POST /query (from ingested SOP)")
    query_payload = {
        "question": "What safety step is required before opening the compressor electrical panel?",
        "top_k": 5,
        "include_sources": True
    }
    r = httpx.post(f"{BASE_URL}/query", json=query_payload, timeout=60)
    r.raise_for_status()
    print(f"Status: {r.status_code}")
    query_result = r.json()
    print_json(query_result)

    required_fields = {
        "answer", "supported", "answer_type", "sources", "latency_ms", "error"
    }
    assert required_fields <= query_result.keys()
    assert query_result["error"] is None
    print("✓ ASSERTION PASSED: Query returned the documented response schema")

    # 5. /query - question from existing knowledge base
    print_section("5. POST /query (from existing knowledge base)")
    query_payload2 = {
        "question": "Why did the Roman Empire fall?",
        "top_k": 5,
        "include_sources": True
    }
    r = httpx.post(f"{BASE_URL}/query", json=query_payload2, timeout=60)
    r.raise_for_status()
    print(f"Status: {r.status_code}")
    print_json(r.json())

    # 6. /stats again to show updated chunk count
    print_section("6. GET /stats (after ingest)")
    r = httpx.get(f"{BASE_URL}/stats", timeout=5)
    r.raise_for_status()
    print(f"Status: {r.status_code}")
    final_stats = r.json()
    print_json(final_stats)
    assert final_stats["chunk_count"] == ingest_result["total_chunks"]

    print_section("Done")


if __name__ == "__main__":
    main()
