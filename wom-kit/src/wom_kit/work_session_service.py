"""Bounded public management using the original work-session authorities.

App registration, human task creation, original continuation/re-review,
claiming, pause, paused-session resume, completion, handoff, acceptance and
human recovery are connected. No implicit latest selector, create preview or key injection
is exposed. Handoff does not assign responsibility for existing artifacts.
Every mutation waits once, checks the actual loaded runtime under that lock,
then calls the existing held runner. A successful registration is self-declared;
an original receipt is not proof of present claim ownership.
"""

from pathlib import Path

from . import __version__
from . import exact_human_approval_windows as native_approval
from . import project_runtime
from . import work_session_actor as actor
from . import work_session_claim as claim
from . import work_session_handoff as handoff
from . import work_session_lifecycle as lifecycle
from . import work_session_registration as registration
from . import work_session_recovery as recovery
from . import work_session_registry as registry
from . import work_session_rereview as rereview
from . import work_session_state as session_state
from .work_session_wait import WorkSessionWaitError, wait_for_archive_writer


_RUNTIME_BLOCKERS = frozenset({
    "project_runtime_unavailable", "project_runtime_mismatch",
    "project_runtime_pin_unsafe", "project_runtime_pin_invalid",
    "project_update_recovery_required",
})
_ERRORS = (frozenset({"work_session_service_invalid", "work_session_service_unavailable",
                     "work_session_wait_cancelled", "work_session_wait_root_changed"})
           | _RUNTIME_BLOCKERS | registration._ERRORS | lifecycle._ERRORS
           | claim._ERRORS | rereview._ERRORS | session_state._ERRORS | handoff._ERRORS | recovery._ERRORS)


class WorkSessionServiceError(ValueError):
    """A fixed code only; original commit and current ownership stay separate."""

    def __init__(self, code="work_session_service_invalid", *, original_commit_verified=False):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_service_invalid"
        self.original_commit_verified = original_commit_verified is True
        super().__init__(self.code)


def _safe_call(call):
    code, committed = "work_session_service_unavailable", False
    try:
        return call()
    except WorkSessionServiceError as error:
        code, committed = error.code, error.original_commit_verified
    except (registration.WorkSessionRegistrationError, lifecycle.WorkSessionLifecycleError,
            claim.WorkSessionClaimError, rereview.WorkSessionRereviewError,
            session_state.WorkSessionStateError, handoff.WorkSessionHandoffError,
            recovery.WorkSessionRecoveryError) as error:
        code = error.code if type(error.code) is str and error.code in _ERRORS else code
        committed = (isinstance(error, (claim.WorkSessionClaimError, session_state.WorkSessionStateError,
                                       handoff.WorkSessionHandoffError, recovery.WorkSessionRecoveryError))
                     and error.original_commit_verified is True)
    except WorkSessionWaitError as error:
        if error.args in (("work_session_wait_cancelled",), ("work_session_wait_root_changed",)):
            code = error.args[0]
    except registry.WorkSessionRegistryError:
        code = "work_session_service_invalid"
    except Exception:
        pass
    # Raise outside the handler: neither private arguments nor nested paths
    # survive in cause/context or an arbitrary dependency error string.
    raise WorkSessionServiceError(code, original_commit_verified=committed)


def _root(root):
    if not (type(root) is str or isinstance(root, Path)):
        raise WorkSessionServiceError()
    return registration._store(root).root


def _refs(client_app_ref, task_route_ref, work_session_ref=None, *, require_session=False):
    for value, prefix in ((client_app_ref, "client_app"), (task_route_ref, "task_route")):
        if value is None:
            raise WorkSessionServiceError("work_session_task_context_required")
        if not registry._ref(value, prefix):
            raise WorkSessionServiceError("work_session_task_context_mismatch")
    if require_session:
        if work_session_ref is None:
            raise WorkSessionServiceError("work_session_task_context_required")
        if not registry._ref(work_session_ref, "work_session"):
            raise WorkSessionServiceError("work_session_task_context_mismatch")


def _runtime_guard(root):
    observed = project_runtime.project_write_guard(
        Path(root), running_version=__version__, running_module_path=Path(__file__),
        # Observe the actually loaded CLI origin; this service's own origin
        # must not be passed off as the CLI, or replaced with a guessed path.
        running_archive_cli_module_path=None,
    )
    if type(observed) is not dict or type(observed.get("blocked")) is not bool:
        raise WorkSessionServiceError("project_runtime_unavailable")
    reason = observed.get("reason_code")
    if observed["blocked"] is True:
        raise WorkSessionServiceError(
            reason if type(reason) is str and reason in _RUNTIME_BLOCKERS else "project_runtime_unavailable",
        )
    if (type(reason) is not str
            or reason not in {"project_runtime_version_aligned", "project_runtime_pin_not_found"}
            or ("runtime_inspection_state" in observed
                and (type(observed["runtime_inspection_state"]) is not str
                     or observed["runtime_inspection_state"] not in {"passed", "not_reached"}))):
        raise WorkSessionServiceError("project_runtime_unavailable")


def _write(root, *, cancel_requested, progress, run):
    if not callable(cancel_requested) or not callable(progress):
        raise WorkSessionServiceError()
    with wait_for_archive_writer(Path(root), cancel_requested=cancel_requested, progress=progress) as held:
        held.verify_held()
        _runtime_guard(root)
        held.verify_held()
        return run(held)


def preview_registration(root, *, label):
    """Read-only original app selection; the harness must retain it first."""
    return _safe_call(lambda: registration.preview_registration(_root(root), label=registry._label(label)))


def initialize_task_request(root, *, client_app_ref):
    """Issue routing preparation only, for one explicitly registered app.

    The caller retains the returned route for this request and all original
    continuation calls. This neither creates a session nor previews a human
    decision; losing a route is not permission to select the latest task.
    """
    def run():
        if not registry._ref(client_app_ref, "client_app"):
            raise WorkSessionServiceError("work_session_service_invalid")
        store = registration._store(_root(root))
        before = store.read()
        if client_app_ref not in before._document["apps"]:
            raise WorkSessionServiceError("work_session_service_invalid")
        route = actor.new_task_route_ref()
        if not registry._ref(route, "task_route"):
            raise WorkSessionServiceError("work_session_service_unavailable")
        if store.read().sha256 != before.sha256:
            raise WorkSessionServiceError("work_session_registration_changed")
        current = registration._store(store.root)
        if (current.archive_identity_sha256 != store.archive_identity_sha256
                or current._root_identity != store._root_identity):
            raise WorkSessionServiceError("work_session_registration_changed")
        return {
            "schema": "wom-kit/work-session-task-request/v1",
            "ok": True,
            "client_app_ref": client_app_ref,
            "task_route_ref": route,
            "read_only": True,
            "routing_is_write_authority": False,
            "native_approval_required": False,
            "archive_changed": False,
        }
    return _safe_call(run)


def apply_or_resume_registration(root, *, selection, label,
                                 cancel_requested=lambda: False, progress=lambda _event: None):
    """Apply/observe this exact registration, never infer another app."""
    def run():
        selected, original_label = registration._selection(selection), registry._label(label)
        resolved = _root(root)
        store = registration._store(resolved)
        if (selected["archive_identity_sha256"] != store.archive_identity_sha256
                or selected["label_sha256"] != registry._label_digest(original_label)):
            raise WorkSessionServiceError("work_session_registration_changed")
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: registration._apply_or_resume_registration_held(
                resolved, held=held, selection=selected, label=original_label))
    return _safe_call(run)


def create_task(root, *, client_app_ref, task_route_ref, label, reviewer_claim,
                cancel_requested=lambda: False, progress=lambda _event: None):
    """Request the original native decision, not an unsupported dry-run."""
    def run():
        _refs(client_app_ref, task_route_ref)
        original_label = registry._label(label)
        if (type(reviewer_claim) is not str
                or native_approval._REVIEWER_CLAIM_RE.fullmatch(reviewer_claim) is None):
            raise WorkSessionServiceError()
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: lifecycle._create_task_held(
                resolved, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                label=original_label, reviewer_claim=reviewer_claim))
    return _safe_call(run)


def resume_task_create(root, *, client_app_ref, task_route_ref,
                       cancel_requested=lambda: False, progress=lambda _event: None):
    """Resume only the selected original operation with no new native input."""
    def run():
        _refs(client_app_ref, task_route_ref)
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: lifecycle._resume_task_create_held(
                resolved, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref))
    return _safe_call(run)


def review_original_task_create(root, *, client_app_ref, task_route_ref,
                                cancel_requested=lambda: False, progress=lambda _event: None):
    """Explicit original re-review only when the authenticated claim is absent."""
    def run():
        _refs(client_app_ref, task_route_ref)
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: rereview._review_original_session_decision_held(
                resolved, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref))
    return _safe_call(run)


def apply_or_resume_task_claim(root, *, client_app_ref, task_route_ref, work_session_ref,
                              cancel_requested=lambda: False, progress=lambda _event: None):
    """Claim or observe the original exact session; no claim token is accepted."""
    def run():
        _refs(client_app_ref, task_route_ref, work_session_ref, require_session=True)
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: claim._claim_task_held(
                resolved, held=held, client_app_ref=client_app_ref,
                task_route_ref=task_route_ref, work_session_ref=work_session_ref))
    return _safe_call(run)


def accept_task(root, *, client_app_ref, task_route_ref, predecessor_work_session_ref,
                reviewer_claim, cancel_requested=lambda: False, progress=lambda _event: None):
    """Accept an explicit predecessor into a new, caller-retained task route.

    The original held facade requires that route to be blank. Acceptance does
    not itself claim the successor or assign responsibility for old artifacts.
    """
    def run():
        _refs(client_app_ref, task_route_ref, predecessor_work_session_ref, require_session=True)
        if (type(reviewer_claim) is not str
                or native_approval._REVIEWER_CLAIM_RE.fullmatch(reviewer_claim) is None):
            raise WorkSessionServiceError()
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: lifecycle._establish_task_held(
                resolved, held=held, action="accept", client_app_ref=client_app_ref,
                task_route_ref=task_route_ref, predecessor_work_session_ref=predecessor_work_session_ref,
                reviewer_claim=reviewer_claim))
    return _safe_call(run)


def resume_task_accept(root, *, client_app_ref, task_route_ref,
                       cancel_requested=lambda: False, progress=lambda _event: None):
    """Continue only this route's original acceptance, without new selectors."""
    def run():
        _refs(client_app_ref, task_route_ref)
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: lifecycle._resume_task_establishment_held(
                resolved, held=held, action="accept", client_app_ref=client_app_ref,
                task_route_ref=task_route_ref))
    return _safe_call(run)


def review_original_task_accept(root, *, client_app_ref, task_route_ref,
                                cancel_requested=lambda: False, progress=lambda _event: None):
    """Explicit original acceptance re-review; an existing claim is resumed."""
    def run():
        _refs(client_app_ref, task_route_ref)
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: rereview._review_original_session_decision_held(
                resolved, held=held, action="accept", client_app_ref=client_app_ref,
                task_route_ref=task_route_ref))
    return _safe_call(run)


def handoff_task(root, *, client_app_ref, task_route_ref, work_session_ref,
                  target_app_ref, original_resume, reviewer_claim=None,
                  cancel_requested=lambda: False, progress=lambda _event: None):
    """Offer this exact claimed session, or resume its original handoff only."""
    def run():
        if type(original_resume) is not bool:
            raise WorkSessionServiceError()
        _refs(client_app_ref, task_route_ref, work_session_ref, require_session=True)
        if not registry._ref(target_app_ref, "client_app"):
            raise WorkSessionServiceError("work_session_task_context_mismatch")
        if original_resume:
            if reviewer_claim is not None:
                raise WorkSessionServiceError("work_session_task_context_mismatch")
        elif (type(reviewer_claim) is not str
                or native_approval._REVIEWER_CLAIM_RE.fullmatch(reviewer_claim) is None):
            raise WorkSessionServiceError()
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: handoff._handoff_task_held(
                resolved, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                work_session_ref=work_session_ref, target_app_ref=target_app_ref,
                original_resume=original_resume, reviewer_claim=reviewer_claim))
    return _safe_call(run)


def review_original_task_handoff(root, *, client_app_ref, task_route_ref, work_session_ref,
                                 target_app_ref, cancel_requested=lambda: False, progress=lambda _event: None):
    """Explicit original handoff re-review, with no replacement reviewer."""
    def run():
        _refs(client_app_ref, task_route_ref, work_session_ref, require_session=True)
        if not registry._ref(target_app_ref, "client_app"):
            raise WorkSessionServiceError("work_session_task_context_mismatch")
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: handoff._review_original_handoff_held(
                resolved, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                work_session_ref=work_session_ref, target_app_ref=target_app_ref))
    return _safe_call(run)


def recover_task(root, *, client_app_ref, task_route_ref, work_session_ref,
                  original_resume, reviewer_claim=None,
                  cancel_requested=lambda: False, progress=lambda _event: None):
    """Human recovery of one explicit same-app session, never TTL lock theft."""
    def run():
        if type(original_resume) is not bool:
            raise WorkSessionServiceError()
        _refs(client_app_ref, task_route_ref, work_session_ref, require_session=True)
        if original_resume:
            if reviewer_claim is not None:
                raise WorkSessionServiceError("work_session_task_context_mismatch")
        elif (type(reviewer_claim) is not str
                or native_approval._REVIEWER_CLAIM_RE.fullmatch(reviewer_claim) is None):
            raise WorkSessionServiceError()
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: recovery._recover_task_held(
                resolved, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                work_session_ref=work_session_ref, original_resume=original_resume, reviewer_claim=reviewer_claim))
    return _safe_call(run)


def review_original_task_recovery(root, *, client_app_ref, task_route_ref, work_session_ref,
                                  cancel_requested=lambda: False, progress=lambda _event: None):
    """Review only the original pending recovery without replacing its input."""
    def run():
        _refs(client_app_ref, task_route_ref, work_session_ref, require_session=True)
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: recovery._review_original_recovery_held(
                resolved, held=held, client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                work_session_ref=work_session_ref))
    return _safe_call(run)


def transition_task_state(root, *, action, original_resume, client_app_ref,
                          task_route_ref, work_session_ref,
                          cancel_requested=lambda: False, progress=lambda _event: None):
    """Pause/reclaim/complete a session, or continue only its original operation.

    The action named resume creates a new exact claim only with apply. The
    original_resume flag selects prior durable evidence and cannot create a
    fresh transition. Private claim tokens remain owned by the actor facade.
    """
    def run():
        if type(action) is not str or action not in {"pause", "resume", "complete"} or type(original_resume) is not bool:
            raise WorkSessionServiceError()
        _refs(client_app_ref, task_route_ref, work_session_ref, require_session=True)
        resolved = _root(root)
        return _write(resolved, cancel_requested=cancel_requested, progress=progress,
            run=lambda held: session_state._transition_task_held(
                resolved, held=held, action=action, original_resume=original_resume,
                client_app_ref=client_app_ref, task_route_ref=task_route_ref,
                work_session_ref=work_session_ref))
    return _safe_call(run)


__all__ = ["WorkSessionServiceError", "preview_registration", "initialize_task_request", "apply_or_resume_registration",
           "create_task", "resume_task_create", "review_original_task_create", "apply_or_resume_task_claim",
           "transition_task_state", "accept_task", "resume_task_accept", "review_original_task_accept",
           "handoff_task", "review_original_task_handoff", "recover_task", "review_original_task_recovery"]
