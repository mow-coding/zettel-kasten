"""OS-backed target leases for new concurrent operations.

These leases never impersonate the legacy archive-wide writer lock. Network
work holds only its target/execution leases; shared publication still takes
the existing archive lock. A lock file is stable and is never stolen/deleted.
"""
from contextlib import ExitStack
import hashlib
import math
import time

from .exact_operation_manifest import (
    ExactOperationWriterLock, FileExactOperationCheckpointStore,
    _ensure_private_directory, _exact_operation_archive_root, _digest, _fail,
)


def target_digest(kind, reference):
    if kind not in {"object", "zet", "file", "activity", "execution"} or type(reference) is not str or not reference:
        raise _fail("exact_operation_writer_lock_invalid")
    return hashlib.sha256((kind + "\0" + reference).encode("utf-8")).hexdigest()


class TargetLease(ExactOperationWriterLock):
    """A named OS lease, deliberately rejected by legacy exact-type checks."""

    def __init__(self, archive_root, *, kind, reference, timeout_seconds=30, heartbeat=None):
        digest = target_digest(kind, reference)
        super().__init__(archive_root, timeout_seconds=timeout_seconds, heartbeat=heartbeat)
        self.private_root = _ensure_private_directory(self.private_root, ("target-locks",))
        self.path = self.private_root / (digest + ".lock")
        self.kind = kind
        self.reference_digest = digest


class TargetLeases:
    """Deterministic lock order and one bounded, cancelable contention budget."""

    def __init__(self, archive_root, targets, *, timeout_seconds=30, heartbeat=None):
        if (type(timeout_seconds) not in {int, float} or not math.isfinite(timeout_seconds)
                or not 0 <= timeout_seconds <= 60):
            raise _fail("exact_operation_writer_lock_invalid")
        self.root = archive_root
        self.targets = sorted(set(targets), key=lambda item: target_digest(*item))
        if not self.targets:
            raise _fail("exact_operation_writer_lock_invalid")
        self.timeout = timeout_seconds
        self.heartbeat = heartbeat or (lambda: None)
        self._stack = None
        self.leases = {}
        self.wait_seconds = 0.0

    def __enter__(self):
        if self._stack is not None:
            raise _fail("exact_operation_writer_lock_invalid")
        started = time.monotonic()
        stack = ExitStack()
        try:
            for kind, reference in self.targets:
                self.heartbeat()
                lease = stack.enter_context(TargetLease(
                    self.root, kind=kind, reference=reference,
                    timeout_seconds=max(0, self.timeout - (time.monotonic() - started)),
                    heartbeat=self.heartbeat))
                self.leases[(kind, reference)] = lease
            self._stack = stack
            self.wait_seconds = time.monotonic() - started
            return self
        except BaseException:
            stack.close()
            self.leases.clear()
            raise

    def verify_held(self):
        if self._stack is None:
            raise _fail("exact_operation_writer_lock_required")
        for lease in self.leases.values():
            lease.verify_held()

    def __exit__(self, *exc):
        try:
            if self._stack is not None:
                return self._stack.__exit__(*exc)
        finally:
            self._stack = None
            self.leases.clear()


class ExecutionCheckpointStore(FileExactOperationCheckpointStore):
    """Retain the common authenticated checkpoint format, scoped to one run.

    A dedicated execution lease allows linear checkpoint scans and append
    cursors to live across remote calls without holding the archive lock.
    Every path access rejects an execution outside this exact lease.
    """

    def __init__(self, archive_root, *, execution_sha256, lease):
        root = _exact_operation_archive_root(archive_root)
        self.execution_sha256 = _digest(execution_sha256, code="exact_operation_checkpoint_store_invalid")
        if (type(lease) is not TargetLease or lease.archive_root != root or lease.kind != "execution"
                or lease.reference_digest != target_digest("execution", self.execution_sha256)):
            raise _fail("exact_operation_writer_lock_required")
        self._initialize(root, lease)

    def _require_execution(self, value):
        if value != self.execution_sha256:
            raise _fail("exact_operation_checkpoint_store_invalid")

    def _checkpoint_path(self, execution_sha256):
        self._require_execution(execution_sha256)
        return super()._checkpoint_path(execution_sha256)

    def _result_path(self, execution_sha256):
        self._require_execution(execution_sha256)
        return super()._result_path(execution_sha256)
