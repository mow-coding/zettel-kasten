"""Approval-bound external source staging; immutable originals, bounded streams."""
import hashlib
import os
from pathlib import Path
import stat


SCHEMA = "wom-kit/source-intake-batch-exact/v3"
TARGET_KIND = "source_intake_external_copy"
FIELD_REF = "verified_copy_token"


def relative_path(request_sha, ordinal, source_sha):
    return f"staging/incoming/source-intake/{request_sha[7:]}/{ordinal:04d}-{source_sha[7:]}.bin"


def external_items(plan_or_items, root=None):
    items = plan_or_items.items if root is None else plan_or_items
    return tuple(item for item in items if item.external_copy)


def token(item):
    from .source_intake_batch_exact import _canonical_bytes
    return _canonical_bytes({"schema": "wom-kit/external-copy-token/v1",
        "sha256": item.source_bytes_sha256, "size_bytes": item.source_size_bytes,
        "original_identity_sha256": item.source_file_identity_sha256})


def operation_items(root, archive_id, items, *, offset):
    from . import source_intake_batch_exact as intake
    from .exact_operation_manifest import ExactOperationItem, ExactFieldEffect, hash_field_value
    identity = intake.exact_human_approval_archive_identity_sha256(archive_id)
    return tuple(ExactOperationItem(ordinal=offset + index,
        item_id="item:external-copy:" + str(item.ordinal), target_kind=TARGET_KIND,
        target_ref=item.capture_staged_path,
        target_identity_sha256=intake._sha_document({"schema": "wom-kit/external-copy-target/v1",
            "archive_identity_sha256": identity, "target_ref": item.capture_staged_path}),
        fields=(ExactFieldEffect(field_ref=FIELD_REF, pre_sha256=hash_field_value(None),
            post_sha256=hash_field_value(token(item)), source_sha256=hash_field_value(item.source_basis_bytes)),))
        for index, item in enumerate(external_items(items, root)))


def state(root, item, heartbeat=lambda: None):
    from . import source_intake_batch_exact as intake
    target = root / item.capture_staged_path
    if not os.path.lexists(target):
        return "ready_to_create"
    try:
        sha, size, _identity, info = intake._stable_source_digest(target, heartbeat=heartbeat)
        if sha == item.source_bytes_sha256 and size == item.source_size_bytes and info.st_nlink == 1:
            return "exact_target_present"
    except (OSError, intake.SourceIntakeBatchExactError):
        pass
    return "target_collision"


def copy_approved(plan, item, *, heartbeat):
    from . import source_intake_batch_exact as intake, archive_services as services
    from .object_storage_restore import _atomic_move_file_no_replace
    target = plan.archive_root / item.capture_staged_path
    if state(plan.archive_root, item, heartbeat) != "ready_to_create":
        raise intake._fail("source_intake_batch_target_collision")
    source = item.source_path
    intake._reject_link_or_reparse_chain(source, code="source_intake_batch_source_invalid")
    source_stat = os.lstat(source)
    # Keep parent chains and the exact source descriptor held throughout the
    # copy. Prefix resumption never truncates or replaces foreign residue.
    with services._bound_directory_chain(Path(source.anchor), source.parent) as source_parent:
        with services._hold_bound_regular_file(source_parent, source, source_stat) as held_source:
            with services._activity_group_bound_directory_chain(plan.archive_root, target.parent, create=True):
                partial = target.with_suffix(".copying")
                flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                try:
                    descriptor = os.open(partial, flags | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    intake._reject_link_or_reparse_chain(partial, code="source_intake_batch_target_unsafe")
                    descriptor = os.open(partial, flags)
                try:
                    opened = os.fstat(descriptor)
                    named = os.lstat(partial)
                    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                            or not intake._same_file_identity(opened, named)
                            or opened.st_size > item.source_size_bytes):
                        raise intake._fail("source_intake_batch_target_collision")
                    digest, count = hashlib.sha256(), 0
                    # Hash and compare the entire retained prefix before append.
                    while count < opened.st_size:
                        heartbeat()
                        chunk = os.read(descriptor, min(1024 * 1024, opened.st_size - count))
                        if not chunk or os.read(held_source.descriptor, len(chunk)) != chunk:
                            raise intake._fail("source_intake_batch_target_collision")
                        digest.update(chunk)
                        count += len(chunk)
                    while True:
                        heartbeat()
                        chunk = os.read(held_source.descriptor, 1024 * 1024)
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > item.source_size_bytes:
                            raise intake._fail("source_intake_batch_source_drifted")
                        digest.update(chunk)
                        view = memoryview(chunk)
                        while view:
                            written = os.write(descriptor, view)
                            if written <= 0:
                                raise intake._fail("source_intake_batch_write_failed")
                            view = view[written:]
                    os.fsync(descriptor)
                    if ("sha256:" + digest.hexdigest() != item.source_bytes_sha256
                            or count != item.source_size_bytes
                            or not intake._same_file_identity(os.fstat(descriptor), os.lstat(partial))):
                        raise intake._fail("source_intake_batch_source_drifted")
                finally:
                    os.close(descriptor)
                sha, size, identity, _info = intake._stable_source_digest(source, heartbeat=heartbeat)
                if (sha != item.source_bytes_sha256 or size != item.source_size_bytes
                        or identity != item.source_file_identity_sha256):
                    raise intake._fail("source_intake_batch_source_drifted")
                _atomic_move_file_no_replace(partial, target)
                if state(plan.archive_root, item, heartbeat) != "exact_target_present":
                    raise intake._fail("source_intake_batch_target_collision")
