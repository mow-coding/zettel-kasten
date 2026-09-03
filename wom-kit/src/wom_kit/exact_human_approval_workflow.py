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

import os
import re
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, TypeVar

from .exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    _authenticated_claim_routing_core,
    _claim_exact_human_approval_core,
    _rehydrate_existing_exact_human_approval_core,
    _rehydrate_exact_human_approval_core,
    _rehydrate_succeeded_exact_human_approval_core,
    exact_human_approval_context_sha256,
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
_APPROVAL_CLAIM_FILENAME_RE = re.compile(
    r"^(approval_[0-9a-f]{32})\.json$"
)
_MAX_RESUME_CLAIM_DIRECTORY_ENTRIES = 100_000
_RESUME_MISSING_REASON_AUTHENTICATED_CANDIDATE = (
    "authenticated_candidate_missing"
)
_RESUME_MISSING_REASON_CLAIM_STORE_ABSENT = "claim_store_absent"
_AUTOMATIC_RESUME_PRIVATE_LOCATOR_KEYS = frozenset(
    {
        "approval_id",
        "exact_human_approval",
        "exact_human_approval_reference",
        "operation_exact_human_approval",
        "transaction_logical_ref",
        "transaction_ref",
    }
)
_AUTOMATIC_RESUME_APPROVAL_LOCATOR_RE = re.compile(
    r"approval_[0-9a-f]{32}"
)
_AUTOMATIC_RESUME_TRANSACTION_LOCATOR_RE = re.compile(
    r"update_[0-9a-f]{32}"
)
_AUTOMATIC_RESUME_OMITTED = object()


class _ArchiveAuthenticationKeyProvider(Protocol):
    def use_key(
        self,
        archive_root: Path | str,
        consumer: Callable[[memoryview], _T],
        *,
        create_if_missing: bool = False,
    ) -> _T: ...


_CAUSE_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,95}")
_CAUSE_STAGES = frozenset({"candidate_missing_handler"})


class ExactHumanApprovalWorkflowError(RuntimeError):
    _CODES = {
        "exact_human_approval_cancelled",
        "exact_human_approval_key_unavailable",
        "exact_human_approval_claim_failed",
        "exact_human_approval_resume_claim_invalid",
        "exact_human_approval_resume_candidate_missing",
        "exact_human_approval_resume_candidate_ambiguous",
        "exact_human_approval_resume_checkpoint_invalid",
        "exact_human_approval_writer_result_invalid",
        "exact_human_approval_operation_failed",
        "exact_human_approval_state_unknown",
    }

    def __init__(
        self,
        code: str,
        *,
        cause_code: str | None = None,
        cause_stage: str | None = None,
    ) -> None:
        self.code = code if code in self._CODES else "exact_human_approval_state_unknown"
        # v0.4.18: a wrapped service failure may leave one fixed, code-shaped
        # inner reason and the fixed stage that wrapped it.  Free text, paths,
        # values, and identifiers never qualify, and ``args``/``str()`` still
        # carry only the public workflow code.
        self.cause_code = (
            cause_code
            if type(cause_code) is str
            and _CAUSE_CODE_RE.fullmatch(cause_code) is not None
            else None
        )
        self.cause_stage = (
            cause_stage if cause_stage in _CAUSE_STAGES else None
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ExactHumanApprovalWorkflowError({self.code!r})"


def _content_free_cause_code(cause: BaseException | None) -> str | None:
    """Return a wrapped service error's fixed code only when it is code-shaped.

    ``ArchiveServiceError`` is also used for messages that can contain private
    paths or values, so only a single string argument that matches the fixed
    reason-code shape is carried.  The class is matched by name so this module
    never imports the service layer.
    """

    if (
        cause is None
        or type(cause).__name__
        not in {"ArchiveServiceError", "ProjectUpdateTransactionError"}
        or len(cause.args) != 1
        or type(cause.args[0]) is not str
        or _CAUSE_CODE_RE.fullmatch(cause.args[0]) is None
    ):
        return None
    return cause.args[0]


def _fail(
    code: str,
    *,
    cause: BaseException | None = None,
    cause_stage: str | None = None,
) -> ExactHumanApprovalWorkflowError:
    return ExactHumanApprovalWorkflowError(
        code,
        cause_code=_content_free_cause_code(cause),
        cause_stage=cause_stage,
    )


def _automatic_resume_content_free_projection(
    result: Mapping[str, Any],
    *,
    selected_approval_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Remove private resume locators from one public automatic result.

    Ordinary exact-approval execution and explicit id-based resume keep their
    existing result contract. Automatic discovery is different: its selected
    claim and transaction locators are internal hand-off values, not operator
    output. Project the complete writer/finalizer result at this one boundary
    so nested operation receipts and locator-bearing path strings cannot bypass
    a shallow top-level filter. Content-free state and evidence digests remain.
    """

    if not isinstance(result, Mapping) or any(
        type(value) is not str for value in selected_approval_ids
    ):
        raise _fail("exact_human_approval_state_unknown")

    private_locators = {
        value for value in selected_approval_ids if value
    }

    def collect(value: Any) -> None:
        if isinstance(value, Mapping):
            for raw_key, child in value.items():
                key = str(raw_key)
                if (
                    key
                    in {
                        "approval_id",
                        "transaction_logical_ref",
                        "transaction_ref",
                    }
                    and type(child) is str
                    and child
                ):
                    private_locators.add(child)
                collect(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                collect(child)

    collect(result)

    def contains_private_locator(value: str) -> bool:
        return bool(
            _AUTOMATIC_RESUME_APPROVAL_LOCATOR_RE.search(value)
            or _AUTOMATIC_RESUME_TRANSACTION_LOCATOR_RE.search(value)
            or any(locator in value for locator in private_locators)
        )

    def project(value: Any) -> Any:
        if isinstance(value, Mapping):
            projected: dict[str, Any] = {}
            for raw_key, child in value.items():
                key = str(raw_key)
                if (
                    key in _AUTOMATIC_RESUME_PRIVATE_LOCATOR_KEYS
                    or contains_private_locator(key)
                ):
                    continue
                public_child = project(child)
                if public_child is _AUTOMATIC_RESUME_OMITTED:
                    continue
                projected[key] = public_child
            return projected
        if isinstance(value, (list, tuple)):
            projected_items = []
            for child in value:
                public_child = project(child)
                if public_child is not _AUTOMATIC_RESUME_OMITTED:
                    projected_items.append(public_child)
            return projected_items
        if type(value) is str and contains_private_locator(value):
            return _AUTOMATIC_RESUME_OMITTED
        return value

    projected = project(result)
    if not isinstance(projected, dict):
        raise _fail("exact_human_approval_state_unknown")
    projected["approval_identifier_exposed"] = False
    projected["transaction_identifier_exposed"] = False
    return projected


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
    claim_publication_boundary: (
        Callable[[], AbstractContextManager[Any]] | None
    ) = None,
    claim_succeeded_finalizer: _ClaimSucceededFinalizer | None = None,
) -> dict[str, Any]:
    """Internal fakeable orchestration core for production and bounded tests."""

    if (
        type(context) is not ExactHumanApprovalContext
        or not callable(writer)
        or (
            claim_publication_boundary is not None
            and not callable(claim_publication_boundary)
        )
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
            publication_context = (
                claim_publication_boundary()
                if claim_publication_boundary is not None
                else nullcontext()
            )
            with publication_context:
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
) -> dict[str, Any]:
    """Run one writer through the non-injectable production approval boundary."""

    return _execute_exact_human_approved_write_core(
        archive_root,
        context,
        writer,
        native=None,
        key_provider=None,
        post_decision_boundary=None,
        claim_publication_boundary=None,
        claim_succeeded_finalizer=None,
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


def _resume_exact_human_approved_transaction_with_key_core(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    approval_id: str,
    started_checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    started_writer: Callable[[_ClaimedExactHumanApproval], Mapping[str, Any]],
    succeeded_checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    claim_succeeded_finalizer: _ClaimSucceededFinalizer,
    *,
    key: memoryview,
    filesystem_boundary: tuple[Path, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Finish one selected transaction while its discovery lock is held."""

    if (
        type(context) is not ExactHumanApprovalContext
        or type(approval_id) is not str
        or not callable(started_checkpoint_guard)
        or not callable(started_writer)
        or not callable(succeeded_checkpoint_guard)
        or not callable(claim_succeeded_finalizer)
    ):
        raise _fail("exact_human_approval_writer_result_invalid")

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
        return _resume_exact_human_approved_transaction_with_key_core(
            archive_root,
            context,
            approval_id,
            started_checkpoint_guard,
            started_writer,
            succeeded_checkpoint_guard,
            claim_succeeded_finalizer,
            key=key,
            filesystem_boundary=filesystem_boundary,
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


def _discover_exact_human_approved_transaction_resume_core(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    started_checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    succeeded_checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    *,
    candidate_missing_handler: (
        Callable[[str], Mapping[str, Any]] | None
    ) = None,
    _selected_candidate_handler: (
        Callable[
            [
                str,
                memoryview,
                tuple[Path, dict[str, Any]] | None,
            ],
            Mapping[str, Any],
        ]
        | None
    ) = None,
    key_provider: _ArchiveAuthenticationKeyProvider | None = None,
    resume_boundary: Callable[
        [],
        AbstractContextManager[tuple[Path, dict[str, Any]] | None],
    ],
) -> str | dict[str, Any]:
    """Find one authenticated, checkpoint-valid transaction claim read-only.

    The returned identifier is an internal hand-off to the ordinary resume
    workflow.  It is never needed from the operator and is never included in
    the discovery summary.  The caller must provide a non-creating filesystem
    boundary for the claim directory.  When supplied, the candidate-missing
    handler runs inside the key-provider consumer for an existing claim store
    with zero authenticated checkpoint-valid candidates.  The private selected
    handler likewise runs before that consumer releases the key, so an auto
    resume can finish without a discovery-to-resume lock gap.
    """

    if (
        type(context) is not ExactHumanApprovalContext
        or not callable(started_checkpoint_guard)
        or not callable(succeeded_checkpoint_guard)
        or (
            candidate_missing_handler is not None
            and not callable(candidate_missing_handler)
        )
        or (
            _selected_candidate_handler is not None
            and not callable(_selected_candidate_handler)
        )
        or not callable(resume_boundary)
    ):
        raise _fail("exact_human_approval_writer_result_invalid")

    def _handle_candidate_missing(reason: str) -> dict[str, Any] | None:
        if candidate_missing_handler is None:
            return None
        try:
            raw_result = candidate_missing_handler(reason)
        except ExactHumanApprovalWorkflowError:
            raise
        except BaseException as failure:
            # The handler may have completed zero, some, or all of its bounded
            # recovery effect.  Do not turn an exception into a retryable
            # ordinary missing-candidate result.  Only a fixed code-shaped
            # service reason survives as ``cause_code``; the exception text
            # itself is dropped.
            raise _fail(
                "exact_human_approval_state_unknown",
                cause=failure,
                cause_stage="candidate_missing_handler",
            ) from None
        if (
            not isinstance(raw_result, Mapping)
            or type(raw_result.get("ok")) is not bool
        ):
            raise _fail(
                "exact_human_approval_state_unknown",
                cause_stage="candidate_missing_handler",
            )
        return dict(raw_result)

    def _with_key(
        key: memoryview,
        filesystem_boundary: tuple[Path, dict[str, Any]] | None,
    ) -> str | dict[str, Any]:
        candidates: list[str] = []
        if filesystem_boundary is None:
            raise _fail("exact_human_approval_resume_claim_invalid")
        bound_archive_root, claim_parent_binding = filesystem_boundary
        claims_root = Path(bound_archive_root).joinpath(
            *Path(CLAIMS_RELATIVE_ROOT).parts
        )
        if claim_parent_binding.get("path") != claims_root:
            raise _fail("exact_human_approval_resume_claim_invalid")
        directory_target = claim_parent_binding.get("descriptor")
        if type(directory_target) is not int:
            directory_target = claim_parent_binding.get("path")
        try:
            names = os.listdir(directory_target)
        except (OSError, TypeError, ValueError):
            raise _fail("exact_human_approval_resume_claim_invalid") from None
        if (
            len(names) > _MAX_RESUME_CLAIM_DIRECTORY_ENTRIES
            or any(type(name) is not str for name in names)
        ):
            raise _fail("exact_human_approval_resume_claim_invalid")

        approval_ids = tuple(
            match.group(1)
            for name in sorted(names)
            if (
                match := _APPROVAL_CLAIM_FILENAME_RE.fullmatch(name)
            ) is not None
        )
        for approval_id in approval_ids:
            try:
                claim = _rehydrate_existing_exact_human_approval_core(
                    archive_root,
                    context,
                    approval_id,
                    key,
                    bound_archive_root=bound_archive_root,
                    claim_parent_binding=claim_parent_binding,
                )
            except ExactHumanApprovalError as error:
                if error.code == "exact_human_approval_claim_state_invalid":
                    try:
                        routed_context, _routed_status = (
                            _authenticated_claim_routing_core(
                                archive_root,
                                approval_id,
                                key,
                                bound_archive_root=bound_archive_root,
                                claim_parent_binding=claim_parent_binding,
                            )
                        )
                    except ExactHumanApprovalError:
                        raise _fail(
                            "exact_human_approval_resume_claim_invalid"
                        ) from None
                    if routed_context != exact_human_approval_context_sha256(
                        context
                    ):
                        # An authenticated claim for another exact context is
                        # not a candidate.  A failed or otherwise invalid claim
                        # for this context must never be treated as absence.
                        continue
                raise _fail(
                    "exact_human_approval_resume_claim_invalid"
                ) from None
            try:
                guard = (
                    started_checkpoint_guard
                    if claim.status == "started"
                    else succeeded_checkpoint_guard
                )
                try:
                    checkpoint_matches = guard(claim)
                except BaseException:
                    raise _fail(
                        "exact_human_approval_resume_checkpoint_invalid"
                    ) from None
                if checkpoint_matches is True:
                    candidates.append(approval_id)
            finally:
                claim.close()
        if not candidates:
            handled_missing = _handle_candidate_missing(
                _RESUME_MISSING_REASON_AUTHENTICATED_CANDIDATE
            )
            if handled_missing is None:
                raise _fail(
                    "exact_human_approval_resume_candidate_missing"
                )
            return handled_missing
        if len(candidates) != 1:
            raise _fail("exact_human_approval_resume_candidate_ambiguous")
        approval_id = candidates[0]
        if _selected_candidate_handler is None:
            return approval_id
        try:
            raw_result = _selected_candidate_handler(
                approval_id,
                key,
                filesystem_boundary,
            )
        except ExactHumanApprovalWorkflowError:
            raise
        except BaseException:
            # The selected handler may have entered the domain writer.  Any
            # unclassified exception is therefore an unknown durable state,
            # never a key-acquisition failure or retryable discovery miss.
            raise _fail("exact_human_approval_state_unknown") from None
        if (
            not isinstance(raw_result, Mapping)
            or type(raw_result.get("ok")) is not bool
        ):
            raise _fail("exact_human_approval_state_unknown")
        return dict(raw_result)

    filesystem_boundary_entered = False
    try:
        with resume_boundary() as filesystem_boundary:
            filesystem_boundary_entered = True
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
    except FileNotFoundError:
        if filesystem_boundary_entered:
            raise _fail("exact_human_approval_key_unavailable") from None
        handled_missing = _handle_candidate_missing(
            _RESUME_MISSING_REASON_CLAIM_STORE_ABSENT
        )
        if handled_missing is None:
            raise _fail("exact_human_approval_resume_candidate_missing")
        return handled_missing
    except ExactHumanApprovalWorkflowError:
        raise
    except BaseException:
        raise _fail("exact_human_approval_key_unavailable") from None


def _resume_exact_human_approved_transaction_auto_core(
    archive_root: Path | str,
    context: ExactHumanApprovalContext,
    started_checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    started_writer: Callable[[_ClaimedExactHumanApproval], Mapping[str, Any]],
    succeeded_checkpoint_guard: Callable[[_ClaimedExactHumanApproval], bool],
    claim_succeeded_finalizer: _ClaimSucceededFinalizer,
    *,
    supplied_approval_id: str | None = None,
    candidate_missing_handler: (
        Callable[[str], Mapping[str, Any]] | None
    ) = None,
    key_provider: _ArchiveAuthenticationKeyProvider | None = None,
    resume_boundary: Callable[
        [],
        AbstractContextManager[tuple[Path, dict[str, Any]] | None],
    ],
) -> dict[str, Any]:
    """Discover and resume the only authenticated transaction candidate.

    An optional operator-supplied approval id is an assertion only.  It is
    compared after the complete authenticated, checkpoint-valid candidate
    discovery succeeds, so it can never narrow or bypass that discovery.
    """

    operator_approval_id_supplied = supplied_approval_id is not None
    missing_reasons: list[str] = []
    selected_approval_ids: list[str] = []

    def _record_candidate_missing(reason: str) -> Mapping[str, Any]:
        if operator_approval_id_supplied:
            # A supplied id is an exact assertion about an authenticated
            # candidate, never authority to enter claimless recovery.  For an
            # existing claim store this executes inside the same key and
            # filesystem boundaries that established the zero-candidate fact.
            raise _fail("exact_human_approval_resume_claim_invalid")
        missing_reasons.append(reason)
        if candidate_missing_handler is None:
            raise _fail("exact_human_approval_resume_candidate_missing")
        return candidate_missing_handler(reason)

    def _resume_selected_candidate(
        approval_id: str,
        key: memoryview,
        filesystem_boundary: tuple[Path, dict[str, Any]] | None,
    ) -> Mapping[str, Any]:
        if operator_approval_id_supplied and (
            type(supplied_approval_id) is not str
            or supplied_approval_id != approval_id
        ):
            raise _fail("exact_human_approval_resume_claim_invalid")
        selected_approval_ids.append(approval_id)
        return _resume_exact_human_approved_transaction_with_key_core(
            archive_root,
            context,
            approval_id,
            started_checkpoint_guard,
            started_writer,
            succeeded_checkpoint_guard,
            claim_succeeded_finalizer,
            key=key,
            filesystem_boundary=filesystem_boundary,
        )

    discovered = _discover_exact_human_approved_transaction_resume_core(
        archive_root,
        context,
        started_checkpoint_guard,
        succeeded_checkpoint_guard,
        candidate_missing_handler=_record_candidate_missing,
        _selected_candidate_handler=_resume_selected_candidate,
        key_provider=key_provider,
        resume_boundary=resume_boundary,
    )
    if not isinstance(discovered, Mapping):
        raise _fail("exact_human_approval_state_unknown")
    operator_identifier_supplied = (
        operator_approval_id_supplied
        or discovered.get("operator_resume_identifiers_supplied") is True
    )
    if not selected_approval_ids:
        missing_reason = (
            missing_reasons[0]
            if len(missing_reasons) == 1
            else _RESUME_MISSING_REASON_AUTHENTICATED_CANDIDATE
        )
        public_discovered = _automatic_resume_content_free_projection(
            discovered
        )
        return {
            **public_discovered,
            "resume_discovery": {
                "schema_version": (
                    "wom-kit/exact-human-approval-resume-discovery/v0.1"
                ),
                "authenticated_candidate_count": 0,
                "exact_context_matched": False,
                "checkpoint_chain_validated_read_only": (
                    missing_reason
                    != _RESUME_MISSING_REASON_CLAIM_STORE_ABSENT
                ),
                "operator_identifiers_required": False,
                "private_folder_inspection_required": False,
                "writes_performed_by_discovery": False,
                "directories_created_by_discovery": False,
                "new_locks_created": False,
                "credential_values_echoed": False,
                "private_values_echoed": False,
                "paths_echoed": False,
            },
            "automatic_resume_discovery": True,
            "operator_resume_identifiers_supplied": (
                operator_identifier_supplied
            ),
            "native_approval_redisplayed": False,
        }
    if len(selected_approval_ids) != 1:
        raise _fail("exact_human_approval_state_unknown")
    result = _automatic_resume_content_free_projection(
        discovered,
        selected_approval_ids=tuple(selected_approval_ids),
    )
    return {
        **result,
        "resume_discovery": {
            "schema_version": (
                "wom-kit/exact-human-approval-resume-discovery/v0.1"
            ),
            "authenticated_candidate_count": 1,
            "exact_context_matched": True,
            "checkpoint_chain_validated_read_only": True,
            "operator_identifiers_required": False,
            "private_folder_inspection_required": False,
            "writes_performed_by_discovery": False,
            "directories_created_by_discovery": False,
            "new_locks_created": False,
            "credential_values_echoed": False,
            "private_values_echoed": False,
            "paths_echoed": False,
        },
        "automatic_resume_discovery": True,
        "operator_resume_identifiers_supplied": (
            operator_identifier_supplied
        ),
        "native_approval_redisplayed": False,
    }


__all__ = [
    "ExactHumanApprovalWorkflowError",
]
