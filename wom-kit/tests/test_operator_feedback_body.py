from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import wom_kit.operator_feedback_body as body_module
from wom_kit.operator_feedback_body import (
    approve_operator_feedback_body,
    check_operator_feedback_body,
    plan_operator_feedback_body,
)


FEEDBACK_ID = "WOM-feedback-120"
PRIVATE_MARKER = "PRIVATE-VALUE-MUST-NOT-BE-ECHOED"


def valid_request() -> dict[str, object]:
    return {
        "schema": body_module.REQUEST_SCHEMA,
        "feedback_id": FEEDBACK_ID,
        "title": "Operator feedback body preservation",
        "sections": {
            "environment": "wom-kit 0.3.312 local archive",
            "task": "Preserve a reviewed feedback body exactly.",
            "observed_failure": "The metadata record had no durable body contract.",
            "suspected_cause": "The former workflow owned metadata only.",
            "requested_resolution": "Create an approval-bound Markdown body.",
            "reproduction": "Plan the request, approve its digest, then check the body.",
        },
    }


class OperatorFeedbackBodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
        self.request_dir = (
            self.root / "profiles" / "local" / "operator-feedback" / "requests"
        )
        self.request_dir.mkdir(parents=True)
        self.request_path = self.request_dir / "letter120.json"
        self.write_request(valid_request())

    def write_request(self, document: object) -> None:
        self.request_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def snapshot_files(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def approve(self) -> tuple[dict[str, object], dict[str, object]]:
        plan = plan_operator_feedback_body(self.root, self.request_path)
        self.assertTrue(plan["ok"], plan)
        result = approve_operator_feedback_body(
            self.root,
            self.request_path,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="operator:reviewer",
        )
        return plan, result

    def assert_nonreflecting(self, result: dict[str, object], *values: str) -> None:
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)
        for value in values:
            self.assertNotIn(value, rendered)
        guards = result["privacy_guards"]
        self.assertFalse(guards["title_echoed"])
        self.assertFalse(guards["section_values_echoed"])
        self.assertFalse(guards["request_path_echoed"])
        self.assertFalse(guards["matched_private_value_echoed"])
        self.assertFalse(guards["provider_called"])

    def test_plan_is_write_free_content_free_and_digest_bound(self) -> None:
        before = self.snapshot_files()
        request = valid_request()

        plan = plan_operator_feedback_body(self.root, self.request_path)

        self.assertEqual(self.snapshot_files(), before)
        self.assertTrue(plan["ok"])
        self.assertTrue(plan["dry_run"])
        self.assertFalse(plan["approved"])
        self.assertEqual(plan["state"], "preview")
        self.assertRegex(str(plan["plan_sha256"]), r"^[0-9a-f]{64}$")
        self.assertEqual(
            plan["proposed_relative_path"],
            f"ops/feedback/letters/{FEEDBACK_ID}.md",
        )
        self.assertEqual(plan["section_count"], 6)
        self.assertTrue(
            all(item["present"] for item in plan["section_summary"].values())
        )
        self.assertTrue(plan["body_utf8_bytes"] > 0)
        self.assertFalse(plan["external_delivery_performed"])
        self.assert_nonreflecting(
            plan,
            str(self.request_path),
            str(request["title"]),
            *request["sections"].values(),
        )

    def test_request_schema_missing_unknown_and_duplicate_keys_fail_closed(self) -> None:
        missing = valid_request()
        del missing["sections"]["reproduction"]
        self.write_request(missing)
        result = plan_operator_feedback_body(self.root, self.request_path)
        self.assertFalse(result["ok"])
        self.assertIn("feedback_body_sections_invalid", result["blockers"])

        unknown = valid_request()
        unknown["unexpected"] = "safe extra field"
        self.write_request(unknown)
        result = plan_operator_feedback_body(self.root, self.request_path)
        self.assertFalse(result["ok"])
        self.assertIn("feedback_body_request_schema_invalid", result["blockers"])

        unknown["unexpected"] = PRIVATE_MARKER + " person@example.com"
        self.write_request(unknown)
        result = plan_operator_feedback_body(self.root, self.request_path)
        self.assertFalse(result["ok"])
        self.assertEqual(
            result["blockers"],
            ["feedback_body_private_or_secret_content_detected"],
        )
        self.assert_nonreflecting(result, PRIVATE_MARKER)

        self.request_path.write_text(
            '{"schema":"one","schema":"two","feedback_id":"'
            + FEEDBACK_ID
            + '","title":"'
            + PRIVATE_MARKER
            + '","sections":{}}',
            encoding="utf-8",
        )
        result = plan_operator_feedback_body(self.root, self.request_path)
        self.assertEqual(result["blockers"], ["feedback_body_request_invalid"])
        self.assert_nonreflecting(result, PRIVATE_MARKER)

    def test_lone_surrogate_title_and_section_fail_closed(self) -> None:
        title_request = valid_request()
        title_request["title"] = "invalid-\ud800-title"
        self.request_path.write_text(
            json.dumps(title_request, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        title_result = plan_operator_feedback_body(self.root, self.request_path)
        self.assertFalse(title_result["ok"])
        self.assertIn("feedback_body_title_invalid", title_result["blockers"])

        section_request = valid_request()
        section_request["sections"]["task"] = "invalid-\ud800-section"
        self.request_path.write_text(
            json.dumps(section_request, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        section_result = plan_operator_feedback_body(self.root, self.request_path)
        self.assertFalse(section_result["ok"])
        self.assertIn("feedback_body_sections_invalid", section_result["blockers"])

    def test_private_shapes_are_fixed_nonreflecting_blockers(self) -> None:
        private_values = (
            "token=sk-example-placeholder",
            "https://provider.example/private-page",
            "person@example.com",
            "C:\\Users\\example\\archive\\request.json",
            "/home/example/archive/request.json",
            "+82 10-1234-5678",
            "Authorization: " + "Bearer example-token-value-123456",
            "eyJexample12345." + "payloadexample12345." + "signatureexample12345",
            "xoxb-" + "exampleplaceholder123456",
            "glpat-" + "exampleplaceholder123456",
            "AIza" + "ExamplePlaceholderValue1234567890",
        )
        for value in private_values:
            with self.subTest(value=value):
                request = valid_request()
                request["sections"]["environment"] = value
                self.write_request(request)
                result = plan_operator_feedback_body(self.root, self.request_path)
                self.assertFalse(result["ok"])
                self.assertIn(
                    "feedback_body_private_or_secret_content_detected",
                    result["blockers"],
                )
                self.assert_nonreflecting(result, value)

    def test_secret_shaped_feedback_id_is_never_projected(self) -> None:
        private_id = "ghp_" + "exampleplaceholder1234567890"
        request = valid_request()
        request["feedback_id"] = private_id
        self.write_request(request)

        plan = plan_operator_feedback_body(self.root, self.request_path)
        checked = check_operator_feedback_body(self.root, private_id)

        for result in (plan, checked):
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["blockers"],
                ["feedback_body_private_or_secret_content_detected"],
            )
            self.assert_nonreflecting(result, private_id)

    def test_request_must_be_effectively_ignored_and_inside_exact_directory(self) -> None:
        (self.root / ".gitignore").write_text(
            "profiles/local/\n!profiles/local/operator-feedback/requests/letter120.json\n",
            encoding="utf-8",
        )
        result = plan_operator_feedback_body(self.root, self.request_path)
        self.assertEqual(result["blockers"], ["feedback_body_request_not_ignored"])

        outside = self.root / "request.json"
        outside.write_text("{}", encoding="utf-8")
        result = plan_operator_feedback_body(self.root, outside)
        self.assertEqual(result["blockers"], ["feedback_body_request_path_invalid"])
        self.assert_nonreflecting(result, str(outside))

    def test_slash_wildcard_is_not_mistaken_for_git_ignore_authority(self) -> None:
        (self.root / ".gitignore").write_text(
            "profiles/*/letter120.json\n",
            encoding="utf-8",
        )
        self.write_request(valid_request())

        result = plan_operator_feedback_body(self.root, self.request_path)

        self.assertFalse(result["ok"])
        self.assertEqual(result["blockers"], ["feedback_body_request_not_ignored"])

    def test_whitespace_or_backslashes_cannot_be_promoted_to_ignore_authority(self) -> None:
        self.write_request(valid_request())
        for misleading_rule in (" profiles/local/\n", "profiles\\local\\\n"):
            with self.subTest(rule=misleading_rule):
                (self.root / ".gitignore").write_text(
                    misleading_rule,
                    encoding="utf-8",
                )
                result = plan_operator_feedback_body(self.root, self.request_path)
                self.assertFalse(result["ok"])
                self.assertEqual(
                    result["blockers"],
                    ["feedback_body_request_not_ignored"],
                )

    def test_any_later_negation_is_conservatively_rejected(self) -> None:
        self.write_request(valid_request())
        for negation in (
            "!profiles/l?cal/   \n",
            "!profiles/[l]ocal/   \n",
            "!unrelated-example.txt\n",
        ):
            with self.subTest(negation=negation):
                (self.root / ".gitignore").write_text(
                    "profiles/local/\n" + negation,
                    encoding="utf-8",
                )
                result = plan_operator_feedback_body(self.root, self.request_path)
                self.assertFalse(result["ok"])
                self.assertEqual(
                    result["blockers"],
                    ["feedback_body_request_not_ignored"],
                )

    def test_force_added_private_request_is_not_treated_as_ignored(self) -> None:
        subprocess.run(
            ["git", "init", "--quiet", str(self.root)],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "add",
                "--force",
                "--",
                self.request_path.relative_to(self.root).as_posix(),
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        result = plan_operator_feedback_body(self.root, self.request_path)

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["blockers"],
            ["feedback_body_request_not_ignored"],
        )
        self.assert_nonreflecting(result, str(self.request_path))

    def test_symlink_or_reparse_request_is_rejected_before_open(self) -> None:
        original_lstat = body_module.os.lstat

        class ReparseStat:
            def __init__(self, wrapped: os.stat_result, *, symlink: bool) -> None:
                self._wrapped = wrapped
                self.st_file_attributes = 0 if symlink else body_module.REPARSE_FLAG
                self.st_mode = (
                    (wrapped.st_mode & 0o777) | 0o120000 if symlink else wrapped.st_mode
                )

            def __getattr__(self, name: str) -> object:
                return getattr(self._wrapped, name)

        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                def marked_lstat(
                    path: os.PathLike[str] | str,
                ) -> os.stat_result | ReparseStat:
                    info = original_lstat(path)
                    if Path(path) == self.request_path:
                        return ReparseStat(info, symlink=symlink)
                    return info

                with mock.patch.object(
                    body_module.os, "lstat", side_effect=marked_lstat
                ):
                    result = plan_operator_feedback_body(
                        self.root, self.request_path
                    )

                self.assertEqual(
                    result["blockers"],
                    ["feedback_body_request_unsafe_or_invalid"],
                )

    def test_approve_rejects_digest_drift_and_writes_nothing(self) -> None:
        plan = plan_operator_feedback_body(self.root, self.request_path)
        request = valid_request()
        request["sections"]["task"] = "A changed reviewed task."
        self.write_request(request)

        result = approve_operator_feedback_body(
            self.root,
            self.request_path,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="operator:reviewer",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["blockers"], ["feedback_body_plan_changed"])
        self.assertFalse((self.root / "ops").exists())
        self.assertFalse((self.root / "receipts").exists())

    def test_approve_rejects_private_or_unsafe_reviewer_without_writing(self) -> None:
        plan = plan_operator_feedback_body(self.root, self.request_path)
        private_reviewer = "person@example.com"

        result = approve_operator_feedback_body(
            self.root,
            self.request_path,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by=private_reviewer,
        )

        self.assertEqual(result["blockers"], ["feedback_body_reviewer_invalid"])
        self.assertFalse((self.root / "ops").exists())
        self.assertFalse((self.root / "receipts").exists())
        self.assert_nonreflecting(result, private_reviewer)

    def test_approve_rejects_reparse_output_chain_without_writing(self) -> None:
        plan = plan_operator_feedback_body(self.root, self.request_path)
        output_root = self.root / "ops"
        output_root.mkdir()
        original_lstat = body_module.os.lstat

        class ReparseStat:
            def __init__(self, wrapped: os.stat_result) -> None:
                self._wrapped = wrapped
                self.st_file_attributes = body_module.REPARSE_FLAG

            def __getattr__(self, name: str) -> object:
                return getattr(self._wrapped, name)

        def marked_lstat(path: os.PathLike[str] | str) -> os.stat_result | ReparseStat:
            info = original_lstat(path)
            if Path(path) == output_root:
                return ReparseStat(info)
            return info

        with mock.patch.object(body_module.os, "lstat", side_effect=marked_lstat):
            result = approve_operator_feedback_body(
                self.root,
                self.request_path,
                expected_plan_sha256=str(plan["plan_sha256"]),
                reviewed_by="operator:reviewer",
            )

        self.assertEqual(
            result["blockers"], ["feedback_body_existing_body_unsafe"]
        )
        self.assertEqual(list(output_root.iterdir()), [])

    def test_approve_preserves_exact_body_and_is_exactly_idempotent(self) -> None:
        plan, first = self.approve()
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["state"], "written")
        self.assertEqual(len(first["files_written"]), 2)
        self.assertRegex(
            str(first["feedback_ref"]), r"^feedback-body-sha256:[0-9a-f]{64}$"
        )
        body_path = self.root / str(first["proposed_relative_path"])
        receipt_path = self.root / str(first["proposed_receipt_relative_path"])
        raw = body_path.read_bytes()
        self.assertEqual(raw.count(b"\r"), 0)
        self.assertTrue(raw.endswith(b"\n"))
        text = raw.decode("utf-8")
        for heading in body_module.STRUCTURE_LINES:
            self.assertEqual(text.splitlines().count(heading), 1)
        for value in valid_request()["sections"].values():
            self.assertEqual(text.count(value), 1)
        self.assertIn("### 관찰된 실패 (사실)", text)
        self.assertIn("### 추정 원인 (추정)", text)
        before = self.snapshot_files()

        second = approve_operator_feedback_body(
            self.root,
            self.request_path,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="operator:reviewer",
        )

        self.assertTrue(receipt_path.is_file())
        self.assertEqual(second["state"], "already_written")
        self.assertEqual(second["files_written"], [])
        self.assertEqual(self.snapshot_files(), before)

    def test_approve_conflict_never_overwrites_existing_body(self) -> None:
        plan = plan_operator_feedback_body(self.root, self.request_path)
        body_path = self.root / str(plan["proposed_relative_path"])
        body_path.parent.mkdir(parents=True)
        body_path.write_bytes(b"pre-existing user body\n")

        result = approve_operator_feedback_body(
            self.root,
            self.request_path,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="operator:reviewer",
        )

        self.assertEqual(
            result["blockers"], ["feedback_body_existing_body_conflict"]
        )
        self.assertEqual(body_path.read_bytes(), b"pre-existing user body\n")

    def test_receipt_failure_is_crash_honest_and_safe_to_resume(self) -> None:
        plan = plan_operator_feedback_body(self.root, self.request_path)
        original_write = body_module._write_create_if_absent

        def fail_receipt(root: Path, path: Path, value: bytes) -> bool:
            if "receipts" in path.parts:
                raise OSError("simulated receipt failure")
            return original_write(root, path, value)

        with mock.patch.object(
            body_module, "_write_create_if_absent", side_effect=fail_receipt
        ):
            partial = approve_operator_feedback_body(
                self.root,
                self.request_path,
                expected_plan_sha256=str(plan["plan_sha256"]),
                reviewed_by="operator:reviewer",
            )

        self.assertEqual(partial["state"], "partial")
        self.assertTrue(partial["body_persisted"])
        self.assertFalse(partial["receipt_persisted"])
        self.assertEqual(
            partial["blockers"], ["feedback_body_receipt_write_failed"]
        )
        resumed = approve_operator_feedback_body(
            self.root,
            self.request_path,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="operator:reviewer",
        )
        self.assertTrue(resumed["ok"], resumed)
        self.assertTrue(resumed["receipt_persisted"])

    def test_final_verification_detects_body_change_during_receipt_publish(self) -> None:
        plan = plan_operator_feedback_body(self.root, self.request_path)
        body_path = self.root / str(plan["proposed_relative_path"])
        original_write = body_module._write_create_if_absent

        def corrupt_after_receipt(root: Path, path: Path, value: bytes) -> bool:
            created = original_write(root, path, value)
            if "receipts" in path.parts:
                body_path.write_bytes(b"corrupted after body verification\n")
            return created

        with mock.patch.object(
            body_module,
            "_write_create_if_absent",
            side_effect=corrupt_after_receipt,
        ):
            result = approve_operator_feedback_body(
                self.root,
                self.request_path,
                expected_plan_sha256=str(plan["plan_sha256"]),
                reviewed_by="operator:reviewer",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "partial")
        self.assertEqual(
            result["blockers"], ["feedback_body_final_verification_failed"]
        )
        self.assertFalse(result["body_persisted"])
        self.assertTrue(result["receipt_persisted"])
        self.assertNotIn(
            "corrupted after body verification",
            json.dumps(result, ensure_ascii=False),
        )

    def test_check_reports_body_health_and_requires_metadata_binding(self) -> None:
        _plan, approved = self.approve()

        unbound = check_operator_feedback_body(self.root, FEEDBACK_ID)

        self.assertFalse(unbound["ok"])
        self.assertEqual(unbound["state"], "blocked")
        self.assertEqual(unbound["blockers"], ["feedback_record_binding_missing"])
        self.assertEqual(
            unbound["body_check"],
            {
                "structure_valid": True,
                "privacy_valid": True,
                "exact_hash_bound_by_receipt": True,
            },
        )
        self.assertFalse(unbound["record_binding"]["record_present"])
        record = self.root / "ops" / "feedback" / f"{FEEDBACK_ID}.yml"
        record.write_text(
            "feedback_id: "
            + FEEDBACK_ID
            + "\nfeedback_ref: "
            + str(approved["feedback_ref"])
            + "\n",
            encoding="utf-8",
        )

        bound = check_operator_feedback_body(self.root, FEEDBACK_ID)

        self.assertTrue(bound["ok"], bound)
        self.assertEqual(bound["state"], "verified")
        self.assertTrue(bound["record_binding"]["record_present"])
        self.assertTrue(bound["record_binding"]["feedback_ref_bound"])
        self.assertEqual(bound["blockers"], [])

    def test_check_fail_closes_unhashable_yaml_record_key(self) -> None:
        _plan, approved = self.approve()
        record = self.root / "ops" / "feedback" / f"{FEEDBACK_ID}.yml"
        record.write_text(
            "? [unhashable, key]\n: value\nfeedback_id: "
            + FEEDBACK_ID
            + "\nfeedback_ref: "
            + str(approved["feedback_ref"])
            + "\n",
            encoding="utf-8",
        )

        result = check_operator_feedback_body(self.root, FEEDBACK_ID)

        self.assertFalse(result["ok"])
        self.assertIn("feedback_record_binding_invalid", result["blockers"])

    def test_check_detects_body_conflict_without_echoing_content(self) -> None:
        _plan, approved = self.approve()
        body_path = self.root / str(approved["proposed_relative_path"])
        private_value = "person@example.com"
        body_path.write_text(private_value + "\n", encoding="utf-8")

        result = check_operator_feedback_body(self.root, FEEDBACK_ID)

        self.assertFalse(result["ok"])
        self.assertIn("feedback_body_structure_invalid", result["blockers"])
        self.assertIn(
            "feedback_body_private_or_secret_content_detected", result["blockers"]
        )
        self.assertIn("feedback_body_receipt_missing", result["blockers"])
        self.assert_nonreflecting(result, private_value)


if __name__ == "__main__":
    unittest.main()
