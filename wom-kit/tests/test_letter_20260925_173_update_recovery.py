"""Beta letter wom-feedback-20260925-173: a v0.4.38 -> v0.4.42 project update
ended at the native approval with only an exception family in its result,
and the official resume and abandon ended the same way.

Request (2): the fixed sub-code and the failing stage must reach the result
without any private value. ``ExactHumanApprovalWindowsError`` carries a code
from a closed set; before v0.4.43 only the family crossed.
"""

from __future__ import annotations

import unittest

from wom_kit import archive_cli
from wom_kit.exact_human_approval_windows import ExactHumanApprovalWindowsError


class WindowsApprovalCauseCodeTests(unittest.TestCase):
    def test_every_windows_approval_code_crosses_with_its_stage(self) -> None:
        for code in sorted(ExactHumanApprovalWindowsError._CODES):
            with self.subTest(code=code):
                projected = archive_cli._project_version_update_content_free_cause(
                    ExactHumanApprovalWindowsError(code), journal_stage="native-approval"
                )
                self.assertEqual(projected, {"cause_code": code, "cause_stage": "native-approval"})

    def test_an_unknown_native_text_never_crosses(self) -> None:
        error = ExactHumanApprovalWindowsError("native text with a private detail")
        projected = archive_cli._project_version_update_content_free_cause(error, journal_stage="verify-release")
        self.assertEqual(projected["cause_code"], "exact_human_approval_native_call_failed")
        self.assertEqual(projected["cause_stage"], "verify-release")



class BareReviewerAndStrandedTransactionTests(unittest.TestCase):
    """A tester passed ``--reviewed-by alex``; the services accepted it,
    the approval context required a kind prefix, and the reserved transaction
    stayed locked because only a human cancel released it."""

    def test_a_bare_reviewer_is_read_as_a_person_and_other_kinds_stay_refused(self) -> None:
        from wom_kit import exact_human_approval_windows as windows
        from wom_kit.operation_approval_binding import plan_digest_approval_binding

        binding = plan_digest_approval_binding(
            windows.ExactHumanApprovalOperation.project_version_update, "sha256:" + "a" * 64
        )
        context = binding.context(archive_id="archive:personal:synthetic", reviewer_claim="alex")
        self.assertEqual(context.reviewer_claim, "person:alex")
        same = binding.context(archive_id="archive:personal:synthetic", reviewer_claim="person:alex")
        from wom_kit.exact_human_approval import exact_human_approval_context_sha256

        self.assertEqual(exact_human_approval_context_sha256(context), exact_human_approval_context_sha256(same))
        for refused in ("agent:codex", "alex with space", "x" * 97):
            with self.subTest(refused=refused[:20]):
                with self.assertRaises(windows.ExactHumanApprovalWindowsError):
                    binding.context(archive_id="archive:personal:synthetic", reviewer_claim=refused)

    def test_a_pre_dialog_context_failure_releases_the_reserved_transaction(self) -> None:
        import tempfile
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import patch

        from wom_kit import archive_services
        from wom_kit.exact_human_approval_windows import ExactHumanApprovalWindowsError
        from wom_kit.exact_human_approval_workflow import ExactHumanApprovalWorkflowError

        cases = (
            ("raw_context_invalid", ExactHumanApprovalWindowsError("exact_human_approval_context_invalid"), True),
            ("human_cancel", ExactHumanApprovalWorkflowError("exact_human_approval_cancelled"), True),
            ("unknown_after_dialog", ExactHumanApprovalWorkflowError("exact_human_approval_state_unknown"), False),
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = __import__("pathlib").Path(tmp)
            for name, failure, expect_cancel in cases:
                with self.subTest(case=name):
                    state = SimpleNamespace(
                        inspection_root=project, project_root=project,
                        transaction=SimpleNamespace(transaction_ref="update_" + "9" * 32, close=lambda: None),
                        prepared_preview={"status": "prepared"}, reviewer="alex",
                        terminal_update_verified=False,
                    )
                    prepared = archive_services._ProjectVersionUpdatePreparedApproval(
                        preview={"status": "prepared"}, state=state,
                    )

                    def prepared_generator():
                        yield prepared

                    cancels: list[str] = []

                    def executor(*_args, failure=failure, **_kwargs):
                        raise failure

                    with (
                        patch.object(archive_services, "_project_update_fresh_update_cleanup_preflight_read_only",
                                     return_value=None),
                        patch.object(archive_services, "_wom_kit_project_version_update_approval_authority_matches",
                                     return_value=True),
                        patch.object(archive_services, "_wom_kit_project_version_update_legacy_core_generator",
                                     side_effect=lambda *_a, **_k: prepared_generator()),
                        patch.object(archive_services, "_project_update_terminal_execution_lease",
                                     return_value=nullcontext()),
                        patch.object(archive_services, "_project_update_cancel_before_native",
                                     side_effect=lambda _state: cancels.append("cancel")),
                        patch.object(archive_services, "_project_update_close_after_service_failure",
                                     side_effect=lambda *_a, **_k: None),
                    ):
                        with self.assertRaises(type(failure)):
                            archive_services._wom_kit_project_version_update_live_approval_transaction(
                                project, target="v0.4.43", reviewed_by="alex",
                                affirm_external_writers_quiescent=True, approval_executor=executor,
                                _expected_approval_root=project, _expected_archive_id="archive:test",
                            )
                    self.assertEqual(cancels, ["cancel"] if expect_cancel else [])


if __name__ == "__main__":
    unittest.main()
