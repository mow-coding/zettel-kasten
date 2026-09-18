"""v0.4.27: the small follow-ups from the client's 2026-09-18 v0.4.25 success report.

1. A usage refusal of project-version-update (missing --target, --reviewed-by
   or --affirm-external-writers-quiescent) names its fixed code as the cause.
2. A bootstrap installed from a local wheel file is told to reinstall from the
   exact public release URL.
3. A refused permission grant says which position was refused and which
   operation names are grantable, without echoing the refused value.
4. A UTF-8 byte-order mark in an intake plan or batch request is accepted;
   UTF-16/32 marks are named.
5. discard-draft and discard-draft-restore previews expose plan_sha256 at the
   top level like every other reviewed writer.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest import mock

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import source_intake_batch_exact as batch_exact
from wom_kit import source_intake_record_exact as record_exact
from wom_kit import work_session_command as command
from wom_kit import work_session_permission as permission
from wom_kit import work_session_service as service


class UsageErrorCauseTests(unittest.TestCase):
    def test_usage_refusals_carry_their_token_and_the_journal_stage(self) -> None:
        for token in (
            "project_version_update_quiescence_required",
            "project_version_update_target_required",
            "project_version_update_reviewer_required",
            "project_version_update_abandon_requires_resume",
        ):
            with self.subTest(token=token):
                self.assertEqual(
                    archive_cli._project_version_update_content_free_cause(ValueError(token), journal_stage="starting"),
                    {"cause_code": token, "cause_stage": "starting"},
                )

    def test_other_value_errors_never_become_a_cause(self) -> None:
        for error in (
            ValueError("project version update target required"),
            ValueError("C:\\Users\\<user>\\private\\path"),
            ValueError("credential_registry_local_profile_not_ignored"),
            ValueError("project_version_update_x", "second"),
            service.WorkSessionServiceError("work_session_service_invalid"),  # a ValueError subclass
        ):
            with self.subTest(error=repr(error)[:50]):
                self.assertIsNone(archive_cli._project_version_update_content_free_cause(error, journal_stage="starting"))


class PublicWheelHintTests(unittest.TestCase):
    def test_blocked_result_advice_names_the_public_url_reinstall(self) -> None:
        text = Path(archive_services.__file__).read_text(encoding="utf-8")
        self.assertIn('if "project_runtime_exact_public_wheel_required" in blockers', text)
        self.assertIn("Reinstall the updater bootstrap from the exact public release URL", text)


class PermissionRefusalDetailTests(unittest.TestCase):
    def test_refused_operation_position_and_grantable_names_are_reported(self) -> None:
        with self.assertRaises(permission.WorkSessionPermissionError) as raised:
            permission.normalize_grant("limited", ["create_draft", "discard_draft", "zettel_edge"])
        error = raised.exception
        self.assertEqual(error.code, "work_session_permission_operation_not_grantable")
        self.assertEqual(error.detail["rejected_operation_index"], 1)
        self.assertIn("draft_discard", error.detail["grantable_operations"])
        self.assertIn("project_version_update", error.detail["always_dialog_operations"])
        self.assertNotIn("discard_draft", json.dumps(error.detail))  # the refused value is not echoed
        self.assertEqual(len(error.detail["grantable_operations"]), len(permission.GRANTABLE_OPERATIONS))

    def test_detail_survives_the_service_boundary_into_the_public_failure(self) -> None:
        def refuse():
            permission.normalize_grant("limited", ["PRIVATE_NAME_DO_NOT_ECHO"])

        with self.assertRaises(service.WorkSessionServiceError) as raised:
            service._safe_call(refuse)
        error = raised.exception
        self.assertEqual(error.code, "work_session_permission_operation_not_grantable")
        self.assertEqual(error.detail["rejected_operation_index"], 0)
        failure = command.management_failure(error.code, detail=error.detail)
        self.assertFalse(failure["ok"])
        self.assertEqual(failure["reason_detail"]["rejected_operation_index"], 0)
        self.assertNotIn("PRIVATE_NAME", json.dumps(failure))
        self.assertNotIn("reason_detail", command.management_failure("work_session_service_invalid"))

    def test_other_permission_errors_carry_no_detail(self) -> None:
        with self.assertRaises(permission.WorkSessionPermissionError) as raised:
            permission.normalize_grant("allow_all", ["create_draft"])
        self.assertEqual(raised.exception.code, "work_session_permission_invalid")
        self.assertIsNone(raised.exception.detail)


class ByteOrderMarkTests(unittest.TestCase):
    def test_utf8_bom_is_accepted_and_utf16_is_named(self) -> None:
        document = json.dumps({"schema": "x", "items": []}).encode("utf-8")
        for loader, invalid, encoding in (
            (record_exact._strict_json_object, "source_intake_record_plan_invalid", "source_intake_record_plan_encoding_invalid"),
            (batch_exact._strict_json_object, "source_intake_batch_request_invalid", "source_intake_batch_request_encoding_invalid"),
        ):
            with self.subTest(loader=loader.__module__):
                self.assertEqual(loader(b"\xef\xbb\xbf" + document), {"schema": "x", "items": []})
                self.assertEqual(loader(document), {"schema": "x", "items": []})
                for raw in (b"\xff\xfe" + document, b"\xfe\xff" + document, b"\x00\x00\xfe\xff" + document):
                    with self.assertRaises(Exception) as raised:
                        loader(raw)
                    self.assertEqual(raised.exception.code, encoding)
                with self.assertRaises(Exception) as raised:
                    loader(b"\xef\xbb\xbf" + b"not json")
                self.assertEqual(raised.exception.code, invalid)

    def test_a_second_bom_after_the_first_is_still_invalid_json(self) -> None:
        document = json.dumps({"schema": "x"}).encode("utf-8")
        with self.assertRaises(record_exact.SourceIntakeRecordExactError) as raised:
            record_exact._strict_json_object(b"\xef\xbb\xbf\xef\xbb\xbf" + document)
        self.assertEqual(raised.exception.code, "source_intake_record_plan_invalid")


class DiscardPlanShapeTests(unittest.TestCase):
    def test_discard_plans_mirror_plan_sha256_at_the_top_level(self) -> None:
        from wom_kit import completion_workflows
        import inspect
        for name in ("_draft_discard_plan_core", "_draft_discard_restore_plan_core"):
            source = inspect.getsource(getattr(completion_workflows, name))
            with self.subTest(function=name):
                self.assertIn('"lifecycle_action": "discard_draft', source)
                self.assertRegex(source, r'"archive_id": archive_id,\n\s+(# [^\n]*\n\s+)*"plan_sha256": plan_sha256 if')


if __name__ == "__main__":
    unittest.main()
