"""Parser-derived, content-free command approval status inventory.

Current approval truth comes from an already-built ``argparse.ArgumentParser``;
optional exposure history records a bounded audit of public source tags, not
successful use.  The inventory does not evaluate command prerequisites,
render help text, execute handlers, or inspect any filesystem, network, or
provider state.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from contextlib import redirect_stderr
import io
from itertools import product
import re
import shlex
from typing import AbstractSet, Any
import unicodedata


COMMAND_STATUS_INVENTORY_SCHEMA = (
    "wom-kit/command-approval-status-inventory/v0.2"
)
SUGGESTED_COMMAND_MODE_STATUS_SCHEMA = (
    "wom-kit/suggested-command-mode-status/v0.2"
)
CAPABILITY_AVAILABILITY_SCHEMA = "wom-kit/capability-availability/v0.1"

APPROVAL_AVAILABLE = "approval_available"
APPROVAL_FIXED_CLOSED = "approval_fixed_closed"
APPROVAL_NOT_EXPOSED = "approval_not_exposed"
APPROVAL_STATUSES = (
    APPROVAL_AVAILABLE,
    APPROVAL_FIXED_CLOSED,
    APPROVAL_NOT_EXPOSED,
)

CAPABILITY_AVAILABLE = "available"
CAPABILITY_WRITER_UNAVAILABLE = "writer_unavailable"
CAPABILITY_MODE_UNAVAILABLE = "mode_unavailable"
CAPABILITY_NOT_REQUESTED = "not_requested"
CAPABILITY_AVAILABILITY_STATES = (
    CAPABILITY_AVAILABLE,
    CAPABILITY_WRITER_UNAVAILABLE,
    CAPABILITY_MODE_UNAVAILABLE,
    CAPABILITY_NOT_REQUESTED,
)
WRITER_UNAVAILABLE_REASON_CODE = "writer_unavailable"

COMPOUND_APPROVAL_REASON_CODE = (
    "compound_exact_human_approval_binding_required"
)

# One content-free source of truth for public approval surfaces that remain
# deliberately closed.  CLI help, capability inventory, and read-only planners
# must consume this registry instead of maintaining independent claims.
COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS = frozenset(
    {
        "activity-group-membership-recover",
        "activity-group-membership-removal-recover",
        "activity-group-membership-removal-write",
        "activity-group-membership-write",
        "add-source",
        "ai-scratch-gc",
        "credential-keepassxc-write",
        "credential-lifecycle",
        "delegate-zet",
        "discard-draft",
        "discard-draft-restore",
        "derive-text capture",
        "external-locator-deactivate",
        "external-locator-revert",
        "github-repo",
        "identity-reconcile",
        "imap-mailbox-adapter-manifest-write",
        "imap-mailbox-header-metadata-scan",
        "import-external",
        "legacy-coordination-cleanup",
        "markup-normalization",
        "markup-normalization-recovery",
        "markup-normalization-revert",
        "mint-zet-batch",
        "notion-ancestor-fetch-adapter-run",
        "notion-objet-manifest-locator-label",
        "notion-objet-link-convert",
        "notion-page-recovery",
        "notion-recover",
        "object-storage-upload",
        "object-storage-upload-evidence",
        "object-storage-wom-location-reconcile",
        "objet-capture-enable",
        "objet-source-metadata-write",
        "onboard",
        "prehashed-objet-ledger",
        "principal-register",
        "principal-unregister",
        "project-bytecode-repair",
        "project-version-update-collision",
        "repair-gitignore",
        "quarantine-foreign-block",
        "record-quarantine-decision",
        "remint-reconcile",
        "retire-draft-batch",
        "retire-draft-reconcile",
        "runtime-skill-install",
        "runtime-skill-uninstall",
        "revert-batch",
        "restore-drill",
        "saved-view-revert",
        "saved-view-write",
        "scan-source",
        "tiro-lossless-recovery-capture",
        "tiro-lossless-recovery-fetch-run",
        "transfer-ownership",
        "zet-abstract-backfill-recover",
        "zet-abstract-backfill-revert",
        "zet-abstract-backfill-write",
        "zet-catalog-pass-cleanup",
        "zet-revision-restore-write",
        "zet-revision-restore-proposal-from-snapshot",
        "zet-revision-write",
        "zet-title-remap-recover",
        "zet-title-remap-revert-recover",
        "zettel-edge-batch",
        "zettel-objet-link-revert",
    }
)

COMPOUND_APPROVAL_FIXED_CLOSED_PLAN_WRITERS = {
    "discard-draft": "discard-draft",
    "zet-revision-plan": "zet-revision-write",
}

# Public parser and dispatch exposure was audited at v0.3.320 and its explicit
# restriction at v0.4.0. These facts do not prove successful execution at either
# tag, and must never be presented as a last-working-version or downgrade path.
AUDITED_PREVIOUSLY_EXPOSED_APPROVAL_COMMANDS = frozenset({
    "discard-draft",
    "discard-draft-restore",
    "mint-zet-batch",
    "retire-draft-batch",
    "zettel-edge-batch",
    "zet-revision-write",
    "zet-revision-restore-write",
    "remint-reconcile",
    "retire-draft-reconcile",
})


def approval_exposure_history(
    command: str,
    approval_status: str,
) -> dict[str, Any]:
    """Return only audited public exposure, never infer successful use."""

    if (
        command in AUDITED_PREVIOUSLY_EXPOSED_APPROVAL_COMMANDS
        and approval_status == APPROVAL_FIXED_CLOSED
    ):
        return {
            "state": "previously_exposed_now_restricted",
            "exposed_at_tag": "v0.3.320",
            "restricted_at_tag": "v0.4.0",
            "evidence_basis": "public_tag_parser_and_dispatch",
            "successful_use_verified": False,
        }
    # Unaudited commands, old inventory rows, and future reopened surfaces must
    # not inherit an unsupported never-implemented or currently-restricted claim.
    return {"state": "history_not_audited", "successful_use_verified": False}


# These top-level launchers deliberately hand their remaining argv to bounded
# parsers that do not use argparse. Keep that exceptional surface explicit so
# the shared inventory reports the mode the real dispatcher accepts instead of
# mistaking argparse.REMAINDER for no dry-run. Structural checks below make the
# declaration fail closed if a launcher changes.
_DELEGATED_DRY_RUN_COMMANDS = {
    "source-reference-coverage-audit": (
        "coverage_audit_argv",
        "command_source_reference_coverage_audit",
    ),
}

# A parser leaf with ``argparse.REMAINDER`` may bind one content-free callback
# under this private attribute.  The callback is the delegated command's real
# grammar authority and returns only syntax validity, requested mode, and a
# fixed reason code.  Both generated suggestions and live dispatch consume the
# same callback; neither path treats a successfully collected remainder as a
# successfully parsed delegated invocation.
_DELEGATED_ARGUMENT_SYNTAX_ATTRIBUTE = (
    "_wom_delegated_argument_syntax_status"
)
_DELEGATED_ARGUMENT_SYNTAX_KEYS = frozenset(
    {"valid", "requested_mode", "reason_code"}
)
_APPROVAL_SCOPE_PREDICATE_ATTRIBUTE = "_wom_approval_scope_predicate"


def compound_approval_fixed_closed_contract(command: str) -> dict[str, Any]:
    """Return the shared content-free approval truth for one closed writer."""

    normalized = " ".join(str(command or "").split())
    if normalized not in COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS:
        raise ValueError("compound_approval_command_not_fixed_closed")
    return {
        "approval_status": APPROVAL_FIXED_CLOSED,
        "approval_reason_code": COMPOUND_APPROVAL_REASON_CODE,
        "approved_write_implemented": False,
        "actionable_handoff_available": False,
    }


def compound_approval_fixed_closed_plan_contract(
    plan_command: str,
) -> dict[str, Any]:
    """Separate a safe validation preview from unavailable approval authority."""

    normalized = " ".join(str(plan_command or "").split())
    writer = COMPOUND_APPROVAL_FIXED_CLOSED_PLAN_WRITERS.get(normalized)
    if writer is None:
        raise ValueError("compound_approval_plan_command_not_registered")
    return {
        **compound_approval_fixed_closed_contract(writer),
        "validation_preview_available": True,
        "validation_digest_is_approval_authority": False,
        "writer_command": writer,
    }


def _subparser_actions(
    parser: argparse.ArgumentParser,
) -> tuple[argparse._SubParsersAction, ...]:
    return tuple(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )


def _grouped_choices(
    action: argparse._SubParsersAction,
) -> Iterable[tuple[str, tuple[str, ...], argparse.ArgumentParser]]:
    """Yield one canonical name, its aliases, and parser per parser object.

    ``argparse`` inserts the canonical name before aliases in ``choices``.
    Grouping by parser identity prevents aliases from becoming duplicate
    command records while retaining every accepted invocation surface.
    """

    grouped: dict[int, tuple[list[str], argparse.ArgumentParser]] = {}
    for name, command_parser in action.choices.items():
        group = grouped.setdefault(id(command_parser), ([], command_parser))
        group[0].append(name)
    for names, command_parser in grouped.values():
        yield names[0], tuple(sorted(names[1:])), command_parser


def _option_exposed(
    parser: argparse.ArgumentParser,
    option: str,
) -> bool:
    return any(option in action.option_strings for action in parser._actions)


def _invocation_surface_available(parser: argparse.ArgumentParser) -> bool:
    return callable(parser._defaults.get("func"))


def _dry_run_exposed(
    canonical_path: str,
    parser: argparse.ArgumentParser,
) -> bool:
    if _option_exposed(parser, "--dry-run"):
        return True
    delegated = _DELEGATED_DRY_RUN_COMMANDS.get(canonical_path)
    if delegated is None:
        return False
    remainder_dest, expected_handler_name = delegated
    handler = parser._defaults.get("func")
    positional_actions = [
        action
        for action in parser._actions
        if not action.option_strings
        and not isinstance(action, argparse._SubParsersAction)
    ]
    return (
        getattr(handler, "__name__", None) == expected_handler_name
        and len(positional_actions) == 1
        and positional_actions[0].dest == remainder_dest
        and positional_actions[0].nargs == argparse.REMAINDER
    )


def _parser_approval_scope(
    parser: argparse.ArgumentParser,
) -> dict[str, Any] | None:
    """Return one strictly content-free parser-declared approval scope."""

    raw = parser._defaults.get("_wom_approval_scope")
    if raw is None:
        return None
    if type(raw) is not dict:
        raise ValueError("command_approval_scope_invalid")
    if (
        raw.get("outside_scope_status") != APPROVAL_FIXED_CLOSED
        or raw.get("outside_scope_reason_code") != COMPOUND_APPROVAL_REASON_CODE
    ):
        raise ValueError("command_approval_scope_invalid")
    common = {
        "outside_scope_status": APPROVAL_FIXED_CLOSED,
        "outside_scope_reason_code": COMPOUND_APPROVAL_REASON_CODE,
    }
    if raw.get("kind") == "namespace_predicate":
        if (
            set(raw) != {"kind", "predicate_ref", *common}
            or type(raw.get("predicate_ref")) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]*", raw["predicate_ref"]) is None
            or not callable(
                getattr(parser, _APPROVAL_SCOPE_PREDICATE_ATTRIBUTE, None)
            )
        ):
            raise ValueError("command_approval_scope_invalid")
        return {
            "kind": "namespace_predicate",
            "predicate_ref": raw["predicate_ref"],
            **common,
        }
    if raw.get("kind") == "argument_value_allowlist":
        if set(raw) != {
            "kind",
            "argument",
            "allowed_values",
            *common,
        }:
            raise ValueError("command_approval_scope_invalid")
        argument = raw.get("argument")
        allowed_values = raw.get("allowed_values")
        if (
            type(argument) is not str
            or re.fullmatch(r"--[a-z0-9][a-z0-9-]*", argument) is None
            or not _option_exposed(parser, argument)
            or type(allowed_values) is not list
            or not allowed_values
            or any(
                type(value) is not str
                or re.fullmatch(r"[a-z0-9][a-z0-9-]*", value) is None
                for value in allowed_values
            )
            or len(set(allowed_values)) != len(allowed_values)
        ):
            raise ValueError("command_approval_scope_invalid")
        return {
            "kind": "argument_value_allowlist",
            "argument": argument,
            "allowed_values": sorted(allowed_values),
            **common,
        }
    if raw.get("kind") in {
        "argument_flag_exactly_one_allowlist",
        "argument_flag_any_allowlist",
    }:
        if set(raw) != {"kind", "allowed_flags", *common}:
            raise ValueError("command_approval_scope_invalid")
        allowed_flags = raw.get("allowed_flags")
        if (
            type(allowed_flags) is not list
            or not allowed_flags
            or any(
                type(flag) is not str
                or re.fullmatch(r"--[a-z0-9][a-z0-9-]*", flag) is None
                or not _option_exposed(parser, flag)
                for flag in allowed_flags
            )
            or len(set(allowed_flags)) != len(allowed_flags)
        ):
            raise ValueError("command_approval_scope_invalid")
        return {
            "kind": raw["kind"],
            "allowed_flags": sorted(allowed_flags),
            **common,
        }
    raise ValueError("command_approval_scope_invalid")


def _normalize_fixed_closed_commands(
    fixed_closed_commands: AbstractSet[str],
) -> frozenset[str]:
    normalized: set[str] = set()
    for command in fixed_closed_commands:
        if not isinstance(command, str) or not command.strip():
            raise TypeError("fixed_closed_command_invalid")
        normalized.add(" ".join(command.split()))
    return frozenset(normalized)


def _alias_paths(
    parent_invocation_paths: tuple[tuple[str, ...], ...],
    canonical_parent_path: tuple[str, ...],
    canonical_name: str,
    aliases: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    canonical_path = canonical_parent_path + (canonical_name,)
    segment_names = (canonical_name, *aliases)
    invocation_paths = tuple(
        prefix + (name,)
        for prefix, name in product(parent_invocation_paths, segment_names)
    )
    return canonical_path, invocation_paths


def build_command_status_inventory(
    parser: argparse.ArgumentParser,
    fixed_closed_commands: AbstractSet[str],
) -> dict[str, Any]:
    """Return a stable JSON-ready inventory derived only from ``parser``.

    A fixed-closed entry may name either a canonical top-level command or a
    canonical space-delimited command path.  Alias names never decide the
    approval classification.  A parser without ``--approve`` is always
    ``approval_not_exposed``, even if its name was supplied accidentally in
    ``fixed_closed_commands``.
    """

    if not isinstance(parser, argparse.ArgumentParser):
        raise TypeError("command_status_parser_invalid")
    fixed_closed = _normalize_fixed_closed_commands(fixed_closed_commands)
    matched_fixed_closed: set[str] = set()
    commands: list[dict[str, Any]] = []

    def walk(
        current_parser: argparse.ArgumentParser,
        canonical_parent_path: tuple[str, ...],
        parent_invocation_paths: tuple[tuple[str, ...], ...],
        parser_ancestry: frozenset[int],
    ) -> None:
        for subparsers in _subparser_actions(current_parser):
            for canonical_name, aliases, command_parser in _grouped_choices(
                subparsers
            ):
                parser_id = id(command_parser)
                if parser_id in parser_ancestry:
                    raise ValueError("command_parser_cycle_detected")
                canonical_path, invocation_paths = _alias_paths(
                    parent_invocation_paths,
                    canonical_parent_path,
                    canonical_name,
                    aliases,
                )

                if _invocation_surface_available(command_parser):
                    canonical_path_text = " ".join(canonical_path)
                    canonical_top_level = canonical_path[0]
                    approval_exposed = _option_exposed(
                        command_parser,
                        "--approve",
                    )
                    matching_fixed_closed = {
                        command
                        for command in fixed_closed
                        if command
                        in {canonical_top_level, canonical_path_text}
                    }
                    if not approval_exposed:
                        approval_status = APPROVAL_NOT_EXPOSED
                        approval_reason_code = None
                    elif matching_fixed_closed:
                        approval_status = APPROVAL_FIXED_CLOSED
                        approval_reason_code = COMPOUND_APPROVAL_REASON_CODE
                        matched_fixed_closed.update(matching_fixed_closed)
                    else:
                        approval_status = APPROVAL_AVAILABLE
                        approval_reason_code = None
                    approval_scope = (
                        _parser_approval_scope(command_parser)
                        if approval_status == APPROVAL_AVAILABLE
                        else None
                    )

                    alias_path_texts = sorted(
                        {
                            " ".join(invocation_path)
                            for invocation_path in invocation_paths
                            if invocation_path != canonical_path
                        }
                    )
                    commands.append(
                        {
                            "canonical_path": canonical_path_text,
                            "alias_paths": alias_path_texts,
                            "approval_status": approval_status,
                            "approval_reason_code": approval_reason_code,
                            "approval_scope": approval_scope,
                            "approval_exposure_history": approval_exposure_history(
                                canonical_path_text, approval_status
                            ),
                            "dry_run_exposed": _dry_run_exposed(
                                canonical_path_text,
                                command_parser,
                            ),
                            "invocation_surface_available": True,
                        }
                    )

                walk(
                    command_parser,
                    canonical_path,
                    invocation_paths,
                    parser_ancestry | {parser_id},
                )

    walk(parser, (), ((),), frozenset({id(parser)}))
    commands.sort(key=lambda command: command["canonical_path"])

    status_counts = {
        status: sum(
            command["approval_status"] == status for command in commands
        )
        for status in APPROVAL_STATUSES
    }
    alias_path_count = sum(len(command["alias_paths"]) for command in commands)
    conditional_approval_count = sum(
        command["approval_scope"] is not None for command in commands
    )
    return {
        "schema": COMMAND_STATUS_INVENTORY_SCHEMA,
        "state": "complete",
        "parser_derived": True,
        "prerequisites_evaluated": False,
        "private_values_echoed": False,
        "external_effects_performed": False,
        "counts": {
            "total_command_count": len(commands),
            "canonical_executable_command_count": len(commands),
            "alias_invocation_path_count": alias_path_count,
            "invocation_path_count": len(commands) + alias_path_count,
            "approval_status_counts": status_counts,
            "approval_available_command_count": status_counts[
                APPROVAL_AVAILABLE
            ],
            "approval_fixed_closed_command_count": status_counts[
                APPROVAL_FIXED_CLOSED
            ],
            "approval_not_exposed_command_count": status_counts[
                APPROVAL_NOT_EXPOSED
            ],
            "conditional_approval_command_count": conditional_approval_count,
            "dry_run_exposed_command_count": sum(
                bool(command["dry_run_exposed"]) for command in commands
            ),
            "supplied_fixed_closed_command_count": len(fixed_closed),
            "matched_fixed_closed_command_count": len(
                matched_fixed_closed
            ),
            "unmatched_fixed_closed_command_count": len(
                fixed_closed - matched_fixed_closed
            ),
        },
        "commands": commands,
    }


def _suggested_command_tokens(invocation: str) -> tuple[str, ...] | None:
    if type(invocation) is not str or not invocation.strip():
        return None
    try:
        tokens = tuple(shlex.split(invocation, posix=True))
    except ValueError:
        return None
    return tokens or None


_COMMAND_PATH_PATTERN = re.compile(
    r"[a-z0-9][a-z0-9-]*(?: [a-z0-9][a-z0-9-]*)*"
)
_OPTION_PATTERN = re.compile(r"--[a-z0-9][a-z0-9-]*")
_ALLOWLIST_VALUE_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")
_PORTABLE_PLACEHOLDER_PATTERN = re.compile(
    r"<[A-Za-z0-9][A-Za-z0-9_.:-]*(?::\.\.\.)?>"
)
_MAX_SUGGESTED_COMMAND_LENGTH = 32 * 1024
_MAX_SUGGESTED_COMMAND_TOKEN_COUNT = 2048
_MAX_SUGGESTED_COMMAND_TOKEN_LENGTH = 8192


def _portable_invocation_syntax_status(invocation: str) -> tuple[bool, str | None]:
    """Check only WOM's deliberately small, shell-neutral suggestion grammar.

    This is not a PowerShell, cmd.exe, or POSIX shell parser.  Shell control,
    expansion, comments, redirection, and multi-line input are rejected instead
    of being interpreted.  The caller can therefore tokenize a WOM-generated
    portable suggestion without claiming that arbitrary shell syntax was
    evaluated.
    """

    if type(invocation) is not str or not invocation.strip():
        return False, "suggested_command_parse_failed"
    if len(invocation) > _MAX_SUGGESTED_COMMAND_LENGTH:
        return False, "suggested_command_portable_syntax_unsafe"
    if any(
        unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
        for character in invocation
    ):
        return False, "suggested_command_portable_syntax_unsafe"
    lowered = invocation.casefold()
    if any(
        marker in lowered
        for marker in (
            "`",
            ";",
            "|",
            "&",
            "$",
            "@",
            "\\",
            "*",
            "?",
            "!",
        )
    ):
        return False, "suggested_command_portable_syntax_unsafe"
    if re.search(r"%[^%\s]+%", invocation) is not None:
        return False, "suggested_command_portable_syntax_unsafe"
    return True, None


def _portable_tokens_are_safe(tokens: tuple[str, ...]) -> bool:
    if (
        not tokens
        or len(tokens) > _MAX_SUGGESTED_COMMAND_TOKEN_COUNT
        or any(len(token) > _MAX_SUGGESTED_COMMAND_TOKEN_LENGTH for token in tokens)
    ):
        return False
    for token in tokens:
        if token == "--%" or token.startswith("#"):
            return False
        if "<" in token or ">" in token:
            if _PORTABLE_PLACEHOLDER_PATTERN.fullmatch(token) is None:
                return False
    return True


def _validated_approval_scope(scope: Any) -> dict[str, Any] | None:
    if scope is None:
        return None
    if type(scope) is not dict:
        raise ValueError("command_status_inventory_invalid")
    common = {
        "outside_scope_status": APPROVAL_FIXED_CLOSED,
        "outside_scope_reason_code": COMPOUND_APPROVAL_REASON_CODE,
    }
    if (
        scope.get("outside_scope_status") != APPROVAL_FIXED_CLOSED
        or scope.get("outside_scope_reason_code")
        != COMPOUND_APPROVAL_REASON_CODE
    ):
        raise ValueError("command_status_inventory_invalid")
    kind = scope.get("kind")
    if kind == "namespace_predicate":
        if (
            set(scope) != {"kind", "predicate_ref", *common}
            or type(scope.get("predicate_ref")) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]*", scope["predicate_ref"]) is None
        ):
            raise ValueError("command_status_inventory_invalid")
        return {"kind": kind, "predicate_ref": scope["predicate_ref"], **common}
    if kind == "argument_value_allowlist":
        if set(scope) != {"kind", "argument", "allowed_values", *common}:
            raise ValueError("command_status_inventory_invalid")
        argument = scope.get("argument")
        allowed_values = scope.get("allowed_values")
        if (
            type(argument) is not str
            or _OPTION_PATTERN.fullmatch(argument) is None
            or type(allowed_values) is not list
            or not allowed_values
            or any(
                type(value) is not str
                or _ALLOWLIST_VALUE_PATTERN.fullmatch(value) is None
                for value in allowed_values
            )
            or len(set(allowed_values)) != len(allowed_values)
        ):
            raise ValueError("command_status_inventory_invalid")
        return {
            "kind": kind,
            "argument": argument,
            "allowed_values": sorted(allowed_values),
            **common,
        }
    if kind in {
        "argument_flag_exactly_one_allowlist",
        "argument_flag_any_allowlist",
    }:
        if set(scope) != {"kind", "allowed_flags", *common}:
            raise ValueError("command_status_inventory_invalid")
        allowed_flags = scope.get("allowed_flags")
        if (
            type(allowed_flags) is not list
            or not allowed_flags
            or any(
                type(flag) is not str
                or _OPTION_PATTERN.fullmatch(flag) is None
                for flag in allowed_flags
            )
            or len(set(allowed_flags)) != len(allowed_flags)
        ):
            raise ValueError("command_status_inventory_invalid")
        return {
            "kind": kind,
            "allowed_flags": sorted(allowed_flags),
            **common,
        }
    raise ValueError("command_status_inventory_invalid")


def _validated_inventory_commands(inventory: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    if type(inventory) is not dict:
        raise TypeError("command_status_inventory_invalid")
    if (
        inventory.get("schema") != COMMAND_STATUS_INVENTORY_SCHEMA
        or inventory.get("state") != "complete"
        or inventory.get("parser_derived") is not True
        or inventory.get("prerequisites_evaluated") is not False
        or inventory.get("private_values_echoed") is not False
        or inventory.get("external_effects_performed") is not False
        or type(inventory.get("commands")) is not list
    ):
        raise TypeError("command_status_inventory_invalid")

    expected_keys = {
        "canonical_path",
        "alias_paths",
        "approval_status",
        "approval_reason_code",
        "approval_scope",
        "dry_run_exposed",
        "invocation_surface_available",
    }
    sanitized: list[dict[str, Any]] = []
    canonical_paths: set[str] = set()
    for raw_command in inventory["commands"]:
        if type(raw_command) is not dict or set(raw_command) not in (
            expected_keys,
            expected_keys | {"approval_exposure_history"},
        ):
            raise TypeError("command_status_inventory_invalid")
        canonical_path = raw_command.get("canonical_path")
        alias_paths = raw_command.get("alias_paths")
        if (
            type(canonical_path) is not str
            or _COMMAND_PATH_PATTERN.fullmatch(canonical_path) is None
            or canonical_path in canonical_paths
            or type(alias_paths) is not list
            or any(
                type(path) is not str
                or _COMMAND_PATH_PATTERN.fullmatch(path) is None
                for path in alias_paths
            )
            or len(set(alias_paths)) != len(alias_paths)
            or canonical_path in alias_paths
        ):
            raise TypeError("command_status_inventory_invalid")
        canonical_paths.add(canonical_path)

        approval_status = raw_command.get("approval_status")
        approval_reason_code = raw_command.get("approval_reason_code")
        approval_scope = _validated_approval_scope(
            raw_command.get("approval_scope")
        )
        if approval_status == APPROVAL_AVAILABLE:
            if approval_reason_code is not None:
                raise ValueError("command_status_inventory_invalid")
        elif approval_status == APPROVAL_FIXED_CLOSED:
            if (
                approval_reason_code != COMPOUND_APPROVAL_REASON_CODE
                or approval_scope is not None
            ):
                raise ValueError("command_status_inventory_invalid")
        elif approval_status == APPROVAL_NOT_EXPOSED:
            if approval_reason_code is not None or approval_scope is not None:
                raise ValueError("command_status_inventory_invalid")
        else:
            raise ValueError("command_status_inventory_invalid")
        history = approval_exposure_history("", approval_status)
        if "approval_exposure_history" in raw_command:
            raw_history = raw_command["approval_exposure_history"]
            expected_history = approval_exposure_history(canonical_path, approval_status)
            if (
                type(raw_history) is not dict
                or raw_history.get("successful_use_verified") is not False
                or (raw_history != history and raw_history != expected_history)
            ):
                raise ValueError("command_status_inventory_invalid")
            history = dict(raw_history)
        if (
            type(raw_command.get("dry_run_exposed")) is not bool
            or raw_command.get("invocation_surface_available") is not True
        ):
            raise TypeError("command_status_inventory_invalid")
        sanitized.append(
            {
                "canonical_path": canonical_path,
                "alias_paths": sorted(alias_paths),
                "approval_status": approval_status,
                "approval_reason_code": approval_reason_code,
                "approval_scope": approval_scope,
                "approval_exposure_history": history,
                "dry_run_exposed": raw_command["dry_run_exposed"],
                "invocation_surface_available": True,
            }
        )
    return tuple(sanitized)


def _approval_scope_summary(scope: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Expose only the public scope shape, never allowlisted input values."""

    if scope is None:
        return None
    if scope["kind"] == "namespace_predicate":
        return {
            "kind": scope["kind"],
            "predicate_ref": scope["predicate_ref"],
            "allowlisted_entry_count": None,
            "values_disclosed": False,
        }
    if scope["kind"] == "argument_value_allowlist":
        count = len(scope["allowed_values"])
    else:
        count = len(scope["allowed_flags"])
    return {
        "kind": scope["kind"],
        "allowlisted_entry_count": count,
        "values_disclosed": False,
    }


def _trusted_parser_for_path(
    parser: argparse.ArgumentParser,
    invocation_path: tuple[str, ...],
) -> argparse.ArgumentParser | None:
    current = parser
    for segment in invocation_path:
        matches = {
            id(action.choices[segment]): action.choices[segment]
            for action in _subparser_actions(current)
            if segment in action.choices
        }
        if len(matches) != 1:
            return None
        current = next(iter(matches.values()))
    return current


def _syntax_projection(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Clone only argparse arity/requiredness without types or handlers."""

    projection = argparse.ArgumentParser(
        add_help=False,
        allow_abbrev=parser.allow_abbrev,
        exit_on_error=False,
    )
    group_targets: dict[int, argparse._MutuallyExclusiveGroup] = {}
    for group in parser._mutually_exclusive_groups:
        target = projection.add_mutually_exclusive_group(required=group.required)
        for action in group._group_actions:
            group_targets[id(action)] = target

    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        target: Any = group_targets.get(id(action), projection)
        if action.option_strings:
            kwargs: dict[str, Any] = {
                "dest": action.dest,
                "default": argparse.SUPPRESS,
                "required": bool(action.required),
            }
            if isinstance(action, argparse._StoreTrueAction):
                kwargs["action"] = "store_true"
            elif isinstance(action, argparse._StoreFalseAction):
                kwargs["action"] = "store_false"
            elif isinstance(action, argparse._AppendAction):
                kwargs["action"] = "append"
                if action.nargs is not None:
                    kwargs["nargs"] = action.nargs
            elif action.nargs == 0:
                # Preserve zero-arity syntax for count/store-const and custom
                # flag actions without invoking their original behavior.
                kwargs["action"] = "store_true"
            elif action.nargs is not None:
                kwargs["nargs"] = action.nargs
            target.add_argument(*action.option_strings, **kwargs)
        else:
            kwargs = {"default": argparse.SUPPRESS}
            if action.nargs is not None:
                kwargs["nargs"] = action.nargs
            target.add_argument(action.dest, **kwargs)
    return projection


def _delegated_argument_syntax_status(
    parser: argparse.ArgumentParser,
    argument_tokens: tuple[str, ...],
) -> dict[str, Any] | None:
    callback = getattr(parser, _DELEGATED_ARGUMENT_SYNTAX_ATTRIBUTE, None)
    if callback is None:
        return None
    if not callable(callback):
        raise ValueError("delegated_argument_syntax_contract_invalid")
    try:
        raw = callback(argument_tokens)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        raise ValueError("delegated_argument_syntax_unavailable") from None
    if type(raw) is not dict or set(raw) != _DELEGATED_ARGUMENT_SYNTAX_KEYS:
        raise ValueError("delegated_argument_syntax_contract_invalid")
    valid = raw.get("valid")
    requested_mode = raw.get("requested_mode")
    reason_code = raw.get("reason_code")
    if (
        type(valid) is not bool
        or requested_mode
        not in {"dry_run", "approve", "conflicting", "unspecified"}
        or (
            reason_code is not None
            and (
                type(reason_code) is not str
                or re.fullmatch(r"[a-z][a-z0-9_]{0,95}", reason_code) is None
            )
        )
        or (valid and reason_code is not None)
        or (not valid and reason_code is None)
    ):
        raise ValueError("delegated_argument_syntax_contract_invalid")
    return {
        "valid": valid,
        "requested_mode": requested_mode,
        "reason_code": reason_code,
    }


def _evaluate_argument_syntax(
    trusted_parser: argparse.ArgumentParser,
    matched_path: tuple[str, ...],
    argument_tokens: tuple[str, ...],
) -> tuple[
    bool,
    bool | None,
    str | None,
    argparse.ArgumentParser | None,
    argparse.Namespace | None,
]:
    leaf = _trusted_parser_for_path(trusted_parser, matched_path)
    if leaf is None:
        return (
            False,
            None,
            "suggested_command_trusted_parser_path_mismatch",
            None,
            None,
        )
    try:
        delegated = _delegated_argument_syntax_status(leaf, argument_tokens)
    except ValueError:
        return (
            False,
            None,
            "suggested_command_argument_syntax_not_evaluated",
            None,
            None,
        )
    if delegated is not None:
        if delegated["valid"] is not True:
            return (
                True,
                False,
                str(delegated["reason_code"]),
                None,
                None,
            )
        return (
            True,
            True,
            None,
            leaf,
            argparse.Namespace(
                _wom_delegated_requested_mode=delegated["requested_mode"]
            ),
        )
    try:
        projection = _syntax_projection(leaf)
    except (TypeError, ValueError, argparse.ArgumentError):
        return (
            False,
            None,
            "suggested_command_argument_syntax_not_evaluated",
            None,
            None,
        )
    try:
        with redirect_stderr(io.StringIO()):
            namespace = projection.parse_args(argument_tokens)
    except (SystemExit, argparse.ArgumentError):
        return (
            True,
            False,
            "suggested_command_argument_syntax_invalid",
            None,
            None,
        )
    return True, True, None, leaf, namespace


def _namespace_requested_mode(namespace: argparse.Namespace) -> str:
    delegated = getattr(namespace, "_wom_delegated_requested_mode", None)
    if delegated in {"dry_run", "approve", "conflicting", "unspecified"}:
        return str(delegated)
    dry_run = getattr(namespace, "dry_run", False) is True
    approve = getattr(namespace, "approve", False) is True
    return (
        "conflicting"
        if dry_run and approve
        else "dry_run"
        if dry_run
        else "approve"
        if approve
        else "unspecified"
    )


def _argument_syntax_unavailable(
    command: Mapping[str, Any],
    *,
    requested_mode: str,
) -> dict[str, Any]:
    availability = _capability_availability_for_command(
        command,
        requested_mode=requested_mode,
    )
    return {
        **availability,
        "state": CAPABILITY_MODE_UNAVAILABLE,
        "available": False,
        "reason_code": "capability_argument_syntax_invalid",
        "detail_reason_code": "capability_argument_syntax_invalid",
    }


def _option_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    return tokens[: tokens.index("--")] if "--" in tokens else tokens


def _requested_mode(tokens: tuple[str, ...]) -> str:
    option_tokens = _option_tokens(tokens)
    dry_run = "--dry-run" in option_tokens
    approve = "--approve" in option_tokens
    if dry_run and approve:
        return "conflicting"
    if dry_run:
        return "dry_run"
    if approve:
        return "approve"
    return "unspecified"


def _approval_argument_values(
    tokens: tuple[str, ...],
    argument: str,
) -> tuple[str, ...]:
    values: list[str] = []
    for index, token in enumerate(tokens):
        if token == argument:
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
                values.append(tokens[index + 1])
        elif token.startswith(argument + "="):
            values.append(token.split("=", 1)[1])
    return tuple(values)


def _approval_scope_mode_status(
    scope: Mapping[str, Any] | None,
    argument_tokens: tuple[str, ...],
    *,
    argument_predicate_matched: bool | None = None,
) -> tuple[bool, str | None]:
    if scope is None:
        return True, None
    kind = scope.get("kind")
    outside_reason = COMPOUND_APPROVAL_REASON_CODE
    if kind == "namespace_predicate":
        # Only a trusted parser callback can classify private argument values.
        # Public inventories and raw-token callers remain conservative.
        return (
            (True, None)
            if argument_predicate_matched is True
            else (False, outside_reason)
        )
    if kind == "argument_value_allowlist":
        argument = scope.get("argument")
        allowed_values = scope.get("allowed_values")
        if type(argument) is not str or type(allowed_values) is not list:
            raise ValueError("command_approval_scope_invalid")
        values = _approval_argument_values(argument_tokens, argument)
        if len(values) != 1 or values[0] not in allowed_values:
            return False, outside_reason
        return True, None
    if kind in {
        "argument_flag_exactly_one_allowlist",
        "argument_flag_any_allowlist",
    }:
        allowed_flags = scope.get("allowed_flags")
        if type(allowed_flags) is not list:
            raise ValueError("command_approval_scope_invalid")
        present = {
            flag
            for flag in allowed_flags
            if type(flag) is str and flag in argument_tokens
        }
        allowed = (
            len(present) == 1
            if kind == "argument_flag_exactly_one_allowlist"
            else bool(present)
        )
        return (True, None) if allowed else (False, outside_reason)
    raise ValueError("command_approval_scope_invalid")


def _capability_availability_for_command(
    command: Mapping[str, Any],
    *,
    requested_mode: str,
    argument_tokens: tuple[str, ...] = (),
    argument_predicate_matched: bool | None = None,
) -> dict[str, Any]:
    """Resolve one parser-declared mode through the shared availability gate.

    This deliberately answers only whether the installed command surface can
    dispatch the requested mode.  Archive, provider, credential, and other
    runtime prerequisites remain separate.  Argument values may be inspected
    for a parser-declared allowlist, but they are never returned.
    """

    if requested_mode not in {
        "dry_run",
        "approve",
        "conflicting",
        "unspecified",
    }:
        raise ValueError("capability_requested_mode_invalid")
    if (
        type(argument_tokens) is not tuple
        or any(type(token) is not str for token in argument_tokens)
    ):
        raise TypeError("capability_argument_tokens_invalid")

    canonical_path = command.get("canonical_path")
    invocation_available = command.get("invocation_surface_available") is True
    dry_run_exposed = command.get("dry_run_exposed") is True
    approval_status = command.get("approval_status")
    approval_reason_code = command.get("approval_reason_code")
    raw_scope = command.get("approval_scope")
    approval_scope = dict(raw_scope) if isinstance(raw_scope, Mapping) else None

    available: bool | None
    state: str
    reason_code: str | None = None
    detail_reason_code: str | None = None
    if requested_mode == "unspecified":
        available = None
        state = CAPABILITY_NOT_REQUESTED
    elif requested_mode == "conflicting":
        available = False
        state = CAPABILITY_MODE_UNAVAILABLE
        reason_code = "capability_mode_conflicting"
    elif not invocation_available:
        available = False
        state = CAPABILITY_MODE_UNAVAILABLE
        reason_code = "invocation_surface_unavailable"
    elif requested_mode == "dry_run":
        available = dry_run_exposed
        state = CAPABILITY_AVAILABLE if available else CAPABILITY_MODE_UNAVAILABLE
        if not available:
            reason_code = "dry_run_unavailable"
    else:
        if approval_status == APPROVAL_AVAILABLE:
            scope_available, scope_reason = _approval_scope_mode_status(
                approval_scope,
                argument_tokens,
                argument_predicate_matched=argument_predicate_matched,
            )
            available = scope_available
            if available:
                state = CAPABILITY_AVAILABLE
            else:
                state = CAPABILITY_WRITER_UNAVAILABLE
                reason_code = WRITER_UNAVAILABLE_REASON_CODE
                detail_reason_code = scope_reason
        else:
            available = False
            state = CAPABILITY_WRITER_UNAVAILABLE
            reason_code = WRITER_UNAVAILABLE_REASON_CODE
            detail_reason_code = str(
                approval_reason_code
                or approval_status
                or "approval_surface_unavailable"
            )

    return {
        "schema": CAPABILITY_AVAILABILITY_SCHEMA,
        "canonical_path": canonical_path,
        "requested_mode": requested_mode,
        "state": state,
        "available": available,
        "reason_code": reason_code,
        "detail_reason_code": detail_reason_code,
        "approval_status": approval_status,
        "approval_exposure_history": dict(command["approval_exposure_history"]),
        "dry_run_exposed": dry_run_exposed,
        "parser_derived": True,
        "argument_scope_evaluated": requested_mode == "approve",
        "prerequisites_evaluated": False,
        "private_values_echoed": False,
        "external_effects_performed": False,
    }


def resolve_capability_availability(
    inventory: Mapping[str, Any],
    command_path: str,
    *,
    requested_mode: str,
    argument_tokens: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Resolve a canonical or alias command path without executing it."""

    commands = _validated_inventory_commands(inventory)
    if (
        type(command_path) is not str
        or _COMMAND_PATH_PATTERN.fullmatch(command_path) is None
    ):
        raise ValueError("capability_command_path_invalid")
    matches = [
        command
        for command in commands
        if command_path == command["canonical_path"]
        or command_path in command["alias_paths"]
    ]
    if len(matches) != 1:
        raise ValueError("capability_command_path_unresolved")
    return _capability_availability_for_command(
        matches[0],
        requested_mode=requested_mode,
        argument_tokens=argument_tokens,
    )


def build_capability_availability_projection(
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Return content-free dry-run and writer availability for capabilities."""

    commands = _validated_inventory_commands(inventory)
    rows = []
    for command in commands:
        rows.append(
            {
                "canonical_path": command["canonical_path"],
                "dry_run": _capability_availability_for_command(
                    command,
                    requested_mode="dry_run",
                ),
                # Conditional approval rows are conservatively unavailable
                # without exact arguments.  Actual dispatch resolves them again
                # after argparse has validated the concrete invocation.
                "approve_without_arguments": (
                    _capability_availability_for_command(
                        command,
                        requested_mode="approve",
                    )
                ),
            }
        )
    return {
        "schema": "wom-kit/capability-availability-projection/v0.1",
        "state": "complete",
        "rows": rows,
        "parser_derived": True,
        "prerequisites_evaluated": False,
        "private_values_echoed": False,
        "external_effects_performed": False,
    }


def _selected_canonical_parser_path(
    parser: argparse.ArgumentParser,
    namespace: argparse.Namespace,
) -> tuple[str, argparse.ArgumentParser]:
    current = parser
    canonical_segments: list[str] = []
    while True:
        matches: list[tuple[str, argparse.ArgumentParser]] = []
        for action in _subparser_actions(current):
            selected = getattr(namespace, action.dest, None)
            if type(selected) is not str or selected not in action.choices:
                continue
            selected_parser = action.choices[selected]
            canonical_name = next(
                name
                for name, candidate in action.choices.items()
                if candidate is selected_parser
            )
            matches.append((canonical_name, selected_parser))
        if not matches:
            break
        if len(matches) != 1:
            raise ValueError("capability_namespace_path_ambiguous")
        canonical_name, current = matches[0]
        canonical_segments.append(canonical_name)
    if not canonical_segments or not callable(current._defaults.get("func")):
        raise ValueError("capability_namespace_path_unresolved")
    return " ".join(canonical_segments), current


def _namespace_approval_scope_tokens(
    leaf_parser: argparse.ArgumentParser,
    namespace: argparse.Namespace,
    scope: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if scope is None:
        return ()
    option_actions = {
        option: action
        for action in leaf_parser._actions
        for option in action.option_strings
    }
    kind = scope.get("kind")
    if kind == "namespace_predicate":
        return ()
    if kind == "argument_value_allowlist":
        option = scope.get("argument")
        action = option_actions.get(option)
        if type(option) is not str or action is None:
            raise ValueError("command_approval_scope_invalid")
        value = getattr(namespace, action.dest, None)
        if type(value) is not str:
            return ()
        return (option, value)
    if kind in {
        "argument_flag_exactly_one_allowlist",
        "argument_flag_any_allowlist",
    }:
        tokens: list[str] = []
        for option in scope.get("allowed_flags") or []:
            action = option_actions.get(option)
            if action is None:
                raise ValueError("command_approval_scope_invalid")
            value = getattr(namespace, action.dest, None)
            if isinstance(action, argparse._StoreTrueAction):
                selected = value is True
            elif isinstance(action, argparse._StoreFalseAction):
                selected = value is False
            elif isinstance(action, argparse._AppendAction):
                selected = isinstance(value, list) and bool(value)
            else:
                # Value-taking options such as --source-mirror and repeated
                # --markup-receipt are still scope selectors.  Their private
                # values are inspected only for presence and are never copied
                # into the content-free token set or availability record.
                selected = value is not None
            if selected:
                tokens.append(option)
        return tuple(tokens)
    raise ValueError("command_approval_scope_invalid")


def _namespace_approval_predicate_result(
    leaf_parser: argparse.ArgumentParser,
    namespace: argparse.Namespace,
    scope: Mapping[str, Any] | None,
) -> bool | None:
    if scope is None or scope.get("kind") != "namespace_predicate":
        return None
    predicate = getattr(leaf_parser, _APPROVAL_SCOPE_PREDICATE_ATTRIBUTE, None)
    if not callable(predicate):
        raise ValueError("command_approval_scope_invalid")
    # Suggested-command parsing suppresses omitted defaults. Restore only the
    # trusted leaf's argument defaults so its predicate sees the same values as
    # actual argparse dispatch, without copying values into public records.
    predicate_namespace = argparse.Namespace(**{
        action.dest: action.default
        for action in leaf_parser._actions
        if action.dest != argparse.SUPPRESS and action.default != argparse.SUPPRESS
    })
    vars(predicate_namespace).update(vars(namespace))
    result = predicate(predicate_namespace)
    if type(result) is not bool:
        raise ValueError("command_approval_scope_invalid")
    return result


def resolve_namespace_capability_availability(
    parser: argparse.ArgumentParser,
    inventory: Mapping[str, Any],
    namespace: argparse.Namespace,
) -> dict[str, Any]:
    """Resolve actual argparse dispatch through the same availability truth."""

    if not isinstance(parser, argparse.ArgumentParser):
        raise TypeError("capability_parser_invalid")
    if not isinstance(namespace, argparse.Namespace):
        raise TypeError("capability_namespace_invalid")
    canonical_path, leaf_parser = _selected_canonical_parser_path(
        parser,
        namespace,
    )
    commands = _validated_inventory_commands(inventory)
    command = next(
        (row for row in commands if row["canonical_path"] == canonical_path),
        None,
    )
    if command is None:
        raise ValueError("capability_namespace_path_unresolved")
    requested_mode = _namespace_requested_mode(namespace)
    remainder_actions = [
        action
        for action in leaf_parser._actions
        if not action.option_strings and action.nargs == argparse.REMAINDER
    ]
    if getattr(
        leaf_parser,
        _DELEGATED_ARGUMENT_SYNTAX_ATTRIBUTE,
        None,
    ) is not None:
        if len(remainder_actions) != 1:
            raise ValueError("delegated_argument_syntax_contract_invalid")
        raw_tokens = getattr(namespace, remainder_actions[0].dest, None)
        if type(raw_tokens) is not list or any(
            type(token) is not str for token in raw_tokens
        ):
            raise ValueError("delegated_argument_syntax_contract_invalid")
        delegated = _delegated_argument_syntax_status(
            leaf_parser,
            tuple(raw_tokens),
        )
        if delegated is None:
            raise ValueError("delegated_argument_syntax_contract_invalid")
        requested_mode = str(delegated["requested_mode"])
        if delegated["valid"] is not True:
            return _argument_syntax_unavailable(
                command,
                requested_mode=requested_mode,
            )
    argument_tokens = _namespace_approval_scope_tokens(
        leaf_parser,
        namespace,
        command.get("approval_scope"),
    )
    return _capability_availability_for_command(
        command,
        requested_mode=requested_mode,
        argument_tokens=argument_tokens,
        argument_predicate_matched=_namespace_approval_predicate_result(
            leaf_parser, namespace, command.get("approval_scope")
        ),
    )


def _unresolved_suggested_command_status(
    *,
    reason_code: str,
    requested_mode: str,
    portable_syntax_safe: bool | None = None,
    portable_template_placeholders_present: bool | None = None,
    argument_syntax_evaluated: bool = False,
    argument_syntax_valid: bool | None = None,
    argument_syntax_reason_code: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": SUGGESTED_COMMAND_MODE_STATUS_SCHEMA,
        "resolution_state": "unresolved",
        "resolution_scope": None,
        "resolution_reason_code": reason_code,
        "canonical_path": None,
        "matched_invocation_path": None,
        "invocation_surface_available": False,
        "requested_mode": requested_mode,
        "requested_mode_available": None,
        "requested_mode_reason_code": reason_code,
        "dry_run_exposed": None,
        "approval_status": None,
        "approval_reason_code": None,
        "approval_scope": None,
        "approval_mode_available_for_arguments": None,
        "approval_mode_reason_code_for_arguments": reason_code,
        "capability_availability": None,
        "portable_invocation_syntax_evaluated": True,
        "portable_invocation_syntax_safe": portable_syntax_safe,
        "portable_template_placeholders_present": (
            portable_template_placeholders_present
        ),
        "portable_template_substitution_evaluated": False,
        "argument_syntax_evaluated": argument_syntax_evaluated,
        "argument_syntax_valid": argument_syntax_valid,
        "argument_syntax_reason_code": (
            argument_syntax_reason_code or reason_code
        ),
        "shell_syntax_evaluated": False,
        "prerequisites_evaluated": False,
        "full_command_executability_evaluated": False,
        "full_command_executable": None,
        "private_values_echoed": False,
        "external_effects_performed": False,
    }


def resolve_suggested_command_mode(
    inventory: Mapping[str, Any],
    invocation: str,
    *,
    launchers: tuple[str, ...] = ("archive", "wom"),
    trusted_parser: argparse.ArgumentParser | None = None,
) -> dict[str, Any]:
    """Resolve one WOM-generated suggestion without executing or echoing it.

    Resolution is inventory-derived only.  ``requested_mode_available`` answers
    whether the explicit ``--dry-run`` or ``--approve`` mode is exposed by the
    supplied parser-derived inventory.  It never claims that archive-specific
    prerequisites, template substitution, shell parsing, or full command
    execution have passed.  When ``trusted_parser`` is supplied, a sanitized
    argparse projection checks only option/positional arity and requiredness;
    a leaf that delegates ``argparse.REMAINDER`` instead uses its explicitly
    bound content-free grammar projection.  Neither path calls original
    argument types, actions, handlers, or help output.
    The separate
    ``approval_mode_available_for_arguments`` field evaluates the suggestion's
    argument-level approval scope even when the requested mode is dry-run.
    ``invocation`` is the
    product's own portable suggestion syntax, not an arbitrary PowerShell or
    Windows ``CommandLineToArgvW`` command line.
    """

    commands = _validated_inventory_commands(inventory)
    if (
        type(launchers) is not tuple
        or not launchers
        or any(
            type(launcher) is not str
            or _ALLOWLIST_VALUE_PATTERN.fullmatch(launcher) is None
            for launcher in launchers
        )
        or len(set(launchers)) != len(launchers)
    ):
        raise ValueError("suggested_command_launchers_invalid")
    if trusted_parser is not None and not isinstance(
        trusted_parser,
        argparse.ArgumentParser,
    ):
        raise TypeError("suggested_command_trusted_parser_invalid")

    portable_safe, portable_reason = _portable_invocation_syntax_status(
        invocation
    )
    if not portable_safe:
        return _unresolved_suggested_command_status(
            reason_code=portable_reason or "suggested_command_portable_syntax_unsafe",
            requested_mode="unspecified",
            portable_syntax_safe=False,
        )
    tokens = _suggested_command_tokens(invocation)
    requested_mode = _requested_mode(tokens or ())
    if tokens is None or not _portable_tokens_are_safe(tokens):
        return _unresolved_suggested_command_status(
            reason_code=(
                "suggested_command_parse_failed"
                if tokens is None
                else "suggested_command_portable_syntax_unsafe"
            ),
            requested_mode=requested_mode,
            portable_syntax_safe=False,
        )
    placeholders_present = any(
        _PORTABLE_PLACEHOLDER_PATTERN.fullmatch(token) is not None
        for token in tokens
    )
    if tokens[0] not in launchers:
        return _unresolved_suggested_command_status(
            reason_code="suggested_command_launcher_unrecognized",
            requested_mode=requested_mode,
            portable_syntax_safe=True,
            portable_template_placeholders_present=placeholders_present,
        )

    candidates: dict[tuple[str, ...], Mapping[str, Any]] = {}
    for command in commands:
        canonical_path = command.get("canonical_path")
        alias_paths = command.get("alias_paths")
        for path_text in (canonical_path, *alias_paths):
            path_tokens = tuple(path_text.split())
            previous = candidates.get(path_tokens)
            if previous is not None and previous.get("canonical_path") != canonical_path:
                raise ValueError("command_status_invocation_path_ambiguous")
            candidates[path_tokens] = command

    command_tokens = tokens[1:]
    matches = [
        (path_tokens, command)
        for path_tokens, command in candidates.items()
        if command_tokens[: len(path_tokens)] == path_tokens
    ]
    if not matches:
        return _unresolved_suggested_command_status(
            reason_code="suggested_command_not_in_inventory",
            requested_mode=requested_mode,
            portable_syntax_safe=True,
            portable_template_placeholders_present=placeholders_present,
        )
    matched_path, command = max(matches, key=lambda item: len(item[0]))
    raw_argument_tokens = command_tokens[len(matched_path) :]
    argument_tokens = _option_tokens(raw_argument_tokens)
    parsed_leaf: argparse.ArgumentParser | None = None
    parsed_namespace: argparse.Namespace | None = None
    if trusted_parser is None:
        argument_syntax_evaluated = False
        argument_syntax_valid = None
        argument_syntax_reason_code = "suggested_command_trusted_parser_not_supplied"
    else:
        (
            argument_syntax_evaluated,
            argument_syntax_valid,
            argument_syntax_reason_code,
            parsed_leaf,
            parsed_namespace,
        ) = _evaluate_argument_syntax(
            trusted_parser,
            matched_path,
            raw_argument_tokens,
        )
        if argument_syntax_valid is not True:
            unresolved = _unresolved_suggested_command_status(
                reason_code=(
                    argument_syntax_reason_code
                    or "suggested_command_argument_syntax_not_evaluated"
                ),
                requested_mode=requested_mode,
                portable_syntax_safe=True,
                portable_template_placeholders_present=placeholders_present,
                argument_syntax_evaluated=argument_syntax_evaluated,
                argument_syntax_valid=argument_syntax_valid,
                argument_syntax_reason_code=argument_syntax_reason_code,
            )
            if argument_syntax_valid is False:
                unavailable = _argument_syntax_unavailable(
                    command,
                    requested_mode=requested_mode,
                )
                unresolved.update(
                    {
                        "resolution_scope": "inventory_path_and_argument_syntax",
                        "canonical_path": command["canonical_path"],
                        "matched_invocation_path": " ".join(matched_path),
                        "invocation_surface_available": command.get(
                            "invocation_surface_available"
                        )
                        is True,
                        "requested_mode_available": False,
                        "requested_mode_reason_code": unavailable[
                            "reason_code"
                        ],
                        "dry_run_exposed": command.get("dry_run_exposed")
                        is True,
                        "approval_status": command.get("approval_status"),
                        "approval_reason_code": command.get(
                            "approval_reason_code"
                        ),
                        "approval_scope": _approval_scope_summary(
                            command.get("approval_scope")
                        ),
                        "approval_mode_available_for_arguments": False,
                        "approval_mode_reason_code_for_arguments": unavailable[
                            "reason_code"
                        ],
                        "capability_availability": unavailable,
                    }
                )
            return unresolved
        if parsed_leaf is not None and parsed_namespace is not None:
            parsed_mode = _namespace_requested_mode(parsed_namespace)
            # Delegated parsers intentionally receive argparse.REMAINDER, so
            # their mode remains visible only in the validated raw token list.
            # Normal argparse commands use their sanitized parsed namespace,
            # including --option=value and duplicate-option last-wins rules.
            if not any(
                action.nargs == argparse.REMAINDER
                for action in parsed_leaf._actions
            ):
                requested_mode = parsed_mode
    invocation_available = command.get("invocation_surface_available") is True
    dry_run_exposed = command.get("dry_run_exposed") is True
    approval_status = command.get("approval_status")
    approval_reason_code = command.get("approval_reason_code")
    raw_scope = command.get("approval_scope")
    approval_scope = dict(raw_scope) if isinstance(raw_scope, Mapping) else None
    argument_predicate_matched: bool | None = None
    if (
        approval_scope is not None
        and parsed_leaf is not None
        and parsed_namespace is not None
    ):
        argument_tokens = _namespace_approval_scope_tokens(
            parsed_leaf,
            parsed_namespace,
            approval_scope,
        )
        argument_predicate_matched = _namespace_approval_predicate_result(
            parsed_leaf, parsed_namespace, approval_scope
        )

    approval_availability = _capability_availability_for_command(
        command,
        requested_mode="approve",
        argument_tokens=argument_tokens,
        argument_predicate_matched=argument_predicate_matched,
    )
    approval_mode_available_for_arguments = bool(
        approval_availability["available"]
    )
    approval_mode_reason_code_for_arguments = (
        approval_availability["detail_reason_code"]
        or approval_availability["reason_code"]
    )

    capability_availability = _capability_availability_for_command(
        command,
        requested_mode=requested_mode,
        argument_tokens=argument_tokens,
        argument_predicate_matched=argument_predicate_matched,
    )
    requested_mode_available = capability_availability["available"]
    requested_mode_reason_code = capability_availability[
        "detail_reason_code"
    ] or capability_availability["reason_code"]
    # Preserve the established public reason vocabulary while the nested
    # CapabilityAvailability record supplies the new normalized state.
    if requested_mode == "conflicting":
        requested_mode_reason_code = "suggested_command_mode_conflicting"
    elif not invocation_available:
        requested_mode_reason_code = (
            "suggested_command_invocation_surface_unavailable"
        )
    elif requested_mode == "dry_run" and requested_mode_available is False:
        requested_mode_reason_code = "suggested_command_dry_run_not_exposed"

    return {
        "schema": SUGGESTED_COMMAND_MODE_STATUS_SCHEMA,
        "resolution_state": "resolved",
        "resolution_scope": "inventory_path_and_requested_mode_only",
        "resolution_reason_code": None,
        "canonical_path": command["canonical_path"],
        "matched_invocation_path": " ".join(matched_path),
        "invocation_surface_available": invocation_available,
        "requested_mode": requested_mode,
        "requested_mode_available": requested_mode_available,
        "requested_mode_reason_code": requested_mode_reason_code,
        "dry_run_exposed": dry_run_exposed,
        "approval_status": approval_status,
        "approval_reason_code": approval_reason_code,
        "approval_scope": _approval_scope_summary(approval_scope),
        "approval_mode_available_for_arguments": (
            approval_mode_available_for_arguments
        ),
        "approval_mode_reason_code_for_arguments": (
            approval_mode_reason_code_for_arguments
        ),
        "capability_availability": capability_availability,
        "portable_invocation_syntax_evaluated": True,
        "portable_invocation_syntax_safe": True,
        "portable_template_placeholders_present": placeholders_present,
        "portable_template_substitution_evaluated": False,
        "argument_syntax_evaluated": argument_syntax_evaluated,
        "argument_syntax_valid": argument_syntax_valid,
        "argument_syntax_reason_code": argument_syntax_reason_code,
        "shell_syntax_evaluated": False,
        "prerequisites_evaluated": False,
        "full_command_executability_evaluated": False,
        "full_command_executable": None,
        "private_values_echoed": False,
        "external_effects_performed": False,
    }
