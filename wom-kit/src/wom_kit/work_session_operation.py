"""Session decisions use the existing exact manifest and authenticated claim.

This is an internal domain adapter, not a second approval mechanism. A session
transition appends one immutable generation; its compensation is another
explicit transition, never deletion or rewriting of historical responsibility.
Public CLI orchestration must own lock acquisition, native intent and discovery.
"""

from dataclasses import dataclass, replace
import hashlib
import hmac
import json
import os
from typing import Any, Callable

from . import exact_operation_manifest as exact
from . import work_session_registry as registry
from .exact_human_approval import (
    _ClaimedExactHumanApproval, _archive_identity, exact_human_approval_context_sha256,
)
from .exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation
from .operation_approval_binding import exact_operation_manifest_approval_binding


_KIND = "work_session_generation"
_FIELD = "immutable_registry_generation"
_ACTIONS = {"create": "start", "handoff": "handoff", "accept": "accept", "recover": "recover"}


def _fail():
    return registry.WorkSessionRegistryError("work_session_transition_invalid")


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def task_route_binding_sha256(*, archive_identity_sha256, client_app_ref, task_route_ref) -> str:
    """Bind an explicit private caller route, not app attestation or authority."""
    if (not registry._is_digest(archive_identity_sha256)
            or not registry._ref(client_app_ref, "client_app")
            or not registry._ref(task_route_ref, "task_route")):
        raise _fail()
    return registry._digest({
        "schema": "wom-kit/work-session-task-route-binding/v1",
        "archive_identity_sha256": archive_identity_sha256,
        "client_app_ref": client_app_ref,
        "task_route_ref": task_route_ref,
    })


@dataclass(frozen=True, repr=False)
class PreparedSessionDecision:
    transition: registry.RegistryTransition
    manifest: exact.ExactOperationManifest
    source_bytes: bytes
    task_route_ref: str | None = None

    def __repr__(self) -> str:
        return "PreparedSessionDecision(<private>)"

    def validate(self) -> None:
        self.transition.validate()
        if self.transition.action not in _ACTIONS:
            raise _fail()
        # Recompute all public bindings from the frozen private transition.
        expected = _build(self.transition, task_route_ref=self.task_route_ref)
        if (self.manifest.document() != expected.manifest.document()
                or self.source_bytes != expected.source_bytes):
            raise _fail()

    @property
    def task_route_binding_sha256(self) -> str | None:
        if self.task_route_ref is None:
            return None
        binding = self.transition.after.binding(self.transition.result_refs[-1])
        return task_route_binding_sha256(
            archive_identity_sha256=binding.archive_identity_sha256,
            client_app_ref=binding.client_app_ref, task_route_ref=self.task_route_ref,
        )

    def context(self, *, archive_id: str, reviewer_claim: str) -> ExactHumanApprovalContext:
        self.validate()
        binding = exact_operation_manifest_approval_binding(
            self.manifest, operation=ExactHumanApprovalOperation.work_session,
            archive_id=archive_id,
        )
        # Generic caller warnings are intentionally hashed, not display text.
        # Only this fixed internal action table supplies the new UI discriminator.
        binding = replace(binding, warning_codes=("work_session_" + _ACTIONS[self.transition.action],))
        return binding.context(archive_id=archive_id, reviewer_claim=reviewer_claim)


def _build(transition: registry.RegistryTransition, *, task_route_ref=None) -> PreparedSessionDecision:
    archive_sha = transition.after._document["archive_identity_sha256"]
    revision = transition.after.revision
    target = f"work-session-generation:{revision:012d}"
    source = registry._canonical({
        "schema": "wom-kit/work-session-transition-source/v1",
        "previous_generation_sha256": transition.before_sha256,
        "transition_sha256": transition.plan_sha256,
        "action": transition.action,
    })
    # create and accept return the new session; handoff/recover return the
    # responsible existing session. Bind the exact resulting revision, not a
    # later registry lookup, and never retrofit an old approval.
    session_ref = transition.result_refs[-1]
    binding = transition.after.binding(session_ref)
    evidence_digests = (("transition_sha256", transition.plan_sha256),)
    if task_route_ref is not None:
        evidence_digests = (("task_route_binding_sha256", task_route_binding_sha256(
            archive_identity_sha256=archive_sha, client_app_ref=binding.client_app_ref,
            task_route_ref=task_route_ref,
        )), *evidence_digests)
    item = exact.ExactOperationItem(
        ordinal=0, item_id=f"item:session-generation:{revision:012d}",
        target_kind=_KIND, target_ref=target,
        target_identity_sha256=registry._digest({"archive": archive_sha, "target": target}),
        fields=(exact.ExactFieldEffect(
            field_ref=_FIELD, pre_sha256=exact.ABSENT_FIELD_SHA256,
            post_sha256=transition.after.sha256, source_sha256=_sha(source),
        ),),
    )
    manifest = exact.ExactOperationManifest.build(
        operation="work_session", archive_identity_sha256=archive_sha,
        items=(item,), work_session_binding=binding,
        operation_evidence=exact.ExactOperationEvidence(
            schema="wom-kit/work-session-decision-evidence/v1",
            counts=(("generation_count", 1),),
            digests=evidence_digests,
        ),
    )
    return PreparedSessionDecision(transition, manifest, source, task_route_ref)


def prepare_session_decision(transition: registry.RegistryTransition, *, task_route_ref=None) -> PreparedSessionDecision:
    if type(transition) is not registry.RegistryTransition:
        raise _fail()
    transition.validate()
    if transition.action not in _ACTIONS:
        raise _fail()
    # None is the historical contract: no new evidence, source or bundle key.
    # Never retrofit an old approved operation with a current caller route.
    return _build(transition, task_route_ref=task_route_ref)


class _Payloads:
    def __init__(self, prepared: PreparedSessionDecision):
        self.prepared = prepared

    def field_value(self, *, item_id, field_ref, state, heartbeat):
        self.prepared.validate()
        if item_id != self.prepared.manifest.items[0].item_id or field_ref != _FIELD:
            raise _fail()
        heartbeat()
        if state == "pre":
            return None
        if state == "post":
            return registry._canonical(self.prepared.transition.after._document)
        if state == "source":
            return self.prepared.source_bytes
        raise _fail()


class _Verifier:
    def __init__(self, store: registry.WorkSessionRegistryStore, prepared: PreparedSessionDecision):
        self.store, self.prepared = store, prepared

    def _check_target(self, target_kind, target_ref):
        self.prepared.validate()
        item = self.prepared.manifest.items[0]
        if (target_kind != _KIND or target_ref != item.target_ref
                or self.store.archive_identity_sha256 != self.prepared.manifest.archive_identity_sha256):
            raise _fail()
        return item

    def target_identity_sha256(self, *, target_kind, target_ref, heartbeat):
        item = self._check_target(target_kind, target_ref)
        self.store.read()  # Independently recheck root/chain and latest generation.
        heartbeat()
        return item.target_identity_sha256

    def read_field(self, *, target_kind, target_ref, field_ref, heartbeat):
        self._check_target(target_kind, target_ref)
        if field_ref != _FIELD:
            raise _fail()
        # Observe the immutable target, not the latest full registry state.
        # A later unrelated session therefore cannot rewrite old success proof.
        self.store.read()
        raw = self.store._read_generation_bytes(
            self.prepared.transition.after.revision, heartbeat=heartbeat,
        )
        if raw is None:
            return None
        try:
            observed = registry.RegistrySnapshot(json.loads(raw))
        except (ValueError, TypeError, UnicodeError):
            raise _fail() from None
        if (observed.revision != self.prepared.transition.after.revision
                or observed._document["archive_identity_sha256"] != self.store.archive_identity_sha256):
            raise _fail()
        return raw


class _Writer:
    def __init__(self, store, prepared, lock, verify_authority):
        self.store, self.prepared, self.lock = store, prepared, lock
        self.verify_authority = verify_authority

    def write_field(self, *, target_kind, target_ref, field_ref, value, heartbeat):
        self.prepared.validate()
        item = self.prepared.manifest.items[0]
        if (target_kind != _KIND or target_ref != item.target_ref or field_ref != _FIELD
                or type(value) is not bytes
                or not hmac.compare_digest(value, registry._canonical(self.prepared.transition.after._document))):
            # Never delete/revert an immutable generation or publish different bytes.
            raise _fail()
        heartbeat()
        self.store.commit(self.prepared.transition, held_lock=self.lock,
                          verify_human_authority=self.verify_authority)
        heartbeat()


def apply_session_decision_with_claim(
    store: registry.WorkSessionRegistryStore, prepared: PreparedSessionDecision, *,
    context: ExactHumanApprovalContext, claim: _ClaimedExactHumanApproval,
    held_lock: exact.ExactOperationWriterLock, resume: bool = False,
    progress_hook: Callable[[exact.ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    """Internal authenticated writer; callers cannot supply a boolean approval."""
    if type(prepared) is not PreparedSessionDecision or type(claim) is not _ClaimedExactHumanApproval:
        raise _fail()
    prepared.validate()
    if (context.plan_sha256 != prepared.manifest.manifest_sha256
            or context.target_binding_sha256 != prepared.manifest.target_set_sha256
            or context.archive_identity_sha256 != prepared.manifest.archive_identity_sha256
            or context.operation is not ExactHumanApprovalOperation.work_session
            or context.warning_codes != ("work_session_" + _ACTIONS[prepared.transition.action],)):
        raise _fail()
    held_lock.verify_held()
    if not os.path.samefile(held_lock.archive_root, store.root):
        raise _fail()
    _root, archive_id = _archive_identity(store.root)
    expected_context = prepared.context(archive_id=archive_id, reviewer_claim=context.reviewer_claim)
    if not hmac.compare_digest(exact_human_approval_context_sha256(context),
                               exact_human_approval_context_sha256(expected_context)):
        raise _fail()
    reference = claim.assert_ready_for_context(context)
    authority = exact.ExactOperationApprovalAuthority.from_reference(reference)

    def verify_authority(transition_sha):
        return (transition_sha == prepared.transition.plan_sha256
                and claim.assert_ready_for_context(context) == reference)

    def authenticate_completion(payload):
        return {"approval_reference": claim.public_reference(),
                "terminal_mac": claim.exact_terminal_record_mac(payload)}

    checkpoint_store = exact.FileExactOperationCheckpointStore(store.root, writer_lock=held_lock)
    result = exact.apply_exact_operation(
        prepared.manifest, payloads=_Payloads(prepared),
        writer=_Writer(store, prepared, held_lock, verify_authority),
        verifier=_Verifier(store, prepared), checkpoint_store=checkpoint_store,
        approval_authority=authority, completion_authenticator=authenticate_completion,
        resume=resume, progress_hook=progress_hook,
    )
    return {**result, "ok": result["status"] == "completed",
            "work_session_binding": prepared.manifest.work_session_binding.document(),
            "lifecycle_action": "work_session_" + prepared.transition.action,
            "registry_generation_sha256": prepared.transition.after.sha256,
            "result_refs": list(prepared.transition.result_refs), "private_labels_echoed": False}
