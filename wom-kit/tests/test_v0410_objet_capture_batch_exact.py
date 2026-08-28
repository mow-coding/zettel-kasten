from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_services,
    completion_workflows,
    exact_human_approval,
    exact_operation_manifest,
    objet_capture_batch_exact,
    source_intake_batch_exact,
)
from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID,
    ExactHumanApprovalOperation,
)
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:v0410-batch-reviewer"
PRIVATE_BODY = b"PRIVATE_LETTER147_BATCH_BODY\n"


class _Native:
    def __init__(self, *, approved: bool) -> None:
        self.approved = approved
        self.calls = 0

    def show(self, **_kwargs: str) -> tuple[int, bool]:
        self.calls += 1
        return (APPROVE_BUTTON_ID, True) if self.approved else (2, False)


class _KeyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        self.assert_create(create_if_missing)
        self.calls += 1
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)

    @staticmethod
    def assert_create(value: bool) -> None:
        if value is not True:
            raise AssertionError("approval key must be requested explicitly")


class _ReadKeyProvider(_KeyProvider):
    @staticmethod
    def assert_create(value: bool) -> None:
        if value is not False:
            raise AssertionError("existing approval key must be read without creation")


class ObjetCaptureBatchExactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        # No sandbox marker and no persistent capture-enablement record: the
        # legacy batch preview is closed, while native exact approval may plan.
        self.root = self.workspace / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        archive_services.index_archive(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _snapshot(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }

    @staticmethod
    def _manifest_lines(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line)

    @staticmethod
    def _canonical_bytes(value: Any) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")

    @classmethod
    def _document_sha256(cls, value: Any) -> str:
        return "sha256:" + hashlib.sha256(cls._canonical_bytes(value)).hexdigest()

    @classmethod
    def _write_canonical_json(cls, path: Path, value: Any) -> None:
        path.write_bytes(cls._canonical_bytes(value) + b"\n")

    @staticmethod
    def _execution_hex(execution_sha256: str) -> str:
        return execution_sha256.removeprefix("sha256:")

    def _final_receipt_path(self, execution_sha256: str) -> Path:
        return (
            self.root
            / "receipts"
            / "ops"
            / "exact-operations"
            / (self._execution_hex(execution_sha256) + ".json")
        )

    def _checkpoint_path(self, execution_sha256: str) -> Path:
        return (
            self.root
            / "profiles"
            / "local"
            / "exact-operations"
            / "checkpoints"
            / (self._execution_hex(execution_sha256) + ".jsonl")
        )

    def _claim_path(self, final_receipt: dict[str, Any]) -> Path:
        authentication = final_receipt["result"]["completion_authentication"]
        approval_id = authentication["approval_reference"]["approval_id"]
        return (
            self.root
            / "profiles"
            / "local"
            / "exact-human-approvals"
            / "claims"
            / f"{approval_id}.json"
        )

    @classmethod
    def _refresh_unkeyed_final_receipt_hashes(
        cls,
        final_receipt: dict[str, Any],
    ) -> None:
        """Recompute every public/self hash but deliberately not the keyed MAC."""

        result = final_receipt["result"]
        authentication = result["completion_authentication"]
        payload = exact_operation_manifest.exact_operation_completion_authentication_payload(
            result
        )
        authentication["payload_sha256"] = (
            "sha256:" + hashlib.sha256(payload).hexdigest()
        )
        result_basis = dict(result)
        result_basis.pop("result_sha256", None)
        result["result_sha256"] = cls._document_sha256(result_basis)
        receipt_basis = dict(final_receipt)
        receipt_basis.pop("receipt_sha256", None)
        final_receipt["receipt_sha256"] = cls._document_sha256(receipt_basis)

    @classmethod
    def _refresh_checkpoint_chain_hashes(
        cls,
        rows: list[dict[str, Any]],
    ) -> None:
        previous: str | None = None
        for sequence, row in enumerate(rows):
            row["sequence"] = sequence
            row["previous_checkpoint_sha256"] = previous
            basis = dict(row)
            basis.pop("checkpoint_sha256", None)
            row["checkpoint_sha256"] = cls._document_sha256(basis)
            previous = row["checkpoint_sha256"]

    @staticmethod
    def _workflow(native: _Native, keys: _KeyProvider):
        def execute(root, context, writer):
            return _execute_exact_human_approved_write_core(
                root,
                context,
                writer,
                native=native,
                key_provider=keys,
            )

        return execute

    def _request(self, count: int, *, batch_id: str) -> tuple[Path, str]:
        items = []
        for index in range(count):
            relative = f"staging/incoming/{batch_id}-private-{index}.pdf"
            source = self.root / Path(relative)
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(PRIVATE_BODY + str(index).encode("ascii"))
            items.append(
                {
                    "item_id": f"{batch_id}-item-{index:02d}",
                    "local_path": relative,
                    "source_role": "primary_source",
                }
            )
        request = {
            "schema": source_intake_batch_exact.REQUEST_SCHEMA,
            "batch_id": batch_id,
            "items": items,
        }
        path = self.workspace / f"{batch_id}.source-intake.json"
        path.write_text(
            json.dumps(request, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            path,
        )
        self.assertTrue(plan.approveable, plan.public_document())
        native = _Native(approved=True)
        keys = _KeyProvider()
        with mock.patch.object(
            source_intake_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, keys),
        ):
            result = source_intake_batch_exact.execute_source_intake_batch(
                plan,
                expected_plan_sha256=plan.manifest.manifest_sha256,
                reviewer_claim=REVIEWER,
            )
        self.assertTrue(result["ok"], result)
        prepared = plan.prepared_capture_request
        self.assertIsNotNone(prepared)
        prepared_path = self.root.joinpath(*prepared.relative_path.split("/"))
        self.assertTrue(prepared_path.is_file())
        return prepared_path, str(result["execution_sha256"])

    def _plan(
        self,
        request: Path,
        execution_sha256: str,
        *,
        root: Path | None = None,
    ):
        return objet_capture_batch_exact.plan_objet_capture_batch(
            root or self.root,
            request,
            intake_execution_sha256=execution_sha256,
            claim_key_provider=_ReadKeyProvider(),
        )

    def _assert_intake_chain_rejected(
        self,
        request: Path,
        execution_sha256: str,
        *,
        root: Path | None = None,
    ) -> None:
        try:
            plan = self._plan(request, execution_sha256, root=root)
        except objet_capture_batch_exact.ObjetCaptureBatchExactError as exc:
            self.assertEqual(exc.code, "objet_capture_batch_intake_chain_invalid")
            return
        self.assertFalse(plan.approveable, plan.public_document())
        self.assertIn(
            "objet_capture_batch_intake_chain_invalid",
            plan.blockers,
        )

    def _assert_local_authentication_truth(self, document: dict[str, Any]) -> None:
        self.assertTrue(document["credential_material_used_for_local_authentication"])
        self.assertFalse(document["credential_values_echoed"])
        self.assertFalse(document["provider_calls_performed"])
        self.assertNotIn("credential_values_read", document)

    def test_one_and_three_item_plans_are_stable_on_unenabled_live_root(self) -> None:
        for count in (1, 3):
            with self.subTest(count=count):
                request, execution = self._request(
                    count,
                    batch_id=f"batch-{count}",
                )
                before = self._snapshot(self.root)
                legacy = completion_workflows.objet_capture_batch_plan(
                    self.root,
                    manifest_path=request,
                )
                first = self._plan(request, execution)
                second = self._plan(request, execution)
                self.assertFalse(legacy["ok"], legacy)
                self.assertTrue(first.approveable, first.public_document())
                self.assertEqual(first.batch_plan_sha256, second.batch_plan_sha256)
                self.assertEqual(
                    first.native_binding.plan_sha256,
                    second.native_binding.plan_sha256,
                )
                self.assertIs(
                    first.native_binding.operation,
                    ExactHumanApprovalOperation.objet_capture_batch,
                )
                self.assertIs(
                    objet_capture_batch_exact.approval_context(
                        first,
                        reviewer_claim=REVIEWER,
                    ).operation,
                    ExactHumanApprovalOperation.objet_capture_batch,
                )
                public = first.public_document()
                self.assertEqual(public["summary"]["item_count"], count)
                self.assertEqual(public["summary"]["ready_item_count"], count)
                self.assertTrue(public["source_intake_completion"]["verified"])
                self._assert_local_authentication_truth(public)
                self.assertEqual(self._snapshot(self.root), before)
                rendered = json.dumps(public)
                self.assertNotIn(str(self.root), rendered)
                self.assertNotIn(PRIVATE_BODY.decode().strip(), rendered)

    def test_handmade_or_copied_request_cannot_bypass_exact_intake_completion(self) -> None:
        request, execution = self._request(1, batch_id="unbound-copy")
        copied = self.workspace / "copied-request.json"
        copied.write_bytes(request.read_bytes())

        with self.assertRaises(objet_capture_batch_exact.ObjetCaptureBatchExactError) as raised:
            self._plan(copied, execution)

        self.assertEqual(
            raised.exception.code,
            "objet_capture_batch_intake_chain_invalid",
        )

    def test_receipt_raw_byte_or_staged_byte_drift_breaks_intake_chain(self) -> None:
        request, execution = self._request(1, batch_id="chain-drift")
        request_document = json.loads(request.read_text(encoding="utf-8"))
        receipt = self.root / Path(
            request_document["items"][0]["source_intake_receipt_path"]
        )
        receipt.write_bytes(receipt.read_bytes() + b" ")

        receipt_drift = self._plan(request, execution)
        self.assertFalse(receipt_drift.approveable)
        self.assertIn(
            "objet_capture_batch_intake_chain_invalid",
            receipt_drift.blockers,
        )

        request2, execution2 = self._request(1, batch_id="source-drift")
        request2_document = json.loads(request2.read_text(encoding="utf-8"))
        staged = self.root / Path(request2_document["items"][0]["staged_path"])
        original = staged.read_bytes()
        staged.write_bytes(bytes([original[0] ^ 1]) + original[1:])

        source_drift = self._plan(request2, execution2)
        self.assertFalse(source_drift.approveable)
        self.assertIn(
            "objet_capture_batch_intake_chain_invalid",
            source_drift.blockers,
        )

    def test_missing_exact_final_receipt_blocks_without_fallback_scan(self) -> None:
        request, execution = self._request(1, batch_id="missing-final")
        final = self._final_receipt_path(execution)
        final.unlink()

        with self.assertRaises(objet_capture_batch_exact.ObjetCaptureBatchExactError) as raised:
            self._plan(request, execution)

        self.assertEqual(
            raised.exception.code,
            "objet_capture_batch_intake_chain_invalid",
        )

    def test_self_consistent_unkeyed_final_receipt_forgery_is_rejected(self) -> None:
        request, execution = self._request(1, batch_id="forged-final")
        path = self._final_receipt_path(execution)
        final = json.loads(path.read_text(encoding="utf-8"))

        # Change a field that the downstream domain does not otherwise use,
        # then recompute every attacker-computable hash.  Only the terminal
        # claim MAC should distinguish this from the approved receipt.
        counts = final["result"]["operation_evidence"]["counts"]
        counts["warning_count"] += 1
        self._refresh_unkeyed_final_receipt_hashes(final)
        self._write_canonical_json(path, final)

        result_basis = dict(final["result"])
        supplied_result_sha = result_basis.pop("result_sha256")
        receipt_basis = dict(final)
        supplied_receipt_sha = receipt_basis.pop("receipt_sha256")
        self.assertEqual(supplied_result_sha, self._document_sha256(result_basis))
        self.assertEqual(supplied_receipt_sha, self._document_sha256(receipt_basis))
        self._assert_intake_chain_rejected(request, execution)

    def test_rehashed_checkpoint_jsonl_tamper_is_rejected(self) -> None:
        request, execution = self._request(1, batch_id="checkpoint-tamper")
        path = self._checkpoint_path(execution)
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        terminal = next(
            row for row in reversed(rows) if row["stage"] == "item_verified"
        )
        terminal["observed_sha256"] = "sha256:" + ("0" * 64)
        self._refresh_checkpoint_chain_hashes(rows)
        path.write_bytes(b"".join(self._canonical_bytes(row) + b"\n" for row in rows))

        # Prove this is not a trivial broken-chain test: every public
        # checkpoint hash and predecessor link is internally self-consistent.
        previous: str | None = None
        for row in rows:
            self.assertEqual(row["previous_checkpoint_sha256"], previous)
            basis = dict(row)
            supplied = basis.pop("checkpoint_sha256")
            self.assertEqual(supplied, self._document_sha256(basis))
            previous = supplied
        self._assert_intake_chain_rejected(request, execution)

    def test_claim_hmac_tamper_is_rejected(self) -> None:
        request, execution = self._request(1, batch_id="claim-hmac-tamper")
        final = json.loads(
            self._final_receipt_path(execution).read_text(encoding="utf-8")
        )
        path = self._claim_path(final)
        claim = json.loads(path.read_text(encoding="utf-8"))
        mac = claim["authentication"]["mac"]
        claim["authentication"]["mac"] = mac[:-1] + ("0" if mac[-1] != "0" else "1")
        self._write_canonical_json(path, claim)

        self._assert_intake_chain_rejected(request, execution)

    def test_authenticated_but_non_succeeded_claim_is_rejected(self) -> None:
        request, execution = self._request(1, batch_id="claim-not-succeeded")
        final = json.loads(
            self._final_receipt_path(execution).read_text(encoding="utf-8")
        )
        path = self._claim_path(final)
        claim = json.loads(path.read_text(encoding="utf-8"))
        claim["status"] = "failed"
        claim["failure_code"] = "simulated_failure"
        key = bytearray(range(32))
        try:
            claim["authentication"]["mac"] = exact_human_approval._claim_mac(
                claim,
                key,
            )
        finally:
            key[:] = b"\0" * len(key)
        self._write_canonical_json(path, claim)

        self._assert_intake_chain_rejected(request, execution)

    def test_copying_completion_evidence_to_another_archive_is_rejected(self) -> None:
        request, execution = self._request(1, batch_id="cross-archive-copy")
        copied_root = self.workspace / "other-archive"
        shutil.copytree(self.root, copied_root)
        archive_config = copied_root / "archive.yml"
        archive_config.write_text(
            archive_config.read_text(encoding="utf-8").replace(
                "archive_id: archive:personal:fake-life",
                "archive_id: archive:personal:other-life",
                1,
            ),
            encoding="utf-8",
        )
        copied_request = copied_root / request.relative_to(self.root)

        self._assert_intake_chain_rejected(
            copied_request,
            execution,
            root=copied_root,
        )

    def test_approval_reference_and_checkpoint_binding_mismatches_are_rejected(
        self,
    ) -> None:
        for mismatch in ("approval_id", "context_sha256", "checkpoint_binding"):
            with self.subTest(mismatch=mismatch):
                request, execution = self._request(
                    1,
                    batch_id=f"mismatch-{mismatch}",
                )
                final_path = self._final_receipt_path(execution)
                final = json.loads(final_path.read_text(encoding="utf-8"))
                reference = final["result"]["completion_authentication"][
                    "approval_reference"
                ]
                altered_reference = dict(reference)
                if mismatch == "approval_id":
                    altered_reference["approval_id"] = "approval_" + ("0" * 32)
                    final["result"]["completion_authentication"][
                        "approval_reference"
                    ] = altered_reference
                    self._refresh_unkeyed_final_receipt_hashes(final)
                    self._write_canonical_json(final_path, final)
                elif mismatch == "context_sha256":
                    altered_reference["context_sha256"] = "sha256:" + ("1" * 64)
                    final["result"]["completion_authentication"][
                        "approval_reference"
                    ] = altered_reference
                    self._refresh_unkeyed_final_receipt_hashes(final)
                    self._write_canonical_json(final_path, final)
                else:
                    altered_reference["approval_id"] = "approval_" + ("2" * 32)
                    altered_authority = (
                        exact_operation_manifest.ExactOperationApprovalAuthority.from_reference(
                            altered_reference
                        ).document()
                    )
                    checkpoint_path = self._checkpoint_path(execution)
                    rows = [
                        json.loads(line)
                        for line in checkpoint_path.read_text(
                            encoding="utf-8"
                        ).splitlines()
                        if line
                    ]
                    for row in rows:
                        row["approval"] = altered_authority
                    self._refresh_checkpoint_chain_hashes(rows)
                    checkpoint_path.write_bytes(
                        b"".join(
                            self._canonical_bytes(row) + b"\n" for row in rows
                        )
                    )

                self._assert_intake_chain_rejected(request, execution)

    def test_cancel_has_zero_domain_or_claim_writes(self) -> None:
        request, execution = self._request(1, batch_id="cancel")
        plan = self._plan(request, execution)
        before = self._snapshot(self.root)
        native = _Native(approved=False)
        keys = _KeyProvider()
        with mock.patch.object(
            objet_capture_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, keys),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError) as raised:
                objet_capture_batch_exact.execute_objet_capture_batch(
                    plan,
                    expected_plan_sha256=plan.batch_plan_sha256,
                    reviewer_claim=REVIEWER,
                )
        self.assertEqual(raised.exception.code, "exact_human_approval_cancelled")
        self.assertEqual(native.calls, 1)
        self.assertEqual(keys.calls, 0)
        self.assertEqual(self._snapshot(self.root), before)

    def test_capture_and_freshly_approved_replay_converge(self) -> None:
        request, execution = self._request(1, batch_id="replay")
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        native = _Native(approved=True)
        keys = _KeyProvider()
        with mock.patch.object(
            objet_capture_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, keys),
        ):
            first_plan = self._plan(request, execution)
            first = objet_capture_batch_exact.execute_objet_capture_batch(
                first_plan,
                expected_plan_sha256=first_plan.batch_plan_sha256,
                reviewer_claim=REVIEWER,
            )
            first_lines = self._manifest_lines(manifest)
            replay_plan = self._plan(request, execution)
            replay = objet_capture_batch_exact.execute_objet_capture_batch(
                replay_plan,
                expected_plan_sha256=replay_plan.batch_plan_sha256,
                reviewer_claim=REVIEWER,
            )
        self.assertTrue(first["ok"], first)
        self._assert_local_authentication_truth(first)
        self.assertEqual(first["items"][0]["terminal_state"], "captured")
        capture_receipt = self.root.joinpath(
            *first["summary"]["capture_receipt_path"].split("/")
        )
        receipt_document = json.loads(capture_receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            receipt_document["exact_human_approval"]["operation"],
            "objet_capture_batch",
        )
        self.assertTrue(replay["ok"], replay)
        self._assert_local_authentication_truth(replay)
        self.assertEqual(replay["items"][0]["terminal_state"], "already_present")
        self.assertEqual(self._manifest_lines(manifest), first_lines)
        self.assertEqual(native.calls, 2)
        self.assertEqual(keys.calls, 2)

    def test_partial_object_bytes_require_fresh_plan_and_reapproval_then_converge(self) -> None:
        request, execution = self._request(3, batch_id="partial-converge")
        initial = self._plan(request, execution)
        first_selection = initial.selection_document["items"][0]
        digest = first_selection["approved_object_id"].removeprefix("sha256:")
        staged = self.root / Path(first_selection["staged_path"])
        preserved = self.root / "objects" / "sha256" / digest[:2] / digest
        preserved.parent.mkdir(parents=True, exist_ok=True)
        preserved.write_bytes(staged.read_bytes())

        fresh = self._plan(request, execution)
        summary = fresh.public_document()["summary"]
        self.assertEqual(summary["would_repair_append"], 1)
        self.assertEqual(summary["would_capture"], 2)
        self.assertFalse(summary["same_claim_resume_supported"])
        self.assertFalse(summary["automatic_retry_allowed"])

        native = _Native(approved=True)
        keys = _KeyProvider()
        with mock.patch.object(
            objet_capture_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, keys),
        ):
            result = objet_capture_batch_exact.execute_objet_capture_batch(
                fresh,
                expected_plan_sha256=fresh.batch_plan_sha256,
                reviewer_claim=REVIEWER,
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["summary"]["terminal_item_count"], 3)
        self.assertEqual(native.calls, 1)
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        object_ids = [
            json.loads(line)["object_id"]
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        expected_ids = {
            item["approved_object_id"]
            for item in fresh.selection_document["items"]
        }
        self.assertEqual(
            {object_id: object_ids.count(object_id) for object_id in expected_ids},
            {object_id: 1 for object_id in expected_ids},
        )

    def test_request_drift_after_decision_blocks_before_capture(self) -> None:
        request, execution = self._request(1, batch_id="drift")
        plan = self._plan(request, execution)
        before_manifest = self._manifest_lines(
            self.root / "objects" / "manifests" / "files.jsonl"
        )
        native = _Native(approved=True)
        keys = _KeyProvider()

        def drifting_workflow(root, context, writer):
            @contextmanager
            def drift():
                document = json.loads(request.read_text(encoding="utf-8"))
                document["batch_id"] = "drifted-after-review"
                request.write_text(json.dumps(document), encoding="utf-8")
                yield None

            return _execute_exact_human_approved_write_core(
                root,
                context,
                writer,
                native=native,
                key_provider=keys,
                post_decision_boundary=drift,
            )

        with mock.patch.object(
            objet_capture_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=drifting_workflow,
        ):
            result = objet_capture_batch_exact.execute_objet_capture_batch(
                plan,
                expected_plan_sha256=plan.batch_plan_sha256,
                reviewer_claim=REVIEWER,
            )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["blockers"], ["objet_capture_batch_state_drifted"])
        self.assertEqual(result["items"][0]["terminal_state"], "blocked")
        self.assertEqual(
            self._manifest_lines(self.root / "objects" / "manifests" / "files.jsonl"),
            before_manifest,
        )

    def test_writer_exception_is_content_free_and_classifies_every_item(self) -> None:
        request, execution = self._request(3, batch_id="fault")
        plan = self._plan(request, execution)
        native = _Native(approved=True)
        keys = _KeyProvider()
        private_exception = "PRIVATE_WRITER_EXCEPTION_MUST_NOT_ECHO"
        with (
            mock.patch.object(
                objet_capture_batch_exact,
                "plan_objet_capture_batch",
                return_value=plan,
            ),
            mock.patch.object(
                objet_capture_batch_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, keys),
            ),
            mock.patch.object(
                archive_services,
                "objet_capture_apply",
                side_effect=RuntimeError(private_exception),
            ),
        ):
            result = objet_capture_batch_exact.execute_objet_capture_batch(
                plan,
                expected_plan_sha256=plan.batch_plan_sha256,
                reviewer_claim=REVIEWER,
            )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["state"], "outcome_unverified")
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(
            {item["terminal_state"] for item in result["items"]},
            {"outcome_unverified"},
        )
        self.assertNotIn(private_exception, json.dumps(result))

    def test_failure_document_is_truthful_about_uncertain_writes(self) -> None:
        uncertain = objet_capture_batch_exact.failure_document(
            "exact_human_approval_state_unknown"
        )
        self.assertTrue(uncertain["writes_may_have_occurred"])
        self.assertTrue(uncertain["outcome_unverified"])
        self.assertEqual(
            uncertain["safe_recovery_actions"],
            [
                "preserve_state",
                "fresh_dry_run_then_new_approval",
                "do_not_reuse_previous_approval",
            ],
        )
        self.assertEqual(len(uncertain["next_safe_actions"]), 3)
        blocked = objet_capture_batch_exact.failure_document(
            "objet_capture_batch_plan_blocked"
        )
        self.assertFalse(blocked["writes_may_have_occurred"])
        self.assertFalse(blocked["outcome_unverified"])
        for pre_writer_code in (
            "exact_human_approval_operation_failed",
            "exact_human_approval_writer_result_invalid",
        ):
            with self.subTest(pre_writer_code=pre_writer_code):
                pre_writer = objet_capture_batch_exact.failure_document(
                    pre_writer_code
                )
                self.assertFalse(pre_writer["writes_may_have_occurred"])
                self.assertFalse(pre_writer["outcome_unverified"])
                self.assertEqual(pre_writer["safe_recovery_actions"], [])
                self.assertEqual(pre_writer["next_safe_actions"], [])

    def test_cli_dry_run_and_approve_use_one_native_batch_decision(self) -> None:
        request, execution = self._request(3, batch_id="cli-batch")
        parser = archive_cli.build_parser()

        def run(values: list[str]) -> tuple[int, dict[str, Any], str]:
            args = parser.parse_args(values)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = args.func(args)
            return int(code), json.loads(stdout.getvalue()), stderr.getvalue()

        common = [
            "objet-capture-batch",
            str(self.root),
            "--source-intake-execution-sha256",
            execution,
            "--no-progress",
            "--format",
            "json",
        ]
        native = _Native(approved=True)
        keys = _KeyProvider()
        with (
            mock.patch(
                "wom_kit.exact_human_approval_workflow._production_key_provider",
                return_value=_ReadKeyProvider(),
            ),
            mock.patch.object(
                objet_capture_batch_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, keys),
            ),
        ):
            dry_code, dry, dry_stderr = run([*common, "--dry-run"])
            self.assertEqual(dry_code, 0, dry)
            self.assertEqual(dry_stderr, "")
            self.assertEqual(dry["summary"]["item_count"], 3)
            apply_code, applied, apply_stderr = run(
                [
                    *common,
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                    "--expected-plan-sha256",
                    dry["plan_sha256"],
                ]
            )
        self.assertEqual(apply_code, 0, applied)
        self.assertEqual(apply_stderr, "")
        self.assertEqual(native.calls, 1)
        self.assertEqual(applied["summary"]["terminal_item_count"], 3)

    def test_cli_reports_state_unknown_as_possible_partial_write(self) -> None:
        request, execution = self._request(1, batch_id="cli-uncertain")
        plan = self._plan(request, execution)
        parser = archive_cli.build_parser()
        args = parser.parse_args(
            [
                "objet-capture-batch", str(self.root),
                "--source-intake-execution-sha256", execution,
                "--approve", "--reviewed-by", REVIEWER,
                "--expected-plan-sha256", plan.batch_plan_sha256,
                "--no-progress", "--format", "json",
            ]
        )
        with (
            mock.patch.object(
                objet_capture_batch_exact,
                "plan_objet_capture_batch",
                return_value=plan,
            ),
            mock.patch.object(
                objet_capture_batch_exact,
                "execute_objet_capture_batch",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_state_unknown"
                ),
            ),
            redirect_stdout(stdout := io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(args.func(args), 1)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["writes_may_have_occurred"])
        self.assertTrue(result["outcome_unverified"])
        self.assertEqual(
            result["safe_recovery_actions"],
            [
                "preserve_state",
                "fresh_dry_run_then_new_approval",
                "do_not_reuse_previous_approval",
            ],
        )
        text_args = parser.parse_args(
            [
                "objet-capture-batch",
                str(self.root),
                "--source-intake-execution-sha256",
                execution,
                "--approve",
                "--reviewed-by",
                REVIEWER,
                "--expected-plan-sha256",
                str(plan.batch_plan_sha256),
                "--no-progress",
                "--format",
                "text",
            ]
        )
        with (
            mock.patch.object(
                objet_capture_batch_exact,
                "plan_objet_capture_batch",
                return_value=plan,
            ),
            mock.patch.object(
                objet_capture_batch_exact,
                "execute_objet_capture_batch",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_state_unknown"
                ),
            ),
            redirect_stdout(text_stdout := io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(text_args.func(text_args), 1)
        text_output = text_stdout.getvalue()
        self.assertIn("NEXT: Preserve the current archive state", text_output)
        self.assertIn("fresh dry-run", text_output)
        self.assertIn("Do not reuse the previous capture approval", text_output)

    def test_cli_reports_pre_writer_operation_failure_as_zero_write(self) -> None:
        request, execution = self._request(1, batch_id="cli-pre-writer")
        plan = self._plan(request, execution)
        parser = archive_cli.build_parser()
        args = parser.parse_args(
            [
                "objet-capture-batch", str(self.root),
                "--source-intake-execution-sha256", execution,
                "--approve", "--reviewed-by", REVIEWER,
                "--expected-plan-sha256", plan.batch_plan_sha256,
                "--no-progress", "--format", "json",
            ]
        )
        with (
            mock.patch.object(
                objet_capture_batch_exact,
                "plan_objet_capture_batch",
                return_value=plan,
            ),
            mock.patch.object(
                objet_capture_batch_exact,
                "execute_objet_capture_batch",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_operation_failed"
                ),
            ),
            redirect_stdout(stdout := io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(args.func(args), 1)
        result = json.loads(stdout.getvalue())
        self.assertFalse(result["writes_may_have_occurred"])
        self.assertFalse(result["outcome_unverified"])
        self.assertEqual(result["safe_recovery_actions"], [])
        self.assertEqual(result["next_safe_actions"], [])

        text_args = parser.parse_args(
            [
                "objet-capture-batch", str(self.root),
                "--source-intake-execution-sha256", execution,
                "--approve", "--reviewed-by", REVIEWER,
                "--expected-plan-sha256", plan.batch_plan_sha256,
                "--no-progress", "--format", "text",
            ]
        )
        with (
            mock.patch.object(
                objet_capture_batch_exact,
                "plan_objet_capture_batch",
                return_value=plan,
            ),
            mock.patch.object(
                objet_capture_batch_exact,
                "execute_objet_capture_batch",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_operation_failed"
                ),
            ),
            redirect_stdout(text_stdout := io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(text_args.func(text_args), 1)
        text_output = text_stdout.getvalue()
        self.assertIn("writes may have occurred: no", text_output)
        self.assertIn("outcome unverified: no", text_output)
        self.assertIn("BLOCKED: objet_capture_batch_write_failed", text_output)
        self.assertNotIn("NEXT:", text_output)

    def test_successful_three_item_text_output_reports_actual_counts(self) -> None:
        _request, execution = self._request(3, batch_id="cli-text")
        plan = self._plan(_request, execution)
        parser = archive_cli.build_parser()
        args = parser.parse_args(
            [
                "objet-capture-batch",
                str(self.root),
                "--source-intake-execution-sha256",
                execution,
                "--approve",
                "--reviewed-by",
                REVIEWER,
                "--expected-plan-sha256",
                str(plan.batch_plan_sha256),
                "--no-progress",
                "--format",
                "text",
            ]
        )
        native = _Native(approved=True)
        keys = _KeyProvider()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch(
                "wom_kit.exact_human_approval_workflow._production_key_provider",
                return_value=_ReadKeyProvider(),
            ),
            mock.patch.object(
                objet_capture_batch_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, keys),
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = args.func(args)

        output = stdout.getvalue()
        self.assertEqual(code, 0, output)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("- batch: cli-text", output)
        self.assertIn("- items: 3", output)
        self.assertIn(
            "- terminal captured/already present/partial/blocked/"
            "outcome unverified: 3/0/0/0/0",
            output,
        )
        self.assertIn(
            "- local capture written/repaired/rematerialized/skipped/blocked: "
            "3/0/0/0/0",
            output,
        )
        self.assertNotIn("unknown", output)
        self.assertEqual(native.calls, 1)


if __name__ == "__main__":
    unittest.main()
