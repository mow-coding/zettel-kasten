"""Cancelable waiting around the existing archive OS lock, not a new lock.

The caller plans again only after this context yields, then requests approval.
Progress contains no owner labels, paths, session IDs or approval authority.
Local display of holder names must use separately verified private registry
state; a timeout, stale PID or label can never revoke the operating-system lock.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import time
from typing import Callable, Iterator

from . import exact_operation_manifest as exact
from . import project_update_transaction as durable


class WorkSessionWaitError(RuntimeError):
    def __init__(self, code):
        super().__init__(code if code in {
            "work_session_wait_cancelled", "work_session_wait_root_changed",
        } else "work_session_wait_root_changed")


def _root_identity(root: Path):
    try:
        durable._safe_existing_chain(root, directory=True)
        info = os.lstat(root)
        return info.st_dev, info.st_ino
    except (OSError, durable.ProjectUpdateTransactionError):
        raise WorkSessionWaitError("work_session_wait_root_changed") from None


@contextmanager
def wait_for_archive_writer(
    archive_root: Path, *,
    cancel_requested: Callable[[], bool],
    progress: Callable[[dict], None],
) -> Iterator[exact.ExactOperationWriterLock]:
    """Wait without stealing; cancellation is observed before every attempt.

    Acquisition attempts are nonblocking. Between them a short sleep bounds
    cancellation latency; progress is emitted immediately and every five seconds.
    No approval or domain callback occurs before a real held lock is yielded.
    """
    started = time.monotonic()
    if cancel_requested():
        raise WorkSessionWaitError("work_session_wait_cancelled")
    root = Path(os.path.abspath(archive_root))
    identity = _root_identity(root)
    progress({"stage": "waiting_for_writer", "elapsed_seconds": 0.0})
    last_progress = started
    while True:
        if cancel_requested():
            raise WorkSessionWaitError("work_session_wait_cancelled")
        if _root_identity(root) != identity:
            raise WorkSessionWaitError("work_session_wait_root_changed")
        held = exact.ExactOperationWriterLock(root, timeout_seconds=0)
        try:
            held.__enter__()
        except exact.ExactOperationManifestError as error:
            if error.code != "exact_operation_writer_busy":
                raise
            now = time.monotonic()
            if now - last_progress >= 5:
                progress({"stage": "waiting_for_writer", "elapsed_seconds": round(now - started, 3)})
                last_progress = now
            time.sleep(0.1)
            continue
        try:
            if cancel_requested():
                raise WorkSessionWaitError("work_session_wait_cancelled")
            if _root_identity(root) != identity:
                raise WorkSessionWaitError("work_session_wait_root_changed")
            held.verify_held()
            progress({"stage": "writer_acquired_revalidation_required", "elapsed_seconds": round(time.monotonic() - started, 3)})
            # A synchronous display callback can deliver cancellation or alter
            # the observed boundary. Recheck before any caller plan or approval.
            if cancel_requested():
                raise WorkSessionWaitError("work_session_wait_cancelled")
            if _root_identity(root) != identity:
                raise WorkSessionWaitError("work_session_wait_root_changed")
            held.verify_held()
            yield held
        finally:
            held.__exit__(None, None, None)
        return
