"""Explicit caller task selection plus actual claimed ownership, not approval.

A valid claim for task B cannot authorize silently changing a task A request
into B. This private composition checks both the caller's explicit session and
its explicit per-task route under the one existing archive writer lock.
Historical approved-operation resume deliberately does not use this guard.
"""

from . import work_session_actor as actor
from . import work_session_execution as execution
from . import work_session_registry as registry
from .work_session_binding import WorkSessionBinding


_ERRORS = frozenset({
    "work_session_task_context_required", "work_session_task_context_mismatch",
    "work_session_task_context_changed", "work_session_original_operation_pending",
    "work_session_task_ownership_unavailable", "work_session_lock_required",
})


class WorkSessionTaskSelectionError(ValueError):
    def __init__(self, code="work_session_task_context_mismatch"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_task_context_mismatch"
        super().__init__(self.code)


def _require_actor_selection_for_write_held(
    archive_root, *, held, client_app_ref, task_route_ref, work_session_ref,
) -> WorkSessionBinding:
    """Read only; verify original caller selection and current claimed binding.

    No caller-supplied claim token, approval, new selector or latest-task
    fallback is accepted. The returned binding is an ownership prerequisite,
    never a substitute for the writer's exact manifest and human approval.
    """
    code = "work_session_task_ownership_unavailable"
    try:
        for value, prefix in ((client_app_ref, "client_app"),
                              (task_route_ref, "task_route"),
                              (work_session_ref, "work_session")):
            if value is None:
                raise WorkSessionTaskSelectionError("work_session_task_context_required")
            if not registry._ref(value, prefix):
                raise WorkSessionTaskSelectionError("work_session_task_context_mismatch")
        store, _archive_id = execution._store(archive_root)
        store._require_held_lock(held)
        routing = actor.WorkSessionActorStore(
            store, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
        )
        selected = routing.read()
        if selected is None:
            raise WorkSessionTaskSelectionError("work_session_task_context_required")
        document = selected.document()
        if (document["client_app_ref"] != client_app_ref
                or document["task_route_ref"] != task_route_ref
                or document["work_session_ref"] != work_session_ref):
            raise WorkSessionTaskSelectionError("work_session_task_context_mismatch")
        if (document["pending_manifest_sha256"] is not None
                or document.get("pending_registry_intent_plan_sha256") is not None):
            raise WorkSessionTaskSelectionError("work_session_original_operation_pending")
        binding = store.require_claimed_binding(
            client_app_ref=client_app_ref, work_session_ref=work_session_ref,
            claim_ref=document["claim_ref"], held_lock=held,
            expected_binding=WorkSessionBinding.from_document(document["observed_binding"]),
        )
        current = routing.read()
        if current is None or current.sha256 != selected.sha256:
            raise WorkSessionTaskSelectionError("work_session_task_context_changed")
        store._require_held_lock(held)
        return binding
    except WorkSessionTaskSelectionError as error:
        code = error.code
    except registry.WorkSessionRegistryError as error:
        if error.args == ("work_session_lock_required",):
            code = "work_session_lock_required"
    except Exception:
        pass
    # Do not retain private actor values or nested filesystem exceptions.
    raise WorkSessionTaskSelectionError(code)
