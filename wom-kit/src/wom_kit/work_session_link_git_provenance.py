"""Private classification of one session's zettel-objet link outputs for Git.

v0.4.66 (beta letter 184, part 2). A conversation that wrote zettel-objet
links under its work-session grant could not back those changes up through
the session-scoped Git route: nothing proved the changed files were its own.

What is authenticated with the archive receipt key (MAC):

- the approval claim: succeeded, operation ``zettel_objet_link``, its plan
  and target-binding digests, and the work session whose grant it used;
- the session-object-usage record written by that approved write: its whole
  bytes, bound to the same claim, naming the linked objet.

What is not MAC-bound and is therefore verified by content instead:

- the link receipt names the zettel. A receipt is accepted only when it is
  the single receipt that names an authenticated approval of this session,
  repeats that claim's context, plan and target digests, and links the objet
  of the authenticated usage record;
- the zettel change itself: Git's HEAD must hold exactly the preimage that
  the first receipt of the chain recorded (the retained before-snapshot is
  read and hashed), the worktree exactly the postimage of the last, every
  step of the chain must be an accepted receipt of this session, and the
  parsed difference between preimage and worktree must be nothing but the
  appended asset entries of those links plus ``updated_at``.

A zettel with any other pending edit, a link of another conversation, a gap
in the chain or an unreadable snapshot stays unselected. This adapter
performs no Git or network observation and never authorizes a write; the
approved writer revalidates every proof with its own claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from . import exact_human_approval as approval
from . import git_backup_session_scope as scope_codec
from . import git_backup_writer as writer
from . import work_session_git_provenance as snapshots
from . import work_session_registry as registry
from . import work_session_source_intake_bundle as bundle
from .exact_human_approval_windows import ExactHumanApprovalOperation
from .work_session_binding import WorkSessionBinding


_PRODUCER = scope_codec._LINK_PRODUCER
_KIND_ZETTEL = "linked_zettel_document"
_KIND_RECEIPT = "zettel_objet_link_receipt"
_KIND_SNAPSHOT = "zettel_link_before_snapshot"
_KIND_USAGE = "session_object_usage_record"
_USAGE_ROOT = "receipts/session-object-usage"
_LINK_ROOT = "receipts/objects/zettel-links"
_MAX_FILES = 20_000
_MAX_PROOFS = 8192
_MAX_PROOF_BYTES = 16 * 1024 * 1024
_MAX_RESULT_BYTES = 32 * 1024 * 1024
_MAX_USAGE_BYTES = 128 * 1024
_MAX_RECEIPT_BYTES = 64 * 1024
_MAX_ZETTEL_BYTES = 16 * 1024 * 1024
_MAX_CHAIN = 512
_ERRORS = frozenset({
    "work_session_link_git_invalid", "work_session_link_git_lock_required",
    "work_session_link_git_limit", "work_session_link_git_proof_unavailable",
    "work_session_link_git_evidence_unavailable",
})


class WorkSessionLinkGitProvenanceError(RuntimeError):
    def __init__(self, code="work_session_link_git_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_link_git_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_link_git_invalid"
    try:
        return call()
    except WorkSessionLinkGitProvenanceError as error:
        code = error.code
    except bundle.WorkSessionIntakeBundleError as error:
        if error.code == "work_session_intake_bundle_lock_required":
            code = "work_session_link_git_lock_required"
    except Exception:
        pass
    raise WorkSessionLinkGitProvenanceError(code)


def _canonical(value, maximum=_MAX_RESULT_BYTES):
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > maximum:
        raise WorkSessionLinkGitProvenanceError("work_session_link_git_limit")
    return raw


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _digest(value):
    return type(value) is str and registry._is_digest(value)


def _prefixed(value):
    """Receipts store bare hex; Git observations store ``sha256:<hex>``."""
    if type(value) is not str:
        return None
    candidate = value if value.startswith("sha256:") else "sha256:" + value
    return candidate if registry._is_digest(candidate) else None


# --------------------------------------------------------------- authenticators
class _KeyAuthenticator:
    """Read-only: the key stays inside one provider callback for the whole pass."""

    def __init__(self, root, key_provider):
        self.root, self.key_provider = root, key_provider

    def run(self, consumer):
        if self.key_provider is None:
            from .exact_human_approval_workflow import _production_key_provider
            provider = _production_key_provider()
        else:
            provider = self.key_provider

        def with_key(key):
            def session(reference, plan_sha256, target_sha256, payload, mac):
                return approval._audited_terminal_record_session_ref_core(
                    self.root, reference, expected_operation=ExactHumanApprovalOperation.zettel_objet_link,
                    expected_plan_sha256=plan_sha256, expected_target_binding_sha256=target_sha256,
                    payload=payload, expected_mac=mac, receipt_authentication_key=key)
            return consumer(session)
        return provider.use_key(self.root, with_key, create_if_missing=False)


class _ClaimAuthenticator:
    """The approved Git writer's own claim audits the original link claims."""

    def __init__(self, claim):
        if type(claim) is not approval._ClaimedExactHumanApproval:
            raise WorkSessionLinkGitProvenanceError()
        self.claim = claim

    def run(self, consumer):
        def session(reference, plan_sha256, target_sha256, payload, mac):
            return self.claim.exact_terminal_record_session_ref(
                reference, ExactHumanApprovalOperation.zettel_objet_link, plan_sha256, target_sha256, payload, mac)
        return consumer(session)


class _ImageAuthenticator:
    """No authentication: names the session each claim file states, for a
    before/after byte comparison only. Never used to select or to write."""

    def __init__(self, root):
        self.root = root

    def run(self, consumer):
        def session(reference, _plan, _target, _payload, _mac):
            try:
                path = Path(self.root).joinpath(*approval.CLAIMS_RELATIVE_ROOT.split("/"),
                                                reference["approval_id"] + ".json")
                document = json.loads(path.read_bytes())
                return document["session_presenter"]["work_session_ref"]
            except Exception:
                return None
        return consumer(session)


# --------------------------------------------------------------------- evidence
def _names(root, relative, suffix):
    from . import archive_services as services

    directory = services.archive_internal_path(root, relative)
    if not os.path.lexists(directory):
        return []
    if services.objet_capture_path_chain_blockers(root, relative) or not directory.is_dir():
        raise WorkSessionLinkGitProvenanceError("work_session_link_git_evidence_unavailable")
    names = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name.endswith(suffix) and entry.is_file(follow_symlinks=False):
                names.append(entry.name)
                if len(names) > _MAX_FILES:
                    raise WorkSessionLinkGitProvenanceError("work_session_link_git_limit")
    return sorted(names)


def _read(root, relative, maximum):
    from . import archive_services as services

    if services.objet_capture_path_chain_blockers(root, relative):
        return None
    raw, reason = services._bounded_stable_regular_file_read(
        services.archive_internal_path(root, relative), max_bytes=maximum)
    return None if reason is not None else raw


def _usage_approvals(root, archive_id, session_ref, authenticate, held):
    """Authenticated link approvals of ``session_ref`` from MAC'd usage records."""
    from . import work_session_git_coverage as coverage
    from .session_object_usage import SCHEMA, encoded

    names = _names(root, _USAGE_ROOT, ".json")
    coverage.add_total(len(names))
    approvals, seen = {}, set()
    for name in names:
        held.verify_held()
        coverage.tick()
        relative = _USAGE_ROOT + "/" + name
        raw = _read(root, relative, _MAX_USAGE_BYTES)
        if raw is None:
            continue
        try:
            document = json.loads(raw)
            payload, mac = document["payload"], document["mac"]
            reference = payload["approval"]
            approval_id = reference["approval_id"]
            if (set(document) != {"payload", "mac"} or payload.get("schema") != SCHEMA
                    or payload.get("operation") != "zettel_objet_link" or payload.get("archive_id") != archive_id
                    or payload.get("part") != 0 or payload.get("part_count") != 1
                    or name != approval_id + "-0.json" or encoded(document) != raw
                    or not _digest(payload.get("plan_sha256")) or not _digest(payload.get("target_binding_sha256"))
                    or type(payload.get("object_ids")) is not list
                    or any(not _digest(oid) for oid in payload["object_ids"])):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        if approval_id in seen:
            approvals.pop(approval_id, None)
            continue
        seen.add(approval_id)
        owner = authenticate(reference, payload["plan_sha256"], payload["target_binding_sha256"],
                             encoded(payload), mac)
        if owner != session_ref:
            continue
        approvals[approval_id] = {
            "approval_id": approval_id, "context_sha256": reference["context_sha256"],
            "plan_sha256": payload["plan_sha256"], "target_binding_sha256": payload["target_binding_sha256"],
            "object_ids": sorted(payload["object_ids"]),
            "usage_path": relative, "usage_sha256": _sha(raw), "usage_bytes": len(raw),
        }
    return approvals


def _link_receipts(root, archive_id, approvals, held):
    """The single schema-valid receipt of each authenticated approval."""
    from . import archive_services as services
    from . import completion_workflows as workflows
    from . import work_session_git_coverage as coverage

    names = [name for name in _names(root, _LINK_ROOT, ".json") if name.startswith("link.")]
    coverage.add_total(len(names))
    found, duplicated = {}, set()
    for name in names:
        held.verify_held()
        coverage.tick()
        relative = _LINK_ROOT + "/" + name
        if services.objet_capture_path_chain_blockers(root, relative):
            continue
        document, raw = workflows._read_validated_zettel_objet_link_receipt(
            services.archive_internal_path(root, relative), max_bytes=_MAX_RECEIPT_BYTES)
        if document is None or raw is None or document.get("schema") != workflows.ZETTEL_OBJET_LINK_RECEIPT_SCHEMA:
            continue
        try:
            operation = document["exact_human_approval"]
            reference = operation["exact_human_approval"]
            entry = approvals.get(reference["approval_id"])
            before, after = _prefixed(document["before_zettel_sha256"]), _prefixed(document["after_zettel_sha256"])
            if (entry is None or document.get("archive_id") != archive_id
                    or document.get("action") != "add_zettel_objet_link"
                    or reference.get("context_sha256") != entry["context_sha256"]
                    or operation.get("plan_sha256") != entry["plan_sha256"]
                    or operation.get("target_binding_sha256") != entry["target_binding_sha256"]
                    or document.get("object_id") not in entry["object_ids"]
                    or before is None or after is None or before == after
                    or type(document.get("zettel_path")) is not str
                    or type(document.get("before_snapshot_path")) is not str
                    or not document["before_snapshot_path"].startswith(_LINK_ROOT + "/snapshots/")
                    or type(document.get("role")) is not str):
                continue
        except (KeyError, TypeError):
            continue
        approval_id = entry["approval_id"]
        if approval_id in found or approval_id in duplicated:
            # One approval writes one receipt. Two receipts naming it prove
            # neither, so the approval yields no zettel or receipt output.
            found.pop(approval_id, None)
            duplicated.add(approval_id)
            continue
        found[approval_id] = {
            **entry, "receipt_path": relative, "receipt_sha256": _sha(raw), "receipt_bytes": len(raw),
            "zettel_path": document["zettel_path"], "object_id": document["object_id"], "role": document["role"],
            "before_sha256": before, "after_sha256": after, "snapshot_path": document["before_snapshot_path"],
        }
    return found


def _evidence_entry(link):
    return {name: link[name] for name in (
        "approval_id", "context_sha256", "plan_sha256", "target_binding_sha256",
        "usage_sha256", "receipt_sha256", "object_id")}


def _evidence_sha(links):
    return _sha(_canonical([_evidence_entry(link) for link in links], _MAX_PROOF_BYTES))


def _gather(root, held, binding, authenticator):
    """All accepted link evidence of ``binding``'s session. Private; holds paths."""
    actual, archive_id = bundle._held_root(root, held)
    if binding.archive_identity_sha256 != approval.exact_human_approval_archive_identity_sha256(archive_id):
        raise WorkSessionLinkGitProvenanceError()

    def consume(authenticate):
        approvals = _usage_approvals(actual, archive_id, binding.work_session_ref, authenticate, held)
        return approvals, _link_receipts(actual, archive_id, approvals, held)
    approvals, links = authenticator.run(consume)
    whole, zettels = {}, {}
    for approval_id, entry in sorted(approvals.items()):
        link = links.get(approval_id)
        # The usage record is MAC-bound to the claim on its own.
        whole[entry["usage_path"]] = {
            "output_kind": _KIND_USAGE, "sha256": entry["usage_sha256"], "size_bytes": entry["usage_bytes"],
            "evidence": [{**entry, "receipt_sha256": entry["usage_sha256"],
                          "object_id": entry["object_ids"][0] if entry["object_ids"] else "sha256:" + "0" * 64}],
        }
        if link is None:
            continue
        whole[entry["usage_path"]]["evidence"] = [link]
        if link["receipt_path"] in whole:
            raise WorkSessionLinkGitProvenanceError("work_session_link_git_proof_unavailable")
        whole[link["receipt_path"]] = {"output_kind": _KIND_RECEIPT, "sha256": link["receipt_sha256"],
                                       "size_bytes": link["receipt_bytes"], "evidence": [link]}
        zettels.setdefault(link["zettel_path"], []).append(link)
    for links_of_zettel in zettels.values():
        for link in links_of_zettel:
            # The before-snapshot is created once by the first link from a
            # given preimage; it is self-verifying by its content digest.
            raw = _read(actual, link["snapshot_path"], _MAX_ZETTEL_BYTES)
            if raw is not None and _sha(raw) == link["before_sha256"] and link["snapshot_path"] not in whole:
                whole[link["snapshot_path"]] = {"output_kind": _KIND_SNAPSHOT, "sha256": _sha(raw),
                                                "size_bytes": len(raw), "evidence": [link]}
    bundle._held_root(actual, held)
    return {"root": actual, "archive_id": archive_id, "approval_count": len(approvals),
            "receipt_count": len(links), "whole": whole, "zettels": zettels}


def _chain(links, head_sha256, worktree_sha256):
    """The unique run of this session's links from HEAD's bytes to the worktree's."""
    by_before = {}
    for link in links:
        if link["before_sha256"] in by_before:
            return None
        by_before[link["before_sha256"]] = link
    chain, current, visited = [], head_sha256, set()
    while current != worktree_sha256:
        link = by_before.get(current)
        if link is None or current in visited or len(chain) >= _MAX_CHAIN:
            return None
        visited.add(current)
        chain.append(link)
        current = link["after_sha256"]
    return chain or None


def _transition_is_only_these_links(preimage, postimage, chain):
    """Parsed difference: appended asset entries of ``chain`` and ``updated_at``."""
    from . import archive_services as services

    def parts(raw):
        text = raw.decode("utf-8")
        approval_text = text[1:] if text.startswith("﻿") else text
        boundary = services.parse_approval_zettel_content_boundary(text)
        match = services.FRONTMATTER_RE.match(approval_text)
        frontmatter = boundary.get("frontmatter")
        if boundary.get("state") != "readable" or type(frontmatter) is not dict or match is None:
            raise ValueError()
        return frontmatter, approval_text[match.end():], text.startswith("﻿")
    try:
        before, body_before, bom_before = parts(preimage)
        after, body_after, bom_after = parts(postimage)
    except Exception:
        # Any parse doubt is a refusal, never a pass.
        return False
    if body_before != body_after or bom_before != bom_after:
        return False
    ignored = {"assets", "updated_at"}
    if ({key: value for key, value in before.items() if key not in ignored}
            != {key: value for key, value in after.items() if key not in ignored}):
        return False
    old, new = before.get("assets", []), after.get("assets")
    if type(old) is not list or type(new) is not list or new[:len(old)] != old:
        return False
    added = new[len(old):]
    if len(added) != len(chain):
        return False
    for asset, link in zip(added, chain):
        if (type(asset) is not dict or set(asset) - {"object_id", "role", "label"}
                or asset.get("object_id") != link["object_id"] or asset.get("role") != link["role"]):
            return False
    return True


def _zettel_match(evidence, row):
    """(chain, head observation) when the row is exactly this session's links."""
    public = row["public_observation"]
    head, worktree = public["head"], public["worktree"]
    links = evidence["zettels"].get(row["path"])
    if (links is None or row["original_path"] is not None or public["operation"] != "modified"
            or head.get("state") != "blob" or worktree.get("state") != "regular_file"
            or not _digest(head.get("sha256")) or not _digest(worktree.get("sha256"))):
        return None
    chain = _chain(links, head["sha256"], worktree["sha256"])
    if chain is None:
        return None
    proof = {"head_file_sha256": head["sha256"], "head_file_bytes": head["bytes"],
             "whole_file_sha256": worktree["sha256"], "whole_file_bytes": worktree["bytes"]}
    if not scope_codec._modified_document_matches(public, proof):
        return None
    preimage = _read(evidence["root"], chain[0]["snapshot_path"], _MAX_ZETTEL_BYTES)
    postimage = _read(evidence["root"], row["path"], _MAX_ZETTEL_BYTES)
    if (preimage is None or postimage is None or _sha(preimage) != head["sha256"]
            or len(preimage) != head["bytes"] or _sha(postimage) != worktree["sha256"]
            or len(postimage) != worktree["bytes"]
            or not _transition_is_only_these_links(preimage, postimage, chain)):
        return None
    return chain, proof


def _proof(change_ref, path, kind, links, binding, *, whole_sha256, whole_bytes, head_sha256=None, head_bytes=None):
    return {"change_ref": change_ref, "producer": _PRODUCER, "output_kind": kind,
            "document_path_sha256": scope_codec._sha_text(path),
            "whole_file_sha256": whole_sha256, "whole_file_bytes": whole_bytes,
            "head_file_sha256": head_sha256, "head_file_bytes": head_bytes,
            "link_evidence_sha256": _evidence_sha(links), "link_count": len(links),
            "original_work_session_binding": binding.document()}


def _row_proof(evidence, row, binding):
    change_ref = row["public_observation"]["change_ref"]
    output = evidence["whole"].get(row["path"])
    if output is not None:
        worktree = row["public_observation"]["worktree"]
        if (snapshots._new_whole_receipt(row) and type(worktree["bytes"]) is int
                and worktree["sha256"] == output["sha256"] and worktree["bytes"] == output["size_bytes"]):
            return _proof(change_ref, row["path"], output["output_kind"], output["evidence"], binding,
                          whole_sha256=output["sha256"], whole_bytes=output["size_bytes"])
        return None
    matched = _zettel_match(evidence, row)
    if matched is None:
        return None
    chain, facts = matched
    return _proof(change_ref, row["path"], _KIND_ZETTEL, chain, binding,
                  whole_sha256=facts["whole_file_sha256"], whole_bytes=facts["whole_file_bytes"],
                  head_sha256=facts["head_file_sha256"], head_bytes=facts["head_file_bytes"])


# ------------------------------------------------------------------- selection
@dataclass(frozen=True, slots=True, repr=False)
class _LinkSelection:
    _raw: bytes

    def __repr__(self):
        return "<private link-output selection; not Git or write authority>"

    def _private_document(self):
        return json.loads(self._raw)

    def public_summary(self):
        data = self._private_document()
        proofs = data["proofs"]
        return {"state": "link_selection_classified", "selected_output_count": len(proofs),
                "selected_linked_zettel_count": sum(proof["output_kind"] == _KIND_ZETTEL for proof in proofs),
                "authenticated_link_approval_count": data["approval_count"],
                "accepted_link_receipt_count": data["receipt_count"],
                "linked_zettel_candidate_count": data["zettel_candidate_count"],
                "linked_zettel_not_selected_count": data["zettel_not_selected_count"],
                "private_values_echoed": False, "paths_echoed": False}


def _rows(private_changes):
    if type(private_changes) is not list:
        raise WorkSessionLinkGitProvenanceError()
    copied = json.loads(_canonical(private_changes, writer.GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES))
    if any(type(row) is not dict or type(row.get("path")) is not str
           or type(row.get("public_observation")) is not dict for row in copied):
        raise WorkSessionLinkGitProvenanceError()
    refs = [row["public_observation"].get("change_ref") for row in copied]
    if (any(type(ref) is not str or scope_codec._CHANGE_REF.fullmatch(ref) is None for ref in refs)
            or len(set(refs)) != len(refs)):
        raise WorkSessionLinkGitProvenanceError()
    return copied


def _evidence_held(root, held, binding, key_provider):
    """One authenticated pass per fresh preview or write (see work_session_git_coverage)."""
    from . import work_session_git_coverage as coverage

    shared = coverage.memo()
    if shared is not None and "link" in shared and shared["link"][0] == binding.document():
        return shared["link"][1]
    evidence = _gather(root, held, binding, _KeyAuthenticator(Path(root), key_provider))
    if shared is not None:
        shared["link"] = (binding.document(), evidence)
    return evidence


def _authenticated_output_inventory_held(root, held, binding, key_provider=None):
    """Candidate paths to inspect: (origins, outputs) in the shape of the other adapters."""
    def discover():
        if type(binding) is not WorkSessionBinding:
            raise WorkSessionLinkGitProvenanceError()
        evidence = _evidence_held(root, held, binding, key_provider)
        key = ("link", binding.work_session_ref)
        origins = {key: {"work_session_binding": binding.document()}}
        outputs = {path: (key, None) for path in (*evidence["whole"], *evidence["zettels"])}
        return origins, outputs
    return _safe_call(discover)


def _select_link_changes_held(root, *, held, snapshot, selected_binding, key_provider=None):
    def select():
        if type(selected_binding) is not WorkSessionBinding or type(snapshot) is not snapshots._GitChangeSnapshot:
            raise WorkSessionLinkGitProvenanceError()
        binding = WorkSessionBinding.from_document(selected_binding.document())
        rows = _rows(snapshot._document()["capture"]["private_changes"])
        evidence = _evidence_held(root, held, binding, key_provider)
        proofs, zettel_rows = [], 0
        for row in rows:
            zettel_rows += row["path"] in evidence["zettels"]
            proof = _row_proof(evidence, row, binding)
            if proof is not None:
                proofs.append(proof)
                if len(proofs) > _MAX_PROOFS:
                    raise WorkSessionLinkGitProvenanceError("work_session_link_git_limit")
        proofs.sort(key=lambda row: row["change_ref"])
        _canonical(proofs, _MAX_PROOF_BYTES)
        selected_zettels = sum(proof["output_kind"] == _KIND_ZETTEL for proof in proofs)
        return _LinkSelection(_canonical({
            "schema": "wom-kit/private-link-git-selection/v1", "proofs": proofs,
            "approval_count": evidence["approval_count"], "receipt_count": evidence["receipt_count"],
            "zettel_candidate_count": len(evidence["zettels"]),
            "zettel_not_selected_count": len(evidence["zettels"]) - selected_zettels,
            "zettel_rows_observed": zettel_rows}))
    return _safe_call(select)


# ----------------------------------------------------------------- revalidation
def _stored(proofs, private_changes):
    if type(proofs) is not list or not 1 <= len(proofs) <= _MAX_PROOFS:
        raise WorkSessionLinkGitProvenanceError()
    detached = json.loads(_canonical(proofs, _MAX_PROOF_BYTES))
    rows = {row["public_observation"]["change_ref"]: row for row in _rows(private_changes)}
    refs = set()
    for proof in detached:
        if (not scope_codec._is_link_proof(proof) or set(proof) != scope_codec._LINK_KEYS
                or proof["change_ref"] in refs or proof["change_ref"] not in rows
                or type(proof["original_work_session_binding"]) is not dict):
            raise WorkSessionLinkGitProvenanceError()
        refs.add(proof["change_ref"])
    return detached, rows


def _revalidate(root, held, proofs, private_changes, authenticator):
    detached, rows = _stored(proofs, private_changes)  # Detach before callbacks.
    bindings = {_canonical(proof["original_work_session_binding"]) for proof in detached}
    if len(bindings) != 1:
        raise WorkSessionLinkGitProvenanceError("work_session_link_git_proof_unavailable")
    binding = WorkSessionBinding.from_document(detached[0]["original_work_session_binding"])
    evidence = _gather(root, held, binding, authenticator)
    verified = []
    for proof in detached:
        observed = _row_proof(evidence, rows[proof["change_ref"]], binding)
        if observed != proof:
            raise WorkSessionLinkGitProvenanceError("work_session_link_git_proof_unavailable")
        verified.append(proof)
    return sorted(verified, key=lambda row: row["change_ref"])


def _revalidate_link_proofs_held(root, *, held, proofs, private_changes, key_provider=None):
    return _safe_call(lambda: _revalidate(root, held, proofs, private_changes,
                                          _KeyAuthenticator(Path(root), key_provider)))


def _revalidate_link_proofs_with_claim_held(root, *, held, proofs, private_changes, claim):
    return _safe_call(lambda: _revalidate(root, held, proofs, private_changes, _ClaimAuthenticator(claim)))


def _original_link_proof_images_held(root, *, held, proofs, private_changes):
    """Bytes-level image of the evidence behind the proofs; this does not authenticate."""
    def image():
        detached, rows = _stored(proofs, private_changes)
        binding = WorkSessionBinding.from_document(detached[0]["original_work_session_binding"])
        evidence = _gather(root, held, binding, _ImageAuthenticator(Path(root)))
        images = []
        for proof in detached:
            if _row_proof(evidence, rows[proof["change_ref"]], binding) != proof:
                raise WorkSessionLinkGitProvenanceError("work_session_link_git_proof_unavailable")
            images.append((proof["change_ref"], proof["link_evidence_sha256"], proof["whole_file_sha256"]))
        return tuple(sorted(images))
    return _safe_call(image)
