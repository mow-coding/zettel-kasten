"""Historical intake proof, never current ownership or downstream write authority.

The data image is deliberately distinct from authenticated completion. Both
readers retain one decoded original per call, verify only its immutable output
metadata, and never re-read the caller request or the original source bodies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import stat

from . import exact_human_approval as approval
from . import exact_human_approval_workflow as broker
from . import exact_operation_manifest as exact
from . import source_intake_batch_exact as intake
from . import source_intake_record_exact as record
from . import work_session_bundle as controls
from . import work_session_establishment as establishment
from . import work_session_execution as session_execution
from . import work_session_operation as session_operation
from . import work_session_registry as registry
from . import work_session_source_intake_bundle as bundle
from . import work_session_source_intake_record_bundle as record_bundle
from . import work_session_source_intake_record_execution as record_execution


_ERRORS = frozenset({
    "work_session_intake_completion_invalid", "work_session_intake_completion_unavailable",
    "work_session_intake_completion_missing", "work_session_intake_completion_changed",
    "work_session_intake_completion_authentication_invalid", "work_session_intake_completion_ambiguous",
    "work_session_intake_completion_lock_required",
})
_MAX_CLAIM_IMAGE_BYTES = 32 * 1024 * 1024


class _IntakeFamily(Enum):
    BATCH = "source_intake_batch"
    RECORD = "source_intake_record"


class WorkSessionIntakeCompletionError(RuntimeError):
    def __init__(self, code="work_session_intake_completion_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_intake_completion_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_intake_completion_unavailable"
    try:
        return call()
    except WorkSessionIntakeCompletionError as error:
        code = error.code
    except bundle.WorkSessionIntakeBundleError as error:
        if error.code == "work_session_intake_bundle_lock_required":
            code = "work_session_intake_completion_lock_required"
        elif error.code == "work_session_intake_bundle_missing":
            code = "work_session_intake_completion_missing"
    except record_bundle.WorkSessionIntakeRecordBundleError as error:
        if error.code == "work_session_intake_record_bundle_lock_required":
            code = "work_session_intake_completion_lock_required"
        elif error.code == "work_session_intake_record_bundle_missing":
            code = "work_session_intake_completion_missing"
    except broker.ExactHumanApprovalWorkflowError as error:
        if error.code == "exact_human_approval_resume_candidate_missing":
            code = "work_session_intake_completion_missing"
        elif error.code == "exact_human_approval_resume_candidate_ambiguous":
            code = "work_session_intake_completion_ambiguous"
        else:
            code = "work_session_intake_completion_authentication_invalid"
    except Exception:
        pass
    raise WorkSessionIntakeCompletionError(code)


def _invalid():
    return WorkSessionIntakeCompletionError("work_session_intake_completion_authentication_invalid")


def _final_document(raw):
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        raise _invalid()
    return exact._strict_json_document(raw[:-1])


@dataclass(frozen=True, slots=True, repr=False)
class _Original:
    prepared: object
    context: object
    plan: object
    scope: object
    raw: bytes
    store: object
    origin: object
    origin_raw: bytes
    family: _IntakeFamily = _IntakeFamily.BATCH


def _original(root, held, manifest_sha256, context_sha256, *, family=_IntakeFamily.BATCH):
    if not registry._is_digest(manifest_sha256) or not registry._is_digest(context_sha256):
        raise WorkSessionIntakeCompletionError()
    if family is _IntakeFamily.BATCH:
        bound = bundle._load_original_source_intake_context_held(root,
            manifest_sha256=manifest_sha256, held=held)
        prepared, context = bundle._decode_context(bound._root, bound._raw, manifest_sha256)
        plan, scope, _rows = bundle._decode_prepared(prepared._root, prepared._raw)
    elif family is _IntakeFamily.RECORD:
        bound = record_bundle._load_original_source_intake_record_context_held(root,
            manifest_sha256=manifest_sha256, held=held)
        prepared, context = record_bundle._decode_context(bound._root, bound._raw, manifest_sha256)
        plan, scope, _input = record_bundle._decode_prepared(prepared._root, prepared._raw)
    else:
        raise WorkSessionIntakeCompletionError()
    if approval.exact_human_approval_context_sha256(context) != context_sha256:
        raise _invalid()
    store, _archive = session_execution._store(plan.archive_root)
    selector = establishment.EstablishmentSelector.from_document(scope.document()["original_establishment"])
    origin_raw = controls._read_bundle_raw(store, selector.manifest_sha256)
    binding = plan.manifest.work_session_binding
    origin = establishment.load_original_establishment(store, selector=selector,
        client_app_ref=binding.client_app_ref, task_route_ref=scope.document()["task_route_ref"],
        work_session_ref=binding.work_session_ref)
    original = _Original(prepared, context, plan, scope, bound._raw, store, origin, origin_raw, family)
    _require_original(original, held)
    return original


def _require_original(original, held):
    plan, scope = original.plan, original.scope.document()
    if original.family is _IntakeFamily.BATCH:
        bundle._held_root(plan.archive_root, held)
        raw = bundle._read_raw(plan.archive_root, plan.manifest.manifest_sha256)
    elif original.family is _IntakeFamily.RECORD:
        record_bundle._held_root(plan.archive_root, held)
        raw = record_bundle._read_raw(plan.archive_root, plan.manifest.manifest_sha256)
    else:
        raise WorkSessionIntakeCompletionError()
    if (raw != original.raw
            or controls._read_bundle_raw(original.store, original.origin.context.plan_sha256) != original.origin_raw
            or plan.manifest.operation_evidence.document()["digests"]["session_scope_sha256"] != scope["scope_sha256"]
            or plan.manifest.work_session_binding.document() != scope["work_session_binding"]
            or (intake.approval_context(plan, reviewer_claim=original.context.reviewer_claim, allow_resume=True)
                if original.family is _IntakeFamily.BATCH else
                record.approval_context(plan, reviewer_claim=original.context.reviewer_claim))
                != original.context):
        raise WorkSessionIntakeCompletionError("work_session_intake_completion_changed")


def _completion_evidence_view(original, *, reference, execution, final):
    if original.family is _IntakeFamily.BATCH:
        return intake._source_intake_batch_completion_evidence_view(original.plan, context=original.context,
            reference=reference, execution=execution, final=final)
    if original.family is _IntakeFamily.RECORD:
        return record_execution._source_intake_record_completion_evidence_view(original.plan,
            context=original.context, reference=reference, execution=execution, final=final)
    raise WorkSessionIntakeCompletionError()


def _output_verifier(original):
    if original.family is _IntakeFamily.BATCH:
        return intake._Verifier(original.plan)
    if original.family is _IntakeFamily.RECORD:
        return record_execution._Verifier(original.plan)
    raise WorkSessionIntakeCompletionError()


def _verify_own_completion(original, claim, held):
    if original.family is _IntakeFamily.BATCH:
        return intake._verify_source_intake_batch_completion_with_claim_held(original.plan,
            context=original.context, claim=claim, writer_lock=held)
    if original.family is _IntakeFamily.RECORD:
        return record_execution._verify_source_intake_record_completion_with_claim_held(original.plan,
            context=original.context, claim=claim, writer_lock=held)
    raise WorkSessionIntakeCompletionError()


def _final_image(root, execution, held):
    if not registry._is_digest(execution):
        raise WorkSessionIntakeCompletionError()
    final = exact.load_exact_operation_final_receipt_read_only(root, execution, heartbeat=held.verify_held)
    if final is None:
        raise WorkSessionIntakeCompletionError("work_session_intake_completion_missing")
    relative = exact.EXACT_OPERATION_RECEIPTS_ROOT + "/" + execution[7:] + ".json"
    raw = controls._read_control(root / relative, maximum=exact._MAX_CANONICAL_BYTES)
    checkpoint = controls._read_control(root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints" /
        (execution[7:] + ".jsonl"), maximum=exact._MAX_CHECKPOINT_FILE_BYTES)
    if (_final_document(raw) != final
            or exact.load_exact_operation_final_receipt_read_only(root, execution, heartbeat=held.verify_held) != final):
        raise WorkSessionIntakeCompletionError("work_session_intake_completion_changed")
    reference = final["result"].get("completion_authentication", {}).get("approval_reference")
    exact.ExactOperationApprovalAuthority.from_reference(reference)
    with session_execution._claim_boundary(session_execution._store(root)[0], held, create=False) as boundary:
        claim_raw = approval._read_claim_bytes(root / approval.CLAIMS_RELATIVE_ROOT /
            (reference["approval_id"] + ".json"), bound_archive_root=boundary[0], claim_parent_binding=boundary[1])
    return final, relative, raw, checkpoint, claim_raw


def _claim_generation(original, held):
    """Bounded byte/identity inventory, not an unkeyed claim classifier."""
    root = original.plan.archive_root
    with session_execution._claim_boundary(original.store, held, create=False) as boundary:
        directory = boundary[1]
        descriptor = directory.get("descriptor")
        location = descriptor if type(descriptor) is int else directory["path"]
        names = tuple(sorted(os.listdir(location)))
        if len(names) > broker._MAX_RESUME_CLAIM_DIRECTORY_ENTRIES:
            raise _invalid()
        rows, total = [], 0
        for name in names:
            held.verify_held()
            path = directory["path"] / name
            before = os.lstat(path)
            identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                      value.st_mtime_ns, value.st_mode, getattr(value, "st_file_attributes", 0))
            if (not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode)
                    or exact._path_is_reparse(before) or before.st_nlink != 1
                    or not 0 <= before.st_size <= approval._MAX_CLAIM_BYTES):
                raise _invalid()
            total += before.st_size
            if total > _MAX_CLAIM_IMAGE_BYTES:
                raise _invalid()
            raw = approval._read_claim_bytes(path, bound_archive_root=boundary[0], claim_parent_binding=directory)
            after = os.lstat(path)
            if identity(before) != identity(after) or len(raw) != before.st_size:
                raise WorkSessionIntakeCompletionError("work_session_intake_completion_changed")
            rows.append((name, identity(after), raw))
        if tuple(sorted(os.listdir(location))) != names:
            raise WorkSessionIntakeCompletionError("work_session_intake_completion_changed")
    return tuple(rows)


def _origin_evidence(original, final):
    scope, context, manifest = original.scope.document(), original.origin.context, original.origin.prepared.manifest
    result = final["result"]
    auth = result.get("completion_authentication")
    if type(auth) is not dict:
        raise _invalid()
    authority = exact.ExactOperationApprovalAuthority.from_reference(auth["approval_reference"])
    evidence, binding = manifest.operation_evidence, manifest.work_session_binding
    if (final["receipt_sha256"] != scope["establishment_receipt_sha256"]
            or authority.context_sha256 != approval.exact_human_approval_context_sha256(context)
            or result["status"] != "completed" or result["mode"] != "apply"
            or result["manifest_sha256"] != manifest.manifest_sha256
            or result["execution_sha256"] != scope["establishment_execution_sha256"]
            or exact.exact_operation_execution_sha256(manifest, approval_authority=authority) != result["execution_sha256"]
            or result["approval_binding_sha256"] != authority.binding_sha256
            or result.get("operation_evidence") != (None if evidence is None else evidence.document())
            or result.get("work_session_binding_sha256") != (None if binding is None else binding.binding_sha256)
            or result.get("extension_sha256") != manifest.extension_sha256
            or result["item_count"] != len(manifest.items)
            or result["field_count"] != sum(len(item.fields) for item in manifest.items)
            or auth["operation"] != context.operation.value
            or auth["target_binding_sha256"] != context.target_binding_sha256):
        raise _invalid()
    return auth, exact.exact_operation_completion_authentication_payload(result)


@dataclass(frozen=True, slots=True, repr=False)
class _SessionSourceIntakeCompletionImage:
    """Strict DATA ONLY. Even matching hashes are not authenticated completion."""
    _original: _Original
    execution_sha256: str
    _files: tuple
    _final_raw: bytes
    _origin_final_raw: bytes
    _outputs_raw: bytes

    def __repr__(self):
        return "<private intake completion image; unauthenticated data>"

    @property
    def prepared(self):
        return self._original.prepared

    @property
    def context(self):
        return self._original.context

    @property
    def plan(self):
        return self._original.plan

    @property
    def scope(self):
        return self._original.scope

    @property
    def common_final_receipt_raw(self):
        return self._final_raw

    @property
    def image_sha256(self):
        return intake._sha_document([[name, intake._sha_bytes(raw), len(raw)] for name, raw in self._files])

    def approved_output_map(self):
        return controls._strict_document(self._outputs_raw)

    def proof_document(self):
        """Structural proof fields only; this image has NOT verified their MACs."""
        final = _final_document(self._final_raw)
        authority = exact.ExactOperationApprovalAuthority.from_reference(
            final["result"]["completion_authentication"]["approval_reference"])
        return {"manifest_sha256": self.plan.manifest.manifest_sha256,
            "context_sha256": authority.context_sha256, "execution_sha256": self.execution_sha256,
            "common_final_receipt_sha256": final["receipt_sha256"],
            "common_result_sha256": final["result"]["result_sha256"],
            "approval_binding_sha256": authority.binding_sha256,
            "session_scope_sha256": self.scope.document()["scope_sha256"],
            "work_session_binding": self.plan.manifest.work_session_binding.document()}


@dataclass(frozen=True, slots=True, repr=False)
class _SessionSourceIntakeRecordCompletionImage(_SessionSourceIntakeCompletionImage):
    """Single-record DATA ONLY, not a batch result or authenticated proof."""

    def __repr__(self):
        return "<private single-intake completion image; unauthenticated data>"


def _image(original, execution, held):
    _require_original(original, held)
    plan, context, scope = original.plan, original.context, original.scope.document()
    final, relative, raw, checkpoint, claim_raw = _final_image(plan.archive_root, execution, held)
    reference = final["result"]["completion_authentication"]["approval_reference"]
    _completion_evidence_view(original, reference=reference, execution=execution, final=final)
    origin_final, _origin_path, origin_raw, origin_checkpoint, origin_claim = _final_image(
        plan.archive_root, scope["establishment_execution_sha256"], held)
    _origin_evidence(original, origin_final)
    if (exact.verify_exact_operation(plan.manifest, verifier=_output_verifier(original), state="post",
            heartbeat=held.verify_held)["all_match"] is not True
            or exact.verify_exact_operation(original.origin.prepared.manifest,
                verifier=session_operation._Verifier(original.store, original.origin.prepared), state="post",
                heartbeat=held.verify_held)["all_match"] is not True):
        raise WorkSessionIntakeCompletionError("work_session_intake_completion_changed")
    files = [("original", original.raw), ("establishment", original.origin_raw),
        ("common_final", raw), ("checkpoint", checkpoint), ("claim", claim_raw),
        ("establishment_final", origin_raw), ("establishment_checkpoint", origin_checkpoint),
        ("establishment_claim", origin_claim)]
    outputs = {}
    def add(path, value, kind, target_kind, field_ref, identity):
        outputs[path] = {"output_kind": kind, "target_kind": target_kind, "field_ref": field_ref,
            "sha256": intake._sha_bytes(value), "size_bytes": len(value), "output_identity_sha256": identity}
        files.append(("output:" + path, value))
    if original.family is _IntakeFamily.BATCH:
        for item in plan.items:
            add(item.receipt_relative_path, item.receipt_bytes, "source_intake_receipt",
                intake.TARGET_KIND, intake.FIELD_REF, item.source_intake_plan_sha256)
        artifact = plan.prepared_capture_request
        add(artifact.relative_path, artifact.request_bytes, "prepared_capture_request",
            intake.CAPTURE_REQUEST_TARGET_KIND, intake.CAPTURE_REQUEST_FIELD_REF, artifact.request_sha256)
    elif original.family is _IntakeFamily.RECORD:
        add(plan.receipt_relative_path, plan.receipt_bytes, "source_intake_receipt",
            record.TARGET_KIND, record.FIELD_REF, plan.source_intake_plan_sha256)
    else:
        raise WorkSessionIntakeCompletionError()
    add(relative, raw, "common_completion_receipt", "exact_operation_final_receipt", "receipt_bytes", execution)
    _require_original(original, held)
    if original.family is _IntakeFamily.RECORD:
        return _SessionSourceIntakeRecordCompletionImage(original, execution, tuple(files), raw, origin_raw,
                                                       bundle._canonical(outputs))
    return _SessionSourceIntakeCompletionImage(original, execution, tuple(files), raw, origin_raw,
                                              bundle._canonical(outputs))


@dataclass(frozen=True, slots=True, repr=False)
class _VerifiedSessionSourceIntakeCompletion:
    """Historical proof only; the downstream caller still owns write admission."""
    _image: _SessionSourceIntakeCompletionImage
    _proof_raw: bytes

    def __repr__(self):
        return "<private authenticated historical intake completion; no current ownership authority>"

    @property
    def prepared(self):
        return self._image.prepared

    @property
    def context(self):
        return self._image.context

    @property
    def plan(self):
        return self._image.plan

    @property
    def scope(self):
        return self._image.scope

    @property
    def common_final_receipt_raw(self):
        return self._image.common_final_receipt_raw

    @property
    def image_sha256(self):
        return self._image.image_sha256

    def proof_document(self):
        return controls._strict_document(self._proof_raw)

    def approved_output_map(self):
        return self._image.approved_output_map()


@dataclass(frozen=True, slots=True, repr=False)
class _VerifiedSessionSourceIntakeRecordCompletion(_VerifiedSessionSourceIntakeCompletion):
    """Historical single-record proof, never source custody or write authority."""

    def __repr__(self):
        return "<private authenticated single-intake completion; no current ownership authority>"


def _authenticate(image, claim, held):
    original, context, plan = image._original, image.context, image.plan
    if (type(claim) is not approval._ClaimedExactHumanApproval
            or not os.path.samefile(claim._path, plan.archive_root / approval.CLAIMS_RELATIVE_ROOT /
                                   (claim.approval_id + ".json"))):
        raise _invalid()
    _require_original(original, held)
    final = _final_document(image._final_raw)
    reference = final["result"]["completion_authentication"]["approval_reference"]
    authority, auth, payload = _completion_evidence_view(original,
        reference=reference, execution=image.execution_sha256, final=final)
    origin_auth, origin_payload = _origin_evidence(original, _final_document(image._origin_final_raw))
    for row, expected, value in ((auth, context, payload), (origin_auth, original.origin.context, origin_payload)):
        if not claim.exact_terminal_record_matches(row["approval_reference"], expected.operation,
                expected.plan_sha256, expected.target_binding_sha256, frozenset({"succeeded"}),
                None, value, row["terminal_mac"]):
            raise _invalid()
    _require_original(original, held)
    return authority


def _verified(original, execution, claim, held):
    image = _image(original, execution, held)
    authority = _authenticate(image, claim, held)
    observed = _image(original, execution, held)
    if observed._files != image._files:
        raise WorkSessionIntakeCompletionError("work_session_intake_completion_changed")
    _authenticate(observed, claim, held)
    if original.family is _IntakeFamily.RECORD:
        return _VerifiedSessionSourceIntakeRecordCompletion(image, bundle._canonical(image.proof_document()))
    return _VerifiedSessionSourceIntakeCompletion(image, bundle._canonical(image.proof_document()))


def _read_session_source_intake_completion_image_held(root, *, held, manifest_sha256,
                                                    context_sha256, execution_sha256):
    """Data-only exact byte image, with no claim/MAC or ownership assertion."""
    return _safe_call(lambda: _image(_original(root, held, manifest_sha256, context_sha256),
                                      execution_sha256, held))


def _verify_completed_session_source_intake_with_claim_held(root, *, held, manifest_sha256,
                                                           context_sha256, execution_sha256, claim):
    """Audit original succeeded intake using an active same-archive claim key.

    The active claim may belong to another operation. This read does not admit
    that operation: its own concrete typed runner must still verify authority.
    """
    return _safe_call(lambda: _verified(_original(root, held, manifest_sha256, context_sha256),
                                         execution_sha256, claim, held))


def _read_completed_session_source_intake_held(root, *, held, manifest_sha256, context_sha256,
                                             key_provider=None):
    """Find only the exact authenticated succeeded original, without creating."""
    return _safe_call(lambda: _read_completed(_original(root, held, manifest_sha256, context_sha256),
                                             held, key_provider))


def _read_completed(original, held, key_provider):
    def read():
        generation = _claim_generation(original, held)
        candidates = []
        def started(_claim):
            raise _invalid()
        def succeeded(claim):
            # Keep the original intake-specific succeeded gate strict. The
            # shared cross-operation verifier below cannot replace this gate.
            verified = _verify_own_completion(original, claim, held)
            candidates.append(_verified(original, verified["execution_sha256"], claim, held))
            return True
        broker._discover_exact_human_approved_transaction_resume_core(original.plan.archive_root,
            original.context, started, succeeded, key_provider=key_provider,
            resume_boundary=lambda: session_execution._claim_boundary(original.store, held, create=False))
        if len(candidates) != 1:
            raise _invalid()
        result = candidates[0]
        if (_image(original, result._image.execution_sha256, held)._files != result._image._files
                or _claim_generation(original, held) != generation):
            raise WorkSessionIntakeCompletionError("work_session_intake_completion_changed")
        return result
    return _safe_call(read)


def _read_session_source_intake_record_completion_image_held(root, *, held, manifest_sha256,
                                                           context_sha256, execution_sha256):
    """Single-record DATA ONLY; no MAC, ownership or source-custody assertion."""
    return _safe_call(lambda: _image(_original(root, held, manifest_sha256, context_sha256,
        family=_IntakeFamily.RECORD), execution_sha256, held))


def _verify_completed_session_source_intake_record_with_claim_held(root, *, held, manifest_sha256,
                                                                  context_sha256, execution_sha256, claim):
    """Audit a succeeded original record with an active same-archive claim key."""
    return _safe_call(lambda: _verified(_original(root, held, manifest_sha256, context_sha256,
        family=_IntakeFamily.RECORD), execution_sha256, claim, held))


def _read_completed_session_source_intake_record_held(root, *, held, manifest_sha256, context_sha256,
                                                    key_provider=None):
    """Discover only a succeeded original record; never create key or approval."""
    return _safe_call(lambda: _read_completed(_original(root, held, manifest_sha256, context_sha256,
        family=_IntakeFamily.RECORD), held, key_provider))
