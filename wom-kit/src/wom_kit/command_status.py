"""Parser-derived, content-free command approval status inventory.

The inventory describes only facts exposed by an already-built
``argparse.ArgumentParser``.  It does not evaluate command prerequisites,
render help text, execute handlers, or inspect any filesystem, network, or
provider state.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from itertools import product
from typing import AbstractSet, Any


COMMAND_STATUS_INVENTORY_SCHEMA = (
    "wom-kit/command-approval-status-inventory/v0.1"
)

APPROVAL_AVAILABLE = "approval_available"
APPROVAL_FIXED_CLOSED = "approval_fixed_closed"
APPROVAL_NOT_EXPOSED = "approval_not_exposed"
APPROVAL_STATUSES = (
    APPROVAL_AVAILABLE,
    APPROVAL_FIXED_CLOSED,
    APPROVAL_NOT_EXPOSED,
)

COMPOUND_APPROVAL_REASON_CODE = (
    "compound_exact_human_approval_binding_required"
)


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
                            "dry_run_exposed": _option_exposed(
                                command_parser,
                                "--dry-run",
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
