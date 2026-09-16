"""Private owned-session intake: exact local receipts, not artifact capture.

The retained scope is data, never authority. Every domain mutation requires
the original pending actor, current claim ownership and authenticated origin.
Original continuation selects retained context only. Missing approval remains
an auto-resume blocker; explicit original re-review uses the shared broker.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import os

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as broker
from . import exact_operation_manifest as exact
from . import source_intake_batch_exact as intake
from . import work_session_actor as actor
from . import work_session_actor_execution as actor_selection
from . import work_session_claim as session_claim
from . import work_session_establishment as establishment
from . import work_session_execution as session_execution
from . import work_session_lifecycle as lifecycle
from . import work_session_operation as session_operation
from . import work_session_registry as registry
from . import work_session_source_intake_bundle as bundle
from . import work_session_state as session_state


_ERRORS = frozenset({
    "work_session_intake_invalid", "work_session_intake_changed", "work_session_intake_unavailable",
    "work_session_intake_original_missing", "work_session_intake_original_approval_missing",
    "work_session_intake_original_evidence_invalid", "work_session_intake_ownership_unavailable",
    "work_session_intake_plan_blocked", "work_session_task_context_required",
    "work_session_task_context_mismatch", "work_session_original_operation_pending",
    "work_session_lock_required", "exact_human_approval_cancelled", "exact_human_approval_state_unknown",
})


class WorkSessionIntakeWorkflowError(RuntimeError):
    def __init__(self, code="work_session_intake_invalid", *, original_completion_verified=False):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_intake_invalid"
        self.original_completion_verified = original_completion_verified is True
        super().__init__(self.code)


def _safe_call(call):
    code, committed = "work_session_intake_unavailable", False
    try:
        return call()
    except WorkSessionIntakeWorkflowError as error:
        code, committed = error.code, error.original_completion_verified
    except Exception as error:
        candidate = getattr(error, "code", None)
        if type(candidate) is str and candidate in _ERRORS:
            code = candidate
        elif isinstance(error, registry.WorkSessionRegistryError) and error.args == ("work_session_lock_required",):
            code = "work_session_lock_required"
    raise WorkSessionIntakeWorkflowError(code, original_completion_verified=committed)


def _assert_actor(routing, selected):
    current = routing._read(current=False)
    if current is None or current._raw != selected._raw:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")


def _progress(hook, phase):
    if hook is not None:
        hook({"phase": phase, "private_values_echoed": False})


def _pointer(prepared, context):
    return {"kind": "source_intake_batch", "manifest_sha256": prepared.plan.manifest.manifest_sha256,
            "context_sha256": approval.exact_human_approval_context_sha256(context)}


@dataclass(frozen=True, repr=False)
class _IntakeOperationView:
    """Entry-validated private data; not independently admitted write authority."""
    plan: object
    scope: object
    rows: bytes
    original_raw: bytes

    def request_items(self):
        return bundle.controls._strict_document(self.rows)


def _source_intake_operation_view(prepared, context, held):
    if type(prepared) is not bundle.PreparedSessionSourceIntakeBatch:
        raise WorkSessionIntakeWorkflowError()
    # One bounded decode of this input. Repeated mutation guards compare the
    # exact retained context bytes, not N items times a full batch reconstruction.
    plan, scope, rows = bundle._decode_prepared(prepared._root, prepared._raw)
    intake._require_source_intake_batch_held_lock(plan, held)
    original = bundle._load_original_source_intake_context_held(plan.archive_root,
        manifest_sha256=plan.manifest.manifest_sha256, held=held)
    if original.prepared._raw != prepared._raw or original.context != context:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    return _IntakeOperationView(plan, scope, bundle._canonical(rows), original._raw)


def _current(prepared, store, routing, selected, held):
    scope, binding = prepared.scope.document(), prepared.plan.manifest.work_session_binding
    # The retained registry preimage is historical approval evidence. Unrelated
    # app changes do not change this session's current ownership contract.
    if (store.require_claimed_binding(client_app_ref=binding.client_app_ref,
                work_session_ref=binding.work_session_ref, claim_ref=scope["claim_ref"],
                expected_binding=binding, held_lock=held) != binding):
        raise WorkSessionIntakeWorkflowError("work_session_intake_ownership_unavailable")
    _assert_actor(routing, selected)
    store._require_held_lock(held)


def _fresh(root, request_path, *, held, client_app_ref, task_route_ref, work_session_ref,
           key_provider, progress_hook):
    store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref,
                                        task_route_ref=task_route_ref)
    selected = routing._read(current=False)
    binding = actor_selection._require_actor_selection_for_write_held(root, held=held,
        client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
    origin = session_state._source_selector(store, selected, held=held, app=client_app_ref, session=work_session_ref)
    original = session_claim._verify_original_establishment(root, store, routing, selected,
        held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
        work_session_ref=work_session_ref, key_provider=key_provider, original_establishment_selector=origin)
    established = session_execution._resume_session_decision_held(root, held=held,
        manifest_sha256=origin.manifest_sha256, completed_only=True, key_provider=key_provider)
    if (established.get("ok") is not True or established.get("independent_post_verification") is not True
            or established.get("work_session_binding") != original.prepared.manifest.work_session_binding.document()):
        raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
    generation = store.read().sha256
    _progress(progress_hook, "intake_preflight")
    def heartbeat():
        _progress(progress_hook, "intake_preflight")
        held.verify_held()
    plan = intake.plan_source_intake_batch(root, request_path, heartbeat=heartbeat)
    if not plan.approveable:
        raise WorkSessionIntakeWorkflowError("work_session_intake_plan_blocked")
    raw = intake._stable_request_bytes(plan.request_path)
    if intake._sha_bytes(raw) != plan.request_bytes_sha256:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    scope = bundle._SourceIntakeBatchSessionScope.build(plan=plan, request_bytes=raw,
        work_session_binding=binding, task_route_ref=task_route_ref, actor_sha256=selected.sha256,
        registry_preimage_sha256=generation, claim_ref=selected.document()["claim_ref"],
        original_establishment=origin, establishment_execution_sha256=established["execution_sha256"],
        establishment_receipt_sha256=established["receipt_sha256"])
    prepared = bundle._prepare_session_source_intake_batch(plan, request_bytes=raw, scope=scope)
    _current(prepared, store, routing, selected, held)
    return prepared, store, routing, selected


def _preview_result(prepared):
    plan = prepared.plan
    return {"schema": "wom-kit/work-session-source-intake-preview/v1", "ok": True, "ready_for_write": True,
            "manifest_sha256": plan.manifest.manifest_sha256,
            "operation_evidence": plan.manifest.operation_evidence.document(), "item_count": len(plan.items),
            "current_claim_ownership_verified": True, "original_establishment_authenticated": True,
            "original_completion_verified": False, "actor_completion_published": False,
            "writes_performed": False, "source_bytes_retained": False, "artifact_capture_performed": False,
            "private_values_echoed": False, "paths_echoed": False}


def _preview_session_source_intake_batch_held(root, request_path, *, held, client_app_ref, task_route_ref,
                                            work_session_ref, key_provider=None, progress_hook=None):
    return _safe_call(lambda: _preview_result(_fresh(root, request_path, held=held,
        client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref,
        key_provider=key_provider, progress_hook=progress_hook)[0]))


def _selected_scope(prepared, context, held, *, completed=False):
    frozen = (prepared if type(prepared) is _IntakeOperationView
              else _source_intake_operation_view(prepared, context, held))
    plan = frozen.plan
    intake._require_source_intake_batch_held_lock(plan, held)
    if bundle._read_raw(plan.archive_root, plan.manifest.manifest_sha256) != frozen.original_raw:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    scope, binding = frozen.scope.document(), plan.manifest.work_session_binding
    if (plan.manifest.operation_evidence.document()["digests"].get("session_scope_sha256") != scope["scope_sha256"]
            or scope["work_session_binding"] != binding.document()
            or intake.approval_context(plan, reviewer_claim=context.reviewer_claim, allow_resume=True) != context):
        raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
    store, routing = lifecycle._routing(plan.archive_root, held=held,
        client_app_ref=binding.client_app_ref, task_route_ref=scope["task_route_ref"])
    selected = routing._read(current=False)
    if selected is None:
        raise WorkSessionIntakeWorkflowError("work_session_intake_original_missing")
    document, pointer = selected.document(), _pointer(frozen, context)
    if (document["work_session_ref"] != binding.work_session_ref
            or document["observed_binding"] != binding.document() or document["claim_ref"] != scope["claim_ref"]
            or document.get("pending_registry_intent_plan_sha256") is not None
            or document.get("established_origin") != scope["original_establishment"]):
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    if completed:
        if selected.pending_operation() is not None or document.get("last_completed_operation") != pointer:
            raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    elif (selected.pending_operation() is None or selected.pending_operation().document() != pointer
            or document["previous_sha256"] != scope["actor_sha256"]):
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    _assert_actor(routing, selected)
    return frozen, store, routing, selected


def _authenticate_establishment(prepared, store, claim, held):
    scope, binding = prepared.scope.document(), prepared.plan.manifest.work_session_binding
    origin = establishment.EstablishmentSelector.from_document(scope["original_establishment"])
    original = establishment.load_original_establishment(store, selector=origin,
        client_app_ref=binding.client_app_ref, task_route_ref=scope["task_route_ref"],
        work_session_ref=binding.work_session_ref)
    receipt = exact.load_exact_operation_final_receipt_read_only(store.root,
        scope["establishment_execution_sha256"], heartbeat=held.verify_held)
    if receipt is None or receipt["receipt_sha256"] != scope["establishment_receipt_sha256"]:
        raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
    result, context = receipt["result"], original.context
    auth = result.get("completion_authentication")
    if type(auth) is not dict:
        raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
    authority = exact.ExactOperationApprovalAuthority.from_reference(auth["approval_reference"])
    if (result["mode"] != "apply" or result["manifest_sha256"] != origin.manifest_sha256
            or authority.context_sha256 != approval.exact_human_approval_context_sha256(context)
            or auth["operation"] != context.operation.value
            or auth["target_binding_sha256"] != context.target_binding_sha256
            or exact.exact_operation_execution_sha256(original.prepared.manifest, approval_authority=authority)
                != scope["establishment_execution_sha256"]
            or not claim.exact_terminal_record_matches(auth["approval_reference"], context.operation,
                context.plan_sha256, context.target_binding_sha256, frozenset({"succeeded"}), None,
                exact.exact_operation_completion_authentication_payload(result), auth["terminal_mac"])
            or exact.verify_exact_operation(original.prepared.manifest,
                verifier=session_operation._Verifier(store, original.prepared), state="post")["all_match"] is not True
            or exact.load_exact_operation_final_receipt_read_only(store.root, scope["establishment_execution_sha256"]) != receipt):
        raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")


def _require_pending_source_intake_scope_held(prepared, *, context, claim, held):
    """Concrete admission, including proof MACs with the broker's existing key."""
    def require():
        frozen, store, routing, selected = _selected_scope(prepared, context, held)
        intake._authority(frozen.plan, claim, context, allow_resume=True)
        if not os.path.samefile(claim._path,
                frozen.plan.archive_root / approval.CLAIMS_RELATIVE_ROOT / (claim.approval_id + ".json")):
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        _current(frozen, store, routing, selected, held)
        _authenticate_establishment(frozen, store, claim, held)
        _current(frozen, store, routing, selected, held)
        claim.assert_ready_for_context(context)
        return frozen
    return _safe_call(require)


def _preimage(prepared, held, progress_hook=None):
    plan, rows = prepared.plan, prepared.request_items()
    def heartbeat():
        _progress(progress_hook, "intake_revalidation")
        held.verify_held()
    for item in plan.items:
        intake._revalidate_item(plan, item, request_items=rows, heartbeat=heartbeat)
    if exact.verify_exact_operation(plan.manifest, verifier=intake._Verifier(plan), state="pre")["all_match"] is not True:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")


def _finish(prepared, context, claim, held, *, completed):
    verified = intake._verify_source_intake_batch_completion_with_claim_held(prepared.plan,
        context=context, claim=claim, writer_lock=held)
    failure = None
    try:
        frozen, store, routing, selected = _selected_scope(prepared, context, held, completed=completed)
        _authenticate_establishment(frozen, store, claim, held)
        _current(frozen, store, routing, selected, held)
        # Origin/current reads must not consume a replaced common receipt.
        if intake._verify_source_intake_batch_completion_with_claim_held(frozen.plan,
                context=context, claim=claim, writer_lock=held) != verified:
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        _current(frozen, store, routing, selected, held)
        if not completed:
            binding = frozen.plan.manifest.work_session_binding
            selected = routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=binding.work_session_ref, claim_ref=selected.document()["claim_ref"],
                observed_binding=binding, pending_operation=None, pending_registry_intent_plan_sha256=None,
                last_completed_operation=actor.CompletedOperationSelector.from_document(_pointer(frozen, context)))
        _assert_actor(routing, selected)
    except WorkSessionIntakeWorkflowError as error:
        failure = error.code
    except Exception:
        failure = "work_session_intake_ownership_unavailable"
    if failure is not None:
        raise WorkSessionIntakeWorkflowError(failure, original_completion_verified=True)
    return {**verified, "original_completion_verified": True, "current_claim_ownership_verified": True,
            "actor_completion_published": not completed, "original_operation_already_completed": completed,
            "artifact_capture_performed": False, "requires_new_capture_approval": True}


def _execute_session_source_intake_batch_held(root, request_path, *, held, client_app_ref, task_route_ref,
                                            work_session_ref, reviewer_claim, native=None, key_provider=None,
                                            progress_hook=None):
    def execute():
        args = dict(held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref, key_provider=key_provider, progress_hook=progress_hook)
        prepared, store, routing, selected = _fresh(root, request_path, **args)
        context = intake.approval_context(prepared.plan, reviewer_claim=reviewer_claim)
        results, failures = {}, []

        @contextmanager
        def post_decision():
            try:
                _progress(progress_hook, "intake_revalidation")
                repeated, _store, _routing, current = _fresh(root, request_path, **args)
                if repeated._raw != prepared._raw or current._raw != selected._raw:
                    raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
            except Exception:
                failures.append(("work_session_intake_changed", False))
                raise
            with session_execution._claim_boundary(store, held, create=True) as boundary:
                yield boundary

        @contextmanager
        def publication():
            # Provider entry is a callback too. Recheck exact source/output
            # preimage and current ownership BEFORE context or actor selfwrites.
            _preimage(prepared, held)
            _current(prepared, store, routing, selected, held)
            bundle._save_original_source_intake_context_held(prepared, context=context, held=held)
            _current(prepared, store, routing, selected, held)
            scope, binding = prepared.scope.document(), prepared.plan.manifest.work_session_binding
            routing.save(expected_sha256=selected.sha256, held_lock=held, work_session_ref=work_session_ref,
                claim_ref=scope["claim_ref"], observed_binding=binding,
                established_origin=establishment.EstablishmentSelector.from_document(scope["original_establishment"]),
                pending_registry_intent_plan_sha256=None,
                pending_operation=actor.PendingOperationSelector.from_document(_pointer(prepared, context)))
            frozen, _store, _routing, pending = _selected_scope(prepared, context, held)
            _current(frozen, store, routing, pending, held)
            yield

        def finish(claim):
            try:
                results.update(_finish(prepared, context, claim, held, completed=False))
            except WorkSessionIntakeWorkflowError as error:
                failures.append((error.code, error.original_completion_verified))
                raise

        try:
            outcome = broker._execute_exact_human_approved_write_core(root, context,
                lambda claim: intake._run_session_source_intake_batch_exact_operation(prepared,
                    context=context, claim=claim, writer_lock=held, resume=False, progress_hook=progress_hook),
                native=native, key_provider=key_provider, post_decision_boundary=post_decision,
                claim_publication_boundary=publication, claim_succeeded_finalizer=finish)
        except Exception:
            if not failures:
                raise
        if failures:
            raise WorkSessionIntakeWorkflowError(failures[0][0], original_completion_verified=failures[0][1])
        # The domain result contains historical relative receipt paths; the
        # owned public projection deliberately returns only counts and digests.
        return {**results, "native_approval_redisplayed": False,
                "writes_performed": outcome.get("writes_performed") is True}
    return _safe_call(execute)


def _started_state(prepared, context, claim, held):
    frozen = _require_pending_source_intake_scope_held(prepared, context=context, claim=claim, held=held)
    plan = frozen.plan
    authority = intake._authority(plan, claim, context, allow_resume=True)
    execution = exact.exact_operation_execution_sha256(plan.manifest, approval_authority=authority)
    present = exact.validate_exact_operation_resume_checkpoint_read_only(plan.archive_root, plan.manifest,
        execution_sha256=execution, approval_authority=authority)
    final = exact.load_exact_operation_final_receipt_read_only(plan.archive_root, execution)
    if final is not None:
        result, reference = final["result"], claim.public_reference()
        auth = result.get("completion_authentication")
        binding = plan.manifest.work_session_binding
        if (result["mode"] != "apply" or result["manifest_sha256"] != plan.manifest.manifest_sha256
                or result["execution_sha256"] != execution or result["approval_binding_sha256"] != authority.binding_sha256
                or result.get("operation_evidence") != plan.manifest.operation_evidence.document()
                or result.get("work_session_binding_sha256") != binding.binding_sha256
                or result.get("extension_sha256") != plan.manifest.extension_sha256
                or result["item_count"] != len(plan.manifest.items)
                or result["field_count"] != sum(len(item.fields) for item in plan.manifest.items)
                or type(auth) is not dict or auth["approval_reference"] != reference
                or auth["operation"] != intake.OPERATION or auth["target_binding_sha256"] != context.target_binding_sha256
                or not claim.exact_terminal_record_matches(reference, context.operation, context.plan_sha256,
                    context.target_binding_sha256, frozenset({"started"}), None,
                    exact.exact_operation_completion_authentication_payload(result), auth["terminal_mac"])
                or exact.verify_exact_operation(plan.manifest, verifier=intake._Verifier(plan), state="post")["all_match"] is not True
                or exact.load_exact_operation_final_receipt_read_only(plan.archive_root, execution) != final):
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        _require_pending_source_intake_scope_held(frozen, context=context, claim=claim, held=held)
        if exact.load_exact_operation_final_receipt_read_only(plan.archive_root, execution) != final:
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        return "common_final_present"
    if present:
        return "checkpoint_present"
    _preimage(frozen, held)
    _require_pending_source_intake_scope_held(frozen, context=context, claim=claim, held=held)
    return "authenticated_before_first_checkpoint"


def _resume_session_source_intake_batch_held(root, *, held, client_app_ref, task_route_ref,
                                           work_session_ref=None, key_provider=None, progress_hook=None):
    def resume():
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_missing")
        document = selected.document()
        session = document["work_session_ref"]
        if work_session_ref is not None and work_session_ref != session:
            raise WorkSessionIntakeWorkflowError("work_session_task_context_mismatch")
        pending = selected.pending_operation()
        completed = pending is None
        pointer = pending.document() if pending is not None else document.get("last_completed_operation")
        if type(pointer) is not dict or pointer.get("kind") != "source_intake_batch":
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_missing")
        bound = bundle._load_original_source_intake_context_held(root, manifest_sha256=pointer["manifest_sha256"], held=held)
        prepared, context = bound.prepared, bound.context
        retained = prepared
        binding = prepared.plan.manifest.work_session_binding
        if (_pointer(prepared, context) != pointer or prepared.scope.document()["task_route_ref"] != task_route_ref
                or binding.client_app_ref != client_app_ref or binding.work_session_ref != session):
            raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
        prepared = _source_intake_operation_view(prepared, context, held)
        results, states, missing, failures = {}, {}, [], []

        def started_guard(claim):
            if completed:
                raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
            _started_state(prepared, context, claim, held)
            return True

        def apply(claim):
            state = _started_state(prepared, context, claim, held)
            states["started_resume_state"] = state
            if state == "common_final_present":
                return {"ok": True, "writes_performed": False, "domain_writer_reentered": False}
            return intake._run_session_source_intake_batch_exact_operation(retained, context=context,
                claim=claim, writer_lock=held, resume=state == "checkpoint_present", progress_hook=progress_hook)

        def succeeded_guard(claim):
            intake._verify_source_intake_batch_completion_with_claim_held(prepared.plan,
                context=context, claim=claim, writer_lock=held)
            return True

        def finish(claim):
            try:
                results.update(_finish(prepared, context, claim, held, completed=completed))
            except WorkSessionIntakeWorkflowError as error:
                failures.append((error.code, error.original_completion_verified))
                raise

        def absent(_reason):
            missing.append(True)
            return {"ok": False, "status": "work_session_intake_original_approval_missing"}

        try:
            outcome = broker._resume_exact_human_approved_transaction_auto_core(root, context,
                started_guard, apply, succeeded_guard, finish, key_provider=key_provider,
                candidate_missing_handler=absent,
                resume_boundary=lambda: session_execution._claim_boundary(store, held, create=False))
        except Exception:
            if not failures:
                raise
        if failures:
            raise WorkSessionIntakeWorkflowError(failures[0][0], original_completion_verified=failures[0][1])
        if missing:
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_approval_missing")
        if states.get("started_resume_state") == "authenticated_before_first_checkpoint":
            outcome["resume_discovery"].update(checkpoint_chain_validated_read_only=False,
                authenticated_precheckpoint_preimage_verified=True)
        return {**states, **results, "resume_discovery": outcome["resume_discovery"],
                "native_approval_redisplayed": False, "automatic_resume_discovery": True,
                "writes_performed": outcome.get("writes_performed") is True}
    return _safe_call(resume)


def _review_original_session_source_intake_batch_held(root, *, held, client_app_ref, task_route_ref,
        work_session_ref=None, native=None, key_provider=None, progress_hook=None):
    from .work_session_source_intake_rereview import _IntakeFamily, _review_original_session_source_intake_held
    return _review_original_session_source_intake_held(root, family=_IntakeFamily.BATCH, held=held,
        client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref,
        native=native, key_provider=key_provider, progress_hook=progress_hook)
