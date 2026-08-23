"""Fail-closed orchestration for one exact human-approved archive write.

The order is fixed:

1. show the live native digest-bound review dialog;
2. acquire/create the existing archive-specific Windows authentication key;
3. publish and reauthenticate a durable ``started`` one-use claim;
4. give the in-process authenticated claim object to the writer so the writer
   can reauthenticate the exact context immediately before mutation;
5. finalize only a well-formed successful writer result as ``succeeded``;
6. if supplied, run one bounded finalizer only after that durable succeeded
   claim is re-observable; every non-success after writer entry remains
   ``started`` for reconciliation;
7. wipe the copied key.

Cancellation performs no key/store/filesystem write.  Synthetic intent and
generic writer injection are not public APIs.  Bounded tests use only the
underscore orchestration core, so no real popup or Windows credential
operation is performed.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, TypeVar

from .exact_human_approval import (
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    _claim_exact_human_approval_core,
    _rehydrate_existing_exact_human_approval_core,
    _rehydrate_exact_human_approval_core,
    _rehydrate_succeeded_exact_human_approval_core,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalIntent,
    ExactHumanApprovalWindowsError,
    _ExactHumanApprovalNative,
    _request_exact_human_approval_core,
)


_T = TypeVar("_T")
_ClaimSucceededFinalizer = Callable[[_ClaimedExactHumanApproval], None]


class _ArchiveAuthenticationKeyProvider(Protocol):
    def use_key(
        self,
        archive_root: Path | str,
        consumer: Callable[[memoryview], _T],
        *,
        create_if_missing: bool = False,
    ) -> _T: ...


class ExactHumanApprovalWorkflowError(RuntimeError):
    _CODES = {
        "exact_human_approval_cancelled",
        "exact_human_approval_key_unavailable",
        "exact_human_approval_claim_failed",
        "exact_human_approval_resume_claim_invalid",
        "exact_human_approval_resume_checkpoint_invalid",
        "exact_human_approval_writer_result_invalid",
        "exact_human_approval_operation_failed",
        "exact_human_approval_state_unknown",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "exact_human_approval_state_unknown"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ExactHumanApprovalWorkflowError({self.code!r})"


def _fail(code: str) -> ExactHumanApprovalWorkflowError:
    return ExactHumanApprovalWorkflowError(code)


def _production_key_provider() -> _ArchiveAuthenticationKeyProvider:
    try:
        from .credential_secure_intake_windows import _CtypesWindowsNativeFacade
        from .credential_secure_registry import _StableArchiveFingerprintKeyProvider

        native = _CtypesWindowsNativeFacade(cli_live_approved=True)
        return _StableArchiveFingerprintKeyProvider(native)
    except BaseException:
        raise _fail("exact_human_approval_key_unavailable") from None


def _run_started_claim_writer(
    context: ExactHumanApprovalContext,
    writer: Callable[[_ClaimedExactHumanApproval], Mapping[str, Any]],
    claim: _ClaimedExactHumanApproval,
    *,
    claim_succeeded_finalizer: _ClaimSucceededFinalizer | None = None,
) -> dict[str, Any]:
    """Run one writer, then finish claim-bound domain finalization in order."""

    try:
        reference = claim.assert_ready_for_context(context)
        try:
            raw_result = writer(claim)
        except BaseException:
            # The writer is the mutation boundary.  Once it has been entered,
            # an exception cannot prove whether zero, some, or all durable
            # writes happened.  Preserve the authenticated claim in
            # ``started`` for reconciliation.
            raise _fail("exact_human_approval_state_unknown") from None
        if not isinstance(raw_result, Mapping) or type(raw_result.get("ok")) is not bool:
            # A malformed return has the same ambiguity as an exception: the
            # writer may already have committed its mutation.
            raise _fail("exact_human_approval_state_unknown")
        result = dict(raw_result)
        if result["ok"] is True:
            try:
                claim.finalize_succeeded()
                if claim_succeeded_finalizer is not None:
                    claim_succeeded_finalizer(claim)
            except BaseException:
                # The claim may already be durably ``succeeded`` and the
                # bounded domain finalizer may have completed zero, some, or
                # all of its effects.  Never retry or report ordinary failure
                # from this ambiguity.  A transaction-aware caller keeps its
                # lock/evidence for explicit reconciliation.
                raise _fail("exact_human_approval_state_unknown") from None
        else:
            # A writer-level ``ok: false`` cannot prove that zero durable
            # effects occurred.  Keep the one-use claim ``started`` and
            # require explicit reconciliation.
            result["exact_human_approval_reconciliation"] = {
                "required": True,
                "reason_code": "approval_claim_reconciliation_required",
                "automatic_retry_allowed": False,
            }
        result["exact_human_approval"] = claim.public_summary()
        result["exact_human_approval_reference"] = reference
        return result
    finally:
        claim.close()


def _execute_exact_human_approved_write_core(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    writer: Callable[[_ClaimedExactHumanApproval], Mapping[str, Any]],
    *,
    native: _ExactHumanApprovalNative | None = None,
    key_provider: _ArchiveAuthenticationKeyProvider | None = None,
    post_decision_boundary: (
        Callable[
            [],
            AbstractContextManager[
                tuple[Path, dict[str, Any]] | None
            ],
        ]
        | None
    ) = None,
    claim_succeeded_finalizer: _ClaimSucceededFinalizer | None = None,
) -> dict[str, Any]:
    """Internal fakeable orchestration core for production and bounded tests."""

    if (
        type(context) is not ExactHumanApprovalContext
        or not callable(writer)
        or (
            claim_succeeded_finalizer is not None
            and not callable(claim_succeeded_finalizer)
        )
    ):
        raise _fail("exact_human_approval_writer_result_invalid")
    try:
        decision = _request_exact_human_approval_core(
            context,
            intent=ExactHumanApprovalIntent.live_write,
            native=native,
        )
    except ExactHumanApprovalWindowsError:
        raise _fail("exact_human_approval_operation_failed") from None
    if decision.approved is not True:
        raise _fail("exact_human_approval_cancelled")

    def _with_key(
        key: memoryview,
        filesystem_boundary: tuple[Path, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        try:
            claim = _claim_exact_human_approval_core(
                archive_root,
                context,
                decision,
                key,
                bound_archive_root=(
                    filesystem_boundary[0]
                    if filesystem_boundary is not None
                    else None
                ),
                claim_parent_binding=(
                    filesystem_boundary[1]
                    if filesystem_boundary is not None
                    else None
                ),
            )
        except ExactHumanApprovalError:
            raise _fail("exact_human_approval_claim_failed") from None
        return _run_started_claim_writer(
            context,
            writer,
            claim,
            claim_succeeded_finalizer=claim_succeeded_finalizer,
        )

    try:
        boundary_context = (
            post_decision_boundary()
            if post_decision_boundary is not None
            else nullcontext(None)
        )
        with boundary_context as filesystem_boundary:
            selected = (
                key_provider
                if key_provider is not None
                else _production_key_provider()
            )
            return selected.use_key(
                archive_root,
                lambda key: _with_key(key, filesystem_boundary),
                create_if_missing=True,
            )
    except ExactHumanApprovalWorkflowError:
        raise
    except BaseException:
        raise _fail("exact_human_approval_key_unavailable") from None


def _execute_exact_human_approved_write(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    writer: Callable[[_ClaimedExactHumanApproval], Mapping[str, Any]],
    *,
    claim_succeeded_finalizer: _ClaimSucceededFinalizer | None = None,
) -> dict[str, Any]:
    """Run one writer through the non-injectable production approval boundary."""

    return _execute_exact_human_approved_write_core(
        archive_root,
        context,
        writer,
        native=None,
        key_provider=None,
        post_decision_boundary=None,
        claim_succeeded_finalizer=claim_succeeded_finalizer,
    )


def _resume_exact_human_approved_write_core(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    approval_id: str,
    checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    writer: Callable[[_ClaimedExactHumanApproval], Mapping[str, Any]],
    *,
    key_provider: _ArchiveAuthenticationKeyProvider | None = None,
    resume_boundary: (
        Callable[
            [],
            AbstractContextManager[tuple[Path, dict[str, Any]] | None],
        ]
        | None
    ) = None,
    claim_succeeded_finalizer: _ClaimSucceededFinalizer | None = None,
) -> dict[str, Any]:
    """Resume the same started claim without displaying a new native dialog.

    ``checkpoint_guard`` is a fail-closed domain callback.  It receives the
    reauthenticated started claim so it can derive the exact approval
    authority and execution digest, then must prove that the corresponding
    durable checkpoint exists before the writer is entered.  The
    exact-operation runner performs the full checkpoint-chain and target-state
    validation after that guard.
    """

    if (
        type(context) is not ExactHumanApprovalContext
        or type(approval_id) is not str
        or not callable(checkpoint_guard)
        or not callable(writer)
        or (
            claim_succeeded_finalizer is not None
            and not callable(claim_succeeded_finalizer)
        )
    ):
        raise _fail("exact_human_approval_writer_result_invalid")

    def _with_key(
        key: memoryview,
        filesystem_boundary: tuple[Path, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        try:
            claim = _rehydrate_exact_human_approval_core(
                archive_root,
                context,
                approval_id,
                key,
                bound_archive_root=(
                    filesystem_boundary[0]
                    if filesystem_boundary is not None
                    else None
                ),
                claim_parent_binding=(
                    filesystem_boundary[1]
                    if filesystem_boundary is not None
                    else None
                ),
            )
        except ExactHumanApprovalError:
            raise _fail("exact_human_approval_resume_claim_invalid") from None
        try:
            try:
                checkpoint_matches = checkpoint_guard(claim)
            except BaseException:
                raise _fail(
                    "exact_human_approval_resume_checkpoint_invalid"
                ) from None
            if checkpoint_matches is not True:
                raise _fail("exact_human_approval_resume_checkpoint_invalid")
        except BaseException:
            claim.close()
            raise
        return _run_started_claim_writer(
            context,
            writer,
            claim,
            claim_succeeded_finalizer=claim_succeeded_finalizer,
        )

    try:
        boundary_context = (
            resume_boundary() if resume_boundary is not None else nullcontext(None)
        )
        with boundary_context as filesystem_boundary:
            selected = (
                key_provider
                if key_provider is not None
                else _production_key_provider()
            )
            return selected.use_key(
                archive_root,
                lambda key: _with_key(key, filesystem_boundary),
                create_if_missing=False,
            )
    except ExactHumanApprovalWorkflowError:
        raise
    except BaseException:
        raise _fail("exact_human_approval_key_unavailable") from None


def _resume_succeeded_claim_finalizer_core(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    approval_id: str,
    checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    claim_succeeded_finalizer: _ClaimSucceededFinalizer,
    *,
    key_provider: _ArchiveAuthenticationKeyProvider | None = None,
    resume_boundary: (
        Callable[
            [],
            AbstractContextManager[tuple[Path, dict[str, Any]] | None],
        ]
        | None
    ) = None,
) -> dict[str, Any]:
    """Finish only the bounded tail of an authenticated succeeded claim.

    This recovery path never displays another native dialog and never enters
    the domain writer.  It exists for the hard-exit window after the claim was
    durably finalized but before the transaction journal and lock-release tail
    completed.
    """

    if (
        type(context) is not ExactHumanApprovalContext
        or type(approval_id) is not str
        or not callable(checkpoint_guard)
        or not callable(claim_succeeded_finalizer)
    ):
        raise _fail("exact_human_approval_writer_result_invalid")

    def _with_key(
        key: memoryview,
        filesystem_boundary: tuple[Path, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        try:
            claim = _rehydrate_succeeded_exact_human_approval_core(
                archive_root,
                context,
                approval_id,
                key,
                bound_archive_root=(
                    filesystem_boundary[0]
                    if filesystem_boundary is not None
                    else None
                ),
                claim_parent_binding=(
                    filesystem_boundary[1]
                    if filesystem_boundary is not None
                    else None
                ),
            )
        except ExactHumanApprovalError:
            raise _fail("exact_human_approval_resume_claim_invalid") from None
        try:
            reference = claim.assert_succeeded_for_context(context)
            try:
                checkpoint_matches = checkpoint_guard(claim)
            except BaseException:
                raise _fail(
                    "exact_human_approval_resume_checkpoint_invalid"
                ) from None
            if checkpoint_matches is not True:
                raise _fail("exact_human_approval_resume_checkpoint_invalid")
            try:
                claim_succeeded_finalizer(claim)
            except BaseException:
                raise _fail("exact_human_approval_state_unknown") from None
            return {
                "ok": True,
                "status": "succeeded_claim_finalizer_completed",
                "domain_writer_reentered": False,
                "native_approval_redisplayed": False,
                "exact_human_approval": claim.public_summary(),
                "exact_human_approval_reference": reference,
            }
        finally:
            claim.close()

    try:
        boundary_context = (
            resume_boundary() if resume_boundary is not None else nullcontext(None)
        )
        with boundary_context as filesystem_boundary:
            selected = (
                key_provider
                if key_provider is not None
                else _production_key_provider()
            )
            return selected.use_key(
                archive_root,
                lambda key: _with_key(key, filesystem_boundary),
                create_if_missing=False,
            )
    except ExactHumanApprovalWorkflowError:
        raise
    except BaseException:
        raise _fail("exact_human_approval_key_unavailable") from None


def _resume_exact_human_approved_transaction_core(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    approval_id: str,
    started_checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    started_writer: Callable[[_ClaimedExactHumanApproval], Mapping[str, Any]],
    succeeded_checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    claim_succeeded_finalizer: _ClaimSucceededFinalizer,
    *,
    key_provider: _ArchiveAuthenticationKeyProvider | None = None,
    resume_boundary: (
        Callable[
            [],
            AbstractContextManager[tuple[Path, dict[str, Any]] | None],
        ]
        | None
    ) = None,
) -> dict[str, Any]:
    """Route one authenticated resume without guessing the durable claim state."""

    if (
        type(context) is not ExactHumanApprovalContext
        or type(approval_id) is not str
        or not callable(started_checkpoint_guard)
        or not callable(started_writer)
        or not callable(succeeded_checkpoint_guard)
        or not callable(claim_succeeded_finalizer)
    ):
        raise _fail("exact_human_approval_writer_result_invalid")

    def _with_key(
        key: memoryview,
        filesystem_boundary: tuple[Path, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        try:
            claim = _rehydrate_existing_exact_human_approval_core(
                archive_root,
                context,
                approval_id,
                key,
                bound_archive_root=(
                    filesystem_boundary[0]
                    if filesystem_boundary is not None
                    else None
                ),
                claim_parent_binding=(
                    filesystem_boundary[1]
                    if filesystem_boundary is not None
                    else None
                ),
            )
        except ExactHumanApprovalError:
            raise _fail("exact_human_approval_resume_claim_invalid") from None

        if claim.status == "started":
            try:
                try:
                    checkpoint_matches = started_checkpoint_guard(claim)
                except BaseException:
                    raise _fail(
                        "exact_human_approval_resume_checkpoint_invalid"
                    ) from None
                if checkpoint_matches is not True:
                    raise _fail(
                        "exact_human_approval_resume_checkpoint_invalid"
                    )
            except BaseException:
                claim.close()
                raise
            result = _run_started_claim_writer(
                context,
                started_writer,
                claim,
                claim_succeeded_finalizer=claim_succeeded_finalizer,
            )
            result["exact_human_approval_resume_branch"] = "started_writer"
            result["native_approval_redisplayed"] = False
            return result

        try:
            reference = claim.assert_succeeded_for_context(context)
            try:
                checkpoint_matches = succeeded_checkpoint_guard(claim)
            except BaseException:
                raise _fail(
                    "exact_human_approval_resume_checkpoint_invalid"
                ) from None
            if checkpoint_matches is not True:
                raise _fail("exact_human_approval_resume_checkpoint_invalid")
            try:
                claim_succeeded_finalizer(claim)
            except BaseException:
                raise _fail("exact_human_approval_state_unknown") from None
            return {
                "ok": True,
                "status": "succeeded_claim_finalizer_completed",
                "exact_human_approval_resume_branch": "succeeded_tail",
                "domain_writer_reentered": False,
                "native_approval_redisplayed": False,
                "exact_human_approval": claim.public_summary(),
                "exact_human_approval_reference": reference,
            }
        finally:
            claim.close()

    try:
        boundary_context = (
            resume_boundary() if resume_boundary is not None else nullcontext(None)
        )
        with boundary_context as filesystem_boundary:
            selected = (
                key_provider
                if key_provider is not None
                else _production_key_provider()
            )
            return selected.use_key(
                archive_root,
                lambda key: _with_key(key, filesystem_boundary),
                create_if_missing=False,
            )
    except ExactHumanApprovalWorkflowError:
        raise
    except BaseException:
        raise _fail("exact_human_approval_key_unavailable") from None


__all__ = [
    "ExactHumanApprovalWorkflowError",
]
