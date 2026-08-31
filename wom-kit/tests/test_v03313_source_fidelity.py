from __future__ import annotations

import hashlib
import io
import json
import shutil
import shlex
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from wom_kit import archive_cli, archive_services
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
    exact_human_approval_warning_codes,
)
from wom_kit.operation_approval_binding import mint_zet_approval_binding


class SourceFidelityV03313Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        kit_root = Path(__file__).resolve().parents[1]
        template_root = (kit_root / "templates" / "personal").resolve()
        zettel_kasten_root = (kit_root / "zettel-kasten").resolve()
        fixture_root = self.root.resolve()

        self.assertEqual(template_root.parent, (kit_root / "templates").resolve())
        self.assertTrue(template_root.is_dir())
        self.assertEqual(zettel_kasten_root, (kit_root / "zettel-kasten").resolve())
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
            "receipts/derived-text-capture",
            "receipts/delegate",
            "receipts/edges",
            "receipts/import",
            "receipts/lineage",
            "receipts/mint",
            "receipts/mint/drafts",
            "receipts/recovery",
            "receipts/share",
            "receipts/sources",
        ):
            destination = (fixture_root / relative).resolve()
            self.assertTrue(destination.is_relative_to(fixture_root))
            destination.mkdir(parents=True, exist_ok=True)

        archive_path = fixture_root / "archive.yml"
        archive_doc = archive_cli.load_yaml(archive_path.read_text(encoding="utf-8"))
        archive_doc["archive_id"] = "archive:personal:fidelity-test"
        archive_doc["name"] = "Fidelity Test Archive"
        archive_doc["type"] = "personal"
        archive_doc["principal"] = {
            "principal_id": "person:fidelity-test",
            "display_name": "Fidelity Test",
            "kind": "person",
        }
        archive_path.write_text(archive_cli.dump_yaml(archive_doc), encoding="utf-8")

        identity_path = fixture_root / "archive-identity.yml"
        identity_doc = archive_cli.load_yaml(identity_path.read_text(encoding="utf-8"))
        identity_doc["identity"].update(
            {
                "archive_id": "archive:personal:fidelity-test",
                "identity_id": "identity:archive:personal:fidelity-test",
                "scope": "personal",
                "principal_id": "person:fidelity-test",
                "display_name": "Fidelity Test",
            }
        )
        identity_doc["ownership"].update(
            {
                "owner_id": "person:fidelity-test",
                "owner_kind": "person",
                "owner_display_name": "Fidelity Test",
                "owner_archive_id": "archive:personal:fidelity-test",
                "operators": [
                    {
                        "operator_id": "person:fidelity-test",
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
            binding_doc["archive_id"] = "archive:personal:fidelity-test"
            binding_path.write_text(
                archive_cli.dump_yaml(binding_doc),
                encoding="utf-8",
            )

        (fixture_root / ".gitignore").write_text(
            "# Bounded historical pre-v0.4 fixture defaults\n"
            + "\n".join(archive_cli.RECOMMENDED_GITIGNORE_PATTERNS)
            + "\n",
            encoding="utf-8",
        )
        self.assertEqual(
            archive_services.read_archive_id(fixture_root),
            "archive:personal:fidelity-test",
        )
        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)

    def manifested_source(self, raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        object_id = f"sha256:{digest}"
        logical_key = f"objects/sha256/{digest[:2]}/{digest}"
        object_path = self.root.joinpath(*logical_key.split("/"))
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(raw)
        manifest_path = self.root / "objects" / "manifests" / "files.jsonl"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "object_id": object_id,
            "sha256": digest,
            "logical_key": logical_key,
            "mime": "text/plain",
            "size_bytes": len(raw),
            "locations": [
                {
                    "provider": "local",
                    "path": logical_key,
                    "availability": "available",
                }
            ],
            "provenance": {"source": "test"},
        }
        with manifest_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)
        return object_id

    def archive_file_snapshot(self) -> dict[str, str]:
        return {
            path.relative_to(self.root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

    def write_historical_human_draft(
        self,
        *,
        draft_id: str,
        title: str,
        body: str,
        abstract: str,
        facets: dict[str, object],
        created_at: str,
        created_by: str = "person:legacy-fixture",
    ) -> dict[str, str]:
        """Write one bounded pre-v0.4 human draft fixture without a writer."""

        self.assertRegex(draft_id, r"^zet_[A-Za-z0-9_]+$")
        relative_path = f"inbox/{draft_id}.md"
        path = (self.root / relative_path).resolve()
        self.assertTrue(path.is_relative_to(self.root.resolve()))
        self.assertFalse(path.exists())
        frontmatter = {
            "id": draft_id,
            "title": title,
            "abstract": abstract,
            "created_at": created_at,
            "updated_at": created_at,
            "archive_id": "archive:personal:fidelity-test",
            "status": "draft",
            "kind": "fleeting_capture",
            "facets": facets,
            "assets": [],
            "edges": [],
            "provenance": {
                "created_by": created_by,
                "created_in": "archive:personal:fidelity-test",
                "source": "test_fixture",
                "derived_from": [],
                "creation_mode": "human_written",
            },
            "visibility": {
                "scope": "private",
                "allowed_archives": [],
                "source_visibility": "private",
            },
            "promotion": {
                "stage": "captured",
                "ready_for_promotion": False,
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            + archive_services.dump_yaml(frontmatter)
            + "---\n\n"
            + body.rstrip()
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(path.read_bytes().count(b"\r"), 0)
        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)
        return {"path": relative_path}

    def ai_kwargs(
        self,
        object_id: str,
        *,
        draft_id: str = "zet_20260810_121_fidelity",
        title: str = "Source fidelity record",
        body: str = "",
        mode: str = "verbatim",
        audience: str = "private_self",
    ) -> dict[str, object]:
        return {
            "title": title,
            "body": body,
            "abstract": "A reviewed source fidelity record.",
            "kind": "record_note",
            "facets": {"record_type": "source_fidelity"},
            "created_by": "ai_runtime:test",
            "source": "test_fixture",
            "creation_mode": "ai_assisted",
            "assisted_by": ["ai_runtime:test"],
            "draft_id": draft_id,
            "created_at": "2026-08-10T12:10:00+09:00",
            "source_fidelity_mode": mode,
            "source_fidelity_audience": audience,
            "fidelity_source_object_id": object_id,
        }

    def exact_claim(self, context: ExactHumanApprovalContext):
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
            bytearray(b"f" * 32),
        )
        self.addCleanup(claim.close)
        return claim

    def create_approved(
        self,
        kwargs: dict[str, object],
        *,
        preview: dict[str, object] | None = None,
    ) -> dict[str, object]:
        preview = preview or archive_services.create_draft_zettel(
            self.root, dry_run=True, **kwargs
        )
        self.assertTrue(preview["ok"], preview)
        bound_preview = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            approved=True,
            draft_approved_by="person:fidelity-test",
            expected_body_sha256=preview["body_sha256"],
            expected_source_fidelity_plan_sha256=preview[
                "source_fidelity_plan_sha256"
            ],
            **kwargs,
        )
        self.assertTrue(bound_preview["ok"], bound_preview)
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.create_draft,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                "archive:personal:fidelity-test"
            ),
            plan_sha256=(
                "sha256:"
                + str(bound_preview["source_fidelity_plan_sha256"])
            ),
            target_binding_sha256=(
                "sha256:" + str(bound_preview["body_sha256"])
            ),
            reviewer_claim="person:fidelity-test",
            review_binding_codes=(
                "body_digest_reviewed",
                "draft_identity_reviewed",
                "source_fidelity_reviewed",
            ),
            warning_codes=exact_human_approval_warning_codes(
                bound_preview.get("warnings")
                if isinstance(bound_preview.get("warnings"), list)
                else []
            ),
        )
        claim = self.exact_claim(context)
        result = archive_services.create_draft_zettel(
            self.root,
            approved=True,
            draft_approved_by="person:fidelity-test",
            expected_body_sha256=preview["body_sha256"],
            expected_source_fidelity_plan_sha256=preview[
                "source_fidelity_plan_sha256"
            ],
            exact_human_approval_claim=claim,
            **kwargs,
        )
        claim.finalize_succeeded()
        return result

    def test_verbatim_preserves_unicode_whitespace_order_and_only_normalizes_newlines(self) -> None:
        source_text = (
            "\ufeff  홍길동 010-1234-5678  \r\n"
            "\tleading-tab and trailing spaces  \r"
            "NFC é / NFD e\u0301 / 😀 / אבג\r\n\r\n\r\n"
        )
        object_id = self.manifested_source(source_text.encode("utf-8"))
        kwargs = self.ai_kwargs(object_id)
        preview = archive_services.create_draft_zettel(
            self.root, dry_run=True, **kwargs
        )
        self.assertTrue(preview["ok"], preview)
        safe = preview["source_fidelity"]
        self.assertNotIn("source", safe)
        self.assertNotIn("region", safe)
        self.assertNotIn(object_id, json.dumps(preview, ensure_ascii=False))

        result = self.create_approved(kwargs)
        draft_path = self.root / result["path"]
        receipt_path = self.root / result["source_fidelity_draft_receipt_path"]
        receipt_schema = json.loads(
            (
                Path(__file__).parents[1]
                / "schemas"
                / "source-fidelity-draft-receipt.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(receipt_schema)
        Draft202012Validator(receipt_schema).validate(
            json.loads(receipt_path.read_text(encoding="utf-8"))
        )
        snapshot = archive_services._source_fidelity_raw_draft_snapshot(
            self.root, draft_path
        )
        self.assertTrue(snapshot["ok"], snapshot)
        expected = source_text.replace("\r\n", "\n").replace("\r", "\n")
        self.assertEqual(snapshot["body_bytes"], expected.encode("utf-8"))
        self.assertTrue(result["source_fidelity"]["mechanically_verified"])

        replay = self.create_approved(kwargs, preview=preview)
        self.assertTrue(replay["idempotent_replay"], replay)
        self.assertEqual(replay["created_paths"], [])

    def test_receipt_schema_rejects_mode_region_and_mechanical_contradictions(self) -> None:
        object_id = self.manifested_source(
            b"Schema parity source with a mechanically verified exact region."
        )
        result = self.create_approved(
            self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_schema_parity",
                title="Receipt schema parity",
            )
        )
        receipt = json.loads(
            (self.root / result["source_fidelity_draft_receipt_path"])
            .read_text(encoding="utf-8")
        )
        schema = json.loads(
            (
                Path(__file__).parents[1]
                / "schemas"
                / "source-fidelity-draft-receipt.schema.json"
            ).read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        contradictions = []
        missing_verbatim_region = json.loads(json.dumps(receipt))
        missing_verbatim_region["source_fidelity"]["region"] = None
        missing_verbatim_region["source_fidelity"][
            "mechanically_verified"
        ] = False
        contradictions.append(missing_verbatim_region)
        false_summary_proof = json.loads(json.dumps(receipt))
        false_summary_proof["source_fidelity"]["mode"] = "faithful_summary"
        contradictions.append(false_summary_proof)
        for index, contradiction in enumerate(contradictions):
            with self.subTest(index=index):
                self.assertTrue(list(validator.iter_errors(contradiction)))

    def test_unapproved_ai_write_and_secret_source_fail_closed_without_echo(self) -> None:
        ordinary_id = self.manifested_source(
            b"ordinary private source text long enough for review"
        )
        kwargs = self.ai_kwargs(
            ordinary_id,
            draft_id="zet_20260810_121_unapproved",
            title="Unapproved fidelity record",
        )
        before = self.archive_file_snapshot()
        blocked_write = archive_services.create_draft_zettel(self.root, **kwargs)
        self.assertFalse(blocked_write["ok"])
        self.assertEqual(
            blocked_write["reason_codes"],
            ["compound_exact_human_approval_binding_required"],
        )
        self.assertEqual(blocked_write["files_written"], [])
        self.assertFalse(blocked_write["private_values_echoed"])
        self.assertNotIn(ordinary_id, json.dumps(blocked_write, ensure_ascii=False))
        self.assertEqual(self.archive_file_snapshot(), before)
        self.assertFalse(
            (self.root / "inbox" / "zet_20260810_121_unapproved.md").exists()
        )

        token = "Bearer PRIVATE_TOKEN_12345678901234567890"
        secret_id = self.manifested_source(token.encode("utf-8"))
        blocked = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            **self.ai_kwargs(
                secret_id,
                draft_id="zet_20260810_121_secret",
                title="Secret fidelity record",
            ),
        )
        self.assertIn("credential_secret_present", blocked["blockers"])
        self.assertNotIn(token, json.dumps(blocked, ensure_ascii=False))
        self.assertNotIn(secret_id, json.dumps(blocked, ensure_ascii=False))

        for index, empty_source in enumerate((b"", b" \t\r\n", b"\xef\xbb\xbf\r\n")):
            with self.subTest(empty_source=index):
                empty_id = self.manifested_source(empty_source)
                empty_result = archive_services.create_draft_zettel(
                    self.root,
                    dry_run=True,
                    **self.ai_kwargs(
                        empty_id,
                        draft_id=f"zet_20260810_121_empty_source_{index}",
                        title=f"Empty source {index}",
                        body="Context cannot substitute for an empty source.",
                    ),
                )
                self.assertIn(
                    "source_fidelity_source_must_contain_non_whitespace_text",
                    empty_result["blockers"],
                )

    def test_declared_ai_provenance_cannot_fall_back_to_human_write_route(self) -> None:
        cases = [
            {
                "creation_mode": None,
                "created_by": "ai_runtime:test",
                "assisted_by": None,
            },
            {
                "creation_mode": None,
                "created_by": "person:test",
                "assisted_by": ["ai_runtime:test"],
            },
            {
                "creation_mode": "human_written",
                "created_by": "person:test",
                "assisted_by": ["ai_runtime:test"],
            },
            {
                "creation_mode": "human_written",
                "created_by": "person:test",
                "assisted_by": None,
                "local_ai_sessions": [
                    {
                        "session_ref": "session:explicit-ai",
                        "runtime": "codex",
                    }
                ],
            },
        ]
        for index, evidence in enumerate(cases):
            with self.subTest(index=index):
                draft_id = f"zet_20260810_121_ai_route_{index}"
                preview = archive_services.create_draft_zettel(
                    self.root,
                    title=f"AI provenance route {index}",
                    body="A body that must not be written through the human route.",
                    abstract="A reviewed abstract for the provenance route test.",
                    facets={"record_type": "source_fidelity"},
                    draft_id=draft_id,
                    created_at="2026-08-10T12:15:00+09:00",
                    dry_run=True,
                    **evidence,
                )
                self.assertIn(
                    "ai_provenance_requires_ai_creation_mode",
                    preview["blockers"],
                )
                before = self.archive_file_snapshot()
                blocked_write = archive_services.create_draft_zettel(
                    self.root,
                    title=f"AI provenance route {index}",
                    body="A body that must not be written through the human route.",
                    abstract="A reviewed abstract for the provenance route test.",
                    facets={"record_type": "source_fidelity"},
                    draft_id=draft_id,
                    created_at="2026-08-10T12:15:00+09:00",
                    **evidence,
                )
                self.assertFalse(blocked_write["ok"])
                self.assertEqual(
                    blocked_write["reason_codes"],
                    ["compound_exact_human_approval_binding_required"],
                )
                self.assertEqual(blocked_write["files_written"], [])
                self.assertFalse(blocked_write["private_values_echoed"])
                self.assertNotIn(
                    draft_id,
                    json.dumps(blocked_write, ensure_ascii=False),
                )
                self.assertEqual(self.archive_file_snapshot(), before)
                self.assertFalse((self.root / "inbox" / f"{draft_id}.md").exists())

    def test_ai_approval_plan_binds_full_frontmatter_authority(self) -> None:
        object_id = self.manifested_source(
            b"Reviewed source whose complete draft metadata must remain approval-bound."
        )
        kwargs = self.ai_kwargs(
            object_id,
            draft_id="zet_20260810_121_approval_authority",
            title="Approval authority binding",
        )
        preview = archive_services.create_draft_zettel(
            self.root, dry_run=True, **kwargs
        )
        self.assertTrue(preview["ok"], preview)
        before = self.archive_file_snapshot()
        mutations = [
            {"abstract": "A different abstract after human review."},
            {"assisted_by": ["ai_runtime:different"]},
            {
                "local_ai_sessions": [
                    {
                        "session_ref": "session:changed-after-review",
                        "runtime": "codex",
                    }
                ]
            },
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                changed = {**kwargs, **mutation}
                blocked_write = archive_services.create_draft_zettel(
                    self.root,
                    approved=True,
                    draft_approved_by="person:fidelity-test",
                    expected_body_sha256=preview["body_sha256"],
                    expected_source_fidelity_plan_sha256=preview[
                        "source_fidelity_plan_sha256"
                    ],
                    **changed,
                )
                self.assertFalse(blocked_write["ok"])
                self.assertEqual(
                    blocked_write["reason_codes"],
                    ["compound_exact_human_approval_binding_required"],
                )
                self.assertEqual(blocked_write["files_written"], [])
                self.assertFalse(blocked_write["private_values_echoed"])
                self.assertEqual(self.archive_file_snapshot(), before)

    def test_post_create_metadata_edit_gets_a_new_mint_plan(self) -> None:
        object_id = self.manifested_source(
            b"Exact source region that remains intact while metadata is edited."
        )
        result = self.create_approved(
            self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_metadata_edit",
                title="Metadata edit receives a new plan",
            )
        )
        path = self.root / result["path"]
        snapshot = archive_services._source_fidelity_raw_draft_snapshot(
            self.root, path
        )
        self.assertTrue(snapshot["ok"], snapshot)
        frontmatter = snapshot["frontmatter"]
        frontmatter["abstract"] = "A newly reviewed abstract before mint."
        path.write_bytes(
            (
                "---\n"
                + archive_services.dump_yaml(frontmatter)
                + "---\n\n"
            ).encode("utf-8")
            + snapshot["body_bytes"]
        )
        verification = archive_services._source_fidelity_verify_for_mint(
            self.root, path, affirmations=None
        )
        self.assertTrue(verification["ok"], verification)
        self.assertNotEqual(
            verification["current_plan_sha256"],
            verification["creation_plan_sha256"],
        )

    def test_private_fidelity_object_is_removed_from_ordinary_intake_projection(self) -> None:
        object_id = self.manifested_source(
            b"Private manifested source whose locator stays in the receipt only."
        )
        intake = archive_services.source_intake_plan(
            self.root, object_id=object_id
        )
        self.assertTrue(intake["ok"], intake)
        kwargs = {
            **self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_intake_projection",
                title="Private intake projection",
            ),
            "source_intake_plan": intake,
        }
        preview = archive_services.create_draft_zettel(
            self.root, dry_run=True, **kwargs
        )
        self.assertTrue(preview["ok"], preview)
        result = self.create_approved(kwargs)
        draft_bytes = (self.root / result["path"]).read_bytes()
        mint_preview = archive_services.mint_zettel_dry_run(
            self.root, relative_path=result["path"]
        )
        private_digest = object_id.removeprefix("sha256:")
        for value in (preview, result, mint_preview):
            serialized = json.dumps(value, ensure_ascii=False)
            self.assertNotIn(object_id, serialized)
        self.assertNotIn(object_id.encode("utf-8"), draft_bytes)
        frontmatter, _ = archive_services.require_readable_zettel_content(
            self.root / result["path"]
        )
        ordinary_authority = {
            key: value
            for key, value in frontmatter.items()
            if key not in {"draft_creation", "source_fidelity"}
        }
        self.assertNotIn(
            private_digest,
            json.dumps(ordinary_authority, ensure_ascii=False),
        )

    def test_external_derivative_frontmatter_and_result_have_zero_private_authority(self) -> None:
        object_id = self.manifested_source(
            "PRIVATE PERSON 010-9876-5432".encode("utf-8")
        )
        kwargs = self.ai_kwargs(
            object_id,
            draft_id="zet_20260810_121_derivative",
            title="Reviewed public derivative",
            body="A human-reviewed derivative that contains no private source values.",
            mode="sanitized_derivative",
            audience="public_web",
        )
        result = self.create_approved(kwargs)
        draft = self.root / result["path"]
        frontmatter, _ = archive_services.require_readable_zettel_content(draft)
        public_values = json.dumps(
            {
                "frontmatter": frontmatter,
                "result_source_fidelity": result["source_fidelity"],
            },
            ensure_ascii=False,
        )
        digest = object_id.removeprefix("sha256:")
        self.assertNotIn(object_id, public_values)
        self.assertNotIn(digest, public_values)
        self.assertFalse(
            result["source_fidelity"]["semantic_fidelity_machine_verified"]
        )
        self.assertFalse(result["source_fidelity"]["share_performed"])

    def test_fidelity_draft_cannot_bypass_mint_through_promote(self) -> None:
        object_id = self.manifested_source(
            b"A source record with enough durable context for publication review."
        )
        result = self.create_approved(
            self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_promote_block",
                title="Promote bypass blocked",
            )
        )
        dry = archive_services.promote_zettel_dry_run(
            self.root, relative_path=result["path"]
        )
        self.assertIn(
            "ai_source_fidelity_draft_requires_mint_zettel", dry["blockers"]
        )
        with self.assertRaises(archive_services.ArchiveServiceError):
            archive_services.promote_zettel(
                self.root,
                relative_path=result["path"],
                reviewed_by="person:fidelity-test",
                allow_warnings=True,
            )
        self.assertFalse((self.root / "zettels" / Path(result["path"]).name).exists())

    def test_runtime_surfaces_share_one_content_free_policy(self) -> None:
        expected = archive_services.source_fidelity_policy()
        runtime = archive_services.runtime_context(self.root)
        start = archive_services.ai_start_here(self.root)
        response = archive_services.ai_response_contract(self.root)
        authoring = archive_services.authoring_conventions(self.root)
        self.assertEqual(runtime["source_fidelity_policy"], expected)
        self.assertEqual(start["source_fidelity_policy"], expected)
        self.assertEqual(response["source_fidelity_policy"], expected)
        self.assertEqual(authoring["source_fidelity_policy"], expected)
        serialized = json.dumps(expected, ensure_ascii=False)
        self.assertNotIn("sha256:", serialized)
        self.assertTrue(expected["explicit_private_verbatim_no_silent_redaction"])
        create_route = next(
            item
            for item in archive_services.runtime_context_write_action_routes()
            if item["action"] == "create_ai_draft"
        )
        self.assertIn("--source-fidelity <mode>", create_route["preview_command"])
        self.assertIn("--fidelity-audience <audience>", create_route["preview_command"])
        self.assertIn("--approve", create_route["approved_command"])
        self.assertEqual(len(create_route["writes_when_approved"]), 2)
        replacements = {
            "<archive-root>": str(self.root),
            "<title>": "Safe-title",
            "<abstract>": "Safe-abstract",
            "<facet>": "record_type=source_fidelity",
            "<private-context-file>": "context.md",
            "<ai-actor>": "ai_runtime:test",
            "<ai-runtime>": "ai_runtime:test",
            "<mode>": "verbatim",
            "<audience>": "private_self",
            "<manifested-object-id>": "sha256:" + "a" * 64,
            "<draft-id>": "zet_20260810_121_route",
            "<created-at>": "2026-08-10T12:10:00+09:00",
            "<body-sha256>": "b" * 64,
            "<fidelity-plan-sha256>": "c" * 64,
            "<human-actor>": "person:fidelity-test",
        }
        parser = archive_cli.build_parser()
        for command_key in ("preview_command", "approved_command"):
            tokens = [
                replacements.get(token, token)
                for token in shlex.split(create_route[command_key])
            ]
            self.assertEqual(tokens.pop(0), "archive")
            parsed = parser.parse_args(tokens)
            self.assertEqual(parsed.command, "create-draft")
        context_file = self.root.parent / "route-context.md"
        context_file.write_text(
            "Safe private context for the runtime route.", encoding="utf-8"
        )
        route_object_id = self.manifested_source(
            b"Safe private source bytes for the runtime route."
        )
        live_replacements = {
            **replacements,
            "<private-context-file>": str(context_file),
            "<manifested-object-id>": route_object_id,
        }
        preview_tokens = [
            live_replacements.get(token, token)
            for token in shlex.split(create_route["preview_command"])
        ][1:]
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = archive_cli.main(preview_tokens)
        self.assertEqual(code, 0, output.getvalue())
        self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_verbatim_visibility_and_locator_scope_fail_closed(self) -> None:
        locator = "https://www.notion.so/private-record"
        object_id = self.manifested_source(
            ("Private locator inside preserved source: " + locator).encode("utf-8")
        )
        unsafe = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            visibility={
                "scope": "public",
                "source_visibility": "public",
                "allowed_archives": ["archive:public:test"],
            },
            **self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_visibility",
                title="Unsafe visibility fidelity record",
            ),
        )
        self.assertIn("verbatim_requires_private_visibility", unsafe["blockers"])

        kwargs = self.ai_kwargs(
            object_id,
            draft_id="zet_20260810_121_locator",
            title="Private locator fidelity record",
        )
        result = self.create_approved(kwargs)
        promotion = archive_services.promote_zettel_dry_run(
            self.root, relative_path=result["path"]
        )
        self.assertNotIn(
            "Body appears to contain a private provider locator or local absolute path.",
            promotion["blockers"],
        )
        verification = archive_services._source_fidelity_verify_for_mint(
            self.root,
            self.root / result["path"],
            affirmations=None,
        )
        self.assertTrue(verification["ok"], verification)

        context_blocked = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            **self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_context_locator",
                title="Context locator blocked",
                body="Unsafe context " + locator,
            ),
        )
        self.assertIn(
            "private_locator_or_path_present",
            context_blocked["blockers"],
        )

    def test_legacy_crlf_ai_requires_attributed_affirmation(self) -> None:
        result = self.write_historical_human_draft(
            title="Legacy CRLF AI draft",
            body="Legacy AI body with enough context for a human fidelity review.",
            abstract="A legacy AI draft requiring attributed review.",
            facets={"record_type": "legacy_ai"},
            draft_id="zet_20260810_121_legacy_crlf",
            created_at="2026-08-10T12:20:00+09:00",
        )
        path = self.root / result["path"]
        frontmatter, body = archive_services.require_readable_zettel_content(path)
        frontmatter["provenance"]["creation_mode"] = "ai_assisted"
        frontmatter["provenance"]["assisted_by"] = ["ai_runtime:legacy"]
        text = (
            "---\n"
            + archive_services.dump_yaml(frontmatter)
            + "---\n\n"
            + body.rstrip()
            + "\n"
        )
        path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        blocked = archive_services._source_fidelity_verify_for_mint(
            self.root, path, affirmations=None
        )
        self.assertIn("legacy_source_fidelity_review_required", blocked["blockers"])
        allowed = archive_services._source_fidelity_verify_for_mint(
            self.root,
            path,
            affirmations={"legacy_source_fidelity_reviewed": "person:reviewer"},
        )
        self.assertTrue(allowed["ok"], allowed)
        self.assertTrue(allowed["legacy_review"])

    def test_all_legacy_ai_indicators_require_review_and_the_mint_route(self) -> None:
        indicators = [
            {"created_by": "ai_runtime:legacy"},
            {"created_by": "ai:codex"},
            {"created_by": "mcp:zettel-kasten-archive-mcp"},
            {"assisted_by": ["ai_runtime:legacy"]},
            {
                "local_ai_sessions": [
                    {
                        "session_ref": "session:legacy-ai",
                        "runtime": "codex",
                    }
                ]
            },
        ]
        for index, indicator in enumerate(indicators):
            with self.subTest(index=index):
                draft_id = f"zet_20260810_121_legacy_indicator_{index}"
                result = self.write_historical_human_draft(
                    title=f"Legacy AI indicator {index}",
                    body="Legacy AI body requiring an attributed fidelity review.",
                    abstract="A bounded legacy AI review fixture.",
                    facets={"record_type": "legacy_ai"},
                    created_by="person:legacy-fixture",
                    draft_id=draft_id,
                    created_at=f"2026-08-10T12:2{index}:00+09:00",
                )
                path = self.root / result["path"]
                frontmatter, body = archive_services.require_readable_zettel_content(
                    path
                )
                provenance = frontmatter["provenance"]
                provenance.pop("creation_mode", None)
                provenance.pop("assisted_by", None)
                frontmatter.pop("local_ai_sessions", None)
                if "created_by" in indicator:
                    provenance["created_by"] = indicator["created_by"]
                if "assisted_by" in indicator:
                    provenance["assisted_by"] = indicator["assisted_by"]
                if "local_ai_sessions" in indicator:
                    frontmatter["local_ai_sessions"] = indicator[
                        "local_ai_sessions"
                    ]
                path.write_text(
                    "---\n"
                    + archive_services.dump_yaml(frontmatter)
                    + "---\n\n"
                    + body.rstrip()
                    + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                archive_services.index_archive(self.root)

                blocked = archive_services._source_fidelity_verify_for_mint(
                    self.root, path, affirmations=None
                )
                self.assertIn(
                    "legacy_source_fidelity_review_required",
                    blocked["blockers"],
                )
                promoted = archive_services.promote_zettel_dry_run(
                    self.root, relative_path=result["path"]
                )
                self.assertIn(
                    "ai_source_fidelity_draft_requires_mint_zettel",
                    promoted["blockers"],
                )
                mint_preview = archive_services.mint_zettel_dry_run(
                    self.root, relative_path=result["path"]
                )
                self.assertIn(
                    "legacy_source_fidelity_review_required",
                    mint_preview["blockers"],
                )
                allowed = archive_services._source_fidelity_verify_for_mint(
                    self.root,
                    path,
                    affirmations={
                        "legacy_source_fidelity_reviewed": "person:reviewer"
                    },
                )
                self.assertTrue(allowed["ok"], allowed)
                self.assertTrue(allowed["legacy_review"])

    def test_high_confidence_credential_shapes_block_without_echo(self) -> None:
        secrets = [
            "AKIAABCDEFGHIJKLMNOP",
            "Bearer abcdefghijklmnop",
            "Authorization: Basic dXNlcjpwYXNzd29yZA==",
            "Authorization: Basic dTpw",
            "Authorization: Basic abcdefghij-_",
            "Authorization: Token 0123456789abcdef",
            "Authorization: ApiKey 0123456789abcdef",
            "Authorization: Bearer abc",
            "Authorization: Token x",
            "Authorization: abc123",
            "curl -H 'Authorization: Basic dXNlcjpwYXNzd29yZA==' https://example.invalid",
            "curl --header='Cookie: sessionid=abcdefgh12345678' https://example.invalid",
            "headers = {'Authorization': 'Basic dXNlcjpwYXNzd29yZA=='}",
            "headers = {'Cookie': 'sessionid=abcdefgh12345678'}",
            "Cookie: sessionid=private-session-value",
            "Set-Cookie: sessionid=private-session-value; HttpOnly",
            "Cookie: JSESSIONID=ABCDEF1234567890",
            "Cookie: session=abc123",
            "Cookie: sid=1234",
            "Cookie: auth=a1b2c3",
            "Cookie: connect.sid=s%3Aabc123456789.abcdef",
            'Cookie: session="AbCdEf1234567890"',
            "Cookie: csrftoken=AbCdEf1234567890",
            "Cookie: theme=dark; sessionid=private-session-value",
            "Cookie: theme=dark, JSESSIONID=ABCDEF1234567890",
            '{"Authorization":"Basic dXNlcjpwYXNzd29yZA=="}',
            '{"Cookie":"sessionid=private-session-value"}',
            (
                '{"Cookie":"session=AbCdEf1234567890",'
                '"theme":"dark"}'
            ),
            (
                '{"theme":"dark","Cookie":"session=AbCdEf1234567890",'
                '"lang":"ko"}'
            ),
            (
                '{"theme":"dark",'
                '"Cookie":"session=AbCdEf1234567890"}'
            ),
            '{"Cookie":"session=\\"AbCdEf1234567890\\""}',
            '{"Cookie":"theme=dark; JSESSIONID=ABCDEF1234567890"}',
            '{"password":"abcdefghijklmnop"}',
            '{"token":"abcdefghijklmnop"}',
            '{"secret":"abcdefghijklmnop"}',
            '{"credential":"abcdefghijklmnop"}',
            '{"client_secret":"abcdefghijklmnop"}',
            '{"access_token":"abcdefghijklmnop"}',
            "password: P@ssw0rd!Abcdefgh",
            '{"password":"P@ssw0rd!Abcdefgh"}',
            "client_secret: aB3$xyz!987654321",
            "DB_PASSWORD=P@ssw0rd!Abcdefgh",
            "export DB_PASSWORD=P@ssw0rd!Abcdefgh",
            "set DB_PASSWORD=P@ssw0rd!Abcdefgh",
            "$env:DB_PASSWORD=P@ssw0rd!Abcdefgh",
            "env GITHUB_TOKEN=abcdefghijklmnop command",
            "The leaked DB_PASSWORD=P@ssw0rd!Abcdefgh",
            '{"DB_PASSWORD":"P@ssw0rd!Abcdefgh"}',
            "GITHUB_TOKEN=abcdefghijklmnop",
            "MY_CLIENT_SECRET=aB3$xyz!987654321",
            'password: "correct horse battery staple"',
            '{"password":"correct horse battery staple"}',
            "DB_PASSWORD: |\n  correct horse battery staple",
            "password: correct horse battery staple",
            "DB_PASSWORD=correct horse battery staple",
            "eyJabcdefgh.ijklmnop.qrstuvwx",
            "github_" + "pat_abcdefghijklmnopqrstuvwxyz",
            "".join(("AI", "za", "A" * 35)),
            "sk-proj-exampleabcdefghijklmnopqrstuvwxyz",
            "_".join(("sk", "live")) + "_abcdefghijklmnopqrstuvwx",
            "_".join(("rk", "live")) + "_abcdefghijklmnopqrstuvwx",
            "AWS_SECRET_ACCESS_KEY=abcdefghijklmnopqrstuvwx12345678",
            "aws_secret_access_key: abcdefghijklmnopqrstuvwx12345678",
            "SECRET=abcdefghijklmnopqrstuvwx12345678",
            "TOKEN=abcdefghijklmnopqrstuvwx12345678",
            "TOKEN=abcdefghijkl",
            "password: abcdefghijkl",
            "DB_PASSWORD=x",
            "export API_TOKEN=abc",
            "client_secret: short",
            "Password: the current value is abcdefghijklmnop.",
            "Token: gh" + "p_abcdefghijklmnopqrstuvwxyz is used by automation.",
            "Secret: abcdefghijkl is the key.",
            'Credential: "short value should stay private."',
            "password: this is my secret phrase.",
            "password: my dog is very cute.",
            "token: abc def ghi is secret.",
            "client secret: this is super secret passphrase.",
            "password: correct horse battery staple is valid.",
            "password: hunter two can open the vault.",
            "password: should be correct horse battery staple.",
            "password: must be correct horse battery staple.",
            "token: a unit hunter two three.",
            "secret: proof of horse battery staple.",
            "credential: information that opens my account.",
            "client secret: should be abc def ghi.",
            "token: example as "
            + "abcdefghijklmnopqrstuvwxyz"
            + "1234567890",
            "secret: example as " + "A1b2C3d4E5f6G7h8I9j0K1l2",
            "credential: EXAMPLE as "
            + "vendorOpaqueCredential"
            + "9876543210",
            "token: example"
            + "A1b2C3d4E5f6G7h8"
            + "TOKEN",
            "password: fake"
            + "CorrectHorseBatteryStaple"
            + "PASSWORD",
            "credential: sample"
            + "VendorOpaque987654321"
            + "CREDENTIAL",
            "token: YOUR"
            + "stolenOpaqueValue123456789"
            + "TOKEN",
        ]
        for index, secret in enumerate(secrets):
            with self.subTest(index=index):
                object_id = self.manifested_source(secret.encode("utf-8"))
                result = archive_services.create_draft_zettel(
                    self.root,
                    dry_run=True,
                    **self.ai_kwargs(
                        object_id,
                        draft_id=f"zet_20260810_121_secret_{index}",
                        title=f"Credential shape {index}",
                    ),
                )
                serialized = json.dumps(result, ensure_ascii=False)
                self.assertIn("credential_secret_present", result["blockers"])
                self.assertNotIn(secret, serialized)
                self.assertNotIn(object_id, serialized)

    def test_product_vocabulary_is_not_a_credential_secret(self) -> None:
        object_id = self.manifested_source(
            b"Safe manifested source for ordinary product vocabulary."
        )
        phrases = (
            "GCP Secret Manager",
            "OAuth client",
            "Basic authentication",
            "cookie policy",
            "token budget",
            "Token: a unit of text processed by a language model.",
            "Password: must be stored in a password manager.",
            "Secret: information that should not be public.",
            "Credential: proof of identity used for authentication.",
            "Client secret: should be kept private.",
            "password: REDACTED",
            "token: <token>",
            'password: "REDACTED"',
            "token: |\n  REDACTED",
            "password: not configured",
            "token: null",
            "Authorization: Bearer <token>",
            "Authorization: Basic BASE64",
            '{"Authorization":"Basic BASE64"}',
            "Authorization: REDACTED",
            "Authorization: none",
            "curl -H 'Authorization: Basic BASE64' https://example.invalid",
            "curl --header='Cookie: sessionid=YOUR_SESSION_TOKEN' https://example.invalid",
            "headers = {'Authorization': 'Bearer <token>'}",
            "headers = {'Cookie': 'theme=dark'}",
            "Cookie: theme=dark",
            "Cookie: sidebar=expanded",
            "Cookie: consider=expanded",
            "Cookie: sessionid=REDACTED",
            "Cookie: sessionid=<SESSION_TOKEN>",
            "Cookie: sessionid=YOUR_SESSION_TOKEN",
            '{"Cookie":"lang=ko"}',
            "design_token=#12345678",
        )
        plain_colon_definitions = {
            "Token: a unit of text processed by a language model.",
            "Password: must be stored in a password manager.",
            "Secret: information that should not be public.",
            "Credential: proof of identity used for authentication.",
            "Client secret: should be kept private.",
        }
        exact_placeholder_assignments = {
            "password: REDACTED",
            "token: <token>",
            'password: "REDACTED"',
            "token: |\n  REDACTED",
            "password: not configured",
            "token: null",
        }
        for index, phrase in enumerate(phrases):
            with self.subTest(phrase=phrase):
                result = archive_services.create_draft_zettel(
                    self.root,
                    dry_run=True,
                    **self.ai_kwargs(
                        object_id,
                        draft_id=(
                            f"zet_20260810_121_product_vocabulary_{index}"
                        ),
                        title=f"Product vocabulary {index}",
                        body=(
                            f"{phrase}\nThe team reviewed the definition "
                            "as a product term.\n"
                            if phrase
                            in (
                                plain_colon_definitions
                                | exact_placeholder_assignments
                            )
                            else (
                                f"The team reviewed {phrase} as a product "
                                "term.\n"
                            )
                        ),
                    ),
                )
                self.assertTrue(result["ok"], result)
                self.assertNotIn(
                    "credential_secret_present", result["blockers"]
                )
        self.assertEqual(
            archive_services._source_fidelity_request_metadata_blockers(
                {
                    "headers": {
                        "Authorization": "Basic BASE64",
                        "Cookie": (
                            "theme=dark; lang=ko; sidebar=expanded; "
                            "consider=expanded"
                        ),
                    }
                }
            ),
            [],
        )

    def test_structured_header_collections_keep_header_context(self) -> None:
        secret_cases = (
            {"Authorization": ["Basic dTpw"]},
            {"Authorization": ["Token 0123456789abcdef"]},
            {
                "Set-Cookie": [
                    "theme=dark",
                    "JSESSIONID=ABCDEF1234567890",
                ]
            },
            [("Cookie", "JSESSIONID=ABCDEF1234567890")],
            ("Cookie", "JSESSIONID=ABCDEF1234567890"),
            ["Authorization", "Basic dTpw"],
            {"headers": ("Cookie", "JSESSIONID=ABCDEF1234567890")},
        )
        for case in secret_cases:
            with self.subTest(case_type=type(case).__name__):
                self.assertEqual(
                    archive_services._source_fidelity_request_metadata_blockers(
                        case
                    ),
                    ["credential_secret_present"],
                )

        self.assertEqual(
            archive_services._source_fidelity_request_metadata_blockers(
                {
                    "Authorization": ["Basic BASE64", "Bearer <token>"],
                    "Cookie": ["theme=dark", "sessionid=YOUR_SESSION_TOKEN"],
                }
            ),
            [],
        )

    def test_credential_secrets_in_ai_frontmatter_block_without_echo(self) -> None:
        object_id = self.manifested_source(
            b"Safe source body used to test frontmatter credential rejection."
        )
        cases = [
            {
                "title": "AKIAABCDEFGHIJKLMNOP",
            },
            {
                "facets": {
                    "private_value": (
                        "AWS_SECRET_ACCESS_KEY="
                        "abcdefghijklmnopqrstuvwx12345678"
                    )
                },
            },
            {
                "visibility": {
                    "scope": "private",
                    "source_visibility": "private",
                    "policy": "TOKEN=abcdefghijklmnopqrstuvwx12345678",
                },
            },
            {
                "facets": {
                    "headers": {
                        "Cookie": "sessionid=private-session-value"
                    }
                },
            },
            {
                "facets": {
                    "DB_PASSWORD": "P@ssw0rd!Abcdefgh"
                },
            },
            {
                "facets": {
                    "MY_CLIENT_SECRET": "aB3$xyz!987654321"
                },
            },
            {
                "facets": {
                    "GITHUB_TOKEN": "abcdefghijklmnop"
                },
            },
            {
                "facets": {
                    "headers": {
                        "Cookie": 'session="AbCdEf1234567890"'
                    }
                },
            },
            {
                "facets": {
                    "headers": {
                        "Authorization": (
                            "Basic dXNlcjpwYXNzd29yZA=="
                        )
                    }
                },
            },
            {
                "title": "AKIAABCDEFGHIJKLMNOP",
                "draft_id": None,
            },
        ]
        for index, mutation in enumerate(cases):
            with self.subTest(index=index):
                kwargs = self.ai_kwargs(
                    object_id,
                    draft_id=f"zet_20260810_121_frontmatter_secret_{index}",
                    title=f"Frontmatter secret {index}",
                )
                kwargs.update(mutation)
                result = archive_services.create_draft_zettel(
                    self.root, dry_run=True, **kwargs
                )
                serialized = json.dumps(result, ensure_ascii=False)
                self.assertIn("credential_secret_present", result["blockers"])
                for secret in (
                    "AKIAABCDEFGHIJKLMNOP",
                    "akiaabcdefghijklmnop",
                    "AWS_SECRET_ACCESS_KEY=abcdefghijklmnopqrstuvwx12345678",
                    "TOKEN=abcdefghijklmnopqrstuvwx12345678",
                    "sessionid=private-session-value",
                    'session="AbCdEf1234567890"',
                    "P@ssw0rd!Abcdefgh",
                    "aB3$xyz!987654321",
                    "Basic dXNlcjpwYXNzd29yZA==",
                ):
                    self.assertNotIn(secret, serialized)
                self.assertEqual(result["frontmatter_preview"], {})
                if mutation.get("draft_id", object()) is None:
                    self.assertIsNone(result["proposed_path"])
                    self.assertIsNone(result["approval_replay"]["draft_id"])

    def test_all_ai_request_metadata_failures_use_a_content_free_envelope(self) -> None:
        object_id = self.manifested_source(
            b"Safe source for request metadata privacy checks."
        )
        private_digest = object_id.removeprefix("sha256:")
        cases = [
            {
                "title": "AKIAABCDEFGHIJKLMNOP",
                "draft_id": None,
            },
            {
                "draft_approved_by": (
                    "sk-proj-exampleabcdefghijklmnopqrstuvwxyz"
                ),
            },
            {
                "profile_id": r"C:\Users\example\source.md",
            },
            {
                "expected_archive_id": (
                    "TOKEN=abcdefghijklmnopqrstuvwx12345678"
                ),
            },
            {
                "facets": {
                    "TOKEN=abcdefghijklmnopqrstuvwx12345678": "safe"
                },
            },
            {
                "facets": {r"C:\Users\example\source.md": "safe"},
            },
            {"draft_approved_by": private_digest},
            {
                "draft_approved_by": (
                    f"person:prefix-{private_digest}-suffix"
                )
            },
        ]
        private_values = (
            "AKIAABCDEFGHIJKLMNOP",
            "akiaabcdefghijklmnop",
            "sk-proj-exampleabcdefghijklmnopqrstuvwxyz",
            r"C:\Users\example\source.md",
            "TOKEN=abcdefghijklmnopqrstuvwx12345678",
            private_digest,
        )
        for index, mutation in enumerate(cases):
            with self.subTest(index=index):
                kwargs = self.ai_kwargs(
                    object_id,
                    draft_id=f"zet_20260810_121_request_private_{index}",
                    title=f"Request metadata privacy {index}",
                )
                kwargs.update(mutation)
                result = archive_services.create_draft_zettel(
                    self.root, dry_run=True, **kwargs
                )
                serialized = json.dumps(result, ensure_ascii=False)
                self.assertFalse(result["ok"])
                self.assertEqual(result["frontmatter_preview"], {})
                self.assertIsNone(result["proposed_path"])
                self.assertIsNone(result["approval_replay"]["draft_id"])
                self.assertEqual(result["warnings"], [])
                self.assertEqual(
                    result["input_privacy_check"],
                    {
                        "scope": "pre_write_caller_input_safety",
                        "performed": True,
                        "caller_supplied_input_read_for_safety": True,
                        "body_read_for_safety": True,
                        "input_values_echoed": False,
                        "blocked": True,
                        "reason_codes": result["blockers"],
                    },
                )
                self.assertFalse(
                    result["first_read_check"]["body_read_for_check"]
                )
                for private_value in private_values:
                    self.assertNotIn(private_value, serialized)

        public_citation = archive_services.create_draft_zettel(
            self.root,
            dry_run=True,
            **self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_public_citation",
                title="Public standards citation",
                body="Reference: https://www.w3.org/TR/prov-o/\n",
            ),
        )
        self.assertTrue(public_citation["ok"], public_citation)

    def test_mint_rejects_post_create_secrets_and_private_source_authority(self) -> None:
        source = (
            b"Safe manifested source for post-create metadata checks.\r\n"
        )
        object_id = self.manifested_source(source)
        private_digest = object_id.removeprefix("sha256:")
        normalized_digest = hashlib.sha256(
            source.replace(b"\r\n", b"\n")
        ).hexdigest()
        mutations = [
            ("title", "AKIAABCDEFGHIJKLMNOP"),
            (
                "facet",
                "TOKEN=abcdefghijklmnopqrstuvwx12345678",
            ),
            ("visibility", r"C:\Users\example\source.md"),
            ("object_id", object_id),
            ("raw_digest", private_digest),
            ("embedded_object_id", f"prefix {object_id} suffix"),
            ("embedded_raw_digest", f"prefix {private_digest} suffix"),
            ("normalized_digest", normalized_digest),
            (
                "embedded_normalized_digest",
                f"prefix {normalized_digest} suffix",
            ),
            ("uppercase_raw_digest", private_digest.upper()),
            (
                "draft_creation_extra",
                f"prefix {private_digest} suffix",
            ),
            (
                "dict_key_private_digest",
                f"prefix {private_digest} suffix",
            ),
            ("reviewer", private_digest),
        ]
        for index, (kind, private_value) in enumerate(mutations):
            with self.subTest(kind=kind):
                indexed = archive_services.index_archive(self.root)
                self.assertTrue(indexed["ok"], indexed)
                self.assertEqual(indexed["index_state"], "current")
                result = self.create_approved(
                    self.ai_kwargs(
                        object_id,
                        draft_id=(
                            f"zet_20260810_121_post_create_{index}"
                        ),
                        title=f"Post-create metadata {index}",
                    )
                )
                draft_path = self.root / result["path"]
                snapshot = archive_services._source_fidelity_raw_draft_snapshot(
                    self.root, draft_path
                )
                self.assertTrue(snapshot["ok"], snapshot)
                frontmatter = snapshot["frontmatter"]
                if kind == "title":
                    frontmatter["title"] = private_value
                elif kind == "facet":
                    frontmatter["facets"]["private_value"] = private_value
                elif kind == "visibility":
                    frontmatter["visibility"]["policy"] = private_value
                elif kind == "reviewer":
                    frontmatter["draft_creation"]["approved_by"] = (
                        private_value
                    )
                elif kind == "draft_creation_extra":
                    frontmatter["draft_creation"][
                        "unexpected_private_authority"
                    ] = private_value
                elif kind == "dict_key_private_digest":
                    frontmatter["facets"][private_value] = "safe"
                else:
                    frontmatter.setdefault("source_refs", []).append(
                        {"type": "object_id", "value": private_value}
                    )
                draft_path.write_bytes(
                    (
                        "---\n"
                        + archive_services.dump_yaml(frontmatter)
                        + "---\n\n"
                    ).encode("utf-8")
                    + snapshot["body_bytes"]
                )
                verification = archive_services._source_fidelity_verify_for_mint(
                    self.root, draft_path, affirmations=None
                )
                serialized = json.dumps(verification, ensure_ascii=False)
                self.assertFalse(verification["ok"], verification)
                expected = (
                    "source_fidelity_private_authority_exposed"
                    if kind
                    in {
                        "object_id",
                        "raw_digest",
                        "embedded_object_id",
                        "embedded_raw_digest",
                        "normalized_digest",
                        "embedded_normalized_digest",
                        "uppercase_raw_digest",
                        "draft_creation_extra",
                        "dict_key_private_digest",
                        "reviewer",
                    }
                    else (
                        "private_locator_or_path_present"
                        if kind == "visibility"
                        else "credential_secret_present"
                    )
                )
                self.assertIn(expected, verification["blockers"])
                self.assertNotIn(private_value, serialized)
                if kind == "title":
                    archive_services.index_archive(self.root)
                    outer = archive_services.mint_zettel_dry_run(
                        self.root, relative_path=result["path"]
                    )
                    outer_serialized = json.dumps(
                        outer, ensure_ascii=False
                    )
                    self.assertFalse(outer["ok"], outer)
                    self.assertIsNone(outer["title"])
                    self.assertIsNone(outer["draft_path"])
                    self.assertEqual(outer["would_change"], [])
                    self.assertNotIn(private_value, outer_serialized)
                    promoted = archive_services.promote_zettel_dry_run(
                        self.root, relative_path=result["path"]
                    )
                    promoted_serialized = json.dumps(
                        promoted, ensure_ascii=False
                    )
                    self.assertFalse(promoted["ok"], promoted)
                    self.assertIsNone(promoted["title"])
                    self.assertNotIn(private_value, promoted_serialized)

    def test_legacy_ai_credentials_block_even_with_attributed_affirmation(self) -> None:
        for index, location in enumerate(("body", "frontmatter")):
            with self.subTest(location=location):
                result = self.write_historical_human_draft(
                    title=f"Legacy credential blocker {index}",
                    body="Safe initial legacy draft body.",
                    abstract="A bounded legacy review fixture.",
                    facets={"record_type": "legacy_ai"},
                    created_by="person:legacy-fixture",
                    draft_id=f"zet_20260810_121_legacy_secret_{index}",
                    created_at=f"2026-08-10T12:4{index}:00+09:00",
                )
                path = self.root / result["path"]
                frontmatter, body = archive_services.require_readable_zettel_content(
                    path
                )
                frontmatter["provenance"].pop("creation_mode", None)
                frontmatter["provenance"]["created_by"] = (
                    "mcp:zettel-kasten-archive-mcp"
                )
                secret = "TOKEN=abcdefghijklmnopqrstuvwx12345678"
                if location == "frontmatter":
                    frontmatter["facets"]["private_value"] = secret
                else:
                    body = secret
                path.write_text(
                    "---\n"
                    + archive_services.dump_yaml(frontmatter)
                    + "---\n\n"
                    + body.rstrip()
                    + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                verification = archive_services._source_fidelity_verify_for_mint(
                    self.root,
                    path,
                    affirmations={
                        "legacy_source_fidelity_reviewed": "person:reviewer"
                    },
                )
                self.assertFalse(verification["ok"], verification)
                self.assertIn(
                    "credential_secret_present", verification["blockers"]
                )
                self.assertNotIn(
                    secret, json.dumps(verification, ensure_ascii=False)
                )

    def test_mint_uses_current_plan_and_preserves_raw_body_bytes(self) -> None:
        source_text = (
            "  Reviewed source leading spaces\n"
            "\tordered detail with trailing spaces  \n"
            "Human name and phone 010-1111-2222 😀 אבג\n\n\n"
        )
        object_id = self.manifested_source(source_text.encode("utf-8"))
        result = self.create_approved(
            self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_mint",
                title="Mint fidelity body preservation",
            )
        )
        affirmations = {
            "one_clear_purpose": "person:fidelity-test",
            "sensitive_content_reviewed": "person:fidelity-test",
        }
        archive_services.index_archive(self.root)
        dry = archive_services.mint_zettel_dry_run(
            self.root,
            relative_path=result["path"],
            affirmations=affirmations,
        )
        self.assertTrue(dry["ok"], dry)
        current_plan = dry["current_source_fidelity_plan_sha256"]
        self.assertRegex(current_plan, r"^[0-9a-f]{64}$")
        with self.assertRaises(archive_services.ArchiveServiceError):
            archive_services.mint_zettel(
                self.root,
                relative_path=result["path"],
                reviewed_by="person:fidelity-test",
                allow_warnings=True,
                affirmations=affirmations,
            )
        mint_binding = mint_zet_approval_binding(dry)
        minted = archive_services.mint_zettel(
            self.root,
            relative_path=result["path"],
            reviewed_by="person:fidelity-test",
            allow_warnings=True,
            affirmations=affirmations,
            expected_source_fidelity_plan_sha256=current_plan,
            expected_exact_approval_plan_sha256=mint_binding.plan_sha256,
            expected_exact_approval_target_binding_sha256=(
                mint_binding.target_binding_sha256
            ),
            exact_human_approval_claim=self.exact_claim(
                mint_binding.context(
                    archive_id="archive:personal:fidelity-test",
                    reviewer_claim="person:fidelity-test",
                )
            ),
        )
        self.assertTrue(minted["ok"], minted)
        canonical = self.root / minted["canonical_path"]
        canonical_snapshot = archive_services._source_fidelity_raw_draft_snapshot(
            self.root, canonical
        )
        self.assertTrue(canonical_snapshot["ok"], canonical_snapshot)
        self.assertEqual(
            canonical_snapshot["body_bytes"], source_text.encode("utf-8")
        )
        public_receipt = json.dumps(minted["receipt"], ensure_ascii=False)
        self.assertNotIn(object_id, public_receipt)
        self.assertNotIn(object_id.removeprefix("sha256:"), public_receipt)

    def test_manifested_object_drift_blocks_mint_verifier_with_provider_and_write_zero(self) -> None:
        source = b"Stable manifested source bytes for drift verification."
        object_id = self.manifested_source(source)
        result = self.create_approved(
            self.ai_kwargs(
                object_id,
                draft_id="zet_20260810_121_object_drift",
                title="Manifested object drift blocker",
            )
        )
        digest = object_id.removeprefix("sha256:")
        object_path = (
            self.root / "objects" / "sha256" / digest[:2] / digest
        )
        drifted = bytearray(source)
        drifted[-2] = ord("X")
        object_path.write_bytes(bytes(drifted))
        before = self.archive_file_snapshot()

        with patch.object(
            archive_services.urllib.request,
            "urlopen",
            side_effect=AssertionError("provider access is forbidden"),
        ):
            verification = archive_services._source_fidelity_verify_for_mint(
                self.root,
                self.root / result["path"],
                affirmations=None,
            )

        self.assertFalse(verification["ok"], verification)
        self.assertIn(
            "source_fidelity_object_digest_mismatch",
            verification["blockers"],
        )
        self.assertEqual(self.archive_file_snapshot(), before)
        self.assertFalse(
            (
                self.root
                / "zettels"
                / "zet_20260810_121_object_drift.md"
            ).exists()
        )
        self.assertFalse(
            (
                self.root
                / "receipts"
                / "mint"
                / "zet_20260810_121_object_drift.mint.json"
            ).exists()
        )

    def test_verbatim_region_one_character_delete_or_change_blocks_without_mint_writes(self) -> None:
        for mutation in ("delete", "change"):
            with self.subTest(mutation=mutation):
                source = (
                    f"Exact verbatim region for {mutation} mutation."
                ).encode("utf-8")
                object_id = self.manifested_source(source)
                draft_id = f"zet_20260810_121_region_{mutation}"
                result = self.create_approved(
                    self.ai_kwargs(
                        object_id,
                        draft_id=draft_id,
                        title=f"Region {mutation} blocker",
                    )
                )
                draft_path = self.root / result["path"]
                snapshot = archive_services._source_fidelity_raw_draft_snapshot(
                    self.root, draft_path
                )
                self.assertTrue(snapshot["ok"], snapshot)
                source_offset = snapshot["body_bytes"].index(source)
                absolute_offset = snapshot["body_start"] + source_offset + 7
                raw = snapshot["raw"]
                if mutation == "delete":
                    mutated = raw[:absolute_offset] + raw[absolute_offset + 1 :]
                else:
                    replacement = (
                        b"X"
                        if raw[absolute_offset : absolute_offset + 1] != b"X"
                        else b"Y"
                    )
                    mutated = (
                        raw[:absolute_offset]
                        + replacement
                        + raw[absolute_offset + 1 :]
                    )
                draft_path.write_bytes(mutated)
                before = self.archive_file_snapshot()

                with patch.object(
                    archive_services.urllib.request,
                    "urlopen",
                    side_effect=AssertionError("provider access is forbidden"),
                ):
                    verification = archive_services.mint_zettel_dry_run(
                        self.root,
                        relative_path=result["path"],
                    )

                self.assertFalse(verification["ok"], verification)
                self.assertIn(
                    "source_fidelity_region_mismatch",
                    verification["blockers"],
                )
                self.assertEqual(self.archive_file_snapshot(), before)
                self.assertFalse(
                    (self.root / "zettels" / f"{draft_id}.md").exists()
                )
                self.assertFalse(
                    (
                        self.root
                        / "receipts"
                        / "mint"
                        / f"{draft_id}.mint.json"
                    ).exists()
                )

    def test_duplicate_yaml_or_private_receipt_json_keys_fail_closed_without_echo(self) -> None:
        private_canary = "PRIVATE_DUPLICATE_KEY_CANARY_121"
        for duplicate_kind in (
            "draft_yaml",
            "draft_projection_unknown",
            "receipt_json",
            "receipt_unknown_field",
            "receipt_content_contract_true",
            "receipt_source_flag_true",
            "receipt_region_shape_invalid",
        ):
            with self.subTest(duplicate_kind=duplicate_kind):
                object_id = self.manifested_source(
                    (private_canary + " " + duplicate_kind).encode("utf-8")
                )
                draft_id = f"zet_20260810_121_duplicate_{duplicate_kind}"
                result = self.create_approved(
                    self.ai_kwargs(
                        object_id,
                        draft_id=draft_id,
                        title=f"Duplicate key {duplicate_kind}",
                    )
                )
                draft_path = self.root / result["path"]
                expected_blocker: str
                if duplicate_kind == "draft_yaml":
                    raw = draft_path.read_bytes()
                    self.assertTrue(raw.startswith(b"---\n"))
                    draft_path.write_bytes(
                        b"---\nid: zet_duplicate_shadow\n" + raw[4:]
                    )
                    expected_blocker = (
                        "source_fidelity_legacy_boundary_invalid"
                    )
                elif duplicate_kind == "draft_projection_unknown":
                    snapshot = archive_services._source_fidelity_raw_draft_snapshot(
                        self.root, draft_path
                    )
                    self.assertTrue(snapshot["ok"], snapshot)
                    frontmatter = snapshot["frontmatter"]
                    frontmatter["source_fidelity"][
                        "unexpected_private_field"
                    ] = private_canary
                    draft_path.write_bytes(
                        (
                            "---\n"
                            + archive_services.dump_yaml(frontmatter)
                            + "---\n\n"
                        ).encode("utf-8")
                        + snapshot["body_bytes"]
                    )
                    expected_blocker = (
                        "source_fidelity_private_receipt_projection_mismatch"
                    )
                elif duplicate_kind == "receipt_json":
                    receipt_path = (
                        self.root
                        / result["source_fidelity_draft_receipt_path"]
                    )
                    receipt_text = receipt_path.read_text(encoding="utf-8")
                    receipt_path.write_text(
                        receipt_text.replace(
                            "{\n",
                            "{\n  \"schema\": "
                            "\"wom-kit/source-fidelity-draft-receipt/v0.1\",\n",
                            1,
                        ),
                        encoding="utf-8",
                        newline="\n",
                    )
                    expected_blocker = (
                        "source_fidelity_private_receipt_invalid"
                    )
                else:
                    receipt_path = (
                        self.root
                        / result["source_fidelity_draft_receipt_path"]
                    )
                    receipt = json.loads(
                        receipt_path.read_text(encoding="utf-8")
                    )
                    if duplicate_kind == "receipt_unknown_field":
                        receipt["unexpected_private_field"] = private_canary
                    elif duplicate_kind == "receipt_content_contract_true":
                        receipt["content_contract"]["source_text_stored"] = True
                    elif duplicate_kind == "receipt_source_flag_true":
                        receipt["source_fidelity"]["source"][
                            "source_text_stored"
                        ] = True
                    else:
                        receipt["source_fidelity"]["region"][
                            "offset_bytes"
                        ] = True
                    receipt_path.write_text(
                        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    expected_blocker = (
                        "source_fidelity_private_receipt_schema_invalid"
                    )
                before = self.archive_file_snapshot()

                with patch.object(
                    archive_services.urllib.request,
                    "urlopen",
                    side_effect=AssertionError("provider access is forbidden"),
                ):
                    verification = archive_services.mint_zettel_dry_run(
                        self.root,
                        relative_path=result["path"],
                    )

                self.assertFalse(verification["ok"], verification)
                self.assertIn(expected_blocker, verification["blockers"])
                serialized = json.dumps(verification, ensure_ascii=False)
                self.assertNotIn(private_canary, serialized)
                self.assertNotIn(object_id, serialized)
                self.assertNotIn(
                    object_id.removeprefix("sha256:"), serialized
                )
                self.assertEqual(self.archive_file_snapshot(), before)
                self.assertFalse(
                    (self.root / "zettels" / f"{draft_id}.md").exists()
                )
                self.assertFalse(
                    (
                        self.root
                        / "receipts"
                        / "mint"
                        / f"{draft_id}.mint.json"
                    ).exists()
                )

    def test_receipt_review_and_fidelity_authority_tamper_fail_closed(self) -> None:
        for index, tamper_kind in enumerate(("reviewer", "newline_flag")):
            with self.subTest(tamper_kind=tamper_kind):
                object_id = self.manifested_source(
                    (
                        "Receipt authority fixture with CRLF.\r\n"
                        + tamper_kind
                    ).encode("utf-8")
                )
                result = self.create_approved(
                    self.ai_kwargs(
                        object_id,
                        draft_id=f"zet_20260810_121_receipt_tamper_{index}",
                        title=f"Receipt authority tamper {index}",
                    )
                )
                draft_path = self.root / result["path"]
                receipt_path = (
                    self.root
                    / result["source_fidelity_draft_receipt_path"]
                )
                receipt = json.loads(
                    receipt_path.read_text(encoding="utf-8")
                )
                self.assertNotIn("draft_sha256", receipt)
                self.assertRegex(
                    receipt["review_binding_sha256"], r"^[0-9a-f]{64}$"
                )
                snapshot = archive_services._source_fidelity_raw_draft_snapshot(
                    self.root, draft_path
                )
                self.assertTrue(snapshot["ok"], snapshot)
                frontmatter = snapshot["frontmatter"]
                if tamper_kind == "reviewer":
                    receipt["reviewed_by"] = "person:forged-reviewer"
                    frontmatter["draft_creation"]["approved_by"] = (
                        "person:forged-reviewer"
                    )
                    expected_blocker = (
                        "source_fidelity_review_binding_invalid"
                    )
                else:
                    source_authority = receipt["source_fidelity"]["source"]
                    source_authority["newline_transformation_applied"] = not (
                        source_authority["newline_transformation_applied"]
                    )
                    forged_evidence_id = (
                        "source-fidelity-evidence:" + "f" * 24
                    )
                    receipt["source_fidelity"]["evidence_id"] = (
                        forged_evidence_id
                    )
                    frontmatter["source_fidelity"]["evidence_id"] = (
                        forged_evidence_id
                    )
                    expected_blocker = (
                        "source_fidelity_creation_plan_tampered"
                    )
                receipt_path.write_text(
                    json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                draft_path.write_bytes(
                    (
                        "---\n"
                        + archive_services.dump_yaml(frontmatter)
                        + "---\n\n"
                    ).encode("utf-8")
                    + snapshot["body_bytes"]
                )
                verification = archive_services._source_fidelity_verify_for_mint(
                    self.root, draft_path, affirmations=None
                )
                self.assertFalse(verification["ok"], verification)
                self.assertIn(expected_blocker, verification["blockers"])

    def test_create_only_writer_stream_verifies_without_path_read_bytes(self) -> None:
        target = self.root / "receipts" / "writer-regression.bin"
        payload = b"x" * (2 * 1024 * 1024 + 17)
        with patch.object(
            Path,
            "read_bytes",
            side_effect=AssertionError("read_bytes must not be used"),
        ):
            archive_services._write_bytes_create_if_absent(target, payload)
        with target.open("rb") as handle:
            self.assertEqual(hashlib.sha256(handle.read()).digest(), hashlib.sha256(payload).digest())


if __name__ == "__main__":
    unittest.main()
