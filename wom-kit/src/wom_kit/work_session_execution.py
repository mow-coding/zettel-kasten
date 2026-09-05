"""Session decision orchestration using the existing native broker and runner.

This is the internal vertical slice for public routing. It does not discover an
app installation, infer a current claimant, or expose native/key injection as a
CLI/MCP option. A private prepared payload remains data, never approval. Resume
recovers the original context and asks the existing authenticated claim router
to distinguish started work from completed, output-lost work.
"""

from contextlib import contextmanager
import hmac
from pathlib import Path
from typing import Any, Callable

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as workflow
from . import exact_operation_manifest as exact
from . import work_session_bundle as bundle
from . import work_session_operation as operation
from . import work_session_registry as registry
from .work_session_wait import wait_for_archive_writer
from .target_collection_preview import TargetCollectionItem, TargetCollectionPreview


class WorkSessionExecutionError(RuntimeError):
    def __init__(self, code="work_session_execution_invalid"):
        self.code = code if code in {
            "work_session_execution_invalid", "work_session_execution_changed",
            "work_session_resume_evidence_invalid",
        } else "work_session_execution_invalid"
        super().__init__(self.code)


def _store(archive_root):
    root, archive_id = approval._archive_identity(archive_root)
    return registry.WorkSessionRegistryStore(
        root, approval.exact_human_approval_archive_identity_sha256(archive_id),
    ), archive_id


def _reload(store, prepared, context):
    restored = bundle.load_context_bound_session_decision(
        store, manifest_sha256=prepared.manifest.manifest_sha256,
    )
    if (restored.prepared != prepared or not hmac.compare_digest(
            approval.exact_human_approval_context_sha256(restored.context),
            approval.exact_human_approval_context_sha256(context))):
        raise WorkSessionExecutionError("work_session_execution_changed")


@contextmanager
def _claim_boundary(store, held, *, create):
    # Retain the common claim directory for authenticated discovery/publication;
    # the writer lock is already held BEFORE planning or native human review.
    from .archive_services import _activity_group_bound_directory_chain

    held.verify_held()
    target = store.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts)
    with _activity_group_bound_directory_chain(store.root, target, create=create) as binding:
        yield store.root, binding
    held.verify_held()


def _execution_authority(prepared, context, claim):
    reference = (claim.assert_ready_for_context(context) if claim.status == "started"
                 else claim.assert_succeeded_for_context(context))
    authority = exact.ExactOperationApprovalAuthority.from_reference(reference)
    return authority, exact.exact_operation_execution_sha256(
        prepared.manifest, approval_authority=authority,
    )


def _verified_terminal(store, prepared, context, claim):
    """A real terminal receipt, matching claim MAC and independent target read."""
    _reload(store, prepared, context)
    authority, execution_sha = _execution_authority(prepared, context, claim)
    receipt = exact.load_exact_operation_final_receipt_read_only(store.root, execution_sha)
    if receipt is None:
        raise WorkSessionExecutionError("work_session_resume_evidence_invalid")
    result = receipt["result"]
    authentication = result.get("completion_authentication")
    if (result.get("manifest_sha256") != prepared.manifest.manifest_sha256
            or not isinstance(authentication, dict)
            or authentication.get("approval_reference") != claim.public_reference()
            or exact.ExactOperationApprovalAuthority.from_reference(
                authentication["approval_reference"]) != authority):
        raise WorkSessionExecutionError("work_session_resume_evidence_invalid")
    payload = exact.exact_operation_completion_authentication_payload(result)
    expected_mac = authentication.get("terminal_mac")
    if (type(expected_mac) is not str or not hmac.compare_digest(
            claim.exact_terminal_record_mac(payload), expected_mac)):
        raise WorkSessionExecutionError("work_session_resume_evidence_invalid")
    verified = exact.verify_exact_operation(
        prepared.manifest, verifier=operation._Verifier(store, prepared), state="post",
    )
    if verified["all_match"] is not True:
        raise WorkSessionExecutionError("work_session_resume_evidence_invalid")
    return {
        "execution_sha256": execution_sha, "receipt_sha256": receipt["receipt_sha256"],
        "result_sha256": result["result_sha256"], "independent_post_verification": True,
    }


def _started_state(store, prepared, context, claim):
    """Distinguish real checkpoints from the reachable pre-checkpoint cut.

Missing checkpoints are not success evidence. An authenticated started claim
may begin its original exact runner only while its immutable target is absent,
the exact predecessor is still current and no final receipt exists. This emits
the first real checkpoint; it does not fabricate or repair historical evidence.
"""
    _reload(store, prepared, context)
    authority, execution_sha = _execution_authority(prepared, context, claim)
    present = exact.validate_exact_operation_resume_checkpoint_read_only(
        store.root, prepared.manifest, execution_sha256=execution_sha,
        approval_authority=authority,
    )
    if present:
        # Validate a terminal record now if it already exists. A malformed
        # published result must never be passed to another mutation attempt.
        if exact.load_exact_operation_final_receipt_read_only(store.root, execution_sha) is not None:
            _verified_terminal(store, prepared, context, claim)
        return "checkpoint_present"
    if (exact.load_exact_operation_final_receipt_read_only(store.root, execution_sha) is not None
            or store.read().sha256 != prepared.transition.before_sha256
            or exact.verify_exact_operation(prepared.manifest,
                verifier=operation._Verifier(store, prepared), state="pre")["all_match"] is not True):
        raise WorkSessionExecutionError("work_session_resume_evidence_invalid")
    return "authenticated_before_first_checkpoint"


def _result(prepared, outcome, terminal):
    return {
        **outcome, **terminal, "lifecycle_action": "work_session_" + prepared.transition.action,
        "work_session_binding": prepared.manifest.work_session_binding.document(),
        "registry_generation_sha256": prepared.transition.after.sha256,
        "result_refs": list(prepared.transition.result_refs), "private_labels_echoed": False,
    }


def _local_preview(prepared):
    """Show only labels from the already-bound private generation in memory."""
    document = prepared.transition.after._document
    binding = prepared.manifest.work_session_binding.document()
    session = document["sessions"][binding["work_session_ref"]]
    refs = [("workstream", session["workstream_ref"]), ("client_app", session["client_app_ref"])]
    if session["handoff_app_ref"] is not None:
        refs.append(("client_app", session["handoff_app_ref"]))
    return TargetCollectionPreview(items=tuple(
        TargetCollectionItem(
            identity_sha256=registry._digest({"archive": prepared.manifest.archive_identity_sha256,
                                             "kind": kind, "ref": ref}),
            kind=kind,
            title=document["workstreams" if kind == "workstream" else "apps"][ref]["label"],
        ) for kind, ref in refs
    ))


def _execute_session_decision_core(
    archive_root, *, action, client_app_ref, reviewer_claim,
    work_session_ref=None, label=None, claim_ref=None, target_app_ref=None,
    cancel_requested: Callable[[], bool] = lambda: False,
    progress: Callable[[dict], None] = lambda _value: None,
    native=None, key_provider=None,
) -> dict[str, Any]:
    """Only internal tests substitute the native input and secure key seams."""
    with wait_for_archive_writer(Path(archive_root), cancel_requested=cancel_requested,
                                 progress=progress) as held:
        store, archive_id = _store(archive_root)
        transition = registry.plan_transition(
            store.read(), action=action, client_app_ref=client_app_ref,
            work_session_ref=work_session_ref, label=label,
            claim_ref=claim_ref, target_app_ref=target_app_ref,
        )
        prepared = operation.prepare_session_decision(transition)
        context = prepared.context(archive_id=archive_id, reviewer_claim=reviewer_claim)
        terminal = {}

        def observe_target_binding():
            held.verify_held()
            prepared.validate()
            if store.read().sha256 != prepared.transition.before_sha256:
                raise WorkSessionExecutionError("work_session_execution_changed")
            return prepared.manifest.target_set_sha256

        @contextmanager
        def publication():
            held.verify_held()
            if store.read().sha256 != prepared.transition.before_sha256:
                raise WorkSessionExecutionError("work_session_execution_changed")
            bundle.save_context_bound_session_decision(store, prepared, context=context, held_lock=held)
            yield

        def writer(claim):
            _reload(store, prepared, context)
            return operation.apply_session_decision_with_claim(
                store, prepared, context=context, claim=claim, held_lock=held,
            )

        def finish(claim):
            terminal.update(_verified_terminal(store, prepared, context, claim))

        outcome = workflow._execute_exact_human_approved_write_core(
            store.root, context, writer, native=native, key_provider=key_provider,
            post_decision_boundary=lambda: _claim_boundary(store, held, create=True),
            claim_publication_boundary=publication, claim_succeeded_finalizer=finish,
            target_collection=_local_preview(prepared), observe_target_binding=observe_target_binding,
        )
        return _result(prepared, outcome, terminal)


def _resume_session_decision_core(
    archive_root, *, manifest_sha256,
    cancel_requested: Callable[[], bool] = lambda: False,
    progress: Callable[[dict], None] = lambda _value: None,
    key_provider=None,
) -> dict[str, Any]:
    """No approval identifier, new reviewer, new context or native dialog.

The manifest is an internal private-payload selector, not an authorization.
Public task-scoped payload discovery remains the caller's responsibility.
"""
    with wait_for_archive_writer(Path(archive_root), cancel_requested=cancel_requested,
                                 progress=progress) as held:
        store, _archive_id = _store(archive_root)
        bound = bundle.load_context_bound_session_decision(store, manifest_sha256=manifest_sha256)
        prepared, context = bound.prepared, bound.context
        terminal, resume_state = {}, {}

        def started_guard(claim):
            _started_state(store, prepared, context, claim)
            return True

        def writer(claim):
            state = _started_state(store, prepared, context, claim)
            resume_state["started_resume_state"] = state
            return operation.apply_session_decision_with_claim(
                store, prepared, context=context, claim=claim, held_lock=held,
                resume=state == "checkpoint_present",
            )

        def succeeded_guard(claim):
            _verified_terminal(store, prepared, context, claim)
            return True

        def finish(claim):
            terminal.update(_verified_terminal(store, prepared, context, claim))

        outcome = workflow._resume_exact_human_approved_transaction_auto_core(
            store.root, context, started_guard, writer, succeeded_guard, finish,
            key_provider=key_provider,
            resume_boundary=lambda: _claim_boundary(store, held, create=False),
        )
        if resume_state.get("started_resume_state") == "authenticated_before_first_checkpoint":
            # The shared historical router assumes every admitted candidate
            # already had a checkpoint. This reachable cut has no chain yet;
            # report its different, actual evidence without changing authority.
            outcome = {**outcome, "resume_discovery": {
                **outcome.get("resume_discovery", {}),
                "checkpoint_chain_validated_read_only": False,
                "authenticated_precheckpoint_preimage_verified": True,
            }}
        return _result(prepared, {**outcome, **resume_state}, terminal)
