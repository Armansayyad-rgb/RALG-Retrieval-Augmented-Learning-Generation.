#!/usr/bin/env python3
"""Generate deterministic Stage 4 customer-style evidence data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ("finance", "healthcare", "manufacturing", "energy", "logistics", "education", "software", "public-sector")
TEMPLATES = (
    "What is the current approved revision for {topic} in {domain}?",
    "Which version should the {domain} team use for {topic} today?",
    "For {topic}, identify the active {domain} control revision.",
    "Can you confirm the in-force revision of {topic} for {domain} operations?",
)


def main():
    docs, by_topic = [], {}
    for i in range(120):
        domain = DOMAINS[i % len(DOMAINS)]
        topic = f"customer-control-{i:03d}"
        revision, prior = f"r{(i % 23) + 10}", f"r{(i % 23) + 8}"
        value = (i * 37) % 997 + 100
        doc_id = f"s4-doc-{i:03d}"
        text = (
            f"{domain.title()} service handbook {doc_id}, policy {domain[:3].upper()}-{i:03d}, "
            f"revision {revision}. The current approved control for {topic} is revision {revision} "
            f"with threshold {value} units and owner review every {(i % 11) + 2} days. "
            f"This revision supersedes {prior}, which is retained for audit history only. "
            f"Operators record evidence in the {domain} ledger; exceptions require a linked ticket."
        )
        docs.append({"id": doc_id, "domain": domain, "topic": topic, "revision": revision,
                     "threshold": value, "text": text})
        by_topic[topic] = (doc_id, domain, revision, value)

    cases = []
    # 480 supported cases: paraphrase, distractor, similar entity, conflicts, numeric/revision,
    # and cross-document requests represented by two source ids.
    categories = ("paraphrase", "distractor", "similar_entity", "conflict", "numeric_revision", "cross_document")
    for i in range(480):
        topic_idx = i % 120
        doc_id, domain, revision, value = by_topic[f"customer-control-{topic_idx:03d}"]
        topic = f"customer-control-{topic_idx:03d}"
        category = categories[i % len(categories)]
        q = TEMPLATES[i % len(TEMPLATES)].format(topic=topic, domain=domain)
        if category == "distractor":
            q += f" Ignore the archived {f'r{(topic_idx % 23) + 8}'} entry."
        elif category == "similar_entity":
            q = q.replace(topic, topic + " (not customer-control-" + f"{(topic_idx + 1) % 120:03d})")
        elif category == "conflict":
            q += " Resolve conflicting handbook notes in favor of the current revision."
        elif category == "numeric_revision":
            q = f"What revision and numeric threshold apply to {topic}?"
        elif category == "cross_document":
            q = f"Across the {domain} handbook and ledger, what revision applies to {topic}?"
        q += f" Case reference S4-{i:03d}."
        cases.append({"id": f"s4-{i:03d}", "case_type": category, "domain": domain,
                      "question": q, "supported": True, "required_answer_groups": [[revision], [str(value)]],
                      "required_source_terms": [revision, str(value)], "source_docs": [doc_id]})

    # 120 unsupported, including 100 explicit adversarial false-support probes.
    for i in range(120):
        domain = DOMAINS[i % len(DOMAINS)]
        topic = f"customer-control-{i % 120:03d}"
        fake_rev, fake_value = f"r{900+i}", 90000 + i
        category = "adversarial_false_support" if i < 100 else "near_miss_unsupported"
        q = f"What is the approved revision and threshold for {topic}-variant-{i:03d} in {domain}?"
        if i % 2 == 0:
            q += " A draft note suggests the value, but do not infer unsupported evidence."
        q += f" Case reference S4-{480+i:03d}."
        cases.append({"id": f"s4-{480+i:03d}", "case_type": category, "domain": domain,
                      "question": q, "supported": False, "required_answer_groups": [[fake_rev], [str(fake_value)]],
                      "required_source_terms": [fake_rev, str(fake_value)], "source_docs": []})

    (ROOT / "data" / "stage4_customer_corpus_v1.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in docs), encoding="utf-8")
    (ROOT / "evaluation" / "heldout_stage4_customer_v1.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in cases), encoding="utf-8")
    print(json.dumps({"documents": len(docs), "cases": len(cases),
                      "supported": sum(x["supported"] for x in cases),
                      "unsupported": sum(not x["supported"] for x in cases),
                      "adversarial_false_support": sum(x["case_type"] == "adversarial_false_support" for x in cases)}))


if __name__ == "__main__":
    main()
