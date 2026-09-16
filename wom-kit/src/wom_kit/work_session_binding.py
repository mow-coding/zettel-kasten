"""Immutable, content-free work-session identity; never write authority.

The private registry owns human labels and current claim validation. This
contract records an explicit historical revision without consulting that
registry, guessing authorship, or changing an already approved operation.
Opaque references identify installations and work, not machines or accounts.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from typing import Any, Mapping


WORK_SESSION_BINDING_SCHEMA = "wom-kit/work-session-binding/v1"
_REF_PREFIXES = ("client_app", "workstream", "work_session")
_DIGEST_FIELDS = (
    "archive_identity_sha256",
    "client_app_label_sha256",
    "workstream_label_sha256",
)
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_BASIS_FIELDS = (
    *(prefix + "_ref" for prefix in _REF_PREFIXES),
    "revision",
    *_DIGEST_FIELDS,
)


class WorkSessionBindingError(ValueError):
    """Fixed-code failure without rejected labels, references, or values."""

    def __init__(self) -> None:
        self.code = "work_session_binding_invalid"
        super().__init__(self.code)


def new_work_session_ref(kind: str) -> str:
    """Generate a random opaque reference for one supported identity kind."""
    if type(kind) is not str or kind not in _REF_PREFIXES:
        raise WorkSessionBindingError()
    return kind + "_" + secrets.token_hex(16)


def _digest_basis(basis: Mapping[str, Any]) -> str:
    raw = json.dumps(
        basis, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _validate_fields(fields: Mapping[str, Any]) -> None:
    for prefix in _REF_PREFIXES:
        value = fields[prefix + "_ref"]
        if (
            type(value) is not str
            or len(value) != len(prefix) + 33
            or re.fullmatch(prefix + r"_[0-9a-f]{32}", value) is None
        ):
            raise WorkSessionBindingError()
    revision = fields["revision"]
    if type(revision) is not int or not 1 <= revision <= 2**63 - 1:
        raise WorkSessionBindingError()
    for name in _DIGEST_FIELDS:
        _validate_digest(fields[name])


def _validate_digest(value: Any) -> None:
    if (
        type(value) is not str or len(value) != 71
        or _DIGEST_RE.fullmatch(value) is None
    ):
        raise WorkSessionBindingError()


@dataclass(frozen=True)
class WorkSessionBinding:
    client_app_ref: str
    workstream_ref: str
    work_session_ref: str
    revision: int
    archive_identity_sha256: str
    client_app_label_sha256: str
    workstream_label_sha256: str
    binding_sha256: str

    def __post_init__(self) -> None:
        _validate_fields(self._basis())
        _validate_digest(self.binding_sha256)
        if not hmac.compare_digest(self.binding_sha256, _digest_basis(self._basis())):
            raise WorkSessionBindingError()

    def _basis(self) -> dict[str, Any]:
        return {
            "schema": WORK_SESSION_BINDING_SCHEMA,
            **{name: getattr(self, name) for name in _BASIS_FIELDS},
        }

    def document(self) -> dict[str, Any]:
        return {**self._basis(), "binding_sha256": self.binding_sha256}

    @classmethod
    def build(
        cls,
        *,
        client_app_ref: str,
        workstream_ref: str,
        work_session_ref: str,
        revision: int,
        archive_identity_sha256: str,
        client_app_label_sha256: str,
        workstream_label_sha256: str,
    ) -> "WorkSessionBinding":
        fields = {
            "client_app_ref": client_app_ref,
            "workstream_ref": workstream_ref,
            "work_session_ref": work_session_ref,
            "revision": revision,
            "archive_identity_sha256": archive_identity_sha256,
            "client_app_label_sha256": client_app_label_sha256,
            "workstream_label_sha256": workstream_label_sha256,
        }
        # Validate and bound every value before serialization; rejected data
        # cannot trigger an unbounded encoding or a custom conversion error.
        _validate_fields(fields)
        basis = {"schema": WORK_SESSION_BINDING_SCHEMA, **fields}
        try:
            digest = _digest_basis(basis)
        except (TypeError, ValueError, UnicodeError):
            raise WorkSessionBindingError() from None
        return cls(**fields, binding_sha256=digest)

    @classmethod
    def from_document(cls, value: Mapping[str, Any]) -> "WorkSessionBinding":
        if (
            not isinstance(value, Mapping)
            or set(value) != {"schema", *_BASIS_FIELDS, "binding_sha256"}
            or type(value.get("schema")) is not str
            or value.get("schema") != WORK_SESSION_BINDING_SCHEMA
        ):
            raise WorkSessionBindingError()
        return cls(**{
            name: value[name] for name in (*_BASIS_FIELDS, "binding_sha256")
        })


__all__ = [
    "WORK_SESSION_BINDING_SCHEMA", "WorkSessionBinding", "WorkSessionBindingError",
    "new_work_session_ref",
]
