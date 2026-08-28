from __future__ import annotations

import ctypes
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_services,
    completion_workflows,
    credential_secure_registry,
    exact_human_approval,
    operation_approval_binding,
)
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL_ID = "zet_20240504_fake_lunch_thought"
OBJECT_ID = (
    "sha256:"
    "9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
)
ROLE = "evidence"
REVIEWER = "person:letter140-approval-boundary-test"


class _Native:
    def __init__(
        self,
        result: tuple[int, bool],
        hook: Callable[[], None] | None = None,
    ) -> None:
        self.result = result
        self.hook = hook

    def show(self, **_kwargs: str) -> tuple[int, bool]:
        if self.hook is not None:
            self.hook()
        return self.result


class _EphemeralKeyProvider:
    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        if create_if_missing is not True:
            raise AssertionError("key creation authority was not explicit")
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class Letter140ApprovalBoundaryPrivacyTests(unittest.TestCase):
    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        indexed = archive_services.index_archive(root)
        self.assertTrue(indexed["ok"], indexed)
        return root

    @staticmethod
    def create_directory_junction(link: Path, target: Path) -> None:
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            raise OSError("Windows junction creation failed")

    def require_directory_junctions(self, parent: Path) -> None:
        target = parent / "junction-target"
        link = parent / "junction-link"
        target.mkdir()
        try:
            self.create_directory_junction(link, target)
        except OSError:
            self.skipTest("Windows directory junctions are unavailable")
        finally:
            if link.exists():
                os.rmdir(link)

    @staticmethod
    def context(root: Path):
        plan = completion_workflows.zettel_objet_link_plan(
            root,
            zettel_id=ZETTEL_ID,
            object_id=OBJECT_ID,
            role=ROLE,
        )
        if plan.get("ok") is not True:
            raise AssertionError(plan)
        binding = operation_approval_binding.zettel_objet_link_approval_binding(
            plan
        )
        return plan, binding.context(
            archive_id=str(plan["archive_id"]),
            reviewer_claim=REVIEWER,
        )

    @staticmethod
    def run_cli(values: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(values)
        return int(code), stdout.getvalue(), stderr.getvalue()

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_preview_return_root_swap_is_blocked_before_native_workflow(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            self.require_directory_junctions(parent)
            root = self.archive(parent).resolve()
            outside = parent / "outside-root"
            shutil.copytree(FIXTURE, outside)
            hidden = parent / "archive-hidden"
            baseline = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            real_plan = completion_workflows.zettel_objet_link_plan
            attempted = False
            blocked = False

            def plan_then_attempt_swap(*args, **kwargs):
                nonlocal attempted, blocked
                result = real_plan(*args, **kwargs)
                attempted = True
                try:
                    root.rename(hidden)
                except OSError:
                    blocked = True
                else:
                    self.create_directory_junction(root, outside)
                return result

            common = [
                "zettel-objet-link",
                str(root),
                "--zettel-id",
                ZETTEL_ID,
                "--object-id",
                OBJECT_ID,
                "--role",
                ROLE,
                "--approve",
                "--expected-plan-sha256",
                str(baseline["summary"]["plan_sha256"]),
                "--reviewed-by",
                REVIEWER,
                "--format",
                "json",
            ]
            try:
                with (
                    mock.patch.object(
                        completion_workflows,
                        "zettel_objet_link_plan",
                        side_effect=plan_then_attempt_swap,
                    ),
                    mock.patch.object(
                        archive_cli,
                        "_execute_zettel_objet_link_exact_human_approved_write",
                        side_effect=ExactHumanApprovalWorkflowError(
                            "exact_human_approval_cancelled"
                        ),
                    ),
                ):
                    code, stdout, stderr = self.run_cli(common)
                self.assertEqual(code, 1)
                self.assertEqual(stderr, "")
                self.assertTrue(attempted)
                self.assertTrue(blocked)
                self.assertFalse(hidden.exists())
                self.assertEqual(json.loads(stdout)["effects_state"], "none")
                self.assertFalse((root / "profiles").exists())
            finally:
                if root.exists() and root.is_symlink():
                    os.rmdir(root)
                if hidden.exists() and not root.exists():
                    hidden.rename(root)

    def test_cancel_does_not_enter_post_decision_boundary_or_write_profiles(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary)).resolve()
            with archive_cli._zettel_objet_link_approval_read_boundary(
                root
            ) as (bound_root, _archive_id):
                _plan, context = self.context(bound_root)
                boundary_calls = 0

                def boundary():
                    nonlocal boundary_calls
                    boundary_calls += 1
                    return archive_cli._zettel_objet_link_post_decision_boundary(
                        bound_root
                    )

                with self.assertRaises(ExactHumanApprovalWorkflowError) as error:
                    _execute_exact_human_approved_write_core(
                        bound_root,
                        context,
                        lambda _claim: {"ok": True},
                        native=_Native((2, False)),
                        key_provider=_EphemeralKeyProvider(),
                        post_decision_boundary=boundary,
                    )
            self.assertEqual(error.exception.code, "exact_human_approval_cancelled")
            self.assertEqual(boundary_calls, 0)
            self.assertFalse((root / "profiles").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_native_review_root_swap_is_blocked_until_claim_writer_finishes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            self.require_directory_junctions(parent)
            root = self.archive(parent).resolve()
            outside = parent / "outside-native-root"
            shutil.copytree(FIXTURE, outside)
            hidden = parent / "archive-hidden-native"
            attempted = False
            blocked = False

            def attempt_swap() -> None:
                nonlocal attempted, blocked
                attempted = True
                try:
                    root.rename(hidden)
                except OSError:
                    blocked = True
                else:
                    self.create_directory_junction(root, outside)

            try:
                with archive_cli._zettel_objet_link_approval_read_boundary(
                    root
                ) as (bound_root, _archive_id):
                    _plan, context = self.context(bound_root)
                    result = _execute_exact_human_approved_write_core(
                        bound_root,
                        context,
                        lambda _claim: {"ok": False},
                        native=_Native(
                            (APPROVE_BUTTON_ID, True),
                            hook=attempt_swap,
                        ),
                        key_provider=_EphemeralKeyProvider(),
                        post_decision_boundary=lambda: (
                            archive_cli._zettel_objet_link_post_decision_boundary(
                                bound_root
                            )
                        ),
                    )
                self.assertFalse(result["ok"])
                self.assertTrue(attempted)
                self.assertTrue(blocked)
                self.assertFalse(hidden.exists())
                self.assertEqual(
                    list(outside.rglob("approval_*.json")),
                    [],
                )
            finally:
                if hidden.exists() and not root.exists():
                    hidden.rename(root)

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_native_claim_parent_junction_is_rejected_before_key_or_claim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            self.require_directory_junctions(parent)
            root = self.archive(parent).resolve()
            outside = parent / "outside-native-claims"
            outside.mkdir()
            claims_parent = (
                root
                / "profiles"
                / "local"
                / "exact-human-approvals"
                / "claims"
            )
            injected = False

            def inject_claim_junction() -> None:
                nonlocal injected
                claims_parent.parent.mkdir(parents=True, exist_ok=True)
                self.create_directory_junction(claims_parent, outside)
                injected = True

            with archive_cli._zettel_objet_link_approval_read_boundary(
                root
            ) as (bound_root, _archive_id):
                _plan, context = self.context(bound_root)
                with self.assertRaises(ExactHumanApprovalWorkflowError) as error:
                    _execute_exact_human_approved_write_core(
                        bound_root,
                        context,
                        lambda _claim: {"ok": True},
                        native=_Native(
                            (APPROVE_BUTTON_ID, True),
                            hook=inject_claim_junction,
                        ),
                        key_provider=_EphemeralKeyProvider(),
                        post_decision_boundary=lambda: (
                            archive_cli._zettel_objet_link_post_decision_boundary(
                                bound_root
                            )
                        ),
                    )
            self.assertEqual(
                error.exception.code,
                "exact_human_approval_key_unavailable",
            )
            self.assertTrue(injected)
            self.assertEqual(list(outside.iterdir()), [])
            os.rmdir(claims_parent)

    @unittest.skipUnless(os.name == "nt", "Windows hard-link contract")
    def test_registry_lock_hardlink_preemption_opens_and_writes_nothing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.archive(parent).resolve()
            outside = parent / "PRIVATE_OUTSIDE_LOCK"
            outside.write_bytes(b"")
            with archive_cli._zettel_objet_link_approval_read_boundary(
                root
            ) as (bound_root, _archive_id):
                with archive_cli._zettel_objet_link_post_decision_boundary(
                    bound_root
                ):
                    lock_path = (
                        bound_root
                        / "profiles"
                        / "local"
                        / "credential-intake"
                        / ".registry.lock"
                    )
                    real_check = (
                        credential_secure_registry._ensure_safe_parent_chain
                    )
                    injected = False

                    def check_then_preempt(*args, **kwargs):
                        nonlocal injected
                        result = real_check(*args, **kwargs)
                        path = Path(args[1])
                        if path == lock_path and not injected:
                            os.link(outside, lock_path)
                            injected = True
                        return result

                    with (
                        mock.patch.object(
                            credential_secure_registry,
                            "_ensure_safe_parent_chain",
                            side_effect=check_then_preempt,
                        ),
                        mock.patch.object(
                            ctypes,
                            "WinDLL",
                            wraps=ctypes.WinDLL,
                        ) as win_dll,
                        self.assertRaises(
                            credential_secure_registry.SecureCredentialRegistryError
                        ),
                    ):
                        with credential_secure_registry._InterprocessLock(
                            lock_path,
                            create_if_missing=True,
                        ):
                            self.fail("unsafe hard-link lock was accepted")
                    self.assertTrue(injected)
                    win_dll.assert_not_called()
            self.assertEqual(outside.read_bytes(), b"")

    @unittest.skipUnless(os.name == "nt", "Windows hard-link contract")
    def test_claim_create_hardlink_preemption_reads_and_writes_nothing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.archive(parent).resolve()
            outside = parent / "PRIVATE_OUTSIDE_CLAIM_CREATE"
            outside.write_bytes(b"")
            with archive_cli._zettel_objet_link_approval_read_boundary(
                root
            ) as (bound_root, _archive_id):
                _plan, context = self.context(bound_root)
                real_create = (
                    archive_services._write_activity_group_bytes_new_file_bound
                )
                injected = False

                def preempt_then_create(binding, path: Path, raw: bytes):
                    nonlocal injected
                    if path.suffix == ".json" and not injected:
                        os.link(outside, path)
                        injected = True
                    return real_create(binding, path, raw)

                with (
                    mock.patch.object(
                        archive_services,
                        "_write_activity_group_bytes_new_file_bound",
                        side_effect=preempt_then_create,
                    ),
                    mock.patch.object(
                        exact_human_approval,
                        "_read_bound_claim_bytes",
                        wraps=exact_human_approval._read_bound_claim_bytes,
                    ) as claim_reader,
                    self.assertRaises(ExactHumanApprovalWorkflowError) as error,
                ):
                    _execute_exact_human_approved_write_core(
                        bound_root,
                        context,
                        lambda _claim: {"ok": True},
                        native=_Native((APPROVE_BUTTON_ID, True)),
                        key_provider=_EphemeralKeyProvider(),
                        post_decision_boundary=lambda: (
                            archive_cli._zettel_objet_link_post_decision_boundary(
                                bound_root
                            )
                        ),
                    )
                self.assertEqual(error.exception.code, "exact_human_approval_claim_failed")
                self.assertTrue(injected)
                claim_reader.assert_not_called()
            self.assertEqual(outside.read_bytes(), b"")

    @unittest.skipUnless(os.name == "nt", "Windows hard-link contract")
    def test_claim_read_hardlink_preemption_never_opens_outside(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.archive(parent).resolve()
            outside = parent / "PRIVATE_OUTSIDE_CLAIM_READ"
            outside.write_bytes(b"PRIVATE_UNKNOWN")
            hidden_claim: Path | None = None
            with archive_cli._zettel_objet_link_approval_read_boundary(
                root
            ) as (bound_root, _archive_id):
                _plan, context = self.context(bound_root)
                real_reader = exact_human_approval._read_bound_claim_bytes
                injected = False

                def preempt_then_read(path: Path, *, parent_binding):
                    nonlocal injected, hidden_claim
                    if not injected:
                        hidden_claim = path.with_name(path.name + ".original")
                        path.rename(hidden_claim)
                        os.link(outside, path)
                        injected = True
                    with mock.patch.object(
                        ctypes,
                        "WinDLL",
                        side_effect=AssertionError(
                            "outside claim handle must not be opened"
                        ),
                    ):
                        return real_reader(
                            path,
                            parent_binding=parent_binding,
                        )

                with (
                    mock.patch.object(
                        exact_human_approval,
                        "_read_bound_claim_bytes",
                        side_effect=preempt_then_read,
                    ),
                    self.assertRaises(ExactHumanApprovalWorkflowError) as error,
                ):
                    _execute_exact_human_approved_write_core(
                        bound_root,
                        context,
                        lambda _claim: {"ok": True},
                        native=_Native((APPROVE_BUTTON_ID, True)),
                        key_provider=_EphemeralKeyProvider(),
                        post_decision_boundary=lambda: (
                            archive_cli._zettel_objet_link_post_decision_boundary(
                                bound_root
                            )
                        ),
                    )
                self.assertEqual(error.exception.code, "exact_human_approval_claim_failed")
                self.assertTrue(injected)
                self.assertIsNotNone(hidden_claim)
                self.assertTrue(hidden_claim.is_file())
            self.assertEqual(outside.read_bytes(), b"PRIVATE_UNKNOWN")

    @unittest.skipUnless(os.name == "nt", "Windows hard-link contract")
    def test_claim_finalize_foreign_leaf_is_preserved_and_claim_stays_started(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.archive(parent).resolve()
            outside = parent / "PRIVATE_OUTSIDE_CLAIM_FINALIZE"
            foreign = b"PRIVATE_UNKNOWN_FINALIZE"
            outside.write_bytes(foreign)
            hidden_claim: Path | None = None
            with archive_cli._zettel_objet_link_approval_read_boundary(
                root
            ) as (bound_root, _archive_id):
                _plan, context = self.context(bound_root)
                real_replace = (
                    archive_services._replace_regular_file_bytes_compare_and_swap
                )
                injected = False

                def preempt_then_replace(root_path, path: Path, **kwargs):
                    nonlocal injected, hidden_claim
                    if (
                        kwargs.get("error_prefix")
                        == "exact_human_approval"
                        and not injected
                    ):
                        hidden_claim = path.with_name(path.name + ".started")
                        path.rename(hidden_claim)
                        os.link(outside, path)
                        injected = True
                    return real_replace(root_path, path, **kwargs)

                with (
                    mock.patch.object(
                        archive_services,
                        "_replace_regular_file_bytes_compare_and_swap",
                        side_effect=preempt_then_replace,
                    ),
                    self.assertRaises(ExactHumanApprovalWorkflowError) as error,
                ):
                    _execute_exact_human_approved_write_core(
                        bound_root,
                        context,
                        lambda _claim: {"ok": True},
                        native=_Native((APPROVE_BUTTON_ID, True)),
                        key_provider=_EphemeralKeyProvider(),
                        post_decision_boundary=lambda: (
                            archive_cli._zettel_objet_link_post_decision_boundary(
                                bound_root
                            )
                        ),
                    )
                self.assertEqual(error.exception.code, "exact_human_approval_state_unknown")
                self.assertTrue(injected)
                self.assertIsNotNone(hidden_claim)
                started = json.loads(hidden_claim.read_text(encoding="utf-8"))
                self.assertEqual(started["status"], "started")
            self.assertEqual(outside.read_bytes(), foreign)


    def test_duplicate_archive_id_blocks_before_native_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            plan, _context = self.context(root)
            config = root / "archive.yml"
            config.write_text(
                config.read_text(encoding="utf-8")
                + f"\narchive_id: {plan['archive_id']}\n",
                encoding="utf-8",
            )
            command = [
                "zettel-objet-link",
                str(root),
                "--zettel-id",
                ZETTEL_ID,
                "--object-id",
                OBJECT_ID,
                "--role",
                ROLE,
                "--approve",
                "--expected-plan-sha256",
                str(plan["summary"]["plan_sha256"]),
                "--reviewed-by",
                REVIEWER,
                "--format",
                "json",
            ]

            with mock.patch.object(
                archive_cli,
                "_execute_zettel_objet_link_exact_human_approved_write",
            ) as workflow:
                code, stdout, stderr = self.run_cli(command)

            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            workflow.assert_not_called()
            payload = json.loads(stdout)
            self.assertEqual(payload["effects_state"], "none")
            self.assertEqual(
                payload["reason_codes"],
                ["zettel_objet_link_workflow_precondition_failed"],
            )
            self.assertFalse(payload["private_values_echoed"])
            self.assertFalse((root / "profiles").exists())


if __name__ == "__main__":
    unittest.main()
