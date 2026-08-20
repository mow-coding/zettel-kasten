from __future__ import annotations

import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, archive_services


REMOVAL_REQUEST_SCHEMA = (
    "wom-kit/activity-group-membership-removal-request/v0.1"
)
REMOVAL_WRITE_SCHEMA = (
    "wom-kit/activity-group-membership-removal-write/v0.1"
)
REMOVAL_JOURNAL_SCHEMA = (
    "wom-kit/activity-group-membership-removal-transaction-journal/v0.1"
)
REMOVAL_RECEIPT_SCHEMA = (
    "wom-kit/activity-group-membership-removal-receipt/v0.1"
)
REMOVAL_RECOVERY_PLAN_SCHEMA = (
    "wom-kit/activity-group-membership-removal-recovery-plan/v0.1"
)
REMOVAL_RECOVER_SCHEMA = (
    "wom-kit/activity-group-membership-removal-recover/v0.1"
)
REMOVAL_AFFIRMATION = (
    "all_activity_group_membership_removals_reviewed"
)


def _historical_activity_group_membership_removal_write(
    archive_root: Path | str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Exercise the frozen removal core, not the public v0.4 gate."""

    if "affirm_removals_reviewed" in kwargs:
        kwargs["affirm_memberships_reviewed"] = kwargs.pop(
            "affirm_removals_reviewed"
        )
    return archive_services._activity_group_membership_write(
        archive_root,
        operation_contract=archive_services.ACTIVITY_GROUP_MEMBERSHIP_REMOVE,
        **kwargs,
    )


def _historical_activity_group_membership_removal_recover(
    archive_root: Path | str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Exercise the frozen removal recovery core, not the public v0.4 gate."""

    return archive_services._activity_group_membership_recover(
        archive_root,
        operation_contract=archive_services.ACTIVITY_GROUP_MEMBERSHIP_REMOVE,
        **kwargs,
    )


class ActivityGroupMembershipRemovalWriteTests(unittest.TestCase):
    """Release-blocking service tests for the explicit removal writer.

    These fixtures intentionally do not inherit the very large CLI test class.
    They exercise the removal plan/write service boundary, its focused CLI
    contract, and the shared transaction primitives needed to prove the exact
    mutation set.
    """

    def _run_cli(self, args: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = archive_cli.main(args)
        return code, output.getvalue()

    def _init_archive(self, root: Path, archive_id: str) -> None:
        """Install the checked-in pre-v0.4 template without calling init."""

        fixture_root = root.resolve()
        template_root = (KIT_ROOT / "templates" / "personal").resolve()
        zettel_kasten_root = (KIT_ROOT / "zettel-kasten").resolve()
        self.assertEqual(template_root.parent, (KIT_ROOT / "templates").resolve())
        self.assertTrue(template_root.is_dir())
        self.assertEqual(zettel_kasten_root, (KIT_ROOT / "zettel-kasten").resolve())
        self.assertTrue(zettel_kasten_root.is_dir())
        self.assertFalse(fixture_root.exists())

        shutil.copytree(template_root, fixture_root)
        shutil.copytree(
            zettel_kasten_root,
            fixture_root / "zettel-kasten",
            dirs_exist_ok=True,
        )
        for relative in (
            "inbox",
            "zettels",
            "views",
            "source-maps",
            "objects/manifests",
            "objects/derived-text/sha256",
            "db",
            "workbench",
            "receipts",
            "receipts/recovery",
        ):
            destination = (fixture_root / relative).resolve()
            self.assertTrue(destination.is_relative_to(fixture_root))
            destination.mkdir(parents=True, exist_ok=True)

        archive_path = fixture_root / "archive.yml"
        archive_doc = archive_cli.load_yaml(archive_path.read_text(encoding="utf-8"))
        archive_doc["archive_id"] = archive_id
        archive_doc["name"] = "Test Personal Archive"
        archive_doc["type"] = "personal"
        archive_doc["principal"] = {
            "principal_id": "person:test",
            "display_name": "Test Person",
            "kind": "person",
        }
        archive_path.write_text(archive_cli.dump_yaml(archive_doc), encoding="utf-8")

        identity_path = fixture_root / "archive-identity.yml"
        identity_doc = archive_cli.load_yaml(identity_path.read_text(encoding="utf-8"))
        identity_doc["identity"].update(
            {
                "archive_id": archive_id,
                "identity_id": f"identity:{archive_id}",
                "scope": "personal",
                "principal_id": "person:test",
                "display_name": "Test Person",
            }
        )
        identity_doc["ownership"].update(
            {
                "owner_id": "person:test",
                "owner_kind": "person",
                "owner_display_name": "Test Person",
                "owner_archive_id": archive_id,
            }
        )
        identity_path.write_text(archive_cli.dump_yaml(identity_doc), encoding="utf-8")

        for filename in ("provider-bindings.yml", "source-bindings.yml"):
            binding_path = fixture_root / filename
            binding_doc = archive_cli.load_yaml(binding_path.read_text(encoding="utf-8"))
            binding_doc["archive_id"] = archive_id
            binding_path.write_text(archive_cli.dump_yaml(binding_doc), encoding="utf-8")

        self.assertEqual(archive_services.read_archive_id(fixture_root), archive_id)

    def _create_canonical(
        self,
        root: Path,
        *,
        zettel_id: str,
        title: str,
        facets: dict[str, Any],
        body: str,
        bom_crlf: bool = False,
    ) -> Path:
        path = root / "zettels" / f"{zettel_id}.md"
        frontmatter = {
            "id": zettel_id,
            "title": title,
            "created_at": "2026-07-30T01:02:03+09:00",
            "updated_at": "2026-07-30T01:02:03+09:00",
            "archive_id": archive_services.read_archive_id(root),
            "status": "canonical",
            "kind": "record_note",
            "facets": facets,
            "assets": [],
            "edges": [],
            "provenance": {
                "created_by": "person:test",
                "created_in": archive_services.read_archive_id(root),
                "source": "private_removal_write_fixture",
            },
            "visibility": {
                "scope": "private",
                "source_visibility": "private",
            },
        }
        raw = (
            "---\n"
            + archive_services.dump_yaml(frontmatter)
            + "---\n\n"
            + body
            + "\n"
        ).encode("utf-8")
        if bom_crlf:
            raw = b"\xef\xbb\xbf" + raw.replace(b"\n", b"\r\n")
        path.write_bytes(raw)
        return path

    def _fixture(
        self,
        root: Path,
        *,
        suffix: str,
        mode: str = "mixed",
    ) -> dict[str, Any]:
        archive_id = f"archive:personal:removal-write-{suffix}"
        self._init_archive(root, archive_id)
        anchor_id = (
            f"zet_20260730_{suffix}0000_private_removal_event_anchor"
        )
        other_anchor_ids = [
            f"zet_20260730_{suffix}9001_private_other_event_one",
            f"zet_20260730_{suffix}9002_private_other_event_two",
        ]
        anchor_path = self._create_canonical(
            root,
            zettel_id=anchor_id,
            title=f"PRIVATE_REMOVAL_EVENT_TITLE_{suffix}",
            facets={
                "record_type": "event",
                "event_start": "2022-08-26",
                "event_end": "2022-08-27",
                "location": f"PRIVATE_REMOVAL_LOCATION_{suffix}",
            },
            body=f"PRIVATE_REMOVAL_EVENT_BODY_{suffix}",
        )
        if mode == "mixed":
            memberships: list[Any] = [
                anchor_id,
                [anchor_id],
                [other_anchor_ids[0], anchor_id],
                [
                    other_anchor_ids[0],
                    anchor_id,
                    other_anchor_ids[1],
                ],
                other_anchor_ids[0],
            ]
        elif mode == "all_absent":
            memberships = [
                other_anchor_ids[0],
                [other_anchor_ids[0], other_anchor_ids[1]],
            ]
        elif mode == "one_ready":
            memberships = [anchor_id]
        elif mode == "privacy":
            memberships = [
                [
                    other_anchor_ids[0],
                    anchor_id,
                    other_anchor_ids[1],
                ]
            ]
        else:
            raise AssertionError(f"unsupported fixture mode: {mode}")

        member_ids = [
            f"zet_20260730_{suffix}{index + 1:04d}_private_removal_member"
            for index in range(len(memberships))
        ]
        member_paths = [
            self._create_canonical(
                root,
                zettel_id=member_id,
                title=f"PRIVATE_REMOVAL_MEMBER_TITLE_{suffix}_{index}",
                facets={
                    "record_type": "memory",
                    "activity_group": memberships[index],
                    "subject": (
                        f"PRIVATE_REMOVAL_SUBJECT_{suffix}_{index}"
                    ),
                },
                body=f"PRIVATE_REMOVAL_MEMBER_BODY_{suffix}_{index}",
                bom_crlf=bool(mode == "mixed" and index == 3),
            )
            for index, member_id in enumerate(member_ids)
        ]
        request_relative = (
            ".wom-scratch/private/activity-group-removals/"
            f"PRIVATE_REMOVAL_WRITE_REQUEST_{suffix}.json"
        )
        request_path = root / request_relative
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(
            json.dumps(
                {
                    "schema": REMOVAL_REQUEST_SCHEMA,
                    "archive_id": archive_id,
                    "anchor_zettel_id": anchor_id,
                    "member_zettel_ids": member_ids,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        plan = archive_services.activity_group_membership_removal_plan(
            root,
            request_path=request_relative,
            dry_run=True,
        )
        self.assertTrue(plan["ok"], plan)
        return {
            "root": root,
            "archive_id": archive_id,
            "anchor_id": anchor_id,
            "anchor_path": anchor_path,
            "other_anchor_ids": other_anchor_ids,
            "memberships": memberships,
            "member_ids": member_ids,
            "member_paths": member_paths,
            "request_relative": request_relative,
            "request_path": request_path,
            "plan": plan,
        }

    def _call_write(
        self,
        fixture: dict[str, Any],
        **overrides: Any,
    ) -> dict[str, Any]:
        plan = fixture["plan"]
        arguments: dict[str, Any] = {
            "request_path": fixture["request_relative"],
            "expected_request_sha256": plan["request"]["sha256"],
            "expected_review_plan_sha256": plan[
                "review_plan_sha256"
            ],
        }
        arguments.update(overrides)
        return _historical_activity_group_membership_removal_write(
            fixture["root"],
            **arguments,
        )

    @staticmethod
    def _recovery_evidence_paths(
        fixture: dict[str, Any],
    ) -> dict[str, Path]:
        root = fixture["root"]
        request_sha256 = fixture["plan"]["request"]["sha256"]
        coordination_root = (
            root
            / ".wom-scratch"
            / "private"
            / "activity-groups"
        )
        return {
            "journal": (
                archive_services
                .activity_group_membership_removal_transaction_journal_path(
                    root,
                    request_sha256,
                )
            ),
            "receipt": (
                archive_services
                .activity_group_membership_removal_receipt_path(
                    root,
                    request_sha256,
                )
            ),
            "lock": (
                coordination_root
                / archive_services
                .ACTIVITY_GROUP_MEMBERSHIP_WRITE_LOCK_NAME
            ),
            "guard": (
                coordination_root
                / archive_services
                .ACTIVITY_GROUP_MEMBERSHIP_RECOVERY_GUARD_NAME
            ),
        }

    @staticmethod
    def _call_recovery_plan(
        fixture: dict[str, Any],
    ) -> dict[str, Any]:
        return (
            archive_services
            .activity_group_membership_removal_recovery_plan(
                fixture["root"],
                expected_request_sha256=fixture["plan"][
                    "request"
                ]["sha256"],
                dry_run=True,
            )
        )

    @staticmethod
    def _call_recover(
        fixture: dict[str, Any],
        recovery_plan: dict[str, Any],
        *,
        reviewed_by: str,
    ) -> dict[str, Any]:
        return (
            _historical_activity_group_membership_removal_recover(
                fixture["root"],
                expected_request_sha256=fixture["plan"][
                    "request"
                ]["sha256"],
                expected_recovery_plan_sha256=recovery_plan[
                    "recovery_plan_sha256"
                ],
                approve=True,
                reviewed_by=reviewed_by,
                affirm_recovery_reviewed=True,
            )
        )

    @staticmethod
    def _file_state(root: Path) -> dict[str, tuple[bytes, int]]:
        return {
            path.relative_to(root).as_posix(): (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
            for path in root.rglob("*")
            if path.is_file()
        }

    @staticmethod
    def _body_bytes(raw: bytes) -> bytes:
        payload = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
        for marker in (b"\r\n---\r\n", b"\n---\n"):
            boundary = payload.find(marker, 4)
            if boundary >= 0:
                return payload[boundary + len(marker) :]
        raise AssertionError("fixture frontmatter boundary not found")

    def _assert_result_is_content_free(
        self,
        value: Any,
        fixture: dict[str, Any],
        *,
        extra_forbidden: tuple[str, ...] = (),
    ) -> None:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        forbidden = (
            fixture["request_path"].name,
            fixture["anchor_id"],
            *fixture["other_anchor_ids"],
            *fixture["member_ids"],
            f"PRIVATE_REMOVAL_EVENT_TITLE_"
            f"{fixture['archive_id'].rsplit('-', 1)[-1]}",
            "PRIVATE_REMOVAL_MEMBER_TITLE",
            "PRIVATE_REMOVAL_MEMBER_BODY",
            "PRIVATE_REMOVAL_SUBJECT",
            "PRIVATE_REMOVAL_LOCATION",
            str(fixture["root"]),
            *extra_forbidden,
        )
        for private_value in forbidden:
            self.assertNotIn(private_value, serialized)

    def test_mixed_removal_apply_writes_only_ready_rows_and_preserves_exact_shape(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="01",
            )
            root = fixture["root"]
            member_paths = fixture["member_paths"]
            absent_path = member_paths[4]
            absent_before = absent_path.read_bytes()
            original_review_digest = fixture["plan"][
                "review_plan_sha256"
            ]

            # An already-absent row is still review authority: changing its
            # exact canonical bytes must change the review digest.
            absent_path.write_bytes(
                absent_before.replace(
                    b"PRIVATE_REMOVAL_MEMBER_BODY_01_4",
                    b"PRIVATE_REMOVAL_MEMBER_BODY_01_4_CHANGED",
                )
            )
            changed_absent_plan = (
                archive_services.activity_group_membership_removal_plan(
                    root,
                    request_path=fixture["request_relative"],
                    dry_run=True,
                )
            )
            self.assertTrue(changed_absent_plan["ok"])
            self.assertEqual(
                changed_absent_plan["items"][4]["status"],
                "already_absent",
            )
            self.assertNotEqual(
                changed_absent_plan["review_plan_sha256"],
                original_review_digest,
            )
            absent_path.write_bytes(absent_before)
            fixture["plan"] = (
                archive_services.activity_group_membership_removal_plan(
                    root,
                    request_path=fixture["request_relative"],
                    dry_run=True,
                )
            )
            self.assertEqual(
                fixture["plan"]["review_plan_sha256"],
                original_review_digest,
            )

            before = {
                path: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in [fixture["anchor_path"], *member_paths]
            }
            tree_before_preview = self._file_state(root)
            preview = self._call_write(fixture, dry_run=True)
            self.assertTrue(preview["ok"], preview)
            self.assertEqual(preview["schema"], REMOVAL_WRITE_SCHEMA)
            self.assertEqual(preview["status"], "ready_to_apply")
            self.assertEqual(
                preview["summary"]["ready_to_remove_count"],
                4,
            )
            self.assertEqual(
                preview["summary"]["already_absent_count"],
                1,
            )
            self.assertEqual(
                preview["summary"]["canonical_files_written_this_run"],
                0,
            )
            self.assertEqual(
                [item["status"] for item in preview["items"]],
                [
                    "ready_to_apply",
                    "ready_to_apply",
                    "ready_to_apply",
                    "ready_to_apply",
                    "already_absent",
                ],
            )
            self.assertEqual(tree_before_preview, self._file_state(root))

            captured_evidence: list[dict[str, Any]] = []
            snapshot_candidates: list[dict[str, Any]] = []
            canonical_cas_paths: list[Path] = []
            original_bound_write = (
                archive_services._write_activity_group_bytes_new_file_bound
            )
            original_preserve = (
                archive_services
                .preserve_activity_group_membership_before_snapshots
            )
            original_cas = (
                archive_services
                ._replace_activity_group_canonical_bytes_compare_and_swap
            )

            def capture_bound_write(
                binding: dict[str, Any],
                path: Path,
                raw: bytes,
            ) -> Any:
                try:
                    document = json.loads(raw.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError):
                    document = None
                if isinstance(document, dict):
                    captured_evidence.append(copy.deepcopy(document))
                return original_bound_write(binding, path, raw)

            def capture_snapshots(
                archive_root: Path,
                **kwargs: Any,
            ) -> dict[str, int]:
                snapshot_candidates.extend(
                    {
                        "row_index": item["row_index"],
                        "zettel_id": item["zettel_id"],
                        "before_snapshot": copy.deepcopy(
                            item["before_snapshot"]
                        ),
                    }
                    for item in kwargs["candidates"]
                )
                return original_preserve(archive_root, **kwargs)

            def capture_cas(
                archive_root: Path,
                path: Path,
                **kwargs: Any,
            ) -> None:
                canonical_cas_paths.append(path)
                original_cas(archive_root, path, **kwargs)

            with (
                patch.object(
                    archive_services,
                    "_write_activity_group_bytes_new_file_bound",
                    side_effect=capture_bound_write,
                ),
                patch.object(
                    archive_services,
                    "preserve_activity_group_membership_before_snapshots",
                    side_effect=capture_snapshots,
                ),
                patch.object(
                    archive_services,
                    (
                        "_replace_activity_group_canonical_bytes_"
                        "compare_and_swap"
                    ),
                    side_effect=capture_cas,
                ),
            ):
                applied = self._call_write(
                    fixture,
                    approve=True,
                    reviewed_by="person:private-removal-reviewer",
                    affirm_removals_reviewed=True,
                )

            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["status"], "applied")
            self.assertEqual(
                applied["summary"]["canonical_files_written_this_run"],
                4,
            )
            self.assertEqual(
                applied["summary"]["canonical_write_attempt_count"],
                4,
            )
            self.assertEqual(
                applied["prior_byte_snapshots"]["verified_snapshot_count"],
                4,
            )
            self.assertTrue(
                applied["write_boundary"][
                    "membership_removal_implemented"
                ]
            )
            expected_ready_ids = fixture["member_ids"][:4]
            self.assertEqual(
                [item["zettel_id"] for item in snapshot_candidates],
                expected_ready_ids,
            )
            self.assertEqual(
                [path.name for path in canonical_cas_paths],
                [path.name for path in member_paths[:4]],
            )

            journal = next(
                document
                for document in captured_evidence
                if document.get("schema") == REMOVAL_JOURNAL_SCHEMA
            )
            receipt = next(
                document
                for document in captured_evidence
                if document.get("schema") == REMOVAL_RECEIPT_SCHEMA
            )
            self.assertEqual(
                journal["action"],
                "activity_group_membership_removal_transaction",
            )
            self.assertEqual(journal["operation"], "remove")
            self.assertEqual(
                receipt["action"],
                "activity_group_membership_removal_write",
            )
            self.assertEqual(
                receipt["human_affirmation"],
                REMOVAL_AFFIRMATION,
            )
            for evidence in (journal, receipt):
                self.assertEqual(evidence["item_count"], 4)
                self.assertEqual(
                    [item["zettel_id"] for item in evidence["items"]],
                    expected_ready_ids,
                )
                self.assertNotIn(
                    fixture["member_ids"][4],
                    json.dumps(evidence, ensure_ascii=False),
                )

            expected_memberships = [
                None,
                None,
                [fixture["other_anchor_ids"][0]],
                fixture["other_anchor_ids"],
            ]
            for index, path in enumerate(member_paths[:4]):
                before_bytes = before[path][0]
                after_bytes = path.read_bytes()
                before_frontmatter, _before_payload, _source = (
                    archive_services._parse_activity_group_canonical(
                        before_bytes
                    )
                )
                after_frontmatter, _after_payload, _source = (
                    archive_services._parse_activity_group_canonical(
                        after_bytes
                    )
                )
                expected_frontmatter = copy.deepcopy(before_frontmatter)
                if expected_memberships[index] is None:
                    expected_frontmatter["facets"].pop(
                        "activity_group",
                        None,
                    )
                else:
                    expected_frontmatter["facets"]["activity_group"] = (
                        expected_memberships[index]
                    )
                self.assertEqual(
                    after_frontmatter,
                    expected_frontmatter,
                )
                self.assertEqual(
                    after_frontmatter["updated_at"],
                    before_frontmatter["updated_at"],
                )
                self.assertEqual(
                    self._body_bytes(after_bytes),
                    self._body_bytes(before_bytes),
                )
            crlf_bom_after = member_paths[3].read_bytes()
            self.assertTrue(crlf_bom_after.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", crlf_bom_after)
            self.assertNotIn(
                b"\n",
                crlf_bom_after.replace(b"\r\n", b""),
            )
            for untouched_path in (
                fixture["anchor_path"],
                absent_path,
            ):
                self.assertEqual(
                    before[untouched_path],
                    (
                        untouched_path.read_bytes(),
                        untouched_path.stat().st_mtime_ns,
                    ),
                )
            self._assert_result_is_content_free(
                (preview, applied),
                fixture,
                extra_forbidden=("person:private-removal-reviewer",),
            )

    def test_all_already_absent_is_satisfied_without_transaction_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="02",
                mode="all_absent",
            )
            root = fixture["root"]
            before = self._file_state(root)
            original_bound_write = (
                archive_services._write_activity_group_bytes_new_file_bound
            )
            original_preserve = (
                archive_services
                .preserve_activity_group_membership_before_snapshots
            )
            original_cas = (
                archive_services
                ._replace_activity_group_canonical_bytes_compare_and_swap
            )
            with (
                patch.object(
                    archive_services,
                    "_write_activity_group_bytes_new_file_bound",
                    wraps=original_bound_write,
                ) as bound_write,
                patch.object(
                    archive_services,
                    "preserve_activity_group_membership_before_snapshots",
                    wraps=original_preserve,
                ) as preserve,
                patch.object(
                    archive_services,
                    (
                        "_replace_activity_group_canonical_bytes_"
                        "compare_and_swap"
                    ),
                    wraps=original_cas,
                ) as canonical_cas,
            ):
                result = self._call_write(
                    fixture,
                    approve=True,
                    reviewed_by="person:removal-reviewer",
                    affirm_removals_reviewed=True,
                )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "already_satisfied")
            self.assertEqual(
                result["summary"]["ready_to_remove_count"],
                0,
            )
            self.assertEqual(
                result["summary"]["already_absent_count"],
                2,
            )
            self.assertEqual(
                result["summary"]["canonical_write_attempt_count"],
                0,
            )
            self.assertEqual(before, self._file_state(root))
            bound_write.assert_not_called()
            preserve.assert_not_called()
            canonical_cas.assert_not_called()
            request_sha256 = fixture["plan"]["request"]["sha256"]
            self.assertFalse(
                archive_services
                .activity_group_membership_removal_receipt_path(
                    root,
                    request_sha256,
                )
                .exists()
            )
            self.assertFalse(
                archive_services
                .activity_group_membership_removal_transaction_journal_path(
                    root,
                    request_sha256,
                )
                .exists()
            )

    def test_removal_write_requires_exact_approval_request_and_review(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="03",
                mode="one_ready",
            )
            root = fixture["root"]
            add_request_relative = (
                ".wom-scratch/private/activity-groups/"
                "PRIVATE_ADD_AUTHORITY_MUST_NOT_REMOVE.json"
            )
            add_request_path = root / add_request_relative
            add_request_path.parent.mkdir(parents=True, exist_ok=True)
            add_request_path.write_text(
                json.dumps(
                    {
                        "schema": (
                            "wom-kit/activity-group-membership-request/v0.1"
                        ),
                        "archive_id": fixture["archive_id"],
                        "anchor_zettel_id": fixture["anchor_id"],
                        "member_zettel_ids": fixture["member_ids"],
                    }
                ),
                encoding="utf-8",
            )
            add_plan = archive_services.activity_group_membership_plan(
                root,
                request_path=add_request_relative,
                dry_run=True,
            )
            self.assertTrue(add_plan["ok"], add_plan)
            before = self._file_state(root)
            cases = [
                (
                    "no_execution_mode",
                    {},
                    "choose_exactly_one_of_dry_run_or_approve",
                ),
                (
                    "two_execution_modes",
                    {"dry_run": True, "approve": True},
                    "choose_exactly_one_of_dry_run_or_approve",
                ),
                (
                    "missing_human_authority",
                    {
                        "approve": True,
                        "reviewed_by": None,
                        "affirm_removals_reviewed": False,
                    },
                    "safe_reviewed_by_required",
                ),
                (
                    "wrong_request_digest",
                    {
                        "dry_run": True,
                        "expected_request_sha256": "sha256:" + "0" * 64,
                    },
                    "request_sha256_mismatch",
                ),
                (
                    "wrong_review_digest",
                    {
                        "dry_run": True,
                        "expected_review_plan_sha256": (
                            "sha256:" + "1" * 64
                        ),
                    },
                    "review_plan_sha256_mismatch",
                ),
                (
                    "add_review_digest",
                    {
                        "dry_run": True,
                        "expected_review_plan_sha256": add_plan[
                            "review_plan_sha256"
                        ],
                    },
                    "review_plan_sha256_mismatch",
                ),
            ]
            for name, overrides, expected_blocker in cases:
                with self.subTest(name=name):
                    result = self._call_write(fixture, **overrides)
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(result["status"], "blocked")
                    self.assertIn(expected_blocker, result["blockers"])
                    self.assertEqual(
                        result["summary"][
                            "canonical_write_attempt_count"
                        ],
                        0,
                    )
                    self.assertEqual(before, self._file_state(root))
            missing_authority = self._call_write(
                fixture,
                approve=True,
                reviewed_by=None,
                affirm_removals_reviewed=False,
            )
            self.assertIn(
                "affirm_removals_reviewed_required",
                missing_authority["blockers"],
            )
            with patch.object(
                archive_services,
                "_activity_group_membership_write",
                side_effect=AssertionError(
                    "blocked public approval reached private core"
                ),
            ) as private_core:
                blocked = (
                    archive_services
                    .activity_group_membership_removal_write(
                        root,
                        request_path=fixture["request_relative"],
                        expected_request_sha256=fixture["plan"][
                            "request"
                        ]["sha256"],
                        expected_review_plan_sha256=fixture["plan"][
                            "review_plan_sha256"
                        ],
                        approve=True,
                        reviewed_by="person:private-service-reviewer",
                        affirm_removals_reviewed=True,
                    )
                )
            private_core.assert_not_called()
            self.assertFalse(blocked["ok"], blocked)
            self.assertEqual(blocked["state"], "blocked")
            self.assertEqual(
                blocked["reason_codes"],
                ["compound_exact_human_approval_binding_required"],
            )
            self.assertFalse(blocked["private_values_echoed"])
            self.assertEqual(before, self._file_state(root))

    def test_under_lock_absent_to_present_drift_is_blocked(
        self,
    ) -> None:
        self._assert_under_lock_membership_drift(
            suffix="04",
            member_index=4,
            operation="add",
        )

    def test_under_lock_ready_to_absent_drift_is_blocked(
        self,
    ) -> None:
        self._assert_under_lock_membership_drift(
            suffix="05",
            member_index=0,
            operation="remove",
        )

    def _assert_under_lock_membership_drift(
        self,
        *,
        suffix: str,
        member_index: int,
        operation: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix=suffix,
            )
            root = fixture["root"]
            target_path = fixture["member_paths"][member_index]
            target_before = target_path.read_bytes()
            drifted_bytes = archive_services._activity_group_candidate_bytes(
                target_before,
                anchor_zettel_id=fixture["anchor_id"],
                operation=operation,
            )
            original_plan = archive_services._activity_group_membership_plan
            original_preserve = (
                archive_services
                .preserve_activity_group_membership_before_snapshots
            )
            original_cas = (
                archive_services
                ._replace_activity_group_canonical_bytes_compare_and_swap
            )
            plan_calls = 0

            def drift_before_locked_plan(*args: Any, **kwargs: Any) -> Any:
                nonlocal plan_calls
                plan_calls += 1
                if plan_calls == 2:
                    target_path.write_bytes(drifted_bytes)
                return original_plan(*args, **kwargs)

            with (
                patch.object(
                    archive_services,
                    "_activity_group_membership_plan",
                    side_effect=drift_before_locked_plan,
                ),
                patch.object(
                    archive_services,
                    "preserve_activity_group_membership_before_snapshots",
                    wraps=original_preserve,
                ) as preserve,
                patch.object(
                    archive_services,
                    (
                        "_replace_activity_group_canonical_bytes_"
                        "compare_and_swap"
                    ),
                    wraps=original_cas,
                ) as canonical_cas,
            ):
                result = self._call_write(
                    fixture,
                    approve=True,
                    reviewed_by="person:removal-reviewer",
                    affirm_removals_reviewed=True,
                )
            self.assertGreaterEqual(plan_calls, 2)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(
                result["summary"]["canonical_write_attempt_count"],
                0,
            )
            self.assertEqual(target_path.read_bytes(), drifted_bytes)
            preserve.assert_not_called()
            canonical_cas.assert_not_called()
            self.assertFalse(
                archive_services
                .activity_group_membership_removal_transaction_journal_path(
                    root,
                    fixture["plan"]["request"]["sha256"],
                )
                .exists()
            )

    def test_receipt_replay_never_redeletes_readded_membership(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="06",
                mode="one_ready",
            )
            first = self._call_write(
                fixture,
                approve=True,
                reviewed_by="person:removal-reviewer",
                affirm_removals_reviewed=True,
            )
            self.assertTrue(first["ok"], first)
            self.assertEqual(first["status"], "applied")
            member_path = fixture["member_paths"][0]
            removed_bytes = member_path.read_bytes()
            readded_bytes = archive_services._activity_group_candidate_bytes(
                removed_bytes,
                anchor_zettel_id=fixture["anchor_id"],
                operation="add",
            )
            member_path.write_bytes(readded_bytes)
            receipt_path = (
                archive_services
                .activity_group_membership_removal_receipt_path(
                    fixture["root"],
                    fixture["plan"]["request"]["sha256"],
                )
            )
            receipt_before = (
                receipt_path.read_bytes(),
                receipt_path.stat().st_mtime_ns,
            )
            original_cas = (
                archive_services
                ._replace_activity_group_canonical_bytes_compare_and_swap
            )
            with patch.object(
                archive_services,
                (
                    "_replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                wraps=original_cas,
            ) as canonical_cas:
                replay = self._call_write(
                    fixture,
                    approve=True,
                    reviewed_by="person:removal-reviewer",
                    affirm_removals_reviewed=True,
                )
            self.assertFalse(replay["ok"], replay)
            self.assertEqual(replay["status"], "blocked")
            self.assertNotEqual(replay["status"], "already_applied")
            self.assertEqual(
                replay["summary"]["canonical_write_attempt_count"],
                0,
            )
            canonical_cas.assert_not_called()
            self.assertEqual(member_path.read_bytes(), readded_bytes)
            frontmatter, _payload, _source = (
                archive_services._parse_activity_group_canonical(
                    readded_bytes
                )
            )
            self.assertEqual(
                frontmatter["facets"]["activity_group"],
                fixture["anchor_id"],
            )
            self.assertEqual(
                receipt_before,
                (
                    receipt_path.read_bytes(),
                    receipt_path.stat().st_mtime_ns,
                ),
            )

    def test_lock_only_interrupted_removal_recovers_by_cleaning_lock(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="08",
                mode="one_ready",
            )
            member_path = fixture["member_paths"][0]
            member_before = member_path.read_bytes()
            paths = self._recovery_evidence_paths(fixture)

            with patch.object(
                archive_services,
                "preserve_activity_group_membership_before_snapshots",
                side_effect=KeyboardInterrupt(
                    "PRIVATE_REMOVAL_EXIT_BEFORE_JOURNAL"
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self._call_write(
                        fixture,
                        approve=True,
                        reviewed_by="person:private-removal-writer",
                        affirm_removals_reviewed=True,
                    )

            self.assertEqual(member_path.read_bytes(), member_before)
            self.assertTrue(paths["lock"].is_file())
            self.assertFalse(paths["journal"].exists())
            self.assertFalse(paths["receipt"].exists())

            recovery_plan = self._call_recovery_plan(fixture)
            self.assertTrue(recovery_plan["ok"], recovery_plan)
            self.assertEqual(
                recovery_plan["transaction_state"],
                "lock_only_before_journal",
            )
            self.assertEqual(
                recovery_plan["recovery_action"],
                "cleanup_unstarted_removal_lock",
            )
            recovered = self._call_recover(
                fixture,
                recovery_plan,
                reviewed_by="person:private-removal-recovery-reviewer",
            )

            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(recovered["status"], "cleanup_completed")
            self.assertEqual(
                recovered["summary"][
                    "canonical_files_restored_this_run"
                ],
                0,
            )
            self.assertTrue(
                recovered["summary"]["write_lock_removed"]
            )
            self.assertEqual(member_path.read_bytes(), member_before)
            for path in paths.values():
                self.assertFalse(path.exists(), path)
            self._assert_result_is_content_free(
                {
                    "recovery_plan": recovery_plan,
                    "recovered": recovered,
                },
                fixture,
                extra_forbidden=(
                    "person:private-removal-writer",
                    "person:private-removal-recovery-reviewer",
                    "PRIVATE_REMOVAL_EXIT_BEFORE_JOURNAL",
                ),
            )

    def test_prepared_removal_journal_before_first_swap_recovers_by_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="09",
                mode="one_ready",
            )
            member_path = fixture["member_paths"][0]
            member_before = member_path.read_bytes()
            paths = self._recovery_evidence_paths(fixture)

            with patch.object(
                archive_services,
                (
                    "_replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                side_effect=KeyboardInterrupt(
                    "PRIVATE_REMOVAL_EXIT_BEFORE_FIRST_SWAP"
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self._call_write(
                        fixture,
                        approve=True,
                        reviewed_by="person:private-removal-writer",
                        affirm_removals_reviewed=True,
                    )

            self.assertEqual(member_path.read_bytes(), member_before)
            self.assertTrue(paths["lock"].is_file())
            self.assertTrue(paths["journal"].is_file())
            self.assertFalse(paths["receipt"].exists())

            recovery_plan = self._call_recovery_plan(fixture)
            self.assertTrue(recovery_plan["ok"], recovery_plan)
            self.assertEqual(
                recovery_plan["transaction_state"],
                "prepared_not_started",
            )
            self.assertEqual(
                recovery_plan["recovery_action"],
                (
                    "cleanup_unstarted_removal_"
                    "transaction_evidence"
                ),
            )
            self.assertEqual(recovery_plan["summary"]["before_count"], 1)
            self.assertEqual(recovery_plan["summary"]["after_count"], 0)
            recovered = self._call_recover(
                fixture,
                recovery_plan,
                reviewed_by="person:private-removal-recovery-reviewer",
            )

            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(recovered["status"], "cleanup_completed")
            self.assertEqual(
                recovered["summary"][
                    "canonical_files_restored_this_run"
                ],
                0,
            )
            self.assertTrue(
                recovered["summary"]["transaction_journal_removed"]
            )
            self.assertTrue(
                recovered["summary"]["write_lock_removed"]
            )
            self.assertEqual(member_path.read_bytes(), member_before)
            for path in paths.values():
                self.assertFalse(path.exists(), path)
            self._assert_result_is_content_free(
                {
                    "recovery_plan": recovery_plan,
                    "recovered": recovered,
                },
                fixture,
                extra_forbidden=(
                    "person:private-removal-writer",
                    "person:private-removal-recovery-reviewer",
                    "PRIVATE_REMOVAL_EXIT_BEFORE_FIRST_SWAP",
                ),
            )

    def test_partial_removal_after_first_swap_recovers_exact_before_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="10",
                mode="mixed",
            )
            member_paths = fixture["member_paths"]
            member_before = [
                path.read_bytes() for path in member_paths
            ]
            paths = self._recovery_evidence_paths(fixture)
            original_cas = (
                archive_services
                ._replace_activity_group_canonical_bytes_compare_and_swap
            )
            ready_names = {
                path.name for path in member_paths[:4]
            }
            attempts = 0

            def interrupt_second_swap(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> None:
                nonlocal attempts
                if path.name in ready_names:
                    attempts += 1
                    if attempts == 2:
                        raise KeyboardInterrupt(
                            "PRIVATE_REMOVAL_EXIT_AFTER_FIRST_SWAP"
                        )
                original_cas(root, path, **kwargs)

            with patch.object(
                archive_services,
                (
                    "_replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                side_effect=interrupt_second_swap,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self._call_write(
                        fixture,
                        approve=True,
                        reviewed_by="person:private-removal-writer",
                        affirm_removals_reviewed=True,
                    )

            self.assertEqual(attempts, 2)
            self.assertNotEqual(
                member_paths[0].read_bytes(),
                member_before[0],
            )
            self.assertEqual(
                [path.read_bytes() for path in member_paths[1:]],
                member_before[1:],
            )
            self.assertTrue(paths["lock"].is_file())
            self.assertTrue(paths["journal"].is_file())
            self.assertFalse(paths["receipt"].exists())

            recovery_plan = self._call_recovery_plan(fixture)
            self.assertTrue(recovery_plan["ok"], recovery_plan)
            self.assertEqual(
                recovery_plan["transaction_state"],
                "partially_applied_without_receipt",
            )
            self.assertEqual(
                recovery_plan["recovery_action"],
                (
                    "rollback_uncommitted_membership_"
                    "removals_to_before"
                ),
            )
            self.assertEqual(recovery_plan["summary"]["before_count"], 3)
            self.assertEqual(recovery_plan["summary"]["after_count"], 1)
            recovered = self._call_recover(
                fixture,
                recovery_plan,
                reviewed_by="person:private-removal-recovery-reviewer",
            )

            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(recovered["status"], "recovered")
            self.assertEqual(
                recovered["summary"][
                    "canonical_files_restored_this_run"
                ],
                1,
            )
            self.assertEqual(
                [path.read_bytes() for path in member_paths],
                member_before,
            )
            for path in paths.values():
                self.assertFalse(path.exists(), path)
            self._assert_result_is_content_free(
                {
                    "recovery_plan": recovery_plan,
                    "recovered": recovered,
                },
                fixture,
                extra_forbidden=(
                    "person:private-removal-writer",
                    "person:private-removal-recovery-reviewer",
                    "PRIVATE_REMOVAL_EXIT_AFTER_FIRST_SWAP",
                ),
            )

    def test_valid_removal_receipt_hard_exit_recovers_by_evidence_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="11",
                mode="one_ready",
            )
            member_path = fixture["member_paths"][0]
            member_before = member_path.read_bytes()
            paths = self._recovery_evidence_paths(fixture)
            original_bound_write = (
                archive_services._write_activity_group_bytes_new_file_bound
            )
            receipt_written = False

            def interrupt_after_receipt(
                binding: dict[str, Any],
                path: Path,
                raw: bytes,
            ) -> None:
                nonlocal receipt_written
                original_bound_write(binding, path, raw)
                if path == paths["receipt"]:
                    receipt_written = True
                    raise KeyboardInterrupt(
                        "PRIVATE_REMOVAL_EXIT_AFTER_VALID_RECEIPT"
                    )

            with patch.object(
                archive_services,
                "_write_activity_group_bytes_new_file_bound",
                side_effect=interrupt_after_receipt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self._call_write(
                        fixture,
                        approve=True,
                        reviewed_by="person:private-removal-writer",
                        affirm_removals_reviewed=True,
                    )

            self.assertTrue(receipt_written)
            self.assertNotEqual(member_path.read_bytes(), member_before)
            completed_bytes = member_path.read_bytes()
            self.assertTrue(paths["lock"].is_file())
            self.assertTrue(paths["journal"].is_file())
            self.assertTrue(paths["receipt"].is_file())

            recovery_plan = self._call_recovery_plan(fixture)
            self.assertTrue(recovery_plan["ok"], recovery_plan)
            self.assertEqual(
                recovery_plan["transaction_state"],
                "verified_completed_residue",
            )
            self.assertEqual(
                recovery_plan["recovery_action"],
                (
                    "cleanup_verified_completed_removal_"
                    "evidence"
                ),
            )
            self.assertTrue(recovery_plan["evidence"]["receipt_verified"])
            recovered = self._call_recover(
                fixture,
                recovery_plan,
                reviewed_by="person:private-removal-recovery-reviewer",
            )

            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(recovered["status"], "cleanup_completed")
            self.assertEqual(
                recovered["summary"][
                    "canonical_files_restored_this_run"
                ],
                0,
            )
            self.assertEqual(member_path.read_bytes(), completed_bytes)
            self.assertTrue(paths["receipt"].is_file())
            self.assertFalse(paths["journal"].exists())
            self.assertFalse(paths["lock"].exists())
            self.assertFalse(paths["guard"].exists())
            self._assert_result_is_content_free(
                {
                    "recovery_plan": recovery_plan,
                    "recovered": recovered,
                },
                fixture,
                extra_forbidden=(
                    "person:private-removal-writer",
                    "person:private-removal-recovery-reviewer",
                    "PRIVATE_REMOVAL_EXIT_AFTER_VALID_RECEIPT",
                ),
            )

    def test_removal_writer_blocks_retained_add_journal_without_reading_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="15",
                mode="one_ready",
            )
            add_private_root = (
                fixture["root"]
                / ".wom-scratch"
                / "private"
                / "activity-groups"
            )
            add_private_root.mkdir(parents=True, exist_ok=True)
            journal_path = (
                add_private_root
                / (
                    "."
                    + ("a" * 64)
                    + archive_services
                    .ACTIVITY_GROUP_MEMBERSHIP_TRANSACTION_JOURNAL_SUFFIX
                )
            )
            private_payload = (
                b"PRIVATE_RETAINED_ADD_JOURNAL_MUST_NOT_BE_READ_OR_ECHOED"
            )
            journal_path.write_bytes(private_payload)
            before = self._file_state(fixture["root"])

            with patch.object(
                archive_services,
                "_read_activity_group_evidence_json",
                side_effect=AssertionError(
                    "discovery must not open a retained add journal"
                ),
            ):
                blocked = self._call_write(
                    fixture,
                    dry_run=True,
                )

            self.assertFalse(blocked["ok"], blocked)
            self.assertEqual(blocked["status"], "blocked")
            self.assertIn(
                "activity_group_unresolved_transaction_evidence_exists",
                blocked["blockers"],
            )
            self.assertEqual(
                self._file_state(fixture["root"]),
                before,
            )
            serialized = json.dumps(blocked, ensure_ascii=False)
            self.assertNotIn(journal_path.name, serialized)
            self.assertNotIn(private_payload.decode("ascii"), serialized)
            self._assert_result_is_content_free(blocked, fixture)

            journal_path.unlink()
            ready = self._call_write(fixture, dry_run=True)
            self.assertTrue(ready["ok"], ready)
            self.assertEqual(ready["status"], "ready_to_apply")

    def test_removal_write_result_and_progress_are_content_free(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="07",
                mode="privacy",
            )
            progress: list[tuple[str, str, int | None, int | None]] = []

            def capture_progress(
                operation: str,
                phase: str,
                current: int | None,
                total: int | None,
            ) -> None:
                progress.append((operation, phase, current, total))

            preview = self._call_write(
                fixture,
                dry_run=True,
                progress_callback=capture_progress,
            )
            applied = self._call_write(
                fixture,
                approve=True,
                reviewed_by="person:PRIVATE_REMOVAL_REVIEWER",
                affirm_removals_reviewed=True,
                progress_callback=capture_progress,
            )
            self.assertTrue(preview["ok"], preview)
            self.assertTrue(applied["ok"], applied)
            self.assertTrue(progress)
            self._assert_result_is_content_free(
                {
                    "preview": preview,
                    "applied": applied,
                    "progress": progress,
                },
                fixture,
                extra_forbidden=("person:PRIVATE_REMOVAL_REVIEWER",),
            )
            privacy = applied["privacy_guards"]
            for key in (
                "request_path_echoed",
                "zettel_ids_echoed",
                "zettel_paths_echoed",
                "zettel_titles_echoed",
                "facet_values_echoed",
                "body_text_echoed",
                "reviewed_by_echoed",
                "absolute_local_paths_echoed",
                "provider_urls_echoed",
                "provider_api_called",
                "model_called",
                "network_called",
                "secret_store_or_environment_read",
            ):
                self.assertFalse(privacy[key], key)
            self.assertFalse(applied["request"]["path_echoed"])
            self.assertFalse(
                applied["transaction_journal"]["path_echoed"]
            )

    def test_removal_write_cli_and_event_alias_share_approval_contract(
        self,
    ) -> None:
        commands = (
            "activity-group-membership-removal-write",
            "event-group-membership-removal-write",
        )
        with tempfile.TemporaryDirectory() as tmp:
            for index, command in enumerate(commands, start=12):
                with self.subTest(command=command):
                    fixture = self._fixture(
                        Path(tmp) / f"archive-{index}",
                        suffix=str(index),
                        mode="one_ready",
                    )
                    plan = fixture["plan"]
                    base_args = [
                        command,
                        str(fixture["root"]),
                        "--request",
                        fixture["request_relative"],
                        "--expected-request-sha256",
                        plan["request"]["sha256"],
                        "--expected-review-plan-sha256",
                        plan["review_plan_sha256"],
                        "--format",
                        "json",
                    ]
                    before = self._file_state(fixture["root"])
                    outputs: list[str] = []

                    preview_code, preview_output = self._run_cli(
                        [*base_args, "--dry-run"]
                    )
                    outputs.append(preview_output)
                    self.assertEqual(
                        preview_code,
                        0,
                        preview_output,
                    )
                    preview = json.loads(preview_output)
                    self.assertTrue(preview["ok"], preview)
                    self.assertEqual(
                        preview["schema"],
                        REMOVAL_WRITE_SCHEMA,
                    )
                    self.assertEqual(
                        preview["lifecycle_action"],
                        "activity_group_membership_removal_write",
                    )
                    self.assertEqual(
                        preview["status"],
                        "ready_to_apply",
                    )
                    self.assertTrue(preview["dry_run"])
                    self.assertFalse(preview["approved"])
                    self.assertEqual(
                        before,
                        self._file_state(fixture["root"]),
                    )

                    approval_variants = (
                        ["--approve"],
                        [
                            "--approve",
                            "--reviewed-by",
                            "person:PRIVATE_CLI_REMOVAL_REVIEWER",
                            "--affirm-removals-reviewed",
                        ],
                        [
                            "--dry-run",
                            "--approve",
                            "--reviewed-by",
                            "person:PRIVATE_CLI_REMOVAL_REVIEWER",
                            "--affirm-removals-reviewed",
                        ],
                    )
                    with patch.object(
                        archive_services,
                        "_activity_group_membership_write",
                        side_effect=AssertionError(
                            "blocked public approval reached private core"
                        ),
                    ) as private_core:
                        for approval_args in approval_variants:
                            blocked_code, blocked_output = self._run_cli(
                                [*base_args, *approval_args]
                            )
                            outputs.append(blocked_output)
                            self.assertEqual(
                                blocked_code,
                                1,
                                blocked_output,
                            )
                            blocked = json.loads(blocked_output)
                            self.assertFalse(blocked["ok"], blocked)
                            self.assertEqual(blocked["state"], "blocked")
                            self.assertEqual(
                                blocked["lifecycle_action"],
                                "activity_group_membership_removal_write",
                            )
                            self.assertEqual(
                                blocked["reason_codes"],
                                [
                                    "compound_exact_human_approval_"
                                    "binding_required"
                                ],
                            )
                            self.assertFalse(
                                blocked["private_values_echoed"]
                            )
                            self.assertEqual(
                                before,
                                self._file_state(fixture["root"]),
                            )
                    private_core.assert_not_called()
                    self._assert_result_is_content_free(
                        outputs,
                        fixture,
                        extra_forbidden=(
                            "person:PRIVATE_CLI_REMOVAL_REVIEWER",
                        ),
                    )

    def test_removal_recovery_plan_cli_and_event_alias_are_read_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._fixture(
                Path(tmp) / "archive",
                suffix="14",
                mode="one_ready",
            )
            paths = self._recovery_evidence_paths(fixture)
            with patch.object(
                archive_services,
                "preserve_activity_group_membership_before_snapshots",
                side_effect=KeyboardInterrupt(
                    "PRIVATE_CLI_REMOVAL_PLAN_INTERRUPTION"
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self._call_write(
                        fixture,
                        approve=True,
                        reviewed_by="person:private-cli-removal-writer",
                        affirm_removals_reviewed=True,
                    )
            self.assertTrue(paths["lock"].is_file())
            self.assertFalse(paths["journal"].exists())
            before = self._file_state(fixture["root"])
            outputs: list[str] = []

            for command in (
                "activity-group-membership-removal-recovery-plan",
                "event-group-membership-removal-recovery-plan",
            ):
                with self.subTest(command=command):
                    base_args = [
                        command,
                        str(fixture["root"]),
                        "--expected-request-sha256",
                        fixture["plan"]["request"]["sha256"],
                        "--format",
                        "json",
                    ]
                    missing_code, missing_output = self._run_cli(
                        base_args
                    )
                    outputs.append(missing_output)
                    self.assertEqual(
                        missing_code,
                        1,
                        missing_output,
                    )
                    self.assertIn(
                        "is read-only and requires --dry-run",
                        missing_output,
                    )

                    plan_code, plan_output = self._run_cli(
                        [*base_args, "--dry-run"]
                    )
                    outputs.append(plan_output)
                    self.assertEqual(plan_code, 0, plan_output)
                    recovery_plan = json.loads(plan_output)
                    self.assertTrue(
                        recovery_plan["ok"],
                        recovery_plan,
                    )
                    self.assertEqual(
                        recovery_plan["schema"],
                        REMOVAL_RECOVERY_PLAN_SCHEMA,
                    )
                    self.assertEqual(
                        recovery_plan["lifecycle_action"],
                        (
                            "activity_group_membership_removal_"
                            "recovery_plan"
                        ),
                    )
                    self.assertEqual(
                        recovery_plan["status"],
                        "recovery_ready",
                    )
                    self.assertEqual(
                        recovery_plan["transaction_state"],
                        "lock_only_before_journal",
                    )
                    self.assertEqual(
                        recovery_plan["recovery_action"],
                        "cleanup_unstarted_removal_lock",
                    )
                    self.assertRegex(
                        recovery_plan["recovery_plan_sha256"],
                        r"^sha256:[0-9a-f]{64}$",
                    )
                    self.assertEqual(
                        before,
                        self._file_state(fixture["root"]),
                    )

            self._assert_result_is_content_free(
                outputs,
                fixture,
                extra_forbidden=(
                    "person:private-cli-removal-writer",
                    "PRIVATE_CLI_REMOVAL_PLAN_INTERRUPTION",
                ),
            )

    def test_removal_recover_cli_and_event_alias_require_full_authority(
        self,
    ) -> None:
        commands = (
            "activity-group-membership-removal-recover",
            "event-group-membership-removal-recover",
        )
        with tempfile.TemporaryDirectory() as tmp:
            for index, command in enumerate(commands, start=15):
                with self.subTest(command=command):
                    fixture = self._fixture(
                        Path(tmp) / f"archive-{index}",
                        suffix=str(index),
                        mode="one_ready",
                    )
                    paths = self._recovery_evidence_paths(fixture)
                    with patch.object(
                        archive_services,
                        (
                            "preserve_activity_group_membership_"
                            "before_snapshots"
                        ),
                        side_effect=KeyboardInterrupt(
                            "PRIVATE_CLI_REMOVAL_RECOVER_INTERRUPTION"
                        ),
                    ):
                        with self.assertRaises(KeyboardInterrupt):
                            self._call_write(
                                fixture,
                                approve=True,
                                reviewed_by=(
                                    "person:private-cli-removal-writer"
                                ),
                                affirm_removals_reviewed=True,
                            )
                    recovery_plan = self._call_recovery_plan(
                        fixture
                    )
                    self.assertTrue(recovery_plan["ok"], recovery_plan)
                    base_args = [
                        command,
                        str(fixture["root"]),
                        "--expected-request-sha256",
                        fixture["plan"]["request"]["sha256"],
                        "--expected-recovery-plan-sha256",
                        recovery_plan["recovery_plan_sha256"],
                        "--format",
                        "json",
                    ]
                    before = self._file_state(fixture["root"])
                    outputs: list[str] = []

                    missing_approve_code, missing_approve_output = (
                        self._run_cli(base_args)
                    )
                    outputs.append(missing_approve_output)
                    self.assertEqual(
                        missing_approve_code,
                        1,
                        missing_approve_output,
                    )
                    self.assertIn(
                        "requires --approve",
                        missing_approve_output,
                    )
                    approval_variants = (
                        ["--approve"],
                        [
                            "--approve",
                            "--reviewed-by",
                            "person:PRIVATE_CLI_RECOVERY_REVIEWER",
                            "--affirm-recovery-reviewed",
                        ],
                    )
                    with patch.object(
                        archive_services,
                        "_activity_group_membership_recover",
                        side_effect=AssertionError(
                            "blocked public recovery reached private core"
                        ),
                    ) as private_core:
                        for approval_args in approval_variants:
                            blocked_code, blocked_output = self._run_cli(
                                [*base_args, *approval_args]
                            )
                            outputs.append(blocked_output)
                            self.assertEqual(
                                blocked_code,
                                1,
                                blocked_output,
                            )
                            blocked = json.loads(blocked_output)
                            self.assertFalse(blocked["ok"], blocked)
                            self.assertEqual(blocked["state"], "blocked")
                            self.assertEqual(
                                blocked["lifecycle_action"],
                                "activity_group_membership_removal_recover",
                            )
                            self.assertEqual(
                                blocked["reason_codes"],
                                [
                                    "compound_exact_human_approval_"
                                    "binding_required"
                                ],
                            )
                            self.assertFalse(
                                blocked["private_values_echoed"]
                            )
                            self.assertEqual(
                                before,
                                self._file_state(fixture["root"]),
                            )
                    private_core.assert_not_called()
                    self.assertTrue(paths["lock"].is_file())
                    self.assertFalse(paths["journal"].exists())
                    self.assertFalse(paths["guard"].exists())
                    with patch.object(
                        archive_services,
                        "_activity_group_membership_recover",
                        side_effect=AssertionError(
                            "blocked public recovery reached private core"
                        ),
                    ) as service_core:
                        service_blocked = (
                            archive_services
                            .activity_group_membership_removal_recover(
                                fixture["root"],
                                expected_request_sha256=fixture["plan"][
                                    "request"
                                ]["sha256"],
                                expected_recovery_plan_sha256=(
                                    recovery_plan[
                                        "recovery_plan_sha256"
                                    ]
                                ),
                                approve=True,
                                reviewed_by=(
                                    "person:private-service-reviewer"
                                ),
                                affirm_recovery_reviewed=True,
                            )
                        )
                    service_core.assert_not_called()
                    self.assertEqual(
                        service_blocked["reason_codes"],
                        [
                            "compound_exact_human_approval_"
                            "binding_required"
                        ],
                    )
                    self.assertFalse(
                        service_blocked["private_values_echoed"]
                    )
                    self.assertEqual(
                        before,
                        self._file_state(fixture["root"]),
                    )
                    self._assert_result_is_content_free(
                        outputs,
                        fixture,
                        extra_forbidden=(
                            "person:private-cli-removal-writer",
                            "person:PRIVATE_CLI_RECOVERY_REVIEWER",
                            (
                                "PRIVATE_CLI_REMOVAL_RECOVER_"
                                "INTERRUPTION"
                            ),
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
