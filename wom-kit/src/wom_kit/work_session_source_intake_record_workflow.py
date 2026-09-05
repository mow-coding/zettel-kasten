"""Owned single metadata receipt, preserving the original exact approval.

This composes the existing session ownership checks, claim broker and exact
engine. It neither captures source bytes nor manufactures a batch request.
Missing approval is a blocker, not permission to prompt during auto-resume.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import os

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as broker
from . import exact_operation_manifest as exact
from . import source_intake_record_exact as intake
from . import work_session_actor as actor
from . import work_session_actor_execution as actor_selection
from . import work_session_claim as session_claim
from . import work_session_establishment as establishment
from . import work_session_execution as session_execution
from . import work_session_lifecycle as lifecycle
from . import work_session_source_intake_record_bundle as bundle
from . import work_session_source_intake_record_execution as domain
from . import work_session_source_intake_workflow as common
from . import work_session_state as session_state


# Reuse the closed intake error/progress and concrete ownership/origin checks.
# These helpers authenticate session facts, not batch-specific payloads.
WorkSessionIntakeWorkflowError = common.WorkSessionIntakeWorkflowError
_ERRORS = common._ERRORS
_safe_call = common._safe_call
_progress = common._progress
_current = common._current
_assert_actor = common._assert_actor
_authenticate_establishment = common._authenticate_establishment


def _pointer(prepared, context):
    return {"kind": "source_intake_record", "manifest_sha256": prepared.plan.manifest.manifest_sha256,
            "context_sha256": approval.exact_human_approval_context_sha256(context)}


@dataclass(frozen=True, repr=False)
class _RecordOperationView:
    """Entry-validated private data; the held guard still checks authority."""
    plan: object
    scope: object
    input_plan_bytes: bytes
    original_raw: bytes


def _source_intake_record_operation_view(prepared, context, held):
    if type(prepared) is not bundle.PreparedSessionSourceIntakeRecord:
        raise WorkSessionIntakeWorkflowError()
    plan, scope, raw = bundle._decode_prepared(prepared._root, prepared._raw)
    domain._require_source_intake_record_held_lock(plan, held)
    original = bundle._load_original_source_intake_record_context_held(plan.archive_root,
        manifest_sha256=plan.manifest.manifest_sha256, held=held)
    if original.prepared._raw != prepared._raw or original.context != context:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    return _RecordOperationView(plan, scope, raw, original._raw)


def _fresh(root, plan_path, *, held, client_app_ref, task_route_ref, work_session_ref,
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
    plan = intake.plan_source_intake_record(root, plan_path)
    if not plan.approveable:
        raise WorkSessionIntakeWorkflowError("work_session_intake_plan_blocked")
    raw = intake._stable_regular_bytes(plan.input_plan_path, maximum=intake._MAX_PLAN_BYTES)
    if intake._sha_bytes(raw) != plan.input_plan_bytes_sha256:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    scope = bundle._SourceIntakeRecordSessionScope.build(plan=plan, input_plan_bytes=raw,
        work_session_binding=binding, task_route_ref=task_route_ref, actor_sha256=selected.sha256,
        registry_preimage_sha256=generation, claim_ref=selected.document()["claim_ref"],
        original_establishment=origin, establishment_execution_sha256=established["execution_sha256"],
        establishment_receipt_sha256=established["receipt_sha256"])
    prepared = bundle._prepare_session_source_intake_record(plan, input_plan_bytes=raw, scope=scope)
    _current(prepared, store, routing, selected, held)
    return prepared, store, routing, selected


def _preview_session_source_intake_record_held(root, plan_path, *, held, client_app_ref, task_route_ref,
                                             work_session_ref, key_provider=None, progress_hook=None):
    def preview():
        prepared = _fresh(root, plan_path, held=held, client_app_ref=client_app_ref,
            task_route_ref=task_route_ref, work_session_ref=work_session_ref,
            key_provider=key_provider, progress_hook=progress_hook)[0]
        return {"schema": "wom-kit/work-session-source-intake-record-preview/v1", "ok": True,
                "ready_for_write": True, "manifest_sha256": prepared.plan.manifest.manifest_sha256,
                "item_count": 1, "current_claim_ownership_verified": True,
                "original_establishment_authenticated": True, "original_completion_verified": False,
                "actor_completion_published": False, "writes_performed": False,
                "source_bytes_retained": False, "artifact_capture_performed": False,
                "prepared_capture_request_created": False, "private_values_echoed": False, "paths_echoed": False}
    return _safe_call(preview)


def _selected_scope(prepared, context, held, *, completed=False):
    frozen = (prepared if type(prepared) is _RecordOperationView
              else _source_intake_record_operation_view(prepared, context, held))
    plan = frozen.plan
    domain._require_source_intake_record_held_lock(plan, held)
    if bundle._read_raw(plan.archive_root, plan.manifest.manifest_sha256) != frozen.original_raw:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    scope, binding = frozen.scope.document(), plan.manifest.work_session_binding
    if (plan.manifest.operation_evidence.document()["digests"].get("session_scope_sha256") != scope["scope_sha256"]
            or scope["work_session_binding"] != binding.document()
            or intake.approval_context(plan, reviewer_claim=context.reviewer_claim) != context):
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


def _require_pending_source_intake_record_scope_held(prepared, *, context, claim, held):
    def require():
        frozen, store, routing, selected = _selected_scope(prepared, context, held)
        intake._authority(frozen.plan, claim, context)
        if not os.path.samefile(claim._path,
                frozen.plan.archive_root / approval.CLAIMS_RELATIVE_ROOT / (claim.approval_id + ".json")):
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        _current(frozen, store, routing, selected, held)
        _authenticate_establishment(frozen, store, claim, held)
        _current(frozen, store, routing, selected, held)
        claim.assert_ready_for_context(context)
        return frozen
    return _safe_call(require)


def _preimage(prepared, held, *, require_input=False):
    if type(prepared) is bundle.PreparedSessionSourceIntakeRecord:
        plan, _scope, raw = bundle._decode_prepared(prepared._root, prepared._raw)
    elif type(prepared) is _RecordOperationView:
        plan, raw = prepared.plan, prepared.input_plan_bytes
    else:
        raise WorkSessionIntakeWorkflowError()
    domain._require_source_intake_record_held_lock(plan, held)
    if require_input and intake._stable_regular_bytes(plan.input_plan_path, maximum=intake._MAX_PLAN_BYTES) != raw:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
    if exact.verify_exact_operation(plan.manifest, verifier=domain._Verifier(plan), state="pre")["all_match"] is not True:
        raise WorkSessionIntakeWorkflowError("work_session_intake_changed")


def _finish(prepared, context, claim, held, *, completed):
    verified = domain._verify_source_intake_record_completion_with_claim_held(prepared.plan,
        context=context, claim=claim, writer_lock=held)
    failure = None
    try:
        frozen, store, routing, selected = _selected_scope(prepared, context, held, completed=completed)
        _authenticate_establishment(frozen, store, claim, held)
        _current(frozen, store, routing, selected, held)
        if domain._verify_source_intake_record_completion_with_claim_held(frozen.plan,
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
            "artifact_capture_performed": False, "prepared_capture_request_created": False,
            "source_bytes_retained": False, "requires_new_capture_approval": True}


def _execute_session_source_intake_record_held(root, plan_path, *, held, client_app_ref, task_route_ref,
                                             work_session_ref, reviewer_claim, native=None, key_provider=None,
                                             progress_hook=None):
    def execute():
        args = dict(held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref, key_provider=key_provider, progress_hook=progress_hook)
        prepared, store, routing, selected = _fresh(root, plan_path, **args)
        context = intake.approval_context(prepared.plan, reviewer_claim=reviewer_claim)
        results, failures = {}, []

        @contextmanager
        def post_decision():
            try:
                _progress(progress_hook, "intake_revalidation")
                repeated, _store, _routing, current = _fresh(root, plan_path, **args)
                if repeated._raw != prepared._raw or current._raw != selected._raw:
                    raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
            except Exception:
                failures.append(("work_session_intake_changed", False))
                raise
            with session_execution._claim_boundary(store, held, create=True) as boundary:
                yield boundary

        @contextmanager
        def publication():
            _preimage(prepared, held, require_input=True)
            _current(prepared, store, routing, selected, held)
            bundle._save_original_source_intake_record_context_held(prepared, context=context, held=held)
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
                lambda claim: domain._run_session_source_intake_record_exact_operation(prepared,
                    context=context, claim=claim, writer_lock=held, resume=False, progress_hook=progress_hook),
                native=native, key_provider=key_provider, post_decision_boundary=post_decision,
                claim_publication_boundary=publication, claim_succeeded_finalizer=finish)
        except Exception:
            if not failures:
                raise
        if failures:
            raise WorkSessionIntakeWorkflowError(failures[0][0], original_completion_verified=failures[0][1])
        return {**results, "native_approval_redisplayed": False,
                "writes_performed": outcome.get("writes_performed") is True}
    return _safe_call(execute)


def _started_state(prepared, context, claim, held):
    frozen = _require_pending_source_intake_record_scope_held(prepared, context=context, claim=claim, held=held)
    plan = frozen.plan
    authority = intake._authority(plan, claim, context)
    execution = exact.exact_operation_execution_sha256(plan.manifest, approval_authority=authority)
    present = exact.validate_exact_operation_resume_checkpoint_read_only(plan.archive_root, plan.manifest,
        execution_sha256=execution, approval_authority=authority)
    final = exact.load_exact_operation_final_receipt_read_only(plan.archive_root, execution)
    if final is not None:
        reference = claim.public_reference()
        _authority, auth, payload = domain._source_intake_record_completion_evidence_view(plan,
            context=context, reference=reference, execution=execution, final=final)
        if (not claim.exact_terminal_record_matches(reference, context.operation, context.plan_sha256,
                context.target_binding_sha256, frozenset({"started"}), None, payload, auth["terminal_mac"])
                or exact.verify_exact_operation(plan.manifest, verifier=domain._Verifier(plan), state="post")["all_match"] is not True
                or exact.load_exact_operation_final_receipt_read_only(plan.archive_root, execution) != final):
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        _require_pending_source_intake_record_scope_held(frozen, context=context, claim=claim, held=held)
        if exact.load_exact_operation_final_receipt_read_only(plan.archive_root, execution) != final:
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        return "common_final_present"
    if present:
        return "checkpoint_present"
    _preimage(frozen, held)
    _require_pending_source_intake_record_scope_held(frozen, context=context, claim=claim, held=held)
    return "authenticated_before_first_checkpoint"


def _resume_session_source_intake_record_held(root, *, held, client_app_ref, task_route_ref,
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
        if type(pointer) is not dict or pointer.get("kind") != "source_intake_record":
            raise WorkSessionIntakeWorkflowError("work_session_intake_original_missing")
        bound = bundle._load_original_source_intake_record_context_held(root, manifest_sha256=pointer["manifest_sha256"], held=held)
        retained, context = bound.prepared, bound.context
        binding = retained.plan.manifest.work_session_binding
        if (_pointer(retained, context) != pointer or retained.scope.document()["task_route_ref"] != task_route_ref
                or binding.client_app_ref != client_app_ref or binding.work_session_ref != session):
            raise WorkSessionIntakeWorkflowError("work_session_intake_changed")
        prepared = _source_intake_record_operation_view(retained, context, held)
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
            return domain._run_session_source_intake_record_exact_operation(retained, context=context,
                claim=claim, writer_lock=held, resume=state == "checkpoint_present", progress_hook=progress_hook)

        def succeeded_guard(claim):
            domain._verify_source_intake_record_completion_with_claim_held(prepared.plan,
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
