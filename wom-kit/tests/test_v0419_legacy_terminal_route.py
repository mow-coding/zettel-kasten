"""The prewrite compatibility route must not swallow completed cleanup."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services as services


class LegacyTerminalRouteTests(unittest.TestCase):
    def test_resume_bootstrap_identity_excludes_only_non_fetch_transport(self):
        sealed = services.project_runtime.BootstrapWheel(
            version="0.4.19",
            tag="v0.4.19",
            url="https://invalid.example/intent-bound-never-fetched",
            sha256="a" * 64,
            file_name="wom_kit-0.4.19-py3-none-any.whl",
        )
        live = replace(
            sealed,
            url=(
                "https://github.com/mow-coding/zettel-kasten/releases/"
                "download/v0.4.19/wom_kit-0.4.19-py3-none-any.whl"
            ),
        )
        self.assertNotEqual(live, sealed)
        self.assertTrue(
            services._project_update_approved_bootstrap_identity_matches(live, sealed)
        )
        for changes in (
            {"version": "0.4.18"},
            {"tag": "v0.4.18"},
            {"sha256": "b" * 64},
            {"file_name": "wom_kit-0.4.18-py3-none-any.whl"},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(
                    services._project_update_approved_bootstrap_identity_matches(
                        replace(live, **changes), sealed
                    )
                )
        self.assertFalse(
            services._project_update_approved_bootstrap_identity_matches(None, sealed)
        )

    def test_only_exact_completed_cleanup_returns_to_authenticated_resume(self):
        authority = "sha256:" + "a" * 64
        cases = (
            ("complete", "exact", "completed", "verified", authority, authority, True),
            ("completed_original", "exact", "completed", "verified", None, None, True),
            ("missing_authority", "exact", "completed", "verified", None, authority, False),
            ("forged_authority", "exact", "completed", "verified", "sha256:" + "b" * 64, authority, False),
            ("malformed_authority", "exact", "completed", "verified", "private-marker", authority, False),
            ("missing_plan", "exact", "completed", "verified", authority, None, False),
            ("plan_drift", "exact", "completed", "verified", authority, OSError("synthetic-private-marker"), False),
            ("partial_journal", "partial", "completed", "verified", authority, authority, False),
            ("unverified_terminal", "exact", "completed", "intent", authority, authority, False),
            ("prewrite_not_terminal", "exact", "approval_bound", "verified", authority, authority, False),
        )
        for label, journal_state, phase, stage, state_authority, plan_authority, returns in cases:
            with self.subTest(label=label):
                transaction = Mock(spec=services.project_update_transaction.ProjectUpdateTransaction)
                transaction.intent = SimpleNamespace(
                    runtime_candidate=SimpleNamespace(legacy_document_shape=True)
                )
                transaction.inspect.return_value = SimpleNamespace(
                    journal=SimpleNamespace(
                        state=journal_state,
                        verified_prefix=(SimpleNamespace(phase=phase, stage=stage),),
                    ),
                    lock_backlinked=False,
                )
                if isinstance(plan_authority, BaseException):
                    transaction.cleanup_authority_sha256_read_only.side_effect = plan_authority
                else:
                    transaction.cleanup_authority_sha256_read_only.return_value = plan_authority
                state = SimpleNamespace(
                    transaction=transaction,
                    target_tag="v0.4.15",
                    existing_cleanup_authority_sha256=state_authority,
                    directory_guard=Mock(),
                )
                approval = Mock(side_effect=AssertionError("no native approval here"))
                with patch.object(services, "_project_update_close_after_service_failure") as close:
                    def route():
                        return services._project_update_resume_legacy_approval_bound_prewrite(
                            state,
                            lifetime=Mock(),
                            approval_executor=approval,
                            progress_callback=None,
                            key_provider=None,
                            resume_boundary=None,
                        )

                    if returns:
                        self.assertIsNone(route())
                        close.assert_not_called()
                    else:
                        with self.assertRaisesRegex(
                            services.ArchiveServiceError,
                            "^project_version_update_legacy_recovery_state_ambiguous$",
                        ):
                            route()
                        close.assert_called_once()
                approval.assert_not_called()


if __name__ == "__main__":
    unittest.main()
