"""Retained original intake data, not approval, ownership or execution.

Only a fresh ready legacy plan can be wrapped. Its v2 manifest is retained
unchanged; a NEW scoped manifest binds the complete private input and original
session facts. Loading never replans, opens source/request files, authenticates
a claim, or upgrades old receipts. Concrete held execution remains separate.
"""

from __future__ import annotations

import base64
from contextlib import ExitStack
from dataclasses import dataclass, fields, replace
import os
from pathlib import Path
import stat
import uuid

from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import project_update_transaction as durable
from . import source_intake_batch_exact as intake
from . import work_session_bundle as controls
from . import work_session_registry as registry
from .exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation
from .work_session_binding import WorkSessionBinding
from .work_session_establishment import EstablishmentSelector


SCOPE_SCHEMA = "wom-kit/source-intake-batch-session-scope/v1"
EVIDENCE_SCHEMA = "wom-kit/source-intake-batch-session-evidence/v1"
PREPARED_SCHEMA = "wom-kit/source-intake-batch-retained-prepared/v1"
CONTEXT_SCHEMA = "wom-kit/source-intake-batch-original-context/v1"
PRIVATE_ROOT = ("profiles", "local", "exact-operations", "source-intake-contexts")
# Reuse the bounded control codec (32 MiB). This retains metadata/receipt and
# request bytes, never source bodies. Over-budget NEW scoped plans refuse;
# the existing 1-1000 item legacy route and its byte grammar are not changed.
MAX_BUNDLE_BYTES = controls.MAX_BUNDLE_BYTES
_ERRORS = frozenset({
    "work_session_intake_bundle_invalid", "work_session_intake_bundle_missing",
    "work_session_intake_bundle_changed", "work_session_intake_bundle_context_invalid",
    "work_session_intake_bundle_lock_required", "work_session_intake_bundle_path_unsafe",
    "work_session_intake_bundle_durability_unknown",
})
_SCOPE_KEYS = frozenset({
    "schema", "task_route_ref", "actor_sha256", "registry_preimage_sha256", "claim_ref",
    "work_session_binding", "original_establishment", "establishment_execution_sha256",
    "establishment_receipt_sha256", "unbound_manifest_sha256", "retained_input_sha256", "scope_sha256",
})
_INPUT_KEYS = frozenset({
    "archive_id", "request_path", "request_bytes", "request_bytes_sha256", "request_document_sha256",
    "batch_id", "items", "prepared_capture_request", "unbound_manifest",
})
_ITEM_KEYS = frozenset(field.name for field in fields(intake.SourceIntakeBatchExactItem))
_CAPTURE_KEYS = frozenset(field.name for field in fields(intake.PreparedObjetCaptureBatchRequest))
_ITEM_BYTES = frozenset({"receipt_bytes", "source_basis_bytes"})
_CAPTURE_BYTES = frozenset({"request_bytes", "source_basis_bytes"})


class WorkSessionIntakeBundleError(RuntimeError):
    def __init__(self, code="work_session_intake_bundle_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_intake_bundle_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_intake_bundle_invalid"
    try:
        return call()
    except WorkSessionIntakeBundleError as error:
        code = error.code
    except Exception:
        pass
    # Neither private rejected inputs nor OS/parser/callback exceptions escape.
    raise WorkSessionIntakeBundleError(code)


def _canonical(value):
    raw = controls._canonical(value)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise WorkSessionIntakeBundleError()
    return raw


def _sha(value):
    return controls._sha(_canonical(value))


def _bytes(value, *, maximum):
    if type(value) is not str or not value or len(value) > 4 * ((maximum + 2) // 3):
        raise WorkSessionIntakeBundleError()
    raw = base64.b64decode(value, validate=True)
    if not raw or len(raw) > maximum or base64.b64encode(raw).decode("ascii") != value:
        raise WorkSessionIntakeBundleError()
    return raw


def _encoded(raw):
    if type(raw) is not bytes or not raw:
        raise WorkSessionIntakeBundleError()
    return base64.b64encode(raw).decode("ascii")


def _absolute_path(value):
    if type(value) is not str or not 1 <= len(value) <= 32768 or "\0" in value or not Path(value).is_absolute():
        raise WorkSessionIntakeBundleError()
    return Path(value)


def _relative(value):
    if type(value) is not str or intake.normalize_archive_relative_path(value) != value:
        raise WorkSessionIntakeBundleError()
    return value


def _record_document(record, expected_type, byte_fields):
    if type(record) is not expected_type:
        raise WorkSessionIntakeBundleError()
    result = {}
    for field in fields(expected_type):
        value = getattr(record, field.name)
        if field.name in byte_fields:
            value = _encoded(value)
        elif field.name == "source_path":
            value = str(value)
        elif field.name == "warnings":
            value = list(value)
        result[field.name] = value
    return result


def _input_document(plan, request_bytes):
    if (type(plan) is not intake.SourceIntakeBatchExactPlan or not plan.approveable
            or type(plan.manifest) is not exact.ExactOperationManifest
            or plan.manifest.work_session_binding is not None):
        raise WorkSessionIntakeBundleError()
    intake._require_legacy_unbound_plan(plan)
    if (type(request_bytes) is not bytes or not 1 <= len(request_bytes) <= intake._MAX_REQUEST_BYTES
            or type(plan.items) is not tuple or not 1 <= len(plan.items) <= intake._MAX_ITEMS
            or type(plan.prepared_capture_request) is not intake.PreparedObjetCaptureBatchRequest):
        raise WorkSessionIntakeBundleError()
    # Count the complete encoded byte budget BEFORE allocating any base64
    # copies. A malformed in-memory plan cannot multiply per-item maxima into
    # gigabytes. The canonical envelope receives a second exact total check.
    payloads = [request_bytes, plan.prepared_capture_request.request_bytes,
                plan.prepared_capture_request.source_basis_bytes]
    for item in plan.items:
        if type(item) is not intake.SourceIntakeBatchExactItem:
            raise WorkSessionIntakeBundleError()
        payloads.extend((item.receipt_bytes, item.source_basis_bytes))
    if (any(type(raw) is not bytes or not raw or len(raw) > intake._MAX_RECEIPT_BYTES for raw in payloads)
            or sum(4 * ((len(raw) + 2) // 3) for raw in payloads) > MAX_BUNDLE_BYTES):
        raise WorkSessionIntakeBundleError()
    return {
        "archive_id": plan.archive_id, "request_path": str(plan.request_path),
        "request_bytes": _encoded(request_bytes), "request_bytes_sha256": plan.request_bytes_sha256,
        "request_document_sha256": plan.request_document_sha256, "batch_id": plan.batch_id,
        "items": [_record_document(item, intake.SourceIntakeBatchExactItem, _ITEM_BYTES) for item in plan.items],
        "prepared_capture_request": _record_document(plan.prepared_capture_request,
            intake.PreparedObjetCaptureBatchRequest, _CAPTURE_BYTES),
        "unbound_manifest": plan.manifest.document(),
    }


def _decode_item(root, value, raw_item, ordinal, archive_id, request_sha):
    if type(value) is not dict or set(value) != _ITEM_KEYS:
        raise WorkSessionIntakeBundleError()
    values = dict(value)
    for name in _ITEM_BYTES:
        values[name] = _bytes(values[name], maximum=intake._MAX_RECEIPT_BYTES)
    values["source_path"] = _absolute_path(values["source_path"])
    for name in _ITEM_KEYS:
        if name.endswith("_sha256") and not registry._is_digest(values[name]):
            raise WorkSessionIntakeBundleError()
    warnings = values["warnings"]
    if (type(warnings) is not list or any(type(warning) is not str for warning in warnings)
            or len(warnings) > 1000 or type(values["ordinal"]) is not int or values["ordinal"] != ordinal
            or type(values["source_size_bytes"]) is not int
            or not 0 <= values["source_size_bytes"] <= intake._MAX_SOURCE_BYTES
            or values["target_state"] != "ready_to_create"
            or values["request_item_id"] != raw_item["item_id"]
            or values["request_item_sha256"] != intake._sha_document(raw_item)
            or values["capture_title"] != raw_item.get("title")):
        raise WorkSessionIntakeBundleError()
    values["warnings"] = tuple(warnings)
    staged = _relative(values["capture_staged_path"])
    source = Path(raw_item["local_path"])
    # Absolute caller paths can have a different original OS spelling (for
    # example Windows short names). Their exact raw spelling AND the planner's
    # resolved path are scope-bound; do not resolve missing inputs during load.
    if not source.is_absolute():
        relative = intake.normalize_archive_relative_path(raw_item["local_path"])
        if values["source_path"] != root.joinpath(*relative.split("/")):
            raise WorkSessionIntakeBundleError()
    if (values["source_path"] != root.joinpath(*staged.split("/"))
            or values["source_path_binding_sha256"] != intake._sha_bytes(
                os.path.normcase(str(values["source_path"].absolute())).encode("utf-8"))):
        raise WorkSessionIntakeBundleError()
    document, receipt_plan_sha = intake.source_intake_record_exact._validated_plan_document(
        values["receipt_bytes"], archive_id=archive_id)
    if (intake._receipt_bytes(document) != values["receipt_bytes"]
            or receipt_plan_sha != values["source_intake_plan_sha256"]
            or values["receipt_relative_path"] != intake.archive_services.source_intake_record_path(receipt_plan_sha)
            or document["source_metadata"]["size_bytes"] != values["source_size_bytes"]
            or tuple(document["warnings"]) != values["warnings"]):
        raise WorkSessionIntakeBundleError()
    _relative(values["receipt_relative_path"])
    item_digest = intake.hashlib.sha256((raw_item["item_id"] + "\0" + values["request_item_sha256"]).encode("utf-8")).hexdigest()[:20]
    if values["operation_item_id"] != f"item:source-intake:{ordinal:04d}:{item_digest}":
        raise WorkSessionIntakeBundleError()
    basis = intake._strict_json_object(values["source_basis_bytes"])
    expected = {
        "schema": "wom-kit/source-intake-batch-exact-source/v0.1",
        "archive_identity_sha256": approval.exact_human_approval_archive_identity_sha256(archive_id),
        "request_bytes_sha256": request_sha,
        **{name: values[name] for name in ("request_item_sha256", "source_path_binding_sha256",
            "source_physical_identity_sha256", "source_bytes_sha256", "source_size_bytes",
            "source_file_identity_sha256", "source_intake_plan_sha256")},
        "receipt_bytes_sha256": intake._sha_bytes(values["receipt_bytes"]),
        "target_ref_sha256": intake._sha_bytes(values["receipt_relative_path"].encode("utf-8")),
        "warning_set_sha256": intake._sha_document(list(values["warnings"])),
    }
    if basis != expected or intake._canonical_bytes(expected) != values["source_basis_bytes"]:
        raise WorkSessionIntakeBundleError()
    return intake.SourceIntakeBatchExactItem(**values)


def _decode_capture(value, items, archive_id, batch_id):
    if type(value) is not dict or set(value) != _CAPTURE_KEYS:
        raise WorkSessionIntakeBundleError()
    values = dict(value)
    for name in _CAPTURE_BYTES:
        values[name] = _bytes(values[name], maximum=intake._MAX_RECEIPT_BYTES)
    request = {"schema": intake.CAPTURE_REQUEST_SCHEMA, "batch_id": batch_id, "items": [
        {"item_id": item.request_item_id, "staged_path": item.capture_staged_path,
         "source_intake_receipt_path": item.receipt_relative_path,
         **({"title": item.capture_title} if item.capture_title is not None else {})} for item in items]}
    raw = intake._canonical_bytes(request) + b"\n"
    request_sha = intake._sha_bytes(raw)
    chain = intake.intake_capture_chain_binding_sha256(archive_id=archive_id, batch_id=batch_id,
        capture_request_sha256=request_sha, item_bindings=[intake._capture_item_binding(item) for item in items])
    if (values["request_bytes"] != raw or values["request_sha256"] != request_sha
            or values["chain_binding_sha256"] != chain or values["target_state"] != "ready_to_create"
            or values["operation_item_id"] != "item:source-intake:capture-request:" + request_sha[7:27]
            or values["relative_path"] != f"{intake.CAPTURE_REQUESTS_ROOT}/{request_sha[7:]}.objet-capture-request.json"
            or values["source_basis_bytes"] != intake._canonical_bytes({
                "schema": "wom-kit/source-intake-capture-request-source/v0.1",
                "capture_request_sha256": request_sha, "chain_binding_sha256": chain})):
        raise WorkSessionIntakeBundleError()
    return intake.PreparedObjetCaptureBatchRequest(**values)


def _decode_input(root, document):
    if (type(root) is not type(Path()) or not root.is_absolute()
            or type(document) is not dict or set(document) != _INPUT_KEYS or type(document["archive_id"]) is not str):
        raise WorkSessionIntakeBundleError()
    raw = _bytes(document["request_bytes"], maximum=intake._MAX_REQUEST_BYTES)
    request = intake._strict_json_object(raw)
    batch_id, rows = intake._validate_request(request)
    if (document["request_bytes_sha256"] != intake._sha_bytes(raw)
            or document["request_document_sha256"] != intake._sha_document(request)
            or document["batch_id"] != batch_id or type(document["items"]) is not list
            or len(document["items"]) != len(rows)):
        raise WorkSessionIntakeBundleError()
    items = tuple(_decode_item(root, value, row, index, document["archive_id"], document["request_bytes_sha256"])
                  for index, (value, row) in enumerate(zip(document["items"], rows)))
    artifact = _decode_capture(document["prepared_capture_request"], items, document["archive_id"], batch_id)
    manifest = exact.ExactOperationManifest.from_document(document["unbound_manifest"])
    if (manifest.operation != intake.OPERATION or manifest.work_session_binding is not None
            or manifest.archive_identity_sha256 != approval.exact_human_approval_archive_identity_sha256(document["archive_id"])
            or len(manifest.items) != len(items) + 1
            or len({item.source_physical_identity_sha256 for item in items}) != len(items)):
        raise WorkSessionIntakeBundleError()
    plan = intake.SourceIntakeBatchExactPlan(root, document["archive_id"], _absolute_path(document["request_path"]),
        document["request_bytes_sha256"], document["request_document_sha256"], batch_id,
        items, artifact, manifest, "ready", ())
    intake._require_legacy_unbound_plan(plan)
    targets = [(item.operation_item_id, item.receipt_relative_path, intake.TARGET_KIND, intake.FIELD_REF) for item in items]
    targets.append((artifact.operation_item_id, artifact.relative_path, intake.CAPTURE_REQUEST_TARGET_KIND, intake.CAPTURE_REQUEST_FIELD_REF))
    for index, (operation, expected) in enumerate(zip(manifest.items, targets)):
        if (operation.ordinal != index or (operation.item_id, operation.target_ref, operation.target_kind,
                operation.fields[0].field_ref) != expected or len(operation.fields) != 1):
            raise WorkSessionIntakeBundleError()
        target_schema = ("wom-kit/source-intake-batch-exact-target/v0.1" if index < len(items)
                         else "wom-kit/source-intake-capture-request-target/v0.1")
        if operation.target_identity_sha256 != intake._sha_document({"schema": target_schema,
                "archive_identity_sha256": manifest.archive_identity_sha256, "target_ref": operation.target_ref}):
            raise WorkSessionIntakeBundleError()
    exact._validate_payloads(tuple((item, item.fields) for item in manifest.items), intake._Payloads(plan), heartbeat=lambda: None)
    expected_evidence = intake._source_intake_batch_operation_evidence(items=items,
        request_bytes_sha256=plan.request_bytes_sha256, request_document_sha256=plan.request_document_sha256,
        prepared_capture_request=artifact)
    if manifest.operation_evidence.document() != expected_evidence:
        raise WorkSessionIntakeBundleError()
    return plan, {row["item_id"]: row for row in rows}


def _scope_document(raw):
    value = controls._strict_document(raw)
    if set(value) != _SCOPE_KEYS or value["schema"] != SCOPE_SCHEMA:
        raise WorkSessionIntakeBundleError()
    for name in _SCOPE_KEYS:
        if name.endswith("_sha256") and not registry._is_digest(value[name]):
            raise WorkSessionIntakeBundleError()
    if not registry._ref(value["task_route_ref"], "task_route") or not registry._ref(value["claim_ref"], "claim"):
        raise WorkSessionIntakeBundleError()
    WorkSessionBinding.from_document(value["work_session_binding"])
    EstablishmentSelector.from_document(value["original_establishment"])
    if value["scope_sha256"] != _sha({name: field for name, field in value.items() if name != "scope_sha256"}):
        raise WorkSessionIntakeBundleError()
    return value


@dataclass(frozen=True, slots=True, repr=False)
class _SourceIntakeBatchSessionScope:
    """Exact historical fields; their validity is not current-owner authority."""
    _raw: bytes

    def __post_init__(self):
        _safe_call(lambda: _scope_document(self._raw))

    def __repr__(self):
        return "<private intake scope; no approval or ownership authority>"

    def document(self):
        return _safe_call(lambda: _scope_document(self._raw))

    @classmethod
    def build(cls, *, plan, request_bytes, work_session_binding, task_route_ref, actor_sha256,
              registry_preimage_sha256, claim_ref, original_establishment,
              establishment_execution_sha256, establishment_receipt_sha256):
        def build():
            if type(work_session_binding) is not WorkSessionBinding or type(original_establishment) is not EstablishmentSelector:
                raise WorkSessionIntakeBundleError()
            data = _input_document(plan, request_bytes)
            _decode_input(plan.archive_root, data)
            if work_session_binding.archive_identity_sha256 != plan.manifest.archive_identity_sha256:
                raise WorkSessionIntakeBundleError()
            basis = {"schema": SCOPE_SCHEMA, "work_session_binding": work_session_binding.document(),
                "task_route_ref": task_route_ref, "actor_sha256": actor_sha256,
                "registry_preimage_sha256": registry_preimage_sha256, "claim_ref": claim_ref,
                "original_establishment": original_establishment.document(),
                "establishment_execution_sha256": establishment_execution_sha256,
                "establishment_receipt_sha256": establishment_receipt_sha256,
                "unbound_manifest_sha256": plan.manifest.manifest_sha256, "retained_input_sha256": _sha(data)}
            return cls(_canonical({**basis, "scope_sha256": _sha(basis)}))
        return _safe_call(build)


def _decode_prepared(root, raw):
    document = controls._strict_document(raw)
    if set(document) != {"schema", "input", "scope", "manifest"} or document["schema"] != PREPARED_SCHEMA:
        raise WorkSessionIntakeBundleError()
    plan, request_items = _decode_input(root, document["input"])
    scope = _SourceIntakeBatchSessionScope(_canonical(document["scope"]))
    value = scope.document()
    binding = WorkSessionBinding.from_document(value["work_session_binding"])
    if (value["retained_input_sha256"] != _sha(document["input"])
            or value["unbound_manifest_sha256"] != plan.manifest.manifest_sha256
            or binding.archive_identity_sha256 != plan.manifest.archive_identity_sha256):
        raise WorkSessionIntakeBundleError()
    evidence = plan.manifest.operation_evidence.document()
    evidence["schema"] = EVIDENCE_SCHEMA
    evidence["digests"]["session_scope_sha256"] = value["scope_sha256"]
    manifest = exact.ExactOperationManifest.build(operation=plan.manifest.operation,
        archive_identity_sha256=plan.manifest.archive_identity_sha256, items=plan.manifest.items,
        operation_evidence=evidence, work_session_binding=binding)
    if manifest.document() != document["manifest"]:
        raise WorkSessionIntakeBundleError()
    return replace(plan, manifest=manifest), scope, request_items


@dataclass(frozen=True, slots=True, repr=False)
class PreparedSessionSourceIntakeBatch:
    _root: Path
    _raw: bytes

    def __post_init__(self):
        _safe_call(lambda: _decode_prepared(self._root, self._raw))

    def __repr__(self):
        return "<private retained intake preparation; not approval or current source verification>"

    @property
    def plan(self):
        return _safe_call(lambda: _decode_prepared(self._root, self._raw)[0])

    @property
    def scope(self):
        return _safe_call(lambda: _decode_prepared(self._root, self._raw)[1])

    def request_items(self):
        """Detached ORIGINAL rows, not a replacement request or source proof."""
        return _safe_call(lambda: _decode_prepared(self._root, self._raw)[2])


def _prepare_session_source_intake_batch(plan, *, request_bytes, scope):
    def prepare():
        if type(scope) is not _SourceIntakeBatchSessionScope:
            raise WorkSessionIntakeBundleError()
        data, owner = _input_document(plan, request_bytes), scope.document()
        evidence = plan.manifest.operation_evidence.document()
        evidence["schema"] = EVIDENCE_SCHEMA
        evidence["digests"]["session_scope_sha256"] = owner["scope_sha256"]
        manifest = exact.ExactOperationManifest.build(operation=plan.manifest.operation,
            archive_identity_sha256=plan.manifest.archive_identity_sha256, items=plan.manifest.items,
            operation_evidence=evidence, work_session_binding=WorkSessionBinding.from_document(owner["work_session_binding"]))
        return PreparedSessionSourceIntakeBatch(plan.archive_root, _canonical({"schema": PREPARED_SCHEMA,
            "input": data, "scope": owner, "manifest": manifest.document()}))
    return _safe_call(prepare)


def _factory_context(prepared, context):
    if type(context) is not ExactHumanApprovalContext:
        raise WorkSessionIntakeBundleError("work_session_intake_bundle_context_invalid")
    expected = intake.approval_context(prepared.plan, reviewer_claim=context.reviewer_claim)
    if approval.exact_human_approval_context_sha256(expected) != approval.exact_human_approval_context_sha256(context):
        raise WorkSessionIntakeBundleError("work_session_intake_bundle_context_invalid")
    return expected


def _decode_context(root, raw, manifest_sha256):
    document = controls._strict_document(raw)
    if (set(document) != {"schema", "prepared", "context", "context_sha256", "bundle_sha256"}
            or document["schema"] != CONTEXT_SCHEMA or not registry._is_digest(manifest_sha256)
            or document["bundle_sha256"] != _sha({key: value for key, value in document.items() if key != "bundle_sha256"})):
        raise WorkSessionIntakeBundleError()
    prepared = PreparedSessionSourceIntakeBatch(root, _canonical(document["prepared"]))
    value = document["context"]
    if (type(value) is not dict or set(value) != controls._CONTEXT_KEYS
            or type(value["review_binding_codes"]) is not list or type(value["warning_codes"]) is not list):
        raise WorkSessionIntakeBundleError("work_session_intake_bundle_context_invalid")
    context = ExactHumanApprovalContext(operation=ExactHumanApprovalOperation(value["operation"]),
        archive_identity_sha256=value["archive_identity_sha256"], plan_sha256=value["plan_sha256"],
        target_binding_sha256=value["target_binding_sha256"], reviewer_claim=value["reviewer_claim"],
        review_binding_codes=tuple(value["review_binding_codes"]), warning_codes=tuple(value["warning_codes"]))
    context = _factory_context(prepared, context)
    if (prepared.plan.manifest.manifest_sha256 != manifest_sha256
            or approval.exact_human_approval_context_sha256(context) != document["context_sha256"]):
        raise WorkSessionIntakeBundleError("work_session_intake_bundle_context_invalid")
    return prepared, context


@dataclass(frozen=True, slots=True, repr=False)
class ContextBoundSourceIntakeBatch:
    _root: Path
    _raw: bytes
    _manifest_sha256: str

    def __post_init__(self):
        _safe_call(lambda: _decode_context(self._root, self._raw, self._manifest_sha256))

    def __repr__(self):
        return "<private original intake context; no approval, ownership or completion authority>"

    @property
    def prepared(self):
        return _safe_call(lambda: _decode_context(self._root, self._raw, self._manifest_sha256)[0])

    @property
    def context(self):
        return _safe_call(lambda: _decode_context(self._root, self._raw, self._manifest_sha256)[1])


def _held_root(root, held):
    if type(held) is not exact.ExactOperationWriterLock:
        raise WorkSessionIntakeBundleError("work_session_intake_bundle_lock_required")
    try:
        actual, archive_id = approval._archive_identity(root)
        held.verify_held()
        if os.path.samefile(actual, held.archive_root):
            return actual, archive_id
    except Exception:
        pass
    raise WorkSessionIntakeBundleError("work_session_intake_bundle_lock_required")


def _directory(root):
    current = root
    for part in PRIVATE_ROOT:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return None
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
            raise WorkSessionIntakeBundleError("work_session_intake_bundle_path_unsafe")
    return current


def _read_raw(root, manifest_sha256):
    if not registry._is_digest(manifest_sha256):
        raise WorkSessionIntakeBundleError()
    directory = _directory(root)
    if directory is None:
        raise WorkSessionIntakeBundleError("work_session_intake_bundle_missing")
    try:
        return controls._read_control(directory / (manifest_sha256[7:] + ".json"), maximum=MAX_BUNDLE_BYTES)
    except FileNotFoundError:
        pass
    raise WorkSessionIntakeBundleError("work_session_intake_bundle_missing")


def _flush_chain(root):
    paths = [root]
    for part in PRIVATE_ROOT:
        paths.append(paths[-1] / part)
    with ExitStack() as stack:
        bindings = [stack.enter_context(durable._bound_directory_for_move(path)) for path in paths]
        for path, binding in reversed(list(zip(paths, bindings))):
            durable._assert_named_reservation_directory_identity(path, binding.identity)
            durable._require_directory_durable(path)
            durable._assert_named_reservation_directory_identity(path, binding.identity)
        for path, binding in zip(paths, bindings):
            durable._assert_named_reservation_directory_identity(path, binding.identity)


def _load_original_source_intake_context_held(root, *, manifest_sha256, held):
    def load():
        actual, archive_id = _held_root(root, held)
        raw = _read_raw(actual, manifest_sha256)
        bound = ContextBoundSourceIntakeBatch(actual, raw, manifest_sha256)
        if bound.prepared.plan.archive_id != archive_id:
            raise WorkSessionIntakeBundleError()
        if _read_raw(actual, manifest_sha256) != raw:
            raise WorkSessionIntakeBundleError("work_session_intake_bundle_changed")
        _held_root(actual, held)
        return bound
    return _safe_call(load)


def _save_original_source_intake_context_held(prepared, *, context, held):
    def save():
        if type(prepared) is not PreparedSessionSourceIntakeBatch:
            raise WorkSessionIntakeBundleError()
        # Detach before any filesystem callback; frozen dataclasses alone do
        # not protect caller-owned objects against object.__setattr__.
        frozen = PreparedSessionSourceIntakeBatch(prepared._root, prepared._raw)
        original_context = _factory_context(frozen, context)
        actual, archive_id = _held_root(frozen._root, held)
        if frozen.plan.archive_id != archive_id:
            raise WorkSessionIntakeBundleError()
        manifest_sha = frozen.plan.manifest.manifest_sha256
        basis = {"schema": CONTEXT_SCHEMA, "prepared": controls._strict_document(frozen._raw),
            "context": controls._context_document(original_context),
            "context_sha256": approval.exact_human_approval_context_sha256(original_context)}
        raw = _canonical({**basis, "bundle_sha256": _sha(basis)})
        ContextBoundSourceIntakeBatch(actual, raw, manifest_sha)
        directory = _directory(actual)
        if directory is not None and os.path.lexists(directory / (manifest_sha[7:] + ".json")):
            if _read_raw(actual, manifest_sha) != raw:
                raise WorkSessionIntakeBundleError("work_session_intake_bundle_changed")
            _decode_context(actual, raw, manifest_sha)
            try:
                _flush_chain(actual)
            except Exception:
                raise WorkSessionIntakeBundleError("work_session_intake_bundle_durability_unknown")
        else:
            try:
                directory = exact._ensure_private_directory(actual, PRIVATE_ROOT)
                with durable._bound_directory_for_move(directory) as parent:
                    _flush_chain(actual)
                    pending = directory / (".pending_" + uuid.uuid4().hex)
                    destination = directory / (manifest_sha[7:] + ".json")
                    registry._write_private_pending(pending, raw, root=actual)
                    durable._require_directory_durable(directory)
                    if controls._read_control(pending, maximum=MAX_BUNDLE_BYTES) != raw:
                        raise WorkSessionIntakeBundleError("work_session_intake_bundle_changed")
                    _held_root(actual, held)
                    durable._assert_named_reservation_directory_identity(directory, parent.identity)
                    durable._atomic_move_file_no_replace(pending, destination, expected_parent_identity=parent.identity)
                    durable._require_directory_durable(directory)
                    durable._assert_named_reservation_directory_identity(directory, parent.identity)
            except WorkSessionIntakeBundleError:
                raise
            except Exception:
                raise WorkSessionIntakeBundleError("work_session_intake_bundle_durability_unknown")
        confirmed = _load_original_source_intake_context_held(actual, manifest_sha256=manifest_sha, held=held)
        if confirmed._raw != raw:
            raise WorkSessionIntakeBundleError("work_session_intake_bundle_changed")
        return confirmed
    return _safe_call(save)
