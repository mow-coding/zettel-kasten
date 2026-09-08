"""Explicit original intake review; retained data is never write authority.

The closed family selects existing codecs, guards and runners. A new native
decision is available only for an unchanged pending original with genuinely
absent approval. Existing claims always return to their original auto-resume.
"""

from contextlib import contextmanager

from . import exact_human_approval_workflow as broker
from . import exact_operation_manifest as exact
from . import work_session_claim as session_claim
from . import work_session_establishment as establishment
from . import work_session_execution as execution
from . import work_session_lifecycle as lifecycle
from . import work_session_operation as operation
from . import work_session_source_intake_completion as historical
from . import work_session_source_intake_workflow as common


_IntakeFamily = historical._IntakeFamily


def _workflow(family):
    if family is _IntakeFamily.BATCH:
        return common
    if family is _IntakeFamily.RECORD:
        from . import work_session_source_intake_record_workflow as record
        return record
    raise common.WorkSessionIntakeWorkflowError()


def _selected(original, view, workflow, routing, selected, held, *, completed=False):
    historical._require_original(original, held)
    _view, store, _routing, current = workflow._selected_scope(view, original.context, held, completed=completed)
    if current._raw != selected._raw:
        raise common.WorkSessionIntakeWorkflowError("work_session_intake_changed")
    common._assert_actor(routing, selected)
    return store


def _presence(original, view, workflow, routing, selected, held, key_provider, *, completed):
    """Use authenticated status presence, never filesystem/checkpoint absence."""
    store = _selected(original, view, workflow, routing, selected, held, completed=completed)
    absent = {"ok": False, "original_claim_absent": True}

    def missing(reason):
        if reason not in {"authenticated_candidate_missing", "claim_store_absent"}:
            raise common.WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        return dict(absent)  # Runs inside discovery: no second provider/broker.

    failed = False
    try:
        found = broker._discover_exact_human_approved_transaction_resume_core(
            original.plan.archive_root, original.context, lambda _claim: True, lambda _claim: True,
            candidate_missing_handler=missing, key_provider=key_provider,
            resume_boundary=lambda: execution._claim_boundary(store, held, create=False))
    except Exception:
        failed = True
    if failed:
        raise common.WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
    _selected(original, view, workflow, routing, selected, held, completed=completed)
    if type(found) is str:
        return "existing"
    if type(found) is dict and found == absent:
        return "absent"
    raise common.WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")


def _proof_image(original, held):
    """Existing strict data readers, not a second completion or claim parser."""
    historical._require_original(original, held)
    scope = original.scope.document()
    final, _path, raw, checkpoint, claim_raw = historical._final_image(
        original.plan.archive_root, scope["establishment_execution_sha256"], held)
    historical._origin_evidence(original, final)
    if exact.verify_exact_operation(original.origin.prepared.manifest,
            verifier=operation._Verifier(original.store, original.origin.prepared), state="post",
            heartbeat=held.verify_held)["all_match"] is not True:
        raise common.WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
    historical._require_original(original, held)
    return original.raw, original.origin_raw, raw, checkpoint, claim_raw


def _authenticate_origin(original, view, workflow, routing, selected, held, key_provider):
    store = _selected(original, view, workflow, routing, selected, held)
    common._current(view, store, routing, selected, held)
    image, generation = _proof_image(original, held), historical._claim_generation(original, held)
    scope, binding = original.scope.document(), original.plan.manifest.work_session_binding
    origin = establishment.EstablishmentSelector.from_document(scope["original_establishment"])
    session_claim._verify_original_establishment(original.plan.archive_root, store, routing, selected,
        held=held, client_app_ref=binding.client_app_ref, task_route_ref=scope["task_route_ref"],
        work_session_ref=binding.work_session_ref, key_provider=key_provider,
        original_establishment_selector=origin)
    result = execution._resume_session_decision_held(original.plan.archive_root, held=held,
        manifest_sha256=origin.manifest_sha256, completed_only=True, key_provider=key_provider)
    if (result.get("ok") is not True or result.get("independent_post_verification") is not True
            or result.get("execution_sha256") != scope["establishment_execution_sha256"]
            or result.get("receipt_sha256") != scope["establishment_receipt_sha256"]
            or _proof_image(original, held) != image
            or historical._claim_generation(original, held) != generation):
        raise common.WorkSessionIntakeWorkflowError("work_session_intake_changed")
    _selected(original, view, workflow, routing, selected, held)
    common._current(view, store, routing, selected, held)
    return image, generation


def _review_original_session_source_intake_held(root, *, family, held, client_app_ref, task_route_ref,
        work_session_ref=None, native=None, key_provider=None, progress_hook=None):
    def review():
        workflow = _workflow(family)
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing._read(current=False)
        if selected is None:
            raise common.WorkSessionIntakeWorkflowError("work_session_intake_original_missing")
        document, pending = selected.document(), selected.pending_operation()
        if work_session_ref is not None and work_session_ref != document["work_session_ref"]:
            raise common.WorkSessionIntakeWorkflowError("work_session_task_context_mismatch")
        pointer = pending.document() if pending is not None else document.get("last_completed_operation")
        kind = "source_intake_batch" if family is _IntakeFamily.BATCH else "source_intake_record"
        if type(pointer) is not dict or pointer.get("kind") != kind:
            raise common.WorkSessionIntakeWorkflowError("work_session_intake_original_missing")
        original = historical._original(root, held, pointer["manifest_sha256"], pointer["context_sha256"], family=family)
        binding = original.plan.manifest.work_session_binding
        if (binding.client_app_ref != client_app_ref or binding.work_session_ref != document["work_session_ref"]
                or original.scope.document()["task_route_ref"] != task_route_ref):
            raise common.WorkSessionIntakeWorkflowError("work_session_intake_changed")
        if family is _IntakeFamily.BATCH:
            view = workflow._source_intake_operation_view(original.prepared, original.context, held)
        else:
            view = workflow._source_intake_record_operation_view(original.prepared, original.context, held)
        if _presence(original, view, workflow, routing, selected, held, key_provider, completed=pending is None) == "existing":
            resume = (workflow._resume_session_source_intake_batch_held if family is _IntakeFamily.BATCH
                      else workflow._resume_session_source_intake_record_held)
            result = resume(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                work_session_ref=document["work_session_ref"], key_provider=key_provider, progress_hook=progress_hook)
            return {**result, "native_approval_redisplayed": False, "original_context_preserved": True}
        if pending is None:
            raise common.WorkSessionIntakeWorkflowError("work_session_intake_original_evidence_invalid")
        proof, generation = _authenticate_origin(original, view, workflow, routing, selected, held, key_provider)
        finished, failures = {}, []

        def unchanged():
            # An arbitrary notification runs before the final source read,
            # never after its last hash in this protected preimage interval.
            common._progress(progress_hook, "intake_revalidation")
            _selected(original, view, workflow, routing, selected, held)
            common._current(view, store, routing, selected, held)
            if (_proof_image(original, held) != proof
                    or historical._claim_generation(original, held) != generation):
                raise common.WorkSessionIntakeWorkflowError("work_session_intake_changed")
            if family is _IntakeFamily.BATCH:
                workflow._preimage(view, held)  # Retained rows; actual source identities and bytes.
            else:
                workflow._preimage(view, held, require_input=False)  # Metadata only; no caller JSON/source read.
            _selected(original, view, workflow, routing, selected, held)
            common._current(view, store, routing, selected, held)
            if (_proof_image(original, held) != proof
                    or historical._claim_generation(original, held) != generation):
                raise common.WorkSessionIntakeWorkflowError("work_session_intake_changed")

        unchanged()

        @contextmanager
        def post_decision():
            try:
                if (_authenticate_origin(original, view, workflow, routing, selected, held, key_provider) != (proof, generation)
                        or _presence(original, view, workflow, routing, selected, held, key_provider, completed=False) != "absent"):
                    raise common.WorkSessionIntakeWorkflowError("work_session_intake_changed")
                unchanged()
            except Exception:
                failures.append(("work_session_intake_changed", False))
                raise
            with execution._claim_boundary(store, held, create=True) as boundary:
                yield boundary

        @contextmanager
        def publication():
            try:
                unchanged()  # Same active provider; all readers here are data-only.
            except Exception:
                failures.append(("work_session_intake_changed", False))
                raise
            # No context save or pending CAS: that would change the original
            # actor predecessor. The common broker scans absence with this key
            # immediately after this guard, before creating the one-use claim.
            yield

        def apply(claim):
            require = (workflow._require_pending_source_intake_scope_held if family is _IntakeFamily.BATCH
                       else workflow._require_pending_source_intake_record_scope_held)
            require(view, context=original.context, claim=claim, held=held)
            if _proof_image(original, held) != proof:
                raise common.WorkSessionIntakeWorkflowError("work_session_intake_changed")
            # The new intake claim legitimately changes the full generation.
            # Retain exact old origin images plus active-claim MAC/current guards.
            if family is _IntakeFamily.BATCH:
                from . import source_intake_batch_exact as runner
                return runner._run_session_source_intake_batch_exact_operation(original.prepared,
                    context=original.context, claim=claim, writer_lock=held, resume=False, progress_hook=progress_hook)
            from . import work_session_source_intake_record_execution as runner
            return runner._run_session_source_intake_record_exact_operation(original.prepared,
                context=original.context, claim=claim, writer_lock=held, resume=False, progress_hook=progress_hook)

        def finish(claim):
            try:
                finished.update(workflow._finish(view, original.context, claim, held, completed=False))
            except common.WorkSessionIntakeWorkflowError as error:
                failures.append((error.code, error.original_completion_verified))
                raise

        try:
            outcome = broker._execute_exact_human_approved_original_review_core(root, original.context, apply,
                native=native, key_provider=key_provider, post_decision_boundary=post_decision,
                claim_publication_boundary=publication, claim_succeeded_finalizer=finish)
        except Exception:
            if not failures:
                raise
        if failures:
            raise common.WorkSessionIntakeWorkflowError(failures[0][0], original_completion_verified=failures[0][1])
        return {**broker._automatic_resume_content_free_projection(outcome), **finished,
                "native_approval_redisplayed": True, "original_context_preserved": True,
                "writes_performed": outcome.get("writes_performed") is True}
    return common._safe_call(review)
