from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import (
    archive_cli,
    archive_services,
    mcp_server,
    source_fidelity_session_evidence,
)
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_link import (
    exact_human_approval_link_upgrades_original_operation,
    read_exact_human_approval_link,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
    exact_human_approval_warning_codes,
)


KIT_ROOT = Path(__file__).parents[1]


class Letter136SourceFidelityFacetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        template_root = (KIT_ROOT / "templates" / "personal").resolve()
        zettel_kasten_root = (KIT_ROOT / "zettel-kasten").resolve()
        fixture_root = self.root.resolve()

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
        (fixture_root / ".gitignore").write_text(
            "# Bounded historical pre-v0.4 fixture defaults\n"
            + "\n".join(archive_cli.RECOMMENDED_GITIGNORE_PATTERNS)
            + "\n",
            encoding="utf-8",
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
            "receipts/edges",
            "receipts/mint",
            "receipts/mint/drafts",
            "receipts/source-fidelity-session-evidence",
        ):
            destination = (fixture_root / relative).resolve()
            self.assertTrue(destination.is_relative_to(fixture_root))
            destination.mkdir(parents=True, exist_ok=True)

        archive_path = fixture_root / "archive.yml"
        archive_doc = archive_cli.load_yaml(archive_path.read_text(encoding="utf-8"))
        archive_doc["archive_id"] = "archive:personal:letter136-test"
        archive_doc["name"] = "Letter 136 Test Archive"
        archive_doc["type"] = "personal"
        archive_doc["principal"] = {
            "principal_id": "person:letter136-test",
            "display_name": "Letter 136 Test",
            "kind": "person",
        }
        archive_path.write_text(archive_cli.dump_yaml(archive_doc), encoding="utf-8")

        identity_path = fixture_root / "archive-identity.yml"
        identity_doc = archive_cli.load_yaml(identity_path.read_text(encoding="utf-8"))
        identity_doc["identity"].update(
            {
                "archive_id": "archive:personal:letter136-test",
                "identity_id": "identity:archive:personal:letter136-test",
                "scope": "personal",
                "principal_id": "person:letter136-test",
                "display_name": "Letter 136 Test",
            }
        )
        identity_doc["ownership"].update(
            {
                "owner_id": "person:letter136-test",
                "owner_kind": "person",
                "owner_display_name": "Letter 136 Test",
                "owner_archive_id": "archive:personal:letter136-test",
                "operators": [
                    {
                        "operator_id": "person:letter136-test",
                        "role": "owner_operator",
                        "permissions": [
                            "capture",
                            "curate",
                            "approve",
                            "transfer_request",
                        ],
                    }
                ],
            }
        )
        identity_path.write_text(
            archive_cli.dump_yaml(identity_doc),
            encoding="utf-8",
        )

        for filename in ("provider-bindings.yml", "source-bindings.yml"):
            binding_path = fixture_root / filename
            binding_doc = archive_cli.load_yaml(
                binding_path.read_text(encoding="utf-8")
            )
            binding_doc["archive_id"] = "archive:personal:letter136-test"
            binding_path.write_text(
                archive_cli.dump_yaml(binding_doc),
                encoding="utf-8",
            )

    def private_session_input(self, value: bytes) -> str:
        relative = (
            ".wom-scratch/private/source-fidelity/session-evidence/"
            "reviewed-source.txt"
        )
        path = self.root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        return relative

    def approved_session_evidence(
        self,
        *,
        value: bytes = b"Reviewed external source.\r\nSecond line.\r\n",
        session_ref: str = "session:letter136",
        source_role: str = "external_primary_source",
        producer_kind: str = "human",
        produced_at: str = "2026-08-19T00:00:00Z",
        captured_at: str = "2026-08-19T01:00:00Z",
        input_provenance_sha256: list[str] | None = None,
    ) -> tuple[dict[str, object], str]:
        relative = self.private_session_input(value)
        kwargs = {
            "session_ref": session_ref,
            "source_role": source_role,
            "producer_kind": producer_kind,
            "produced_at": produced_at,
            "captured_at": captured_at,
            "input_provenance_sha256": input_provenance_sha256 or [],
        }
        plan = source_fidelity_session_evidence.plan_session_evidence(
            self.root, relative, **kwargs
        )
        self.assertTrue(plan["ok"], plan)
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.source_fidelity_session_evidence,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                "archive:personal:letter136-test"
            ),
            plan_sha256="sha256:" + str(plan["plan_sha256"]),
            target_binding_sha256=(
                "sha256:" + str(plan["source"]["raw_sha256"])
            ),
            reviewer_claim="person:letter136-test",
            review_binding_codes=(
                "evidence_bytes_reviewed",
                "provenance_reviewed",
                "storage_intent_reviewed",
            ),
            warning_codes=(),
        )
        decision = ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
        )
        claim = claim_exact_human_approval(
            self.root,
            context,
            decision,
            bytearray(b"k" * 32),
        )
        try:
            approved = source_fidelity_session_evidence.approve_session_evidence(
                self.root,
                relative,
                expected_plan_sha256=str(plan["plan_sha256"]),
                reviewed_by="person:letter136-test",
                exact_human_approval_claim=claim,
                **kwargs,
            )
            if approved.get("ok") is True:
                claim.finalize_succeeded()
        finally:
            claim.close()
        self.assertTrue(approved["ok"], approved)
        link_summary = approved["exact_human_approval_link"]
        validated_link = read_exact_human_approval_link(
            self.root,
            link_summary["approval_id"],
            receipt_authentication_key=b"k" * 32,
        )
        expected_created = (
            approved["persistence"]["files_written_count"] > 0
        )
        self.assertEqual(
            validated_link["effect"],
            "created" if expected_created else "already_present_exact",
        )
        self.assertEqual(
            exact_human_approval_link_upgrades_original_operation(
                self.root,
                link_summary["approval_id"],
                receipt_authentication_key=b"k" * 32,
            ),
            expected_created,
        )
        return approved, relative

    def ai_session_kwargs(
        self,
        evidence_id: str,
        *,
        draft_id: str = "zet_20260820_136_session_evidence",
        facets: dict[str, str] | None = None,
        local_session: str = "session:different-workflow",
    ) -> dict[str, object]:
        return {
            "title": "Reviewed session evidence draft",
            "body": "",
            "abstract": "A reviewed session evidence fidelity record.",
            "kind": "record_note",
            "facets": facets or {"record_type": "source_fidelity"},
            "created_by": "ai_runtime:test",
            "source": "test_fixture",
            "creation_mode": "ai_assisted",
            "assisted_by": ["ai_runtime:test"],
            "local_ai_sessions": [{"session_ref": local_session}],
            "draft_id": draft_id,
            "created_at": "2026-08-20T12:10:00+09:00",
            "source_fidelity_mode": "verbatim",
            "source_fidelity_audience": "private_self",
            "fidelity_session_evidence_id": evidence_id,
        }

    def test_session_evidence_is_private_create_only_and_content_free(self) -> None:
        content = b"Private reviewed source bytes.\r\nNo path may be echoed.\r\n"
        raw_ref = "session:letter136-private"
        approved, relative = self.approved_session_evidence(
            value=content, session_ref=raw_ref
        )
        serialized = json.dumps(approved, ensure_ascii=False)
        self.assertNotIn(content.decode("utf-8"), serialized)
        self.assertNotIn(relative, serialized)
        self.assertNotIn(raw_ref, serialized)
        self.assertEqual(
            approved["provenance"]["session_ref_sha256"],
            "sha256:" + hashlib.sha256(raw_ref.encode("utf-8")).hexdigest(),
        )

        evidence_id = str(approved["evidence_id"])
        digest = evidence_id.rsplit(":", 1)[1]
        storage = (
            self.root
            / "profiles"
            / "local"
            / "source-fidelity"
            / "session-evidence"
            / f"{digest}.txt"
        )
        receipt_path = (
            self.root
            / "receipts"
            / "source-fidelity"
            / "session-evidence"
            / f"{digest}.json"
        )
        self.assertEqual(storage.read_bytes(), content)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertNotIn(raw_ref, json.dumps(receipt, ensure_ascii=False))
        self.assertNotIn(relative, json.dumps(receipt, ensure_ascii=False))
        schema = json.loads(
            (
                KIT_ROOT
                / "schemas"
                / "source-fidelity-session-evidence-receipt-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)

        evidence, normalized, blockers = (
            source_fidelity_session_evidence._read_verified_session_evidence(
                self.root, evidence_id
            )
        )
        self.assertEqual(blockers, [])
        self.assertEqual(normalized, content.replace(b"\r\n", b"\n"))
        self.assertEqual(evidence["authority_kind"], "reviewed_session_evidence")

        replay, _ = self.approved_session_evidence(
            value=content, session_ref=raw_ref
        )
        self.assertEqual(replay["state"], "already_written")
        self.assertEqual(replay["persistence"]["files_written_count"], 0)

    def test_v02_session_authority_create_and_mint_verification(self) -> None:
        approved, _ = self.approved_session_evidence()
        kwargs = self.ai_session_kwargs(str(approved["evidence_id"]))
        preview = archive_services.create_draft_zettel(
            self.root, dry_run=True, **kwargs
        )
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(
            preview["source_fidelity"]["schema"],
            archive_services.SOURCE_FIDELITY_SCHEMA_V2,
        )
        self.assertEqual(
            preview["source_fidelity"]["authority_kind"],
            "reviewed_session_evidence",
        )
        self.assertEqual(
            preview["approval_handoff"]["schema"],
            "wom-kit/approval-handoff/v0.1",
        )
        self.assertIsNone(preview["approval_handoff"]["receipt_ref"])
        self.assertTrue(preview["approval_handoff"]["required_review_bindings"])

        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)

        create_context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.create_draft,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                "archive:personal:letter136-test"
            ),
            plan_sha256=(
                "sha256:" + str(preview["source_fidelity_plan_sha256"])
            ),
            target_binding_sha256="sha256:" + str(preview["body_sha256"]),
            reviewer_claim="person:letter136-test",
            review_binding_codes=(
                "body_digest_reviewed",
                "draft_identity_reviewed",
                "source_fidelity_reviewed",
            ),
            warning_codes=(),
        )
        create_decision = ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=create_context.plan_sha256,
            target_binding_sha256=create_context.target_binding_sha256,
        )
        create_claim = claim_exact_human_approval(
            self.root,
            create_context,
            create_decision,
            bytearray(b"c" * 32),
        )
        try:
            written = archive_services.create_draft_zettel(
                self.root,
                approved=True,
                draft_approved_by="person:letter136-test",
                expected_body_sha256=preview["body_sha256"],
                expected_source_fidelity_plan_sha256=preview[
                    "source_fidelity_plan_sha256"
                ],
                exact_human_approval_claim=create_claim,
                **kwargs,
            )
            create_claim.finalize_succeeded()
        finally:
            create_claim.close()
        create_link = written["exact_human_approval_link"]
        self.assertEqual(
            written["approval_handoff"]["receipt_ref"],
            {
                "schema": "wom-kit/exact-human-approval-link-receipt/v0.1",
                "receipt_id": create_link["approval_id"],
                "receipt_sha256": create_link["receipt_sha256"],
                "one_use": True,
                "consumed": True,
            },
        )
        self.assertEqual(
            read_exact_human_approval_link(
                self.root,
                create_link["approval_id"],
                receipt_authentication_key=b"c" * 32,
            )["effect"],
            "created",
        )
        self.assertTrue(
            exact_human_approval_link_upgrades_original_operation(
                self.root,
                create_link["approval_id"],
                receipt_authentication_key=b"c" * 32,
            )
        )
        receipt = json.loads(
            (self.root / written["source_fidelity_draft_receipt_path"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            receipt["schema"],
            archive_services.SOURCE_FIDELITY_DRAFT_RECEIPT_SCHEMA_V2,
        )
        schema = json.loads(
            (
                KIT_ROOT
                / "schemas"
                / "source-fidelity-draft-receipt-v0.2.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
        verification = archive_services._source_fidelity_verify_for_mint(
            self.root,
            self.root / written["path"],
            affirmations=None,
        )
        self.assertTrue(verification["ok"], verification)
        self.assertEqual(
            verification["authority_binding_state"],
            "reviewed_session_evidence",
        )

    def test_circular_self_source_is_blocked_by_positive_evidence(self) -> None:
        approved, _ = self.approved_session_evidence(
            session_ref="session:same-ai-workflow",
            source_role="self_authored_candidate",
            producer_kind="ai_runtime",
            produced_at="2026-08-20T03:10:00Z",
            captured_at="2026-08-20T03:11:00Z",
        )
        preview = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            **self.ai_session_kwargs(
                str(approved["evidence_id"]),
                local_session="session:same-ai-workflow",
            ),
        )
        self.assertIn("circular_self_source", preview["blockers"])
        self.assertFalse(preview["source_fidelity"]["mechanically_verified"])

    def test_scratch_captured_object_self_source_is_blocked_but_v01_remains_readable(self) -> None:
        raw = b"AI-authored candidate later captured as its own object.\n"
        staged_relative = ".wom-scratch/candidate-body.txt"
        staged_path = self.root.joinpath(*staged_relative.split("/"))
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.write_bytes(raw)
        intake_plan = archive_services.source_intake_plan(
            self.root,
            local_path=staged_path,
            source_role="primary_source",
        )
        self.assertTrue(intake_plan["ok"], intake_plan)
        intake_sha = archive_services.sha256_json_value(intake_plan)
        intake_relative = archive_services.source_intake_record_path(intake_sha)
        intake_path = self.root.joinpath(*intake_relative.split("/"))
        intake_path.parent.mkdir(parents=True, exist_ok=True)
        intake_path.write_text(
            json.dumps(intake_plan, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        digest = hashlib.sha256(raw).hexdigest()
        object_id = "sha256:" + digest
        logical_key = f"objects/sha256/{digest[:2]}/{digest}"
        object_path = self.root.joinpath(*logical_key.split("/"))
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(raw)
        manifest_path = self.root / "objects" / "manifests" / "files.jsonl"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "object_id": object_id,
                    "sha256": digest,
                    "logical_key": logical_key,
                    "mime": "text/plain",
                    "size_bytes": len(raw),
                    "locations": [],
                    "provenance": {
                        "captured_at": "2026-08-20T00:00:00Z",
                        "source_staged_path": staged_relative,
                        "source_intake_receipt_path": intake_relative,
                        "source_intake_plan_sha256": intake_sha,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        preview = archive_services.create_draft_zettel(
            self.root,
            title="Circular object candidate",
            body="",
            abstract="A candidate that must not prove fidelity to itself.",
            kind="record_note",
            facets={"record_type": "source_fidelity"},
            created_by="ai_runtime:test",
            source="test_fixture",
            creation_mode="ai_assisted",
            assisted_by=["ai_runtime:test"],
            draft_id="zet_20260820_136_circular_object",
            created_at="2026-08-20T12:10:00+09:00",
            source_fidelity_mode="verbatim",
            source_fidelity_audience="private_self",
            fidelity_source_object_id=object_id,
            dry_run=True,
        )
        self.assertIn("circular_self_source", preview["blockers"])
        self.assertEqual(
            preview["source_fidelity"]["schema"],
            archive_services.SOURCE_FIDELITY_SCHEMA_V1,
        )

    def test_summary_roles_require_input_digest_and_never_claim_semantics(self) -> None:
        relative = self.private_session_input(b"Reviewed multi-source synthesis.")
        blocked = source_fidelity_session_evidence.plan_session_evidence(
            self.root,
            relative,
            session_ref="session:bundle",
            source_role="reviewed_multi_source_bundle",
            producer_kind="mixed",
            produced_at="2026-08-19T00:00:00Z",
            captured_at="2026-08-19T01:00:00Z",
            input_provenance_sha256=[],
        )
        self.assertEqual(
            blocked["blockers"],
            ["session_evidence_input_provenance_required"],
        )
        approved, _ = self.approved_session_evidence(
            value=b"Reviewed multi-source synthesis.",
            session_ref="session:bundle",
            source_role="reviewed_multi_source_bundle",
            producer_kind="mixed",
            input_provenance_sha256=["sha256:" + "1" * 64],
        )
        self.assertFalse(
            approved["provenance"]["semantic_fidelity_machine_verified"]
        )

    def test_replay_identity_code_revision_contract_and_facet_discovery(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = archive_cli.main(
                [
                    "create-draft",
                    str(self.root),
                    "--title",
                    "Missing replay identity",
                    "--body",
                    "Reviewed body",
                    "--abstract",
                    "Reviewed abstract.",
                    "--facet",
                    "record_type=test",
                    "--creation-mode",
                    "ai_assisted",
                    "--assisted-by",
                    "ai_runtime:test",
                    "--source-fidelity",
                    "faithful_summary",
                    "--fidelity-audience",
                    "private_self",
                    "--fidelity-source-object-id",
                    "sha256:" + "0" * 64,
                    "--approve",
                    "--draft-approved-by",
                    "person:letter136-test",
                    "--expected-body-sha256",
                    "1" * 64,
                    "--expected-source-fidelity-plan-sha256",
                    "2" * 64,
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 1)
        blocked_create = json.loads(output.getvalue())
        self.assertEqual(
            blocked_create["reason_codes"],
            ["create_draft_ai_replay_identity_required"],
        )
        self.assertEqual(
            blocked_create["missing_required_options"],
            ["--draft-id", "--created-at"],
        )

        blocked_revision = archive_services.blocked_zet_revision_plan_payload(
            archive_id="archive:personal:letter136-test",
            dry_run=True,
            blockers=["frontmatter_boundary_invalid"],
            warnings=[],
        )
        self.assertEqual(
            blocked_revision["proposal_document_contract"]["format"],
            "complete_zettel_markdown_document",
        )
        self.assertFalse(
            blocked_revision["proposal_document_contract"][
                "partial_body_or_patch_accepted"
            ]
        )
        help_text = archive_cli.build_parser().format_help()
        proposal_help = next(
            action.help
            for action in archive_cli.build_parser()._subparsers._group_actions[0]
            .choices["zet-revision-plan"]
            ._actions
            if action.dest == "proposal"
        )
        self.assertIn("COMPLETE zet Markdown", proposal_help)
        self.assertIsInstance(help_text, str)

        vocabulary = archive_services.facet_vocabulary(
            self.root, dry_run=True
        )
        by_key = {item["key"]: item for item in vocabulary["keys"]}
        self.assertEqual(by_key["education_stage"]["role"], "navigation")
        self.assertTrue(vocabulary["unknown_key_policy"]["accepted_for_draft"])
        self.assertFalse(vocabulary["facet_values_read"])
        self.assertIn(
            "facet_vocabulary",
            {definition["name"] for definition in mcp_server.TOOL_DEFINITIONS},
        )

        approved, _ = self.approved_session_evidence()
        unknown_preview = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            **self.ai_session_kwargs(
                str(approved["evidence_id"]),
                draft_id="zet_20260820_136_unknown_facet",
                facets={"invented_axis": "review-me"},
            ),
        )
        self.assertTrue(unknown_preview["ok"], unknown_preview)
        self.assertIn(
            "unknown_facet_key_requires_human_review",
            unknown_preview["warnings"],
        )
        known_preview = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            **self.ai_session_kwargs(
                str(approved["evidence_id"]),
                draft_id="zet_20260820_136_known_facet",
                facets={"education_stage": "graduate"},
            ),
        )
        self.assertNotIn(
            "unknown_facet_key_requires_human_review",
            known_preview["warnings"],
        )

    def test_create_warning_set_drift_invalidates_exact_approval(self) -> None:
        approved, _ = self.approved_session_evidence()
        kwargs = self.ai_session_kwargs(
            str(approved["evidence_id"]),
            draft_id="zet_20260820_136_warning_drift",
            facets={"invented_axis": "review-me"},
        )
        preview = archive_services.create_draft_zettel(
            self.root, dry_run=True, **kwargs
        )
        bound = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            approved=True,
            draft_approved_by="person:letter136-test",
            expected_body_sha256=preview["body_sha256"],
            expected_source_fidelity_plan_sha256=preview[
                "source_fidelity_plan_sha256"
            ],
            **kwargs,
        )
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.create_draft,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                "archive:personal:letter136-test"
            ),
            plan_sha256="sha256:" + bound["source_fidelity_plan_sha256"],
            target_binding_sha256="sha256:" + bound["body_sha256"],
            reviewer_claim="person:letter136-test",
            review_binding_codes=(
                "body_digest_reviewed",
                "draft_identity_reviewed",
                "source_fidelity_reviewed",
            ),
            warning_codes=exact_human_approval_warning_codes(
                bound["warnings"]
            ),
        )
        claim = claim_exact_human_approval(
            self.root,
            context,
            ExactHumanApprovalDecision(
                approved=True,
                synthetic_acknowledged=False,
                reason_code="exact_human_approval_approved",
                plan_sha256=context.plan_sha256,
                target_binding_sha256=context.target_binding_sha256,
            ),
            b"w" * 32,
        )
        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        vocabulary = archive_services.facet_vocabulary(self.root, dry_run=True)
        vocabulary["keys"] = [
            *vocabulary["keys"],
            {"key": "invented_axis"},
        ]
        try:
            with mock.patch.object(
                archive_services,
                "facet_vocabulary",
                return_value=vocabulary,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "exact_human_approval_invalid",
                ):
                    archive_services.create_draft_zettel(
                        self.root,
                        approved=True,
                        draft_approved_by="person:letter136-test",
                        expected_body_sha256=preview["body_sha256"],
                        expected_source_fidelity_plan_sha256=preview[
                            "source_fidelity_plan_sha256"
                        ],
                        exact_human_approval_claim=claim,
                        **kwargs,
                    )
        finally:
            claim.close()
        self.assertFalse(
            (self.root / "inbox" / "zet_20260820_136_warning_drift.md").exists()
        )


if __name__ == "__main__":
    unittest.main()
