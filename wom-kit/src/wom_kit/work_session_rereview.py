"""Explicit native re-review of an original task cut before claim publication.

The original private bundle is never rewritten or replanned. Claim discovery
classifies presence only and returns before any new broker/key consumer starts.
A present claim always follows the existing original resume route; failed,
corrupt or ambiguous claims are never converted to absence or new approval.
"""

from contextlib import contextmanager

from . import exact_human_approval_workflow as workflow
from . import exact_operation_manifest as exact
from . import work_session_actor as actor
from . import work_session_execution as execution
from . import work_session_lifecycle as lifecycle
from . import work_session_operation as operation
from . import work_session_registry as registry


_ABSENT = {"ok": False, "original_claim_absent": True}
_ERRORS = frozenset({
    "work_session_rereview_invalid", "work_session_original_operation_changed",
    "work_session_original_operation_pending", "work_session_original_operation_missing",
    "work_session_task_context_required", "work_session_task_context_mismatch",
    "work_session_task_context_changed", "work_session_lock_required",
}) | workflow.ExactHumanApprovalWorkflowError._CODES


class WorkSessionRereviewError(ValueError):
    def __init__(self, code="work_session_rereview_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_rereview_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_rereview_invalid"
    try:
        return call()
    except (WorkSessionRereviewError, workflow.ExactHumanApprovalWorkflowError,
            lifecycle.WorkSessionLifecycleError) as error:
        if type(error.code) is str and error.code in _ERRORS:
            code = error.code
    except actor.WorkSessionActorError as error:
        if error.code == "work_session_actor_changed":
            code = "work_session_task_context_changed"
    except registry.WorkSessionRegistryError as error:
        if error.args == ("work_session_lock_required",):
            code = "work_session_lock_required"
    except Exception:
        pass
    raise WorkSessionRereviewError(code)


def _classify_original_claim_presence_held(store, prepared, context, *, held, key_provider=None):
    """Return absent/existing, not checkpoint validity or approval authority."""
    def classify():
        store._require_held_lock(held)
        execution._reload(store, prepared, context)

        def missing(reason):
            if reason not in {"authenticated_candidate_missing", "claim_store_absent"}:
                raise WorkSessionRereviewError()
            # This may run inside the existing provider consumer. It MUST NOT
            # invoke a broker, store, native UI, new key consumer or any writer.
            return dict(_ABSENT)

        found = workflow._discover_exact_human_approved_transaction_resume_core(
            store.root, context, lambda _claim: True, lambda _claim: True,
            candidate_missing_handler=missing, key_provider=key_provider,
            resume_boundary=lambda: execution._claim_boundary(store, held, create=False),
        )
        store._require_held_lock(held)
        execution._reload(store, prepared, context)
        if type(found) is str:
            # The authenticated scanner owns validation of this private ID.
            # Never return it, retain it as authority or echo it in diagnostics.
            return "existing"
        if type(found) is dict and found == _ABSENT:
            return "absent"
        raise WorkSessionRereviewError()
    return _safe_call(classify)


def _review_original_session_decision_held(root, *, held, client_app_ref, task_route_ref,
                                          native=None, key_provider=None, action="create"):
    """Explicitly re-review the pending original create/accept, under one lock.

    No new reviewer, label, work/session reference, manifest or approval ID is
    accepted. The facade's caller explicitly chose re-review; absence alone
    never calls this function or grants approval automatically.
    """
    def run():
        if type(action) is not str or action not in {"create", "accept"}:
            raise WorkSessionRereviewError()
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref)
        selected = routing.read()
        if selected is None:
            raise WorkSessionRereviewError("work_session_original_operation_missing")
        document = selected.document()
        if document.get("pending_registry_intent_plan_sha256") is not None:
            raise WorkSessionRereviewError("work_session_original_operation_pending")
        pending = document["pending_manifest_sha256"] is not None
        pointer = ({"manifest_sha256": document["pending_manifest_sha256"],
                    "context_sha256": document["pending_context_sha256"]} if pending
                   else document.get("last_completed_operation"))
        if pointer is None or (not pending and pointer["kind"] != "human_session_decision"):
            raise WorkSessionRereviewError("work_session_original_operation_missing")
        bound = lifecycle._bound_establishment(store, action=action, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                                         manifest_sha256=pointer["manifest_sha256"], context_sha256=pointer["context_sha256"])
        prepared, context = bound.prepared, bound.context
        if document["work_session_ref"] not in {None, prepared.manifest.work_session_binding.work_session_ref}:
            raise WorkSessionRereviewError("work_session_task_context_mismatch")
        if (document.get("established_origin") is not None
                and document["established_origin"] != lifecycle._origin(bound).document()):
            raise WorkSessionRereviewError("work_session_original_operation_changed")
        lifecycle._assert_actor(routing, selected)
        presence = _classify_original_claim_presence_held(store, prepared, context, held=held, key_provider=key_provider)
        if presence == "existing":
            result = lifecycle._resume_task_establishment_held(root, held=held, action=action, client_app_ref=client_app_ref,
                                                        task_route_ref=task_route_ref, key_provider=key_provider)
            return {**result, "native_approval_redisplayed": False}
        if not pending:
            raise WorkSessionRereviewError("work_session_original_operation_changed")

        def unchanged_preimage():
            store._require_held_lock(held)
            lifecycle._assert_actor(routing, selected)
            execution._reload(store, prepared, context)
            if (store.read().sha256 != prepared.transition.before_sha256
                    or exact.verify_exact_operation(prepared.manifest, verifier=operation._Verifier(store, prepared),
                                                     state="pre")["all_match"] is not True):
                raise WorkSessionRereviewError("work_session_original_operation_changed")
            store._require_held_lock(held)

        unchanged_preimage()
        terminal = {}
        boundary_failure = None

        def verify_boundary():
            nonlocal boundary_failure
            try:
                unchanged_preimage()
            except BaseException:
                boundary_failure = "work_session_original_operation_changed"
                raise

        @contextmanager
        def post_decision():
            nonlocal boundary_failure
            # Discovery has fully left its key consumer before this new broker
            # is called. Re-scan here, before its write key consumer begins.
            verify_boundary()
            try:
                if _classify_original_claim_presence_held(store, prepared, context, held=held, key_provider=key_provider) != "absent":
                    raise WorkSessionRereviewError("work_session_original_operation_changed")
            except BaseException:
                boundary_failure = "work_session_original_operation_changed"
                raise
            with execution._claim_boundary(store, held, create=True) as filesystem_boundary:
                verify_boundary()
                yield filesystem_boundary

        @contextmanager
        def publication():
            # No nested key consumer here. This only revalidates the original
            # retained selection/bundle/preimage before the existing claim write.
            verify_boundary()
            yield

        def observe_target_binding():
            unchanged_preimage()
            return prepared.manifest.target_set_sha256

        def writer(claim):
            execution._reload(store, prepared, context)
            return operation.apply_session_decision_with_claim(store, prepared, context=context, claim=claim, held_lock=held)

        def finish(claim):
            terminal.update(execution._verified_terminal(store, prepared, context, claim))

        try:
            outcome = workflow._execute_exact_human_approved_write_core(
                store.root, context, writer, native=native, key_provider=key_provider,
                post_decision_boundary=post_decision, claim_publication_boundary=publication,
                claim_succeeded_finalizer=finish, target_collection=execution._local_preview(prepared),
                observe_target_binding=observe_target_binding,
            )
        except BaseException:
            if boundary_failure is None:
                raise
        if boundary_failure is not None:
            # Avoid misclassifying a domain/selector drift as key failure, and
            # discard any private cause captured by an inner callback.
            raise WorkSessionRereviewError(boundary_failure)
        result = execution._result(prepared, outcome, terminal)
        result = lifecycle._finish_establishment(store, routing, selected, held=held, bound=bound, result=result)
        return {**result, "native_approval_redisplayed": True}
    return _safe_call(run)
