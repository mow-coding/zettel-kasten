from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import human_artifact_registry as registry
from wom_kit.exact_human_approval import (
    _ClaimedExactHumanApproval as ClaimedExactHumanApproval,
    ExactHumanApprovalError,
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
)


AUTHENTICATION_KEY = bytes(range(32))
REVIEWER_CLAIM = "person:local-reviewer"


class HumanArtifactRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.archive = self.base / "archive"
        self.archive.mkdir()
        (self.archive / "archive.yml").write_text(
            "archive_id: archive:test-human-artifacts\n",
            encoding="utf-8",
        )
        (self.archive / ".gitignore").write_text(
            "profiles/local/\n",
            encoding="utf-8",
        )
        self.claims: list[ClaimedExactHumanApproval] = []
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "human-artifact-registry-v0.1.schema.json"
        )
        self.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(self.schema)
        self.validator = Draft202012Validator(self.schema)

    def tearDown(self) -> None:
        for claim in self.claims:
            claim.close()
        self.temporary.cleanup()

    @staticmethod
    def _suffix(value: int) -> str:
        return f"{value:032x}"

    def _claim(
        self,
        context,
        *,
        seed: int,
    ) -> ClaimedExactHumanApproval:
        decision = ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
        )
        claim = claim_exact_human_approval(
            self.archive,
            context,
            decision,
            AUTHENTICATION_KEY,
            random_hex=lambda _size: self._suffix(seed),
        )
        self.claims.append(claim)
        return claim

    def _register_project_root(
        self,
        project: Path,
        *,
        root_kind: str = "external_project",
        approval_seed: int = 1,
        root_seed: int = 101,
    ) -> dict:
        plan = registry.plan_project_root_registration(
            self.archive,
            project,
            root_kind=root_kind,
        )
        context = registry.project_root_registration_approval_context(
            self.archive,
            project,
            reviewer_claim=REVIEWER_CLAIM,
            root_kind=root_kind,
        )
        self.assertEqual(
            context.operation,
            ExactHumanApprovalOperation.human_artifact_lifecycle,
        )
        claim = self._claim(context, seed=approval_seed)
        result = registry.register_project_root(
            self.archive,
            project,
            expected_plan_sha256=plan["plan_sha256"],
            approval_claim=claim,
            reviewer_claim=REVIEWER_CLAIM,
            root_kind=root_kind,
            random_hex=lambda _size: self._suffix(root_seed),
            random_bytes=lambda _size: bytes([23]) * 32,
        )
        self.assertEqual(claim.status, "started")
        claim.finalize_succeeded()
        return result

    def _transition(
        self,
        artifact_id: str,
        *,
        target_state: str,
        body: bytes,
        approval_seed: int,
        receipt_seed: int,
        related_refs: list[dict[str, str]] | None = None,
    ) -> dict:
        content_sha256 = "sha256:" + hashlib.sha256(body).hexdigest()
        plan = registry.plan_artifact_transition(
            self.archive,
            artifact_id,
            target_state=target_state,
            content_sha256=content_sha256,
            size_bytes=len(body),
            related_refs=related_refs,
        )
        context = registry.artifact_transition_approval_context(
            self.archive,
            artifact_id,
            target_state=target_state,
            content_sha256=content_sha256,
            size_bytes=len(body),
            reviewer_claim=REVIEWER_CLAIM,
            related_refs=related_refs,
        )
        claim = self._claim(context, seed=approval_seed)
        result = registry.write_artifact_transition(
            self.archive,
            artifact_id,
            target_state=target_state,
            content_sha256=content_sha256,
            size_bytes=len(body),
            expected_plan_sha256=plan["plan_sha256"],
            expected_current_state_sha256=plan[
                "expected_current_state_sha256"
            ],
            approval_claim=claim,
            reviewer_claim=REVIEWER_CLAIM,
            related_refs=related_refs,
            random_hex=lambda _size: self._suffix(receipt_seed),
            random_bytes=lambda _size: bytes([23]) * 32,
        )
        self.assertEqual(claim.status, "started")
        claim.finalize_succeeded()
        return result

    def _registry_json_documents(self) -> list[dict]:
        root = self.archive / registry.REGISTRY_RELATIVE_ROOT
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(root.rglob("*.json"))
        ]

    def test_approved_external_root_is_private_and_schema_valid(self) -> None:
        project = self.base / "PRIVATE-PROJECT-ROOT"
        project.mkdir()
        scratch = project / ".wom-scratch"
        scratch.mkdir()
        artifact = scratch / "PRIVATE-LETTER137-ARTIFACT.md"
        artifact.write_text("PRIVATE BODY MUST NEVER ECHO", encoding="utf-8")
        managed_scratch = self.archive / "workbench" / "ai-scratch"
        managed_scratch.mkdir(parents=True)
        managed_artifact = managed_scratch / "PRIVATE-MANAGED-ARTIFACT.md"
        managed_artifact.write_text(
            "PRIVATE MANAGED BODY MUST NEVER ECHO",
            encoding="utf-8",
        )

        plan = registry.plan_project_root_registration(self.archive, project)
        rendered_plan = json.dumps(plan)
        self.assertNotIn(str(project), rendered_plan)
        self.assertNotIn("PRIVATE-PROJECT-ROOT", rendered_plan)

        registered = self._register_project_root(project)
        self.assertTrue(registered["exact_human_approval_claim_reauthenticated"])
        self.assertFalse(registered["exact_human_approval_claim_finalized"])
        self.assertEqual(
            registered["exact_human_approval_claim_finalization_owner"],
            "approval_workflow",
        )
        artifact_keys = {
            os.path.normcase(os.path.abspath(artifact)),
            os.path.normcase(os.path.abspath(managed_artifact)),
        }
        original_os_open = os.open

        def reject_artifact_open(path, *args, **kwargs):
            candidate = os.path.normcase(os.path.abspath(os.fspath(path)))
            if candidate in artifact_keys:
                raise AssertionError("artifact body was opened")
            return original_os_open(path, *args, **kwargs)

        with mock.patch.object(
            registry.os,
            "open",
            side_effect=reject_artifact_open,
        ):
            scan = registry.scan_human_artifacts(self.archive)
        rendered = json.dumps({"registered": registered, "scan": scan})

        self.assertEqual(scan["registered_root_count"], 1)
        self.assertEqual(scan["artifact_count"], 2)
        self.assertEqual(scan["new_unclassified_count"], 2)
        self.assertFalse(scan["closeout_complete"])
        self.assertEqual(
            scan["registry_writer_role"], "actual_local_registry_writer"
        )
        self.assertEqual(
            scan["human_artifact_store_adapter_role"],
            "read_only_future_contract",
        )
        self.assertNotIn(str(project), rendered)
        self.assertNotIn("PRIVATE-PROJECT-ROOT", rendered)
        self.assertNotIn("PRIVATE-LETTER137-ARTIFACT.md", rendered)
        self.assertNotIn("PRIVATE BODY MUST NEVER ECHO", rendered)
        self.assertNotIn("PRIVATE-MANAGED-ARTIFACT.md", rendered)
        self.assertNotIn("PRIVATE MANAGED BODY MUST NEVER ECHO", rendered)
        managed_summary = next(
            value
            for value in scan["root_summaries"]
            if value["root_id"] == "archive_workbench_scratch"
        )
        self.assertTrue(managed_summary["coverage_complete"])
        self.assertEqual(managed_summary["file_count"], 1)

        root_documents = [
            item
            for item in self._registry_json_documents()
            if item.get("schema_version") == registry.ROOT_SCHEMA_VERSION
        ]
        self.assertEqual(len(root_documents), 1)
        self.assertEqual(root_documents[0]["canonical_path"], str(project.resolve()))
        for document in self._registry_json_documents():
            self.validator.validate(document)

        with self.assertRaises(registry.HumanArtifactRegistryError) as duplicate:
            registry.plan_project_root_registration(self.archive, project)
        self.assertEqual(
            duplicate.exception.code,
            "human_artifact_external_root_already_registered",
        )

    def test_approved_delivery_root_is_scanned_directly_and_blocks_closeout(
        self,
    ) -> None:
        delivery = self.base / "PRIVATE-DELIVERY-ROOT"
        delivery.mkdir()
        artifact = delivery / "PRIVATE-DELIVERED-REPORT.html"
        artifact.write_text(
            "PRIVATE DELIVERY BODY MUST NEVER ECHO",
            encoding="utf-8",
        )

        plan = registry.plan_project_root_registration(
            self.archive,
            delivery,
            root_kind="external_delivery",
        )
        self.assertEqual(plan["registered_root_kind"], "external_delivery")
        self.assertEqual(plan["scan_scope"], "registered_delivery_root")
        self.assertNotIn(str(delivery), json.dumps(plan))

        registered = self._register_project_root(
            delivery,
            root_kind="external_delivery",
        )
        self.assertEqual(
            registered["registered_root_kind"],
            "external_delivery",
        )
        self.assertEqual(registered["scan_scope"], "registered_delivery_root")

        original_os_open = os.open

        def reject_artifact_open(path, *args, **kwargs):
            if os.path.normcase(os.path.abspath(os.fspath(path))) == os.path.normcase(
                os.path.abspath(artifact)
            ):
                raise AssertionError("delivery artifact body was opened")
            return original_os_open(path, *args, **kwargs)

        with mock.patch.object(
            registry.os,
            "open",
            side_effect=reject_artifact_open,
        ):
            scan = registry.scan_human_artifacts(self.archive)

        rendered = json.dumps(scan)
        self.assertEqual(scan["registered_root_count"], 1)
        self.assertEqual(scan["artifact_count"], 1)
        self.assertEqual(scan["unresolved_artifact_count"], 1)
        self.assertFalse(scan["closeout_complete"])
        delivery_summary = next(
            item
            for item in scan["root_summaries"]
            if item["root_id"] == registered["root_id"]
        )
        self.assertEqual(delivery_summary["scan_scope"], "registered_delivery_root")
        self.assertEqual(delivery_summary["file_count"], 1)
        self.assertNotIn(str(delivery), rendered)
        self.assertNotIn("PRIVATE-DELIVERY-ROOT", rendered)
        self.assertNotIn("PRIVATE-DELIVERED-REPORT.html", rendered)
        self.assertNotIn("PRIVATE DELIVERY BODY MUST NEVER ECHO", rendered)

        root_documents = [
            item
            for item in self._registry_json_documents()
            if item.get("schema_version") == registry.ROOT_SCHEMA_VERSION
        ]
        self.assertEqual(root_documents[0]["root_kind"], "external_delivery")
        self.assertEqual(root_documents[0]["scan_relative_root"], ".")
        for document in self._registry_json_documents():
            self.validator.validate(document)

        with self.assertRaises(registry.HumanArtifactRegistryError) as unsafe:
            registry.plan_project_root_registration(
                self.archive,
                delivery,
                root_kind="unknown",
            )
        self.assertEqual(unsafe.exception.code, "human_artifact_external_root_unsafe")

    def test_registry_requires_ignored_local_boundary_and_claim_object(self) -> None:
        project = self.base / "project"
        project.mkdir()
        (self.archive / ".gitignore").write_text("tmp/\n", encoding="utf-8")

        with self.assertRaises(registry.HumanArtifactRegistryError) as ignored:
            registry.plan_project_root_registration(self.archive, project)
        self.assertEqual(
            ignored.exception.code,
            "human_artifact_private_registry_not_ignored",
        )
        self.assertFalse((self.archive / "profiles").exists())

        (self.archive / ".gitignore").write_text(
            "profiles/local/\n", encoding="utf-8"
        )
        plan = registry.plan_project_root_registration(self.archive, project)
        with self.assertRaises(registry.HumanArtifactRegistryError) as approval:
            registry.register_project_root(
                self.archive,
                project,
                expected_plan_sha256=plan["plan_sha256"],
                approval_claim={"one_use": True},  # type: ignore[arg-type]
                reviewer_claim=REVIEWER_CLAIM,
            )
        self.assertEqual(
            approval.exception.code,
            "human_artifact_exact_approval_reference_invalid",
        )
        self.assertFalse((self.archive / "profiles").exists())

    def test_lifecycle_versions_and_closeout_gate(self) -> None:
        scratch = self.archive / ".wom-scratch"
        scratch.mkdir()
        artifact = scratch / "PRIVATE-LIFECYCLE.md"
        first_body = b"first reviewed body"
        artifact.write_bytes(first_body)
        initial = registry.scan_human_artifacts(self.archive)
        artifact_id = initial["items"][0]["artifact_id"]

        self.assertEqual(
            registry.LIFECYCLE_STATES,
            {
                "working",
                "review_requested",
                "reviewed_current",
                "superseded",
                "preserved_as_objet",
                "distilled_to_zet",
                "discarded_with_receipt",
            },
        )
        self.assertFalse(initial["closeout_complete"])

        working = self._transition(
            artifact_id,
            target_state="working",
            body=first_body,
            approval_seed=10,
            receipt_seed=110,
        )
        self.assertFalse(working["automatic_deletion_performed"])
        self.assertFalse(registry.scan_human_artifacts(self.archive)["closeout_complete"])

        self._transition(
            artifact_id,
            target_state="review_requested",
            body=first_body,
            approval_seed=11,
            receipt_seed=111,
        )
        self.assertFalse(registry.scan_human_artifacts(self.archive)["closeout_complete"])

        reviewed = self._transition(
            artifact_id,
            target_state="reviewed_current",
            body=first_body,
            approval_seed=12,
            receipt_seed=112,
        )
        self.assertEqual(reviewed["version"]["relationship"], "same_version")
        self.assertTrue(registry.scan_human_artifacts(self.archive)["closeout_complete"])

        second_body = b"second reviewed version with different size"
        artifact.write_bytes(second_body)
        changed = registry.scan_human_artifacts(self.archive)
        self.assertFalse(changed["closeout_complete"])
        self.assertEqual(changed["items"][0]["lifecycle_state"], "unclassified")
        self.assertEqual(
            changed["items"][0]["version_relationship"],
            "changed_since_last_transition",
        )

        preserved = self._transition(
            artifact_id,
            target_state="preserved_as_objet",
            body=second_body,
            approval_seed=13,
            receipt_seed=113,
            related_refs=[{"kind": "object_id", "ref": "sha256:" + "a" * 64}],
        )
        self.assertEqual(preserved["version"]["relationship"], "supersedes")
        self.assertTrue(artifact.is_file())
        self.assertTrue(registry.scan_human_artifacts(self.archive)["closeout_complete"])

        for document in self._registry_json_documents():
            self.validator.validate(document)

    def test_discard_receipt_never_deletes_and_refs_reject_paths(self) -> None:
        scratch = self.archive / ".wom-scratch"
        scratch.mkdir()
        artifact = scratch / "PRIVATE-DISCARD.md"
        body = b"reviewed discard candidate"
        artifact.write_bytes(body)
        item = registry.scan_human_artifacts(self.archive)["items"][0]
        content_sha256 = "sha256:" + hashlib.sha256(body).hexdigest()

        with self.assertRaises(registry.HumanArtifactRegistryError) as unsafe_ref:
            registry.plan_artifact_transition(
                self.archive,
                item["artifact_id"],
                target_state="distilled_to_zet",
                content_sha256=content_sha256,
                size_bytes=len(body),
                related_refs=[{"kind": "object_id", "ref": "C:/PRIVATE/path"}],
            )
        self.assertEqual(
            unsafe_ref.exception.code,
            "human_artifact_related_ref_invalid",
        )
        self.assertNotIn("PRIVATE", str(unsafe_ref.exception))

        for target_state in ("preserved_as_objet", "distilled_to_zet"):
            with self.subTest(target_state=target_state):
                with self.assertRaises(
                    registry.HumanArtifactRegistryError
                ) as missing_ref:
                    registry.plan_artifact_transition(
                        self.archive,
                        item["artifact_id"],
                        target_state=target_state,
                        content_sha256=content_sha256,
                        size_bytes=len(body),
                    )
                self.assertEqual(
                    missing_ref.exception.code,
                    "human_artifact_related_ref_invalid",
                )

        result = self._transition(
            item["artifact_id"],
            target_state="discarded_with_receipt",
            body=body,
            approval_seed=20,
            receipt_seed=120,
        )
        self.assertTrue(artifact.is_file())
        self.assertFalse(result["automatic_deletion_performed"])
        self.assertFalse(result["content_sha256_verified_by_registry"])
        scan = registry.scan_human_artifacts(self.archive)
        self.assertTrue(scan["closeout_complete"])
        self.assertFalse(scan["automatic_deletion_performed"])

    def test_superseded_and_distilled_states_have_safe_destinations(self) -> None:
        scratch = self.archive / ".wom-scratch"
        scratch.mkdir()
        superseded_artifact = scratch / "PRIVATE-SUPERSEDED.md"
        superseded_body = b"superseded source"
        superseded_artifact.write_bytes(superseded_body)
        superseded_id = registry.scan_human_artifacts(self.archive)["items"][0][
            "artifact_id"
        ]
        working = self._transition(
            superseded_id,
            target_state="working",
            body=superseded_body,
            approval_seed=70,
            receipt_seed=170,
        )
        superseded = self._transition(
            superseded_id,
            target_state="superseded",
            body=superseded_body,
            approval_seed=71,
            receipt_seed=171,
            related_refs=[
                {
                    "kind": "artifact_version_id",
                    "ref": "har_version_" + "b" * 32,
                }
            ],
        )
        self.assertEqual(working["to_state"], "working")
        self.assertEqual(superseded["to_state"], "superseded")

        distilled_artifact = scratch / "PRIVATE-DISTILLED.md"
        distilled_body = b"distilled source"
        distilled_artifact.write_bytes(distilled_body)
        distilled_id = next(
            item["artifact_id"]
            for item in registry.scan_human_artifacts(self.archive)["items"]
            if item["lifecycle_state"] == "unclassified"
        )
        distilled = self._transition(
            distilled_id,
            target_state="distilled_to_zet",
            body=distilled_body,
            approval_seed=72,
            receipt_seed=172,
            related_refs=[{"kind": "zet_id", "ref": "zet_safe_target"}],
        )
        self.assertEqual(distilled["to_state"], "distilled_to_zet")
        self.assertTrue(superseded_artifact.is_file())
        self.assertTrue(distilled_artifact.is_file())
        self.assertTrue(registry.scan_human_artifacts(self.archive)["closeout_complete"])

    def test_current_state_compare_and_exact_claim_replay_fail_closed(self) -> None:
        scratch = self.archive / ".wom-scratch"
        scratch.mkdir()
        artifact = scratch / "PRIVATE-REPLAY.md"
        body = b"one-use approval body"
        artifact.write_bytes(body)
        artifact_id = registry.scan_human_artifacts(self.archive)["items"][0][
            "artifact_id"
        ]
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
        plan = registry.plan_artifact_transition(
            self.archive,
            artifact_id,
            target_state="working",
            content_sha256=digest,
            size_bytes=len(body),
        )
        context = registry.artifact_transition_approval_context(
            self.archive,
            artifact_id,
            target_state="working",
            content_sha256=digest,
            size_bytes=len(body),
            reviewer_claim=REVIEWER_CLAIM,
        )
        claim = self._claim(context, seed=30)

        with self.assertRaises(registry.HumanArtifactRegistryError) as stale:
            registry.write_artifact_transition(
                self.archive,
                artifact_id,
                target_state="working",
                content_sha256=digest,
                size_bytes=len(body),
                expected_plan_sha256=plan["plan_sha256"],
                expected_current_state_sha256="sha256:" + "f" * 64,
                approval_claim=claim,
                reviewer_claim=REVIEWER_CLAIM,
            )
        self.assertEqual(
            stale.exception.code,
            "human_artifact_current_state_mismatch",
        )
        self.assertEqual(claim.status, "started")

        result = registry.write_artifact_transition(
            self.archive,
            artifact_id,
            target_state="working",
            content_sha256=digest,
            size_bytes=len(body),
            expected_plan_sha256=plan["plan_sha256"],
            expected_current_state_sha256=plan["expected_current_state_sha256"],
            approval_claim=claim,
            reviewer_claim=REVIEWER_CLAIM,
            random_hex=lambda _size: self._suffix(130),
            random_bytes=lambda _size: bytes([23]) * 32,
        )
        self.assertTrue(result["exact_human_approval_claim_reauthenticated"])
        self.assertEqual(claim.status, "started")
        claim.finalize_succeeded()
        self.assertEqual(claim.status, "succeeded")

        next_plan = registry.plan_artifact_transition(
            self.archive,
            artifact_id,
            target_state="review_requested",
            content_sha256=digest,
            size_bytes=len(body),
        )
        with self.assertRaises(ExactHumanApprovalError):
            registry.write_artifact_transition(
                self.archive,
                artifact_id,
                target_state="review_requested",
                content_sha256=digest,
                size_bytes=len(body),
                expected_plan_sha256=next_plan["plan_sha256"],
                expected_current_state_sha256=next_plan[
                    "expected_current_state_sha256"
                ],
                approval_claim=claim,
                reviewer_claim=REVIEWER_CLAIM,
            )
        receipt_root = (
            self.archive
            / registry.REGISTRY_RELATIVE_ROOT
            / registry.RECEIPTS_DIRECTORY
            / artifact_id
        )
        self.assertEqual(len(list(receipt_root.glob("*.json"))), 1)

    def test_concurrent_same_state_has_one_append_only_winner(self) -> None:
        scratch = self.archive / ".wom-scratch"
        scratch.mkdir()
        artifact = scratch / "PRIVATE-CONCURRENT.md"
        body = b"concurrent state body"
        artifact.write_bytes(body)
        artifact_id = registry.scan_human_artifacts(self.archive)["items"][0][
            "artifact_id"
        ]
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
        plan = registry.plan_artifact_transition(
            self.archive,
            artifact_id,
            target_state="working",
            content_sha256=digest,
            size_bytes=len(body),
        )
        context = registry.artifact_transition_approval_context(
            self.archive,
            artifact_id,
            target_state="working",
            content_sha256=digest,
            size_bytes=len(body),
            reviewer_claim=REVIEWER_CLAIM,
        )
        claims = [self._claim(context, seed=40), self._claim(context, seed=41)]
        barrier = threading.Barrier(2)
        counter_lock = threading.Lock()
        call_count = 0
        original_check = registry._artifact_observation_still_matches

        def gated_check(state):
            nonlocal call_count
            result = original_check(state)
            with counter_lock:
                call_count += 1
                ordinal = call_count
            if ordinal <= 2:
                barrier.wait(timeout=5)
            return result

        def worker(index: int):
            try:
                result = registry.write_artifact_transition(
                    self.archive,
                    artifact_id,
                    target_state="working",
                    content_sha256=digest,
                    size_bytes=len(body),
                    expected_plan_sha256=plan["plan_sha256"],
                    expected_current_state_sha256=plan[
                        "expected_current_state_sha256"
                    ],
                    approval_claim=claims[index],
                    reviewer_claim=REVIEWER_CLAIM,
                    random_hex=lambda _size: self._suffix(140 + index),
                    random_bytes=lambda _size: bytes([23]) * 32,
                )
                claims[index].finalize_succeeded()
                return result
            except BaseException as exc:
                return exc

        with mock.patch.object(
            registry,
            "_artifact_observation_still_matches",
            side_effect=gated_check,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(worker, (0, 1)))

        successes = [item for item in outcomes if isinstance(item, dict)]
        failures = [item for item in outcomes if isinstance(item, BaseException)]
        self.assertEqual(len(successes), 1, outcomes)
        self.assertEqual(len(failures), 1, outcomes)
        self.assertIsInstance(failures[0], registry.HumanArtifactRegistryError)
        self.assertEqual(
            failures[0].code,
            "human_artifact_transition_conflict",
        )
        self.assertEqual(
            sorted(claim.status for claim in claims),
            ["started", "succeeded"],
        )
        receipt_root = (
            self.archive
            / registry.REGISTRY_RELATIVE_ROOT
            / registry.RECEIPTS_DIRECTORY
            / artifact_id
        )
        self.assertEqual(len(list(receipt_root.glob("*.json"))), 1)

    def test_tamper_and_root_identity_drift_fail_without_private_echo(self) -> None:
        project = self.base / "PRIVATE-DRIFT-ROOT"
        project.mkdir()
        scratch = project / ".wom-scratch"
        scratch.mkdir()
        artifact = scratch / "PRIVATE-DRIFT-ARTIFACT.md"
        body = b"drift body"
        artifact.write_bytes(body)
        registered = self._register_project_root(
            project,
            approval_seed=50,
            root_seed=150,
        )
        item = registry.scan_human_artifacts(self.archive)["items"][0]
        self._transition(
            item["artifact_id"],
            target_state="working",
            body=body,
            approval_seed=51,
            receipt_seed=151,
        )

        receipt_root = (
            self.archive
            / registry.REGISTRY_RELATIVE_ROOT
            / registry.RECEIPTS_DIRECTORY
            / item["artifact_id"]
        )
        receipt_path = next(receipt_root.glob("*.json"))
        original_receipt_raw = receipt_path.read_bytes()
        receipt = json.loads(original_receipt_raw.decode("utf-8"))
        receipt["to_state"] = "reviewed_current"
        receipt_path.write_bytes(
            (
                json.dumps(receipt, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")
        )
        with self.assertRaises(registry.HumanArtifactRegistryError) as tampered:
            registry.scan_human_artifacts(self.archive)
        self.assertIn(
            tampered.exception.code,
            {
                "human_artifact_transition_receipt_invalid",
                "human_artifact_registry_authentication_invalid",
            },
        )
        self.assertNotIn("PRIVATE", str(tampered.exception))

        # Restore the exact authenticated receipt before testing root drift.
        receipt_path.write_bytes(original_receipt_raw)
        moved = self.base / "moved-private-root"
        project.rename(moved)
        project.mkdir()
        replacement = project / ".wom-scratch"
        replacement.mkdir()
        (replacement / "PRIVATE-REPLACEMENT.md").write_text(
            "PRIVATE REPLACEMENT BODY",
            encoding="utf-8",
        )
        drifted = registry.scan_human_artifacts(self.archive)
        rendered = json.dumps(drifted)

        root_summary = next(
            value
            for value in drifted["root_summaries"]
            if value["root_id"] == registered["root_id"]
        )
        self.assertFalse(root_summary["coverage_complete"])
        self.assertEqual(root_summary["entries_seen"], 0)
        self.assertEqual(
            root_summary["reason_codes"],
            ["registered_root_identity_drift"],
        )
        self.assertFalse(drifted["closeout_complete"])
        self.assertNotIn(str(project), rendered)
        self.assertNotIn("PRIVATE-REPLACEMENT.md", rendered)
        self.assertNotIn("PRIVATE REPLACEMENT BODY", rendered)

    def test_reparse_root_fails_closed_before_registration_and_scan(self) -> None:
        project = self.base / "PRIVATE-REPARSE-ROOT"
        project.mkdir()
        scratch = project / ".wom-scratch"
        scratch.mkdir()
        (scratch / "PRIVATE-REPARSE-ARTIFACT.md").write_text(
            "PRIVATE REPARSE BODY",
            encoding="utf-8",
        )
        project_key = os.path.normcase(os.path.abspath(project))
        original_lstat = os.lstat

        class ReparseStat:
            def __init__(self, value):
                self._value = value
                self.st_file_attributes = (
                    getattr(value, "st_file_attributes", 0)
                    | registry.REPARSE_FLAG
                )

            def __getattr__(self, name):
                return getattr(self._value, name)

        def mark_project_reparse(path, *args, **kwargs):
            value = original_lstat(path, *args, **kwargs)
            candidate = os.path.normcase(os.path.abspath(os.fspath(path)))
            try:
                same_project = os.path.samefile(path, project)
            except OSError:
                same_project = candidate == project_key
            return ReparseStat(value) if same_project else value

        with mock.patch.object(
            registry.os,
            "lstat",
            side_effect=mark_project_reparse,
        ):
            with self.assertRaises(
                registry.HumanArtifactRegistryError
            ) as unsafe:
                registry.plan_project_root_registration(self.archive, project)
        self.assertEqual(
            unsafe.exception.code,
            "human_artifact_external_root_unsafe",
        )
        self.assertFalse((self.archive / "profiles").exists())

        registered = self._register_project_root(
            project,
            approval_seed=60,
            root_seed=160,
        )
        with mock.patch.object(
            registry.os,
            "lstat",
            side_effect=mark_project_reparse,
        ):
            scan = registry.scan_human_artifacts(self.archive)
        rendered = json.dumps(scan)
        root_summary = next(
            value
            for value in scan["root_summaries"]
            if value["root_id"] == registered["root_id"]
        )
        self.assertFalse(root_summary["coverage_complete"])
        self.assertEqual(root_summary["entries_seen"], 0)
        self.assertEqual(
            root_summary["reason_codes"],
            ["registered_root_unsafe"],
        )
        self.assertFalse(scan["closeout_complete"])
        self.assertNotIn(str(project), rendered)
        self.assertNotIn("PRIVATE-REPARSE-ARTIFACT.md", rendered)
        self.assertNotIn("PRIVATE REPARSE BODY", rendered)


if __name__ == "__main__":
    unittest.main()
