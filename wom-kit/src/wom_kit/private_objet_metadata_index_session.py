"""Opaque SQLite read session and content-free private-index health primitives.

This module deliberately has no ``archive_services`` integration.  It owns the
v0.3.297 read lifecycle and the exact C1-C11 private health contract while the
authority compiler and public command routing remain separate concerns.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import os
from pathlib import Path
import sqlite3
import stat
from types import MappingProxyType
from typing import Any


PRIVATE_INDEX_RELATIVE_PATH = Path("db") / "archive-index.sqlite"
PRIVATE_HEALTH_SCHEMA = "wom-kit/private-objet-index-health/v0.1"
PRIVATE_HEALTH_KEYS = (
    "schema",
    "authority_validity",
    "projection_validity",
    "freshness",
    "index_state",
    "empty_authority",
    "private_layer_complete",
    "fingerprint_matches",
    "schema_matches",
    "observation_rows_digest_matches",
    "alias_rows_digest_matches",
    "projection_rows_digest_matches",
    "observation_count",
    "alias_count",
    "distinct_object_count",
    "projection_count",
    "blocked_alias_derivation_count",
    "blocked_label_projection_count",
    "diagnostic_codes",
)
PRIVATE_HEALTH_DIAGNOSTIC_CODES = frozenset(
    {
        "private_objet_metadata_missing",
        "private_objet_metadata_stale",
        "private_objet_metadata_authority_invalid",
        "private_objet_metadata_authority_blocked",
        "private_objet_metadata_snapshot_changed",
        "private_objet_metadata_projection_unavailable",
        "private_objet_metadata_projection_invalid",
    }
)

_PROJECTION_UNAVAILABLE = "private_objet_metadata_projection_unavailable"
_PROJECTION_INVALID = "private_objet_metadata_projection_invalid"
_SNAPSHOT_CHANGED = "private_objet_metadata_snapshot_changed"
_PRIVATE_MISSING = "private_objet_metadata_missing"
_WINDOWS_REPARSE_ATTRIBUTE = 0x00000400
_READ_ONLY_SQL_PREFIXES = frozenset({"SELECT"})
_SQLITE_HEADER_MAGIC = b"SQLite format 3\x00"
_SQLITE_HEADER_PREFIX_LENGTH = 20
_AUTHORITY_FAILURE_CODES = frozenset(
    {
        "private_objet_metadata_authority_blocked",
        "private_objet_metadata_authority_invalid",
    }
)
_SQLITE_DENIED_ACTIONS = frozenset(
    value
    for name in (
        "SQLITE_ALTER_TABLE",
        "SQLITE_ANALYZE",
        "SQLITE_ATTACH",
        "SQLITE_CREATE_INDEX",
        "SQLITE_CREATE_TABLE",
        "SQLITE_CREATE_TEMP_INDEX",
        "SQLITE_CREATE_TEMP_TABLE",
        "SQLITE_CREATE_TEMP_TRIGGER",
        "SQLITE_CREATE_TEMP_VIEW",
        "SQLITE_CREATE_TRIGGER",
        "SQLITE_CREATE_VIEW",
        "SQLITE_CREATE_VTABLE",
        "SQLITE_DELETE",
        "SQLITE_DETACH",
        "SQLITE_DROP_INDEX",
        "SQLITE_DROP_TABLE",
        "SQLITE_DROP_TEMP_INDEX",
        "SQLITE_DROP_TEMP_TABLE",
        "SQLITE_DROP_TEMP_TRIGGER",
        "SQLITE_DROP_TEMP_VIEW",
        "SQLITE_DROP_TRIGGER",
        "SQLITE_DROP_VIEW",
        "SQLITE_DROP_VTABLE",
        "SQLITE_INSERT",
        "SQLITE_PRAGMA",
        "SQLITE_REINDEX",
        "SQLITE_SAVEPOINT",
        "SQLITE_TRANSACTION",
        "SQLITE_UPDATE",
    )
    if (value := getattr(sqlite3, name, None)) is not None
)


class PrivateObjetIndexSessionError(RuntimeError):
    """Sanitized, content-free read-session failure."""

    def __init__(self, code: str) -> None:
        if code not in PRIVATE_HEALTH_DIAGNOSTIC_CODES:
            raise ValueError("private session errors require a closed diagnostic code")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PrivateObjetMetadataCounts:
    """The six all-or-none counts from one fully validated singleton."""

    observation_count: int
    alias_count: int
    distinct_object_count: int
    projection_count: int
    blocked_alias_derivation_count: int
    blocked_label_projection_count: int

    def __post_init__(self) -> None:
        values_and_bounds = (
            (self.observation_count, 100_000),
            (self.alias_count, 500_000),
            (self.distinct_object_count, 100_000),
            (self.projection_count, 200_000),
            (self.blocked_alias_derivation_count, 100_000),
            (self.blocked_label_projection_count, 200_000),
        )
        for value, maximum in values_and_bounds:
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError("private health count is outside its closed bounds")
        if self.blocked_alias_derivation_count > self.observation_count:
            raise ValueError("blocked alias count exceeds observation count")
        if self.blocked_label_projection_count > self.projection_count:
            raise ValueError("blocked projection count exceeds projection count")
        if self.projection_count != 2 * self.distinct_object_count:
            raise ValueError("projection count does not cover two audiences")
        unblocked = self.observation_count - self.blocked_alias_derivation_count
        if not unblocked <= self.alias_count <= 5 * unblocked:
            raise ValueError("alias count contradicts exact helper bounds")

    def as_values(self) -> tuple[int, int, int, int, int, int]:
        return (
            self.observation_count,
            self.alias_count,
            self.distinct_object_count,
            self.projection_count,
            self.blocked_alias_derivation_count,
            self.blocked_label_projection_count,
        )


@dataclass(frozen=True, repr=False)
class PrivateObjetMetadataHealthObservation:
    """Content-free evidence consumed by the strict C1-C11 classifier."""

    authority_token_a: object = field(repr=False)
    authority_token_b: object = field(repr=False)
    authority_validity: str
    db_identity_token_a: object = field(repr=False)
    db_identity_token_b: object = field(repr=False)
    db_present: bool
    projection_unavailable: bool = False
    db_path_safe: bool = True
    required_private_tables_present: bool | None = None
    singleton_present: bool | None = None
    schema_matches: bool | None = None
    count_digest_matches: bool | None = None
    fingerprint_matches: bool | None = None
    empty_authority: bool | None = None
    counts: PrivateObjetMetadataCounts | None = None


@dataclass(frozen=True)
class PrivateObjetMetadataHealthDecision:
    """One exact classifier outcome ready for later public-health composition."""

    case_id: str
    envelope: dict[str, object]
    blockers: tuple[str, ...]
    stale_reasons: tuple[str, ...]
    translation: str
    query_allowed: bool


_CASE_TUPLES: dict[str, tuple[str, str, str, str]] = {
    "C1": ("unavailable", "unverifiable", "unverifiable", "blocked"),
    "C2": ("valid", "unverifiable", "unverifiable", "blocked"),
    "C3": ("blocked", "unverifiable", "unverifiable", "blocked"),
    "C4": ("invalid", "unverifiable", "unverifiable", "blocked"),
    "C5": ("valid", "missing", "missing", "missing"),
    "C6": ("valid", "unverifiable", "unverifiable", "blocked"),
    "C7": ("valid", "invalid", "unverifiable", "blocked"),
    "C8": ("valid", "missing", "missing", "missing"),
    "C9": ("valid", "valid", "stale", "stale_or_incomplete"),
    "C10": ("valid", "valid", "current", "current"),
    "C11": ("valid", "valid", "current", "current"),
}
_NULL_B7 = (None, None, None, None, None, None, None)
_CASE_B7: dict[str, tuple[bool | None, ...]] = {
    "C1": _NULL_B7,
    "C2": _NULL_B7,
    "C3": _NULL_B7,
    "C4": _NULL_B7,
    "C5": _NULL_B7,
    "C6": _NULL_B7,
    "C7": (None, False, None, None, None, None, None),
    "C8": (None, False, None, None, None, None, None),
    "C9": (None, True, False, True, True, True, True),
    "C10": (True, True, True, True, True, True, True),
    "C11": (False, True, True, True, True, True, True),
}
_CASE_DIAGNOSTICS: dict[str, tuple[str, ...]] = {
    "C1": (_SNAPSHOT_CHANGED,),
    "C2": (_PROJECTION_UNAVAILABLE,),
    "C3": ("private_objet_metadata_authority_blocked",),
    "C4": ("private_objet_metadata_authority_invalid",),
    "C5": (),
    "C6": (_PROJECTION_UNAVAILABLE,),
    "C7": (_PROJECTION_INVALID,),
    "C8": (_PRIVATE_MISSING,),
    "C9": ("private_objet_metadata_stale",),
    "C10": (),
    "C11": (),
}
_CASE_TOP_LEVEL: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "C1": ((_SNAPSHOT_CHANGED,), ()),
    "C2": ((_PROJECTION_UNAVAILABLE,), ()),
    "C3": (("private_objet_metadata_authority_blocked",), ()),
    "C4": (("private_objet_metadata_authority_invalid",), ()),
    "C5": (("archive_index_missing",), ("index_health_blocked",)),
    "C6": ((_PROJECTION_UNAVAILABLE,), ()),
    "C7": ((_PROJECTION_INVALID,), ()),
    "C8": ((), (_PRIVATE_MISSING,)),
    "C9": ((), ("private_objet_metadata_stale",)),
    "C10": ((), ()),
    "C11": ((), ()),
}
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


def build_private_objet_metadata_health_envelope(
    case_id: str,
    *,
    counts: PrivateObjetMetadataCounts | None = None,
) -> dict[str, object]:
    """Build one canonical 19-key envelope in the directive's insertion order."""

    if case_id not in _CASE_TUPLES:
        raise ValueError("unknown private health case")
    if case_id in {"C9", "C11"}:
        if counts is None:
            raise ValueError("valid projections require all six exact counts")
    elif counts is not None:
        raise ValueError("counts are unavailable outside C9/C11")
    if case_id == "C11" and counts is not None:
        if (
            counts.observation_count <= 0
            or counts.distinct_object_count <= 0
            or counts.projection_count <= 0
        ):
            raise ValueError("C11 requires an exact nonempty projection")

    count_values: tuple[int | None, ...]
    if case_id == "C10":
        count_values = (0, 0, 0, 0, 0, 0)
    elif counts is None:
        count_values = (None, None, None, None, None, None)
    else:
        count_values = counts.as_values()

    values: tuple[object, ...] = (
        PRIVATE_HEALTH_SCHEMA,
        *_CASE_TUPLES[case_id],
        *_CASE_B7[case_id],
        *count_values,
        list(_CASE_DIAGNOSTICS[case_id]),
    )
    envelope = dict(zip(PRIVATE_HEALTH_KEYS, values))
    if tuple(envelope) != PRIVATE_HEALTH_KEYS or len(envelope) != 19:
        raise AssertionError("private health insertion-order contract drifted")
    return envelope


def _tokens_equal(left: object, right: object) -> bool:
    try:
        hash(left)
        hash(right)
        result = left == right
    except Exception as exc:
        raise ValueError("comparison tokens must be stable and hashable") from exc
    if type(result) is not bool:
        raise ValueError("comparison token equality must return Boolean")
    return result


def _require_exact_boolean(value: bool | None, field_name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field_name} must be an observed Boolean")
    return value


def classify_private_objet_metadata_health(
    observation: PrivateObjetMetadataHealthObservation,
) -> PrivateObjetMetadataHealthDecision:
    """Apply the directive's strict first-match C1-C11 classifier."""

    if observation.authority_validity not in {"valid", "blocked", "invalid"}:
        raise ValueError("authority_validity is outside the closed classifier input")
    for value, name in (
        (observation.db_present, "db_present"),
        (observation.projection_unavailable, "projection_unavailable"),
        (observation.db_path_safe, "db_path_safe"),
    ):
        _require_exact_boolean(value, name)

    authority_stable = _tokens_equal(
        observation.authority_token_a,
        observation.authority_token_b,
    )
    db_identity_stable = _tokens_equal(
        observation.db_identity_token_a,
        observation.db_identity_token_b,
    )

    if not authority_stable:
        case_id = "C1"
    elif observation.authority_validity == "valid" and not db_identity_stable:
        case_id = "C2"
    elif observation.authority_validity == "blocked":
        case_id = "C3"
    elif observation.authority_validity == "invalid":
        case_id = "C4"
    elif not observation.db_present:
        case_id = "C5"
    elif observation.projection_unavailable:
        case_id = "C6"
    elif not observation.db_path_safe:
        case_id = "C7"
    else:
        tables_present = _require_exact_boolean(
            observation.required_private_tables_present,
            "required_private_tables_present",
        )
        singleton_present = _require_exact_boolean(
            observation.singleton_present,
            "singleton_present",
        )
        if not tables_present or not singleton_present:
            # Missing required objects explicitly bypass generic schema mismatch.
            case_id = "C8"
        else:
            schema_matches = _require_exact_boolean(
                observation.schema_matches,
                "schema_matches",
            )
            count_digest_matches = _require_exact_boolean(
                observation.count_digest_matches,
                "count_digest_matches",
            )
            if not schema_matches or not count_digest_matches:
                case_id = "C7"
            else:
                fingerprint_matches = _require_exact_boolean(
                    observation.fingerprint_matches,
                    "fingerprint_matches",
                )
                if not fingerprint_matches:
                    case_id = "C9"
                elif _require_exact_boolean(
                    observation.empty_authority,
                    "empty_authority",
                ):
                    case_id = "C10"
                else:
                    case_id = "C11"

    envelope = build_private_objet_metadata_health_envelope(
        case_id,
        counts=observation.counts if case_id in {"C9", "C11"} else None,
    )
    blockers, stale_reasons = _CASE_TOP_LEVEL[case_id]
    return PrivateObjetMetadataHealthDecision(
        case_id=case_id,
        envelope=envelope,
        blockers=blockers,
        stale_reasons=stale_reasons,
        translation=_CASE_TRANSLATIONS[case_id],
        query_allowed=case_id == "C11",
    )


def _exact_value_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(  # type: ignore[arg-type]
            _exact_value_equal(a, b) for a, b in zip(left, right)  # type: ignore[arg-type]
        )
    return left == right


def validate_private_objet_metadata_health_envelope(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Validate and copy an exact C1-C11 envelope without private free text."""

    if tuple(value) != PRIVATE_HEALTH_KEYS:
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
    candidate = dict(value)
    possible_counts: PrivateObjetMetadataCounts | None = None
    count_values = tuple(candidate[key] for key in PRIVATE_HEALTH_KEYS[12:18])
    if all(type(item) is int for item in count_values):
        try:
            possible_counts = PrivateObjetMetadataCounts(*count_values)  # type: ignore[arg-type]
        except ValueError:
            possible_counts = None
    for case_id in _CASE_TUPLES:
        try:
            expected = build_private_objet_metadata_health_envelope(
                case_id,
                counts=possible_counts if case_id in {"C9", "C11"} else None,
            )
        except ValueError:
            continue
        if all(
            _exact_value_equal(candidate[key], expected[key])
            for key in PRIVATE_HEALTH_KEYS
        ):
            candidate["diagnostic_codes"] = list(
                candidate["diagnostic_codes"]  # type: ignore[arg-type]
            )
            return candidate
    raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)


def append_private_objet_metadata_top_level_diagnostics(
    case_id: str,
    *,
    blockers: Sequence[str] = (),
    stale_reasons: Sequence[str] = (),
) -> tuple[list[str], list[str]]:
    """Append the exact private delta with order-preserving deduplication."""

    if case_id not in _CASE_TOP_LEVEL:
        raise ValueError("unknown private health case")
    additions = _CASE_TOP_LEVEL[case_id]

    def unique(values: Sequence[str]) -> list[str]:
        result: list[str] = []
        for item in values:
            if item not in result:
                result.append(item)
        return result

    return (
        unique((*blockers, *additions[0])),
        unique((*stale_reasons, *additions[1])),
    )


@dataclass(frozen=True, repr=False)
class _PathIdentity:
    present: bool
    device: int | None
    inode: int | None


@dataclass(frozen=True, repr=False)
class _SQLiteIdentityToken:
    parent: _PathIdentity
    database: _PathIdentity
    wal: _PathIdentity
    shm: _PathIdentity
    journal: _PathIdentity

    @property
    def database_present(self) -> bool:
        return self.database.present


def _is_reparse(stat_result: os.stat_result) -> bool:
    return bool(
        getattr(stat_result, "st_file_attributes", 0)
        & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _path_identity(
    path: Path,
    *,
    expected_directory: bool,
    allow_missing: bool,
) -> _PathIdentity:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return _PathIdentity(False, None, None)
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID) from None
    if stat.S_ISLNK(observed.st_mode) or _is_reparse(observed):
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
    if expected_directory:
        if not stat.S_ISDIR(observed.st_mode):
            raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
    elif not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
    inode = int(observed.st_ino)
    if inode == 0:
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
    return _PathIdentity(True, int(observed.st_dev), inode)


def _same_resolved_path(path: Path) -> bool:
    try:
        absolute = Path(os.path.abspath(path))
        resolved = path.resolve(strict=True)
        return os.path.samefile(absolute, resolved)
    except (OSError, RuntimeError):
        return False


def _capture_sqlite_identity_token(db_path: Path) -> _SQLiteIdentityToken:
    parent = db_path.parent
    if not _same_resolved_path(parent):
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
    parent_token = _path_identity(
        parent,
        expected_directory=True,
        allow_missing=False,
    )
    database = _path_identity(
        db_path,
        expected_directory=False,
        allow_missing=True,
    )
    wal = _path_identity(
        db_path.with_name(db_path.name + "-wal"),
        expected_directory=False,
        allow_missing=True,
    )
    shm = _path_identity(
        db_path.with_name(db_path.name + "-shm"),
        expected_directory=False,
        allow_missing=True,
    )
    journal = _path_identity(
        db_path.with_name(db_path.name + "-journal"),
        expected_directory=False,
        allow_missing=True,
    )
    if not database.present and (wal.present or shm.present or journal.present):
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
    if database.present and not _same_resolved_path(db_path):
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
    return _SQLiteIdentityToken(parent_token, database, wal, shm, journal)


def _private_objet_index_read_uri(db_path: Path) -> str:
    uri = db_path.resolve(strict=True).as_uri() + "?mode=ro"
    if "immutable=" in uri or not uri.endswith("?mode=ro"):
        raise AssertionError("private read URI contract drifted")
    return uri


def _open_private_objet_index_connection(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        _private_objet_index_read_uri(db_path),
        uri=True,
        timeout=30.0,
        isolation_level=None,
    )


def _database_header_read_write_versions(db_path: Path) -> bytes | None:
    """Inspect SQLite header bytes without opening a connection or sidecar."""

    try:
        with db_path.open("rb") as handle:
            header = handle.read(_SQLITE_HEADER_PREFIX_LENGTH)
    except OSError:
        raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE) from None
    if (
        len(header) != _SQLITE_HEADER_PREFIX_LENGTH
        or header[:16] != _SQLITE_HEADER_MAGIC
    ):
        return None
    return header[18:20]


def _database_header_advertises_wal(db_path: Path) -> bool:
    return _database_header_read_write_versions(db_path) == b"\x02\x02"


def _database_header_advertises_delete(db_path: Path) -> bool:
    return _database_header_read_write_versions(db_path) == b"\x01\x01"


def _rollback_read_boundary_is_preopen_coherent(
    db_path: Path,
    identity: _SQLiteIdentityToken,
) -> bool:
    """Require the v0.3.314 rollback-mode snapshot before any SQLite query."""

    wal_present = identity.wal.present
    shm_present = identity.shm.present
    journal_present = identity.journal.present
    return (
        _database_header_advertises_delete(db_path)
        and not wal_present
        and not shm_present
        and not journal_present
    )


class PrivateObjetIndexReadAPI:
    """Restricted materializing query API; it never returns a cursor/connection."""

    __slots__ = ("__connection", "__active")

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.__connection = connection
        self.__active = True

    def _deactivate(self) -> None:
        self.__active = False

    def _require_active(self) -> None:
        if not self.__active:
            raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE)

    @property
    def snapshot_active(self) -> bool:
        self._require_active()
        return bool(self.__connection.in_transaction)

    def fetch_all(
        self,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> tuple[tuple[object, ...], ...]:
        self._require_active()
        if not isinstance(sql, str) or not sql.strip():
            raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
        prefix = sql.lstrip().split(None, 1)[0].upper()
        if prefix not in _READ_ONLY_SQL_PREFIXES:
            raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
        try:
            cursor = self.__connection.execute(sql, tuple(parameters))
            return tuple(tuple(row) for row in cursor.fetchall())
        except sqlite3.Error:
            raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE) from None

    def inspect_private_objet_index_semantics(
        self,
        *,
        expected: object | None = None,
    ) -> object:
        """Run the fixed Batch A inspector without exposing its raw connection."""

        self._require_active()
        try:
            from .private_objet_metadata_index import (
                inspect_private_objet_index_semantics,
            )

            self.__connection.set_authorizer(_sqlite_allow_authorizer)
            try:
                if expected is None:
                    return inspect_private_objet_index_semantics(
                        self.__connection
                    )
                return inspect_private_objet_index_semantics(
                    self.__connection,
                    expected=expected,  # type: ignore[arg-type]
                )
            finally:
                self.__connection.set_authorizer(_sqlite_read_authorizer)
        except PrivateObjetIndexSessionError:
            raise
        except Exception:
            raise PrivateObjetIndexSessionError(_PROJECTION_INVALID) from None

    def fetch_one(
        self,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> tuple[object, ...] | None:
        rows = self.fetch_all(sql, parameters)
        if len(rows) > 1:
            raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
        return rows[0] if rows else None

    def scalar(
        self,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> object | None:
        row = self.fetch_one(sql, parameters)
        if row is None:
            return None
        if len(row) != 1:
            raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
        return row[0]


def _comparison_token(authority_snapshot: object) -> object:
    try:
        token = getattr(authority_snapshot, "comparison_token")
        hash(token)
    except Exception:
        raise PrivateObjetIndexSessionError(_PROJECTION_INVALID) from None
    return token


def _sqlite_read_authorizer(
    action_code: int,
    _argument_1: str | None,
    _argument_2: str | None,
    _database_name: str | None,
    _trigger_or_view: str | None,
) -> int:
    if action_code in _SQLITE_DENIED_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _sqlite_allow_authorizer(
    _action_code: int,
    _argument_1: str | None,
    _argument_2: str | None,
    _database_name: str | None,
    _trigger_or_view: str | None,
) -> int:
    """Clear read restrictions without Python 3.11's ``None`` API."""

    return sqlite3.SQLITE_OK


def _capture_authority_a(capture_authority: Callable[[], object]) -> object:
    try:
        return capture_authority()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code in _AUTHORITY_FAILURE_CODES:
            raise PrivateObjetIndexSessionError(code) from None
        raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE) from None


def _capture_authority_b(capture_authority: Callable[[], object]) -> object:
    try:
        return capture_authority()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        # A successful A followed by any failed/unstable B is C1 evidence.
        raise PrivateObjetIndexSessionError(_SNAPSHOT_CHANGED) from None


def _require_stable_authority_and_db(
    capture_authority: Callable[[], object],
    authority_token_a: object,
    db_path: Path,
    identity_a: _SQLiteIdentityToken,
) -> None:
    """Apply C1 then C2 precedence before accepting any lower-priority result."""

    authority_b = _capture_authority_b(capture_authority)
    if not _tokens_equal(
        authority_token_a,
        _comparison_token(authority_b),
    ):
        raise PrivateObjetIndexSessionError(_SNAPSHOT_CHANGED)
    identity_b = _capture_sqlite_identity_token(db_path)
    if identity_a != identity_b:
        raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE)


def _with_private_objet_index_read_session(
    root: Path | str,
    internal_consumer: Callable[
        [PrivateObjetIndexReadAPI, Mapping[str, object]],
        None,
    ],
    *,
    capture_authority: Callable[[], object],
    inspect_health: Callable[
        [PrivateObjetIndexReadAPI, object],
        Mapping[str, object],
    ],
    final_check: Callable[[PrivateObjetIndexReadAPI, object], bool],
) -> dict[str, object]:
    """Run one opaque, pinned, read-only lifecycle and return only health."""

    connection: sqlite3.Connection | None = None
    read_api: PrivateObjetIndexReadAPI | None = None
    failure: BaseException | None = None
    cleanup_failed = False
    result: dict[str, object] | None = None
    authority_token_a: object | None = None
    db_path: Path | None = None
    identity_a: _SQLiteIdentityToken | None = None
    final_tokens_checked = False
    try:
        authority_a = _capture_authority_a(capture_authority)
        authority_token_a = _comparison_token(authority_a)
        db_path = Path(root) / PRIVATE_INDEX_RELATIVE_PATH
        identity_a = _capture_sqlite_identity_token(db_path)
        if not identity_a.database_present:
            final_tokens_checked = True
            _require_stable_authority_and_db(
                capture_authority,
                authority_token_a,
                db_path,
                identity_a,
            )
            result = build_private_objet_metadata_health_envelope("C5")
            return dict(result)
        if not _rollback_read_boundary_is_preopen_coherent(db_path, identity_a):
            final_tokens_checked = True
            _require_stable_authority_and_db(
                capture_authority,
                authority_token_a,
                db_path,
                identity_a,
            )
            raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE)

        connection = _open_private_objet_index_connection(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE)
        connection.execute("PRAGMA temp_store=MEMORY")
        if connection.execute("PRAGMA temp_store").fetchone()[0] != 2:
            raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE)
        connection.execute("BEGIN")
        connection.execute("SELECT name FROM sqlite_schema ORDER BY name LIMIT 1").fetchone()
        connection.set_authorizer(_sqlite_read_authorizer)

        read_api = PrivateObjetIndexReadAPI(connection)
        health = validate_private_objet_metadata_health_envelope(
            inspect_health(read_api, authority_a)
        )
        consumer_result = internal_consumer(
            read_api,
            MappingProxyType(health),
        )
        if consumer_result is not None:
            raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)
        if final_check(read_api, authority_a) is not True:
            raise PrivateObjetIndexSessionError(_PROJECTION_INVALID)

        final_tokens_checked = True
        _require_stable_authority_and_db(
            capture_authority,
            authority_token_a,
            db_path,
            identity_a,
        )
        result = health
    except BaseException as exc:
        failure = exc
        should_apply_precedence = (
            not final_tokens_checked
            and authority_token_a is not None
            and db_path is not None
            and identity_a is not None
            and not isinstance(exc, (KeyboardInterrupt, SystemExit))
        )
        if should_apply_precedence:
            try:
                final_tokens_checked = True
                _require_stable_authority_and_db(
                    capture_authority,
                    authority_token_a,
                    db_path,
                    identity_a,
                )
            except BaseException as precedence_failure:
                failure = precedence_failure
    finally:
        if read_api is not None:
            read_api._deactivate()
        if connection is not None:
            try:
                connection.set_authorizer(_sqlite_allow_authorizer)
            except BaseException:
                cleanup_failed = True
            try:
                connection.rollback()
            except BaseException:
                cleanup_failed = True
            try:
                connection.close()
            except BaseException:
                cleanup_failed = True

    if cleanup_failed:
        raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE) from None
    if failure is not None:
        if isinstance(failure, (KeyboardInterrupt, SystemExit)):
            raise failure
        if isinstance(failure, PrivateObjetIndexSessionError):
            raise failure from None
        raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE) from None
    if result is None:
        raise PrivateObjetIndexSessionError(_PROJECTION_UNAVAILABLE)
    return dict(result)


__all__ = [
    "PRIVATE_HEALTH_DIAGNOSTIC_CODES",
    "PRIVATE_HEALTH_KEYS",
    "PRIVATE_HEALTH_SCHEMA",
    "PRIVATE_INDEX_RELATIVE_PATH",
    "PrivateObjetIndexReadAPI",
    "PrivateObjetIndexSessionError",
    "PrivateObjetMetadataCounts",
    "PrivateObjetMetadataHealthDecision",
    "PrivateObjetMetadataHealthObservation",
    "_with_private_objet_index_read_session",
    "append_private_objet_metadata_top_level_diagnostics",
    "build_private_objet_metadata_health_envelope",
    "classify_private_objet_metadata_health",
    "validate_private_objet_metadata_health_envelope",
]
