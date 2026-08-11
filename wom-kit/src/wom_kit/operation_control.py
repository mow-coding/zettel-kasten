"""Bounded, content-free CLI operation journals and read-only control views.

The journal is deliberately observational.  It is not a queue, daemon, lock,
receipt, or substitute for command-specific authority checks.  v0.3 keeps
cancel and resume unsupported until transaction-aware control points exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import threading
import time
from typing import Any, Callable


OPERATION_JOURNAL_SCHEMA = "wom-kit/operation-journal/v0.1"
OPERATION_CONTROL_SCHEMA = "wom-kit/operation-control/v0.1"
OPERATION_REF_RE = re.compile(r"op:sha256:([0-9a-f]{64})")
RUN_ID_RE = re.compile(r"[0-9a-f]{32}")
SAFE_REVIEWER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}")
CONTROL_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")

MAX_JOURNAL_BYTES = 1024 * 1024
MAX_JOURNAL_RECORDS = 4096
MAX_JOURNAL_LINE_BYTES = 16 * 1024
MAX_RESULT_BYTES = 64 * 1024 * 1024
MAX_RESULT_SCAN_ENTRIES = 4096
MAX_RESULT_SCAN_BYTES = 256 * 1024 * 1024
HEARTBEAT_INTERVAL_SECONDS = 10.0
HEARTBEAT_STALE_SECONDS = 35.0
MAX_FUTURE_SKEW_SECONDS = 5.0
MAX_WAIT_SECONDS = 60

ARCHIVE_OUTPUT_PREFIX = ".wom-scratch/diagnostics/"
PROJECT_OUTPUT_PREFIX = ".zettel-kasten/diagnostics/"
ARCHIVE_JOURNAL_RELATIVE = PurePosixPath(
    ".wom-scratch/diagnostics/.operations"
)
PROJECT_JOURNAL_RELATIVE = PurePosixPath(".zettel-kasten/operations")

COMMAND_KINDS = {
    "project-version-update": "project_version_update",
    "index": "archive_index",
    "index-health": "archive_index_health",
}
KIND_COMMANDS = {value: key for key, value in COMMAND_KINDS.items()}
COMMAND_STAGES = {
    "project-version-update": frozenset(
        {
            "starting",
            "project-preflight",
            "fetch-release",
            "verify-release",
            "checkout-release",
            "write-pins",
            "write-receipt",
            "unknown",
        }
    ),
    "index": frozenset(
        {
            "starting",
            "index-lock-and-schema",
            "index-zettels",
            "index-objects",
            "index-derived-texts",
            "index-views",
            "index-source-maps",
            "index-commit",
            "unknown",
        }
    ),
    "index-health": frozenset(
        {
            "starting",
            "index-health-live-zettels",
            "index-health-index-rows",
            "index-health-compare",
            "unknown",
        }
    ),
}
JOURNAL_EVENTS = frozenset(
    {"started", "checkpoint", "heartbeat", "completed", "result_unavailable"}
)
RECORD_KEYS = (
    "schema",
    "operation_ref",
    "operation_kind",
    "root_ref",
    "output_ref",
    "run_id",
    "owner_ref",
    "control_digest",
    "sequence",
    "event",
    "stage",
    "observed_at",
    "elapsed_ms",
    "last_completed_stage",
    "terminal",
    "result_available",
    "result_ok",
    "exit_code",
    "result_sha256",
    "result_bytes",
    "recovery_required",
    "previous_record_sha256",
    "record_sha256",
)


class OperationControlError(RuntimeError):
    """Closed operation-control failure without a raw local error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _is_reparse(observed: os.stat_result) -> bool:
    return bool(
        getattr(observed, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _require_real_directory(path: Path) -> os.stat_result:
    try:
        observed = os.lstat(path)
    except OSError:
        raise OperationControlError("operation_control_root_unavailable") from None
    if (
        stat.S_ISLNK(observed.st_mode)
        or _is_reparse(observed)
        or not stat.S_ISDIR(observed.st_mode)
    ):
        raise OperationControlError("operation_control_root_unsafe")
    return observed


def require_control_root(root: Path | str) -> Path:
    absolute = Path(os.path.abspath(str(Path(root))))
    _require_real_directory(absolute)
    try:
        resolved = absolute.resolve(strict=True)
        if not os.path.samefile(absolute, resolved):
            raise OperationControlError("operation_control_root_unsafe")
    except OperationControlError:
        raise
    except OSError:
        raise OperationControlError("operation_control_root_unavailable") from None
    return absolute


def _root_ref(root: Path) -> str:
    """Return an opaque binding to this exact, currently observed root."""

    observed = _require_real_directory(root)
    try:
        resolved = root.resolve(strict=True)
    except OSError:
        raise OperationControlError("operation_control_root_unavailable") from None
    framed = (
        "wom-kit-operation-root-v0.1\0"
        + os.path.normcase(str(resolved))
        + "\0"
        + str(int(observed.st_dev))
        + "\0"
        + str(int(observed.st_ino))
    ).encode("utf-8")
    return "root:sha256:" + hashlib.sha256(framed).hexdigest()


def _path_below(root: Path, relative: PurePosixPath) -> Path:
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise OperationControlError("operation_control_path_unsafe")
    candidate = root.joinpath(*relative.parts)
    try:
        if os.path.commonpath((str(root), str(candidate))) != str(root):
            raise OperationControlError("operation_control_path_unsafe")
    except ValueError:
        raise OperationControlError("operation_control_path_unsafe") from None
    return candidate


def _ensure_real_directory_chain(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        try:
            os.mkdir(current)
        except FileExistsError:
            pass
        except OSError:
            raise OperationControlError(
                "operation_journal_directory_unavailable"
            ) from None
        _require_real_directory(current)
    return current


def _validate_existing_chain(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise OperationControlError("operation_control_path_unsafe") from None
    current = root
    _require_real_directory(current)
    for part in relative.parts[:-1]:
        current = current / part
        _require_real_directory(current)


def _journal_relative_for_output(output_relative: str) -> PurePosixPath:
    normalized = output_relative.replace("\\", "/").strip()
    if normalized.startswith(ARCHIVE_OUTPUT_PREFIX):
        return ARCHIVE_JOURNAL_RELATIVE
    if normalized.startswith(PROJECT_OUTPUT_PREFIX):
        return PROJECT_JOURNAL_RELATIVE
    raise OperationControlError("operation_output_scope_invalid")


def _canonical_record_bytes(record: dict[str, Any]) -> bytes:
    payload = dict(record)
    payload.pop("record_sha256", None)
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _record_digest(record: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_record_bytes(record)).hexdigest()


def _operation_ref(
    command: str,
    run_id: str,
    output_ref: str,
    root_ref: str,
) -> str:
    framed = (
        "wom-kit-operation-ref-v0.1\0"
        + command
        + "\0"
        + run_id
        + "\0"
        + output_ref
        + "\0"
        + root_ref
    ).encode("utf-8")
    return "op:sha256:" + hashlib.sha256(framed).hexdigest()


def _output_ref(output_relative: str) -> str:
    normalized = output_relative.replace("\\", "/").strip()
    return "output:sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _opaque_digest(prefix: str, operation_ref: str, run_id: str) -> str:
    framed = f"{prefix}\0{operation_ref}\0{run_id}".encode("ascii")
    return f"{prefix}:sha256:" + hashlib.sha256(framed).hexdigest()


def _operation_hex(operation_ref: str) -> str:
    match = OPERATION_REF_RE.fullmatch(str(operation_ref or ""))
    if match is None:
        raise OperationControlError("operation_ref_invalid")
    return match.group(1)


def _require_result_path(root: Path, path: Path) -> os.stat_result:
    absolute = Path(os.path.abspath(str(path)))
    _validate_existing_chain(root, absolute)
    try:
        relative = absolute.relative_to(root).as_posix()
    except ValueError:
        raise OperationControlError("operation_result_path_unsafe") from None
    if not (
        relative.startswith(ARCHIVE_OUTPUT_PREFIX)
        or relative.startswith(PROJECT_OUTPUT_PREFIX)
    ) or "/.operations/" in f"/{relative}":
        raise OperationControlError("operation_result_path_unsafe")
    try:
        observed = os.lstat(absolute)
    except OSError:
        raise OperationControlError("operation_result_unavailable") from None
    if (
        stat.S_ISLNK(observed.st_mode)
        or _is_reparse(observed)
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or not 0 < observed.st_size <= MAX_RESULT_BYTES
    ):
        raise OperationControlError("operation_result_unavailable")
    return observed


def _hash_result_artifact(
    root: Path,
    path: Path,
) -> tuple[str, int, dict[str, Any]]:
    observed = _require_result_path(root, path)
    digest = hashlib.sha256()
    total = 0
    chunks: list[bytes] = []
    try:
        descriptor = os.open(
            str(path), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        try:
            current = os.fstat(descriptor)
            if (
                not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or (int(current.st_dev), int(current.st_ino))
                != (int(observed.st_dev), int(observed.st_ino))
                or current.st_size != observed.st_size
            ):
                raise OSError("operation_result_identity_changed")
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESULT_BYTES:
                    raise OSError("operation_result_too_large")
                digest.update(chunk)
                chunks.append(chunk)
            final = os.fstat(descriptor)
            if (
                (int(final.st_dev), int(final.st_ino))
                != (int(observed.st_dev), int(observed.st_ino))
                or final.st_size != observed.st_size
                or total != observed.st_size
            ):
                raise OSError("operation_result_identity_changed")
        finally:
            os.close(descriptor)
    except OSError:
        raise OperationControlError("operation_result_unavailable") from None
    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise OperationControlError("operation_result_invalid") from None
    if not isinstance(payload, dict):
        raise OperationControlError("operation_result_invalid")
    return "sha256:" + digest.hexdigest(), total, payload


def _validated_result_payload(
    payload: dict[str, Any],
    *,
    operation_ref: str,
    run_id: str,
    root_ref: str,
    output_ref: str,
    command: str,
) -> tuple[int, bool] | None:
    execution = payload.get("cli_execution")
    artifact = payload.get("cli_output_artifact")
    operation = artifact.get("operation") if isinstance(artifact, dict) else None
    exit_code = execution.get("exit_code") if isinstance(execution, dict) else None
    result_ok = payload.get("ok")
    if (
        not isinstance(execution, dict)
        or not isinstance(artifact, dict)
        or not isinstance(operation, dict)
        or execution.get("status") != "completed"
        or execution.get("run_id") != run_id
        or execution.get("command") != command
        or artifact.get("command") != command
        or operation.get("operation_ref") != operation_ref
        or operation.get("root_ref") != root_ref
        or operation.get("output_ref") != output_ref
        or operation.get("operation_kind") != COMMAND_KINDS[command]
        or not isinstance(exit_code, int)
        or isinstance(exit_code, bool)
        or not 0 <= exit_code <= 255
        or type(result_ok) is not bool
        or ((exit_code == 0) is not result_ok)
    ):
        return None
    return exit_code, result_ok


def _find_result_artifact(
    root: Path,
    *,
    operation_ref: str,
    run_id: str,
    root_ref: str,
    output_ref: str,
    command: str,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
    expected_exit_code: int | None = None,
    expected_result_ok: bool | None = None,
) -> dict[str, Any] | None:
    scanned_entries = 0
    scanned_bytes = 0
    matches: list[dict[str, Any]] = []
    search_roots = (
        _path_below(root, PurePosixPath(ARCHIVE_OUTPUT_PREFIX.rstrip("/"))),
        _path_below(root, PurePosixPath(PROJECT_OUTPUT_PREFIX.rstrip("/"))),
    )
    for search_root in search_roots:
        try:
            observed_root = os.lstat(search_root)
        except FileNotFoundError:
            continue
        except OSError:
            raise OperationControlError(
                "operation_result_verification_unavailable"
            ) from None
        _validate_existing_chain(root, search_root)
        if (
            stat.S_ISLNK(observed_root.st_mode)
            or _is_reparse(observed_root)
            or not stat.S_ISDIR(observed_root.st_mode)
        ):
            raise OperationControlError("operation_result_verification_unsafe")
        stack = [search_root]
        while stack:
            directory = stack.pop()
            try:
                entries = os.scandir(directory)
            except OSError:
                raise OperationControlError(
                    "operation_result_verification_unavailable"
                ) from None
            with entries:
                for entry in entries:
                    scanned_entries += 1
                    if scanned_entries > MAX_RESULT_SCAN_ENTRIES:
                        raise OperationControlError(
                            "operation_result_verification_bounded"
                        )
                    try:
                        observed = entry.stat(follow_symlinks=False)
                    except OSError:
                        raise OperationControlError(
                            "operation_result_verification_unavailable"
                        ) from None
                    if stat.S_ISLNK(observed.st_mode) or _is_reparse(observed):
                        raise OperationControlError(
                            "operation_result_verification_unsafe"
                        )
                    candidate = Path(entry.path)
                    if stat.S_ISDIR(observed.st_mode):
                        if entry.name != ".operations":
                            stack.append(candidate)
                        continue
                    try:
                        candidate_relative = candidate.relative_to(root).as_posix()
                    except ValueError:
                        raise OperationControlError(
                            "operation_result_verification_unsafe"
                        ) from None
                    if (
                        not stat.S_ISREG(observed.st_mode)
                        or not entry.name.lower().endswith(".json")
                        or _output_ref(candidate_relative) != output_ref
                        or (
                            expected_bytes is not None
                            and observed.st_size != expected_bytes
                        )
                        or not 0 < observed.st_size <= MAX_RESULT_BYTES
                    ):
                        continue
                    scanned_bytes += int(observed.st_size)
                    if scanned_bytes > MAX_RESULT_SCAN_BYTES:
                        raise OperationControlError(
                            "operation_result_verification_bounded"
                        )
                    try:
                        digest, size, payload = _hash_result_artifact(root, candidate)
                    except OperationControlError as exc:
                        if exc.code in {
                            "operation_result_invalid",
                            "operation_result_unavailable",
                        }:
                            continue
                        raise
                    if expected_sha256 is not None and digest != expected_sha256:
                        continue
                    if expected_bytes is not None and size != expected_bytes:
                        continue
                    validated = _validated_result_payload(
                        payload,
                        operation_ref=operation_ref,
                        run_id=run_id,
                        root_ref=root_ref,
                        output_ref=output_ref,
                        command=command,
                    )
                    if validated is None:
                        continue
                    exit_code, result_ok = validated
                    if (
                        expected_exit_code is not None
                        and exit_code != expected_exit_code
                    ) or (
                        expected_result_ok is not None
                        and result_ok is not expected_result_ok
                    ):
                        continue
                    matches.append(
                        {
                            "sha256": digest,
                            "bytes": size,
                            "exit_code": exit_code,
                            "result_ok": result_ok,
                        }
                    )
                    if len(matches) > 1:
                        raise OperationControlError(
                            "operation_result_artifact_ambiguous"
                        )
    return matches[0] if matches else None


@dataclass
class OperationRunJournal:
    control_root: Path
    journal_path: Path
    command: str
    operation_kind: str
    operation_ref: str
    root_ref: str
    output_ref: str
    run_id: str
    owner_ref: str
    control_digest: str
    started_monotonic: float
    _identity: tuple[int, int]
    _sequence: int = 0
    _previous_digest: str | None = None
    _stage: str = "starting"
    _last_completed_stage: str | None = None
    _failed: bool = False
    _terminal: bool = False

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def prepare(
        cls,
        control_root: Path | str,
        *,
        output_relative: str,
        command: str,
        run_id: str,
    ) -> "OperationRunJournal":
        root = require_control_root(control_root)
        if command not in COMMAND_KINDS or RUN_ID_RE.fullmatch(run_id) is None:
            raise OperationControlError("operation_journal_input_invalid")
        journal_relative = _journal_relative_for_output(output_relative)
        journal_root = _ensure_real_directory_chain(root, journal_relative)
        root_ref = _root_ref(root)
        output_ref = _output_ref(output_relative)
        operation_ref = _operation_ref(
            command,
            run_id,
            output_ref,
            root_ref,
        )
        operation_hex = _operation_hex(operation_ref)
        journal_path = journal_root / f"{operation_hex}.jsonl"
        owner_ref = _opaque_digest("owner", operation_ref, run_id)
        control_digest = _opaque_digest("control", operation_ref, run_id).replace(
            "control:sha256:", "sha256:"
        )
        try:
            descriptor = os.open(
                str(journal_path),
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_BINARY", 0),
                0o600,
            )
        except FileExistsError:
            raise OperationControlError("operation_journal_already_exists") from None
        except OSError:
            raise OperationControlError("operation_journal_create_failed") from None
        try:
            observed = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise OperationControlError("operation_journal_create_failed")
        journal = cls(
            control_root=root,
            journal_path=journal_path,
            command=command,
            operation_kind=COMMAND_KINDS[command],
            operation_ref=operation_ref,
            root_ref=root_ref,
            output_ref=output_ref,
            run_id=run_id,
            owner_ref=owner_ref,
            control_digest=control_digest,
            started_monotonic=time.monotonic(),
            _identity=(int(observed.st_dev), int(observed.st_ino)),
        )
        journal._append("started", terminal=False)
        if journal._failed:
            raise OperationControlError("operation_journal_start_failed")
        journal._thread = threading.Thread(
            target=journal._heartbeat_loop,
            name=f"wom-operation-{command}",
            daemon=True,
        )
        journal._thread.start()
        return journal

    @property
    def tracking_ok(self) -> bool:
        return not self._failed

    def metadata(self) -> dict[str, Any]:
        return {
            "operation_ref": self.operation_ref,
            "operation_kind": self.operation_kind,
            "root_ref": self.root_ref,
            "output_ref": self.output_ref,
            "control_digest": self.control_digest,
            "status_command": (
                "archive operation-control <project-or-archive-root> "
                f"--operation-ref {self.operation_ref} --action status "
                "--dry-run --format json"
            ),
            "wait_command": (
                "archive operation-control <project-or-archive-root> "
                f"--operation-ref {self.operation_ref} --action wait "
                "--timeout-seconds 60 --dry-run --format json"
            ),
            "cancel_supported": False,
            "resume_supported": False,
        }

    def _safe_stage(self, stage: object) -> str:
        value = str(stage or "").strip().lower()
        return value if value in COMMAND_STAGES[self.command] else "unknown"

    def _record(
        self,
        event: str,
        *,
        terminal: bool,
        result_available: bool = False,
        result_ok: bool | None = None,
        exit_code: int | None = None,
        result_sha256: str | None = None,
        result_bytes: int | None = None,
        recovery_required: bool = False,
    ) -> dict[str, Any]:
        record = {
            "schema": OPERATION_JOURNAL_SCHEMA,
            "operation_ref": self.operation_ref,
            "operation_kind": self.operation_kind,
            "root_ref": self.root_ref,
            "output_ref": self.output_ref,
            "run_id": self.run_id,
            "owner_ref": self.owner_ref,
            "control_digest": self.control_digest,
            "sequence": self._sequence,
            "event": event,
            "stage": self._stage,
            "observed_at": _utc_now(),
            "elapsed_ms": max(
                0, int((time.monotonic() - self.started_monotonic) * 1000)
            ),
            "last_completed_stage": self._last_completed_stage,
            "terminal": terminal,
            "result_available": result_available,
            "result_ok": result_ok,
            "exit_code": exit_code,
            "result_sha256": result_sha256,
            "result_bytes": result_bytes,
            "recovery_required": recovery_required,
            "previous_record_sha256": self._previous_digest,
            "record_sha256": None,
        }
        record["record_sha256"] = _record_digest(record)
        return record

    def _append(
        self,
        event: str,
        *,
        terminal: bool,
        result_available: bool = False,
        result_ok: bool | None = None,
        exit_code: int | None = None,
        result_sha256: str | None = None,
        result_bytes: int | None = None,
        recovery_required: bool = False,
    ) -> None:
        if self._failed or self._terminal or event not in JOURNAL_EVENTS:
            return
        record = self._record(
            event,
            terminal=terminal,
            result_available=result_available,
            result_ok=result_ok,
            exit_code=exit_code,
            result_sha256=result_sha256,
            result_bytes=result_bytes,
            recovery_required=recovery_required,
        )
        encoded = (
            json.dumps(
                record,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
        if len(encoded) > MAX_JOURNAL_LINE_BYTES:
            self._failed = True
            return
        try:
            _validate_existing_chain(self.control_root, self.journal_path)
            before = os.lstat(self.journal_path)
            if (
                stat.S_ISLNK(before.st_mode)
                or _is_reparse(before)
                or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or (int(before.st_dev), int(before.st_ino)) != self._identity
                or before.st_size + len(encoded) > MAX_JOURNAL_BYTES
            ):
                raise OSError("operation_journal_identity_changed")
            descriptor = os.open(
                str(self.journal_path),
                os.O_WRONLY | os.O_APPEND | getattr(os, "O_BINARY", 0),
            )
            try:
                current = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(current.st_mode)
                    or current.st_nlink != 1
                    or (int(current.st_dev), int(current.st_ino))
                    != self._identity
                ):
                    raise OSError("operation_journal_identity_changed")
                written = os.write(descriptor, encoded)
                if written != len(encoded):
                    raise OSError("operation_journal_append_incomplete")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except (OSError, OperationControlError):
            self._failed = True
            return
        self._previous_digest = str(record["record_sha256"])
        self._sequence += 1
        self._terminal = terminal

    def progress(
        self,
        stage: str,
        message: str,
        _current: int | None,
        _total: int | None,
    ) -> None:
        safe_stage = self._safe_stage(stage)
        normalized_message = str(message or "").strip().lower()
        checkpoint = normalized_message == "start" or normalized_message.startswith(
            "start "
        )
        completed = normalized_message == "done" or normalized_message.startswith(
            "done "
        )
        with self._lock:
            stage_changed = safe_stage != self._stage
            self._stage = safe_stage
            if completed and safe_stage != "unknown":
                self._last_completed_stage = safe_stage
            if stage_changed or checkpoint or completed:
                self._append("checkpoint", terminal=False)

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            with self._lock:
                self._append("heartbeat", terminal=False)

    def complete(
        self,
        *,
        exit_code: int,
        result_available: bool,
        result_ok: bool | None,
        result_path: Path | None = None,
    ) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        result_sha256: str | None = None
        result_bytes: int | None = None
        if result_available:
            try:
                if result_path is None:
                    raise OperationControlError("operation_result_unavailable")
                result_sha256, result_bytes, payload = _hash_result_artifact(
                    self.control_root,
                    result_path,
                )
                validated = _validated_result_payload(
                    payload,
                    operation_ref=self.operation_ref,
                    run_id=self.run_id,
                    root_ref=self.root_ref,
                    output_ref=self.output_ref,
                    command=self.command,
                )
                if validated != (int(exit_code), result_ok):
                    raise OperationControlError("operation_result_binding_invalid")
            except OperationControlError:
                result_available = False
                result_ok = None
        if not self._lock.acquire(timeout=2.0):
            self._failed = True
            return False
        try:
            self._append(
                "completed" if result_available else "result_unavailable",
                terminal=True,
                result_available=result_available,
                result_ok=result_ok if result_available else None,
                exit_code=int(exit_code) if result_available else None,
                result_sha256=result_sha256 if result_available else None,
                result_bytes=result_bytes if result_available else None,
                recovery_required=not result_available,
            )
        finally:
            self._lock.release()
        return not self._failed and self._terminal

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OperationControlError("operation_journal_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise OperationControlError("operation_journal_invalid") from None
    if parsed.tzinfo is None:
        raise OperationControlError("operation_journal_invalid")
    return parsed.astimezone(timezone.utc)


def _read_journal(path: Path, root: Path) -> list[dict[str, Any]]:
    _validate_existing_chain(root, path)
    try:
        observed = os.lstat(path)
    except OSError:
        raise OperationControlError("operation_journal_unavailable") from None
    if (
        stat.S_ISLNK(observed.st_mode)
        or _is_reparse(observed)
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or not 0 < observed.st_size <= MAX_JOURNAL_BYTES
    ):
        raise OperationControlError("operation_journal_invalid")
    chunks: list[bytes] = []
    total = 0
    try:
        descriptor = os.open(
            str(path), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        try:
            current = os.fstat(descriptor)
            identity = (int(observed.st_dev), int(observed.st_ino))
            if (
                not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or (int(current.st_dev), int(current.st_ino)) != identity
                or not observed.st_size <= current.st_size <= MAX_JOURNAL_BYTES
            ):
                raise OSError("operation_journal_identity_changed")
            # Read the complete prefix observed by the initial lstat.  A
            # concurrent append may make the open file larger, but must not
            # invalidate the already fsynced newline-delimited prefix.
            remaining = int(observed.st_size)
            while remaining:
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                if not chunk:
                    raise OSError("operation_journal_read_incomplete")
                total += len(chunk)
                remaining -= len(chunk)
                if total > MAX_JOURNAL_BYTES:
                    raise OSError("operation_journal_too_large")
                chunks.append(chunk)
            final = os.fstat(descriptor)
            if (
                (int(final.st_dev), int(final.st_ino)) != identity
                or not observed.st_size <= final.st_size <= MAX_JOURNAL_BYTES
                or total != observed.st_size
            ):
                raise OSError("operation_journal_identity_changed")
        finally:
            os.close(descriptor)
    except OSError:
        raise OperationControlError("operation_journal_unavailable") from None
    raw = b"".join(chunks)
    if not raw.endswith(b"\n"):
        raise OperationControlError("operation_journal_torn")
    lines = raw.splitlines()
    if not 0 < len(lines) <= MAX_JOURNAL_RECORDS:
        raise OperationControlError("operation_journal_invalid")
    records: list[dict[str, Any]] = []
    previous_digest: str | None = None
    fixed: tuple[str, str, str, str, str, str, str] | None = None
    terminal_seen = False
    previous_elapsed = -1
    previous_timestamp: datetime | None = None
    for sequence, line in enumerate(lines):
        if not line or len(line) > MAX_JOURNAL_LINE_BYTES:
            raise OperationControlError("operation_journal_invalid")
        try:
            decoded = line.decode("ascii")
            record = json.loads(decoded)
        except (UnicodeError, json.JSONDecodeError):
            raise OperationControlError("operation_journal_invalid") from None
        if not isinstance(record, dict) or tuple(record) != tuple(
            sorted(RECORD_KEYS)
        ):
            # Writers sort keys on disk; requiring that order also rejects an
            # unexpected field before any untrusted value is reflected.
            raise OperationControlError("operation_journal_invalid")
        if set(record) != set(RECORD_KEYS):
            raise OperationControlError("operation_journal_invalid")
        operation_ref = record.get("operation_ref")
        operation_kind = record.get("operation_kind")
        root_ref = record.get("root_ref")
        output_ref = record.get("output_ref")
        run_id = record.get("run_id")
        owner_ref = record.get("owner_ref")
        control_digest = record.get("control_digest")
        current_fixed = (
            str(operation_ref),
            str(operation_kind),
            str(root_ref),
            str(output_ref),
            str(run_id),
            str(owner_ref),
            str(control_digest),
        )
        if fixed is None:
            fixed = current_fixed
        if (
            current_fixed != fixed
            or record.get("schema") != OPERATION_JOURNAL_SCHEMA
            or OPERATION_REF_RE.fullmatch(str(operation_ref or "")) is None
            or operation_kind not in KIND_COMMANDS
            or not re.fullmatch(r"root:sha256:[0-9a-f]{64}", str(root_ref or ""))
            or not re.fullmatch(
                r"output:sha256:[0-9a-f]{64}", str(output_ref or "")
            )
            or operation_ref
            != _operation_ref(
                KIND_COMMANDS[str(operation_kind)],
                str(run_id),
                str(output_ref),
                str(root_ref),
            )
            or RUN_ID_RE.fullmatch(str(run_id or "")) is None
            or not re.fullmatch(r"owner:sha256:[0-9a-f]{64}", str(owner_ref or ""))
            or CONTROL_DIGEST_RE.fullmatch(str(control_digest or "")) is None
            or owner_ref
            != _opaque_digest("owner", str(operation_ref), str(run_id))
            or control_digest
            != _opaque_digest(
                "control", str(operation_ref), str(run_id)
            ).replace("control:sha256:", "sha256:")
            or record.get("sequence") != sequence
            or record.get("event") not in JOURNAL_EVENTS
            or record.get("stage")
            not in COMMAND_STAGES[KIND_COMMANDS[str(operation_kind)]]
            or not isinstance(record.get("elapsed_ms"), int)
            or isinstance(record.get("elapsed_ms"), bool)
            or record["elapsed_ms"] < 0
            or record.get("last_completed_stage")
            not in {None, *COMMAND_STAGES[KIND_COMMANDS[str(operation_kind)]]}
            or type(record.get("terminal")) is not bool
            or type(record.get("result_available")) is not bool
            or (
                record.get("result_ok") is not None
                and type(record.get("result_ok")) is not bool
            )
            or (
                record.get("exit_code") is not None
                and (
                    not isinstance(record.get("exit_code"), int)
                    or isinstance(record.get("exit_code"), bool)
                    or not 0 <= record["exit_code"] <= 255
                )
            )
            or (
                record.get("result_sha256") is not None
                and not re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(record.get("result_sha256")),
                )
            )
            or (
                record.get("result_bytes") is not None
                and (
                    not isinstance(record.get("result_bytes"), int)
                    or isinstance(record.get("result_bytes"), bool)
                    or not 0 < record["result_bytes"] <= MAX_RESULT_BYTES
                )
            )
            or type(record.get("recovery_required")) is not bool
            or record.get("previous_record_sha256") != previous_digest
            or record.get("record_sha256") != _record_digest(record)
        ):
            raise OperationControlError("operation_journal_invalid")
        observed_at = _parse_timestamp(record.get("observed_at"))
        if (
            record["elapsed_ms"] < previous_elapsed
            or (previous_timestamp is not None and observed_at < previous_timestamp)
        ):
            raise OperationControlError("operation_journal_invalid")
        previous_elapsed = record["elapsed_ms"]
        previous_timestamp = observed_at
        if terminal_seen:
            raise OperationControlError("operation_journal_invalid")
        if record["event"] == "started" and sequence != 0:
            raise OperationControlError("operation_journal_invalid")
        if (record["event"] in {"completed", "result_unavailable"}) != bool(
            record["terminal"]
        ):
            raise OperationControlError("operation_journal_invalid")
        if record["terminal"]:
            terminal_seen = True
            if record["event"] not in {"completed", "result_unavailable"}:
                raise OperationControlError("operation_journal_invalid")
        elif (
            record["result_available"]
            or record["result_ok"] is not None
            or record["exit_code"] is not None
            or record["recovery_required"]
            or record["result_sha256"] is not None
            or record["result_bytes"] is not None
        ):
            raise OperationControlError("operation_journal_invalid")
        if record["event"] == "completed" and (
            not record["result_available"]
            or record["result_ok"] is None
            or record["exit_code"] is None
            or record["result_sha256"] is None
            or record["result_bytes"] is None
            or record["recovery_required"]
        ):
            raise OperationControlError("operation_journal_invalid")
        if record["event"] == "result_unavailable" and (
            record["result_available"]
            or record["result_ok"] is not None
            or record["exit_code"] is not None
            or record["result_sha256"] is not None
            or record["result_bytes"] is not None
            or not record["recovery_required"]
        ):
            raise OperationControlError("operation_journal_invalid")
        previous_digest = str(record["record_sha256"])
        records.append(record)
    if records[0]["event"] != "started":
        raise OperationControlError("operation_journal_invalid")
    return records


def _control_base(operation_ref: str, action: str) -> dict[str, Any]:
    safe_operation_ref = (
        operation_ref
        if OPERATION_REF_RE.fullmatch(str(operation_ref or "")) is not None
        else None
    )
    return {
        "schema": OPERATION_CONTROL_SCHEMA,
        "ok": False,
        "dry_run": action != "cancel",
        "lifecycle_action": f"operation_control_{action.replace('-', '_')}",
        "operation_ref": safe_operation_ref,
        "operation_kind": None,
        "run_id": None,
        "owner": {"surface": "local_cli", "ref": None},
        "state": "blocked",
        "terminal": False,
        "terminal_source": None,
        "stage": None,
        "elapsed_ms": None,
        "last_observed_at": None,
        "checkpoint": {"sequence": None, "last_completed_stage": None},
        "result": {
            "available": False,
            "available_at_completion": False,
            "reconciled_from_complete_output": False,
            "binding_verified": False,
            "ok": None,
            "exit_code": None,
            "domain_truth_verified": False,
        },
        "control": {
            "control_digest": None,
            "cancel_supported": False,
            "cancel_requested": False,
            "resume_supported": False,
            "recovery_required": False,
        },
        "wait": None,
        "next_safe_actions": [],
        "blockers": [],
        "warnings": [],
        "privacy_guards": {
            "writes": False,
            "locks_acquired": False,
            "process_ids_echoed": False,
            "local_paths_echoed": False,
            "private_values_echoed": False,
            "raw_errors_echoed": False,
            "provider_or_network_called": False,
        },
    }


def _journal_candidates(root: Path, operation_hex: str) -> list[Path]:
    candidates = [
        _path_below(root, ARCHIVE_JOURNAL_RELATIVE)
        / f"{operation_hex}.jsonl",
        _path_below(root, PROJECT_JOURNAL_RELATIVE)
        / f"{operation_hex}.jsonl",
    ]
    return [path for path in candidates if path.exists() or path.is_symlink()]


def inspect_operation(
    control_root: Path | str,
    operation_ref: str,
    *,
    action: str = "status",
) -> dict[str, Any]:
    result = _control_base(str(operation_ref or ""), action)
    try:
        operation_hex = _operation_hex(operation_ref)
        root = require_control_root(control_root)
        candidates = _journal_candidates(root, operation_hex)
        if not candidates:
            raise OperationControlError("operation_not_found")
        if len(candidates) != 1:
            raise OperationControlError("operation_journal_ambiguous")
        records = _read_journal(candidates[0], root)
        if records[0]["operation_ref"] != operation_ref:
            raise OperationControlError("operation_journal_invalid")
        if records[0]["root_ref"] != _root_ref(root):
            raise OperationControlError("operation_root_mismatch")
        if (
            _parse_timestamp(records[-1]["observed_at"])
            - datetime.now(timezone.utc)
        ).total_seconds() > MAX_FUTURE_SKEW_SECONDS:
            raise OperationControlError("operation_journal_future_timestamp")
    except OperationControlError as exc:
        result["state"] = "recovery_required"
        result["control"]["recovery_required"] = True
        result["blockers"] = [exc.code]
        result["next_safe_actions"] = [
            "Preserve any operation journal, result artifact, and command-owned lock; do not force-kill, delete, or retry the writer from this evidence alone."
        ]
        return result

    first = records[0]
    latest = records[-1]
    terminal = bool(latest["terminal"])
    last_observed = _parse_timestamp(latest["observed_at"])
    age_seconds = max(
        0.0, (datetime.now(timezone.utc) - last_observed).total_seconds()
    )
    artifact_match: dict[str, Any] | None = None
    verification_blocker: str | None = None
    should_reconcile_artifact = terminal or age_seconds > HEARTBEAT_STALE_SECONDS
    if should_reconcile_artifact:
        try:
            artifact_match = _find_result_artifact(
                root,
                operation_ref=str(latest["operation_ref"]),
                run_id=str(latest["run_id"]),
                root_ref=str(latest["root_ref"]),
                output_ref=str(latest["output_ref"]),
                command=KIND_COMMANDS[str(latest["operation_kind"])],
                expected_sha256=(
                    str(latest["result_sha256"])
                    if latest["result_available"]
                    else None
                ),
                expected_bytes=(
                    int(latest["result_bytes"])
                    if latest["result_available"]
                    else None
                ),
                expected_exit_code=(
                    int(latest["exit_code"])
                    if latest["result_available"]
                    else None
                ),
                expected_result_ok=(
                    bool(latest["result_ok"])
                    if latest["result_available"]
                    else None
                ),
            )
        except OperationControlError as exc:
            verification_blocker = exc.code
    result_binding_verified = artifact_match is not None
    reconciled_from_output = result_binding_verified and not (
        terminal and latest["result_available"]
    )
    effective_terminal = terminal or reconciled_from_output
    if result_binding_verified:
        state = "completed_result_available"
        recovery_required = False
    elif terminal and latest["result_available"]:
        state = "recovery_required"
        recovery_required = True
        if verification_blocker is None:
            verification_blocker = "operation_result_missing_or_unverifiable"
    elif terminal:
        state = "recovery_required"
        recovery_required = True
        if verification_blocker is None:
            verification_blocker = "operation_result_unavailable_at_completion"
    elif age_seconds <= HEARTBEAT_STALE_SECONDS:
        state = "running_observed"
        recovery_required = False
    else:
        state = "recovery_required"
        recovery_required = True
        if verification_blocker is None:
            verification_blocker = "operation_observation_stale"
    result.update(
        {
            "ok": not recovery_required,
            "operation_kind": latest["operation_kind"],
            "run_id": latest["run_id"],
            "owner": {"surface": "local_cli", "ref": latest["owner_ref"]},
            "state": state,
            "terminal": effective_terminal,
            "terminal_source": (
                "journal_and_complete_output"
                if terminal and result_binding_verified
                else "complete_output_reconciliation"
                if reconciled_from_output
                else "journal_without_verified_output"
                if terminal
                else None
            ),
            "stage": latest["stage"],
            "elapsed_ms": latest["elapsed_ms"],
            "last_observed_at": latest["observed_at"],
            "checkpoint": {
                "sequence": latest["sequence"],
                "last_completed_stage": latest["last_completed_stage"],
            },
            "result": {
                "available": result_binding_verified,
                "available_at_completion": bool(latest["result_available"]),
                "reconciled_from_complete_output": reconciled_from_output,
                "binding_verified": result_binding_verified,
                "ok": (
                    artifact_match["result_ok"]
                    if artifact_match is not None
                    else latest["result_ok"]
                ),
                "exit_code": (
                    artifact_match["exit_code"]
                    if artifact_match is not None
                    else latest["exit_code"]
                ),
                "domain_truth_verified": False,
            },
            "control": {
                "control_digest": first["control_digest"],
                "cancel_supported": False,
                "cancel_requested": False,
                "resume_supported": False,
                "recovery_required": recovery_required,
            },
            "blockers": [verification_blocker] if verification_blocker else [],
        }
    )
    if state == "running_observed":
        result["next_safe_actions"] = [
            "Wait for the same operation; do not start a duplicate writer and do not treat a caller timeout as cancellation."
        ]
    elif state == "completed_result_available":
        result["next_safe_actions"] = [
            "Use the complete output artifact and the command-specific verification step before claiming domain completion."
        ]
    else:
        result["next_safe_actions"] = [
            "Run operation-control recovery-plan; preserve journals, results, locks, and SQLite sidecars until command-specific authority is checked."
        ]
    return result


def wait_operation(
    control_root: Path | str,
    operation_ref: str,
    timeout_seconds: int,
    *,
    _clock: Callable[[], float] = time.monotonic,
    _sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or not 1 <= timeout_seconds <= MAX_WAIT_SECONDS
    ):
        result = _control_base(operation_ref, "wait")
        result["blockers"] = ["operation_wait_timeout_invalid"]
        result["next_safe_actions"] = [
            "Choose --timeout-seconds from 1 through 60."
        ]
        return result
    deadline = _clock() + timeout_seconds
    while True:
        result = inspect_operation(
            control_root, operation_ref, action="wait"
        )
        if (
            not result["ok"]
            or result["terminal"]
            or result["control"]["recovery_required"]
        ):
            result["wait"] = {
                "outcome": "terminal_or_attention_observed",
                "timeout_seconds": timeout_seconds,
                "cancel_requested": False,
            }
            return result
        remaining = deadline - _clock()
        if remaining <= 0:
            result["wait"] = {
                "outcome": "deadline_reached",
                "timeout_seconds": timeout_seconds,
                "cancel_requested": False,
            }
            result["next_safe_actions"] = [
                "Waiting stopped; the operation may still be running. No cancel request was sent. Run status or wait again with the same operation_ref."
            ]
            return result
        _sleep(min(0.25, remaining))


def recovery_plan(
    control_root: Path | str,
    operation_ref: str,
) -> dict[str, Any]:
    result = inspect_operation(
        control_root, operation_ref, action="recovery-plan"
    )
    kind = result.get("operation_kind")
    if result.get("state") == "running_observed":
        actions = [
            "Wait for the same operation_ref; do not start a duplicate writer and do not send a force-kill."
        ]
    elif result.get("state") == "completed_result_available":
        if kind == "project_version_update":
            actions = [
                "Start a new process and run archive version <project-or-archive-root> --format json before claiming the update active."
            ]
        elif kind == "archive_index":
            actions = [
                "Run archive index-health <archive-root> --dry-run --progress --format json before retrying an index-dependent command."
            ]
        else:
            actions = [
                "Review the complete index-health result together with its exit code and index_state."
            ]
    else:
        actions = [
            "Preserve the operation journal, complete result if present, command-owned locks, and SQLite sidecars.",
            "Do not force-kill, delete a lock or sidecar, claim cancellation, resume an old SQLite transaction, or start a duplicate writer from this evidence alone.",
        ]
        if kind == "project_version_update":
            actions.append(
                "Run archive version <project-or-archive-root> --format json and compare source, pins, tag, receipt, and import-origin evidence."
            )
        elif kind in {"archive_index", "archive_index_health"}:
            actions.append(
                "Run a fresh archive index-health <archive-root> --dry-run --progress --format json; treat committed SQLite truth as authoritative over missing terminal output."
            )
    result["next_safe_actions"] = actions
    return result


def unsupported_cancel(
    control_root: Path | str,
    operation_ref: str,
    *,
    approve: bool,
    reviewed_by: str | None,
    expected_control_digest: str | None,
) -> dict[str, Any]:
    # v0.3 intentionally has no cooperative cancel protocol.  Approval inputs
    # are accepted only for forward-compatible CLI parsing and never validated,
    # persisted, or treated as authorization in this unsupported surface.
    del approve, reviewed_by, expected_control_digest
    result = inspect_operation(control_root, operation_ref, action="cancel")
    result["ok"] = False
    result["dry_run"] = False
    blockers: list[str] = list(result.get("blockers") or [])
    if "operation_cancel_not_supported" not in blockers:
        blockers.append("operation_cancel_not_supported")
    result["state"] = "blocked"
    result["blockers"] = blockers
    result["control"]["cancel_supported"] = False
    result["control"]["cancel_requested"] = False
    result["control"]["resume_supported"] = False
    result["privacy_guards"]["writes"] = False
    result["next_safe_actions"] = [
        "No cancel request was written. Use status or bounded wait; if observation becomes stale, use recovery-plan without deleting locks or sidecars."
    ]
    return result


__all__ = [
    "ARCHIVE_OUTPUT_PREFIX",
    "MAX_WAIT_SECONDS",
    "OPERATION_CONTROL_SCHEMA",
    "OPERATION_JOURNAL_SCHEMA",
    "PROJECT_OUTPUT_PREFIX",
    "OperationControlError",
    "OperationRunJournal",
    "inspect_operation",
    "recovery_plan",
    "require_control_root",
    "unsupported_cancel",
    "wait_operation",
]
