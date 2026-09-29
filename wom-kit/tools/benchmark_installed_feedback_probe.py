"""Content-free diagnostic profiler; never performance acceptance evidence.

Invoked by the installed runtime's isolated interpreter. It imports only the
installed CLI, observes call boundaries without patching product functions,
and never records function arguments, return values, paths or object IDs.
"""
import json
from pathlib import Path
import sys
import time

OUTPUT = Path(sys.argv[1])
COMMAND = sys.argv[2:]
START = time.perf_counter()
STACK = {}
LOOKUP_BEFORE = {}
INTERVALS = {key: [] for key in ("module_loading", "approval", "lock_acquisition", "network", "recording")}
COUNTS = {"full_manifest_parser_calls": 0, "canonical_corpus_enumerations": 0,
          "strict_full_manifest_snapshot_calls": 0, "manifest_lookup_rebuild_calls": 0,
          "manifest_lookup_parsed_rows": 0, "manifest_lookup_exact_reads": 0,
          "manifest_lookup_unchanged_reuses": 0, "network_request_calls": 0,
          "live_zettel_stat_snapshot_calls": 0, "live_zettel_stat_scan_calls": 0,
          "stable_file_snapshot_calls": 0, "claim_authentication_calls": 0,
          "claim_archive_identity_calls": 0, "claim_windows_api_setup_calls": 0}
BOUNDARIES = {}
ADDITIONAL_COUNTERS = {
    ("wom_kit.archive_services", "strict_live_zettel_stat_snapshot"): "live_zettel_stat_snapshot_calls",
    ("wom_kit.archive_services", "_strict_live_zettel_stat_scan"): "live_zettel_stat_scan_calls",
    ("wom_kit.archive_services", "archive_index_stable_file_snapshot"): "stable_file_snapshot_calls",
    ("wom_kit.exact_human_approval", "_authenticated_claim_document_core"): "claim_authentication_calls",
    ("wom_kit.exact_human_approval", "_authenticated_claim_document_for_identity"): "claim_authentication_calls",
    ("wom_kit.exact_human_approval", "_archive_identity"): "claim_archive_identity_calls",
    ("wom_kit.exact_human_approval", "_claim_windows_read_api"): "claim_windows_api_setup_calls",
}


def category(module, name, frame):
    if module.startswith("wom_kit") and name == "<module>":
        return "module_loading"
    if module == "wom_kit.exact_human_approval_windows" and name == "show":
        return "approval"
    if module in {"wom_kit.exact_operation_manifest", "wom_kit.operation_target_leases",
                  "wom_kit.credential_secure_registry"} and name == "__enter__":
        return "lock_acquisition"
    if ((module == "urllib.request" and name == "urlopen")
            or (module == "http.client" and name in {"request", "getresponse"})
            or (module == "requests.sessions" and name == "request")):
        return "network"
    if module.startswith("wom_kit") and (name in {"_exclusive_create", "_atomic_replace", "_write_bytes_create_if_absent",
            "_write_activity_group_bytes_new_file_bound", "_write_activity_group_bytes_replace_bound", "atomic_write"}
            or (module == "wom_kit.local_recovery_execution" and name == "write_field")
            or (module == "wom_kit.exact_operation_manifest" and name == "append")):
        return "recording"
    return None


def profile(frame, event, argument):
    if event not in {"call", "return"}:
        return
    module = frame.f_globals.get("__name__", "")
    name = frame.f_code.co_name
    now = time.perf_counter()
    if event == "call":
        if module == "wom_kit.cli_entry" and name == "main":
            BOUNDARIES.setdefault("entry_start", now)
        if module == "wom_kit.archive_cli" and name == "main":
            BOUNDARIES.setdefault("parser_start", now)
        if module == "wom_kit.archive_cli" and name.startswith("command_"):
            BOUNDARIES.setdefault("command_start", now)
        if module == "wom_kit.archive_services" and name == "load_manifest_records":
            COUNTS["full_manifest_parser_calls"] += 1
        if module == "wom_kit.archive_services" and name in {"iter_zettel_paths", "zet_catalog_paths", "zettel_paths_by_id", "strict_local_zettel_paths"}:
            COUNTS["canonical_corpus_enumerations"] += 1
        if module == "wom_kit.archive_services" and name == "archive_index_strict_manifest_snapshot":
            COUNTS["strict_full_manifest_snapshot_calls"] += 1
        counter = ADDITIONAL_COUNTERS.get((module, name))
        if (module == "wom_kit.exact_human_approval" and name == "_authenticated_claim_document_core"
                and "_authenticated_claim_document_for_identity" in frame.f_globals):
            # New versions delegate byte/MAC verification to this helper;
            # count its body once, not both wrapper and body.
            counter = None
        if counter:
            COUNTS[counter] += 1
        if module == "wom_kit.manifest_lookup" and name == "rows":
            instance = frame.f_locals.get("self")
            LOOKUP_BEFORE[id(frame)] = tuple(getattr(instance, field, 0) for field in ("rebuilds", "parsed_rows", "reads", "reuses"))
        kind = category(module, name, frame)
        if kind:
            STACK[id(frame)] = (kind, now)
            if kind == "network" and name in {"urlopen", "request"}:
                COUNTS["network_request_calls"] += 1
    else:
        if id(frame) in LOOKUP_BEFORE:
            before = LOOKUP_BEFORE.pop(id(frame))
            instance = frame.f_locals.get("self")
            for index, (attribute, counter) in enumerate((("rebuilds", "manifest_lookup_rebuild_calls"),
                    ("parsed_rows", "manifest_lookup_parsed_rows"), ("reads", "manifest_lookup_exact_reads"),
                    ("reuses", "manifest_lookup_unchanged_reuses"))):
                COUNTS[counter] += max(0, getattr(instance, attribute, before[index]) - before[index])
        if module == "wom_kit.archive_cli" and name.startswith("command_"):
            BOUNDARIES["command_end"] = now
        if id(frame) in STACK:
            kind, started = STACK.pop(id(frame))
            INTERVALS[kind].append((started, now))


def union_seconds(intervals):
    total, end = 0.0, None
    for start, stop in sorted(intervals):
        if end is None or start >= end:
            total += stop - start
        elif stop > end:
            total += stop - end
        end = max(end or stop, stop)
    return round(total, 6)


sys.setprofile(profile)
try:
    from wom_kit.cli_entry import main
    code = int(main(COMMAND))
finally:
    sys.setprofile(None)
    finished = time.perf_counter()
    phases = {}
    for name, begin, end in (
        ("entry_preparation_and_loading", "entry_start", "parser_start"),
        ("parser_and_dispatch", "parser_start", "command_start"),
        ("command_processing", "command_start", "command_end"),
    ):
        phases[name] = (round(BOUNDARIES[end] - BOUNDARIES[begin], 6)
                        if begin in BOUNDARIES and end in BOUNDARIES else None)
    report = {"schema": "wom-kit/installed-feedback-profile/v1", "diagnostic_only": True,
              "official_launcher": False, "acceptance_evidence": False,
              "instrumentation": "sys.setprofile_observation_without_product_monkeypatch",
              "instrumented_total_seconds": round(finished - START, 6), "phases_seconds": phases,
              "nested_phase_intervals_are_not_additive": True, "counters": COUNTS,
              "operation_phases": {key: {"observed_seconds": union_seconds(values), "observed_calls": len(values),
                  "state": "observed" if values else "not_observed_at_instrumented_boundaries"} for key, values in INTERVALS.items()},
              "arguments_or_return_values_recorded": False,
              "only_numeric_lookup_observation_attributes_read": True,
              "process_and_launcher_startup_not_separately_profiled": True,
              "counter_scope": "named_product_functions_only_not_a_complete_filesystem_or_network_trace",
              "network_request_count_is_instrumented_call_count_not_unique_remote_objects": True}
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
raise SystemExit(code)
