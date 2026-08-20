"""Stable, additive approval replay descriptors for public WOM results.

The descriptor deliberately separates safe result values from private values
that an operator must reuse from the original command.  It is guidance only:
it never renders or executes a shell command.
"""

from __future__ import annotations

from typing import Any, Iterable


APPROVAL_HANDOFF_SCHEMA = "wom-kit/approval-handoff/v0.1"


def argument(
    option: str,
    *,
    required: bool,
    value_source: str,
    json_pointer: str | None = None,
    value: Any = None,
    sensitive: bool = False,
    echoed: bool = True,
) -> dict[str, Any]:
    """Describe one replay argument without constructing a command string."""

    if value_source not in {"json_pointer", "reuse_input", "operator_input"}:
        raise ValueError("approval_handoff_value_source_invalid")
    return {
        "option": option,
        "required": bool(required),
        "value_source": value_source,
        "json_pointer": json_pointer,
        "value": None if sensitive or not echoed else value,
        "sensitive": bool(sensitive),
        "echoed": bool(echoed and not sensitive),
    }


def build(
    *,
    stage: str,
    next_command: str | None,
    ready: bool,
    exact_replay_required: bool,
    replay_scope: str,
    arguments: Iterable[dict[str, Any]],
    required_review_bindings: Iterable[dict[str, Any]] = (),
    receipt_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one JSON-serializable, non-executable handoff descriptor."""

    return {
        "schema": APPROVAL_HANDOFF_SCHEMA,
        "stage": stage,
        "next_command": next_command,
        "ready": bool(ready),
        "exact_replay_required": bool(exact_replay_required),
        "replay_scope": replay_scope,
        "arguments": list(arguments),
        "required_review_bindings": list(required_review_bindings),
        "receipt_ref": receipt_ref,
        "command_rendered": False,
        "command_executed": False,
    }


def review_binding(
    binding: str,
    *,
    required: bool,
    value_json_pointer: str | None,
    one_use: bool = True,
) -> dict[str, Any]:
    """Describe evidence a future one-use approval receipt must bind."""

    return {
        "binding": binding,
        "required": bool(required),
        "value_json_pointer": value_json_pointer,
        "one_use": bool(one_use),
    }
