#!/usr/bin/env python3
"""Build and freeze Independent Holdout V2.

Holdout V2 is a blind acquisition-grade validation set. It intentionally uses
technical-document domains that differ from the existing RFC/PEP development
and benchmark material. The generated files are frozen by SHA-256 hashes in the
manifest; production code must not be tuned against this benchmark.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evaluation" / "holdout_v2"
SOURCES_DIR = OUT_DIR / "sources"
BENCHMARK_VERSION = "holdout_v2.0.0"
ACQUISITION_DATE = "2026-08-27"


SOURCE_TEXTS = {
    "sqlite_wal_checkpoint_ops": """Title: SQLite WAL Checkpoint Operations
Domain: embedded database operations
Source: Authored independent validation note derived from public SQLite documentation.

SQLite write-ahead logging stores committed transactions in a separate WAL file
before checkpointing merges pages back into the main database. A passive
checkpoint copies eligible frames without blocking active readers or writers. A
full checkpoint waits for readers that are using older snapshots before it
finishes. A truncate checkpoint performs the checkpoint and then truncates the
WAL file to zero bytes when it can do so safely.

Operational guidance:
1. Use passive checkpoints for low-interference background maintenance.
2. Use full checkpoints during planned maintenance windows when completion is
   more important than avoiding waits.
3. Use truncate checkpoints when reclaiming disk space from the WAL file is an
   explicit objective.
4. Do not treat checkpointing as a backup substitute; copy or backup the
   database using a backup-safe mechanism.

Evidence note: The file that may shrink to zero bytes is the WAL file, not the
main database file.
""",
    "cmake_presets_ci": """Title: CMake Presets for Continuous Integration
Domain: build-system configuration
Source: Authored independent validation note derived from public CMake documentation.

CMakePresets.json records configure, build, test, package, and workflow presets
in a machine-readable file. Configure presets select a generator, binary
directory, cache variables, environment values, and optional inheritance.
Build presets refer to a configure preset and add build-specific arguments such
as targets, configuration names, and parallel job counts. Test presets likewise
refer to a configure preset and can provide output, filter, and execution
settings for CTest.

Procedural guidance:
1. Add or update a configure preset before adding build or test presets that
   depend on it.
2. Keep CI presets checked into the repository so runners and developers use
   the same names.
3. Place user-specific overrides in CMakeUserPresets.json rather than changing
   shared CI presets.
4. Use workflow presets when a single named operation must run configure, build,
   and test steps in order.

Evidence note: A build preset depends on a configure preset; it does not replace
the configure step.
""",
    "oci_image_layout": """Title: OCI Image Layout Artifact Structure
Domain: container artifact packaging
Source: Authored independent validation note derived from the OCI Image Layout specification.

An OCI image layout directory contains an oci-layout file, an index.json file,
and a blobs directory. The oci-layout file identifies the layout version. The
index.json file points to one or more manifests through descriptors. Each
descriptor includes a media type, digest, and size. Blob content is stored under
the blobs directory by algorithm and encoded digest, for example
blobs/sha256/<hex>.

Operational guidance:
1. Verify descriptor digest and size before trusting a blob.
2. Read index.json to discover the manifests available in the layout.
3. Resolve the manifest descriptor to find config and layer descriptors.
4. Preserve digest-addressed blob paths when copying an image layout.

Evidence note: index.json is the entry point for discovering manifests; blobs
are addressed by digest.
""",
    "postgres_mvcc_maintenance": """Title: PostgreSQL MVCC Vacuum Maintenance
Domain: relational database maintenance
Source: Authored independent validation note derived from public PostgreSQL documentation.

PostgreSQL uses multi-version concurrency control so updates create new row
versions while older versions remain visible to transactions that still need
them. VACUUM removes dead row versions that are no longer visible to any active
transaction. VACUUM also updates planner statistics when ANALYZE is requested
or when autovacuum performs analyze work. VACUUM FULL rewrites the table into a
new physical file and requires an exclusive lock on the table.

Procedural guidance:
1. Keep autovacuum enabled for ordinary maintenance.
2. Investigate long-running transactions before blaming VACUUM for table bloat.
3. Reserve VACUUM FULL for cases where disk reclamation outweighs lock impact.
4. Run ANALYZE after large data changes when query plans need fresh statistics.

Evidence note: Ordinary VACUUM reclaims dead tuples for reuse; VACUUM FULL
rewrites the table and can return disk space to the operating system.
""",
    "opentelemetry_trace_context": """Title: OpenTelemetry Trace Context Propagation
Domain: observability instrumentation
Source: Authored independent validation note derived from OpenTelemetry and W3C trace-context documentation.

Distributed tracing links telemetry across services by propagating context with
each request. The traceparent header carries a version, trace identifier, parent
span identifier, and trace flags. The tracestate header carries vendor-specific
state in an ordered list. A service that receives an incoming request should
extract the context, start a child span, and inject the updated context into
outgoing requests.

Operational guidance:
1. Extract incoming context before starting server-side spans.
2. Start child spans for work caused by the inbound request.
3. Inject the current context into outbound calls so downstream services join
   the same trace.
4. Avoid placing secrets or personal data in trace identifiers or tracestate
   values.

Evidence note: The traceparent header carries identifiers and flags; tracestate
is for vendor-specific state.
""",
    "systemd_unit_ordering": """Title: systemd Unit Ordering and Requirement Semantics
Domain: Linux service management
Source: Authored independent validation note derived from public systemd documentation.

systemd separates requirement relationships from ordering relationships.
Requires= expresses that one unit depends on another unit being started, but it
does not by itself define startup order. After= and Before= define ordering
only; they do not create a requirement. Wants= is a weaker requirement than
Requires= and is commonly used when the dependent unit should be started but
failure should not necessarily stop the requiring unit.

Procedural guidance:
1. Use Wants= for optional cooperating services.
2. Use Requires= when the dependent unit is mandatory.
3. Add After= or Before= when startup order matters.
4. Combine a requirement with an ordering directive when both dependency and
   order are required.

Evidence note: Requires= is not an ordering directive; After= is not a
requirement directive.
""",
    "kubernetes_probe_rollout": """Title: Kubernetes Probe and Rollout Readiness
Domain: cluster workload operations
Source: Authored independent validation note derived from public Kubernetes documentation.

Kubernetes uses probes to decide how to manage container lifecycle and traffic.
A startup probe gives slow-starting containers time to initialize before liveness
or readiness checks are enforced. A liveness probe indicates whether the
container should be restarted. A readiness probe indicates whether the Pod is
ready to receive Service traffic. During a Deployment rollout, unavailable Pods
and surge Pods are constrained by maxUnavailable and maxSurge.

Procedural guidance:
1. Use a startup probe when initialization can legitimately take a long time.
2. Use a readiness probe to remove a Pod from Service endpoints before it can
   safely serve traffic.
3. Use a liveness probe to recover from a deadlocked or unhealthy process.
4. Set maxUnavailable and maxSurge to control rollout availability and capacity.

Evidence note: Readiness affects Service traffic; liveness affects restarts.
""",
}


SOURCE_META = [
    ("sqlite_wal_checkpoint_ops", "SQLite documentation domain", "https://www.sqlite.org/wal.html"),
    ("cmake_presets_ci", "CMake documentation domain", "https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html"),
    ("oci_image_layout", "OCI image-spec domain", "https://github.com/opencontainers/image-spec/blob/main/image-layout.md"),
    ("postgres_mvcc_maintenance", "PostgreSQL documentation domain", "https://www.postgresql.org/docs/current/routine-vacuuming.html"),
    ("opentelemetry_trace_context", "OpenTelemetry/W3C trace-context domain", "https://opentelemetry.io/docs/concepts/context-propagation/"),
    ("systemd_unit_ordering", "systemd documentation domain", "https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html"),
    ("kubernetes_probe_rollout", "Kubernetes documentation domain", "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/"),
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_lf(path: Path, text: str) -> None:
    path.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def locate_span(text: str, needle: str) -> dict:
    start = text.find(needle)
    if start >= 0:
        return {"span_start": start, "span_end": start + len(needle), "quoted_text": needle}
    pattern = re.escape(needle).replace(r"\ ", r"\s+")
    match = re.search(pattern, text)
    if not match:
        raise SystemExit(f"evidence text not found: {needle!r}")
    return {
        "span_start": match.start(),
        "span_end": match.end(),
        "quoted_text": text[match.start():match.end()],
    }


def add_case(
    cases: list[dict],
    category: str,
    question: str,
    evidence_document_ids: list[str],
    expected_answer: str | None,
    evidence_quotes: list[tuple[str, str]] | None = None,
) -> None:
    case = {
        "case_id": f"holdout_v2_{len(cases) + 1:03d}",
        "category": category,
        "question": question,
        "evidence_document_ids": evidence_document_ids,
        "expected_answer": expected_answer,
    }
    if category in {"unsupported", "false_premise", "misleading_overlap"}:
        case["expected_behavior"] = "reject_or_state_insufficient_evidence"
    if evidence_quotes:
        spans = []
        for doc_id, quote in evidence_quotes:
            span = locate_span(SOURCE_TEXTS[doc_id], quote)
            span["doc_id"] = doc_id
            spans.append(span)
        case["evidence_spans"] = spans
    cases.append(case)


def build_cases() -> list[dict]:
    cases: list[dict] = []

    supported = [
        ("Which file can a truncate checkpoint shrink to zero bytes?", "sqlite_wal_checkpoint_ops", "the WAL file", "WAL file to zero bytes"),
        ("What file identifies the version of an OCI image layout?", "oci_image_layout", "oci-layout", "The oci-layout file identifies the layout version."),
        ("Which systemd directive defines ordering but not a requirement?", "systemd_unit_ordering", "After= and Before=", "After= and Before= define ordering only"),
        ("Which PostgreSQL command rewrites a table into a new physical file?", "postgres_mvcc_maintenance", "VACUUM FULL", "VACUUM FULL rewrites the table into a new physical file"),
        ("What Kubernetes probe controls whether a Pod receives Service traffic?", "kubernetes_probe_rollout", "readiness probe", "A readiness probe indicates whether the Pod is ready to receive Service traffic."),
        ("Which OpenTelemetry header carries vendor-specific state?", "opentelemetry_trace_context", "tracestate", "The tracestate header carries vendor-specific state"),
        ("What CMake file should hold user-specific preset overrides?", "cmake_presets_ci", "CMakeUserPresets.json", "Place user-specific overrides in CMakeUserPresets.json"),
        ("In an OCI descriptor, what fields are listed in this corpus?", "oci_image_layout", "media type, digest, and size", "Each descriptor includes a media type, digest, and size."),
        ("What PostgreSQL feature removes dead row versions no longer visible to active transactions?", "postgres_mvcc_maintenance", "VACUUM", "VACUUM removes dead row versions"),
        ("What systemd relationship is weaker than Requires= in this corpus?", "systemd_unit_ordering", "Wants=", "Wants= is a weaker requirement than Requires="),
    ]
    for q, doc, answer, quote in supported:
        add_case(cases, "supported", q, [doc], answer, [(doc, quote)])

    paraphrased = [
        ("I need low-interference SQLite maintenance while traffic continues. Which checkpoint mode fits?", "sqlite_wal_checkpoint_ops", "passive checkpoint", "Use passive checkpoints for low-interference background maintenance."),
        ("A CI job needs one preset name to configure, compile, and test. Which preset type is described?", "cmake_presets_ci", "workflow preset", "Use workflow presets when a single named operation must run configure, build, and test steps in order."),
        ("Where should an OCI reader start when discovering available manifests?", "oci_image_layout", "index.json", "Read index.json to discover the manifests available in the layout."),
        ("A table is bloated but a long transaction is open. What should be checked first?", "postgres_mvcc_maintenance", "long-running transactions", "Investigate long-running transactions before blaming VACUUM for table bloat."),
        ("Which tracing step lets the next service join the same distributed trace?", "opentelemetry_trace_context", "inject the current context into outbound calls", "Inject the current context into outbound calls so downstream services join the same trace."),
        ("A service needs another unit to start but also needs correct startup sequence. What should be combined?", "systemd_unit_ordering", "a requirement with an ordering directive", "Combine a requirement with an ordering directive when both dependency and order are required."),
        ("A container can take a long time to initialize legitimately. Which probe should protect it?", "kubernetes_probe_rollout", "startup probe", "Use a startup probe when initialization can legitimately take a long time."),
        ("Which CMake preset kind can add target names and parallel job counts?", "cmake_presets_ci", "build preset", "Build presets refer to a configure preset and add build-specific arguments"),
        ("What should be verified before an OCI blob is trusted?", "oci_image_layout", "descriptor digest and size", "Verify descriptor digest and size before trusting a blob."),
        ("What PostgreSQL action is appropriate after large data changes when plans need fresh statistics?", "postgres_mvcc_maintenance", "ANALYZE", "Run ANALYZE after large data changes when query plans need fresh statistics."),
    ]
    for q, doc, answer, quote in paraphrased:
        add_case(cases, "paraphrased", q, [doc], answer, [(doc, quote)])

    unsupported = [
        "What is the torque specification for a 2025 electric vehicle wheel lug nut?",
        "How does a BGP route reflector choose among equal local-preference paths?",
        "Which ISO 27001 annex control maps to immutable S3 buckets?",
        "What opcode encodes an ARMv8 exclusive load instruction?",
        "How should a hospital calculate a pediatric medication dose?",
        "What is the rated ampacity of 10 AWG copper wire in conduit?",
        "How does a JPEG decoder reconstruct chroma subsampling?",
        "What is the default retention policy for a Microsoft Purview label?",
        "Which aviation checklist item arms an A320 autothrottle?",
        "How do you calculate a reinforced concrete beam shear stirrup spacing?",
    ]
    for q in unsupported:
        add_case(cases, "unsupported", q, [], None)

    false_premise = [
        ("Why does SQLite checkpointing shrink the main database file to zero bytes?", "sqlite_wal_checkpoint_ops", "truncates the WAL file to zero bytes"),
        ("Why do CMake build presets eliminate the need for configure presets?", "cmake_presets_ci", "A build preset depends on a configure preset; it does not replace the configure step."),
        ("Why does an OCI layout store blobs by tag name rather than digest?", "oci_image_layout", "blobs are addressed by digest"),
        ("Why does ordinary PostgreSQL VACUUM always return table disk space to the operating system?", "postgres_mvcc_maintenance", "Ordinary VACUUM reclaims dead tuples for reuse; VACUUM FULL rewrites the table"),
        ("Why should trace identifiers contain personal data for easier debugging?", "opentelemetry_trace_context", "Avoid placing secrets or personal data in trace identifiers"),
        ("Why does systemd Requires= guarantee that the required unit starts first?", "systemd_unit_ordering", "Requires= is not an ordering directive"),
        ("Why does a Kubernetes readiness probe restart a deadlocked container?", "kubernetes_probe_rollout", "Readiness affects Service traffic; liveness affects restarts."),
        ("Why should CMake CI teams put shared runner presets only in CMakeUserPresets.json?", "cmake_presets_ci", "Keep CI presets checked into the repository"),
        ("Why does tracestate replace traceparent for trace identifiers?", "opentelemetry_trace_context", "The traceparent header carries identifiers and flags"),
        ("Why does VACUUM FULL avoid taking an exclusive table lock?", "postgres_mvcc_maintenance", "requires an exclusive lock on the table"),
    ]
    for q, doc, quote in false_premise:
        add_case(cases, "false_premise", q, [doc], None, [(doc, quote)])

    misleading = [
        ("In the SQLite checkpoint document, which HTTP status code signals checkpoint completion?", "sqlite_wal_checkpoint_ops", "checkpointing"),
        ("In CMake presets, what Kubernetes Service endpoint is changed by a build preset?", "cmake_presets_ci", "Build presets refer to a configure preset"),
        ("In the OCI layout, which SQL command creates index.json?", "oci_image_layout", "index.json is the entry point"),
        ("In PostgreSQL MVCC maintenance, which traceparent flag triggers VACUUM FULL?", "postgres_mvcc_maintenance", "VACUUM FULL rewrites the table"),
        ("In OpenTelemetry context propagation, which systemd directive stores tracestate?", "opentelemetry_trace_context", "tracestate is for vendor-specific state"),
        ("In systemd ordering, which CTest filter is configured by Requires= ?", "systemd_unit_ordering", "Requires= is not an ordering directive"),
        ("In Kubernetes rollout readiness, which OCI digest path records maxSurge?", "kubernetes_probe_rollout", "maxUnavailable and maxSurge"),
        ("Which SQLite WAL checkpoint mode updates PostgreSQL planner statistics?", "sqlite_wal_checkpoint_ops", "checkpoint"),
        ("Which Kubernetes readiness probe truncates an OCI blob to zero bytes?", "kubernetes_probe_rollout", "readiness probe"),
        ("Which CMake workflow preset injects OpenTelemetry headers automatically?", "cmake_presets_ci", "workflow presets"),
    ]
    for q, doc, quote in misleading:
        add_case(cases, "misleading_overlap", q, [doc], None, [(doc, quote)])

    procedural = [
        ("What sequence should be followed before adding CMake build or test presets?", "cmake_presets_ci", "add or update a configure preset first", "Add or update a configure preset before adding build or test presets that depend on it."),
        ("What steps should an OCI reader follow from layout discovery to layers?", "oci_image_layout", "read index.json, resolve the manifest descriptor, then find config and layer descriptors", ["Read index.json to discover the manifests available in the layout.", "Resolve the manifest descriptor to find config and layer descriptors."]),
        ("How should OpenTelemetry context be handled around inbound and outbound requests?", "opentelemetry_trace_context", "extract incoming context, start child spans, and inject current context into outbound calls", ["Extract incoming context before starting server-side spans.", "Start child spans for work caused by the inbound request.", "Inject the current context into outbound calls so downstream services join the same trace."]),
        ("How should Kubernetes probes be chosen for slow startup, traffic removal, and deadlock recovery?", "kubernetes_probe_rollout", "startup probe for slow initialization, readiness probe for Service traffic, liveness probe for restarts", ["Use a startup probe when initialization can legitimately take a long time.", "Use a readiness probe to remove a Pod from Service endpoints before it can safely serve traffic.", "Use a liveness probe to recover from a deadlocked or unhealthy process."]),
        ("How should systemd dependencies be specified when both dependency and order matter?", "systemd_unit_ordering", "combine a requirement with After= or Before=", "Combine a requirement with an ordering directive when both dependency and order are required."),
        ("How should PostgreSQL maintenance respond to bloat and stale planner statistics?", "postgres_mvcc_maintenance", "check long-running transactions and run ANALYZE after large data changes", ["Investigate long-running transactions before blaming VACUUM for table bloat.", "Run ANALYZE after large data changes when query plans need fresh statistics."]),
        ("What SQLite checkpoint mode sequence matches low interference, planned completion, and disk reclamation?", "sqlite_wal_checkpoint_ops", "passive, full, then truncate according to objective", ["Use passive checkpoints for low-interference background maintenance.", "Use full checkpoints during planned maintenance windows when completion is more important than avoiding waits.", "Use truncate checkpoints when reclaiming disk space from the WAL file is an explicit objective."]),
        ("What must be preserved when copying an OCI image layout?", "oci_image_layout", "digest-addressed blob paths", "Preserve digest-addressed blob paths when copying an image layout."),
        ("Where should shared versus user-specific CMake preset changes go?", "cmake_presets_ci", "shared CI presets in CMakePresets.json and user-specific overrides in CMakeUserPresets.json", ["Keep CI presets checked into the repository so runners and developers use the same names.", "Place user-specific overrides in CMakeUserPresets.json"]),
        ("What Kubernetes rollout settings control availability and temporary extra capacity?", "kubernetes_probe_rollout", "maxUnavailable and maxSurge", "Set maxUnavailable and maxSurge to control rollout availability and capacity."),
    ]
    for q, doc, answer, quotes in procedural:
        if isinstance(quotes, str):
            quotes = [quotes]
        add_case(cases, "procedural", q, [doc], answer, [(doc, quote) for quote in quotes])

    cross_doc = [
        ("Which two documents distinguish traffic routing from restarts and requirements from ordering?", ["kubernetes_probe_rollout", "systemd_unit_ordering"], "Kubernetes Probe and Rollout Readiness; systemd Unit Ordering and Requirement Semantics", [("kubernetes_probe_rollout", "Readiness affects Service traffic; liveness affects restarts."), ("systemd_unit_ordering", "Requires= is not an ordering directive; After= is not a requirement directive.")]),
        ("Which documents warn not to use the discussed mechanism as the stronger operation: SQLite checkpointing as backup, and CMake build presets as configure replacement?", ["sqlite_wal_checkpoint_ops", "cmake_presets_ci"], "SQLite WAL Checkpoint Operations; CMake Presets for Continuous Integration", [("sqlite_wal_checkpoint_ops", "Do not treat checkpointing as a backup substitute"), ("cmake_presets_ci", "it does not replace the configure step")]),
        ("Which documents contain digest-addressed artifact verification and trace context propagation?", ["oci_image_layout", "opentelemetry_trace_context"], "OCI Image Layout Artifact Structure; OpenTelemetry Trace Context Propagation", [("oci_image_layout", "Verify descriptor digest and size before trusting a blob."), ("opentelemetry_trace_context", "inject the updated context into outgoing requests.")]),
        ("Which documents discuss maintenance operations that may wait or lock?", ["sqlite_wal_checkpoint_ops", "postgres_mvcc_maintenance"], "SQLite WAL Checkpoint Operations; PostgreSQL MVCC Vacuum Maintenance", [("sqlite_wal_checkpoint_ops", "A full checkpoint waits for readers"), ("postgres_mvcc_maintenance", "requires an exclusive lock on the table")]),
        ("Which documents define files named index.json and CMakeUserPresets.json?", ["oci_image_layout", "cmake_presets_ci"], "OCI Image Layout Artifact Structure; CMake Presets for Continuous Integration", [("oci_image_layout", "The index.json file points to one or more manifests"), ("cmake_presets_ci", "CMakeUserPresets.json")]),
        ("Which documents cover keeping optional collaborators from being fatal and removing unready Pods from traffic?", ["systemd_unit_ordering", "kubernetes_probe_rollout"], "systemd Unit Ordering and Requirement Semantics; Kubernetes Probe and Rollout Readiness", [("systemd_unit_ordering", "Use Wants= for optional cooperating services."), ("kubernetes_probe_rollout", "remove a Pod from Service endpoints")]),
        ("Which documents identify the field carrier for vendor state and the file carrier for layout version?", ["opentelemetry_trace_context", "oci_image_layout"], "OpenTelemetry Trace Context Propagation; OCI Image Layout Artifact Structure", [("opentelemetry_trace_context", "tracestate is for vendor-specific state"), ("oci_image_layout", "The oci-layout file identifies the layout version.")]),
        ("Which documents recommend background automation for ordinary maintenance and repository-checked CI presets?", ["postgres_mvcc_maintenance", "cmake_presets_ci"], "PostgreSQL MVCC Vacuum Maintenance; CMake Presets for Continuous Integration", [("postgres_mvcc_maintenance", "Keep autovacuum enabled for ordinary maintenance."), ("cmake_presets_ci", "Keep CI presets checked into the repository")]),
        ("Which documents connect outbound propagation and downstream service joining with Service endpoint readiness?", ["opentelemetry_trace_context", "kubernetes_probe_rollout"], "OpenTelemetry Trace Context Propagation; Kubernetes Probe and Rollout Readiness", [("opentelemetry_trace_context", "downstream services join the same trace"), ("kubernetes_probe_rollout", "ready to receive Service traffic")]),
        ("Which documents describe disk-space reclamation through WAL truncation and table rewrite?", ["sqlite_wal_checkpoint_ops", "postgres_mvcc_maintenance"], "SQLite WAL Checkpoint Operations; PostgreSQL MVCC Vacuum Maintenance", [("sqlite_wal_checkpoint_ops", "WAL file to zero bytes"), ("postgres_mvcc_maintenance", "VACUUM FULL rewrites the table")]),
    ]
    for q, docs, answer, quotes in cross_doc:
        add_case(cases, "cross_document", q, docs, answer, quotes)

    return cases


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    for doc_id, text in SOURCE_TEXTS.items():
        write_lf(SOURCES_DIR / f"{doc_id}.txt", text)

    source_manifest_lines = []
    for doc_id, domain, url in SOURCE_META:
        path = SOURCES_DIR / f"{doc_id}.txt"
        source_manifest_lines.append(json.dumps({
            "doc_id": doc_id,
            "domain": domain,
            "source_url": url,
            "source_filename": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(path),
            "acquisition_date": ACQUISITION_DATE,
            "license_note": "Authored independent validation note; source URLs record provenance domain.",
        }, sort_keys=True))
    write_lf(OUT_DIR / "sources_manifest.jsonl", "\n".join(source_manifest_lines) + "\n")

    cases = build_cases()
    benchmark_path = OUT_DIR / "holdout_benchmark.jsonl"
    write_lf(benchmark_path, "\n".join(json.dumps(case, sort_keys=True) for case in cases) + "\n")

    counts: dict[str, int] = {}
    for case in cases:
        counts[case["category"]] = counts.get(case["category"], 0) + 1

    manifest = {
        "benchmark_version": BENCHMARK_VERSION,
        "status": "FROZEN / DO NOT TUNE / DO NOT RUN UNTIL FINAL BLIND EVALUATION",
        "generated_from": "authored blind case specs verified against committed source notes",
        "case_count": len(cases),
        "category_counts": counts,
        "retrieval_supported_cases": sum(counts.get(c, 0) for c in (
            "supported", "paraphrased", "procedural", "cross_document")),
        "rejection_cases": sum(counts.get(c, 0) for c in (
            "unsupported", "false_premise", "misleading_overlap")),
        "source_count": len(SOURCE_META),
        "benchmark_sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        "sources_manifest_sha256": hashlib.sha256(
            (OUT_DIR / "sources_manifest.jsonl").read_bytes()).hexdigest(),
        "independence_statement": (
            "No holdout_v1 PEP sources, Stage 5 RFC documents, case IDs, or "
            "questions are reused. Production code must not be tuned against "
            "Holdout V2."
        ),
    }
    write_lf(OUT_DIR / "holdout_manifest.json", json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
