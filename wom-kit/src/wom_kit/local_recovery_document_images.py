"""Whole-document observations for the existing local recovery field CAS.

These digests are data, not ownership or approval. The session control must
bind them to its original human context before they can support provenance.
Git must additionally compare the original HEAD/index and current file; a
field completion alone cannot attribute pre-existing uncommitted changes.
"""

from . import local_recovery_execution as recovery


_KEYS = frozenset({"item_id", "target_ref", "relative_path", "pre_sha256", "pre_bytes",
                   "post_sha256", "post_bytes"})
MAX_IMAGE_DOCUMENT_BYTES = 8 * 1024 * 1024


def _invalid():
    return recovery.LocalRecoveryError("local_recovery_session_context_invalid")


def _validate(plan, images):
    """Validate a complete ordered map of this plan's canonical documents."""
    specs = tuple(spec for spec in plan.specs if spec.target_kind == "zettel")
    if type(images) is not list or len(images) != len(specs):
        raise _invalid()
    previous = {}
    for spec, row in zip(specs, images):
        if (type(row) is not dict or any(type(key) is not str for key in row) or set(row) != _KEYS
                or any(type(row[name]) is not str for name in ("item_id", "target_ref", "relative_path"))
                or row["item_id"] != spec.item_id or row["target_ref"] != spec.target_ref
                or row["relative_path"] != spec.target_relative
                or any(type(row[name]) is not str or recovery._SHA256_RE.fullmatch(row[name]) is None
                       for name in ("pre_sha256", "post_sha256"))
                or any(type(row[name]) is not int or not 0 < row[name] <= recovery.MAX_CANONICAL_BYTES
                       for name in ("pre_bytes", "post_bytes"))):
            raise _invalid()
        last = previous.get(spec.target_relative)
        if last is not None and (last["post_sha256"], last["post_bytes"]) != (row["pre_sha256"], row["pre_bytes"]):
            raise _invalid()
        previous[spec.target_relative] = row
    if len(recovery._canonical_bytes(images)) > MAX_IMAGE_DOCUMENT_BYTES:
        raise _invalid()
    return images


def _capture_held(plan, held):
    """Read actual whole preimages and use the same field replacement function."""
    with recovery._local_recovery_writer_lock(plan, held):
        if recovery.verify_local_recovery_state(plan, state="pre").get("all_match") is not True:
            raise recovery.LocalRecoveryError("local_recovery_plan_changed")
        current, rows = {}, []
        for spec in plan.specs:
            held.verify_held()
            if spec.target_kind != "zettel":
                continue
            if spec.target_relative not in current:
                _path, raw, _frontmatter, _body = recovery._zettel_snapshot(plan.archive_root, spec)
                current[spec.target_relative] = raw
            before = current[spec.target_relative]
            after = recovery._zettel_replacement(before, spec, spec.post_value)
            rows.append({"item_id": spec.item_id, "target_ref": spec.target_ref,
                "relative_path": spec.target_relative, "pre_sha256": recovery._sha(before), "pre_bytes": len(before),
                "post_sha256": recovery._sha(after), "post_bytes": len(after)})
            current[spec.target_relative] = after
        _validate(plan, rows)
        return rows


def _assert_replacement(row, *, before, after):
    """Check the actual CAS input; never regenerate bytes from digest data."""
    if (type(before) is not bytes or type(after) is not bytes
            or (recovery._sha(before), len(before)) != (row["pre_sha256"], row["pre_bytes"])
            or (recovery._sha(after), len(after)) != (row["post_sha256"], row["post_bytes"])):
        raise recovery.LocalRecoveryError("local_recovery_plan_changed")


def _matches_state_held(plan, images, *, state, held):
    """Observe whole bytes only; this is not authentication of their producer."""
    if state not in {"pre", "post"}:
        raise _invalid()
    _validate(plan, images)
    selected = {}
    for row in images:
        if state == "post" or row["relative_path"] not in selected:
            selected[row["relative_path"]] = row
    with recovery._local_recovery_writer_lock(plan, held):
        for relative, row in selected.items():
            held.verify_held()
            path = recovery.archive_services.archive_internal_path(plan.archive_root, relative)
            raw, reason = recovery.archive_services._bounded_stable_regular_file_read(
                path, max_bytes=recovery.MAX_CANONICAL_BYTES)
            if (reason is not None or raw is None
                    or (recovery._sha(raw), len(raw)) != (row[state + "_sha256"], row[state + "_bytes"])):
                return False
    return True
