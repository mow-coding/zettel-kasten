"""Content-free private-index health orchestration for v0.3.297.

The durable authority, generated SQLite projection, and public archive health
have deliberately separate owners.  This module joins their closed evidence
without accepting a borrowed SQLite connection or exposing private values.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .private_objet_metadata_index import (
    PRIVATE_TABLE_NAMES,
    PrivateObjetIndexInspection,
    _PrivateObjetIndexProjection,
    _compile_private_objet_index_projection,
)
from .private_objet_metadata_index_authority import (
    _PrivateObjetIndexAuthorityCapture,
    _capture_private_objet_index_authority,
)
from .private_objet_metadata_index_session import (
    PRIVATE_HEALTH_KEYS,
    _PrivateObjetIndexReadAPI,
    PrivateObjetIndexSessionError,
    PrivateObjetMetadataCounts,
    PrivateObjetMetadataHealthDecision,
    _with_private_objet_index_read_session,
    append_private_objet_metadata_top_level_diagnostics,
    build_private_objet_metadata_health_envelope,
    validate_private_objet_metadata_health_envelope,
)


PUBLIC_INDEX_HEALTH_KEYS = (
    "ok",
    "dry_run",
    "lifecycle_action",
    "archive_id",
    "index_path",
    "index_state",
    "summary",
    "samples",
    "stale_reasons",
    "privacy_guards",
    "would_change",
    "next_safe_actions",
    "blockers",
    "warnings",
)

_CASE_TRANSLATIONS = {
    "C1": "search_incomplete",
    "C2": "search_incomplete",
    "C3": "blocked",
    "C4": "blocked",
    "C5": "search_incomplete",
    "C6": "search_incomplete",
    "C7": "blocked",
    "C8": "search_incomplete",
    "C9": "search_incomplete",
    "C10": "not_found_in_index",
    "C11": "query_allowed",
}
_DIAGNOSTIC_CASES = {
    "private_objet_metadata_snapshot_changed": "C1",
    "private_objet_metadata_authority_blocked": "C3",
    "private_objet_metadata_authority_invalid": "C4",
    "private_objet_metadata_projection_unavailable": "C6",
    "private_objet_metadata_projection_invalid": "C7",
    "private_objet_metadata_missing": "C8",
    "private_objet_metadata_stale": "C9",
}
_SESSION_ERROR_CASES = {
    "private_objet_metadata_snapshot_changed": "C1",
    "private_objet_metadata_authority_blocked": "C3",
    "private_objet_metadata_authority_invalid": "C4",
    "private_objet_metadata_projection_unavailable": "C6",
    "private_objet_metadata_projection_invalid": "C7",
    "private_objet_metadata_missing": "C8",
}
_PUBLIC_CURRENT_ACTION = (
    "Generated index matches the live zettel path/id/status/kind snapshot "
    "checked here."
)
_PUBLIC_REBUILD_ACTION = (
    "Run archive index to rebuild the generated local SQLite index from "
    "current archive files."
)
_PRIVATE_REBUILD_ACTIONS = (
    "Stop all archive writers, then run `archive index <archive-root> "
    "--progress --format json` to rebuild the disposable public/private index.",
    "After the rebuild completes, run `archive index-health <archive-root> "
    "--dry-run --progress --format json`; continue only when `ok` is true.",
)
_PRIVATE_SNAPSHOT_RETRY_ACTION = (
    "Stop all archive writers, then rerun `archive index-health <archive-root> "
    "--dry-run --progress --format json` from a fresh command."
)
_PRIVATE_TABLE_PRESENCE_SQL = (
    "SELECT name FROM sqlite_schema "
    "WHERE type = 'table' AND name IN (?, ?, ?, ?) "
    "ORDER BY name COLLATE BINARY"
)


@dataclass(frozen=True, repr=False)
class _ProjectionProbe:
    """Same-transaction evidence retained only for the final closed check."""

    table_names: tuple[str, ...]
    singleton_count: int | None
    inspection: PrivateObjetIndexInspection | None


def _closed_session_error(code: str) -> PrivateObjetIndexSessionError:
    return PrivateObjetIndexSessionError(code)


def _counts_from_inspection(
    inspection: PrivateObjetIndexInspection,
) -> PrivateObjetMetadataCounts:
    try:
        return PrivateObjetMetadataCounts(
            observation_count=inspection.observation_count,
            alias_count=inspection.alias_count,
            distinct_object_count=inspection.distinct_object_count,
            projection_count=inspection.projection_count,
            blocked_alias_derivation_count=(
                inspection.blocked_alias_derivation_count
            ),
            blocked_label_projection_count=(
                inspection.blocked_label_projection_count
            ),
        )
    except (AttributeError, TypeError, ValueError):
        raise _closed_session_error(
            "private_objet_metadata_projection_invalid"
        ) from None


def _probe_private_projection(
    api: _PrivateObjetIndexReadAPI,
    *,
    expected: _PrivateObjetIndexProjection | None = None,
) -> _ProjectionProbe:
    rows = api.fetch_all(
        _PRIVATE_TABLE_PRESENCE_SQL,
        PRIVATE_TABLE_NAMES,
    )
    table_names: list[str] = []
    for row in rows:
        if len(row) != 1 or type(row[0]) is not str:
            raise _closed_session_error(
                "private_objet_metadata_projection_invalid"
            )
        if row[0] in table_names:
            raise _closed_session_error(
                "private_objet_metadata_projection_invalid"
            )
        table_names.append(row[0])
    names = tuple(table_names)
    required_present = set(names) == set(PRIVATE_TABLE_NAMES)
    if not required_present:
        return _ProjectionProbe(names, None, None)

    singleton_count = api.scalar(
        "SELECT COUNT(*) FROM private_objet_index_metadata"
    )
    if (
        type(singleton_count) is not int
        or singleton_count < 0
        or singleton_count > 1
    ):
        raise _closed_session_error(
            "private_objet_metadata_projection_invalid"
        )
    if singleton_count == 0:
        return _ProjectionProbe(names, 0, None)

    if expected is None:
        inspection = api.inspect_private_objet_index_semantics()
    else:
        inspection = api.inspect_private_objet_index_semantics(
            expected=expected
        )
    if not isinstance(inspection, PrivateObjetIndexInspection):
        raise _closed_session_error(
            "private_objet_metadata_projection_invalid"
        )
    return _ProjectionProbe(names, 1, inspection)


def _envelope_from_probe(
    probe: _ProjectionProbe,
    authority: _PrivateObjetIndexAuthorityCapture,
) -> dict[str, object]:
    if not isinstance(authority, _PrivateObjetIndexAuthorityCapture):
        raise _closed_session_error(
            "private_objet_metadata_projection_invalid"
        )
    if probe.inspection is None:
        return build_private_objet_metadata_health_envelope("C8")

    inspection = probe.inspection
    counts = _counts_from_inspection(inspection)
    if inspection.authority_fingerprint_sha256 != authority.fingerprint_sha256:
        return build_private_objet_metadata_health_envelope(
            "C9",
            counts=counts,
        )

    empty_authority = authority.private_manifest_state == "absent"
    if empty_authority:
        if counts.as_values() != (0, 0, 0, 0, 0, 0):
            raise _closed_session_error(
                "private_objet_metadata_projection_invalid"
            )
        return build_private_objet_metadata_health_envelope("C10")
    if authority.private_manifest_state != "present_nonempty":
        raise _closed_session_error(
            "private_objet_metadata_projection_invalid"
        )
    if (
        counts.observation_count <= 0
        or counts.distinct_object_count <= 0
        or counts.projection_count <= 0
    ):
        raise _closed_session_error(
            "private_objet_metadata_projection_invalid"
        )
    return build_private_objet_metadata_health_envelope(
        "C11",
        counts=counts,
    )


def _case_id_from_envelope(envelope: Mapping[str, object]) -> str:
    checked = validate_private_objet_metadata_health_envelope(envelope)
    diagnostics = checked["diagnostic_codes"]
    if diagnostics:
        code = diagnostics[0]  # type: ignore[index]
        return _DIAGNOSTIC_CASES[code]  # type: ignore[index]
    if checked["projection_validity"] == "missing":
        return "C5"
    if checked["empty_authority"] is True:
        return "C10"
    if checked["empty_authority"] is False:
        return "C11"
    raise _closed_session_error("private_objet_metadata_projection_invalid")


def _counts_from_envelope(
    case_id: str,
    envelope: Mapping[str, object],
) -> PrivateObjetMetadataCounts | None:
    if case_id not in {"C9", "C11"}:
        return None
    values = tuple(envelope[key] for key in PRIVATE_HEALTH_KEYS[12:18])
    try:
        return PrivateObjetMetadataCounts(*values)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise _closed_session_error(
            "private_objet_metadata_projection_invalid"
        ) from None


def _decision(
    case_id: str,
    envelope: Mapping[str, object],
) -> PrivateObjetMetadataHealthDecision:
    checked = validate_private_objet_metadata_health_envelope(envelope)
    counts = _counts_from_envelope(case_id, checked)
    expected = build_private_objet_metadata_health_envelope(
        case_id,
        counts=counts,
    )
    if checked != expected:
        raise _closed_session_error(
            "private_objet_metadata_projection_invalid"
        )
    blockers, stale_reasons = (
        append_private_objet_metadata_top_level_diagnostics(case_id)
    )
    return PrivateObjetMetadataHealthDecision(
        case_id=case_id,
        envelope=checked,
        blockers=tuple(blockers),
        stale_reasons=tuple(stale_reasons),
        translation=_CASE_TRANSLATIONS[case_id],
        query_allowed=case_id == "C11",
    )


def _decision_from_session_error(
    error: PrivateObjetIndexSessionError,
) -> PrivateObjetMetadataHealthDecision:
    # A stable DB-identity race (C2) and an availability failure (C6) have the
    # same public tuple, diagnostic, translation, and composition.  The opaque
    # session exposes only that closed public code, so C6 is the canonical
    # internal label at this boundary.
    case_id = _SESSION_ERROR_CASES.get(error.code, "C6")
    return _decision(
        case_id,
        build_private_objet_metadata_health_envelope(case_id),
    )


def _evaluate_private_objet_metadata_index_with_consumer(
    root: Path | str,
    archive_id: str,
    internal_consumer: Callable[
        [_PrivateObjetIndexReadAPI, Mapping[str, object]],
        None,
    ],
) -> PrivateObjetMetadataHealthDecision:
    """Run the shared opaque health/consumer/final-check read lifecycle."""

    final_probe: _ProjectionProbe | None = None
    final_expected: _PrivateObjetIndexProjection | None = None

    def capture_authority() -> _PrivateObjetIndexAuthorityCapture:
        return _capture_private_objet_index_authority(Path(root), archive_id)

    def inspect_health(
        api: _PrivateObjetIndexReadAPI,
        authority: object,
    ) -> Mapping[str, object]:
        nonlocal final_expected, final_probe
        if not isinstance(authority, _PrivateObjetIndexAuthorityCapture):
            raise _closed_session_error(
                "private_objet_metadata_projection_invalid"
            )
        final_probe = _probe_private_projection(api)
        if (
            final_probe.inspection is not None
            and final_probe.inspection.authority_fingerprint_sha256
            == authority.fingerprint_sha256
        ):
            final_expected = _compile_private_objet_index_projection(
                authority.compiler_input
            )
            verified_probe = _probe_private_projection(
                api,
                expected=final_expected,
            )
            if verified_probe != final_probe:
                raise _closed_session_error(
                    "private_objet_metadata_projection_invalid"
                )
            final_probe = verified_probe
        return _envelope_from_probe(final_probe, authority)

    def final_check(
        api: _PrivateObjetIndexReadAPI,
        _authority: object,
    ) -> bool:
        if final_probe is None:
            return False
        repeated = _probe_private_projection(
            api,
            expected=final_expected,
        )
        return repeated == final_probe

    try:
        envelope = _with_private_objet_index_read_session(
            root,
            internal_consumer,
            capture_authority=capture_authority,
            inspect_health=inspect_health,
            final_check=final_check,
        )
        case_id = _case_id_from_envelope(envelope)
        return _decision(case_id, envelope)
    except (KeyboardInterrupt, SystemExit):
        raise
    except PrivateObjetIndexSessionError as exc:
        return _decision_from_session_error(exc)
    except Exception:
        return _decision_from_session_error(
            _closed_session_error(
                "private_objet_metadata_projection_unavailable"
            )
        )


def evaluate_private_objet_metadata_index_health(
    root: Path | str,
    archive_id: str,
) -> PrivateObjetMetadataHealthDecision:
    """Read and classify the private layer without exposing a DB connection."""

    return _evaluate_private_objet_metadata_index_with_consumer(
        root,
        archive_id,
        lambda _api, _health: None,
    )


def unavailable_private_objet_metadata_index_health(
) -> PrivateObjetMetadataHealthDecision:
    """Return closed C6 evidence when the opaque mode=ro session cannot run."""

    return _decision(
        "C6",
        build_private_objet_metadata_health_envelope("C6"),
    )


def _closed_string_list(value: object, field_name: str) -> list[str]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or any(type(item) is not str for item in value)
    ):
        raise ValueError(f"{field_name} must be a JSON string array")
    return list(value)


def _private_aware_next_safe_actions(
    public_actions: Sequence[str],
    case_id: str,
) -> list[str]:
    actions = [
        action
        for action in public_actions
        if case_id in {"C10", "C11"}
        or action not in {_PUBLIC_CURRENT_ACTION, _PUBLIC_REBUILD_ACTION}
    ]
    if case_id == "C1":
        actions.append(_PRIVATE_SNAPSHOT_RETRY_ACTION)
    elif case_id in {"C2", "C6", "C7", "C8", "C9"}:
        actions.extend(_PRIVATE_REBUILD_ACTIONS)
    return list(dict.fromkeys(actions))


def compose_private_objet_metadata_index_health(
    public_health: Mapping[str, Any],
    decision: PrivateObjetMetadataHealthDecision,
) -> dict[str, Any]:
    """Append the sole v0.3.297 field and recompute exact top-level state."""

    if tuple(public_health) != PUBLIC_INDEX_HEALTH_KEYS:
        raise ValueError("public index-health shape or order changed")
    if not isinstance(decision, PrivateObjetMetadataHealthDecision):
        raise TypeError("private health decision has the wrong type")

    checked_envelope = validate_private_objet_metadata_health_envelope(
        decision.envelope
    )
    checked_decision = _decision(decision.case_id, checked_envelope)
    if (
        decision.blockers != checked_decision.blockers
        or decision.stale_reasons != checked_decision.stale_reasons
        or decision.translation != checked_decision.translation
        or decision.query_allowed != checked_decision.query_allowed
    ):
        raise ValueError("private health decision contradicts its closed case")

    legacy_blockers = _closed_string_list(
        public_health["blockers"],
        "blockers",
    )
    legacy_stale = _closed_string_list(
        public_health["stale_reasons"],
        "stale_reasons",
    )
    legacy_actions = _closed_string_list(
        public_health["next_safe_actions"],
        "next_safe_actions",
    )
    blockers, stale_reasons = (
        append_private_objet_metadata_top_level_diagnostics(
            decision.case_id,
            blockers=legacy_blockers,
            stale_reasons=legacy_stale,
        )
    )
    if blockers:
        ok = False
        index_state = "blocked"
    elif stale_reasons:
        ok = False
        index_state = "stale_or_incomplete"
    else:
        ok = True
        index_state = "current"

    composed: dict[str, Any] = {}
    for key in PUBLIC_INDEX_HEALTH_KEYS:
        if key == "ok":
            value: Any = ok
        elif key == "index_state":
            value = index_state
        elif key == "stale_reasons":
            value = stale_reasons
        elif key == "blockers":
            value = blockers
        elif key == "next_safe_actions":
            value = _private_aware_next_safe_actions(
                legacy_actions,
                decision.case_id,
            )
        else:
            value = deepcopy(public_health[key])
        composed[key] = value
    composed["private_objet_metadata"] = checked_envelope
    return composed


__all__ = [
    "PUBLIC_INDEX_HEALTH_KEYS",
    "compose_private_objet_metadata_index_health",
    "evaluate_private_objet_metadata_index_health",
    "unavailable_private_objet_metadata_index_health",
]
