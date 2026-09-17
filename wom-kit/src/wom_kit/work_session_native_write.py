"""Session ownership for native single writers (v0.4.23, LR-06a).

A native writer that receives session references (``create-draft`` first)
binds its exact approval plan to one content-free scope digest and attributes
its receipt to the claimed session. Every check runs under the caller's held
archive writer lane; this module opens no dialog, writes no receipt and never
substitutes for the writer's own plan digest and human approval.

Fresh writes only: an original resume or review keeps the writer's own
one-use claim semantics, and the ordinary sessionless route is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from . import work_session_actor as actor
from . import work_session_actor_execution as actor_selection
from . import work_session_lifecycle as lifecycle
from .work_session_binding import WorkSessionBinding

SCOPE_SCHEMA = "wom-kit/work-session-native-write-scope/v1"
NATIVE_WRITE_KINDS = frozenset({"create_draft"})
_ERRORS = frozenset({
    "work_session_native_write_invalid",
    "work_session_native_write_changed",
    "work_session_native_write_pending_missing",
    "work_session_task_context_required",
    "work_session_task_context_mismatch",
    "work_session_task_context_changed",
    "work_session_task_ownership_unavailable",
    "work_session_original_operation_pending",
    "work_session_lock_required",
})


class WorkSessionNativeWriteError(ValueError):
    def __init__(self, code: str = "work_session_native_write_invalid") -> None:
        super().__init__(code)
        self.code = code if code in _ERRORS else "work_session_native_write_invalid"


def _fail(code: str = "work_session_native_write_invalid") -> WorkSessionNativeWriteError:
    return WorkSessionNativeWriteError(code)


def _canonical(document: Any) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, repr=False)
class NativeWriteScope:
    """Private ownership facts frozen before the plan digest is computed."""

    kind: str
    binding: WorkSessionBinding
    task_route_ref: str
    actor_sha256: str
    registry_preimage_sha256: str
    claim_ref: str

    def __post_init__(self) -> None:
        if (self.kind not in NATIVE_WRITE_KINDS or type(self.binding) is not WorkSessionBinding
                or any(type(getattr(self, name)) is not str or not getattr(self, name)
                       for name in ("task_route_ref", "actor_sha256", "registry_preimage_sha256", "claim_ref"))):
            raise _fail()

    def document(self) -> dict[str, Any]:
        """Ownership facts the plan binds; stable across the operation itself.

        The actor image and registry generation are deliberately not part of
        the digest: they change when this very operation is recorded as
        pending and completed, and an exact replay must still reproduce the
        reviewed plan. Their freshness is enforced by the compare-and-swap in
        the publish helpers instead.
        """

        return {
            "schema": SCOPE_SCHEMA,
            "kind": self.kind,
            "work_session_binding": self.binding.document(),
            "task_route_ref": self.task_route_ref,
            "claim_ref": self.claim_ref,
        }

    @property
    def scope_sha256(self) -> str:
        return _sha(_canonical(self.document()))

    def public_projection(self) -> dict[str, Any]:
        """Content-free facts for results; no label, path or reviewer id."""

        return {
            "schema": SCOPE_SCHEMA,
            "kind": self.kind,
            "bound": True,
            "scope_sha256": self.scope_sha256,
            "work_session_binding_sha256": self.binding.binding_sha256,
            "current_claim_ownership_verified": True,
            "private_values_echoed": False,
        }

    def __repr__(self) -> str:
        return "NativeWriteScope(<private ownership facts; no write authority>)"


def native_write_scope_held(root, *, held, kind, client_app_ref, task_route_ref, work_session_ref):
    """Verify the caller's claimed session under the held lane; read only.

    Returns the frozen scope with the actor routing store, the routing handle
    and the selected actor context, so a later publish can CAS against them.
    """

    if kind not in NATIVE_WRITE_KINDS:
        raise _fail()
    try:
        binding = actor_selection._require_actor_selection_for_write_held(
            root, held=held, client_app_ref=client_app_ref,
            task_route_ref=task_route_ref, work_session_ref=work_session_ref,
        )
        store, routing = lifecycle._routing(root, held=held, client_app_ref=client_app_ref,
                                            task_route_ref=task_route_ref)
        selected = routing.read()
        if selected is None:
            raise _fail("work_session_task_context_required")
        document = selected.document()
        if document["work_session_ref"] != binding.work_session_ref:
            raise _fail("work_session_task_context_mismatch")
        generation = store.read().sha256
        scope = NativeWriteScope(kind=kind, binding=binding, task_route_ref=task_route_ref,
                                 actor_sha256=selected.sha256, registry_preimage_sha256=generation,
                                 claim_ref=document["claim_ref"])
    except WorkSessionNativeWriteError:
        raise
    except actor_selection.WorkSessionTaskSelectionError as error:
        raise _fail(error.code if error.code in _ERRORS else "work_session_task_ownership_unavailable") from None
    except lifecycle.WorkSessionLifecycleError as error:
        raise _fail(error.code if error.code in _ERRORS else "work_session_task_ownership_unavailable") from None
    except Exception:
        raise _fail("work_session_task_ownership_unavailable") from None
    return scope, store, routing, selected


def operation_pointer(scope: NativeWriteScope, *, plan_sha256: str, context_sha256: str) -> dict[str, str]:
    return {"kind": scope.kind, "manifest_sha256": _digest_ref(plan_sha256), "context_sha256": _digest_ref(context_sha256)}


def _digest_ref(value: str) -> str:
    text = str(value or "").strip().lower()
    return text if text.startswith("sha256:") else "sha256:" + text


def revalidate_scope_held(root, scope: NativeWriteScope, *, held, client_app_ref, task_route_ref,
                          work_session_ref):
    """The ownership facts frozen into the plan must still hold after the dialog."""

    fresh, store, routing, selected = native_write_scope_held(
        root, held=held, kind=scope.kind, client_app_ref=client_app_ref,
        task_route_ref=task_route_ref, work_session_ref=work_session_ref,
    )
    if fresh.scope_sha256 != scope.scope_sha256:
        raise _fail("work_session_native_write_changed")
    return store, routing, selected


def publish_pending_held(scope: NativeWriteScope, routing, selected, *, held, plan_sha256, context_sha256):
    """Record the operation as pending on the actor before the first write."""

    pointer = operation_pointer(scope, plan_sha256=plan_sha256, context_sha256=context_sha256)
    try:
        return routing.save(
            expected_sha256=selected.sha256, held_lock=held,
            work_session_ref=scope.binding.work_session_ref, claim_ref=scope.claim_ref,
            observed_binding=scope.binding, pending_registry_intent_plan_sha256=None,
            pending_operation=actor.PendingOperationSelector.from_document(pointer),
        )
    except Exception:
        raise _fail("work_session_native_write_changed") from None


def publish_completed_held(scope: NativeWriteScope, routing, pending, *, held, plan_sha256, context_sha256):
    """Replace the pending pointer with the completed selector, CAS-checked."""

    pointer = operation_pointer(scope, plan_sha256=plan_sha256, context_sha256=context_sha256)
    try:
        current = routing.read()
        if current is None or current.sha256 != pending.sha256:
            raise _fail("work_session_native_write_changed")
        operation = current.pending_operation()
        if operation is None:
            raise _fail("work_session_native_write_pending_missing")
        if operation.document() != pointer:
            raise _fail("work_session_native_write_changed")
        return routing.save(
            expected_sha256=current.sha256, held_lock=held,
            work_session_ref=scope.binding.work_session_ref, claim_ref=scope.claim_ref,
            observed_binding=scope.binding, pending_registry_intent_plan_sha256=None,
            pending_operation=None,
            last_completed_operation=actor.CompletedOperationSelector.from_document(pointer),
        )
    except WorkSessionNativeWriteError:
        raise
    except Exception:
        raise _fail("work_session_native_write_changed") from None
