#!/usr/bin/env python3
"""Installed-only Windows runtime journey; local synthetic project, real wheel.

Run only with the wheel checker's isolated bootstrap interpreter. This file
never inserts a source checkout in sys.path. Only release transport metadata,
local wheel transport, native button choice, and an ephemeral approval key are
controlled; policy, supply, installer, broker, writers and verifiers stay real.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from functools import wraps
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import threading
import time
from unittest import mock
from types import CodeType


SCHEMA = "wom-kit/installed-v0419-runtime-journey/v0.1"
INITIAL_DIAGNOSTIC_SCHEMA = "wom-kit/installed-runtime-initial-update-diagnostic/v0.1"
PHASE_SCHEMA = "wom-kit/installed-runtime-phase-event/v0.1"
PHASE_PREFIX = "WOM_RUNTIME_PHASE_V1 "
PHASES = (
    "bootstrap_import", "synthetic_project", "initial_update", "healthy_noop",
    "next_preview", "source_drift", "ref_drift", "repair_preimage",
    "repair_prepare_to_cut", "repair_cut_validation", "repair_fresh_resume",
    "repair_result_validation", "repair_independent_noop", "terminal_control_check",
    "runtime_process_origin", "project_launcher_version", "doctor_startup", "final_claim_check",
)
SAFE_REASON_CODES = frozenset({
    "origin_modules_incomplete", "source_checkout_import_denied", "synthetic_child_command_failed",
    "source_resource_path_invalid", "source_resource_drift", "windows_cpython312_required",
    "synthetic_fixture_must_be_new", "bootstrap_version_mismatch", "bootstrap_wheel_hash_mismatch",
    "fixture_invalid", "local_transport_hash_mismatch", "local_transport_size_mismatch",
    "public_update_failed", "public_native_broker_not_once", "update_cleanup_incomplete",
    "public_noop_failed", "noop_revalidation_missing", "noop_runtime_changed", "noop_receipt_added",
    "noop_pin_launcher_receipt_changed", "noop_blocks_next_command", "active_update_lock_remains",
    "active_update_transaction_remains", "runtime_candidate_remains", "runtime_origin_or_version_mismatch",
    "project_launcher_version_mismatch", "durable_broker_claim_missing", "journey_arguments_invalid",
    "doctor_startup_probe_failed", "doctor_startup_progress_missing", "doctor_startup_progress_deadline",
    "doctor_startup_output_invalid", "doctor_startup_probe_output_bound",
    "drift_injection_not_observed", "drift_not_blocked",
    "drift_domain_changed", "drift_requested_effect", "repair_interruption_not_reached",
    "repair_preimage_changed_before_switch", "repair_checkpoint_missing", "repair_claim_missing",
    "repair_resume_failed", "repair_resume_requested_effect", "repair_payload_not_restored",
    "repair_worker_arguments_invalid", "repair_worker_origin_invalid",
})

FAILURE_OBSERVATION_SCHEMA = "wom-kit/installed-runtime-failure-observation/v0.1"
FAILURE_OBSERVATION_STAGES = frozenset({"first_update", "repair_fresh_resume"})
FAILURE_OUTPUT_LIMIT_BYTES = 32 * 1024
COMPONENT_OBSERVATION_SCHEMA = "wom-kit/test-live-component-observation/v1"
COMPONENT_OBSERVATION_ROLES = frozenset({
    "source", "runtime", "launcher", "non_active_pin", "receipt", "active_pin", "unclassified_component",
})
COMPONENT_OBSERVATION_BOUNDARIES = frozenset({"source", "runtime", "repair", "file", "classification"})
COMPONENT_OBSERVATION_REASONS = frozenset({
    "verified", "verified_missing", "not_applicable", "project_git_snapshot_unavailable",
    "project_git_snapshot_invalid", "project_git_snapshot_unsafe", "project_git_snapshot_size_policy_exceeded",
    "project_runtime_existing_observation_unavailable", "project_runtime_existing_missing",
    "project_runtime_existing_unsafe", "project_runtime_existing_install_incomplete",
    "project_runtime_existing_receipt_missing", "project_runtime_existing_receipt_mismatch",
    "project_runtime_existing_receipt_invalid", "project_runtime_existing_integrity_mismatch",
    "project_runtime_existing_artifact_mismatch", "project_runtime_existing_payload_mismatch",
    "project_runtime_existing_supply_mismatch", "project_runtime_repair_observation_unavailable",
    "project_runtime_repair_state_invalid", "project_update_component_size_policy_invalid",
    "project_update_component_observation_unavailable", "project_update_component_path_unsafe",
    "project_update_component_changed", "project_update_component_too_large",
})
COMPONENT_SOURCE_FIELDS = frozenset({
    "head", "branch", "index_sha256", "index_matches_head", "flags_sha256", "eol_sha256",
    "flags_safe", "raw_bytes_match_head", "worktree_sha256", "tracked_file_count", "untracked_paths", "eol_overrides",
})
COMPONENT_CLASSIFICATION_STATES = frozenset({"pre_exact", "post_exact", "pre_and_post_exact", "unknown", "unclassified"})
COMPONENT_PROBE_STATES = frozenset({"passed", "failed", "unavailable", "exception", "unclassified"})


def _component_observation_row_valid(row):
    if (type(row) is not dict or set(row) != {"boundary", "role", "state", "reason_code", "changed_source_fields"}
            or type(row["boundary"]) is not str or row["boundary"] not in COMPONENT_OBSERVATION_BOUNDARIES
            or type(row["role"]) is not str or row["role"] not in COMPONENT_OBSERVATION_ROLES
            or type(row["state"]) is not str):
        return False
    boundary, role, state, reason = (row[name] for name in ("boundary", "role", "state", "reason_code"))
    fields = row["changed_source_fields"]
    if (type(fields) is not list or len(fields) > len(COMPONENT_SOURCE_FIELDS)
            or any(type(field) is not str or field not in COMPONENT_SOURCE_FIELDS for field in fields)
            or fields != sorted(set(fields))):
        return False
    if boundary == "classification":
        return state in COMPONENT_CLASSIFICATION_STATES and reason is None and not fields
    if state not in COMPONENT_PROBE_STATES:
        return False
    if ((boundary == "source" and role != "source")
            or (boundary in {"runtime", "repair"} and role != "runtime")
            or (boundary == "file" and role in {"source", "runtime"})
            or (fields and (boundary != "source" or state != "passed"))):
        return False
    if reason is None:
        return True
    if type(reason) is not str or reason not in COMPONENT_OBSERVATION_REASONS or state in {"exception", "unclassified"}:
        return False
    if state == "passed":
        return reason in ({"verified", "verified_missing"} if boundary == "file" else
                          {"verified", "not_applicable"} if boundary == "repair" else {"verified"})
    prefix = {"source": "project_git_snapshot_", "runtime": "project_runtime_existing_",
              "repair": "project_runtime_repair_", "file": "project_update_component_"}[boundary]
    return reason.startswith(prefix) and (reason.endswith("unavailable") == (state == "unavailable"))
INITIAL_FAILURE_FILE = "initial-update-failure.json"
# Literal allowlists, not a code-shaped regular expression or arbitrary class
# attribute: the parent validates the same contract without importing WOM.
OBSERVED_FAILURE_CODES = frozenset({
    "unclassified_failure", "exact_human_approval_cancelled", "exact_human_approval_key_unavailable",
    "exact_human_approval_claim_failed", "exact_human_approval_resume_claim_invalid",
    "exact_human_approval_resume_candidate_missing", "exact_human_approval_resume_candidate_ambiguous",
    "exact_human_approval_resume_checkpoint_invalid", "exact_human_approval_writer_result_invalid",
    "exact_human_approval_operation_failed", "exact_human_approval_state_unknown",
    "project_update_transaction_invalid", "project_update_transaction_exists",
    "project_update_transaction_not_found", "project_update_transaction_path_unsafe",
    "project_update_transaction_intent_invalid", "project_update_transaction_lock_invalid",
    "project_update_transaction_checkpoint_invalid", "project_update_transaction_checkpoint_write_failed",
    "project_update_transaction_state_transition_invalid", "project_update_transaction_journal_degraded",
    "project_update_transaction_durability_unverified", "project_update_transaction_cleanup_refused",
    "project_update_transaction_not_sealed", "project_update_transaction_candidate_invalid",
    "project_update_transaction_scan_incomplete", "project_update_transaction_reservation_state_changed",
    "project_update_transaction_reservation_busy", "project_update_transaction_reservation_guard_unavailable",
    "project_update_git_runner_unavailable", "project_update_git_runner_unsafe",
    "project_update_git_runner_binding_invalid", "project_update_git_runner_drift",
    "project_update_git_runner_phase_invalid", "project_update_git_runner_command_invalid",
    "project_update_git_runner_closed", "project_update_git_runner_close_unverified",
    "project_update_git_runner_resolved_more_than_once", "project_update_git_runner_handoff_invalid",
    "project_version_update_terminal_cleanup_required", "project_version_update_terminal_cleanup_outcome_unknown",
})
OBSERVED_SUBPROCESS_FAILURE_CODES = frozenset(
    f"{prefix}-{stage}_{outcome}"
    for prefix in ("project-runtime-candidate", "project-runtime-reference", "project-runtime-stage",
                   "project-runtime-final", "project-runtime-reuse", "project-runtime-noop")
    for stage in ("venv", "install", "pip-check", "version", "resources", "new-process",
                  "package-inventory", "python-version")
    for outcome in ("failed", "timeout")
)
OBSERVED_SOURCE_FUNCTIONS = {
    "wom-kit/src/wom_kit/archive_cli.py": frozenset({
        "_command_project_version_update_core", "_project_version_update_approval_read_boundary",
        "_execute_project_version_update_exact_human_approved_write",
        "_project_version_update_privacy_safe_failure_result", "prepare_operation_tracking", "complete_operation_tracking",
    }),
    "wom-kit/src/wom_kit/archive_services.py": frozenset({
        "_wom_kit_project_version_update_live_approval_transaction", "_wom_kit_project_version_update_legacy_core",
        "_wom_kit_project_version_update_legacy_core_generator", "_project_update_close_after_service_failure",
        "_project_update_durable_writer",
    }),
    "wom-kit/src/wom_kit/project_update_transaction.py": frozenset({
        "append", "_append_guard_held", "_validate_live_for_event", "_authority_for_append",
    }),
    "wom-kit/src/wom_kit/project_runtime.py": frozenset({
        "prepare_runtime_candidate", "_initialize_runtime_payload", "_candidate_inventory_snapshot",
        "_path_identity", "_runtime_payload_sha256", "_verify_retained_artifacts", "_run_bounded",
    }),
    "wom-kit/src/wom_kit/exact_human_approval_workflow.py": frozenset({
        "_execute_exact_human_approved_write_core", "_run_started_claim_writer",
        "_resume_exact_human_approved_transaction_auto_core",
    }),
}
OBSERVED_FAILURE_KINDS = frozenset({
    "type_error", "index_error", "key_error", "value_error", "permission_error",
    "file_not_found", "os_error", "unclassified_exception", "approval_workflow_error",
    "transaction_error", "git_runner_error", "domain_error",
})
CLI_OBSERVATION_VALUES = {
    "status": frozenset({"updated_restart_required", "no_change", "blocked", "failed", "error",
        "reservation_busy", "reservation_guard_unavailable", "legacy_prewrite_recovery_blocked",
        "terminal_cleanup_required", "terminal_cleanup_outcome_unknown", "runtime_bootstrap_required"}),
    "state": frozenset({"blocked", "failed", "error", "unavailable", "passed", "not_reached"}),
    "effects_state": frozenset({"none", "unknown", "partial", "complete"}),
    "existing_operation_presence": frozenset({"present", "absent", "unavailable"}),
    "preparation_revalidation_state": frozenset({"passed", "failed", "not_reached", "unavailable"}),
}


class JourneyCheckError(RuntimeError):
    """Only explicit harness assertions can supply public reason codes."""


class InitialUpdateCheckError(JourneyCheckError):
    """Legacy name for the shared typed first-update/resume failure envelope."""

    def __init__(self, observation):
        self.observation = validate_first_update_observation(observation)
        super().__init__("repair_resume_failed" if self.observation["stage"] == "repair_fresh_resume"
                         else "public_update_failed")


class PhaseReporter:
    """Bounded harness observations, never product recovery/approval evidence.

    Keep the original stderr sink so CLI output capture cannot swallow events.
    Child cut/resume are timed at the parent's actual invocation boundaries;
    this does not claim to observe the child's internal implementation stages.
    """

    def __init__(self, *, stream=None, clock=None):
        self.stream = sys.stderr if stream is None else stream
        self.clock = time.monotonic if clock is None else clock
        self.started = self.clock()
        self.sequence = 0
        self.index = 0
        self.active = None
        self.terminal = False

    def _emit(self, stage, event):
        # Do not clamp an over-budget observation into an apparent timely one.
        # The parent retains the validated prefix and marks protocol_invalid.
        elapsed = int((self.clock() - self.started) * 1000)
        self.sequence += 1
        payload = {"schema": PHASE_SCHEMA, "sequence": self.sequence,
                   "stage": stage, "event": event, "elapsed_ms": elapsed}
        self.stream.write(PHASE_PREFIX + json.dumps(payload, separators=(",", ":")) + "\n")
        self.stream.flush()

    def begin(self, stage):
        require(not self.terminal and self.active is None and self.index < len(PHASES)
                and stage == PHASES[self.index], "installed_runtime_journey_failed")
        self.active = stage
        self._emit(stage, "begin")

    def passed(self):
        require(not self.terminal and self.active is not None, "installed_runtime_journey_failed")
        self._emit(self.active, "passed")
        self.index += 1
        self.active = None

    def fail_active(self):
        if self.active is not None and not self.terminal:
            self._emit(self.active, "failed")
            self.terminal = True


def require(condition: object, reason: str) -> None:
    if not condition:
        raise JourneyCheckError(reason if reason in SAFE_REASON_CODES else "installed_runtime_journey_failed")


def verify_installed_origins(modules: dict[str, object], prefix: Path) -> bool:
    """Prove actual module origins, not just an import-success assertion."""
    site = (prefix / "Lib" / "site-packages").resolve(strict=True)
    require(set(modules) == {"wom_kit", "archive_cli", "project_runtime"}, "origin_modules_incomplete")
    for module in modules.values():
        origin = Path(getattr(module, "__file__", "")).resolve(strict=True)
        require(origin.is_file() and origin.is_relative_to(site), "source_checkout_import_denied")
    return True


def command(argv: list[str], *, cwd: Path, timeout: int = 120, expected_code: int = 0,
            runtime_failure_stage: str | None = None) -> str:
    require(runtime_failure_stage is None or type(runtime_failure_stage) is str
            and runtime_failure_stage == "repair_fresh_resume", "journey_arguments_invalid")
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env=environment, timeout=timeout, check=False, **options,
    )
    if completed.returncode != expected_code and runtime_failure_stage is not None:
        observed_failure = None
        try:
            parsed = parse_failure_output(completed.stdout)
            observation = parsed.get("failure_observation")
            if type(observation) is dict and observation["stage"] == runtime_failure_stage:
                observed_failure = observation
        except Exception:
            pass  # Unknown, oversized or private output stays the generic failure.
        if observed_failure is not None:
            # Outside the parser's exception handler: no raw child output or
            # private exception context accompanies the strict typed envelope.
            raise InitialUpdateCheckError(observed_failure)
    require(completed.returncode == expected_code, "synthetic_child_command_failed")
    return completed.stdout.strip()


class CallObservation:
    """Observe real Python boundaries without replacing implementations.

    Only named boundaries are wrapped; their original implementation receives
    the original arguments and supplies the unchanged result or exception. A
    post-return fault may change synthetic disk state or terminate the child,
    but cannot manufacture a verifier/writer result. No global tracing/profile
    callback slows every unrelated file-tree operation.
    """

    def __init__(self, functions, *, on_return=None):
        self.functions = functions
        self.calls = {name: 0 for name in functions}
        self.on_return = on_return
        self.originals = []

    def _wrap(self, name, original):
        @wraps(original)
        def observed(*args, **kwargs):
            self.calls[name] += 1
            value = original(*args, **kwargs)
            if self.on_return is not None:
                self.on_return(name, None, value)
            return value
        return observed

    def __enter__(self):
        try:
            for name, (owner, attribute) in self.functions.items():
                original = getattr(owner, attribute)
                self.originals.append((owner, attribute, original))
                setattr(owner, attribute, self._wrap(name, original))
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *_exception):
        for owner, attribute, original in reversed(self.originals):
            setattr(owner, attribute, original)
        self.originals.clear()


class FirstUpdateObservation:
    """Bounded original-forwarding observations shared by both real journeys."""

    _BOUNDARIES = ("runtime_prepare", "approval_broker")
    _LITERAL_CODES = frozenset({
        "project_version_update_archive_identity_unavailable",
        "project_version_update_approval_archive_identity_changed",
        "project_version_update_live_approval_executor_required",
        "project_version_update_preflight_invalid",
        "project_runtime_candidate_binding_invalid",
        "project_runtime_candidate_preparation_incomplete",
        "project_runtime_candidate_preimage_observation_unavailable",
        "project_runtime_prepared_bundle_cleanup_unverified",
        "project_runtime_tree_changed", "project_runtime_tree_unsafe",
        "project_runtime_parent_identity_drift", "project_runtime_receipt_schema_invalid",
        "project_runtime_preparation_binding_invalid", "project_runtime_preparation_failed",
        "project_runtime_tree_unreadable", "project_runtime_tree_case_collision", "project_runtime_tree_too_large",
        "project_runtime_file_unreadable_or_changed", "project_runtime_artifact_too_large",
        "project_runtime_artifact_size_mismatch", "project_runtime_artifact_sha256_mismatch",
        "project_runtime_wheel_payload_unsafe", "project_runtime_wheel_data_layout_unsupported",
        "project_runtime_wheel_payload_too_large", "project_runtime_wheel_payload_unreadable",
        "project_runtime_wheel_payload_empty", "project_runtime_site_packages_unsafe",
        "project_runtime_wheel_dist_info_invalid", "project_runtime_wheel_payload_collision",
        "project_runtime_wheel_root_collision", "project_runtime_installed_payload_unsafe",
        "project_runtime_installed_payload_mismatch", "project_runtime_installed_payload_inventory_mismatch",
        "project_runtime_trusted_pip_unavailable", "project_runtime_scripts_unsafe",
        "project_runtime_scripts_cleanup_failed", "project_runtime_bytecode_cleanup_failed",
        "project_runtime_pyvenv_unsafe", "project_runtime_pyvenv_write_failed",
        "project_runtime_dist_info_extra_file", "project_runtime_payload_unreadable",
        "project_runtime_prepared_bundle_unsafe", "project_runtime_prepared_bundle_unreadable",
        "project_runtime_prepared_bundle_binding_invalid", "project_runtime_prepared_bundle_drift",
        "project_runtime_artifact_directory_unsafe", "project_runtime_retained_supply_lock_mismatch",
        "project_runtime_artifact_inventory_invalid", "project_runtime_artifact_inventory_unreadable",
        "project_runtime_artifact_inventory_mismatch", "project_runtime_version_mismatch",
        "project_runtime_resource_verification_failed", "project_runtime_new_process_mismatch",
        "project_runtime_package_inventory_invalid", "project_runtime_package_inventory_mismatch",
        "project_runtime_python_version_mismatch",
    }) | OBSERVED_SUBPROCESS_FAILURE_CODES

    def __init__(self, *, stage="first_update"):
        require(type(stage) is str and stage in FAILURE_OBSERVATION_STAGES, "installed_runtime_journey_failed")
        self.stage = stage
        from wom_kit import archive_cli, archive_services, project_runtime
        from wom_kit import exact_human_approval_workflow
        self._services, self._runtime, self._workflow = archive_services, project_runtime, exact_human_approval_workflow
        self.boundaries = {name: {"entered": False, "returned": False} for name in self._BOUNDARIES}
        self.failures = {}
        self.component_observation = None
        self._source_codes = {}
        source_functions = (
            (archive_cli, "archive_cli.py", (
                "_command_project_version_update_core", "_project_version_update_approval_read_boundary",
                "_execute_project_version_update_exact_human_approved_write",
                "_project_version_update_privacy_safe_failure_result",
                "prepare_operation_tracking", "complete_operation_tracking",
            )),
            (archive_services, "archive_services.py", (
                "_wom_kit_project_version_update_live_approval_transaction",
                "_wom_kit_project_version_update_legacy_core",
                "_wom_kit_project_version_update_legacy_core_generator",
                "_project_update_close_after_service_failure",
                "_project_update_durable_writer",
            )),
            (project_runtime, "project_runtime.py", (
                "prepare_runtime_candidate", "_initialize_runtime_payload", "_candidate_inventory_snapshot",
                "_path_identity", "_runtime_payload_sha256", "_verify_retained_artifacts", "_run_bounded",
            )),
            (exact_human_approval_workflow, "exact_human_approval_workflow.py", (
                "_execute_exact_human_approved_write_core", "_run_started_claim_writer",
                "_resume_exact_human_approved_transaction_auto_core",
            )),
        )
        for module, basename, names in source_functions:
            expected_file = os.path.normcase(os.path.abspath(module.__file__))
            for name in names:
                code = getattr(getattr(module, name, None), "__code__", None)
                if isinstance(code, CodeType):
                    self._register_code(code, expected_file, "wom-kit/src/wom_kit/" + basename, name)
        transaction = archive_services.project_update_transaction
        expected_file = os.path.normcase(os.path.abspath(transaction.__file__))
        # Only these original methods and their literal nested code objects
        # identify the refusal branch. Never inspect transaction state, frame
        # locals, argument values, arbitrary members or caller-supplied phases.
        for name in ("append", "_append_guard_held", "_validate_live_for_event", "_authority_for_append"):
            code = getattr(getattr(transaction.ProjectUpdateTransaction, name, None), "__code__", None)
            if isinstance(code, CodeType):
                self._register_code(code, expected_file,
                                    "wom-kit/src/wom_kit/project_update_transaction.py", name)

    def _register_code(self, code, expected_file, relative_file, owner_function=None):
        if os.path.normcase(os.path.abspath(code.co_filename)) != expected_file:
            return
        owner_function = code.co_name if owner_function is None else owner_function
        self._source_codes[id(code)] = (code, relative_file, owner_function)
        # Nested functions belong to these exact, checked-in code objects;
        # no frame globals/locals or arbitrary module members are inspected.
        for constant in code.co_consts:
            if isinstance(constant, CodeType):
                self._register_code(constant, expected_file, relative_file, owner_function)

    def _source_frame(self, error):
        selected = None
        trace = error.__traceback__
        while trace is not None:
            code = trace.tb_frame.f_code
            known = self._source_codes.get(id(code))
            if known is not None and known[0] is code:
                selected = {"file": known[1], "line": trace.tb_lineno, "function": known[2]}
            trace = trace.tb_next
        return selected

    def _error(self, error):
        archive_services, project_runtime, exact_human_approval_workflow = self._services, self._runtime, self._workflow
        kinds = {TypeError: "type_error", IndexError: "index_error", KeyError: "key_error",
                 ValueError: "value_error", PermissionError: "permission_error",
                 FileNotFoundError: "file_not_found", OSError: "os_error"}
        kind, code = kinds.get(type(error), "unclassified_exception"), "unclassified_failure"
        typed_codes = (
            (exact_human_approval_workflow.ExactHumanApprovalWorkflowError, "approval_workflow_error"),
            (archive_services.project_update_transaction.ProjectUpdateTransactionError, "transaction_error"),
            (archive_services.project_update_git_runner.ProjectUpdateGitRunnerError, "git_runner_error"),
        )
        for error_type, fixed_kind in typed_codes:
            if type(error) is error_type:
                kind = fixed_kind
                candidate = error.code
                if type(candidate) is str and candidate in error_type._CODES and candidate in OBSERVED_FAILURE_CODES:
                    code = candidate
                break
        else:
            if type(error) in {archive_services.ArchiveServiceError, project_runtime.ProjectRuntimeError,
                               project_runtime.PreparedRuntimeBundleCleanupError,
                               project_runtime.PreparedRuntimeCandidateIncompleteError}:
                kind = "domain_error"
                if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in self._LITERAL_CODES:
                    code = error.args[0]
        return {"kind": kind, "code": code, "source": self._source_frame(error)}

    def record(self, stage, error):
        if stage not in {*self._BOUNDARIES, "cli_failure_projection", "first_cli_call"}:
            raise ValueError("unknown_observation_stage")
        if stage in self.failures:
            return
        chain, seen = [], set()
        while isinstance(error, BaseException) and id(error) not in seen and len(chain) < 8:
            seen.add(id(error))
            chain.append(self._error(error))
            error = error.__cause__ if error.__cause__ is not None else error.__context__
        self.failures[stage] = chain

    def boundary(self, stage, original):
        if stage not in self._BOUNDARIES:
            raise ValueError("unknown_observation_stage")

        @wraps(original)
        def observe(*args, **kwargs):
            self.boundaries[stage]["entered"] = True
            try:
                result = original(*args, **kwargs)
            except Exception as error:
                self.record(stage, error)
                raise
            self.boundaries[stage]["returned"] = True
            return result
        return observe

    def failure_projector(self, original):
        @wraps(original)
        def observe(error):
            self.record("cli_failure_projection", error)
            return original(error)
        return observe

    @contextmanager
    def live_components(self):
        """Failure-only views of existing calls; no reread, retry or tracing.

        Private state is borrowed only while the original live helper runs.
        Only fixed classifications survive that call. The original classifier
        result object ties the sample to the exact subsequent validator call.
        """
        services, runtime = self._services, self._runtime
        transaction = services.project_update_transaction
        owner = threading.get_ident()
        active = None
        probes, roles, observed, pending_live = [], {}, None, None

        def record(boundary, role, result=None, *, exception=False):
            if len(probes) >= 32:
                return
            result = result if type(result) is dict else {}
            raw_state = result.get("state")
            raw_reason = result.get("reason_code")
            state = "exception" if exception else (
                raw_state if type(raw_state) is str and raw_state in COMPONENT_PROBE_STATES else "unclassified")
            reason = raw_reason if type(raw_reason) is str and raw_reason in COMPONENT_OBSERVATION_REASONS else None
            fields = []
            if boundary == "source" and state == "passed" and active is not None:
                expected = active.private_plan.get("preflight_git_snapshot")
                current = result.get("snapshot")
                if type(expected) is dict and type(current) is dict:
                    fields = sorted(name for name in COMPONENT_SOURCE_FIELDS if expected.get(name) != current.get(name))
            row = {"boundary": boundary, "role": role, "state": state,
                   "reason_code": reason, "changed_source_fields": fields}
            if not _component_observation_row_valid(row):
                row["reason_code"] = None
            if _component_observation_row_valid(row):
                probes.append(row)

        def safe_record(*args, **kwargs):
            try:
                record(*args, **kwargs)
            except Exception:
                pass  # Diagnostic failure must not replace original behavior.

        def probe(boundary, original):
            @wraps(original)
            def forward(*args, **kwargs):
                if threading.get_ident() != owner or active is None:
                    return original(*args, **kwargs)
                role = boundary if boundary in {"source", "runtime"} else (
                    "runtime" if boundary == "repair" else "unclassified_component")
                if boundary == "file" and len(args) >= 2:
                    try:
                        for reference, path in active.component_paths.items():
                            if path == args[1]:
                                role = roles.get(reference, "unclassified_component")
                                break
                    except Exception:
                        pass
                try:
                    result = original(*args, **kwargs)
                except Exception:
                    safe_record(boundary, role, exception=True)
                    raise
                safe_record(boundary, role, result)
                return result
            return forward

        original_live = services._project_update_live_component_sha256

        @wraps(original_live)
        def live(state):
            nonlocal active, probes, roles, observed, pending_live
            if threading.get_ident() != owner:
                return original_live(state)
            probes, roles, observed, pending_live = [], {}, None, None
            try:
                for component in state.transaction.intent.components:
                    role = component.role
                    roles[component.component_ref] = (
                        role if type(role) is str and role in COMPONENT_OBSERVATION_ROLES else "unclassified_component")
            except Exception:
                roles = {}
            active = state
            try:
                result = original_live(state)
                pending_live = result
                return result
            finally:
                active = None

        original_classify = transaction.classify_components

        @wraps(original_classify)
        def classify(*args, **kwargs):
            nonlocal observed
            result = original_classify(*args, **kwargs)
            supplied = args[1] if len(args) > 1 else kwargs.get("live_sha256")
            if threading.get_ident() == owner and pending_live is not None and supplied is pending_live:
                observed = result
            return result

        original_validate = transaction.ProjectUpdateTransaction._validate_live_for_event

        @wraps(original_validate)
        def validate(*args, **kwargs):
            nonlocal observed
            try:
                return original_validate(*args, **kwargs)
            except Exception:
                classification = args[3] if len(args) > 3 else kwargs.get("classification")
                if (threading.get_ident() == owner and observed is classification
                        and observed is not None and self.component_observation is None):
                    try:
                        rows = []
                        # Preserve the decisive unknown roles before ancillary
                        # probes, even when a diagnostic fixture fills the cap.
                        components = sorted(classification.component_states, key=lambda item: item[1] != "unknown")
                        for reference, state in components:
                            if len(rows) >= 32:
                                break
                            rows.append({"boundary": "classification",
                                         "role": roles.get(reference, "unclassified_component"),
                                         "state": state if type(state) is str and state in COMPONENT_CLASSIFICATION_STATES else "unclassified",
                                         "reason_code": None, "changed_source_fields": []})
                        rows.extend(probes[:32 - len(rows)])
                        self.component_observation = {"schema": COMPONENT_OBSERVATION_SCHEMA, "events": rows}
                    except Exception:
                        pass
                raise
            finally:
                if threading.get_ident() == owner:
                    observed = None

        with ExitStack() as stack:
            for module, name, replacement in (
                (services, "_project_update_live_component_sha256", live),
                (services, "_wom_kit_project_update_git_snapshot_observation",
                 probe("source", services._wom_kit_project_update_git_snapshot_observation)),
                (services, "_project_update_runtime_candidate_observation",
                 probe("runtime", services._project_update_runtime_candidate_observation)),
                (runtime, "runtime_repair_state_observation", probe("repair", runtime.runtime_repair_state_observation)),
                (services, "_project_update_component_bytes_observation",
                 probe("file", services._project_update_component_bytes_observation)),
                (transaction, "classify_components", classify),
                (transaction.ProjectUpdateTransaction, "_validate_live_for_event", validate),
            ):
                stack.enter_context(mock.patch.object(module, name, new=replacement))
            try:
                yield
            finally:
                active, observed, pending_live = None, None, None
                roles.clear()

    def diagnostic(self, *, native_observed):
        return json.dumps({"stage": self.stage, "boundaries": self.boundaries,
                           "failures": self.failures, "native_observed": bool(native_observed)},
                          sort_keys=True)

    def failure_payload(self, *, native_observed, cli_code=None, cli_result=None):
        value = cli_result if type(cli_result) is dict else {}
        fields = {name: value.get(name) for name in CLI_OBSERVATION_VALUES}
        runtime = value.get("project_runtime")
        revalidation = runtime.get("preparation_revalidation") if type(runtime) is dict else None
        fields["preparation_revalidation_state"] = (
            revalidation.get("state") if type(revalidation) is dict else None)
        fields = {name: item if type(item) is str and item in CLI_OBSERVATION_VALUES[name] else None
                  for name, item in fields.items()}
        allowed = OBSERVED_FAILURE_CODES | self._LITERAL_CODES
        supplied_codes = value.get("reason_codes")
        if type(supplied_codes) is not list:
            supplied_codes = []
        candidates = [value.get("reason_code"), *supplied_codes[:32]]
        fields["reason_codes"] = sorted({item for item in candidates
                                         if type(item) is str and item in allowed})
        fields["return_code"] = cli_code if type(cli_code) is int and cli_code in {0, 1, 2} else None
        payload = {
            "schema": FAILURE_OBSERVATION_SCHEMA, "scope": "synthetic_harness_only",
            "product_recovery_evidence": False, "private_values_echoed": False,
            "stage": self.stage, "boundaries": self.boundaries, "failures": self.failures,
            "native_observed": native_observed is True, "cli": fields,
        }
        if self.component_observation is not None:
            payload["component_observation"] = self.component_observation
        return validate_first_update_observation(payload)


def validate_first_update_observation(value):
    """Reject rather than echo any unexpected output from the child boundary."""
    required = {
        "schema", "scope", "product_recovery_evidence", "private_values_echoed", "stage",
        "boundaries", "failures", "native_observed", "cli",
    }
    valid = type(value) is dict and (set(value) == required or set(value) == required | {"component_observation"})
    require(valid, "installed_runtime_journey_failed")
    if "component_observation" in value:
        component = value["component_observation"]
        require(type(component) is dict and set(component) == {"schema", "events"}
                and component["schema"] == COMPONENT_OBSERVATION_SCHEMA
                and type(component["events"]) is list and 1 <= len(component["events"]) <= 32,
                "installed_runtime_journey_failed")
        for row in component["events"]:
            require(_component_observation_row_valid(row), "installed_runtime_journey_failed")
    require(value["schema"] == FAILURE_OBSERVATION_SCHEMA and value["scope"] == "synthetic_harness_only"
            and value["product_recovery_evidence"] is False and value["private_values_echoed"] is False
            and type(value["stage"]) is str and value["stage"] in FAILURE_OBSERVATION_STAGES
            and type(value["native_observed"]) is bool,
            "installed_runtime_journey_failed")
    boundaries = value["boundaries"]
    require(type(boundaries) is dict and set(boundaries) == set(FirstUpdateObservation._BOUNDARIES),
            "installed_runtime_journey_failed")
    for row in boundaries.values():
        require(type(row) is dict and set(row) == {"entered", "returned"}
                and all(type(item) is bool for item in row.values())
                and (not row["returned"] or row["entered"]), "installed_runtime_journey_failed")
    failures = value["failures"]
    require(type(failures) is dict and set(failures) <= {
        *FirstUpdateObservation._BOUNDARIES, "cli_failure_projection", "first_cli_call"},
        "installed_runtime_journey_failed")
    for chain in failures.values():
        require(type(chain) is list and 1 <= len(chain) <= 8, "installed_runtime_journey_failed")
        for row in chain:
            require(type(row) is dict and set(row) == {"kind", "code", "source"}
                    and type(row["kind"]) is str and row["kind"] in OBSERVED_FAILURE_KINDS
                    and type(row["code"]) is str
                    and row["code"] in OBSERVED_FAILURE_CODES | FirstUpdateObservation._LITERAL_CODES,
                    "installed_runtime_journey_failed")
            source = row["source"]
            if source is not None:
                require(type(source) is dict and set(source) == {"file", "line", "function"}
                        and type(source["file"]) is str and source["file"] in OBSERVED_SOURCE_FUNCTIONS
                        and type(source["function"]) is str
                        and source["function"] in OBSERVED_SOURCE_FUNCTIONS[source["file"]]
                        and type(source["line"]) is int and 1 <= source["line"] <= 1_000_000,
                        "installed_runtime_journey_failed")
    cli = value["cli"]
    require(type(cli) is dict and set(cli) == set(CLI_OBSERVATION_VALUES) | {"return_code", "reason_codes"},
            "installed_runtime_journey_failed")
    for name, allowed in CLI_OBSERVATION_VALUES.items():
        require(cli[name] is None or type(cli[name]) is str and cli[name] in allowed,
                "installed_runtime_journey_failed")
    require(cli["return_code"] is None or type(cli["return_code"]) is int and cli["return_code"] in {0, 1, 2},
            "installed_runtime_journey_failed")
    codes = cli["reason_codes"]
    require(type(codes) is list and len(codes) <= 32 and all(type(item) is str
            and item in OBSERVED_FAILURE_CODES | FirstUpdateObservation._LITERAL_CODES for item in codes)
            and codes == sorted(set(codes)), "installed_runtime_journey_failed")
    return json.loads(json.dumps(value, allow_nan=False))


def parse_failure_output(stdout):
    """Pure strict parent/child failure protocol; this never proves completion."""
    require(type(stdout) is str and len(stdout.encode("utf-8")) <= FAILURE_OUTPUT_LIMIT_BYTES,
            "installed_runtime_journey_failed")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "installed_runtime_journey_failed")
            value[key] = item
        return value

    value = json.loads(stdout, object_pairs_hook=unique,
                       parse_constant=lambda _value: require(False, "installed_runtime_journey_failed"))
    require(type(value) is dict and set(value) in (
        {"ok", "schema", "reason_code"}, {"ok", "schema", "reason_code", "failure_observation"}),
        "installed_runtime_journey_failed")
    require(value["ok"] is False and value["schema"] == SCHEMA and type(value["reason_code"]) is str
            and value["reason_code"] in SAFE_REASON_CODES | {"installed_runtime_journey_failed"},
            "installed_runtime_journey_failed")
    if "failure_observation" in value:
        value["failure_observation"] = validate_first_update_observation(value["failure_observation"])
        expected_reason = ("repair_resume_failed" if value["failure_observation"]["stage"] == "repair_fresh_resume"
                           else "public_update_failed")
        require(value["reason_code"] == expected_reason, "installed_runtime_journey_failed")
    return value


def _initial_failure_root_identity(root):
    # A fixed child filename below the newly created synthetic root only.
    # Never follow a junction/symlink to preserve diagnostic output elsewhere.
    root = Path(root)
    for path in (root, *root.parents):
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise JourneyCheckError("installed_runtime_journey_failed")
    info = root.lstat()
    return (info.st_dev, info.st_ino)


def write_initial_failure_observation(root, expected_identity, value):
    """No-overwrite diagnostic artifact, not a claim/checkpoint or completion."""
    valid = None
    try:
        valid = parse_failure_output(json.dumps(value, allow_nan=False))
        raw = json.dumps(valid, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if _initial_failure_root_identity(root) != expected_identity:
            raise JourneyCheckError("installed_runtime_journey_failed")
        # Reuse the installed durable writer's retained-parent/no-replace
        # primitives. This is reached only after importing the candidate WOM.
        from wom_kit import project_update_transaction as durable
        with durable._bound_directory_for_move(root) as parent:
            if parent.identity != expected_identity:
                raise JourneyCheckError("installed_runtime_journey_failed")
            if os.name == "nt":
                durable._write_new(parent.path / INITIAL_FAILURE_FILE, raw, within=parent.path)
            else:
                descriptor = os.open(INITIAL_FAILURE_FILE,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=parent.descriptor)
                try:
                    durable._write_all(descriptor, raw)
                    os.fsync(descriptor)
                    os.fsync(parent.descriptor)
                finally:
                    os.close(descriptor)
            durable._assert_named_reservation_directory_identity(parent.path, expected_identity)
        return
    except Exception:
        pass
    raise JourneyCheckError("installed_runtime_journey_failed")


def read_initial_failure_observation(root):
    """Bounded read-only recovery of strict data even after parent rejection."""
    result = None
    try:
        root = Path(root)
        root_identity = _initial_failure_root_identity(root)
        path = root / INITIAL_FAILURE_FILE
        before = path.lstat()
        identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        safe = lambda info: (stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400 and info.st_nlink == 1
            and 0 < info.st_size <= FAILURE_OUTPUT_LIMIT_BYTES)
        if not safe(before):
            raise JourneyCheckError("installed_runtime_journey_failed")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if not safe(opened) or identity(opened) != identity(before):
                raise JourneyCheckError("installed_runtime_journey_failed")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(FAILURE_OUTPUT_LIMIT_BYTES + 1)
            if identity(os.fstat(descriptor)) != identity(opened):
                raise JourneyCheckError("installed_runtime_journey_failed")
        finally:
            os.close(descriptor)
        if identity(path.lstat()) != identity(before) or _initial_failure_root_identity(root) != root_identity:
            raise JourneyCheckError("installed_runtime_journey_failed")
        result = parse_failure_output(raw.decode("utf-8"))
    except Exception:
        pass
    if result is None:
        raise JourneyCheckError("installed_runtime_journey_failed")
    return result



def cli_json(archive_cli, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = archive_cli.main(argv)
    return code, json.loads(stdout.getvalue())


def observed_initial_update(archive_cli, project_runtime, cli, argv, native):
    """Observe the real first call without substituting prepare/broker/writer."""
    return _observed_runtime_call(archive_cli, project_runtime, cli, argv, native, stage="first_update")


def observed_repair_resume(archive_cli, project_runtime, cli, argv, native):
    """Use the same observer on the actual imported auto-resume broker alias."""
    return _observed_runtime_call(archive_cli, project_runtime, cli, argv, native, stage="repair_fresh_resume")


def _observed_runtime_call(archive_cli, project_runtime, cli, argv, native, *, stage):
    observation = FirstUpdateObservation(stage=stage)
    broker_name = ("_resume_exact_human_approved_transaction_auto_core" if stage == "repair_fresh_resume"
                   else "_execute_project_version_update_exact_human_approved_write")
    code, result = None, None
    with ExitStack() as stack:
        stack.enter_context(observation.live_components())
        stack.enter_context(mock.patch.object(project_runtime, "prepare_runtime_candidate",
            new=observation.boundary("runtime_prepare", project_runtime.prepare_runtime_candidate)))
        stack.enter_context(mock.patch.object(archive_cli, broker_name,
            new=observation.boundary("approval_broker", getattr(archive_cli, broker_name))))
        stack.enter_context(mock.patch.object(archive_cli, "_project_version_update_privacy_safe_failure_result",
            new=observation.failure_projector(archive_cli._project_version_update_privacy_safe_failure_result)))
        try:
            code, result = cli(argv)
        except Exception as error:
            observation.record("first_cli_call", error)
    if code != 0 or type(result) is not dict or result.get("status") != "updated_restart_required":
        # Raise after leaving the exception handler: do not retain its private
        # traceback as this public harness exception's context.
        raise InitialUpdateCheckError(observation.failure_payload(
            native_observed=native.called, cli_code=code, cli_result=result))
    return code, result


def approved_arguments(project: Path, version: str) -> list[str]:
    return ["project-version-update", str(project), "--target", "v" + version,
            "--approve", "--affirm-external-writers-quiescent", "--reviewed-by",
            "person:wheel-runtime-reviewer", "--format", "json"]


def local_transport(project_runtime, wheel: Path, bootstrap):
    original_download = project_runtime._download_exact_artifact

    def transport(**kwargs):
        if kwargs["url"] != bootstrap.url:
            return original_download(**kwargs)
        payload = wheel.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == kwargs["expected_sha256"], "local_transport_hash_mismatch")
        size = kwargs.get("expected_size")
        require(size is None or size == len(payload), "local_transport_size_mismatch")
        Path(kwargs["destination"]).write_bytes(payload)
        return len(payload)

    return transport


def assert_no_active_update(project: Path, project_runtime, transaction) -> None:
    require(not (project / transaction.PROJECT_UPDATE_LOCK_LOGICAL).exists(), "active_update_lock_remains")
    transactions = project / transaction.TRANSACTION_ROOT_LOGICAL
    require(not transactions.exists() or not any(
        path.is_dir() and (path.name.startswith("update_") or path.name.startswith(".cleanup_update_"))
        for path in transactions.iterdir()
    ), "active_update_transaction_remains")
    require(not any(path.name == project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME
                    for path in (project / ".zettel-kasten").rglob("*")), "runtime_candidate_remains")


def exercise_installed_drift(project, version, project_runtime, archive_services, native_type, cli, phases):
    """Change real source/ref after the first genuine installed-runtime proof."""
    metadata = project / ".zettel-kasten"
    mirror = metadata / "source"
    source_file = mirror / "wom-kit/src/wom_kit/__init__.py"
    source_before = source_file.read_bytes()
    tag = "refs/tags/v" + version
    tag_before = git(mirror, "rev-parse", tag)
    head = git(mirror, "rev-parse", "HEAD")
    runtime = project_runtime.runtime_path(project, version)
    runtime_before = project_runtime._candidate_inventory_snapshot(runtime)
    receipt_root = metadata / "receipts/version-updates"
    unchanged = {path: path.read_bytes() for path in [metadata / "installed-version.txt",
                 project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE, *receipt_root.glob("*.json")]}
    receipt_names = {path.name for path in receipt_root.glob("*.json")}
    durations = {}
    for kind in ("source", "ref"):
        if kind == "ref":
            phases.begin("ref_drift")
        injected = []

        def inject(name, _frame, result):
            if name != "verify" or injected:
                return
            require(isinstance(result, dict) and result.get("reusable") is True, "drift_injection_not_observed")
            if kind == "source":
                source_file.write_bytes(source_before + b"\n# synthetic source drift\n")
            else:
                git(mirror, "update-ref", tag, head, tag_before)
            injected.append(True)

        started = time.monotonic()
        try:
            with CallObservation({"verify": (project_runtime, "verify_existing_runtime_for_noop"),
                                  "prepare": (project_runtime, "prepare_runtime_candidate"),
                                  "initialize": (project_runtime, "_initialize_runtime_payload")}, on_return=inject) as observer, mock.patch.object(
                native_type, "show", side_effect=JourneyCheckError("drift_requested_effect"),
            ) as native, mock.patch.object(project_runtime, "_download_exact_artifact",
                                          side_effect=JourneyCheckError("drift_requested_effect")) as download:
                code, result = cli(approved_arguments(project, version))
            require(injected == [True], "drift_injection_not_observed")
            revalidation = result.get("project_runtime", {}).get("preparation_revalidation", {})
            dimension = "git_snapshot" if kind == "source" else "target_refs"
            require(code != 0 and result.get("status") == "blocked"
                    and dimension in revalidation.get("changed_dimensions", []), "drift_not_blocked")
            require(native.call_count == download.call_count == 0
                    and observer.calls["prepare"] == observer.calls["initialize"] == 0, "drift_requested_effect")
            require(project_runtime._candidate_inventory_snapshot(runtime) == runtime_before
                    and all(path.read_bytes() == content for path, content in unchanged.items())
                    and {path.name for path in receipt_root.glob("*.json")} == receipt_names
                    and git(mirror, "rev-parse", "HEAD") == head, "drift_domain_changed")
            require(source_file.read_bytes() == (source_before + b"\n# synthetic source drift\n" if kind == "source" else source_before)
                    and git(mirror, "rev-parse", tag) == (head if kind == "ref" else tag_before), "drift_domain_changed")
            assert_no_active_update(project, project_runtime, archive_services.project_update_transaction)
        finally:
            # Only the harness restores its own injected synthetic fault. WOM
            # must leave changed user bytes/refs intact when it refuses a write.
            if injected:
                if kind == "source":
                    source_file.write_bytes(source_before)
                else:
                    git(mirror, "update-ref", tag, tag_before, head)
        durations[kind + "_drift"] = round(time.monotonic() - started, 3)
        phases.passed()
    return durations


def progress_timing(status_seconds: list[float], terminal_seconds: float) -> dict[str, float | int]:
    """Include startup and the final silent interval; never clamp a bad gap."""
    require(bool(status_seconds), "doctor_startup_progress_missing")
    points = [0.0, *status_seconds, terminal_seconds]
    gaps = [after - before for before, after in zip(points, points[1:])]
    require(all(gap >= 0 for gap in gaps), "doctor_startup_output_invalid")
    maximum_gap = max(gaps)
    require(status_seconds[0] <= 2.0 and maximum_gap <= 10.0, "doctor_startup_progress_deadline")
    return {"first_status_seconds": status_seconds[0], "maximum_gap_seconds": maximum_gap,
            "terminal_seconds": terminal_seconds, "status_event_count": len(status_seconds)}


def measure_doctor_startup(argv: list[str], *, cwd: Path) -> dict[str, float | int]:
    """Measure the real public child from before launch, with bounded pipes.

    The enclosing checker already contains this entire descendant tree in its
    kill-on-close job. This observer creates no venv and stores no progress text.
    """
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    output: list[bytes] = []
    status_seconds: list[float] = []
    failures: list[bool] = []
    started = time.monotonic()
    process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=environment, **options)

    def read_pipe(stream, *, progress: bool):
        total = 0
        try:
            while True:
                chunk = stream.readline(4096) if progress else stream.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > 1024 * 1024:
                    failures.append(True)
                    process.kill()
                    break
                if progress:
                    if chunk.startswith((b"[wom] startup:", b"[doctor] ")):
                        status_seconds.append(time.monotonic() - started)
                else:
                    output.append(chunk)
        except (OSError, ValueError):
            failures.append(True)
        finally:
            stream.close()

    readers = [threading.Thread(target=read_pipe, args=(process.stdout,), kwargs={"progress": False}, daemon=True),
               threading.Thread(target=read_pipe, args=(process.stderr,), kwargs={"progress": True}, daemon=True)]
    for reader in readers:
        reader.start()
    try:
        code = process.wait(timeout=180)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
        raise JourneyCheckError("doctor_startup_probe_failed") from None
    finally:
        for reader in readers:
            reader.join(timeout=2)
    require(not failures and not any(reader.is_alive() for reader in readers), "doctor_startup_probe_output_bound")
    require(code == 0, "doctor_startup_probe_failed")
    # Completion is observable only after the child exits and both pipes are
    # drained. Timestamp that boundary, not an earlier wait()/reader race.
    terminal = time.monotonic() - started
    try:
        document = json.loads(b"".join(output).decode("utf-8"))
    except (ValueError, UnicodeError):
        raise JourneyCheckError("doctor_startup_output_invalid") from None
    require(isinstance(document, dict) and document.get("ok") is True, "doctor_startup_output_invalid")
    return progress_timing(status_seconds, terminal)


def git(root: Path, *args: str) -> str:
    return command(["git", "-C", str(root), *args], cwd=root)


def create_project(root: Path, source: Path, shim: Path, version: str) -> dict[str, Path | str]:
    """The old source is inert fixture data; the target is exact build input."""
    upstream = root / "upstream"
    package = upstream / "wom-kit" / "src" / "wom_kit"
    package.mkdir(parents=True)
    old_version = "0.0.1"
    (package / "__init__.py").write_text(f'__version__ = "{old_version}"\n', encoding="utf-8")
    (package / "archive_cli.py").write_text("def main(argv=None):\n    return 0\n", encoding="utf-8")
    (upstream / "wom-kit" / "pyproject.toml").write_text(
        f'[project]\nname = "wom-kit"\nversion = "{old_version}"\n', encoding="utf-8",
    )
    old_shim = upstream / "wom_kit" / "__init__.py"
    old_shim.parent.mkdir()
    old_shim.write_text(f'__version__ = "{old_version}"\n', encoding="utf-8")
    wrapper = upstream / "wom-kit" / "cli" / "archive.py"
    wrapper.parent.mkdir()
    shutil.copyfile(source / "cli" / "archive.py", wrapper)
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "wheel-fixture")
    git(upstream, "config", "user.email", "wheel-fixture.invalid")
    git(upstream, "config", "core.autocrlf", "false")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "synthetic predecessor")
    git(upstream, "tag", "-a", "v" + old_version, "-m", "synthetic predecessor")
    project = root / "project"
    metadata = project / ".zettel-kasten"
    metadata.mkdir(parents=True)
    mirror = metadata / "source"
    command([
        "git", "-c", "protocol.file.allow=always", "-c", "core.autocrlf=false",
        "clone", "--quiet", str(upstream), str(mirror),
    ], cwd=root)
    git(mirror, "checkout", "--detach", "--quiet", "v" + old_version)
    git(mirror, "config", "user.name", "wheel-fixture")
    git(mirror, "config", "user.email", "wheel-fixture.invalid")
    for pin in (metadata / "installed-version.txt", mirror / "installed-version.txt"):
        pin.write_text("v" + old_version + "\n", encoding="utf-8")
    archive = project / "archive"
    archive.mkdir()
    (archive / "archive.yml").write_text(
        "archive_id: archive:personal:wheel-runtime-fixture\narchive_type: personal\n",
        encoding="utf-8",
    )

    # Copy exact package source and every manifest-bound source resource from
    # the same immutable build input, not a tiny replacement WOM package.
    shutil.copytree(source / "src", upstream / "wom-kit" / "src", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
    manifest = json.loads((source / "src/wom_kit/_resources/resource-manifest.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        relative = Path(row["source"])
        require(not relative.is_absolute() and ".." not in relative.parts, "source_resource_path_invalid")
        origin = source / relative
        require(hashlib.sha256(origin.read_bytes()).hexdigest() == row["sha256"], "source_resource_drift")
        destination = upstream / "wom-kit" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    for name in ("pyproject.toml", "project-runtime-policy.json", f"project-runtime-supply-lock-v{version}.json"):
        shutil.copyfile(source / name, upstream / "wom-kit" / name)
    shutil.copyfile(shim, old_shim)
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "exact candidate source")
    git(upstream, "tag", "-a", "v" + version, "-m", "synthetic candidate tag")
    return {"project": project, "metadata": metadata, "archive": archive,
            "target_commit": git(upstream, "rev-parse", "HEAD")}


class _MemoryOnlyApprovalKey:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(b"w" * 32)
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


def run_repair_worker(wheel: Path, root: Path, version: str, mode: str) -> dict[str, object]:
    """Fresh installed process: one real repair, or exact ID-free continuation."""
    require(mode in {"interrupt", "resume"}, "repair_worker_arguments_invalid")
    require(os.name == "nt" and sys.version_info[:2] == (3, 12), "windows_cpython312_required")
    from wom_kit import archive_cli, archive_services, project_runtime
    from wom_kit import exact_human_approval_windows, exact_human_approval_workflow
    import wom_kit
    verify_installed_origins({"wom_kit": wom_kit, "archive_cli": archive_cli,
                              "project_runtime": project_runtime}, Path(sys.prefix))
    direct = json.loads(importlib.metadata.distribution("wom-kit").read_text("direct_url.json") or "{}")
    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    require(wom_kit.__version__ == version and
            direct.get("archive_info", {}).get("hashes", {}).get("sha256") == wheel_hash, "repair_worker_origin_invalid")
    project = root / "project"
    bootstrap = project_runtime.BootstrapWheel(version=version, tag="v" + version,
        url="https://example.invalid/candidate/" + wheel.name, sha256=wheel_hash, file_name=wheel.name)
    native_calls = []

    def native_decision(*_args, **_kwargs):
        native_calls.append(True)
        require(mode == "interrupt" and len(native_calls) == 1, "repair_resume_requested_effect")
        return exact_human_approval_windows.APPROVE_BUTTON_ID, False

    observer = None

    def interrupt_at_checkpoint(name, _frame, checkpoint):
        if (mode == "interrupt" and name == "append"
                and getattr(checkpoint, "phase", None) == "runtime"
                and getattr(checkpoint, "stage", None) == "intent"):
            require(native_calls == [True] and observer.calls["prepare"] == 1
                    and observer.calls["initialize"] == 1, "repair_interruption_not_reached")
            # The real append has returned: its fsynced journal and released
            # append guard exist, but runtime promotion has not executed yet.
            os._exit(86)

    argv = (approved_arguments(project, version) if mode == "interrupt" else
            ["project-version-update", str(project), "--resume",
             "--affirm-external-writers-quiescent", "--format", "json"])
    transport = local_transport(project_runtime, wheel, bootstrap)
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(project_runtime, "bootstrap_wheel_for_target",
                            return_value=(bootstrap, bootstrap.public_summary())))
        stack.enter_context(mock.patch.object(exact_human_approval_workflow, "_production_key_provider",
                            return_value=_MemoryOnlyApprovalKey()))
        native = stack.enter_context(mock.patch.object(exact_human_approval_windows._CtypesTaskDialogNative, "show",
                            side_effect=native_decision))
        download = stack.enter_context(mock.patch.object(project_runtime, "_download_exact_artifact", side_effect=transport))
        observer = stack.enter_context(CallObservation({"prepare": (project_runtime, "prepare_runtime_candidate"),
            "initialize": (project_runtime, "_initialize_runtime_payload"),
            "append": (archive_services.project_update_transaction.ProjectUpdateTransaction, "append")},
            on_return=interrupt_at_checkpoint))
        if mode == "resume":
            code, result = observed_repair_resume(archive_cli, project_runtime,
                lambda selected: cli_json(archive_cli, selected), argv, native)
        else:
            code, result = cli_json(archive_cli, argv)
    require(mode == "resume", "repair_interruption_not_reached")
    require(code == 0 and result.get("status") == "updated_restart_required"
            and result.get("terminal_finalization", {}).get("transaction_cleanup_completed") is True,
            "repair_resume_failed")
    require(native_calls == [] and download.call_count == 0
            and observer.calls["prepare"] == observer.calls["initialize"] == 0, "repair_resume_requested_effect")
    assert_no_active_update(project, project_runtime, archive_services.project_update_transaction)
    return {"ok": True, "schema": SCHEMA, "worker": "resume",
            "same_approval_resumed": True, "no_new_preparation_download_or_approval": True,
            "private_values_echoed": False}


def exercise_installed_repair(wheel, root, project, version, project_runtime, archive_services, cli, native_type, phases):
    phases.begin("repair_preimage")
    runtime = project_runtime.runtime_path(project, version)
    package_file = runtime / "Lib/site-packages/wom_kit/__init__.py"
    healthy_bytes = package_file.read_bytes()
    package_file.write_bytes(healthy_bytes + b"\n# synthetic installed payload damage\n")
    damaged_inventory = project_runtime._candidate_inventory_snapshot(runtime)
    metadata = project / ".zettel-kasten"
    receipt_root = metadata / "receipts/version-updates"
    stable = {path: path.read_bytes() for path in [metadata / "installed-version.txt",
              project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE, *receipt_root.glob("*.json")]}
    receipt_names = {path.name for path in receipt_root.glob("*.json")}
    worker = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--repair-worker",
              str(wheel), str(root), version]
    phases.passed()
    phases.begin("repair_prepare_to_cut")
    started = time.monotonic()
    command([*worker, "interrupt"], cwd=root, timeout=600, expected_code=86)
    interruption_seconds = time.monotonic() - started
    phases.passed()
    phases.begin("repair_cut_validation")
    require(project_runtime._candidate_inventory_snapshot(runtime) == damaged_inventory
            and all(path.read_bytes() == content for path, content in stable.items())
            and {path.name for path in receipt_root.glob("*.json")} == receipt_names, "repair_preimage_changed_before_switch")
    transaction = archive_services.project_update_transaction
    transaction_paths = [path for path in (project / transaction.TRANSACTION_ROOT_LOGICAL).iterdir()
                         if path.is_dir() and transaction.TRANSACTION_REF_RE.fullmatch(path.name)]
    require(len(transaction_paths) == 1, "repair_checkpoint_missing")
    opened = transaction.ProjectUpdateTransaction.open(project, transaction_paths[0].name)
    journal = opened.inspect().journal
    require(journal.state == "exact" and journal.verified_prefix[-1].phase == "runtime"
            and journal.verified_prefix[-1].stage == "intent"
            and any(item.phase == "approval_bound" for item in journal.verified_prefix)
            and (transaction_paths[0] / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME).is_dir(), "repair_checkpoint_missing")
    claims_root = project / "archive/profiles/local/exact-human-approvals/claims"
    interrupted_claims = {path: path.read_bytes() for path in claims_root.glob("approval_*.json")}
    require(len(interrupted_claims) == 2, "repair_claim_missing")
    phases.passed()
    phases.begin("repair_fresh_resume")
    started = time.monotonic()
    resumed = json.loads(command([*worker, "resume"], cwd=root, timeout=600,
                                 runtime_failure_stage="repair_fresh_resume"))
    resume_seconds = time.monotonic() - started
    require(resumed == {"ok": True, "schema": SCHEMA, "worker": "resume", "same_approval_resumed": True,
                        "no_new_preparation_download_or_approval": True, "private_values_echoed": False}, "repair_resume_failed")
    phases.passed()
    phases.begin("repair_result_validation")
    require(package_file.read_bytes() == healthy_bytes
            and all(path.read_bytes() == content for path, content in stable.items())
            and len({path.name for path in receipt_root.glob("*.json")} - receipt_names) == 1
            and set(claims_root.glob("approval_*.json")) == set(interrupted_claims), "repair_payload_not_restored")
    phases.passed()
    phases.begin("repair_independent_noop")
    # Independently re-run the entire retained-artifact, static executable,
    # package-resource and new-process proof after the real writer completed.
    started = time.monotonic()
    with CallObservation({"prepare": (project_runtime, "prepare_runtime_candidate"),
                          "initialize": (project_runtime, "_initialize_runtime_payload")}) as observer, mock.patch.object(
        native_type, "show", side_effect=JourneyCheckError("repair_resume_requested_effect"),
    ) as native, mock.patch.object(project_runtime, "_download_exact_artifact",
                                  side_effect=JourneyCheckError("repair_resume_requested_effect")) as download:
        code, verified = cli(approved_arguments(project, version))
    require(code == 0 and verified.get("status") == "no_change"
            and verified.get("project_runtime", {}).get("preparation_revalidation", {}).get("state") == "passed",
            "repair_payload_not_restored")
    require(native.call_count == download.call_count == observer.calls["prepare"] == observer.calls["initialize"] == 0,
            "repair_resume_requested_effect")
    assert_no_active_update(project, project_runtime, transaction)
    phases.passed()
    return {"repair_until_interruption": round(interruption_seconds, 3), "repair_fresh_resume": round(resume_seconds, 3),
            "repair_independent_noop": round(time.monotonic() - started, 3)}


def initial_update_diagnostic(version, wheel_hash, import_seconds, update_seconds):
    return {"ok": True, "schema": INITIAL_DIAGNOSTIC_SCHEMA,
            "scope": "synthetic_harness_only", "full_journey_complete": False,
            "candidate_wheel_not_public_release_proof": True,
            "package_version": version, "wheel_sha256": wheel_hash,
            "initial_update_completed": True, "private_values_echoed": False,
            "seconds": {"bootstrap_import": round(import_seconds, 3), "update": round(update_seconds, 3)}}


def run_journey(wheel: Path, source: Path, shim: Path, root: Path, expected_version: str, *,
                phases=None, initial_update_only=False) -> dict[str, object]:
    phases = PhaseReporter() if phases is None else phases
    phases.begin("bootstrap_import")
    require(os.name == "nt" and sys.version_info[:2] == (3, 12), "windows_cpython312_required")
    require(not root.exists(), "synthetic_fixture_must_be_new")
    root.mkdir()
    if initial_update_only:
        phases.initial_diagnostic_root = (root, _initial_failure_root_identity(root))
    started = time.monotonic()
    from wom_kit import archive_cli, archive_services, project_runtime
    from wom_kit import exact_human_approval_windows, exact_human_approval_workflow
    import wom_kit
    import_seconds = time.monotonic() - started
    modules = {"wom_kit": wom_kit, "archive_cli": archive_cli, "project_runtime": project_runtime}
    verify_installed_origins(modules, Path(sys.prefix))
    require(wom_kit.__version__ == expected_version, "bootstrap_version_mismatch")
    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    direct = json.loads(importlib.metadata.distribution("wom-kit").read_text("direct_url.json") or "{}")
    require(direct.get("archive_info", {}).get("hashes", {}).get("sha256") == wheel_hash, "bootstrap_wheel_hash_mismatch")
    phases.passed()
    phases.begin("synthetic_project")
    fixture = create_project(root, source, shim, expected_version)
    project = fixture["project"]
    metadata = fixture["metadata"]
    require(isinstance(project, Path) and isinstance(metadata, Path), "fixture_invalid")
    bootstrap = project_runtime.BootstrapWheel(
        version=expected_version, tag="v" + expected_version,
        url="https://example.invalid/candidate/" + wheel.name,
        sha256=wheel_hash, file_name=wheel.name,
    )
    transport = local_transport(project_runtime, wheel, bootstrap)
    cli = lambda argv: cli_json(archive_cli, argv)
    approved = approved_arguments(project, expected_version)
    phases.passed()
    phases.begin("initial_update")
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(project_runtime, "bootstrap_wheel_for_target",
                           return_value=(bootstrap, bootstrap.public_summary())))
        stack.enter_context(mock.patch.object(exact_human_approval_workflow, "_production_key_provider",
                           return_value=_MemoryOnlyApprovalKey()))
        update_start = time.monotonic()
        with mock.patch.object(project_runtime, "_download_exact_artifact", side_effect=transport), mock.patch.object(
            exact_human_approval_windows._CtypesTaskDialogNative, "show",
            return_value=(exact_human_approval_windows.APPROVE_BUTTON_ID, False),
        ) as native:
            code, first = observed_initial_update(archive_cli, project_runtime, cli, approved, native)
        require(native.call_count == 1, "public_native_broker_not_once")
        require(first.get("terminal_finalization", {}).get("transaction_cleanup_completed") is True, "update_cleanup_incomplete")
        update_seconds = time.monotonic() - update_start
        phases.passed()
        if initial_update_only:
            return initial_update_diagnostic(expected_version, wheel_hash, import_seconds, update_seconds)
        phases.begin("healthy_noop")
        runtime = project_runtime.runtime_path(project, expected_version)
        before = project_runtime._candidate_inventory_snapshot(runtime)
        receipt_root = metadata / "receipts" / "version-updates"
        unchanged = {path: path.read_bytes() for path in [
            metadata / "installed-version.txt", project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE,
            *receipt_root.glob("*.json"),
        ]}
        receipt_names = {path.name for path in receipt_root.glob("*.json")}
        noop_start = time.monotonic()
        with ExitStack() as forbidden:
            for name in ("_download_exact_artifact", "prepare_runtime_candidate", "_initialize_runtime_payload"):
                forbidden.enter_context(mock.patch.object(project_runtime, name, side_effect=RuntimeError("noop_forbidden_effect")))
            forbidden.enter_context(mock.patch.object(exact_human_approval_windows._CtypesTaskDialogNative, "show",
                                                    side_effect=RuntimeError("noop_forbidden_approval")))
            code, noop = cli(approved)
        require(code == 0 and noop.get("status") == "no_change" and noop.get("files_written") == [], "public_noop_failed")
        require(noop.get("project_runtime", {}).get("preparation_revalidation", {}).get("state") == "passed", "noop_revalidation_missing")
        require(project_runtime._candidate_inventory_snapshot(runtime) == before, "noop_runtime_changed")
        require({path.name for path in receipt_root.glob("*.json")} == receipt_names, "noop_receipt_added")
        require(all(path.read_bytes() == content for path, content in unchanged.items()), "noop_pin_launcher_receipt_changed")
        noop_seconds = time.monotonic() - noop_start
        phases.passed()
        phases.begin("next_preview")
        dry = ["project-version-update", str(project), "--target", "v" + expected_version,
               "--dry-run", "--format", "json"]
        code, after = cli(dry)
        require(code == 0 and after.get("status") != "terminal_cleanup_required", "noop_blocks_next_command")
        phases.passed()
        phases.begin("source_drift")
        drift_seconds = exercise_installed_drift(project, expected_version, project_runtime, archive_services,
                                                exact_human_approval_windows._CtypesTaskDialogNative, cli, phases)
        repair_seconds = exercise_installed_repair(wheel, root, project, expected_version, project_runtime,
                                                  archive_services, cli, exact_human_approval_windows._CtypesTaskDialogNative, phases)

    phases.begin("terminal_control_check")
    transaction = archive_services.project_update_transaction
    assert_no_active_update(project, project_runtime, transaction)
    phases.passed()
    phases.begin("runtime_process_origin")
    runtime_python = runtime / "Scripts" / "python.exe"
    origin_script = (
        "import json,sys;from pathlib import Path;import wom_kit;"
        "from wom_kit import archive_cli,project_runtime;"
        "site=(Path(sys.prefix)/'Lib'/'site-packages').resolve();"
        "print(json.dumps({'version':wom_kit.__version__,'isolated':sys.flags.isolated==1,"
        "'origins':all(Path(m.__file__).resolve().is_relative_to(site) for m in "
        "(wom_kit,archive_cli,project_runtime)),'prefix':Path(sys.prefix).resolve()==Path(sys.argv[1]).resolve()}))"
    )
    fresh_start = time.monotonic()
    fresh = json.loads(command([str(runtime_python), "-I", "-B", "-c", origin_script, str(runtime)], cwd=root))
    fresh_seconds = time.monotonic() - fresh_start
    require(fresh == {"version": expected_version, "isolated": True, "origins": True, "prefix": True}, "runtime_origin_or_version_mismatch")
    phases.passed()
    phases.begin("project_launcher_version")
    launcher_start = time.monotonic()
    launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
    launcher_version = command([str(launcher), "--version"], cwd=project)
    launcher_seconds = time.monotonic() - launcher_start
    require(launcher_version == "archive " + expected_version, "project_launcher_version_mismatch")
    phases.passed()
    phases.begin("doctor_startup")
    doctor_archive = root / "startup-doctor-archive"
    shutil.copytree(source / "examples" / "fake-life-archive", doctor_archive)
    startup = measure_doctor_startup([
        str(launcher), "doctor", str(doctor_archive), "--summary", "--format", "json", "--progress",
        "--object-byte-verification", "operational",
    ], cwd=project)
    phases.passed()
    phases.begin("final_claim_check")
    claims = [json.loads(path.read_text(encoding="utf-8")) for path in
              (fixture["archive"] / "profiles/local/exact-human-approvals/claims").glob("approval_*.json")]
    require(len(claims) == 2 and all(claim.get("status") == "succeeded" for claim in claims), "durable_broker_claim_missing")
    phases.passed()
    return {"ok": True, "schema": SCHEMA, "package_version": expected_version,
            "wheel_sha256": wheel_hash, "candidate_wheel_not_public_release_proof": True,
            "isolated_bootstrap_origins": True, "isolated_runtime_origins": True,
            "real_locked_dependencies": True, "real_public_cli_broker_writer": True,
            "update_then_noop_then_preview": True, "no_candidate_download_or_approval_on_noop": True,
            "pin_launcher_domain_receipts_unchanged_on_noop": True,
            "no_active_update_residue": True, "new_process_launcher_version": True,
            "public_launcher_doctor_startup_verified": True,
            "real_source_and_ref_drift_blocked_before_approval": True,
            "real_candidate_repair_and_process_loss_resume": True,
            "pre_switch_damaged_preimage_and_active_pin_preserved": True,
            "same_approval_identifier_free_resume_without_rebuild": True,
            "repaired_runtime_independently_reverified": True,
            "doctor_startup_status_event_count": startup["status_event_count"],
            "private_values_echoed": False,
            "seconds": {**drift_seconds, **repair_seconds,
                        "bootstrap_import": round(import_seconds, 3), "update": round(update_seconds, 3),
                        "noop": round(noop_seconds, 3), "fresh_runtime_import": round(fresh_seconds, 3),
                        "project_launcher_version": round(launcher_seconds, 3),
                        "doctor_first_status": startup["first_status_seconds"],
                        "doctor_maximum_progress_gap": startup["maximum_gap_seconds"],
                        "doctor_terminal": startup["terminal_seconds"]}}


def main() -> int:
    phases = None
    initial_only = False
    try:
        if len(sys.argv) == 6 and sys.argv[1] == "--repair-worker":
            result = run_repair_worker(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), sys.argv[4], sys.argv[5])
        else:
            phases = PhaseReporter()
            initial_only = len(sys.argv) == 7 and sys.argv[1] == "--initial-update-only"
            arguments = sys.argv[2:] if initial_only else sys.argv[1:]
            require(len(arguments) == 5, "journey_arguments_invalid")
            options = {"phases": phases}
            if initial_only:
                options["initial_update_only"] = True
            result = run_journey(*(Path(value).resolve() for value in arguments[:4]), arguments[4], **options)
    except Exception as error:
        if phases is not None:
            try:
                phases.fail_active()
            except Exception:
                pass  # Broken diagnostic pipe must not replace the original failure.
        # Never print captured CLI output, private paths, transport values, or
        # traceback into the public wheel evidence. Known reasons are opaque.
        reason = str(error) if isinstance(error, JourneyCheckError) else "installed_runtime_journey_failed"
        result = {"ok": False, "schema": SCHEMA,
                  "reason_code": reason if reason in SAFE_REASON_CODES else "installed_runtime_journey_failed"}
        if type(error) is InitialUpdateCheckError:
            try:
                result["failure_observation"] = validate_first_update_observation(error.observation)
            except Exception:
                pass  # Corrupt diagnostics cannot leak or change failure into success.
        if initial_only and phases is not None and hasattr(phases, "initial_diagnostic_root"):
            try:
                root, identity = phases.initial_diagnostic_root
                write_initial_failure_observation(root, identity, result)
            except Exception:
                pass  # Preserve the original failed result if diagnostic storage fails.
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
