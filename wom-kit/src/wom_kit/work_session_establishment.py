"""Original create/accept selectors, separate from the last task operation.

Parsing and bundle identity checks confer no approval or ownership. The held
verifier only authenticates an already completed original human operation; it
never finishes a started operation, opens native UI or rebinds old evidence.
Actor selection/CAS and current ownership remain the calling facade's duties.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import work_session_registry as registry


_ACTIONS = frozenset({"create", "accept"})
_KEYS = frozenset({"action", "manifest_sha256", "context_sha256"})
_ERRORS = frozenset({
    "work_session_establishment_invalid", "work_session_establishment_changed",
    "work_session_establishment_unavailable", "work_session_task_context_mismatch",
    "work_session_lock_required",
})


class WorkSessionEstablishmentError(ValueError):
    def __init__(self, code="work_session_establishment_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_establishment_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_establishment_unavailable"
    try:
        return call()
    except WorkSessionEstablishmentError as error:
        code = error.code
    except Exception:
        pass
    # Private paths, labels and nested provider/claim failures are not retained.
    raise WorkSessionEstablishmentError(code)


@dataclass(frozen=True, repr=False)
class EstablishmentSelector:
    action: str
    manifest_sha256: str
    context_sha256: str

    def __post_init__(self):
        self._validate()

    def _validate(self):
        if (type(self.action) is not str or self.action not in _ACTIONS
                or not registry._is_digest(self.manifest_sha256)
                or not registry._is_digest(self.context_sha256)):
            raise WorkSessionEstablishmentError()

    @classmethod
    def from_document(cls, document):
        def parse():
            if (type(document) is not dict or any(type(key) is not str for key in document)
                    or set(document) != _KEYS):
                raise WorkSessionEstablishmentError()
            return cls(**document)
        return _safe_call(parse)

    @classmethod
    def from_original_create(cls, document):
        """Read normalization only; never rewrite a historical private image."""
        def parse():
            if (type(document) is not dict or any(type(key) is not str for key in document)
                    or set(document) != {"manifest_sha256", "context_sha256"}):
                raise WorkSessionEstablishmentError()
            return cls(action="create", **document)
        return _safe_call(parse)

    def document(self):
        self._validate()
        return {"action": self.action, "manifest_sha256": self.manifest_sha256,
                "context_sha256": self.context_sha256}

    def public_summary(self):
        self._validate()
        return {"establishment_action": self.action, "establishment_selected": True,
                "human_approval_verified": False, "current_claim_authority_evaluated": False}

    def __repr__(self):
        return "EstablishmentSelector(<private original selector; no approval authority>)"


def _selector(value):
    if type(value) is not EstablishmentSelector:
        raise WorkSessionEstablishmentError()
    return EstablishmentSelector.from_document(value.document())


def _load(store, *, selector, client_app_ref, task_route_ref, work_session_ref):
    # Lazy imports keep pure selector parsing usable from the actor and intent
    # readers without introducing actor -> execution -> actor import cycles.
    from . import work_session_bundle as bundle
    from .exact_human_approval import exact_human_approval_context_sha256

    selector = _selector(selector)
    for value, prefix in ((client_app_ref, "client_app"), (task_route_ref, "task_route"),
                          (work_session_ref, "work_session")):
        if not registry._ref(value, prefix):
            raise WorkSessionEstablishmentError("work_session_task_context_mismatch")
    bundle._check_store(store)
    bound = bundle.load_context_bound_session_decision(store, manifest_sha256=selector.manifest_sha256)
    prepared = bound.prepared
    binding = prepared.manifest.work_session_binding
    if (prepared.transition.action != selector.action
            or prepared.manifest.archive_identity_sha256 != store.archive_identity_sha256
            or binding.client_app_ref != client_app_ref or binding.work_session_ref != work_session_ref
            or prepared.task_route_ref != task_route_ref
            or exact_human_approval_context_sha256(bound.context) != selector.context_sha256):
        raise WorkSessionEstablishmentError("work_session_establishment_changed")
    bundle._check_store(store)
    return bound


def load_original_establishment(store, *, selector, client_app_ref, task_route_ref, work_session_ref):
    """Read original identity/context only; no MAC or current ownership proof."""
    return _safe_call(lambda: _load(store, selector=selector, client_app_ref=client_app_ref,
                                   task_route_ref=task_route_ref, work_session_ref=work_session_ref))


def verify_original_establishment_held(root, store, *, held, selector, client_app_ref,
                                       task_route_ref, work_session_ref, key_provider=None):
    """Authenticate the exact completed original, without any writer admission.

    The key-provider seam is internal, like the existing execution core. Public
    facades do not accept it. Returned original binding is historical evidence,
    not the current session revision or a claim for subsequent domain writes.
    """
    def verify():
        from . import work_session_bundle as bundle
        from . import work_session_execution as execution

        # Check both supplied paths against the same held archive lock before
        # any original-context key access, even for equal archive identifiers.
        try:
            bundle._check_lock(store, held)
        except Exception:
            raise WorkSessionEstablishmentError("work_session_lock_required") from None
        actual_store, _archive_id = execution._store(root)
        try:
            bundle._check_lock(actual_store, held)
        except Exception:
            raise WorkSessionEstablishmentError("work_session_lock_required") from None
        if actual_store.archive_identity_sha256 != store.archive_identity_sha256:
            raise WorkSessionEstablishmentError("work_session_establishment_changed")
        selected = _selector(selector)
        arguments = dict(selector=selected, client_app_ref=client_app_ref,
                         task_route_ref=task_route_ref, work_session_ref=work_session_ref)
        original = _load(store, **arguments)
        result = execution._resume_session_decision_held(
            root, held=held, manifest_sha256=selected.manifest_sha256,
            completed_only=True, key_provider=key_provider,
        )
        if (type(result) is not dict or result.get("ok") is not True
                or result.get("independent_post_verification") is not True
                or result.get("work_session_binding") != original.prepared.manifest.work_session_binding.document()
                or _load(store, **arguments) != original):
            raise WorkSessionEstablishmentError("work_session_establishment_changed")
        bundle._check_lock(store, held)
        return original
    return _safe_call(verify)


__all__ = ["EstablishmentSelector", "WorkSessionEstablishmentError",
           "load_original_establishment", "verify_original_establishment_held"]
