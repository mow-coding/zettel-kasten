"""Local recovery's retained session context, using the existing private control.

The optional control extension binds the exact unbound plan, original session
establishment, actor preimage and original native context. It is not approval
or ownership authority. No new public command, key store or approval broker is
introduced; current authority is checked separately under the caller's lock.
"""

from dataclasses import dataclass, replace
from contextlib import contextmanager
import os

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as broker
from . import exact_operation_manifest as exact
from . import local_recovery_execution as recovery
from . import local_recovery_document_images as document_images
from . import work_session_actor as actor
from . import work_session_actor_execution as actor_selection
from . import work_session_bundle as controls
from . import work_session_claim as session_claim
from . import work_session_establishment as establishment
from . import work_session_execution as session_execution
from . import work_session_lifecycle as lifecycle
from . import work_session_registry as registry
from . import work_session_source_intake_workflow as ownership
from . import work_session_source_intake_completion as evidence_readers
from . import work_session_state as session_state
from .work_session_binding import WorkSessionBinding


_SCHEMA = "wom-kit/local-recovery-session-context/v1"
_SCOPE_KEYS = frozenset({
    "task_route_ref", "actor_sha256", "registry_preimage_sha256", "claim_ref",
    "work_session_binding", "original_establishment", "establishment_execution_sha256",
    "establishment_receipt_sha256", "unbound_control_sha256", "scope_sha256",
})


def _safe(call, code="local_recovery_session_context_invalid"):
    try:
        return call()
    except recovery.LocalRecoveryError as error:
        code = error.code
    except Exception:
        pass
    raise recovery.LocalRecoveryError(code)


def _sha(value):
    return recovery._sha(recovery._canonical_bytes(value))


def _manifest(unbound, scope):
    binding = WorkSessionBinding.from_document(scope["work_session_binding"])
    evidence = unbound.operation_evidence
    counts = (("item_count", len(unbound.items)),) if evidence is None else evidence.counts
    digests = {} if evidence is None else dict(evidence.digests)
    if "session_scope_sha256" in digests:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    digests["session_scope_sha256"] = scope["scope_sha256"]
    return exact.ExactOperationManifest.build(
        operation=unbound.operation,
        archive_identity_sha256=unbound.archive_identity_sha256,
        items=unbound.items,
        operation_evidence=exact.ExactOperationEvidence(
            schema="wom-kit/local-recovery-session-evidence/v1" if evidence is None else evidence.schema,
            counts=counts, digests=tuple(sorted(digests.items())),
        ),
        work_session_binding=binding,
    )


def _decode(plan):
    if (type(plan) is not recovery.LocalRecoveryPlan
            or type(plan.session_context) is not bytes
            or not 0 < len(plan.session_context) <= recovery.MAX_CONTROL_BYTES):
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    value = controls._strict_document(plan.session_context)
    context_keys = {"schema", "scope", "unbound_manifest", "context"}
    has_images = "document_images" in value
    if set(value) != context_keys | ({"document_images"} if has_images else set()) or value["schema"] != _SCHEMA:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    scope = value["scope"]
    scope_keys = _SCOPE_KEYS | ({"document_images_sha256"} if has_images else set())
    if type(scope) is not dict or set(scope) != scope_keys:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    for name in scope_keys:
        if name.endswith("_sha256") and not registry._is_digest(scope[name]):
            raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    if (not registry._ref(scope["task_route_ref"], "task_route")
            or not registry._ref(scope["claim_ref"], "claim")
            or scope["scope_sha256"] != _sha({key: field for key, field in scope.items() if key != "scope_sha256"})):
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    WorkSessionBinding.from_document(scope["work_session_binding"])
    establishment.EstablishmentSelector.from_document(scope["original_establishment"])
    unbound = exact.ExactOperationManifest.from_document(value["unbound_manifest"])
    if unbound.work_session_binding is not None or _manifest(unbound, scope) != plan.manifest:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    if has_images:
        document_images._validate(plan, value["document_images"])
        if scope["document_images_sha256"] != _sha(value["document_images"]):
            raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    original_plan = replace(plan, manifest=unbound, session_context=None)
    if recovery._control_document(original_plan)["control_sha256"] != scope["unbound_control_sha256"]:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    supplied_context = value["context"]
    if type(supplied_context) is not dict:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    context = recovery.local_recovery_context(plan, mode="apply", reviewer_claim=supplied_context.get("reviewer_claim"))
    if controls._context_document(context) != supplied_context:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    return scope, context


def _validate_session_context(plan):
    return _safe(lambda: _decode(plan))


def _document_images(plan):
    # Only read an already validated plan. Legacy originals have no inferred
    # whole-file evidence and keep their exact historical control/context.
    if plan.session_context is None:
        return None
    return controls._strict_document(plan.session_context).get("document_images")


@dataclass(frozen=True, repr=False)
class _Scope:
    raw: bytes

    def document(self):
        return controls._strict_document(self.raw)


@dataclass(frozen=True, repr=False)
class _RecoveryView:
    plan: recovery.LocalRecoveryPlan
    scope: _Scope
    context: object
    control_bytes: bytes


def _view(plan):
    scope, context = _validate_session_context(plan)
    return _RecoveryView(plan, _Scope(recovery._canonical_bytes(scope)), context,
                         recovery._canonical_line(recovery._control_document(plan)))


def _prepare_local_recovery_session_held(root, plan_factory, *, held,
        client_app_ref, task_route_ref, work_session_ref, reviewer_claim, key_provider=None):
    """Plan with the existing actor/origin guards; no control or domain writes."""
    def prepare():
        store, routing = lifecycle._routing(root, held=held,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        binding = actor_selection._require_actor_selection_for_write_held(root, held=held,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref, work_session_ref=work_session_ref)
        origin = session_state._source_selector(store, selected, held=held,
            app=client_app_ref, session=work_session_ref)
        original = session_claim._verify_original_establishment(root, store, routing, selected,
            held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref, key_provider=key_provider, original_establishment_selector=origin)
        established = session_execution._resume_session_decision_held(root, held=held,
            manifest_sha256=origin.manifest_sha256, completed_only=True, key_provider=key_provider)
        if (established.get("ok") is not True or established.get("independent_post_verification") is not True
                or established.get("work_session_binding") != original.prepared.manifest.work_session_binding.document()):
            raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
        generation = store.read().sha256
        plan = plan_factory()
        if (type(plan) is not recovery.LocalRecoveryPlan or not plan.approveable or plan.loaded_from_control
                or plan.session_context is not None or plan.manifest.work_session_binding is not None
                or not os.path.samefile(plan.archive_root, store.root)
                or plan.manifest.archive_identity_sha256 != store.archive_identity_sha256):
            raise recovery.LocalRecoveryError("local_recovery_plan_invalid")
        images = document_images._capture_held(plan, held)
        scope = {
            "task_route_ref": task_route_ref, "actor_sha256": selected.sha256,
            "registry_preimage_sha256": generation, "claim_ref": selected.document()["claim_ref"],
            "work_session_binding": binding.document(), "original_establishment": origin.document(),
            "establishment_execution_sha256": established["execution_sha256"],
            "establishment_receipt_sha256": established["receipt_sha256"],
            "unbound_control_sha256": recovery._control_document(plan)["control_sha256"],
            "document_images_sha256": _sha(images),
        }
        scope["scope_sha256"] = _sha(scope)
        bound = replace(plan, manifest=_manifest(plan.manifest, scope))
        context = recovery.local_recovery_context(bound, mode="apply", reviewer_claim=reviewer_claim)
        prepared = replace(bound, session_context=recovery._canonical_bytes({
            "schema": _SCHEMA, "scope": scope, "unbound_manifest": plan.manifest.document(),
            "context": controls._context_document(context),
            "document_images": images,
        }))
        ownership._current(_view(prepared), store, routing, selected, held)
        return prepared
    return _safe(prepare)


def _pointer(view):
    return {"kind": "local_recovery", "manifest_sha256": view.plan.manifest.manifest_sha256,
            "context_sha256": approval.exact_human_approval_context_sha256(view.context)}


def _selected(view, held, *, completed=False):
    scope, binding = view.scope.document(), view.plan.manifest.work_session_binding
    store, routing = lifecycle._routing(view.plan.archive_root, held=held,
        client_app_ref=binding.client_app_ref, task_route_ref=scope["task_route_ref"])
    selected = routing._read(current=False)
    if selected is None:
        raise recovery.LocalRecoveryError("local_recovery_session_ownership_changed")
    document = selected.document()
    if (document["work_session_ref"] != binding.work_session_ref
            or document["observed_binding"] != binding.document() or document["claim_ref"] != scope["claim_ref"]
            or document.get("pending_registry_intent_plan_sha256") is not None
            or document.get("established_origin") != scope["original_establishment"]):
        raise recovery.LocalRecoveryError("local_recovery_session_ownership_changed")
    if completed:
        valid = selected.pending_operation() is None and document.get("last_completed_operation") == _pointer(view)
    else:
        pending = selected.pending_operation()
        valid = (pending is not None and pending.document() == _pointer(view)
                 and document["previous_sha256"] == scope["actor_sha256"])
    if not valid:
        raise recovery.LocalRecoveryError("local_recovery_session_ownership_changed")
    ownership._current(view, store, routing, selected, held)
    return store, routing, selected


def _require_pending_recovery_owner(view, *, claim, held):
    def require():
        with recovery._local_recovery_writer_lock(view.plan, held):
            _retained(view, held)
            recovery._authority(view.plan, claim, view.context, mode="apply")
            if not os.path.samefile(claim._path,
                    view.plan.archive_root / approval.CLAIMS_RELATIVE_ROOT / (claim.approval_id + ".json")):
                raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
            store, routing, selected = _selected(view, held)
            ownership._authenticate_establishment(view, store, claim, held)
            ownership._current(view, store, routing, selected, held)
            claim.assert_ready_for_context(view.context)
        return view
    return _safe(require, "local_recovery_session_ownership_changed")


def _retained(view, held):
    with recovery._local_recovery_writer_lock(view.plan, held):
        path = recovery.archive_services.archive_internal_path(view.plan.archive_root,
            recovery._control_relative(view.plan.manifest.manifest_sha256))
        if controls._read_control(path, maximum=recovery.MAX_CONTROL_BYTES) != view.control_bytes:
            raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")


def _completion(view, claim, held, *, started=False):
    """Authenticate the original field receipt; do not infer whole-file ownership."""
    plan, context = view.plan, view.context
    with recovery._local_recovery_writer_lock(plan, held):
        if type(claim) is not approval._ClaimedExactHumanApproval:
            raise recovery.LocalRecoveryError("local_recovery_approval_required")
        reference = (claim.assert_ready_for_context(context) if started
                     else claim.assert_succeeded_for_context(context))
        if not os.path.samefile(claim._path,
                plan.archive_root / approval.CLAIMS_RELATIVE_ROOT / (claim.approval_id + ".json")):
            raise recovery.LocalRecoveryError("local_recovery_approval_required")
        authority = exact.ExactOperationApprovalAuthority.from_reference(reference)
        execution = exact.exact_operation_execution_sha256(plan.manifest, approval_authority=authority)

        def authenticated():
            final = exact.load_exact_operation_final_receipt_read_only(plan.archive_root, execution,
                heartbeat=held.verify_held)
            if type(final) is not dict or type(final.get("result")) is not dict:
                raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
            result = final["result"]
            auth = result.get("completion_authentication")
            if (type(auth) is not dict or result.get("status") != "completed" or result.get("mode") != "apply"
                    or result.get("manifest_sha256") != plan.manifest.manifest_sha256
                    or result.get("execution_sha256") != execution
                    or result.get("approval_binding_sha256") != authority.binding_sha256
                    or result.get("operation_evidence") != plan.manifest.operation_evidence.document()
                    or result.get("work_session_binding_sha256") != plan.manifest.work_session_binding.binding_sha256
                    or result.get("extension_sha256") != plan.manifest.extension_sha256
                    or result.get("item_count") != len(plan.specs) or result.get("field_count") != len(plan.specs)
                    or auth.get("operation") != recovery.APPLY_OPERATION
                    or auth.get("target_binding_sha256") != plan.manifest.target_set_sha256
                    or auth.get("approval_reference") != reference
                    or not claim.exact_terminal_record_matches(reference, context.operation, context.plan_sha256,
                        context.target_binding_sha256, frozenset({"started" if started else "succeeded"}), None,
                        exact.exact_operation_completion_authentication_payload(result), auth.get("terminal_mac"))):
                raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
            return final

        final = authenticated()
        if not exact.validate_exact_operation_resume_checkpoint_read_only(plan.archive_root, plan.manifest,
                execution_sha256=execution, approval_authority=authority):
            raise recovery.LocalRecoveryError("local_recovery_resume_invalid")
        if recovery.verify_local_recovery_state(plan, state="post").get("all_match") is not True:
            raise recovery.LocalRecoveryError("local_recovery_plan_changed")
        _retained(view, held)
        if authenticated() != final:
            raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
        images = _document_images(plan)
        whole_observed = (bool(images) and document_images._matches_state_held(plan, images, state="post", held=held))
        return {"ok": True, "state": "applied", "domain": plan.domain, "manifest_sha256": plan.manifest.manifest_sha256,
                "execution_sha256": execution, "common_final_receipt_sha256": final["receipt_sha256"],
                "item_count": len(plan.specs), "field_count": len(plan.specs),
                "original_completion_verified": True, "completion_authentication_verified": True,
                "independent_verification": True, "whole_document_ownership_verified": False,
                "whole_document_transition_verified": whole_observed,
                "whole_document_count": 0 if images is None else len({row["relative_path"] for row in images}),
                "private_values_echoed": False, "paths_echoed": False}


def _finish(view, claim, held, *, completed):
    verified = _completion(view, claim, held)
    store, routing, selected = _selected(view, held, completed=completed)
    ownership._authenticate_establishment(view, store, claim, held)
    ownership._current(view, store, routing, selected, held)
    needs_index = any(spec.target_kind == "zettel" for spec in view.plan.specs)
    index_current = (not needs_index or recovery.archive_services.require_current_zettel_index(
        view.plan.archive_root).get("ok") is True)
    if not index_current:
        raise recovery.LocalRecoveryError("local_recovery_plan_blocked")
    if _completion(view, claim, held) != verified:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    ownership._current(view, store, routing, selected, held)
    if not completed:
        binding = view.plan.manifest.work_session_binding
        routing.save(expected_sha256=selected.sha256, held_lock=held,
            work_session_ref=binding.work_session_ref, claim_ref=view.scope.document()["claim_ref"],
            observed_binding=binding, pending_operation=None, pending_registry_intent_plan_sha256=None,
            last_completed_operation=actor.CompletedOperationSelector.from_document(_pointer(view)))
    return {**verified, "current_claim_ownership_verified": True,
            "index_current": needs_index and index_current, "index_rebuild_required": False,
            "actor_completion_published": not completed, "original_operation_already_completed": completed}


def _complete_original_index(view, claim, held):
    """Finish the existing exact generation after a field-final/index cut."""
    _completion(view, claim, held, started=True)
    _require_pending_recovery_owner(view, claim=claim, held=held)
    plan = view.plan
    index = recovery.ZettelIndexBatchLifecycle.inspect(plan.archive_root,
        has_zettel_targets=any(spec.target_kind == "zettel" for spec in plan.specs),
        allow_dirty_resume=True,
        operation_owner_sha256=recovery.archive_services.archive_manifest_mutation_owner_sha256(
            operation="local_recovery", operation_binding_sha256=plan.manifest.manifest_sha256))
    if index.precondition_blocked:
        return {"ok": False, "state": "applied_index_update_failed", **index.precondition_truth()}
    entries = recovery._zettel_index_entries(plan) if index.mutation_active else ()
    _require_pending_recovery_owner(view, claim=claim, held=held)
    truth = index.finalize(entries)
    _require_pending_recovery_owner(view, claim=claim, held=held)
    return {"ok": truth["index_rebuild_required"] is False, "state": "applied",
            "writes_performed": truth["generated_index_updated"], "domain_writer_reentered": False, **truth}


def _execute_session_local_recovery_held(root, plan_factory, *, held, client_app_ref,
        task_route_ref, work_session_ref, reviewer_claim, native=None, key_provider=None, progress_hook=None):
    def execute():
        options = dict(held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref, reviewer_claim=reviewer_claim, key_provider=key_provider)
        plan = _prepare_local_recovery_session_held(root, plan_factory, **options)
        view = _view(plan)
        store, routing = lifecycle._routing(root, held=held,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None or selected.sha256 != view.scope.document()["actor_sha256"]:
            raise recovery.LocalRecoveryError("local_recovery_session_ownership_changed")
        results = {}

        @contextmanager
        def post_decision():
            repeated = _prepare_local_recovery_session_held(root, plan_factory, **options)
            if recovery._control_document(repeated) != recovery._control_document(plan):
                raise recovery.LocalRecoveryError("local_recovery_plan_changed")
            with session_execution._claim_boundary(store, held, create=True) as boundary:
                yield boundary

        @contextmanager
        def publication():
            ownership._current(view, store, routing, selected, held)
            if recovery.verify_local_recovery_state(plan, state="pre").get("all_match") is not True:
                raise recovery.LocalRecoveryError("local_recovery_plan_changed")
            recovery.persist_local_recovery_control(plan)
            ownership._current(view, store, routing, selected, held)
            routing.save(expected_sha256=selected.sha256, held_lock=held,
                work_session_ref=work_session_ref, claim_ref=view.scope.document()["claim_ref"],
                observed_binding=plan.manifest.work_session_binding,
                established_origin=establishment.EstablishmentSelector.from_document(view.scope.document()["original_establishment"]),
                pending_registry_intent_plan_sha256=None,
                pending_operation=actor.PendingOperationSelector.from_document(_pointer(view)))
            _selected(view, held)
            _retained(view, held)
            yield

        outcome = broker._execute_exact_human_approved_write_core(root, view.context,
            lambda claim: recovery._execute_core(plan, claim, view.context, mode="apply", resume=False,
                progress_hook=progress_hook, writer_lock=held),
            native=native, key_provider=key_provider, post_decision_boundary=post_decision,
            claim_publication_boundary=publication,
            claim_succeeded_finalizer=lambda claim: results.update(_finish(view, claim, held, completed=False)))
        return {**outcome, **results, "native_approval_redisplayed": False}
    return _safe(execute)


def _started_state(view, claim, held):
    _require_pending_recovery_owner(view, claim=claim, held=held)
    _retained(view, held)
    authority = recovery._authority(view.plan, claim, view.context, mode="apply")
    execution = exact.exact_operation_execution_sha256(view.plan.manifest, approval_authority=authority)
    present = exact.validate_exact_operation_resume_checkpoint_read_only(view.plan.archive_root, view.plan.manifest,
        execution_sha256=execution, approval_authority=authority)
    if exact.load_exact_operation_final_receipt_read_only(view.plan.archive_root, execution) is not None:
        _completion(view, claim, held, started=True)
        return "common_final_present"
    if present:
        return "checkpoint_present"
    if recovery.verify_local_recovery_state(view.plan, state="pre").get("all_match") is not True:
        raise recovery.LocalRecoveryError("local_recovery_plan_changed")
    return "authenticated_before_first_checkpoint"


def _load_selected_original(root, *, held, client_app_ref, task_route_ref,
        work_session_ref, allowed_domains):
    store, routing = lifecycle._routing(root, held=held,
        client_app_ref=client_app_ref, task_route_ref=task_route_ref)
    selected = routing._read(current=False)
    if selected is None:
        raise recovery.LocalRecoveryError("local_recovery_resume_invalid")
    document = selected.document()
    if work_session_ref is not None and document["work_session_ref"] != work_session_ref:
        raise recovery.LocalRecoveryError("local_recovery_session_ownership_changed")
    pending = selected.pending_operation()
    completed = pending is None
    pointer = document.get("last_completed_operation") if completed else pending.document()
    if type(pointer) is not dict or pointer.get("kind") != "local_recovery":
        raise recovery.LocalRecoveryError("local_recovery_resume_invalid")
    view = _view(recovery.load_local_recovery_plan(root, manifest_sha256=pointer["manifest_sha256"]))
    if allowed_domains is not None and view.plan.domain not in allowed_domains:
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    if (_pointer(view) != pointer or view.scope.document()["task_route_ref"] != task_route_ref
            or view.plan.manifest.work_session_binding.client_app_ref != client_app_ref
            or view.plan.manifest.work_session_binding.work_session_ref != document["work_session_ref"]):
        raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
    return view, store, completed


def _resume_session_local_recovery_held(root, *, held, client_app_ref, task_route_ref,
        work_session_ref=None, key_provider=None, progress_hook=None, allowed_domains=None):
    def resume():
        view, store, completed = _load_selected_original(root, held=held,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref, allowed_domains=allowed_domains)
        results, states = {}, {}

        def started_guard(claim):
            if completed:
                raise recovery.LocalRecoveryError("local_recovery_resume_invalid")
            _started_state(view, claim, held)
            return True

        def apply(claim):
            state = _started_state(view, claim, held)
            states["started_resume_state"] = state
            if state == "common_final_present":
                return _complete_original_index(view, claim, held)
            return recovery._execute_core(view.plan, claim, view.context, mode="apply",
                resume=state == "checkpoint_present", progress_hook=progress_hook, writer_lock=held)

        def succeeded_guard(claim):
            _completion(view, claim, held)
            return True

        def missing(_reason):
            raise recovery.LocalRecoveryError("local_recovery_approval_required")

        outcome = broker._resume_exact_human_approved_transaction_auto_core(root, view.context,
            started_guard, apply, succeeded_guard,
            lambda claim: results.update(_finish(view, claim, held, completed=completed)),
            key_provider=key_provider, candidate_missing_handler=missing,
            resume_boundary=lambda: session_execution._claim_boundary(store, held, create=False))
        return {**outcome, **states, **results, "native_approval_redisplayed": False}
    return _safe(resume)


@dataclass(frozen=True, repr=False)
class _OriginEvidence:
    """Data-only inputs to the existing bounded origin/claim image readers."""
    plan: object
    store: object
    scope: object
    origin: object


def _review_original_session_local_recovery_held(root, *, held, client_app_ref,
        task_route_ref, work_session_ref=None, native=None, key_provider=None,
        progress_hook=None, allowed_domains=None):
    def review():
        view, store, completed = _load_selected_original(root, held=held,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=work_session_ref, allowed_domains=allowed_domains)
        scope, binding = view.scope.document(), view.plan.manifest.work_session_binding
        _store, _routing, selected = _selected(view, held, completed=completed)

        def current():
            _retained(view, held)
            values = _selected(view, held, completed=completed)
            if values[2]._raw != selected._raw:
                raise recovery.LocalRecoveryError("local_recovery_session_ownership_changed")
            return values

        def presence():
            current()
            absent = {"ok": False, "original_claim_absent": True}

            def missing(reason):
                if reason not in {"authenticated_candidate_missing", "claim_store_absent"}:
                    raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
                return dict(absent)

            found = broker._discover_exact_human_approved_transaction_resume_core(root, view.context,
                lambda _claim: True, lambda _claim: True, key_provider=key_provider,
                candidate_missing_handler=missing,
                resume_boundary=lambda: session_execution._claim_boundary(store, held, create=False))
            current()
            if type(found) is str:
                return "existing"
            if type(found) is dict and found == absent:
                return "absent"
            raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")

        if presence() == "existing":
            result = _resume_session_local_recovery_held(root, held=held,
                client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                work_session_ref=work_session_ref, key_provider=key_provider,
                progress_hook=progress_hook, allowed_domains=allowed_domains)
            return {**result, "original_context_preserved": True}
        if completed:
            raise recovery.LocalRecoveryError("local_recovery_approval_required")

        selector = establishment.EstablishmentSelector.from_document(scope["original_establishment"])
        origin = establishment.load_original_establishment(store, selector=selector,
            client_app_ref=client_app_ref, task_route_ref=task_route_ref,
            work_session_ref=binding.work_session_ref)
        original = _OriginEvidence(view.plan, store, view.scope, origin)

        def proof_image():
            current()
            raw = controls._read_bundle_raw(store, selector.manifest_sha256)
            final, _path, receipt, checkpoint, claim = evidence_readers._final_image(
                store.root, scope["establishment_execution_sha256"], held)
            evidence_readers._origin_evidence(original, final)
            current()
            return raw, receipt, checkpoint, claim

        def authenticate_origin():
            _store, routing, actor_state = current()
            image = proof_image()
            generation = evidence_readers._claim_generation(original, held)
            session_claim._verify_original_establishment(root, store, routing, actor_state,
                held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                work_session_ref=binding.work_session_ref, key_provider=key_provider,
                original_establishment_selector=selector)
            result = session_execution._resume_session_decision_held(root, held=held,
                manifest_sha256=selector.manifest_sha256, completed_only=True, key_provider=key_provider)
            if (result.get("ok") is not True or result.get("independent_post_verification") is not True
                    or result.get("execution_sha256") != scope["establishment_execution_sha256"]
                    or result.get("receipt_sha256") != scope["establishment_receipt_sha256"]
                    or proof_image() != image
                    or evidence_readers._claim_generation(original, held) != generation):
                raise recovery.LocalRecoveryError("local_recovery_session_context_invalid")
            current()
            return image, generation

        proof, generation = authenticate_origin()

        def unchanged():
            # No callback/provider is allowed after the final retained read.
            current()
            if (proof_image() != proof or evidence_readers._claim_generation(original, held) != generation
                    or recovery.verify_local_recovery_state(view.plan, state="pre").get("all_match") is not True):
                raise recovery.LocalRecoveryError("local_recovery_plan_changed")
            images = _document_images(view.plan)
            if images is not None and not document_images._matches_state_held(view.plan, images, state="pre", held=held):
                raise recovery.LocalRecoveryError("local_recovery_plan_changed")
            current()

        unchanged()

        @contextmanager
        def post_decision():
            if authenticate_origin() != (proof, generation) or presence() != "absent":
                raise recovery.LocalRecoveryError("local_recovery_plan_changed")
            unchanged()
            with session_execution._claim_boundary(store, held, create=True) as boundary:
                yield boundary

        @contextmanager
        def publication():
            unchanged()
            # Preserve control and actor predecessor; the broker rechecks
            # authenticated absence with the same key before publishing claim.
            yield

        def apply(claim):
            _require_pending_recovery_owner(view, claim=claim, held=held)
            if proof_image() != proof:
                raise recovery.LocalRecoveryError("local_recovery_plan_changed")
            return recovery._execute_core(view.plan, claim, view.context, mode="apply", resume=False,
                progress_hook=progress_hook, writer_lock=held)

        finished = {}
        outcome = broker._execute_exact_human_approved_original_review_core(root, view.context, apply,
            native=native, key_provider=key_provider, post_decision_boundary=post_decision,
            claim_publication_boundary=publication,
            claim_succeeded_finalizer=lambda claim: finished.update(_finish(view, claim, held, completed=False)))
        return {**outcome, **finished, "native_approval_redisplayed": True, "original_context_preserved": True}
    return _safe(review)


def _dispatch_session_local_recovery(root, *, mode, client_app_ref, task_route_ref,
        work_session_ref=None, plan_factory=None, allowed_domains, reviewer_claim=None,
        cancel_requested=lambda: False, progress=lambda _event: None):
    """Existing command adapters share the held runtime lane and safe results.

    The planner and allowed domains are supplied by a fixed internal command
    branch, never loaded from a caller's original control or plugin name.
    """
    from . import work_session_service as sessions

    started = False
    code = "local_recovery_session_context_invalid"
    try:
        if (type(mode) is not str or mode not in {"preview", "apply", "resume", "review_original"}
                or not callable(cancel_requested) or not callable(progress)
                or type(allowed_domains) not in {set, frozenset} or not allowed_domains
                or any(type(value) is not str or recovery._DOMAIN_RE.fullmatch(value) is None
                       for value in allowed_domains)):
            raise recovery.LocalRecoveryError(code)
        domains = frozenset(allowed_domains)
        original_mode = mode in {"resume", "review_original"}
        if original_mode:
            if plan_factory is not None or reviewer_claim is not None:
                raise recovery.LocalRecoveryError(code)
        elif not callable(plan_factory) or type(reviewer_claim) is not str or not reviewer_claim.strip():
            raise recovery.LocalRecoveryError(code)
        sessions._refs(client_app_ref, task_route_ref, work_session_ref, require_session=not original_mode)
        if work_session_ref is not None:
            sessions._refs(client_app_ref, task_route_ref, work_session_ref, require_session=True)
        actual = sessions._root(root)

        def checked_plan():
            plan = plan_factory()
            if type(plan) is not recovery.LocalRecoveryPlan or plan.domain not in domains:
                raise recovery.LocalRecoveryError(code)
            return plan

        def run(held):
            nonlocal started
            started = True
            common = dict(held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                          work_session_ref=work_session_ref)
            if original_mode:
                continuation = (_review_original_session_local_recovery_held if mode == "review_original"
                                else _resume_session_local_recovery_held)
                return continuation(actual, **common,
                    progress_hook=progress, allowed_domains=domains)
            if mode == "preview":
                plan = _prepare_local_recovery_session_held(actual, checked_plan, **common,
                    reviewer_claim=reviewer_claim)
                return {"ok": True, "state": "ready_for_native_approval", "domain": plan.domain,
                        "manifest_sha256": plan.manifest.manifest_sha256, "item_count": len(plan.specs),
                        "field_count": len(plan.specs), "writes_performed": False,
                        "current_claim_ownership_verified": True, "original_completion_verified": False}
            return _execute_session_local_recovery_held(actual, checked_plan, **common,
                reviewer_claim=reviewer_claim, progress_hook=progress)

        result = sessions._write(actual, cancel_requested=cancel_requested, progress=progress, run=run)
        if type(result) is not dict or type(result.get("ok")) is not bool:
            raise recovery.LocalRecoveryError(code)
        public = {"schema_version": recovery.RESULT_SCHEMA, "ok": result["ok"],
                  "dry_run": mode == "preview", "mode": "apply",
                  "private_values_echoed": False, "paths_echoed": False}
        states = {"ready_for_native_approval", "applied", "applied_index_update_failed", "not_started",
                  "partially_applied", "fully_applied_receipt_pending", "started_no_fields_changed", "requires_review"}
        state = result.get("state")
        if type(state) is not str or state not in states:
            raise recovery.LocalRecoveryError(code)
        public["state"] = state
        domain = result.get("domain")
        if domain is not None:
            if type(domain) is not str or domain not in domains:
                raise recovery.LocalRecoveryError(code)
            public["domain"] = domain
        for key in ("manifest_sha256", "execution_sha256", "common_final_receipt_sha256"):
            if key in result:
                if not registry._is_digest(result[key]):
                    raise recovery.LocalRecoveryError(code)
                public[key] = result[key]
        for key in ("item_count", "field_count", "written_field_count", "resumed_field_count",
                    "whole_document_count",
                    "applied_field_count", "remaining_field_count", "divergent_field_count",
                    "unreadable_field_count", "checkpointed_field_count", "written_before_checkpoint_field_count"):
            if key in result:
                if type(result[key]) is not int or not 0 <= result[key] <= 2**63 - 1:
                    raise recovery.LocalRecoveryError(code)
                public[key] = result[key]
        for key in ("writes_performed", "current_claim_ownership_verified", "original_completion_verified",
                    "completion_authentication_verified", "independent_verification", "whole_document_ownership_verified",
                    "whole_document_transition_verified",
                    "actor_completion_published", "original_operation_already_completed", "native_approval_redisplayed",
                    "original_context_preserved",
                    "index_current", "index_rebuild_required", "generated_index_updated", "resume_supported"):
            if key in result:
                if type(result[key]) is not bool:
                    raise recovery.LocalRecoveryError(code)
                public[key] = result[key]
        if result["ok"] and mode != "preview" and not all(public.get(key) is True for key in (
                "original_completion_verified", "completion_authentication_verified", "independent_verification")):
            raise recovery.LocalRecoveryError(code)
        if mode == "preview" or not result["ok"]:
            public["effects_state"] = "none" if mode == "preview" else "unknown"
        return public
    except KeyboardInterrupt:
        code = "work_session_wait_cancelled"
    except recovery.LocalRecoveryError as error:
        code = error.code
    except sessions.WorkSessionServiceError as error:
        code = error.code if error.code in sessions._ERRORS else code
    except sessions.WorkSessionWaitError as error:
        if error.args in (("work_session_wait_cancelled",), ("work_session_wait_root_changed",)):
            code = error.args[0]
    except Exception:
        pass
    return {"schema_version": recovery.RESULT_SCHEMA, "ok": False, "state": "blocked",
            "dry_run": mode == "preview", "reason_codes": [code],
            "effects_state": "unknown" if started and mode != "preview" else "none",
            "private_values_echoed": False, "paths_echoed": False}
