"""Private held receipt-only Git workflow, never an app-identity attestation.

Fresh review binds current task ownership and authenticated receipt producers.
Original continuation selects only the retained actor/context and claim. Public
dispatch, original re-review after a missing claim, and document provenance are
separate contracts. No Git operation changes the work-session registry.
"""

from contextlib import contextmanager
from contextvars import copy_context
from dataclasses import dataclass
import signal
import threading

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as approval_workflow
from . import exact_operation_manifest as exact
from . import git_backup_plan as planning
from . import git_backup_writer as writer
from . import work_session_actor as actor
from . import work_session_actor_execution as actor_selection
from . import work_session_bundle as session_bundle
from . import work_session_claim as session_claim
from . import work_session_establishment as establishment
from . import work_session_execution as session_execution
from . import work_session_git_anchors as anchors
from . import work_session_git_bundle as git_bundle
from . import work_session_git_provenance as provenance
from . import work_session_git_terminal as terminal
from . import work_session_lifecycle as lifecycle
from . import work_session_operation as session_operation
from . import work_session_registry as registry
from . import work_session_state as session_state
from .git_backup_session_scope import _GitBackupSessionScope
from .work_session_binding import WorkSessionBinding


_ERRORS = frozenset({
    "work_session_git_invalid", "work_session_git_changed", "work_session_git_unavailable",
    "work_session_git_original_missing", "work_session_git_original_approval_missing",
    "work_session_git_original_evidence_invalid", "work_session_git_ownership_unavailable",
    "work_session_git_signal_restore_failed",
    "work_session_task_context_required", "work_session_task_context_mismatch",
    "work_session_original_operation_pending", "work_session_lock_required",
    "exact_human_approval_cancelled", "exact_human_approval_state_unknown",
})


class WorkSessionGitWorkflowError(RuntimeError):
    def __init__(self, code="work_session_git_invalid", *, original_commit_verified=False):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_git_invalid"
        self.original_commit_verified = original_commit_verified is True
        super().__init__(self.code)


def _safe_call(call):
    code, committed = "work_session_git_unavailable", False
    try:
        return call()
    except WorkSessionGitWorkflowError as error:
        code, committed = error.code, error.original_commit_verified
    except Exception as error:
        candidate = getattr(error, "code", None)
        if type(candidate) is str and candidate in _ERRORS:
            code = candidate
        elif isinstance(error, registry.WorkSessionRegistryError) and error.args == ("work_session_lock_required",):
            code = "work_session_lock_required"
    # Do not retain callback, filesystem, claim, or private source exceptions.
    raise WorkSessionGitWorkflowError(code, original_commit_verified=committed)


def _assert_actor(routing, selected):
    current = routing._read(current=False)
    if current is None or current._raw != selected._raw:
        raise WorkSessionGitWorkflowError("work_session_git_changed")


def _progress(hook, phase):
    if hook is not None:
        hook({"phase": phase, "receipt_only": True, "private_values_echoed": False})


@dataclass(frozen=True, repr=False)
class _FreshGit:
    prepared: object
    selected: actor.ActorContext
    origin: establishment.EstablishmentSelector
    binding: WorkSessionBinding
    registry_sha256: str
    summary: dict


def _fresh(root, *, held, client_app_ref, task_route_ref, work_session_ref,
           key_provider, progress_hook, options):
    store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref,
                                        task_route_ref=task_route_ref)
    selected = routing._read(current=False)
    binding = actor_selection._require_actor_selection_for_write_held(
        root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
        work_session_ref=work_session_ref,
    )
    origin = session_state._source_selector(store, selected, held=held,
                                          app=client_app_ref, session=work_session_ref)
    original = session_claim._verify_original_establishment(
        root, store, routing, selected, held=held, client_app_ref=client_app_ref,
        task_route_ref=task_route_ref, work_session_ref=work_session_ref,
        key_provider=key_provider, original_establishment_selector=origin,
    )
    established = session_execution._resume_session_decision_held(
        root, held=held, manifest_sha256=origin.manifest_sha256,
        completed_only=True, key_provider=key_provider)
    if (established.get("ok") is not True or established.get("independent_post_verification") is not True
            or established.get("work_session_binding") != original.prepared.manifest.work_session_binding.document()):
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
    origin_proof = {"manifest_sha256": origin.manifest_sha256, "context_sha256": origin.context_sha256,
                    "execution_sha256": established["execution_sha256"],
                    "receipt_sha256": established["receipt_sha256"]}
    generation = store.read().sha256
    _progress(progress_hook, "git_receipt_snapshot")
    snapshot = provenance._capture_git_snapshot_held(root, held=held, **options)
    _progress(progress_hook, "git_receipt_provenance")
    selected_receipts = provenance._select_receipt_changes_held(
        root, held=held, snapshot=snapshot, selected_binding=binding, key_provider=key_provider,
    )
    data, summary = selected_receipts._private_document(), selected_receipts.public_summary()
    prepared = None
    if summary["selected_receipt_count"]:
        selection = data["selection"]
        scope = _GitBackupSessionScope.build(
            task_route_ref=task_route_ref, actor_sha256=selected.sha256,
            registry_preimage_sha256=generation, claim_ref=selected.document()["claim_ref"],
            work_session_binding=binding, selection_sha256=writer._sha256_json(selection),
            selected_change_count=summary["selected_receipt_count"],
            excluded_change_count=summary["excluded_change_count"], producer_proofs=data["proofs"],
            establishment_proof=origin_proof,
        )
        prepared = writer._prepare_git_backup_from_selection(
            root, expected_plan_sha256=selection["expected_plan_sha256"],
            selection=writer._GitBackupSelectionV2(writer._canonical(selection)),
            work_session_binding=binding, session_scope=scope, **options,
        )
    _assert_actor(routing, selected)
    if (store.read().sha256 != generation or actor_selection._require_actor_selection_for_write_held(
            root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref) != binding):
        raise WorkSessionGitWorkflowError("work_session_git_changed")
    return _FreshGit(prepared, selected, origin, binding, generation, summary)


def _preview_result(fresh):
    result = {**fresh.summary, "ok": True, "schema": "wom-kit/work-session-git-preview/v1",
              "current_claim_ownership_verified": True, "current_claim_authority_evaluated": True,
              "original_establishment_authenticated": True, "write_performed": False,
              "ready_for_write": fresh.prepared is not None}
    if fresh.prepared is not None:
        result.update(manifest_sha256=fresh.prepared.manifest.manifest_sha256,
                      operation_evidence=fresh.prepared.manifest.operation_evidence.document())
    return result


def _preview_session_git_backup_held(
    root, *, held, client_app_ref, task_route_ref, work_session_ref,
    remote_name="origin", branch=None, credential_mode="stored",
    max_changes=planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes=planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
    key_provider=None, progress_hook=None,
):
    options = dict(remote_name=remote_name, branch=branch, credential_mode=credential_mode,
                   max_changes=max_changes, max_changed_bytes=max_changed_bytes)
    return _safe_call(lambda: _preview_result(_fresh(
        root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
        work_session_ref=work_session_ref, key_provider=key_provider,
        progress_hook=progress_hook, options=options,
    )))


def _original_context(prepared, context, held):
    frozen = writer._freeze_validated_prepared(prepared)
    writer._require_git_backup_held_lock(frozen, held)
    if frozen.session_scope is None:
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
    bound = git_bundle._load_original_git_context_held(
        frozen.root, held=held, manifest_sha256=frozen.manifest.manifest_sha256,
    )
    if (writer._bundle_document(bound.prepared) != writer._bundle_document(frozen)
            or approval.exact_human_approval_context_sha256(bound.context)
                != approval.exact_human_approval_context_sha256(context)):
        raise WorkSessionGitWorkflowError("work_session_git_changed")
    return frozen


def _selected_scope(prepared, context, held, *, completed=False):
    frozen = _original_context(prepared, context, held)
    scope = frozen.session_scope.document()
    binding = frozen.manifest.work_session_binding
    store, routing = lifecycle._routing(frozen.root, held=held,
        client_app_ref=binding.client_app_ref, task_route_ref=scope["task_route_ref"])
    selected = routing._read(current=False)
    if selected is None:
        raise WorkSessionGitWorkflowError("work_session_git_original_missing")
    document = selected.document()
    pointer = {"kind": "git_backup", "manifest_sha256": frozen.manifest.manifest_sha256,
               "context_sha256": approval.exact_human_approval_context_sha256(context)}
    if (document["work_session_ref"] != binding.work_session_ref
            or document["observed_binding"] != binding.document()
            or document["claim_ref"] != scope["claim_ref"]
            or document.get("pending_registry_intent_plan_sha256") is not None):
        raise WorkSessionGitWorkflowError("work_session_git_changed")
    if completed:
        if selected.pending_operation() is not None or document.get("last_completed_operation") != pointer:
            raise WorkSessionGitWorkflowError("work_session_git_changed")
    elif (selected.pending_operation() is None or selected.pending_operation().document() != pointer
          or document["previous_sha256"] != scope["actor_sha256"]):
        raise WorkSessionGitWorkflowError("work_session_git_changed")
    origin = establishment.EstablishmentSelector.from_document(document.get("established_origin"))
    origin_proof = scope.get("establishment_proof")
    if (type(origin_proof) is not dict or origin_proof["manifest_sha256"] != origin.manifest_sha256
            or origin_proof["context_sha256"] != origin.context_sha256):
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
    establishment.load_original_establishment(store, selector=origin,
        client_app_ref=binding.client_app_ref, task_route_ref=scope["task_route_ref"],
        work_session_ref=binding.work_session_ref)
    _assert_actor(routing, selected)
    return frozen, store, routing, selected, origin


def _current_scope(prepared, store, routing, selected, held):
    scope, binding = prepared.session_scope.document(), prepared.manifest.work_session_binding
    if (store.read().sha256 != scope["registry_preimage_sha256"]
            or store.require_claimed_binding(client_app_ref=binding.client_app_ref,
                work_session_ref=binding.work_session_ref, claim_ref=scope["claim_ref"],
                held_lock=held, expected_binding=binding) != binding):
        raise WorkSessionGitWorkflowError("work_session_git_ownership_unavailable")
    _assert_actor(routing, selected)
    store._require_held_lock(held)


def _authenticate_proofs(prepared, store, claim, held):
    for proof in prepared.session_scope.document()["producer_proofs"]:
        original = session_bundle.load_context_bound_session_decision(
            store, manifest_sha256=proof["manifest_sha256"])
        receipt = exact.load_exact_operation_final_receipt_read_only(
            store.root, proof["execution_sha256"], heartbeat=held.verify_held)
        if receipt is None:
            raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
        raw = exact._canonical_json_bytes(receipt) + b"\n"
        result = receipt["result"]
        auth = result.get("completion_authentication")
        if type(auth) is not dict:
            raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
        authority = exact.ExactOperationApprovalAuthority.from_reference(auth["approval_reference"])
        if (receipt["receipt_sha256"] != proof["receipt_sha256"]
                or len(raw) != proof["whole_file_bytes"] or writer._sha256_bytes(raw) != proof["whole_file_sha256"]
                or original.prepared.manifest.work_session_binding.document() != proof["original_work_session_binding"]
                or original.prepared.transition.after.sha256 != proof["registry_generation_sha256"]
                or approval.exact_human_approval_context_sha256(original.context) != proof["context_sha256"]
                or result["manifest_sha256"] != proof["manifest_sha256"]
                or authority.context_sha256 != approval.exact_human_approval_context_sha256(original.context)
                or exact.exact_operation_execution_sha256(original.prepared.manifest, approval_authority=authority)
                    != proof["execution_sha256"]
                or not claim.exact_terminal_record_matches(auth["approval_reference"], original.context.operation,
                    original.context.plan_sha256, original.context.target_binding_sha256,
                    frozenset({"succeeded"}), None, exact.exact_operation_completion_authentication_payload(result),
                    auth["terminal_mac"])
                or exact.verify_exact_operation(original.prepared.manifest,
                    verifier=session_operation._Verifier(store, original.prepared), state="post")["all_match"] is not True):
            raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
        if exact.load_exact_operation_final_receipt_read_only(store.root, proof["execution_sha256"]) != receipt:
            raise WorkSessionGitWorkflowError("work_session_git_changed")


def _authenticate_establishment(prepared, store, origin, claim, held):
    proof = prepared.session_scope.document().get("establishment_proof")
    if (type(proof) is not dict or proof["manifest_sha256"] != origin.manifest_sha256
            or proof["context_sha256"] != origin.context_sha256):
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
    binding = prepared.manifest.work_session_binding
    original = establishment.load_original_establishment(store, selector=origin,
        client_app_ref=binding.client_app_ref, task_route_ref=prepared.session_scope.document()["task_route_ref"],
        work_session_ref=binding.work_session_ref)
    receipt = exact.load_exact_operation_final_receipt_read_only(store.root, proof["execution_sha256"],
                                                               heartbeat=held.verify_held)
    if receipt is None or receipt["receipt_sha256"] != proof["receipt_sha256"]:
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
    result, context = receipt["result"], original.context
    auth = result.get("completion_authentication")
    if type(auth) is not dict:
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
    authority = exact.ExactOperationApprovalAuthority.from_reference(auth["approval_reference"])
    if (result["manifest_sha256"] != origin.manifest_sha256
            or authority.context_sha256 != approval.exact_human_approval_context_sha256(context)
            or exact.exact_operation_execution_sha256(original.prepared.manifest, approval_authority=authority)
                != proof["execution_sha256"]
            or not claim.exact_terminal_record_matches(auth["approval_reference"], context.operation,
                context.plan_sha256, context.target_binding_sha256, frozenset({"succeeded"}), None,
                exact.exact_operation_completion_authentication_payload(result), auth["terminal_mac"])
            or exact.verify_exact_operation(original.prepared.manifest,
                verifier=session_operation._Verifier(store, original.prepared), state="post")["all_match"] is not True
            or exact.load_exact_operation_final_receipt_read_only(store.root, proof["execution_sha256"]) != receipt):
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")


def _require_pending_scope_held(prepared, *, context, claim, held):
    """Concrete underlying writer admission, not a caller authority assertion."""
    def verify():
        if type(claim) is not approval._ClaimedExactHumanApproval:
            raise WorkSessionGitWorkflowError()
        claim.assert_ready_for_context(context)
        frozen, store, routing, selected, origin = _selected_scope(prepared, context, held)
        _current_scope(frozen, store, routing, selected, held)
        _authenticate_establishment(frozen, store, origin, claim, held)
        _authenticate_proofs(frozen, store, claim, held)
        _current_scope(frozen, store, routing, selected, held)
        claim.assert_ready_for_context(context)
        return frozen
    return _safe_call(verify)


def _terminal_store():
    from . import work_session_git_terminal_store
    return work_session_git_terminal_store


class _SessionGitBackupWriter:
    """Recheck the concrete current scope immediately before each Git effect."""

    def __init__(self, backend, context, claim, held):
        self.backend, self.context, self.claim, self.held = backend, context, claim, held

    def write_field(self, *, target_kind, target_ref, field_ref, value, heartbeat):
        if value is None:
            raise WorkSessionGitWorkflowError("work_session_git_invalid")
        heartbeat()

        def mutation():
            _require_pending_scope_held(self.backend.prepared, context=self.context,
                                       claim=self.claim, held=self.held)
            self.backend.write(target_kind, target_ref, field_ref, value)

        # An arbitrary progress callback must not run concurrently between the
        # scope guard and Git's actual effect. Existing subprocess limits remain;
        # safe concurrent mutation-stage heartbeat publication is separate work.
        _settled_git_call(mutation)
        heartbeat()


@contextmanager
def _deferred_git_worker_signals():
    """Record console cancellation until the worker is settled, then restore.

    Python dispatches console signals on the main thread. Other caller threads
    do not install process handlers. This mirrors the existing protected worker
    start contract without importing credential workflow machinery.
    """
    originals, cancelled = [], [False]
    failed, restoration_failed, failure_code = False, False, None

    def defer(_number, _frame):
        cancelled[0] = True

    try:
        try:
            if threading.current_thread() is threading.main_thread():
                numbers = (signal.SIGINT,)
                if hasattr(signal, "SIGBREAK"):
                    numbers += (signal.SIGBREAK,)
                captured = tuple((number, signal.getsignal(number)) for number in numbers)
                for number, original in captured:
                    # Own restoration before a setter that may change then raise.
                    originals.append((number, original))
                    signal.signal(number, defer)
                    if signal.getsignal(number) is not defer:
                        raise RuntimeError("git_worker_signal_install_failed")
        except BaseException:
            failed = True
        if failed:
            raise WorkSessionGitWorkflowError("exact_human_approval_state_unknown")
        yield cancelled
    except BaseException as error:
        failure_code = (error.code if type(error) is WorkSessionGitWorkflowError
                        else "exact_human_approval_state_unknown")
    finally:
        for number, original in reversed(originals):
            restored = False
            # No worker remains here (or installation failed before launch).
            # Permanent handler failure must not hold the archive forever.
            for _attempt in range(3):
                try:
                    signal.signal(number, original)
                except BaseException:
                    pass
                try:
                    if signal.getsignal(number) is original:
                        restored = True
                        break
                except BaseException:
                    pass
            restoration_failed = restoration_failed or not restored
    if restoration_failed:
        raise WorkSessionGitWorkflowError("work_session_git_signal_restore_failed")
    if failure_code is not None:
        raise WorkSessionGitWorkflowError(failure_code)


def _settled_git_call(operation, *, wait_pulse=None):
    """Do not release the caller's lock while a Git worker can still run.

    Only read-only observations supply a progress pulse. Mutation callers never
    admit arbitrary callbacks while their guarded operation is in flight.
    """
    context, done = copy_context(), threading.Event()
    values, failures = [], []

    def run():
        try:
            values.append(context.run(operation))
        except BaseException as error:
            failures.append(error)
        finally:
            done.set()

    worker = threading.Thread(target=run, daemon=False)
    interrupted, started = False, False
    with _deferred_git_worker_signals() as cancelled:
        try:
            worker.start()
            started = True
            while not cancelled[0] and not done.wait(timeout=1.0):
                if wait_pulse is not None:
                    wait_pulse()
        except BaseException:
            interrupted = True
        finally:
            # A protected start that never launched has no event to await.
            # For launched work use its explicit event, never is_alive(): a
            # CPython join interrupted by an injected callback can alter state.
            if started or worker.ident is not None:
                while not done.is_set():
                    try:
                        worker.join(timeout=0.05)
                    except BaseException:
                        interrupted = True
                try:
                    worker.join()
                except BaseException:
                    interrupted = True
        interrupted = interrupted or cancelled[0]
    if interrupted:
        raise WorkSessionGitWorkflowError("exact_human_approval_state_unknown")
    if failures:
        raise failures[0]
    return values[0] if values else None


class _SessionGitBackupVerifier(writer._GitBackupVerifier):
    def read_field(self, *, target_kind, target_ref, field_ref, heartbeat):
        heartbeat()
        result = _settled_git_call(lambda: self.backend.read(target_kind, target_ref, field_ref),
                                   wait_pulse=heartbeat)
        heartbeat()
        return result


def _verified_terminal(prepared, context, claim, held):
    record = _terminal_store()._load_git_terminal_record_held(prepared, claim=claim, held=held)
    authenticated = terminal._authenticate_git_terminal_record_with_claim(
        prepared, context=context, record=record, claim=claim)
    payload = authenticated._record._document()["payload"]
    observed = anchors._observe_original_git_anchors_held(
        prepared, held=held, commit_oids=tuple(payload["commit_oids"]))
    if not observed.commit_anchors_verified or not observed.remote_ref_independently_verified:
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
    reread = _terminal_store()._load_git_terminal_record_held(prepared, claim=claim, held=held)
    reauthenticated = terminal._authenticate_git_terminal_record_with_claim(
        prepared, context=context, record=reread, claim=claim)
    if reauthenticated._record._raw != authenticated._record._raw:
        raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
    writer._require_git_backup_held_lock(prepared, held)
    return payload, observed


def _save_terminal(prepared, context, claim, held, commits):
    _require_pending_scope_held(prepared, context=context, claim=claim, held=held)
    record = terminal._build_git_terminal_record(prepared, context=context, claim=claim, commit_oids=commits)
    _terminal_store()._save_git_terminal_record_held(
        prepared, context=context, claim=claim, record=record, held=held)
    return _verified_terminal(prepared, context, claim, held)


def _finish(prepared, context, claim, held, *, completed):
    payload, observed = _verified_terminal(prepared, context, claim, held)
    failure = None
    try:
        frozen, store, routing, selected, _origin = _selected_scope(prepared, context, held, completed=completed)
        _current_scope(frozen, store, routing, selected, held)
        if not completed:
            selected = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=frozen.manifest.work_session_binding.work_session_ref,
                claim_ref=selected.document()["claim_ref"], observed_binding=frozen.manifest.work_session_binding,
                pending_operation=None, pending_registry_intent_plan_sha256=None,
                last_completed_operation=actor.CompletedOperationSelector.from_document({
                    "kind": "git_backup", "manifest_sha256": frozen.manifest.manifest_sha256,
                    "context_sha256": approval.exact_human_approval_context_sha256(context)}))
        _assert_actor(routing, selected)
    except WorkSessionGitWorkflowError as error:
        failure = error.code
    except Exception:
        failure = "work_session_git_ownership_unavailable"
    if failure is not None:
        # Historical authenticated Git proof survives unavailable ownership,
        # selector/CAS or readback. Do not retain a private exception chain.
        raise WorkSessionGitWorkflowError(failure, original_commit_verified=True)
    return {"ok": True, "status": "session_receipts_backed_up", "receipt_only": True,
            "backup_performed": True, "artifact_backup_complete": False,
            "document_provenance_evaluated": False, "original_commit_verified": True,
            "current_claim_ownership_verified": True, "actor_completion_published": True,
            "original_operation_already_completed": completed,
            "execution_sha256": payload["execution_sha256"],
            "common_final_receipt_sha256": payload["common_final_receipt_sha256"],
            "selected_receipt_count": frozen.session_scope.document()["selected_change_count"],
            "excluded_change_count": len(frozen.excluded_changes), "commit_count": len(frozen.groups),
            "original_git_anchors": observed.document(), "private_values_echoed": False}


def _execute_session_git_backup_held(
    root, *, held, client_app_ref, task_route_ref, work_session_ref, reviewer_claim,
    remote_name="origin", branch=None, credential_mode="stored",
    max_changes=planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes=planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
    native=None, key_provider=None, progress_hook=None,
):
    def execute():
        options = dict(remote_name=remote_name, branch=branch, credential_mode=credential_mode,
                       max_changes=max_changes, max_changed_bytes=max_changed_bytes)
        arguments = dict(held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                         work_session_ref=work_session_ref, key_provider=key_provider,
                         progress_hook=progress_hook, options=options)
        fresh = _fresh(root, **arguments)
        if fresh.prepared is None:
            return _preview_result(fresh)
        prepared = fresh.prepared
        context = writer._git_backup_approval_context(prepared, reviewer_claim=reviewer_claim)
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref,
                                            task_route_ref=task_route_ref)
        completed, boundary_failure, finish_failure = {}, [], []

        @contextmanager
        def post_decision():
            try:
                repeated = _fresh(root, **arguments)
                if (repeated.prepared is None or repeated.selected._raw != fresh.selected._raw
                        or repeated.origin != fresh.origin
                        or writer._bundle_document(repeated.prepared) != writer._bundle_document(prepared)):
                    raise WorkSessionGitWorkflowError("work_session_git_changed")
            except Exception:
                boundary_failure.append("work_session_git_changed")
                raise
            with writer._git_backup_post_decision_boundary(prepared, {}, held=held) as boundary:
                yield boundary

        @contextmanager
        def publication():
            # Key-provider entry is another callback boundary. Recheck the
            # actual claim as well as the actor/registry image before selfwrites.
            _current_scope(prepared, store, routing, fresh.selected, held)
            git_bundle._save_original_git_context_held(prepared, context=context, held=held)
            _current_scope(prepared, store, routing, fresh.selected, held)
            routing.save(expected_sha256=fresh.selected.sha256, held_lock=held,
                work_session_ref=work_session_ref, claim_ref=fresh.selected.document()["claim_ref"],
                observed_binding=fresh.binding, established_origin=fresh.origin,
                pending_registry_intent_plan_sha256=None,
                pending_operation=actor.PendingOperationSelector.from_document({
                    "kind": "git_backup", "manifest_sha256": prepared.manifest.manifest_sha256,
                    "context_sha256": approval.exact_human_approval_context_sha256(context)}))
            _frozen, _store, _routing, pending, _origin = _selected_scope(prepared, context, held)
            _current_scope(prepared, store, routing, pending, held)
            yield

        def apply(claim):
            result, backend = writer._run_git_backup_exact_operation(prepared, context=context,
                claim=claim, writer_lock=held, resume=False, progress_hook=progress_hook)
            _save_terminal(prepared, context, claim, held, tuple(backend.commit_oids))
            return {**result, "ok": result["status"] == "completed"}

        def finish(claim):
            try:
                completed.update(_finish(prepared, context, claim, held, completed=False))
            except WorkSessionGitWorkflowError as error:
                finish_failure.append((error.code, error.original_commit_verified))
                raise

        try:
            outcome = approval_workflow._execute_exact_human_approved_write_core(
                prepared.root, context, apply, native=native, key_provider=key_provider,
                post_decision_boundary=post_decision, claim_publication_boundary=publication,
                claim_succeeded_finalizer=finish)
        except Exception:
            if not boundary_failure and not finish_failure:
                raise
        if boundary_failure:
            raise WorkSessionGitWorkflowError(boundary_failure[0])
        if finish_failure:
            raise WorkSessionGitWorkflowError(finish_failure[0][0], original_commit_verified=finish_failure[0][1])
        return {**approval_workflow._automatic_resume_content_free_projection(outcome), **completed}
    return _safe_call(execute)


def _resume_session_git_backup_held(
    root, *, held, client_app_ref, task_route_ref, work_session_ref=None,
    key_provider=None, progress_hook=None,
):
    def resume():
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref,
                                            task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise WorkSessionGitWorkflowError("work_session_git_original_missing")
        document = selected.document()
        session = document["work_session_ref"]
        if work_session_ref is not None and work_session_ref != session:
            raise WorkSessionGitWorkflowError("work_session_task_context_mismatch")
        pending = selected.pending_operation()
        completed = pending is None
        pointer = pending.document() if pending is not None else document.get("last_completed_operation")
        if type(pointer) is not dict or pointer.get("kind") != "git_backup":
            raise WorkSessionGitWorkflowError("work_session_git_original_missing")
        bound = git_bundle._load_original_git_context_held(root, held=held,
                                                         manifest_sha256=pointer["manifest_sha256"])
        prepared, context = bound.prepared, bound.context
        if (approval.exact_human_approval_context_sha256(context) != pointer["context_sha256"]
                or prepared.session_scope is None
                or prepared.session_scope.document()["task_route_ref"] != task_route_ref
                or prepared.manifest.work_session_binding.client_app_ref != client_app_ref
                or prepared.manifest.work_session_binding.work_session_ref != session):
            raise WorkSessionGitWorkflowError("work_session_git_changed")
        _frozen, _store, _routing, original_selected, origin = _selected_scope(prepared, context, held,
                                                                            completed=completed)
        session_claim._verify_original_establishment(root, store, routing, original_selected,
            held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=session, key_provider=key_provider, original_establishment_selector=origin)
        result, state, missing, finish_failure = {}, {}, [], []

        def started_state(claim):
            if completed:
                raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
            _require_pending_scope_held(prepared, context=context, claim=claim, held=held)
            authority = exact.ExactOperationApprovalAuthority.from_reference(claim.assert_ready_for_context(context))
            execution_sha = exact.exact_operation_execution_sha256(prepared.manifest, approval_authority=authority)
            present = exact.validate_exact_operation_resume_checkpoint_read_only(prepared.root,
                prepared.manifest, execution_sha256=execution_sha, approval_authority=authority)
            receipt = exact.load_exact_operation_final_receipt_read_only(prepared.root, execution_sha)
            if receipt is not None:
                _authority, common, payload = terminal._common(prepared, context, claim.public_reference())
                if not claim.exact_terminal_record_matches(claim.public_reference(), context.operation,
                    context.plan_sha256, context.target_binding_sha256, frozenset({"started"}), None,
                    payload, common["result"]["completion_authentication"]["terminal_mac"]):
                    raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
                try:
                    _terminal_store()._load_git_terminal_record_held(prepared, claim=claim, held=held)
                except Exception as error:
                    if getattr(error, "code", None) != "work_session_git_terminal_store_missing":
                        raise
                else:
                    _verified_terminal(prepared, context, claim, held)
                    return "signed_terminal_present"
                return "common_final_present"
            if present:
                return "checkpoint_present"
            with writer._pinned_git_runtime(prepared):
                verified = exact.verify_exact_operation(prepared.manifest,
                    verifier=writer._GitBackupVerifier(writer._GitBackupBackend(prepared)), state="pre")
            if verified["all_match"] is not True:
                raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
            return "authenticated_before_first_checkpoint"

        def started_guard(claim):
            started_state(claim)
            return True

        def apply(claim):
            current = started_state(claim)
            state["started_resume_state"] = current
            if current == "signed_terminal_present":
                _verified_terminal(prepared, context, claim, held)
                return {"ok": True, "domain_writer_reentered": False, "signed_terminal_tail_only": True}
            if current == "common_final_present":
                # A self-created common receipt must not enter the old dirty-
                # tree verifier. Recover only the complete original HEAD prefix.
                with writer._pinned_git_runtime(prepared):
                    commits = writer._GitBackupBackend(prepared)._commit_prefix()
                if commits is None or len(commits) != len(prepared.groups):
                    raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
                observed = anchors._observe_original_git_anchors_held(prepared, held=held, commit_oids=commits)
                if not observed.commit_anchors_verified or not observed.remote_ref_independently_verified:
                    raise WorkSessionGitWorkflowError("work_session_git_original_evidence_invalid")
                _save_terminal(prepared, context, claim, held, commits)
                return {"ok": True, "domain_writer_reentered": False, "common_final_tail_only": True}
            applied, backend = writer._run_git_backup_exact_operation(prepared, context=context,
                claim=claim, writer_lock=held, resume=current == "checkpoint_present", progress_hook=progress_hook)
            _save_terminal(prepared, context, claim, held, tuple(backend.commit_oids))
            return {**applied, "ok": applied["status"] == "completed"}

        def succeeded_guard(claim):
            _verified_terminal(prepared, context, claim, held)
            return True

        def finish(claim):
            try:
                result.update(_finish(prepared, context, claim, held, completed=completed))
            except WorkSessionGitWorkflowError as error:
                finish_failure.append((error.code, error.original_commit_verified))
                raise

        def candidate_missing(_reason):
            missing.append(True)
            return {"ok": False, "status": "work_session_git_original_approval_missing"}

        try:
            outcome = approval_workflow._resume_exact_human_approved_transaction_auto_core(
                prepared.root, context, started_guard, apply, succeeded_guard, finish,
                key_provider=key_provider, candidate_missing_handler=candidate_missing,
                resume_boundary=lambda: session_execution._claim_boundary(store, held, create=False))
        except Exception:
            if not finish_failure:
                raise
        if finish_failure:
            raise WorkSessionGitWorkflowError(finish_failure[0][0], original_commit_verified=finish_failure[0][1])
        if missing:
            raise WorkSessionGitWorkflowError("work_session_git_original_approval_missing")
        if state.get("started_resume_state") == "authenticated_before_first_checkpoint":
            outcome["resume_discovery"].update(checkpoint_chain_validated_read_only=False,
                authenticated_precheckpoint_preimage_verified=True)
        return {**outcome, **state, **result}
    return _safe_call(resume)
