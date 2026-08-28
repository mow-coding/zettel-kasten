"""Fail-closed internal evidence for direct zet--objet SHA transitions.

This module deliberately makes a narrow claim.  It can show that WOM's local
receipt set contains one unambiguous, byte-hash-bound transition chain.  It
does not authenticate the people or processes that produced those files and
does not claim MAC or signature verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any

from . import archive_services, completion_workflows


EXACT_BYTE_TRANSITION_INTERNAL_EVIDENCE = (
    "exact_byte_transition_internal_evidence"
)
TARGET_SHA_UNCHANGED = "target_sha_unchanged"
TARGET_SHA_MISMATCH_UNPROVEN = "target_sha_mismatch_unproven"
TARGET_SHA_EVOLUTION_QUERY_INVALID = "target_sha_evolution_query_invalid"
TARGET_SHA_EVOLUTION_INDEX_INCOMPLETE = (
    "target_sha_evolution_index_incomplete"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ZETTEL_PATH_RE = re.compile(r"^(?:inbox|zettels)/[^/]+\.md$")
_REVERT_RECEIPT_NAME_RE = re.compile(r"^(?P<prefix>[0-9a-f]{24})\.json$")

DEFAULT_MAX_DIRECTORY_ENTRIES = 100_000
DEFAULT_MAX_DIRECTORY_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_RECEIPT_BYTES = 64 * 1024


@dataclass(frozen=True)
class _LinkReceipt:
    archive_id: str
    zettel_id: str
    zettel_path: str
    before_sha256: str
    after_sha256: str
    created_at: str
    created_time: datetime
    receipt_sha256: str
    receipt_generation: int

    @property
    def target_key(self) -> tuple[str, str, str]:
        return (self.archive_id, self.zettel_id, self.zettel_path)


@dataclass(frozen=True)
class _Transition:
    archive_id: str
    zettel_id: str
    zettel_path: str
    before_sha256: str
    after_sha256: str
    created_at: str
    created_time: datetime
    kind: str
    receipt_sha256: str
    source_receipt_sha256: str | None

    @property
    def target_key(self) -> tuple[str, str, str]:
        return (self.archive_id, self.zettel_id, self.zettel_path)

    def chain_binding(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "created_at": self.created_at,
            "receipt_sha256": self.receipt_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
        }


@dataclass(frozen=True)
class ZettelObjetTargetShaEvolutionIndex:
    """One immutable, single-scan projection of local link evidence."""

    archive_id: str
    transitions_by_target: dict[
        tuple[str, str, str], tuple[_Transition, ...]
    ]
    blockers: tuple[str, ...]
    receipt_entry_count: int
    receipt_candidate_count: int
    validated_receipt_count: int
    revert_entry_count: int
    revert_candidate_count: int
    validated_revert_count: int

    @property
    def complete(self) -> bool:
        return not self.blockers

    def summary(self) -> dict[str, Any]:
        return {
            "schema": "wom-kit/target-sha-evolution-index-summary/v0.1",
            "complete": self.complete,
            "blockers": list(self.blockers),
            "receipt_counts": {
                "receipt_directory_entries": self.receipt_entry_count,
                "receipt_candidates": self.receipt_candidate_count,
                "validated_link_receipts": self.validated_receipt_count,
                "revert_directory_entries": self.revert_entry_count,
                "revert_candidates": self.revert_candidate_count,
                "validated_revert_receipts": self.validated_revert_count,
            },
        }

    def assess(
        self,
        *,
        archive_id: str,
        zettel_id: str,
        zettel_path: str,
        expected_sha256: str,
        current_sha256: str,
        cutoff_created_at: str,
    ) -> dict[str, Any]:
        """Explain a proof or the exact fail-closed reason it was withheld."""

        safe_zettel_id = completion_workflows._safe_zettel_id(zettel_id)
        safe_zettel_path = _normalize_zettel_path(zettel_path)
        expected = _safe_sha256(expected_sha256)
        current = _safe_sha256(current_sha256)
        cutoff = _parse_timestamp(cutoff_created_at)

        def assessment(
            state: str,
            reason_code: str,
            *,
            proven: bool = False,
            ambiguous: bool = False,
            target_transition_count: int = 0,
            eligible_transition_count: int = 0,
            evidence: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return {
                "schema": "wom-kit/target-sha-evolution-assessment/v0.1",
                "state": state,
                "reason_code": reason_code,
                "proven": proven,
                "ambiguous": ambiguous,
                "index": self.summary(),
                "cutoff": {
                    "applied": cutoff is not None,
                    "created_at": (
                        cutoff_created_at if cutoff is not None else None
                    ),
                    "eligible_transition_count": eligible_transition_count,
                },
                "target_transition_count": target_transition_count,
                "evidence": evidence,
            }

        if (
            archive_id != self.archive_id
            or safe_zettel_id is None
            or safe_zettel_path is None
            or expected is None
            or current is None
            or cutoff is None
        ):
            return assessment(
                TARGET_SHA_EVOLUTION_QUERY_INVALID,
                TARGET_SHA_EVOLUTION_QUERY_INVALID,
            )
        if expected == current:
            return assessment(
                TARGET_SHA_UNCHANGED,
                "expected_sha_matches_current_sha",
            )
        if not self.complete:
            return assessment(
                TARGET_SHA_EVOLUTION_INDEX_INCOMPLETE,
                TARGET_SHA_EVOLUTION_INDEX_INCOMPLETE,
                ambiguous=any(
                    "ambiguous" in blocker for blocker in self.blockers
                ),
            )

        key = (archive_id, safe_zettel_id, safe_zettel_path)
        target_transitions = self.transitions_by_target.get(key, ())
        eligible = tuple(
            transition
            for transition in target_transitions
            if transition.created_time > cutoff
        )
        if not eligible:
            return assessment(
                TARGET_SHA_MISMATCH_UNPROVEN,
                (
                    "no_validated_target_transitions"
                    if not target_transitions
                    else "no_target_transitions_after_cutoff"
                ),
                target_transition_count=len(target_transitions),
            )

        node = expected
        cursor = cutoff
        visited = {node}
        chain: list[_Transition] = []
        while True:
            outgoing = [
                transition
                for transition in eligible
                if transition.before_sha256 == node
                and transition.created_time > cursor
            ]
            if node == current:
                # A current digest is evidence only when it is the terminal
                # state.  A later outgoing receipt would contradict that.
                if not chain or outgoing:
                    return assessment(
                        TARGET_SHA_MISMATCH_UNPROVEN,
                        "current_sha_not_terminal",
                        ambiguous=len(outgoing) > 1,
                        target_transition_count=len(target_transitions),
                        eligible_transition_count=len(eligible),
                    )
                break
            if not outgoing:
                return assessment(
                    TARGET_SHA_MISMATCH_UNPROVEN,
                    (
                        "expected_sha_not_observed_after_cutoff"
                        if not chain
                        else "current_sha_not_reached"
                    ),
                    target_transition_count=len(target_transitions),
                    eligible_transition_count=len(eligible),
                )
            if len(outgoing) > 1:
                return assessment(
                    TARGET_SHA_MISMATCH_UNPROVEN,
                    "target_sha_transition_branch_ambiguous",
                    ambiguous=True,
                    target_transition_count=len(target_transitions),
                    eligible_transition_count=len(eligible),
                )
            transition = outgoing[0]
            if transition.after_sha256 in visited:
                return assessment(
                    TARGET_SHA_MISMATCH_UNPROVEN,
                    "target_sha_transition_cycle_ambiguous",
                    ambiguous=True,
                    target_transition_count=len(target_transitions),
                    eligible_transition_count=len(eligible),
                )
            chain.append(transition)
            node = transition.after_sha256
            cursor = transition.created_time
            visited.add(node)

        chain_binding = [transition.chain_binding() for transition in chain]
        chain_sha256 = hashlib.sha256(
            completion_workflows._canonical_json_bytes(chain_binding)
        ).hexdigest()
        evidence = {
            "state": EXACT_BYTE_TRANSITION_INTERNAL_EVIDENCE,
            "evidence_kind": EXACT_BYTE_TRANSITION_INTERNAL_EVIDENCE,
            "expected_sha256": expected,
            "current_sha256": current,
            "cutoff_created_at": cutoff_created_at,
            "transition_count": len(chain),
            "transition_kinds": [item.kind for item in chain],
            "transition_receipt_sha256s": [
                item.receipt_sha256 for item in chain
            ],
            "transition_chain_sha256": chain_sha256,
            "cryptographic_authentication": {
                "claimed": False,
                "mac_verified": False,
                "signature_verified": False,
            },
        }
        return assessment(
            EXACT_BYTE_TRANSITION_INTERNAL_EVIDENCE,
            EXACT_BYTE_TRANSITION_INTERNAL_EVIDENCE,
            proven=True,
            target_transition_count=len(target_transitions),
            eligible_transition_count=len(eligible),
            evidence=evidence,
        )

    def evidence(
        self,
        *,
        archive_id: str,
        zettel_id: str,
        zettel_path: str,
        expected_sha256: str,
        current_sha256: str,
        cutoff_created_at: str,
    ) -> dict[str, Any] | None:
        """Return only proven evidence; every other assessment yields None."""

        result = self.assess(
            archive_id=archive_id,
            zettel_id=zettel_id,
            zettel_path=zettel_path,
            expected_sha256=expected_sha256,
            current_sha256=current_sha256,
            cutoff_created_at=cutoff_created_at,
        )
        evidence = result.get("evidence")
        return evidence if isinstance(evidence, dict) and result["proven"] else None


def _safe_sha256(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if _SHA256_RE.fullmatch(text) else None


def _normalize_zettel_path(value: Any) -> str | None:
    try:
        normalized = archive_services.normalize_archive_relative_path(
            str(value or "")
        )
    except archive_services.ArchivePathError:
        return None
    if normalized != str(value or "") or not _ZETTEL_PATH_RE.fullmatch(
        normalized
    ):
        return None
    return normalized


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    try:
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _directory_generation(path: Path) -> tuple[int, ...]:
    observed = os.stat(path, follow_symlinks=False)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISDIR(observed.st_mode)
        or (
            reparse_flag
            and getattr(observed, "st_file_attributes", 0) & reparse_flag
        )
    ):
        raise OSError("target_sha_evolution_directory_unsafe")
    return (
        int(observed.st_mode),
        int(observed.st_dev),
        int(observed.st_ino),
        int(observed.st_size),
        int(observed.st_mtime_ns),
        int(observed.st_ctime_ns),
        int(getattr(observed, "st_birthtime_ns", 0)),
        int(getattr(observed, "st_file_attributes", 0)),
    )


def _scan_evidence_directory(
    root: Path,
    directory: Path,
    *,
    kind: str,
    max_entries: int,
    max_total_bytes: int,
    max_receipt_bytes: int,
) -> tuple[
    list[tuple[str, dict[str, Any], bytes]],
    int,
    int,
    list[str],
]:
    documents: list[tuple[str, dict[str, Any], bytes]] = []
    blockers: list[str] = []
    entry_count = 0
    candidate_names: list[str] = []
    try:
        with archive_services._activity_group_bound_directory_chain(
            root,
            directory,
        ) as parent_binding:
            before_generation = _directory_generation(directory)
            scan_target = (
                parent_binding["descriptor"]
                if parent_binding.get("descriptor") is not None
                else directory
            )
            with os.scandir(scan_target) as entries:
                for entry in entries:
                    entry_count += 1
                    if entry_count > max_entries:
                        blockers.append(
                            f"target_sha_evolution_{kind}_entry_limit_exceeded"
                        )
                        break
                    name = entry.name
                    match = (
                        completion_workflows
                        .ZETTEL_OBJET_LINK_RECEIPT_NAME_RE.fullmatch(name)
                        if kind == "receipt"
                        else _REVERT_RECEIPT_NAME_RE.fullmatch(name)
                    )
                    if match is not None:
                        candidate_names.append(name)
                    elif name.endswith(".json"):
                        blockers.append(
                            f"target_sha_evolution_{kind}_filename_invalid"
                        )

            total_bytes = 0
            if not blockers:
                for name in sorted(candidate_names):
                    candidate_path = directory / name
                    if kind == "receipt":
                        document, raw = (
                            completion_workflows
                            ._read_validated_zettel_objet_link_receipt(
                                candidate_path,
                                max_bytes=max_receipt_bytes,
                                bound_root=root,
                                parent_binding=parent_binding,
                            )
                        )
                    else:
                        document, raw = (
                            completion_workflows._read_validated_zettel_objet_link_json(
                                candidate_path,
                                schema_name=(
                                    "zettel-objet-link-revert-receipt.schema.json"
                                ),
                                schema_id=(
                                    completion_workflows
                                    .ZETTEL_OBJET_LINK_REVERT_RECEIPT_SCHEMA
                                ),
                                max_bytes=max_receipt_bytes,
                                bound_root=root,
                                parent_binding=parent_binding,
                            )
                        )
                    if document is None or raw is None:
                        blockers.append(
                            f"target_sha_evolution_{kind}_validation_failed"
                        )
                        continue
                    total_bytes += len(raw)
                    if total_bytes > max_total_bytes:
                        blockers.append(
                            f"target_sha_evolution_{kind}_byte_limit_exceeded"
                        )
                        break
                    documents.append((name, document, raw))

            after_generation = _directory_generation(directory)
            if after_generation != before_generation:
                blockers.append(
                    f"target_sha_evolution_{kind}_directory_changed"
                )
    except FileNotFoundError:
        return [], 0, 0, []
    except OSError:
        blockers.append(f"target_sha_evolution_{kind}_directory_unavailable")
    return documents, entry_count, len(candidate_names), _unique(blockers)


def _validated_link_receipt(
    *,
    archive_id: str,
    name: str,
    document: dict[str, Any],
    raw: bytes,
) -> _LinkReceipt | None:
    match = completion_workflows.ZETTEL_OBJET_LINK_RECEIPT_NAME_RE.fullmatch(
        name
    )
    zettel_id = completion_workflows._safe_zettel_id(document.get("zettel_id"))
    zettel_path = _normalize_zettel_path(document.get("zettel_path"))
    before_sha256 = _safe_sha256(document.get("before_zettel_sha256"))
    after_sha256 = _safe_sha256(document.get("after_zettel_sha256"))
    created_time = _parse_timestamp(document.get("created_at"))
    if (
        match is None
        or document.get("archive_id") != archive_id
        or zettel_id is None
        or zettel_path is None
        or before_sha256 is None
        or after_sha256 is None
        or before_sha256 == after_sha256
        or created_time is None
    ):
        return None

    generation = int(match.group("generation"))
    if generation < 1:
        return None
    if (
        document.get("schema")
        == completion_workflows.ZETTEL_OBJET_LINK_RECEIPT_SCHEMA
        and document.get("receipt_generation") != generation
    ):
        return None

    link_seed = {
        "archive_id": archive_id,
        "zettel_id": zettel_id,
        "object_id": document.get("object_id"),
        "role": document.get("role"),
    }
    link_digest = hashlib.sha256(
        completion_workflows._canonical_json_bytes(link_seed)
    ).hexdigest()
    if (
        match.group("prefix") != link_digest[:24]
        or document.get("link_id") != f"asset:sha256:{link_digest}"
        or document.get("before_snapshot_path")
        != (
            f"{completion_workflows.ZETTEL_OBJET_LINK_SNAPSHOT_DIR}/"
            f"{before_sha256}.zettel.md"
        )
    ):
        return None

    return _LinkReceipt(
        archive_id=archive_id,
        zettel_id=zettel_id,
        zettel_path=zettel_path,
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        created_at=str(document["created_at"]),
        created_time=created_time,
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        receipt_generation=generation,
    )


def build_zettel_objet_target_sha_evolution_index(
    archive_root: Path | str,
    *,
    max_directory_entries: int = DEFAULT_MAX_DIRECTORY_ENTRIES,
    max_directory_bytes: int = DEFAULT_MAX_DIRECTORY_BYTES,
    max_receipt_bytes: int = DEFAULT_MAX_RECEIPT_BYTES,
) -> ZettelObjetTargetShaEvolutionIndex:
    """Read each evidence directory once and build a fail-closed graph."""

    if (
        max_directory_entries < 1
        or max_directory_bytes < 1
        or max_receipt_bytes < 1
    ):
        raise ValueError("target_sha_evolution_scan_limit_invalid")
    root = Path(archive_root).resolve()
    if not root.is_dir():
        raise archive_services.ArchiveServiceError(
            "target_sha_evolution_archive_unavailable"
        )
    archive_id = completion_workflows._read_zettel_objet_archive_id(root)
    receipt_root = completion_workflows._zettel_objet_link_known_internal_path(
        root,
        completion_workflows.ZETTEL_OBJET_LINK_RECEIPTS_DIR,
    )
    revert_root = completion_workflows._zettel_objet_link_known_internal_path(
        root,
        f"{completion_workflows.ZETTEL_OBJET_LINK_RECEIPTS_DIR}/reverts",
    )

    (
        receipt_documents,
        receipt_entry_count,
        receipt_candidate_count,
        blockers,
    ) = (
        _scan_evidence_directory(
            root,
            receipt_root,
            kind="receipt",
            max_entries=max_directory_entries,
            max_total_bytes=max_directory_bytes,
            max_receipt_bytes=max_receipt_bytes,
        )
    )
    link_receipts: list[_LinkReceipt] = []
    for name, document, raw in receipt_documents:
        validated = _validated_link_receipt(
            archive_id=archive_id,
            name=name,
            document=document,
            raw=raw,
        )
        if validated is None:
            blockers.append("target_sha_evolution_receipt_binding_invalid")
        else:
            link_receipts.append(validated)

    source_receipts: dict[str, _LinkReceipt] = {}
    for receipt in link_receipts:
        if receipt.receipt_sha256 in source_receipts:
            blockers.append("target_sha_evolution_source_receipt_ambiguous")
        else:
            source_receipts[receipt.receipt_sha256] = receipt

    (
        revert_documents,
        revert_entry_count,
        revert_candidate_count,
        revert_blockers,
    ) = (
        _scan_evidence_directory(
            root,
            revert_root,
            kind="revert",
            max_entries=max_directory_entries,
            max_total_bytes=max_directory_bytes,
            max_receipt_bytes=max_receipt_bytes,
        )
    )
    blockers.extend(revert_blockers)

    transitions: list[_Transition] = [
        _Transition(
            archive_id=receipt.archive_id,
            zettel_id=receipt.zettel_id,
            zettel_path=receipt.zettel_path,
            before_sha256=receipt.before_sha256,
            after_sha256=receipt.after_sha256,
            created_at=receipt.created_at,
            created_time=receipt.created_time,
            kind="zettel_objet_link",
            receipt_sha256=receipt.receipt_sha256,
            source_receipt_sha256=None,
        )
        for receipt in link_receipts
    ]
    validated_revert_count = 0
    reverted_sources: set[str] = set()
    for name, document, raw in revert_documents:
        match = _REVERT_RECEIPT_NAME_RE.fullmatch(name)
        source_sha256 = _safe_sha256(document.get("source_receipt_sha256"))
        source = source_receipts.get(source_sha256 or "")
        created_time = _parse_timestamp(document.get("created_at"))
        if (
            match is None
            or source_sha256 is None
            or match.group("prefix") != source_sha256[:24]
            or source is None
            or source_sha256 in reverted_sources
            or document.get("archive_id") != source.archive_id
            or document.get("zettel_id") != source.zettel_id
            or document.get("restored_zettel_sha256")
            != source.before_sha256
            or created_time is None
            or created_time <= source.created_time
        ):
            blockers.append("target_sha_evolution_revert_binding_invalid")
            continue
        reverted_sources.add(source_sha256)
        validated_revert_count += 1
        transitions.append(
            _Transition(
                archive_id=source.archive_id,
                zettel_id=source.zettel_id,
                zettel_path=source.zettel_path,
                before_sha256=source.after_sha256,
                after_sha256=source.before_sha256,
                created_at=str(document["created_at"]),
                created_time=created_time,
                kind="zettel_objet_link_revert",
                receipt_sha256=hashlib.sha256(raw).hexdigest(),
                source_receipt_sha256=source_sha256,
            )
        )

    grouped: dict[tuple[str, str, str], list[_Transition]] = {}
    for transition in transitions:
        grouped.setdefault(transition.target_key, []).append(transition)
    frozen_grouped = {
        key: tuple(
            sorted(
                values,
                key=lambda item: (
                    item.created_time,
                    item.receipt_sha256,
                    item.kind,
                ),
            )
        )
        for key, values in grouped.items()
    }
    return ZettelObjetTargetShaEvolutionIndex(
        archive_id=archive_id,
        transitions_by_target=frozen_grouped,
        blockers=tuple(_unique(blockers)),
        receipt_entry_count=receipt_entry_count,
        receipt_candidate_count=receipt_candidate_count,
        validated_receipt_count=len(link_receipts),
        revert_entry_count=revert_entry_count,
        revert_candidate_count=revert_candidate_count,
        validated_revert_count=validated_revert_count,
    )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


__all__ = [
    "EXACT_BYTE_TRANSITION_INTERNAL_EVIDENCE",
    "TARGET_SHA_EVOLUTION_INDEX_INCOMPLETE",
    "TARGET_SHA_EVOLUTION_QUERY_INVALID",
    "TARGET_SHA_MISMATCH_UNPROVEN",
    "TARGET_SHA_UNCHANGED",
    "ZettelObjetTargetShaEvolutionIndex",
    "build_zettel_objet_target_sha_evolution_index",
]
