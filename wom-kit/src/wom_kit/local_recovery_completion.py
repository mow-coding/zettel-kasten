"""Read-only evidence readers for a completed session local recovery.

The three modes mirror the intake completion readers: a data-only byte image,
an audit with an active same-archive claim key, and keyed discovery of the
exact succeeded original. All read the existing retained control, common
final receipt, checkpoint, claim bytes and establishment evidence. None of
them enters the domain writer, publishes a claim, repairs evidence or grants
current ownership; a caller's own typed runner still owns write admission.
Whole-document images are approved data; Git ownership is decided by the Git
producer, which additionally compares HEAD, index and worktree bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as broker
from . import exact_operation_manifest as exact
from . import local_recovery_document_images as document_images
from . import local_recovery_execution as recovery
from . import local_recovery_session as sessions
from . import work_session_bundle as controls
from . import work_session_establishment as establishment
from . import work_session_execution as session_execution
from . import work_session_operation as session_operation
from . import work_session_registry as registry
from . import work_session_source_intake_completion as evidence_readers


_ERRORS = frozenset({
    "local_recovery_completion_invalid", "local_recovery_completion_missing",
    "local_recovery_completion_changed", "local_recovery_completion_unavailable",
})
DOCUMENT_OUTPUT_KIND = "canonical_zettel_document"
RECEIPT_OUTPUT_KIND = "common_completion_receipt"


class LocalRecoveryCompletionError(RuntimeError):
    def __init__(self, code="local_recovery_completion_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "local_recovery_completion_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "local_recovery_completion_invalid"
    try:
        return call()
    except LocalRecoveryCompletionError as error:
        code = error.code
    except evidence_readers.WorkSessionIntakeCompletionError as error:
        code = {"work_session_intake_completion_missing": "local_recovery_completion_missing",
                "work_session_intake_completion_changed": "local_recovery_completion_changed"}.get(
                    error.code, "local_recovery_completion_invalid")
    except recovery.LocalRecoveryError as error:
        code = {"local_recovery_plan_changed": "local_recovery_completion_changed",
                "local_recovery_control_invalid": "local_recovery_completion_unavailable"}.get(
                    error.code, "local_recovery_completion_invalid")
    except Exception:
        pass
    # Raise outside the handler: no private path, JSON or callback chain survives.
    raise LocalRecoveryCompletionError(code)


def _invalid():
    return LocalRecoveryCompletionError()


@dataclass(frozen=True, slots=True, repr=False)
class _Original:
    """Validated retained control plus its establishment; not authority."""
    view: object
    plan: object
    scope: object
    store: object
    origin: object
    origin_raw: bytes
    images: tuple

    def __repr__(self):
        return "<private local recovery original; not authority>"


def _original(root, held, manifest_sha256, context_sha256):
    if not registry._is_digest(manifest_sha256) or not registry._is_digest(context_sha256):
        raise _invalid()
    plan = recovery.load_local_recovery_plan(root, manifest_sha256=manifest_sha256)
    if plan.session_context is None or plan.manifest.manifest_sha256 != manifest_sha256:
        raise LocalRecoveryCompletionError("local_recovery_completion_unavailable")
    view = sessions._view(plan)
    if approval.exact_human_approval_context_sha256(view.context) != context_sha256:
        raise _invalid()
    images = sessions._document_images(plan)
    if images is None:
        # Historical image-less controls carry no whole-document evidence.
        raise LocalRecoveryCompletionError("local_recovery_completion_unavailable")
    document_images._validate(plan, images)
    store, _archive = session_execution._store(plan.archive_root)
    scope = view.scope.document()
    selector = establishment.EstablishmentSelector.from_document(scope["original_establishment"])
    origin_raw = controls._read_bundle_raw(store, selector.manifest_sha256)
    binding = plan.manifest.work_session_binding
    origin = establishment.load_original_establishment(store, selector=selector,
        client_app_ref=binding.client_app_ref, task_route_ref=scope["task_route_ref"],
        work_session_ref=binding.work_session_ref)
    original = _Original(view, plan, view.scope, store, origin, origin_raw,
                         tuple(controls._strict_document(recovery._canonical_bytes(row)) for row in images))
    _require_original(original, held)
    return original


def _require_original(original, held):
    sessions._retained(original.view, held)
    original.store._require_held_lock(held)
    selector = establishment.EstablishmentSelector.from_document(original.scope.document()["original_establishment"])
    if controls._read_bundle_raw(original.store, selector.manifest_sha256) != original.origin_raw:
        raise LocalRecoveryCompletionError("local_recovery_completion_changed")


def _completion_evidence(original, *, reference, execution, final):
    """Structural agreement of the final receipt with the retained plan; no MAC."""
    plan = original.plan
    authority = exact.ExactOperationApprovalAuthority.from_reference(reference)
    if type(final) is not dict or type(final.get("result")) is not dict:
        raise _invalid()
    result = final["result"]
    auth = result.get("completion_authentication")
    if (type(auth) is not dict or result.get("status") != "completed" or result.get("mode") != "apply"
            or result.get("manifest_sha256") != plan.manifest.manifest_sha256
            or result.get("execution_sha256") != execution
            or exact.exact_operation_execution_sha256(plan.manifest, approval_authority=authority) != execution
            or result.get("approval_binding_sha256") != authority.binding_sha256
            or authority.context_sha256 != approval.exact_human_approval_context_sha256(original.view.context)
            or result.get("operation_evidence") != plan.manifest.operation_evidence.document()
            or result.get("work_session_binding_sha256") != plan.manifest.work_session_binding.binding_sha256
            or result.get("extension_sha256") != plan.manifest.extension_sha256
            or result.get("item_count") != len(plan.specs) or result.get("field_count") != len(plan.specs)
            or auth.get("operation") != recovery.APPLY_OPERATION
            or auth.get("target_binding_sha256") != plan.manifest.target_set_sha256
            or auth.get("approval_reference") != reference):
        raise _invalid()
    return authority, auth, exact.exact_operation_completion_authentication_payload(result)


@dataclass(frozen=True, slots=True, repr=False)
class _LocalRecoveryCompletionImage:
    """Strict DATA ONLY. Matching digests are not authenticated completion."""
    _original: _Original
    execution_sha256: str
    _files: tuple
    _final_raw: bytes
    _origin_final_raw: bytes
    _outputs_raw: bytes

    def __repr__(self):
        return "<private local recovery completion image; unauthenticated data>"

    @property
    def plan(self):
        return self._original.plan

    @property
    def context(self):
        return self._original.view.context

    @property
    def scope(self):
        return self._original.scope

    @property
    def image_sha256(self):
        return recovery._sha(recovery._canonical_bytes(
            [[name, recovery._sha(raw), len(raw)] for name, raw in self._files]))

    def approved_output_map(self):
        return controls._strict_document(self._outputs_raw)

    def proof_document(self):
        """Structural proof fields only; this image has NOT verified their MACs."""
        final = evidence_readers._final_document(self._final_raw)
        authority = exact.ExactOperationApprovalAuthority.from_reference(
            final["result"]["completion_authentication"]["approval_reference"])
        return {"manifest_sha256": self.plan.manifest.manifest_sha256,
                "context_sha256": authority.context_sha256, "execution_sha256": self.execution_sha256,
                "common_final_receipt_sha256": final["receipt_sha256"],
                "recovery_scope_sha256": self.scope.document()["scope_sha256"],
                "work_session_binding": self.plan.manifest.work_session_binding.document()}


def _outputs(original, relative, raw, execution):
    """Approved whole outputs keyed by archive-relative path; digests only."""
    first, last = {}, {}
    for row in original.images:
        first.setdefault(row["relative_path"], row)
        last[row["relative_path"]] = row
    outputs = {}
    for path, row in first.items():
        outputs[path] = {"output_kind": DOCUMENT_OUTPUT_KIND, "output_identity_sha256": row["target_ref"],
                         "head_sha256": row["pre_sha256"], "head_bytes": row["pre_bytes"],
                         "sha256": last[path]["post_sha256"], "size_bytes": last[path]["post_bytes"]}
    if relative in outputs:
        raise _invalid()
    outputs[relative] = {"output_kind": RECEIPT_OUTPUT_KIND, "output_identity_sha256": execution,
                         "head_sha256": None, "head_bytes": None,
                         "sha256": recovery._sha(raw), "size_bytes": len(raw)}
    return outputs


def _image(original, execution, held):
    _require_original(original, held)
    plan, scope = original.plan, original.scope.document()
    final, relative, raw, checkpoint, claim_raw = evidence_readers._final_image(plan.archive_root, execution, held)
    reference = final["result"]["completion_authentication"]["approval_reference"]
    _completion_evidence(original, reference=reference, execution=execution, final=final)
    origin_final, _origin_path, origin_raw, origin_checkpoint, origin_claim = evidence_readers._final_image(
        plan.archive_root, scope["establishment_execution_sha256"], held)
    evidence_readers._origin_evidence(original, origin_final)
    if (not exact.validate_exact_operation_resume_checkpoint_read_only(plan.archive_root, plan.manifest,
            execution_sha256=execution,
            approval_authority=exact.ExactOperationApprovalAuthority.from_reference(reference))
            or recovery.verify_local_recovery_state(plan, state="post").get("all_match") is not True
            or not document_images._matches_state_held(plan, list(original.images), state="post", held=held)
            or exact.verify_exact_operation(original.origin.prepared.manifest,
                verifier=session_operation._Verifier(original.store, original.origin.prepared), state="post",
                heartbeat=held.verify_held)["all_match"] is not True):
        raise LocalRecoveryCompletionError("local_recovery_completion_changed")
    files = [("original", original.view.control_bytes), ("establishment", original.origin_raw),
             ("common_final", raw), ("checkpoint", checkpoint), ("claim", claim_raw),
             ("establishment_final", origin_raw), ("establishment_checkpoint", origin_checkpoint),
             ("establishment_claim", origin_claim)]
    outputs = _outputs(original, relative, raw, execution)
    for path, output in outputs.items():
        if output["output_kind"] == DOCUMENT_OUTPUT_KIND:
            files.append(("document:" + path, recovery._canonical_bytes(output)))
    _require_original(original, held)
    return _LocalRecoveryCompletionImage(original, execution, tuple(files), raw, origin_raw,
                                         recovery._canonical_bytes(outputs))


@dataclass(frozen=True, slots=True, repr=False)
class _VerifiedLocalRecoveryCompletion:
    """Historical proof only; the downstream caller still owns write admission."""
    _image: _LocalRecoveryCompletionImage
    _proof_raw: bytes

    def __repr__(self):
        return "<private authenticated historical local recovery completion; no current ownership authority>"

    @property
    def plan(self):
        return self._image.plan

    @property
    def context(self):
        return self._image.context

    @property
    def scope(self):
        return self._image.scope

    @property
    def image_sha256(self):
        return self._image.image_sha256

    def proof_document(self):
        return controls._strict_document(self._proof_raw)

    def approved_output_map(self):
        return self._image.approved_output_map()


def _authenticate(image, claim, held):
    original, context, plan = image._original, image.context, image.plan
    if (type(claim) is not approval._ClaimedExactHumanApproval
            or not os.path.samefile(claim._path, plan.archive_root / approval.CLAIMS_RELATIVE_ROOT /
                                    (claim.approval_id + ".json"))):
        raise _invalid()
    _require_original(original, held)
    final = evidence_readers._final_document(image._final_raw)
    reference = final["result"]["completion_authentication"]["approval_reference"]
    authority, auth, payload = _completion_evidence(original, reference=reference,
                                                    execution=image.execution_sha256, final=final)
    origin_auth, origin_payload = evidence_readers._origin_evidence(
        original, evidence_readers._final_document(image._origin_final_raw))
    for row, expected, value in ((auth, context, payload), (origin_auth, original.origin.context, origin_payload)):
        if not claim.exact_terminal_record_matches(row["approval_reference"], expected.operation,
                expected.plan_sha256, expected.target_binding_sha256, frozenset({"succeeded"}),
                None, value, row["terminal_mac"]):
            raise _invalid()
    _require_original(original, held)
    return authority


def _verified(original, execution, claim, held):
    image = _image(original, execution, held)
    _authenticate(image, claim, held)
    observed = _image(original, execution, held)
    if observed._files != image._files:
        raise LocalRecoveryCompletionError("local_recovery_completion_changed")
    _authenticate(observed, claim, held)
    return _VerifiedLocalRecoveryCompletion(image, recovery._canonical_bytes(image.proof_document()))


def _read_local_recovery_completion_image_held(root, *, held, manifest_sha256, context_sha256, execution_sha256):
    """Data-only exact byte image, with no claim/MAC or ownership assertion."""
    return _safe_call(lambda: _image(_original(root, held, manifest_sha256, context_sha256),
                                     execution_sha256, held))


def _verify_completed_local_recovery_with_claim_held(root, *, held, manifest_sha256, context_sha256,
                                                     execution_sha256, claim):
    """Audit a succeeded original with an active same-archive claim key.

    The active claim may belong to another operation, such as a started Git
    backup. This read does not admit that operation.
    """
    return _safe_call(lambda: _verified(_original(root, held, manifest_sha256, context_sha256),
                                        execution_sha256, claim, held))


def _read_completed_local_recovery_held(root, *, held, manifest_sha256, context_sha256, key_provider=None):
    """Discover only the exact authenticated succeeded original, without creating."""
    return _safe_call(lambda: _read_completed(_original(root, held, manifest_sha256, context_sha256),
                                              held, key_provider))


def _read_completed(original, held, key_provider):
    def read():
        generation = evidence_readers._claim_generation(original, held)
        candidates = []

        def started(_claim):
            raise _invalid()

        def succeeded(claim):
            # The existing own-completion gate authenticates the exact final
            # receipt and post state for this context before the image reader.
            verified = sessions._completion(original.view, claim, held)
            candidates.append(_verified(original, verified["execution_sha256"], claim, held))
            return True

        broker._discover_exact_human_approved_transaction_resume_core(original.plan.archive_root,
            original.view.context, started, succeeded, key_provider=key_provider,
            resume_boundary=lambda: session_execution._claim_boundary(original.store, held, create=False))
        if len(candidates) != 1:
            raise _invalid()
        result = candidates[0]
        if (_image(original, result._image.execution_sha256, held)._files != result._image._files
                or evidence_readers._claim_generation(original, held) != generation):
            raise LocalRecoveryCompletionError("local_recovery_completion_changed")
        return result
    return _safe_call(read)
