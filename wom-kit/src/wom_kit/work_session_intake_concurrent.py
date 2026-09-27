"""Owned intake with short registry publication and independent copy execution.

The retained original scope, claim MACs and current ownership remain authoritative.
A target lease cannot stand in for an archive writer lock or a human approval.
"""
from contextlib import contextmanager
from pathlib import Path
import json

from . import work_session_source_intake_workflow as legacy
from . import work_session_source_intake_bundle as bundle
from . import source_intake_batch_exact as intake
from . import exact_operation_manifest as exact
from . import exact_human_approval_workflow as broker
from . import archive_services as services
from .operation_target_leases import TargetLeases, ExecutionCheckpointStore


class Lane:
    def __init__(self, root, *, progress=None, cancel=lambda: False):
        self.root, self.progress, self.cancel = root, progress, cancel

    def heartbeat(self):
        if self.cancel():
            raise KeyboardInterrupt()

    @contextmanager
    def shared(self):
        self.heartbeat()
        with exact.exact_operation_writer_lock(self.root, timeout_seconds=30, heartbeat=self.heartbeat) as held:
            yield held

    @contextmanager
    def claim_directory(self, *, create):
        # Bind the claim directory itself across the broker, not the archive writer.
        target = self.root / legacy.approval.CLAIMS_RELATIVE_ROOT
        with services._activity_group_bound_directory_chain(self.root, target, create=create) as binding:
            yield self.root, binding


def _preimage(prepared, lane):
    plan, rows = prepared.plan, prepared.request_items()
    for item in plan.items:
        intake._revalidate_item(plan, item, request_items=rows, heartbeat=lane.heartbeat)
    if exact.verify_exact_operation(plan.manifest, verifier=intake._Verifier(plan), state="pre")["all_match"] is not True:
        raise legacy.WorkSessionIntakeWorkflowError("work_session_intake_changed")


class Writer(intake._Writer):
    def __init__(self, prepared, context, claim, lane):
        super().__init__(prepared.plan, request_items=prepared.request_items())
        self.prepared, self.context, self.claim, self.lane = prepared, context, claim, lane

    def require(self):
        self.lane.heartbeat()
        with self.lane.shared() as held:
            return legacy._require_pending_source_intake_scope_held(self.prepared,
                context=self.context, claim=self.claim, held=held)

    def write_field(self, **kwargs):
        original = kwargs.pop("heartbeat")
        original()
        self.require()
        # Source hashing and the streamed copy run without the shared writer.
        super().write_field(**kwargs, heartbeat=self.require)
        self.require()
        original()

    def _publish(self, target_ref, value, heartbeat):
        # No callback separates current actor validation from receipt publication.
        with self.lane.shared() as held:
            legacy._require_pending_source_intake_scope_held(self.prepared,
                context=self.context, claim=self.claim, held=held)
            super()._publish(target_ref, value, held.verify_held)


def run(prepared, context, claim, lane, *, resume):
    with lane.shared() as held:
        view = legacy._source_intake_operation_view(prepared, context, held)
        frozen = legacy._require_pending_source_intake_scope_held(view, context=context, claim=claim, held=held)
    plan = frozen.plan
    authority = intake._authority(plan, claim, context, allow_resume=True)
    execution = exact.exact_operation_execution_sha256(plan.manifest, approval_authority=authority)
    targets = [("execution", execution), *(("file", item.target_ref) for item in plan.manifest.items)]
    with TargetLeases(plan.archive_root, targets, heartbeat=lane.heartbeat,
            session_ref=plan.manifest.work_session_binding.work_session_ref) as leases:
        writer = Writer(frozen, context, claim, lane)
        writer.require()
        def authenticate(payload):
            writer.require()
            return intake._completion_authenticator(claim)(payload)
        core = exact.apply_exact_operation(plan.manifest, payloads=intake._Payloads(plan), writer=writer,
            verifier=intake._Verifier(plan), approval_authority=authority,
            checkpoint_store=ExecutionCheckpointStore(plan.archive_root, execution_sha256=execution,
                lease=leases.leases[("execution", execution)]),
            completion_authenticator=authenticate, resume=resume, progress_hook=lane.progress)
        writer.require()
        return intake._success_document(plan, core)


def fresh(root, request_path, *, mode, client_app_ref, task_route_ref, work_session_ref,
          reviewer_claim=None, key_provider=None, native=None, progress_hook=None,
          cancel_requested=lambda: False, stage_external=True):
    lane = Lane(root, progress=progress_hook, cancel=cancel_requested)
    args = dict(client_app_ref=client_app_ref, task_route_ref=task_route_ref,
        work_session_ref=work_session_ref, key_provider=key_provider,
        progress_hook=progress_hook, stage_external=stage_external)
    def prepare():
        planned = intake.plan_source_intake_batch(root, request_path,
            stage_external=stage_external, heartbeat=lane.heartbeat)
        with lane.shared() as held:
            return legacy._fresh(root, request_path, held=held, planned=planned, concurrent=True, **args)
    prepared, store, routing, selected = prepare()
    if mode == "preview":
        return legacy._preview_result(prepared)
    context = intake.approval_context(prepared.plan, reviewer_claim=reviewer_claim)
    results = {}

    @contextmanager
    def post_decision():
        repeated, _, _, current = prepare()
        before, after = json.loads(prepared._raw), json.loads(repeated._raw)
        ignored = {"registry_preimage_sha256", "scope_sha256"}
        scope_before = {k: v for k, v in before["scope"].items() if k not in ignored}
        scope_after = {k: v for k, v in after["scope"].items() if k not in ignored}
        if before["input"] != after["input"] or scope_before != scope_after or current._raw != selected._raw:
            raise legacy.WorkSessionIntakeWorkflowError("work_session_intake_changed")
        with lane.claim_directory(create=True) as boundary:
            yield boundary

    @contextmanager
    def publication():
        _preimage(prepared, lane)
        with lane.shared() as held:
            legacy._current(prepared, store, routing, selected, held)
            bundle._save_original_source_intake_context_held(prepared, context=context, held=held)
            legacy._current(prepared, store, routing, selected, held)
            scope, binding = prepared.scope.document(), prepared.plan.manifest.work_session_binding
            routing.save(expected_sha256=selected.sha256, held_lock=held, work_session_ref=work_session_ref,
                claim_ref=scope["claim_ref"], observed_binding=binding,
                established_origin=legacy.establishment.EstablishmentSelector.from_document(scope["original_establishment"]),
                pending_registry_intent_plan_sha256=None,
                pending_operation=legacy.actor.PendingOperationSelector.from_document(legacy._pointer(prepared, context)))
            frozen, _, _, pending = legacy._selected_scope(prepared, context, held)
            legacy._current(frozen, store, routing, pending, held)
            yield

    def finish(claim):
        with lane.shared() as held:
            results.update(legacy._finish(prepared, context, claim, held, completed=False))

    outcome = broker._execute_exact_human_approved_write_core(root, context,
        lambda claim: run(prepared, context, claim, lane, resume=False),
        native=native, key_provider=key_provider, post_decision_boundary=post_decision,
        claim_publication_boundary=publication, claim_succeeded_finalizer=finish)
    return {**results, "native_approval_redisplayed": False, "writes_performed": outcome.get("writes_performed") is True}


def resume(root, *, client_app_ref, task_route_ref, work_session_ref=None, key_provider=None,
           progress_hook=None, cancel_requested=lambda: False):
    lane = Lane(root, progress=progress_hook, cancel=cancel_requested)
    with lane.shared() as held:
        store, routing = legacy.lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise legacy.WorkSessionIntakeWorkflowError("work_session_intake_original_missing")
        doc = selected.document()
        session = doc["work_session_ref"]
        if work_session_ref is not None and session != work_session_ref:
            raise legacy.WorkSessionIntakeWorkflowError("work_session_task_context_mismatch")
        pending = selected.pending_operation()
        completed = pending is None
        pointer = pending.document() if pending else doc.get("last_completed_operation")
        if type(pointer) is not dict or pointer.get("kind") != "source_intake_batch":
            raise legacy.WorkSessionIntakeWorkflowError("work_session_intake_original_missing")
        bound = bundle._load_original_source_intake_context_held(root, manifest_sha256=pointer["manifest_sha256"], held=held)
        prepared, context = bound.prepared, bound.context
        binding = prepared.plan.manifest.work_session_binding
        if (legacy._pointer(prepared, context) != pointer or prepared.scope.document()["task_route_ref"] != task_route_ref
                or binding.client_app_ref != client_app_ref or binding.work_session_ref != session):
            raise legacy.WorkSessionIntakeWorkflowError("work_session_intake_changed")
        # Explicit legacy records keep their original execution semantics.
        if prepared.plan.manifest.operation_evidence.schema != bundle.CONCURRENT_EVIDENCE_SCHEMA:
            return legacy._resume_session_source_intake_batch_held(root, held=held, client_app_ref=client_app_ref,
                task_route_ref=task_route_ref, work_session_ref=work_session_ref,
                key_provider=key_provider, progress_hook=progress_hook)
        view = legacy._source_intake_operation_view(prepared, context, held)
    results, states = {}, {}
    def started_state(claim):
        with lane.shared() as held:
            return legacy._started_state(view, context, claim, held)
    def started_guard(claim):
        if completed:
            raise legacy.WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        started_state(claim)
        return True
    def apply(claim):
        state = started_state(claim)
        states["started_resume_state"] = state
        if state == "common_final_present":
            return {"ok": True, "writes_performed": False, "domain_writer_reentered": False}
        return run(prepared, context, claim, lane, resume=state == "checkpoint_present")
    def succeeded_guard(claim):
        with lane.shared() as held:
            intake._verify_source_intake_batch_completion_with_claim_held(prepared.plan,
                context=context, claim=claim, writer_lock=held)
        return True
    def finish(claim):
        with lane.shared() as held:
            results.update(legacy._finish(view, context, claim, held, completed=completed))
    def absent(_reason):
        raise legacy.WorkSessionIntakeWorkflowError("work_session_intake_original_approval_missing")
    outcome = broker._resume_exact_human_approved_transaction_auto_core(root, context,
        started_guard, apply, succeeded_guard, finish, key_provider=key_provider,
        candidate_missing_handler=absent, resume_boundary=lambda: lane.claim_directory(create=False))
    if states.get("started_resume_state") == "authenticated_before_first_checkpoint":
        outcome["resume_discovery"].update(checkpoint_chain_validated_read_only=False,
            authenticated_precheckpoint_preimage_verified=True)
    return {**states, **results, "resume_discovery": outcome["resume_discovery"],
        "native_approval_redisplayed": False, "automatic_resume_discovery": True,
        "writes_performed": outcome.get("writes_performed") is True}
