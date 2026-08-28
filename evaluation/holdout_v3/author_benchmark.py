#!/usr/bin/env python3
"""Author Holdout V3 benchmark: 120 cases with verified evidence spans.

All cases derived from committed source artifacts under evaluation/holdout_v3/sources/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HOLDOUT_DIR = ROOT / "evaluation" / "holdout_v3"
SOURCES_DIR = HOLDOUT_DIR / "sources"

_cache: dict[str, str] = {}


def load_source(doc_id: str) -> str:
    if doc_id not in _cache:
        _cache[doc_id] = (SOURCES_DIR / f"{doc_id}.txt").read_text(encoding="utf-8")
    return _cache[doc_id]


def find_span(doc_id: str, quoted: str) -> tuple[int, int]:
    text = load_source(doc_id)
    idx = text.find(quoted)
    if idx == -1:
        raise ValueError(f"SPAN NOT FOUND in {doc_id}: {quoted[:80]!r}")
    return (idx, idx + len(quoted))


def case(case_id, category, doc_ids, quotes, question, answer=None, behavior=None):
    spans = []
    for did, qt in zip(doc_ids, quotes):
        s, e = find_span(did, qt)
        spans.append({"doc_id": did, "quoted_text": qt, "span_start": s, "span_end": e})
    c = {"case_id": case_id, "category": category, "evidence_document_ids": doc_ids, "evidence_spans": spans, "question": question}
    if answer is not None:
        c["expected_answer"] = answer
    if behavior is not None:
        c["expected_behavior"] = behavior
    return c


ALL = []

# ── SUPPORTED (15) ──────────────────────────────────────────────
ALL += [
    case("v3_001","supported",["sqlite_wal_mode"],["PRAGMA journal_mode=WAL;"],"What SQL command activates WAL mode in SQLite?","PRAGMA journal_mode=WAL;"),
    case("v3_002","supported",["postgresql_vacuuming"],["dead row"],"What PostgreSQL VACUUM removes?","dead row versions"),
    case("v3_003","supported",["kubernetes_probes"],["readiness probe 15 seconds after the"],"Which Kubernetes probe controls traffic reception?","readiness probe"),
    case("v3_004","supported",["systemd_unit"],["Wants="],"Which systemd dependency is weaker than Requires=?","Wants="),
    case("v3_005","supported",["otel_propagators"],["TextMap Propagator"],"What propagator type reads and writes context data?","TextMap Propagator"),
    case("v3_006","supported",["oci_image_layout"],["oci-layout"],"Which file MUST exist in an OCI image layout?","oci-layout"),
    case("v3_007","supported",["cmake_presets"],["CMakeUserPresets.json"],"Which CMake file should NOT be tracked in VCS?","CMakeUserPresets.json"),
    case("v3_008","supported",["sqlite_wal_mode"],["PASSIVE, FULL, and RESTART"],"What are the three SQLite WAL checkpoint types?","PASSIVE, FULL, and RESTART"),
    case("v3_009","supported",["postgresql_vacuuming"],["autovacuum_max_workers"],"What controls max autovacuum workers?","autovacuum_max_workers"),
    case("v3_010","supported",["kubernetes_probes"],["Startup Probes"],"Which probe protects slow-starting containers?","startup probe"),
    case("v3_011","supported",["systemd_unit"],["After="],"Which directive orders a unit after another?","After="),
    case("v3_012","supported",["oci_image_layout"],["index.json"],"Which OCI file discovers manifests?","index.json"),
    case("v3_013","supported",["cmake_presets"],["configurePresets"],"Which preset type is required for build/test presets?","configurePresets"),
    case("v3_014","supported",["otel_propagators"],["Inject"],"Which operation writes context to a carrier?","Inject"),
    case("v3_015","supported",["systemd_unit"],["Before="],"Which directive orders a unit before another?","Before="),
]

# ── PARAPHRASED (15) ────────────────────────────────────────────
ALL += [
    case("v3_016","paraphrased",["sqlite_wal_mode"],["WAL provides more concurrency as readers do not block writers and"],"What concurrency advantage does WAL offer?","readers do not block writers"),
    case("v3_017","paraphrased",["postgresql_vacuuming"],["autovacuum"],"What background process handles vacuuming?","autovacuum"),
    case("v3_018","paraphrased",["kubernetes_probes"],["200 and less than 400 indicates success"],"What HTTP range means probe success?",">= 200 and < 400"),
    case("v3_019","paraphrased",["systemd_unit"],["Requires="],"Which directive creates a strong dependency?","Requires="),
    case("v3_020","paraphrased",["otel_propagators"],["traceparent"],"What HTTP header carries the W3C trace identifier in OTel?","traceparent"),
    case("v3_021","paraphrased",["oci_image_layout"],["blobs"],"Where are content-addressable objects stored?","blobs directory"),
    case("v3_022","paraphrased",["cmake_presets"],["workflowPresets"],"What preset sequences configure/build/test?","workflow presets"),
    case("v3_023","paraphrased",["sqlite_wal_mode"],["WAL uses many fewer fsync()"],"How does WAL reduce disk I/O compared to rollback journals?","fewer fsync() operations"),
    case("v3_024","paraphrased",["postgresql_vacuuming"],["ANALYZE"],"What updates query planner statistics?","ANALYZE"),
    case("v3_025","paraphrased",["kubernetes_probes"],["liveness probes to detect and remedy"],"What does a liveness probe verify?","detects and remedies failures"),
    case("v3_026","paraphrased",["otel_propagators"],["Extract"],"What does Extract do?","reads context from a carrier"),
    case("v3_027","paraphrased",["systemd_unit"],["Conflicts="],"Which systemd setting prevents two units from running simultaneously?","Conflicts="),
    case("v3_028","paraphrased",["oci_image_layout"],["imageLayoutVersion"],"What field identifies layout version?","imageLayoutVersion"),
    case("v3_029","paraphrased",["cmake_presets"],["buildPresets"],"What adds build-specific arguments?","build presets"),
    case("v3_030","paraphrased",["sqlite_wal_mode"],["wal-index"],"What structure helps WAL readers find pages fast?","wal-index"),
]

# ── PROCEDURAL (15) ─────────────────────────────────────────────
ALL += [
    case("v3_031","procedural",["sqlite_wal_mode"],["PRAGMA journal_mode=WAL;"],"How to enable WAL mode?","Run PRAGMA journal_mode=WAL;"),
    case("v3_032","procedural",["postgresql_vacuuming"],["VACUUM FULL"],"How to reclaim physical disk space?","VACUUM FULL"),
    case("v3_033","procedural",["kubernetes_probes"],["cat /tmp/healthy"],"How to configure a command-based liveness probe?","Use exec type with a command"),
    case("v3_034","procedural",["systemd_unit"],["drop-in"],"How to override vendor unit settings?","Create a drop-in .conf file"),
    case("v3_035","procedural",["otel_propagators"],["Inject"],"How to propagate context across processes?","Inject at exit, extract at entry"),
    case("v3_036","procedural",["oci_image_layout"],["content-addressable blobs"],"How to create a runtime bundle?","Extract blobs per OCI Runtime Spec"),
    case("v3_037","procedural",["cmake_presets"],["CMakePresets.json"],"How to use CMake presets?","Create CMakePresets.json and use --preset"),
    case("v3_038","procedural",["sqlite_wal_mode"],["automatic checkpointing can be completely\ndisabled using the wal_autocheckpoint pragma"],"How can automatic checkpointing be turned off in SQLite?","Disable via wal_autocheckpoint pragma"),
    case("v3_039","procedural",["postgresql_vacuuming"],["ANALYZE"],"When to update planner statistics?","Run ANALYZE after large data changes"),
    case("v3_040","procedural",["kubernetes_probes"],["startup probe"],"How to configure a startup probe?","Use startup probe with failureThreshold"),
    case("v3_041","procedural",["systemd_unit"],["Alias="],"How do you create a runtime symlink for a systemd unit?","Add Alias= in [Install]"),
    case("v3_042","procedural",["oci_image_layout"],["MUST exist"],"What must be in an OCI image layout?","oci-layout, index.json, blobs/"),
    case("v3_043","procedural",["otel_propagators"],["Composite"],"How to configure multiple propagators?","Use a Composite Propagator"),
    case("v3_044","procedural",["cmake_presets"],["testPresets"],"How to configure a test preset?","Define testPresets referencing configurePreset"),
    case("v3_045","procedural",["sqlite_wal_mode"],["WAL file is deleted automatically"],"How is the WAL file cleaned up?","Deleted when last connection closes"),
]

# ── CAUSAL (10) ─────────────────────────────────────────────────
ALL += [
    case("v3_046","causal",["sqlite_wal_mode"],["WAL does not work over a network filesystem"],"Why does WAL not work on network filesystems?","Requires shared memory on same host"),
    case("v3_047","causal",["postgresql_vacuuming"],["long-running open transactions"],"Why do dead rows accumulate despite autovacuum?","Long-running transactions block vacuuming"),
    case("v3_048","causal",["kubernetes_probes"],["liveness probes to detect and remedy"],"What happens when a liveness probe fails?","kubelet restarts the container"),
    case("v3_049","causal",["systemd_unit"],["Default Dependencies"],"What happens when a required unit stops?","Dependent units are also stopped"),
    case("v3_050","causal",["otel_propagators"],["value can not be parsed from the carrier"],"What if extraction fails on a carrier value?","MUST NOT throw exception, MUST NOT store new value"),
    case("v3_051","causal",["oci_image_layout"],["MUST exist"],"What if index.json is missing from OCI layout?","Manifests cannot be discovered"),
    case("v3_052","causal",["cmake_presets"],["CMakePresets.json"],"Why use CMakePresets.json?","Project-wide configuration standardization"),
    case("v3_053","causal",["postgresql_vacuuming"],["wraparound"],"Why must PostgreSQL be vacuumed regularly?","Prevent transaction ID wraparound"),
    case("v3_054","causal",["sqlite_wal_mode"],["read performance deteriorates"],"Why does read perf degrade with WAL growth?","Each reader checks more WAL pages"),
    case("v3_055","causal",["kubernetes_probes"],["lifecycle"],"Why use startup instead of liveness for slow containers?","Liveness would restart before initialization completes"),
]

# ── CROSS_DOCUMENT (10) ─────────────────────────────────────────
ALL += [
    case("v3_056","cross_document",["sqlite_wal_mode","postgresql_vacuuming"],["transfers it back into the original database file","dead row"],"What does each cleanup process clean?","SQLite WAL transfers WAL to DB; PostgreSQL VACUUM cleans dead rows"),
    case("v3_057","cross_document",["kubernetes_probes","systemd_unit"],["startup probe","Default Dependencies"],"Health-check mechanisms in K8s and systemd?","K8s probes; systemd Condition directives"),
    case("v3_058","cross_document",["otel_propagators","oci_image_layout"],["TextMap","content-addressable blobs"],"Content addressing in OTel vs OCI?","OTel addresses context carriers; OCI addresses blobs"),
    case("v3_059","cross_document",["cmake_presets","systemd_unit"],["CMakePresets.json","drop-in"],"Configuration layering in CMake vs systemd?","CMake uses includes; systemd uses drop-in dirs"),
    case("v3_060","cross_document",["sqlite_wal_mode","kubernetes_probes"],["PRAGMA journal_mode=WAL;","liveness probes to detect and remedy"],"Persistence vs restart semantics?","SQLite WAL persists; K8s probes trigger restarts"),
    case("v3_061","cross_document",["postgresql_vacuuming","otel_propagators"],["autovacuum","Composite"],"Multi-component mechanisms?","PostgreSQL autovacuum workers; OTel composite propagators"),
    case("v3_062","cross_document",["oci_image_layout","cmake_presets"],["index.json","CMakePresets.json"],"JSON index files in OCI vs CMake?","OCI discovers manifests; CMake defines configs"),
    case("v3_063","cross_document",["sqlite_wal_mode","postgresql_vacuuming"],["PRAGMA journal_mode=WAL;","VACUUM FULL"],"Rewrite operations?","SQLite WAL merges WAL into DB; PG VACUUM FULL rewrites table"),
    case("v3_064","cross_document",["kubernetes_probes","otel_propagators"],["readiness probe 15 seconds after the","Inject"],"Readiness in K8s vs OTel?","K8s ensures traffic reception; OTel ensures context propagation"),
    case("v3_065","cross_document",["systemd_unit","oci_image_layout"],["Requires=","MUST exist"],"Required structural elements?","systemd requires unit files; OCI requires blobs/oci-layout/index.json"),
]

# ── DOCUMENT_SCOPED (5) ─────────────────────────────────────────
ALL += [
    case("v3_066","document_scoped",["sqlite_wal_mode"],["WAL-Reset Bug"],"What bug was fixed in SQLite 3.51.3?","WAL-Reset Bug"),
    case("v3_067","document_scoped",["postgresql_vacuuming"],["multixact ID wraparound"],"What is multixact ID wraparound?","32-bit multixact IDs can wrap if not vacuumed"),
    case("v3_068","document_scoped",["kubernetes_probes"],["GRPCContainerProbeTLS"],"What K8s feature gate enables TLS for gRPC probes?","GRPCContainerProbeTLS"),
    case("v3_069","document_scoped",["systemd_unit"],["specifiers"],"What are systemd specifiers?","Variable expansion patterns like %n, %N, %p"),
    case("v3_070","document_scoped",["cmake_presets"],["Condition"],"What is the CMake preset Condition object?","Conditional evaluation for presets"),
]

# ── UNSUPPORTED (20) ────────────────────────────────────────────
for i, q in enumerate([
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
    "What is the chemical formula for potassium permanganate?",
    "How does the Higgs field give mass to elementary particles?",
    "What is the blood oxygen saturation level for a healthy adult at sea level?",
    "How does a diesel particulate filter regenerate?",
    "What is the encryption algorithm used in the Signal Protocol?",
    "How does a centrifugal clutch engage at higher RPM?",
    "What is the recommended allele frequency for STR markers in forensic DNA analysis?",
    "How does a variable valve timing system adjust camshaft phase?",
    "What is the maximum pressure rating for Schedule 80 PVC pipe?",
    "How does a thermosiphon circulate coolant without a pump?",
], start=1):
    ALL.append(case(f"v3_{70+i:03d}","unsupported",[],[],q,None,"reject_or_state_insufficient_evidence"))

# ── FALSE_PREMISE (15) ──────────────────────────────────────────
ALL += [
    case("v3_091","false_premise",["sqlite_wal_mode"],["page_size after entering WAL"],"How to change page_size in WAL mode?","Cannot change page_size after entering WAL mode"),
    case("v3_092","false_premise",["postgresql_vacuuming"],["VACUUM FULL"],"Can VACUUM FULL run concurrently with queries?","No, requires ACCESS EXCLUSIVE lock"),
    case("v3_093","false_premise",["kubernetes_probes"],["startup probe"],"Does startup probe restart immediately like liveness?","No, startup probes are independent"),
    case("v3_094","false_premise",["systemd_unit"],["Conflicts="],"Does Conflicts= trigger starting another unit?","No, only prevents simultaneous activation"),
    case("v3_095","false_premise",["oci_image_layout"],["MAY be used in a variety"],"Are unreferenced blobs forbidden in OCI?","No, blobs directory MAY contain unreferenced blobs"),
    case("v3_096","false_premise",["otel_propagators"],["value can not be parsed"],"Should propagator throw on extraction failure?","No, MUST NOT throw exception"),
    case("v3_097","false_premise",["cmake_presets"],["CMakeUserPresets.json"],"Should CMakeUserPresets.json be in VCS?","No, should not be tracked"),
    case("v3_098","false_premise",["sqlite_wal_mode"],["WAL does not work over a network filesystem"],"Can WAL work across machines?","No, requires shared memory on same host"),
    case("v3_099","false_premise",["postgresql_vacuuming"],["autovacuum_max_workers"],"Does disabling autovacuum prevent all vacuuming?","No, XID wraparound prevention still runs"),
    case("v3_100","false_premise",["kubernetes_probes"],["readiness probe 15 seconds after the"],"Do readiness probes only run during startup?","No, run during whole lifecycle"),
    case("v3_101","false_premise",["systemd_unit"],["Default Dependencies"],"Does systemd apply no default dependencies?","No, applies defaults based on unit type"),
    case("v3_102","false_premise",["oci_image_layout"],["MUST exist"],"Can OCI layout omit referenced blobs locally?","Yes, MAY be stored externally"),
    case("v3_103","false_premise",["otel_propagators"],["no-op propagators"],"Does OTel ship with active propagators?","No, uses no-op by default"),
    case("v3_104","false_premise",["sqlite_wal_mode"],["ATTACHed"],"Are multi-database transactions atomic in WAL?","No, atomicity is per-database"),
    case("v3_105","false_premise",["cmake_presets"],["Condition"],"Are CMake presets always unconditional?","No, support Condition objects"),
]

# ── MISLEADING_OVERLAP (10) ─────────────────────────────────────
ALL += [
    case("v3_106","misleading_overlap",["sqlite_wal_mode"],["PRAGMA journal_mode=WAL;"],"Is TRUNCATE journal mode the same as truncate checkpoint?","No, TRUNCATE is a journal mode; checkpoint types are PASSIVE/FULL/RESTART"),
    case("v3_107","misleading_overlap",["postgresql_vacuuming"],["VACUUM FULL"],"Does standard VACUUM rewrite the table?","No, only VACUUM FULL rewrites"),
    case("v3_108","misleading_overlap",["kubernetes_probes"],["startup probe"],"Is startup probe same as readiness with delay?","No, independent probe type"),
    case("v3_109","misleading_overlap",["systemd_unit"],["Alias="],"Is Alias= same as manual symlink?","No, Alias= in [Install] creates runtime symlinks"),
    case("v3_110","misleading_overlap",["otel_propagators"],["W3C"],"Is OTel propagator API same as W3C Trace Context?","No, OTel is generic; W3C is one implementation"),
    case("v3_111","misleading_overlap",["oci_image_layout"],["imageLayoutVersion"],"Is imageLayoutVersion same as OCI spec version?","No, layout format version vs spec version"),
    case("v3_112","misleading_overlap",["cmake_presets"],["CMakePresets.json"],"Is CMakePresets.json same as CMakeSettings.json?","No, different formats"),
    case("v3_113","misleading_overlap",["sqlite_wal_mode"],["wal-index"],"Is wal-index same as WAL file?","No, wal-index is shared-memory index"),
    case("v3_114","misleading_overlap",["postgresql_vacuuming"],["frozen"],"Are frozen XIDs same as vacuumed XIDs?","No, frozen marks permanently visible; vacuum removes dead tuples"),
    case("v3_115","misleading_overlap",["kubernetes_probes"],["liveness probes to detect"],"Is liveness probe same as health check endpoint?","No, probe is kubelet mechanism; endpoint is what it checks"),
]

# ── CONDITIONAL_OR_QUALIFIED (5) ────────────────────────────────
ALL += [
    case("v3_116","conditional_or_qualified",["sqlite_wal_mode"],["WAL does not work over a network filesystem"],"Can SQLite WAL work across machines?","No, requires all processes on same host",None),
    case("v3_117","conditional_or_qualified",["postgresql_vacuuming"],["autovacuum_max_workers"],"Will autovacuum always prevent wraparound?","Only if tables are vacuumed before 2B transactions",None),
    case("v3_118","conditional_or_qualified",["kubernetes_probes"],["200 and less than 400 indicates success"],"Does HTTP probe succeed for any response?","Only for status >= 200 and < 400",None),
    case("v3_119","conditional_or_qualified",["otel_propagators"],["no-op propagators"],"Does OTel propagate context without config?","No, no-op by default; requires configuration",None),
    case("v3_120","conditional_or_qualified",["oci_image_layout"],["MAY be used in a variety"],"Can OCI layout work without local blobs?","Yes, MAY be stored externally",None),
]


# ── MAIN ────────────────────────────────────────────────────────
def main():
    from collections import Counter
    cats = Counter(c["category"] for c in ALL)
    total = len(ALL)
    print(f"Total: {total}")
    for k in sorted(cats):
        print(f"  {k}: {cats[k]}")

    expected = {"supported":15,"paraphrased":15,"procedural":15,"causal":10,"cross_document":10,"document_scoped":5,"unsupported":20,"false_premise":15,"misleading_overlap":10,"conditional_or_qualified":5}
    if dict(cats) != expected:
        print("\nMISMATCH!")
        for k in set(list(cats.keys()) + list(expected.keys())):
            if cats.get(k, 0) != expected.get(k, 0):
                print(f"  {k}: got {cats.get(k,0)}, expected {expected.get(k,0)}")
        sys.exit(1)

    out = HOLDOUT_DIR / "holdout_v3_benchmark.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for c in ALL:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
