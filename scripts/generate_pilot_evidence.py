#!/usr/bin/env python3
"""Generate the deterministic, synthetic pilot evidence fixtures."""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 3817
DOMAINS = {
    "manufacturing": ("Line 7 press", "lockout tagout", "145 psi"),
    "healthcare": ("cold-chain cabinet", "temperature excursion", "2-8 C"),
    "finance": ("settlement service", "dual approval", "T+1"),
    "saas": ("Northstar API", "rolling deploy", "99.9 percent"),
    "energy": ("substation relay", "arc-flash boundary", "12 cal/cm2"),
    "logistics": ("Dock 4 scanner", "hazmat manifest", "UN3481"),
}


def build_corpus() -> list[dict]:
    docs = []
    for i, (domain, (asset, control, value)) in enumerate(DOMAINS.items(), 1):
        docs.append({
            "id": f"{domain}-policy-v2",
            "domain": domain,
            "name": f"{domain.title()} Operations Policy v2",
            "version": "2.0",
            "text": (
                f"{asset} policy v2. The required control is {control}. "
                f"Normal operating value is {value}. Review owner is the {domain} operations lead. "
                f"Procedure: verify the {control} before service. The control exists because it reduces "
                "unplanned downtime. Compare the current approved value with the superseded record "
                "before acting, and escalate any revision conflict for approval. "
                "This synthetic document contains no customer, personal, or production data."
            ),
        })
        docs.append({
            "id": f"{domain}-policy-v1",
            "domain": domain,
            "name": f"{domain.title()} Operations Policy v1 (superseded)",
            "version": "1.0",
            "superseded_by": f"{domain}-policy-v2",
            "text": (
                f"{asset} policy v1 is superseded. Earlier control wording mentioned {control}; "
                f"the recorded value was {value}. Always prefer the newer approved version."
            ),
        })
    docs.append({
        "id": "manufacturing-maintenance-conflict",
        "domain": "manufacturing",
        "name": "Line 7 Maintenance Note (conflicting draft)",
        "version": "draft",
        "conflicts_with": "manufacturing-policy-v2",
        "text": "Draft maintenance note proposes 160 psi for the Line 7 press. It is unapproved and conflicts with policy v2.",
    })
    docs.append({
        "id": "healthcare-cold-chain-conflict",
        "domain": "healthcare",
        "name": "Cold-chain Vendor Memo (unverified)",
        "version": "memo",
        "conflicts_with": "healthcare-policy-v2",
        "text": "Unverified vendor memo says 0-10 C. Treat this as conflicting evidence; approved policy v2 says 2-8 C.",
    })
    return docs


def build_cases(docs: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    cases = []
    for i in range(180):
        domain = list(DOMAINS)[i % len(DOMAINS)]
        asset, control, value = DOMAINS[domain]
        supported = i % 5 != 0
        if supported:
            templates = [
                ("factual", f"What control applies to the {asset}?", [control], [control]),
                ("operating_parameter", f"What is the normal value for the {asset}?", [value], [value]),
                ("revision", f"Which document governs the {asset} now?", ["policy v2"], ["policy v2"]),
                ("ownership", f"Who owns {domain} operations review?", [f"{domain} operations lead"], [domain]),
                ("procedural", f"What should be verified before service on the {asset}?", [control], [control]),
                ("causal", f"Why is the {control} used for the {asset}?", ["reduces", "downtime"], ["reduces", "downtime"]),
                ("comparison", f"How should the current and superseded {asset} records be compared?", ["current", "superseded"], ["current", "superseded"]),
                ("multi_hop", f"What control and review owner apply to the {asset}?", [control, domain], [control, domain]),
                ("approval", f"What should happen when a {asset} revision conflicts?", ["escalate", "approval"], ["conflict", "approval"]),
            ]
            case_type, template, groups, source_terms = templates[(i // len(DOMAINS)) % len(templates)]
            question = template + f" (pilot record {i + 1:03d})"
        else:
            unsupported_templates = [
                ("false_premise", f"Why did the {asset} fail yesterday?"),
                ("serial_number", f"What is the serial number installed on the {asset}?"),
                ("maintenance_interval", f"What is the mandatory maintenance interval for the {asset}?"),
                ("approval_status", f"Who approved the latest {asset} change?"),
                ("operating_parameter", f"What is the approved calibration color for the {asset}?"),
                ("conflict", f"Which value is safe when the {asset} records conflict?"),
            ]
            case_type, template = unsupported_templates[(i // len(DOMAINS)) % len(unsupported_templates)]
            question = template + f" (pilot record {i + 1:03d})"
            groups, source_terms = [], [case_type.replace("_", " ")]
        cases.append({
            "id": f"pilot-{i + 1:03d}",
            "domain": domain,
            "case_type": case_type,
            "question": question,
            "supported": supported,
            "required_answer_groups": groups,
            "required_source_terms": source_terms,
        })
    rng.shuffle(cases)
    return cases


def main() -> None:
    corpus = build_corpus()
    cases = build_cases(corpus)
    (ROOT / "data" / "pilot_customer_corpus_v1.jsonl").write_text(
        "".join(json.dumps(d, sort_keys=True) + "\n" for d in corpus), encoding="utf-8"
    )
    (ROOT / "evaluation" / "heldout_pilot_v1.jsonl").write_text(
        "".join(json.dumps(c, sort_keys=True) + "\n" for c in cases), encoding="utf-8"
    )
    print(f"wrote {len(corpus)} corpus documents and {len(cases)} held-out cases (seed={SEED})")


if __name__ == "__main__":
    main()
