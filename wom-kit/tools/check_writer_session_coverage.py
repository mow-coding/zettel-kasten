"""Compare the parser's approval-available paths with the session-coverage manifest.

Decision 7 of the 2026-09-05 writer-coverage log: compare actual parser paths
against completed adapters and narrowly documented exceptions in CI before
declaring all-writer scope complete. This checker derives the approval
inventory from the real parser (no archive is read), requires every
approval-available path to be classified in ``docs/writer-session-coverage.json``,
rejects stale classifications, and prints the honest denominator. It exits 0
while paths are still pending; it never claims all-writer coverage for them.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = KIT_ROOT / "docs" / "writer-session-coverage.json"
SESSION_OPTIONS = ("--client-app-ref", "--task-route-ref")
ENVIRONMENT_ROUTE = "environment"  # v0.4.36: the broker's WOM_* environment refs
STATUSES = ("session_integrated", "pending", "legacy_exception")


def parser_inventory() -> tuple[dict[str, list[str]], list[str]]:
    sys.path.insert(0, str(KIT_ROOT / "src"))
    from wom_kit import archive_cli  # noqa: WPS433 (deferred import on purpose)

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = archive_cli.main(["capabilities", "--machine"])
    if code != 0:
        raise SystemExit("capabilities --machine failed")
    document = json.loads(out.getvalue())
    data = document["data"]
    options = {row["canonical_path"]: list(row.get("options", [])) for row in data["commands"]}
    available = sorted(
        row["canonical_path"]
        for row in data["approval_status_inventory"]["commands"]
        if row.get("approval_status") == "approval_available"
    )
    return options, available


def check(manifest_path: Path = MANIFEST) -> tuple[list[str], dict[str, int]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return ["writer-session coverage manifest is missing or unreadable."], {}
    if (type(manifest) is not dict or manifest.get("schema") != "wom-kit/writer-session-coverage/v1"
            or not isinstance(manifest.get("paths"), dict)):
        return ["writer-session coverage manifest has an unexpected shape."], {}
    paths = manifest["paths"]
    options, available = parser_inventory()
    problems: list[str] = []
    counts = {status: 0 for status in STATUSES}
    unclassified = sorted(set(available) - set(paths))
    stale = sorted(set(paths) - set(available))
    for path in unclassified:
        problems.append(f"approval-available path is not classified: {path}")
    for path in stale:
        problems.append(f"classified path is no longer approval-available: {path}")
    tests_root = KIT_ROOT / "tests"
    for path, row in sorted(paths.items()):
        status = row.get("status")
        if status not in STATUSES:
            problems.append(f"{path}: unknown status {status!r}")
            continue
        counts[status] += 1
        exposes = any(option in options.get(path, []) for option in SESSION_OPTIONS)
        if status == "session_integrated":
            route = row.get("route", path)
            # v0.4.36 (letter 168 ⑥): a writer whose --approve goes through the
            # exact approval broker resolves the session grant from the process
            # environment refs (WOM_CLIENT_APP_REF / WOM_TASK_ROUTE_REF /
            # WOM_WORK_SESSION_REF); every operation kind is grantable, so the
            # route "environment" is a real integration, not a flag on the path.
            route_exposes = route == ENVIRONMENT_ROUTE or any(
                option in options.get(route, []) for option in SESSION_OPTIONS
            )
            if not route_exposes:
                problems.append(f"{path}: session_integrated but {route} exposes no session refs")
            if route != path:
                counts["session_integrated"] -= 1
                counts["routed"] = counts.get("routed", 0) + 1
                if route != ENVIRONMENT_ROUTE and paths.get(route, {}).get("status") != "session_integrated":
                    problems.append(f"{path}: route {route} is not itself session_integrated")
            evidence = row.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                problems.append(f"{path}: session_integrated without test evidence")
            else:
                for module in evidence:
                    if not (tests_root / f"{module}.py").is_file():
                        problems.append(f"{path}: evidence test module missing: {module}")
        elif exposes:
            problems.append(f"{path}: marked {status} but already exposes session refs; reclassify")
        elif status == "pending" and not str(row.get("target", "")).startswith("v0.4."):
            problems.append(f"{path}: pending without a release target")
        elif status == "legacy_exception" and not row.get("reason"):
            problems.append(f"{path}: legacy_exception without a reason")
    return problems, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    problems, counts = check(args.manifest)
    complete = not problems and counts.get("pending", 0) == 0
    if args.format == "json":
        print(json.dumps({"ok": not problems, "all_writer_session_coverage_complete": complete,
                          "counts": counts, "problems": problems}, ensure_ascii=False))
    else:
        for problem in problems:
            print(f"BLOCKED: {problem}")
        print(
            "Writer-session coverage: "
            f"{counts.get('session_integrated', 0)} integrated, {counts.get('routed', 0)} routed through "
            f"an integrated command, {counts.get('pending', 0)} pending, "
            f"{counts.get('legacy_exception', 0)} documented exceptions; "
            + ("all-writer scope complete." if complete else "all-writer scope NOT complete.")
        )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
