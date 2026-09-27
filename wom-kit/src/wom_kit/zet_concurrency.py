"""Common target coordination for existing exact-approved canonical writers."""
from functools import wraps
import hashlib
import json


def canonical_writer(function):
    @wraps(function)
    def wrapped(archive_root, **kwargs):
        from . import archive_services as services
        from .operation_target_leases import TargetLeases
        if kwargs.get("approve") is not True:
            return function(archive_root, **kwargs)
        try:
            services._require_exact_human_approval_inputs_before_archive_read(
                claim=kwargs.get("exact_human_approval_claim"),
                expected_plan_sha256=kwargs.get("expected_exact_approval_plan_sha256"),
                expected_target_binding_sha256=kwargs.get("expected_exact_approval_target_binding_sha256"))
        except services.ArchiveServiceError:
            # Preserve the existing content-free rejection before any root read.
            return function(archive_root, **kwargs)
        root = services.require_existing_archive_root(archive_root)
        identity = kwargs.get("zettel_id")
        if identity is None:
            # Restore selects its identity through the exact approved receipt.
            # The original writer repeats its complete validation under lease.
            path = services.resolve_zet_revision_restore_receipt_path(root, kwargs["receipt_path"])
            raw = services.read_zet_revision_file_bytes(path, "Zet revision restore source receipt")
            if "sha256:" + hashlib.sha256(raw).hexdigest() != kwargs["expected_receipt_sha256"]:
                return function(root, **kwargs)
            try:
                identity = json.loads(raw)["zettel_id"]
            except (ValueError, KeyError, TypeError):
                return function(root, **kwargs)
        if not isinstance(identity, str) or not services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(identity):
            return function(root, **kwargs)
        with TargetLeases(root, [("zet", identity)]):
            return function(root, **kwargs)
    return wrapped
