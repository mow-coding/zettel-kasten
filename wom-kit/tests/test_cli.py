from __future__ import annotations

import io
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import unicodedata
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
PROMOTION_CHECKLIST_IDS = [
    "one_clear_purpose",
    "understandable_title",
    "future_self_contained",
    "source_clarity",
    "object_id_only",
    "stable_facets",
    "allowed_edges",
    "explicit_visibility",
    "provenance_present",
    "sensitive_content_reviewed",
]

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, archive_services


class ArchiveCliTests(unittest.TestCase):
    def run_cli(self, args: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = archive_cli.main(args)
        return code, buffer.getvalue()

    def init_personal_archive(self, root: Path, archive_id: str = "archive:personal:test") -> tuple[int, str]:
        return self.run_cli(
            [
                "init",
                str(root),
                "--type",
                "personal",
                "--archive-id",
                archive_id,
                "--principal-id",
                "person:test",
                "--principal-name",
                "Test Person",
                "--name",
                "Test Personal Archive",
            ]
        )

    def init_transfer_ready_family_archive(self, root: Path) -> Path:
        code, output = self.run_cli(
            [
                "init",
                str(root),
                "--type",
                "family",
                "--archive-id",
                "archive:family:example-household",
                "--principal-id",
                "family:example-household",
                "--principal-kind",
                "family",
                "--principal-name",
                "Example Household",
                "--name",
                "Example Household Archive",
            ]
        )
        self.assertEqual(code, 0, output)
        identity_path = root / "archive-identity.yml"
        identity = archive_cli.load_yaml(identity_path.read_text(encoding="utf-8"))
        identity["trusted_counterparties"].append(
            {
                "identity_id": "identity:archive:child:example-child",
                "archive_id": "archive:child:example-child",
                "principal_id": "person:child-template",
                "expected_fingerprint": "SHA256:example-child-primary",
                "trust_level": "out_of_band_verified",
            }
        )
        identity_path.write_text(archive_cli.dump_yaml(identity), encoding="utf-8")
        return root

    def init_transfer_ready_business_unit_archive(self, root: Path) -> Path:
        code, output = self.run_cli(
            [
                "init",
                str(root),
                "--type",
                "company",
                "--archive-id",
                "archive:business_unit:fake-space",
                "--principal-id",
                "business_unit:fake-space",
                "--principal-kind",
                "project",
                "--principal-name",
                "Fake Space Business Unit",
                "--name",
                "Fake Space Business Unit Archive",
            ]
        )
        self.assertEqual(code, 0, output)

        archive_path = root / "archive.yml"
        archive_data = archive_cli.load_yaml(archive_path.read_text(encoding="utf-8"))
        archive_data["type"] = "business_unit"
        archive_data["principal"]["kind"] = "business_unit"
        archive_path.write_text(archive_cli.dump_yaml(archive_data), encoding="utf-8")

        identity_path = root / "archive-identity.yml"
        identity = archive_cli.load_yaml(identity_path.read_text(encoding="utf-8"))
        identity["identity"]["scope"] = "business_unit"
        identity["identity"]["principal_id"] = "business_unit:fake-space"
        identity["identity"]["display_name"] = "Fake Space Business Unit"
        identity["ownership"] = {
            "owner_id": "company:fake-blue",
            "owner_kind": "company",
            "owner_display_name": "Fake Blue Company",
            "owner_archive_id": "archive:company:fake-blue",
            "operators": [
                {
                    "operator_id": "role:business-unit-admin",
                    "role": "business_unit_operator",
                    "permissions": ["capture", "curate", "approve", "transfer_request"],
                },
                {
                    "operator_id": "person:fake-founder",
                    "role": "founder_operator",
                    "permissions": ["capture", "curate", "approve", "transfer_request"],
                },
            ],
            "subjects": [
                {
                    "subject_id": "business_unit:fake-space",
                    "relationship": "business_unit_subject",
                }
            ],
            "transfer_policy": {
                "ownership_transfer_allowed": True,
                "requires_human_approval": True,
                "requires_receipt": True,
                "receipt_action": "transfer_archive_ownership",
                "default_transfer_target": "company:fake-spinout",
            },
        }
        identity["trusted_counterparties"].append(
            {
                "identity_id": "identity:archive:company:fake-spinout",
                "archive_id": "archive:company:fake-spinout",
                "principal_id": "company:fake-spinout",
                "expected_fingerprint": "SHA256:fake-spinout-primary",
                "trust_level": "out_of_band_verified",
            }
        )
        identity_path.write_text(archive_cli.dump_yaml(identity), encoding="utf-8")
        return root

    def copy_fake_archive(self, root: Path) -> Path:
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    def write_profile_registry(self, path: Path, profiles: list[dict], default_profile: str = "profile:personal:me") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            archive_cli.dump_yaml(
                {
                    "version": "wom-profile-registry/v0.1",
                    "default_profile": default_profile,
                    "profiles": profiles,
                }
            ),
            encoding="utf-8",
        )
        return path

    def example_profiles(self, personal_root: str = "<local-private-path>/personal") -> list[dict]:
        return [
            {
                "profile_id": "profile:personal:me",
                "label": "Personal archive",
                "aliases": ["me", "personal", "내 개인"],
                "node_id": "person:me",
                "archive_id": "archive:personal:me",
                "archive_type": "personal",
                "archive_root": personal_root,
                "operator_id": "person:me",
                "authority_mode": "owner_operator",
                "token": {"state": "present", "token_ref": "local-keyring:wom/profile/example-personal"},
            },
            {
                "profile_id": "profile:team:younghee-chulsoo",
                "label": "영희 & 철수 팀",
                "aliases": ["영희 철수 팀", "영희&철수", "우리 팀"],
                "node_id": "team:younghee-chulsoo",
                "archive_id": "archive:team:younghee-chulsoo",
                "archive_type": "project",
                "archive_root": "<local-private-path>/younghee-chulsoo-team",
                "operator_id": "person:me",
                "authority_mode": "draft_only",
                "token": {"state": "missing"},
            },
        ]

    def snapshot_archive_files(self, archive_root: Path) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for path in sorted(item for item in archive_root.rglob("*") if item.is_file()):
            snapshot[path.relative_to(archive_root).as_posix()] = path.read_text(encoding="utf-8")
        return snapshot

    def copy_fake_archive_as_company_target(self, root: Path) -> Path:
        archive_root = self.copy_fake_archive(root)
        archive_path = archive_root / "archive.yml"
        archive_data = archive_cli.load_yaml(archive_path.read_text(encoding="utf-8"))
        archive_data["archive_id"] = "archive:company:fake-blue"
        archive_data["name"] = "Fake Blue Target Archive"
        archive_data["type"] = "company"
        archive_path.write_text(archive_cli.dump_yaml(archive_data), encoding="utf-8")

        identity_path = archive_root / "archive-identity.yml"
        identity = archive_cli.load_yaml(identity_path.read_text(encoding="utf-8"))
        identity["identity"]["archive_id"] = "archive:company:fake-blue"
        identity["identity"]["identity_id"] = "identity:archive:company:fake-blue"
        identity["identity"]["scope"] = "company"
        identity["identity"]["principal_id"] = "company:fake-blue"
        identity["identity"]["display_name"] = "Fake Blue Company"
        identity["ownership"]["owner_id"] = "company:fake-blue"
        identity["ownership"]["owner_kind"] = "company"
        identity["ownership"]["owner_display_name"] = "Fake Blue Company"
        identity["ownership"]["owner_archive_id"] = "archive:company:fake-blue"
        identity["trusted_counterparties"].append(
            {
                "identity_id": "identity:archive:personal:fake-life",
                "archive_id": "archive:personal:fake-life",
                "principal_id": "person:fake-user",
                "expected_fingerprint": "SHA256:fake-user-primary",
                "trust_level": "out_of_band_verified",
            }
        )
        identity_path.write_text(archive_cli.dump_yaml(identity), encoding="utf-8")
        return archive_root

    def write_json_receipt(self, archive_root: Path, relative_path: str, payload: dict) -> Path:
        path = archive_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def make_fake_lunch_draft_promotion_ready(self, archive_root: Path, title: str = "Promotion-ready lunch note") -> Path:
        path = archive_root / "inbox" / "zet_20260519_draft_ai_lunch_note.md"
        text = path.read_text(encoding="utf-8")
        match = archive_cli.FRONTMATTER_RE.match(text)
        self.assertIsNotNone(match)
        assert match is not None
        frontmatter = archive_cli.load_yaml(match.group(1))
        body = text[match.end() :].lstrip()
        frontmatter["title"] = title
        frontmatter["kind"] = "permanent_note"
        frontmatter["promotion"] = {
            "stage": "promotion_candidate",
            "ready_for_promotion": True,
            "checklist": {item_id: True for item_id in PROMOTION_CHECKLIST_IDS},
        }
        path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")
        return path

    def test_doctor_fake_life_archive_passes_strict(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["doctor", str(archive_root), "--strict"])
        self.assertEqual(code, 0, output)
        self.assertIn("0 error(s), 0 warning(s)", output)

    def test_profile_list_reads_example_registry_and_redacts_paths(self) -> None:
        registry = KIT_ROOT / "templates" / "profiles" / "wom-profiles.example.yml"
        code, output = self.run_cli(["profile-list", "--registry", str(registry), "--format", "json"])

        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["lifecycle_action"], "profile_list")
        self.assertEqual(result["registry_path"], "<local-path-redacted>")
        self.assertEqual(result["default_profile"], "profile:personal:me")
        self.assertEqual(len(result["profiles"]), 2)
        self.assertEqual(result["profiles"][0]["archive_root"], "<local-path-redacted>")
        self.assertEqual(result["profiles"][0]["token_state"], "present")
        self.assertEqual(result["profiles"][1]["token_state"], "missing")
        self.assertNotIn("token_ref", json.dumps(result))

    def test_profile_resolve_exact_profile_id_match_succeeds(self) -> None:
        registry = KIT_ROOT / "templates" / "profiles" / "wom-profiles.example.yml"
        code, output = self.run_cli(
            [
                "profile-resolve",
                "--registry",
                str(registry),
                "--target",
                "profile:personal:me",
                "--format",
                "json",
            ]
        )

        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution_state"], "resolved")
        self.assertEqual(result["selected_profile"]["profile_id"], "profile:personal:me")
        self.assertTrue(result["direct_write_available"])
        self.assertEqual(result["suggested_next_action"], "run_runtime_context")
        self.assertEqual(result["runtime_context_args_preview"]["expected_archive_id"], "archive:personal:me")
        self.assertEqual(result["runtime_context_args_preview"]["expected_type"], "personal")
        self.assertEqual(result["runtime_context_args_preview"]["archive_root"], "<local-path-redacted>")

    def test_profile_resolve_exact_label_and_alias_match_succeed(self) -> None:
        registry = KIT_ROOT / "templates" / "profiles" / "wom-profiles.example.yml"
        label_code, label_output = self.run_cli(
            ["profile-resolve", "--registry", str(registry), "--target", "Personal archive", "--format", "json"]
        )
        alias_code, alias_output = self.run_cli(
            ["profile-resolve", "--registry", str(registry), "--target", "PERSONAL", "--format", "json"]
        )

        self.assertEqual(label_code, 0, label_output)
        self.assertEqual(alias_code, 0, alias_output)
        self.assertEqual(json.loads(label_output)["matches"][0]["match_type"], "label")
        self.assertEqual(json.loads(alias_output)["matches"][0]["match_type"], "alias")

    def test_profile_resolve_normalizes_korean_label_and_alias_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            decomposed_alias = unicodedata.normalize("NFD", "영희&철수")
            registry = self.write_profile_registry(
                Path(tmp) / "profiles.yml",
                [{**self.example_profiles()[1], "aliases": [decomposed_alias], "token": {"state": "present"}}],
                default_profile="profile:team:younghee-chulsoo",
            )

            code, output = self.run_cli(
                ["profile-resolve", "--registry", str(registry), "--target", "\u200b영희&철수", "--format", "json"]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["resolution_state"], "resolved")
            self.assertEqual(result["selected_profile"]["profile_id"], "profile:team:younghee-chulsoo")

    def test_profile_resolve_ambiguous_match_returns_ambiguous_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = self.write_profile_registry(
                Path(tmp) / "profiles.yml",
                [
                    {**self.example_profiles()[0], "aliases": ["shared"]},
                    {**self.example_profiles()[1], "aliases": ["shared"], "token": {"state": "present"}},
                ],
            )

            code, output = self.run_cli(["profile-resolve", "--registry", str(registry), "--target", "shared", "--format", "json"])

            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertEqual(result["resolution_state"], "ambiguous")
            self.assertEqual(result["suggested_next_action"], "ask_user_to_choose_profile")
            self.assertEqual(len(result["matches"]), 2)

    def test_profile_resolve_missing_target_suggests_delegate_or_registration(self) -> None:
        registry = KIT_ROOT / "templates" / "profiles" / "wom-profiles.example.yml"
        code, output = self.run_cli(
            ["profile-resolve", "--registry", str(registry), "--target", "unknown target", "--format", "json"]
        )

        result = json.loads(output)
        self.assertEqual(code, 1, output)
        self.assertFalse(result["ok"])
        self.assertEqual(result["resolution_state"], "not_found")
        self.assertEqual(result["suggested_next_action"], "suggest_delegate_flow")
        self.assertIn("register the profile", result["warnings"][0])
        self.assertEqual(result["delegate_fallback_preview"]["reason"], "target_profile_not_found")

    def test_profile_resolve_token_missing_disables_direct_write(self) -> None:
        registry = KIT_ROOT / "templates" / "profiles" / "wom-profiles.example.yml"
        code, output = self.run_cli(
            ["profile-resolve", "--registry", str(registry), "--target", "영희&철수", "--format", "json"]
        )

        result = json.loads(output)
        self.assertEqual(code, 0, output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["resolution_state"], "token_missing")
        self.assertFalse(result["direct_write_available"])
        self.assertEqual(result["suggested_next_action"], "register_profile_token")
        self.assertEqual(result["delegate_fallback_preview"]["reason"], "profile_token_missing")
        self.assertEqual(result["target_archive_context_preview"]["archive_type"], "project")

    def test_profile_list_no_redact_local_paths_exposes_paths_in_cli_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = str((Path(tmp) / "personal-archive").resolve())
            registry = self.write_profile_registry(Path(tmp) / "profiles.yml", self.example_profiles(archive_root))

            code, output = self.run_cli(
                ["profile-list", "--registry", str(registry), "--no-redact-local-paths", "--format", "json"]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertFalse(result["redaction"]["local_paths_redacted"])
            self.assertEqual(result["registry_path"], str(registry.resolve()))
            self.assertEqual(result["profiles"][0]["archive_root"], archive_root)

    def test_profile_registry_commands_write_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = self.write_profile_registry(Path(tmp) / "profiles.yml", self.example_profiles())
            before = {
                path.relative_to(tmp).as_posix(): path.read_text(encoding="utf-8")
                for path in sorted(Path(tmp).rglob("*"))
                if path.is_file()
            }

            list_code, list_output = self.run_cli(["profile-list", "--registry", str(registry), "--format", "json"])
            resolve_code, resolve_output = self.run_cli(
                ["profile-resolve", "--registry", str(registry), "--target", "personal", "--format", "json"]
            )

            after = {
                path.relative_to(tmp).as_posix(): path.read_text(encoding="utf-8")
                for path in sorted(Path(tmp).rglob("*"))
                if path.is_file()
            }
            self.assertEqual(list_code, 0, list_output)
            self.assertEqual(resolve_code, 0, resolve_output)
            self.assertEqual(after, before)

    def test_profile_registry_version_mismatch_blocks_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = self.write_profile_registry(Path(tmp) / "profiles.yml", self.example_profiles())
            data = archive_cli.load_yaml(registry.read_text(encoding="utf-8"))
            data["version"] = "wom-profile-registry/v9"
            registry.write_text(archive_cli.dump_yaml(data), encoding="utf-8")

            code, output = self.run_cli(["profile-list", "--registry", str(registry), "--format", "json"])

            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("version must be wom-profile-registry/v0.1" in item for item in result["blockers"]))

    def test_profile_registry_blocks_raw_token_values_and_duplicate_profile_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_token_profile = {
                **self.example_profiles()[0],
                "token": {
                    "state": "present",
                    "token_ref": "local-keyring:wom/profile/example-personal",
                    "value": "example-raw-token-value",
                },
            }
            duplicate_profile = {**self.example_profiles()[1], "profile_id": "profile:personal:me"}
            registry = self.write_profile_registry(Path(tmp) / "profiles.yml", [raw_token_profile, duplicate_profile])

            code, output = self.run_cli(["profile-list", "--registry", str(registry), "--format", "json"])

            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("raw secret-like" in item for item in result["blockers"]))
            self.assertTrue(any("unsupported field" in item for item in result["blockers"]))
            self.assertTrue(any("duplicate profile_id" in item for item in result["blockers"]))
            self.assertNotIn("example-raw-token-value", output)

    def test_runtime_context_returns_deterministic_redacted_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            args = ["runtime-context", str(archive_root), "--format", "json"]
            first_code, first_output = self.run_cli(args)
            second_code, second_output = self.run_cli(args)

            self.assertEqual(first_code, 0, first_output)
            self.assertEqual(second_code, 0, second_output)
            self.assertEqual(json.loads(first_output), json.loads(second_output))
            self.assertNotIn(str(archive_root), first_output)

            result = json.loads(first_output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["lifecycle_action"], "runtime_context")
            self.assertEqual(result["archive_id"], "archive:personal:fake-life")
            self.assertEqual(result["archive_type"], "personal")
            self.assertEqual(result["scope"], "personal")
            self.assertEqual(
                result["paths"],
                {
                    "inbox": "inbox/",
                    "zettels": "zettels/",
                    "receipts": "receipts/",
                    "object_manifest": "objects/manifests/files.jsonl",
                },
            )
            self.assertTrue(result["redaction"]["local_paths_redacted"])
            self.assertNotIn("local_archive_root", result)
            self.assertNotIn("local_paths", result)
            self.assertIn("create draft in inbox", result["available_safe_actions"])
            self.assertIn("mint only through CLI approve path", result["available_safe_actions"])

    def test_runtime_context_expected_archive_id_mismatch_blocks(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "runtime-context",
                str(archive_root),
                "--expected-archive-id",
                "archive:personal:wrong",
                "--format",
                "json",
            ]
        )
        result = json.loads(output)
        self.assertEqual(code, 1, output)
        self.assertFalse(result["ok"])
        self.assertIn("Expected archive id archive:personal:wrong", result["blockers"][0])

    def test_runtime_context_expected_type_mismatch_warns_by_default_and_blocks_in_strict(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"

        default_code, default_output = self.run_cli(
            ["runtime-context", str(archive_root), "--expected-type", "company", "--format", "json"]
        )
        default_result = json.loads(default_output)
        self.assertEqual(default_code, 0, default_output)
        self.assertTrue(default_result["ok"])
        self.assertEqual(default_result["blockers"], [])
        self.assertIn("Expected archive type company", default_result["warnings"][0])

        strict_code, strict_output = self.run_cli(
            ["runtime-context", str(archive_root), "--expected-type", "company", "--strict", "--format", "json"]
        )
        strict_result = json.loads(strict_output)
        self.assertEqual(strict_code, 1, strict_output)
        self.assertFalse(strict_result["ok"])
        self.assertIn("Expected archive type company", strict_result["blockers"][0])

    def test_runtime_context_writes_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            before = self.snapshot_archive_files(archive_root)

            code, output = self.run_cli(["runtime-context", str(archive_root), "--format", "json"])

            self.assertEqual(code, 0, output)
            self.assertEqual(self.snapshot_archive_files(archive_root), before)

    def test_github_repo_dry_run_generates_default_private_repo_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            before = self.snapshot_archive_files(archive_root)

            code, output = self.run_cli(
                [
                    "github-repo",
                    str(archive_root),
                    "--dry-run",
                    "--profile-id",
                    "profile:personal:HongGilDong",
                    "--profile-slug",
                    "HongGilDong",
                    "--github-owner",
                    "example-user",
                    "--github-account-ref",
                    "github:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["lifecycle_action"], "github_repository_setup_plan")
            self.assertEqual(result["proposed_repo_name"], "zettel-kasten-HongGilDong")
            self.assertEqual(result["proposed_visibility"], "private")
            self.assertEqual(result["proposed_remote_protocol"], "ssh")
            self.assertFalse(result["provider_setup_receipt_preview"]["external_actions"]["github_api_called"])
            self.assertEqual(self.snapshot_archive_files(archive_root), before)

    def test_github_repo_invalid_slugs_and_unsafe_repo_names_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            common = [
                "github-repo",
                str(archive_root),
                "--dry-run",
                "--profile-id",
                "profile:personal:test",
                "--github-owner",
                "example-user",
                "--github-account-ref",
                "github:account:test",
                "--format",
                "json",
            ]

            for bad_slug in ["bad slug", "../bad", "person@example.com", "https-token", "secret-slug"]:
                with self.subTest(slug=bad_slug):
                    code, output = self.run_cli(common + ["--profile-slug", bad_slug])
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("profile_slug" in blocker for blocker in result["blockers"]))

            for bad_repo in ["wrong-HongGilDong", "zettel-kasten-Hong/GilDong", "zettel-kasten-Hong GilDong", "zettel-kasten-" + "a" * 90]:
                with self.subTest(repo=bad_repo):
                    code, output = self.run_cli(common + ["--profile-slug", "HongGilDong", "--repo-name", bad_repo])
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("repo_name" in blocker for blocker in result["blockers"]))

    def test_github_repo_rejects_unsafe_owner_and_account_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            common = [
                "github-repo",
                str(archive_root),
                "--dry-run",
                "--profile-id",
                "profile:personal:test",
                "--profile-slug",
                "HongGilDong",
                "--format",
                "json",
            ]

            for bad_owner in ["bad/owner", "person@example.com", "https://example.com", "secret-owner"]:
                with self.subTest(owner=bad_owner):
                    code, output = self.run_cli(
                        common + ["--github-owner", bad_owner, "--github-account-ref", "github:account:test"]
                    )
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("github_owner" in blocker for blocker in result["blockers"]))

            for bad_ref in [
                "person@example.com",
                "https://example.com/private",
                "example.com",
                "http:foo",
                "../secret",
                "secret-account",
            ]:
                with self.subTest(account_ref=bad_ref):
                    code, output = self.run_cli(
                        common + ["--github-owner", "example-user", "--github-account-ref", bad_ref]
                    )
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("github_account_ref" in blocker for blocker in result["blockers"]))

    def test_github_repo_non_ascii_profile_without_explicit_slug_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "github-repo",
                    str(archive_root),
                    "--dry-run",
                    "--profile-id",
                    "profile:personal:홍길동",
                    "--github-owner",
                    "example-user",
                    "--github-account-ref",
                    "github:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Non-ASCII" in blocker for blocker in result["blockers"]))

    def test_github_repo_approve_requires_reviewed_by(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "github-repo",
                    str(archive_root),
                    "--approve",
                    "--profile-id",
                    "profile:personal:HongGilDong",
                    "--profile-slug",
                    "HongGilDong",
                    "--github-owner",
                    "example-user",
                    "--github-account-ref",
                    "github:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            self.assertEqual(code, 1)
            self.assertIn("--reviewed-by", output)

    def test_github_repo_approve_writes_only_local_metadata_and_doctor_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:github-plan")
            self.assertEqual(init_code, 0, init_output)
            before = self.snapshot_archive_files(archive_root)

            code, output = self.run_cli(
                [
                    "github-repo",
                    str(archive_root),
                    "--approve",
                    "--reviewed-by",
                    "person:me",
                    "--write-local-profile",
                    "--profile-id",
                    "profile:personal:HongGilDong",
                    "--profile-slug",
                    "HongGilDong",
                    "--github-owner",
                    "example-user",
                    "--github-account-ref",
                    "github:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertFalse(result["dry_run"])
            self.assertFalse(result["github_api_called"])
            self.assertFalse(result["github_repository_created"])
            self.assertFalse(result["git_remote_configured"])
            self.assertFalse(result["git_push_performed"])
            self.assertFalse((archive_root / ".git").exists())
            self.assertEqual(
                set(result["changed_paths"]),
                {
                    "provider-bindings.yml",
                    "receipts/providers/zettel_kasten_honggildong.github-repository-setup.json",
                    "profiles/local/github-accounts.local.yml",
                },
            )
            after = self.snapshot_archive_files(archive_root)
            changed = {path for path in after if before.get(path) != after[path]} | {path for path in before if path not in after}
            self.assertEqual(changed, set(result["changed_paths"]))
            provider_text = (archive_root / "provider-bindings.yml").read_text(encoding="utf-8")
            receipt_text = (archive_root / result["receipt_path"]).read_text(encoding="utf-8")
            self.assertIn("repo: zettel-kasten-HongGilDong", provider_text)
            for text in [provider_text, receipt_text]:
                self.assertNotIn("ghp_", text)
                self.assertNotIn("github_pat_", text)
                self.assertNotIn("person@example.com", text)
                self.assertNotIn("https://example.com", text)
            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict", "--format", "json"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_github_repo_approve_local_profile_requires_gitignore_protection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:github-plan")
            self.assertEqual(init_code, 0, init_output)
            gitignore_path = archive_root / ".gitignore"
            gitignore_path.write_text(
                "\n".join(line for line in gitignore_path.read_text(encoding="utf-8").splitlines() if line.strip() != "profiles/local/") + "\n",
                encoding="utf-8",
            )
            before = self.snapshot_archive_files(archive_root)

            code, output = self.run_cli(
                [
                    "github-repo",
                    str(archive_root),
                    "--approve",
                    "--reviewed-by",
                    "person:me",
                    "--write-local-profile",
                    "--profile-id",
                    "profile:personal:HongGilDong",
                    "--profile-slug",
                    "HongGilDong",
                    "--github-owner",
                    "example-user",
                    "--github-account-ref",
                    "github:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            self.assertEqual(code, 1)
            self.assertIn("profiles/local/", output)
            self.assertEqual(self.snapshot_archive_files(archive_root), before)

    def test_github_repo_approve_rolls_back_provider_binding_when_local_profile_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:github-plan")
            self.assertEqual(init_code, 0, init_output)
            local_profile_parent = archive_root / "profiles" / "local"
            local_profile_parent.parent.mkdir(parents=True, exist_ok=True)
            local_profile_parent.write_text("not a directory\n", encoding="utf-8")
            before = self.snapshot_archive_files(archive_root)

            code, output = self.run_cli(
                [
                    "github-repo",
                    str(archive_root),
                    "--approve",
                    "--reviewed-by",
                    "person:me",
                    "--write-local-profile",
                    "--profile-id",
                    "profile:personal:HongGilDong",
                    "--profile-slug",
                    "HongGilDong",
                    "--github-owner",
                    "example-user",
                    "--github-account-ref",
                    "github:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            self.assertEqual(code, 1)
            self.assertEqual(self.snapshot_archive_files(archive_root), before)
            self.assertFalse(
                (archive_root / "receipts" / "providers" / "zettel_kasten_honggildong.github-repository-setup.json").exists()
            )

    def test_object_storage_dry_run_generates_bucket_prefix_and_writes_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            before = self.snapshot_archive_files(archive_root)

            code, output = self.run_cli(
                [
                    "object-storage",
                    str(archive_root),
                    "--dry-run",
                    "--provider",
                    "cloudflare-r2",
                    "--profile-id",
                    "profile:personal:HongGilDong",
                    "--profile-slug",
                    "HongGilDong",
                    "--storage-account-ref",
                    "storage:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["lifecycle_action"], "object_storage_setup_plan")
            self.assertEqual(result["proposed_bucket_name"], "zettel-kasten-honggildong-objets")
            self.assertEqual(result["proposed_objet_prefix"], "archives/archive:personal:fake-life/objets/")
            self.assertEqual(result["proposed_visibility"], "private")
            self.assertEqual(result["provider"], "cloudflare-r2")
            self.assertFalse(result["provider_setup_receipt_preview"]["external_actions"]["provider_api_called"])
            self.assertFalse(result["provider_setup_receipt_preview"]["external_actions"]["files_uploaded"])
            self.assertEqual(self.snapshot_archive_files(archive_root), before)

    def test_object_storage_invalid_provider_bucket_slug_and_secret_refs_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            common = [
                "object-storage",
                str(archive_root),
                "--dry-run",
                "--profile-id",
                "profile:personal:test",
                "--profile-slug",
                "HongGilDong",
                "--storage-account-ref",
                "storage:account:test",
                "--format",
                "json",
            ]

            code, output = self.run_cli(common + ["--provider", "ftp"])
            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("provider" in blocker for blocker in result["blockers"]))

            for bad_bucket in ["Zettel-Kasten-Hong", "zettel.kasten.hong", "zettel_kasten_hong", "zettel-kasten/hong", "a" * 64]:
                with self.subTest(bucket=bad_bucket):
                    code, output = self.run_cli(common + ["--provider", "cloudflare-r2", "--bucket-name", bad_bucket])
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("bucket_name" in blocker for blocker in result["blockers"]))

            for bad_slug in ["홍길동", "bad slug", "../bad", "person@example.com", "secret-slug"]:
                with self.subTest(slug=bad_slug):
                    code, output = self.run_cli(common + ["--provider", "cloudflare-r2", "--profile-slug", bad_slug])
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("profile_slug" in blocker for blocker in result["blockers"]))

            for bad_ref in ["person@example.com", "https://example.com/private", "example.com", "../secret", "token-account"]:
                with self.subTest(account_ref=bad_ref):
                    code, output = self.run_cli(
                        common + ["--provider", "cloudflare-r2", "--storage-account-ref", bad_ref]
                    )
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("storage_account_ref" in blocker for blocker in result["blockers"]))

            for bad_endpoint in ["https://example.com/private", "s3://bucket-name", "example.com", "http:foo", "../secret"]:
                with self.subTest(endpoint_ref=bad_endpoint):
                    code, output = self.run_cli(
                        common
                        + [
                            "--provider",
                            "cloudflare-r2",
                            "--endpoint-ref",
                            bad_endpoint,
                        ]
                    )
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("endpoint_ref" in blocker for blocker in result["blockers"]))

    def test_object_storage_non_ascii_profile_without_explicit_slug_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "object-storage",
                    str(archive_root),
                    "--dry-run",
                    "--provider",
                    "cloudflare-r2",
                    "--profile-id",
                    "profile:personal:홍길동",
                    "--storage-account-ref",
                    "storage:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Non-ASCII" in blocker for blocker in result["blockers"]))

    def test_object_storage_approve_requires_reviewed_by(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "object-storage",
                    str(archive_root),
                    "--approve",
                    "--provider",
                    "cloudflare-r2",
                    "--profile-id",
                    "profile:personal:HongGilDong",
                    "--profile-slug",
                    "HongGilDong",
                    "--storage-account-ref",
                    "storage:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            self.assertEqual(code, 1)
            self.assertIn("--reviewed-by", output)

    def test_object_storage_approve_writes_only_local_metadata_and_doctor_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:objet-plan")
            self.assertEqual(init_code, 0, init_output)
            before = self.snapshot_archive_files(archive_root)

            code, output = self.run_cli(
                [
                    "object-storage",
                    str(archive_root),
                    "--approve",
                    "--reviewed-by",
                    "person:me",
                    "--write-local-profile",
                    "--provider",
                    "cloudflare-r2",
                    "--profile-id",
                    "profile:personal:HongGilDong",
                    "--profile-slug",
                    "HongGilDong",
                    "--storage-account-ref",
                    "storage:account:honggildong",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertFalse(result["dry_run"])
            self.assertFalse(result["provider_api_called"])
            self.assertFalse(result["bucket_created"])
            self.assertFalse(result["files_uploaded"])
            self.assertFalse(result["sync_started"])
            self.assertFalse(result["files_hashed"])
            self.assertFalse((archive_root / ".git").exists())
            self.assertEqual(
                set(result["changed_paths"]),
                {
                    "provider-bindings.yml",
                    "receipts/providers/zettel_kasten_honggildong_objets.object-storage-setup.json",
                    "profiles/local/object-storage-accounts.local.yml",
                },
            )
            after = self.snapshot_archive_files(archive_root)
            changed = {path for path in after if before.get(path) != after[path]} | {path for path in before if path not in after}
            self.assertEqual(changed, set(result["changed_paths"]))
            provider_text = (archive_root / "provider-bindings.yml").read_text(encoding="utf-8")
            receipt_text = (archive_root / result["receipt_path"]).read_text(encoding="utf-8")
            self.assertIn("provider: object_storage", provider_text)
            self.assertIn("provider_kind: cloudflare-r2", provider_text)
            self.assertIn("bucket: zettel-kasten-honggildong-objets", provider_text)
            for text in [provider_text, receipt_text]:
                self.assertNotIn("github_pat_", text)
                self.assertNotIn("person@example.com", text)
                self.assertNotIn("https://example.com", text)
                self.assertNotIn("PRIVATE KEY", text)
            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict", "--format", "json"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_object_storage_local_profile_preserves_multiple_buckets_for_same_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:objet-plan")
            self.assertEqual(init_code, 0, init_output)

            common = [
                "object-storage",
                str(archive_root),
                "--approve",
                "--reviewed-by",
                "person:me",
                "--write-local-profile",
                "--provider",
                "cloudflare-r2",
                "--profile-id",
                "profile:personal:HongGilDong",
                "--profile-slug",
                "HongGilDong",
                "--storage-account-ref",
                "storage:account:honggildong",
                "--format",
                "json",
            ]
            first_code, first_output = self.run_cli(common)
            self.assertEqual(first_code, 0, first_output)
            second_code, second_output = self.run_cli(common + ["--bucket-name", "zettel-kasten-honggildong-media"])
            self.assertEqual(second_code, 0, second_output)

            provider_data = archive_cli.load_yaml((archive_root / "provider-bindings.yml").read_text(encoding="utf-8"))
            object_buckets = sorted(
                binding["resource"]["bucket"]
                for binding in provider_data["bindings"]
                if binding.get("provider") == "object_storage"
            )
            self.assertEqual(
                object_buckets,
                ["zettel-kasten-honggildong-media", "zettel-kasten-honggildong-objets"],
            )

            local_data = archive_cli.load_yaml(
                (archive_root / "profiles" / "local" / "object-storage-accounts.local.yml").read_text(encoding="utf-8")
            )
            local_buckets = sorted(item["bucket_name"] for item in local_data["object_storage_accounts"])
            self.assertEqual(local_buckets, object_buckets)

    def test_object_storage_approve_rolls_back_provider_binding_when_later_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:objet-plan")
            self.assertEqual(init_code, 0, init_output)
            local_profile_parent = archive_root / "profiles" / "local"
            local_profile_parent.parent.mkdir(parents=True, exist_ok=True)
            local_profile_parent.write_text("not a directory\n", encoding="utf-8")
            before = self.snapshot_archive_files(archive_root)

            with self.assertRaises((archive_services.ArchiveServiceError, OSError)):
                archive_services.approve_object_storage_setup_plan(
                    archive_root,
                    reviewed_by="person:me",
                    write_local_profile=True,
                    provider="cloudflare-r2",
                    profile_id="profile:personal:HongGilDong",
                    profile_slug="HongGilDong",
                    storage_account_ref="storage:account:honggildong",
                )

            self.assertEqual(self.snapshot_archive_files(archive_root), before)
            self.assertFalse(
                (archive_root / "receipts" / "providers" / "zettel_kasten_honggildong_objets.object-storage-setup.json").exists()
            )

    def test_source_intake_local_path_dry_run_returns_safe_metadata_and_writes_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_root = self.copy_fake_archive(tmp_root / "archive")
            source_file = tmp_root / "presentation-notes.pdf"
            source_file.write_text("fake pdf metadata only\n", encoding="utf-8")
            before = self.snapshot_archive_files(archive_root)

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--local-path",
                    str(source_file),
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["lifecycle_action"], "source_intake_plan")
            self.assertEqual(result["input_kind"], "local_path")
            self.assertEqual(result["objet_status"], "candidate_unmanifested")
            self.assertEqual(result["source_metadata"]["label"], "local-file.pdf")
            self.assertEqual(result["source_metadata"]["extension"], ".pdf")
            self.assertEqual(result["source_metadata"]["mime"], "application/pdf")
            self.assertEqual(result["source_metadata"]["size_bytes"], source_file.stat().st_size)
            self.assertEqual(result["source_metadata"]["local_path"], "<redacted-local-path>")
            self.assertFalse(result["content_access"]["content_read"])
            self.assertFalse(result["content_access"]["full_hash_calculated"])
            self.assertFalse(result["content_access"]["copied"])
            self.assertFalse(result["content_access"]["uploaded"])
            self.assertNotIn(str(source_file), output)
            self.assertTrue(any("outside registered source roots" in warning for warning in result["warnings"]))
            self.assertEqual(self.snapshot_archive_files(archive_root), before)

    def test_source_intake_requires_exactly_one_locator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            local_file = archive_root / "objects" / "sample" / "fake-school-record.txt"
            object_id = "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"

            code, output = self.run_cli(["source-intake", str(archive_root), "--dry-run", "--format", "json"])
            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Exactly one" in blocker for blocker in result["blockers"]))

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--local-path",
                    str(local_file),
                    "--object-id",
                    object_id,
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Exactly one" in blocker for blocker in result["blockers"]))

    def test_source_intake_manifest_object_id_and_missing_object_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            object_id = "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"

            code, output = self.run_cli(
                ["source-intake", str(archive_root), "--dry-run", "--object-id", object_id, "--format", "json"]
            )
            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertEqual(result["objet_status"], "manifested")
            self.assertEqual(result["objet_ref"]["ref"], f"objet:{object_id}")
            self.assertEqual(result["source_refs_for_draft"][0]["type"], "object_id")
            self.assertEqual(result["source_refs_for_draft"][0]["value"], object_id)

            missing = "sha256:" + "f" * 64
            code, output = self.run_cli(
                ["source-intake", str(archive_root), "--dry-run", "--object-id", missing, "--format", "json"]
            )
            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertEqual(result["objet_status"], "blocked")
            self.assertTrue(any("does not resolve" in blocker for blocker in result["blockers"]))

    def test_source_intake_source_map_item_resolves_to_draft_ready_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--source",
                    "local:fake-sample-objects",
                    "--item-id",
                    "sourceitem:local_fake_sample_objects:fake-school-record",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertEqual(result["input_kind"], "source_map_item")
            self.assertEqual(result["objet_status"], "candidate_unmanifested")
            self.assertEqual(result["source_refs_for_draft"][0]["type"], "source_map_item")
            self.assertEqual(
                result["source_refs_for_draft"][0]["value"],
                "sourceitem:local_fake_sample_objects:fake-school-record",
            )
            self.assertFalse(result["content_access"]["content_read"])

    def test_source_intake_source_map_relative_path_resolves_and_blocks_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--source",
                    "local:fake-sample-objects",
                    "--relative-path",
                    "fake-family-memory.txt",
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["input_kind"], "source_map_relative_path")
            self.assertEqual(result["source_metadata"]["relative_path"], "fake-family-memory.txt")
            self.assertEqual(result["source_refs_for_draft"][0]["type"], "source_map_item")
            self.assertEqual(
                result["source_refs_for_draft"][0]["value"],
                "sourceitem:local_fake_sample_objects:fake-family-memory",
            )
            self.assertFalse(result["content_access"]["content_read"])

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--source",
                    "local:fake-sample-objects",
                    "--relative-path",
                    "../secret.txt",
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("relative_path is unsafe" in blocker for blocker in result["blockers"]))

    def test_source_intake_provider_and_ai_artifact_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--provider",
                    "google_drive",
                    "--provider-object-id",
                    "drivefile_123",
                    "--provider-kind",
                    "presentation",
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertEqual(result["objet_status"], "provider_reference")
            self.assertEqual(result["provider_object_ref"]["provider_object_id"], "drivefile_123")
            self.assertEqual(result["source_refs_for_draft"][0]["type"], "provider_object_ref")

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--provider",
                    "google_drive",
                    "--provider-object-id",
                    "https://example.com/private-file",
                    "--provider-kind",
                    "presentation",
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("provider_object_id" in blocker for blocker in result["blockers"]))

            for bad_provider_ref in ["s3://private-bucket/object", "token-provider-object", "person@example.com"]:
                with self.subTest(provider_object_id=bad_provider_ref):
                    code, output = self.run_cli(
                        [
                            "source-intake",
                            str(archive_root),
                            "--dry-run",
                            "--provider",
                            "google_drive",
                            "--provider-object-id",
                            bad_provider_ref,
                            "--provider-kind",
                            "presentation",
                            "--format",
                            "json",
                        ]
                    )
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(any("provider_object_id" in blocker for blocker in result["blockers"]))

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--ai-artifact-ref",
                    "artifact:presentation-outline",
                    "--artifact-kind",
                    "presentation_script",
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("AI artifact locator requires" in blocker for blocker in result["blockers"]))

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--ai-artifact-ref",
                    "artifact:presentation-outline",
                    "--runtime",
                    "codex",
                    "--artifact-kind",
                    "presentation_script",
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertEqual(result["objet_status"], "ai_artifact")
            self.assertEqual(result["source_refs_for_draft"][0]["type"], "ai_artifact")
            self.assertEqual(result["draft_provenance_suggestions"]["assisted_by"], ["ai_runtime:codex"])

    def test_source_intake_object_storage_context_warns_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:no-objet-storage")
            self.assertEqual(init_code, 0, init_output)
            provider_path = archive_root / "provider-bindings.yml"
            provider_doc = archive_cli.load_yaml(provider_path.read_text(encoding="utf-8"))
            provider_doc["bindings"] = [
                binding
                for binding in provider_doc.get("bindings", [])
                if binding.get("provider") not in {"object_storage", "cloudflare_r2", "backblaze_b2"}
            ]
            provider_path.write_text(archive_cli.dump_yaml(provider_doc), encoding="utf-8")
            source_file = archive_root / "objects" / "sample.pdf"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text("metadata only\n", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--local-path",
                    str(source_file),
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertFalse(result["object_storage_context"]["object_storage_configured"])
            self.assertTrue(result["object_storage_context"]["manual_setup_required"])
            self.assertTrue(any("object storage / objet setup planner" in warning for warning in result["warnings"]))

    def test_source_intake_refs_work_with_create_draft_and_mint_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            intake_code, intake_output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--object-id",
                    "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(intake_code, 0, intake_output)
            source_ref = json.loads(intake_output)["source_refs_for_draft"][0]
            source_ref_arg = f"{source_ref['type']}:{source_ref['value']}"

            dry_code, dry_output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Objet backed draft",
                    "--body",
                    "# Objet backed draft\n\nThis draft cites an existing manifested objet for test coverage.",
                    "--dry-run",
                    "--source-ref",
                    source_ref_arg,
                    "--format",
                    "json",
                ]
            )
            dry_result = json.loads(dry_output)
            self.assertEqual(dry_code, 0, dry_output)
            self.assertEqual(dry_result["frontmatter_preview"]["source_refs"][0]["value"], source_ref["value"])

            create_code, create_output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Objet backed draft",
                    "--body",
                    "# Objet backed draft\n\nThis draft cites an existing manifested objet for test coverage.",
                    "--source-ref",
                    source_ref_arg,
                    "--format",
                    "json",
                ]
            )
            create_result = json.loads(create_output)
            self.assertEqual(create_code, 0, create_output)
            draft_path = archive_root / create_result["path"]
            match = archive_cli.FRONTMATTER_RE.match(draft_path.read_text(encoding="utf-8"))
            self.assertIsNotNone(match)
            assert match is not None
            frontmatter = archive_cli.load_yaml(match.group(1))
            body = draft_path.read_text(encoding="utf-8")[match.end() :].lstrip()
            frontmatter["kind"] = "permanent_note"
            frontmatter["facets"] = {"domain": "test"}
            frontmatter["promotion"] = {
                "stage": "promotion_candidate",
                "ready_for_promotion": True,
                "checklist": {item_id: True for item_id in PROMOTION_CHECKLIST_IDS},
            }
            draft_path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")

            mint_code, mint_output = self.run_cli(
                ["mint-zet", str(archive_root), "--path", create_result["path"], "--dry-run", "--format", "json"]
            )
            mint_result = json.loads(mint_output)
            self.assertEqual(mint_code, 0, mint_output)
            self.assertIn(
                {"type": source_ref["type"], "value": source_ref["value"]},
                mint_result["receipt_preview"]["source_refs"],
            )

    def test_create_draft_dry_run_consumes_source_intake_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            plan_path = Path(tmp) / "source-intake-plan.json"
            intake_code, intake_output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--object-id",
                    "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136",
                    "--profile-id",
                    "profile:personal:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(intake_code, 0, intake_output)
            plan_path.write_text(intake_output, encoding="utf-8")

            code, output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Plan composed draft",
                    "--body",
                    "Draft text composed from safe source intake refs.",
                    "--dry-run",
                    "--source-intake-plan",
                    str(plan_path),
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertTrue(result["dry_run"])
            self.assertFalse((archive_root / result["proposed_path"]).exists())
            frontmatter = result["frontmatter_preview"]
            self.assertEqual(frontmatter["source_refs"][0]["type"], "object_id")
            self.assertIn("source_intake", frontmatter)
            self.assertTrue(frontmatter["source_intake"]["plan_sha256"].startswith("sha256:"))
            self.assertEqual(frontmatter["source_intake"]["content_access"]["metadata_only"], True)
            self.assertEqual(result["target_archive"]["profile_id"], "profile:personal:test")

    def test_create_draft_write_preserves_source_intake_plan_refs_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            plan_path = Path(tmp) / "plan.json"
            object_id = "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            intake_code, intake_output = self.run_cli(
                ["source-intake", str(archive_root), "--dry-run", "--object-id", object_id, "--format", "json"]
            )
            self.assertEqual(intake_code, 0, intake_output)
            plan_path.write_text(intake_output, encoding="utf-8")
            body = "Approved draft that keeps source intake metadata."
            expected_hash = hashlib.sha256((body.rstrip() + "\n").encode("utf-8")).hexdigest()

            code, output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Approved plan draft",
                    "--body",
                    body,
                    "--source-intake-plan",
                    str(plan_path),
                    "--source-ref",
                    "local_ai_session:session:explicit",
                    "--draft-id",
                    "zet_20260525_plan_composer",
                    "--created-at",
                    "2026-05-25T09:10:11+09:00",
                    "--expected-body-sha256",
                    expected_hash,
                    "--draft-approved-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            draft_path = archive_root / result["path"]
            text = draft_path.read_text(encoding="utf-8")
            self.assertNotIn(str(plan_path), text)
            match = archive_cli.FRONTMATTER_RE.match(text)
            self.assertIsNotNone(match)
            assert match is not None
            frontmatter = archive_cli.load_yaml(match.group(1))
            self.assertIn({"type": "object_id", "value": object_id, "role": "primary_source"}, frontmatter["source_refs"])
            self.assertIn(
                {"type": "local_ai_session", "value": "session:explicit", "role": "prompt_context"},
                frontmatter["source_refs"],
            )
            self.assertEqual(frontmatter["source_intake"]["objet_status"], "manifested")
            self.assertIn(object_id, frontmatter["provenance"]["derived_from"])

            frontmatter["kind"] = "permanent_note"
            frontmatter["facets"] = {"domain": "test"}
            frontmatter["promotion"] = {
                "stage": "promotion_candidate",
                "ready_for_promotion": True,
                "checklist": {item_id: True for item_id in PROMOTION_CHECKLIST_IDS},
            }
            draft_path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body + "\n", encoding="utf-8")
            mint_code, mint_output = self.run_cli(
                ["mint-zet", str(archive_root), "--path", result["path"], "--dry-run", "--format", "json"]
            )
            mint_result = json.loads(mint_output)
            self.assertEqual(mint_code, 0, mint_output)
            self.assertTrue(
                any(
                    ref.get("type") == "object_id" and ref.get("value") == object_id
                    for ref in mint_result["receipt_preview"]["source_refs"]
                )
            )
            self.assertEqual(mint_result["receipt_preview"]["source_intake"]["objet_status"], "manifested")

    def test_create_draft_anonymizes_source_intake_candidate_refs_from_no_redact_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_root = self.copy_fake_archive(tmp_root / "archive")
            source_file = tmp_root / "My Private Diary.pdf"
            source_file.write_text("metadata only\n", encoding="utf-8")
            plan_path = tmp_root / "local-plan.json"
            intake_code, intake_output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--local-path",
                    str(source_file),
                    "--no-redact-local-paths",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(intake_code, 0, intake_output)
            plan = json.loads(intake_output)
            self.assertIn("my_private_diary_pdf", plan["source_refs_for_draft"][0]["value"])
            plan_path.write_text(intake_output, encoding="utf-8")
            body = "Approved draft with an anonymized candidate source ref."
            expected_hash = hashlib.sha256((body.rstrip() + "\n").encode("utf-8")).hexdigest()

            code, output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Anonymized candidate draft",
                    "--body",
                    body,
                    "--source-intake-plan",
                    str(plan_path),
                    "--draft-id",
                    "zet_20260525_anonymized_candidate",
                    "--created-at",
                    "2026-05-25T09:10:11+09:00",
                    "--expected-body-sha256",
                    expected_hash,
                    "--draft-approved-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            draft_path = archive_root / result["path"]
            text = draft_path.read_text(encoding="utf-8")
            self.assertNotIn(str(source_file), text)
            self.assertNotIn(str(plan_path), text)
            self.assertNotIn("my_private_diary", text.lower())
            match = archive_cli.FRONTMATTER_RE.match(text)
            self.assertIsNotNone(match)
            assert match is not None
            frontmatter = archive_cli.load_yaml(match.group(1))
            anonymous_ref = frontmatter["source_refs"][0]["value"]
            self.assertEqual(frontmatter["source_refs"][0]["type"], "source_intake_candidate")
            self.assertTrue(anonymous_ref.startswith("candidate:source-intake:"))
            self.assertNotIn("my_private_diary", anonymous_ref)
            self.assertEqual(frontmatter["provenance"]["derived_from"], [anonymous_ref])

    def test_create_draft_blocks_invalid_source_intake_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            intake_code, intake_output = self.run_cli(
                [
                    "source-intake",
                    str(archive_root),
                    "--dry-run",
                    "--object-id",
                    "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(intake_code, 0, intake_output)
            valid_plan = json.loads(intake_output)
            cases = {
                "wrong lifecycle_action": {"lifecycle_action": "other_action"},
                "ok false": {"ok": False},
                "dry_run false": {"dry_run": False},
                "blockers present": {"blockers": ["blocked by test"]},
                "content read": {"content_access": {**valid_plan["content_access"], "content_read": True}},
                "content uploaded": {"content_access": {**valid_plan["content_access"], "uploaded": True}},
                "full hash": {"content_access": {**valid_plan["content_access"], "full_hash_calculated": True}},
                "local path ref": {"source_refs_for_draft": [{"type": "object_id", "value": "C:\\private\\source.txt"}]},
                "url ref": {"source_refs_for_draft": [{"type": "provider_object_ref", "value": "https://example.invalid/private"}]},
                "secret ref": {"source_refs_for_draft": [{"type": "provider_object_ref", "value": "token"}]},
            }

            for name, patch in cases.items():
                with self.subTest(name=name):
                    plan = {**valid_plan, **patch}
                    plan_path = Path(tmp) / f"{name.replace(' ', '-')}.json"
                    plan_path.write_text(json.dumps(plan), encoding="utf-8")
                    code, output = self.run_cli(
                        [
                            "create-draft",
                            str(archive_root),
                            "--title",
                            "Invalid plan draft",
                            "--body",
                            "This dry-run should be blocked.",
                            "--dry-run",
                            "--source-intake-plan",
                            str(plan_path),
                            "--format",
                            "json",
                        ]
                    )
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["blockers"])

    def write_block_header_fixture(self, archive_root: Path) -> tuple[Path, str, str]:
        object_id = "sha256:" + "b" * 64
        intake_object_id = "sha256:" + "c" * 64
        draft_path = archive_root / "inbox" / "zet_20260525_block_header_fixture.md"
        frontmatter = {
            "id": "zet_20260525_block_header_fixture",
            "title": "Block header fixture",
            "created_at": "2026-05-25T10:11:12+09:00",
            "updated_at": "2026-05-25T10:11:12+09:00",
            "archive_id": "archive:personal:fake-life",
            "status": "draft",
            "kind": "fleeting_capture",
            "facets": {},
            "assets": [{"object_id": object_id, "role": "source_scan", "label": "Fixture objet"}],
            "edges": [{"type": "references", "target": "zet_20240504_fake_lunch_thought"}],
            "source_refs": [
                {"type": "object_id", "value": object_id, "role": "primary_source"},
                {"type": "objet_ref", "value": f"objet:{intake_object_id}", "role": "context"},
            ],
            "source_intake": {
                "plan_sha256": "sha256:" + "d" * 64,
                "input_kind": "object_id",
                "source_kind": "document",
                "objet_status": "manifested",
                "object_id": intake_object_id,
                "receipt_path": "receipts/sources/source-intake-fixture.json",
                "content_access": {
                    "metadata_only": True,
                    "content_read": False,
                    "copied": False,
                    "uploaded": False,
                    "imported": False,
                    "ocr_performed": False,
                    "transcription_performed": False,
                    "external_api_called": False,
                    "full_hash_calculated": False,
                },
            },
            "provenance": {
                "created_by": "ai_runtime:codex",
                "created_in": "archive:personal:fake-life",
                "source": "user_conversation",
                "derived_from": [object_id],
            },
            "visibility": {"scope": "private", "allowed_archives": [], "source_visibility": "private"},
            "promotion": {
                "stage": "captured",
                "ready_for_promotion": False,
                "receipt_path": "receipts/promotion/zet_20260525_block_header_fixture.promotion.json",
            },
            "mint": {
                "stage": "mint_preview",
                "receipt_path": "receipts/mint/zet_20260525_block_header_fixture.mint.json",
            },
        }
        body = "# Block header fixture\n\nThis body is the only zet text hashed by block-header.\n"
        draft_path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")
        object_path = archive_root / "objects" / "sample" / "block-fixture-source.txt"
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_text("original objet bytes that must not affect block header hashes\n", encoding="utf-8")
        return draft_path, object_id, intake_object_id

    def test_block_header_path_dry_run_returns_header_preview_and_writes_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            before = sorted(path.relative_to(archive_root).as_posix() for path in archive_root.rglob("*"))
            code, output = self.run_cli(
                [
                    "block-header",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            after = sorted(path.relative_to(archive_root).as_posix() for path in archive_root.rglob("*"))

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertEqual(before, after)
            self.assertEqual(result["lifecycle_action"], "block_header_preview")
            self.assertEqual(result["source_path"], "inbox/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["block_model"]["block_formula"], "zet + header")
            self.assertEqual(result["header_preview"]["header_version"], "wom-block-header/v0.1-draft")
            self.assertRegex(result["zet_body_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(result["header_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(result["block_hash_preview"], r"^[0-9a-f]{64}$")

    def test_block_header_zettel_id_dry_run_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                [
                    "block-header",
                    str(archive_root),
                    "--zettel-id",
                    "zet_20240504_fake_lunch_thought",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertEqual(result["source_path"], "zettels/zet_20240504_fake_lunch_thought.md")
            self.assertEqual(result["zettel_id"], "zet_20240504_fake_lunch_thought")

    def test_block_header_requires_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                [
                    "block-header",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 1, output)
            self.assertFalse(result["ok"])
            self.assertFalse(result["dry_run"])
            self.assertIn("block-header is dry-run only; pass --dry-run.", result["blockers"])

    def test_block_header_requires_exactly_one_locator_and_blocks_missing_or_unsafe_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            cases = [
                ["block-header", str(archive_root), "--dry-run", "--format", "json"],
                [
                    "block-header",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--zettel-id",
                    "zet_20260519_draft_ai_lunch_note",
                    "--dry-run",
                    "--format",
                    "json",
                ],
                ["block-header", str(archive_root), "--zettel-id", "zet_missing", "--dry-run", "--format", "json"],
                ["block-header", str(archive_root), "--path", "../private.md", "--dry-run", "--format", "json"],
            ]
            for args in cases:
                with self.subTest(args=args):
                    code, output = self.run_cli(args)
                    result = json.loads(output)
                    self.assertEqual(code, 1, output)
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["blockers"])

    def test_block_header_collects_refs_and_hashes_are_deterministic_without_objet_body_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            draft_path, object_id, intake_object_id = self.write_block_header_fixture(archive_root)
            args = [
                "block-header",
                str(archive_root),
                "--path",
                archive_cli.archive_relative_path(draft_path, archive_root),
                "--dry-run",
                "--format",
                "json",
            ]

            first_code, first_output = self.run_cli(args)
            second_code, second_output = self.run_cli(args)
            first = json.loads(first_output)
            second = json.loads(second_output)
            self.assertEqual(first_code, 0, first_output)
            self.assertEqual(second_code, 0, second_output)
            self.assertEqual(first["zet_body_sha256"], second["zet_body_sha256"])
            self.assertEqual(first["header_sha256"], second["header_sha256"])
            self.assertEqual(first["block_hash_preview"], second["block_hash_preview"])
            self.assertIn({"id": "zet_20240504_fake_lunch_thought", "edge_type": "references"}, first["referenced_zets"])
            self.assertTrue(any(ref["value"] == object_id and ref["source"] == "assets" for ref in first["referenced_objets"]))
            self.assertTrue(any(ref["value"] == intake_object_id and ref["source"] == "source_intake" for ref in first["referenced_objets"]))
            receipt_paths = {item["path"] for item in first["referenced_receipts"]}
            self.assertIn("receipts/mint/zet_20260525_block_header_fixture.mint.json", receipt_paths)
            self.assertIn("receipts/promotion/zet_20260525_block_header_fixture.promotion.json", receipt_paths)
            self.assertIn("receipts/sources/source-intake-fixture.json", receipt_paths)

            object_file = archive_root / "objects" / "sample" / "block-fixture-source.txt"
            object_file.write_text("changed objet bytes should not change block header preview\n", encoding="utf-8")
            third_code, third_output = self.run_cli(args)
            third = json.loads(third_output)
            self.assertEqual(third_code, 0, third_output)
            self.assertEqual(first["zet_body_sha256"], third["zet_body_sha256"])
            self.assertEqual(first["header_sha256"], third["header_sha256"])
            self.assertEqual(first["block_hash_preview"], third["block_hash_preview"])

    def test_block_header_redacts_local_absolute_paths_from_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            draft_path, _object_id, _intake_object_id = self.write_block_header_fixture(archive_root)
            frontmatter, body = archive_services.split_zettel_text(draft_path.read_text(encoding="utf-8"))
            frontmatter["source_refs"].append({"type": "local_file", "value": str(Path(tmp) / "private" / "source.pdf")})
            draft_path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")

            code, output = self.run_cli(
                [
                    "block-header",
                    str(archive_root),
                    "--path",
                    archive_cli.archive_relative_path(draft_path, archive_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

            result = json.loads(output)
            self.assertEqual(code, 0, output)
            self.assertNotIn(str(Path(tmp)), output)
            self.assertIn("<redacted-reference>", output)
            self.assertTrue(result["warnings"])

    def test_block_header_hashes_sanitized_projection_not_raw_private_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            draft_path, _object_id, _intake_object_id = self.write_block_header_fixture(archive_root)
            frontmatter, body = archive_services.split_zettel_text(draft_path.read_text(encoding="utf-8"))

            hashes = []
            for private_ref in ["C:\\Users\\example\\private-one.pdf", "C:\\Users\\example\\private-two.pdf"]:
                frontmatter["source_refs"] = [
                    {"type": "local_file", "value": private_ref, "role": "private_debug_source"}
                ]
                draft_path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")
                code, output = self.run_cli(
                    [
                        "block-header",
                        str(archive_root),
                        "--path",
                        archive_cli.archive_relative_path(draft_path, archive_root),
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
                result = json.loads(output)
                self.assertEqual(code, 0, output)
                self.assertIn("<redacted-reference>", output)
                self.assertTrue(result["warnings"])
                hashes.append(result["header_sha256"])

            self.assertEqual(hashes[0], hashes[1])

    def test_runtime_context_no_redact_local_paths_includes_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                ["runtime-context", str(archive_root), "--no-redact-local-paths", "--format", "json"]
            )

            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertFalse(result["redaction"]["local_paths_redacted"])
            self.assertEqual(result["local_archive_root"], str(archive_root.resolve()))
            self.assertEqual(result["local_paths"]["inbox"], str((archive_root / "inbox").resolve()))

    def test_runtime_context_keeps_stable_summary_keys_when_optional_docs_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            (archive_root / "archive-identity.yml").unlink()
            archive_yml = archive_cli.load_yaml((archive_root / "archive.yml").read_text(encoding="utf-8"))
            archive_yml.pop("ai_write_policy")
            (archive_root / "archive.yml").write_text(archive_cli.dump_yaml(archive_yml), encoding="utf-8")

            code, output = self.run_cli(["runtime-context", str(archive_root), "--format", "json"])

            result = json.loads(output)
            self.assertIn(code, {0, 1}, output)
            self.assertEqual(
                set(result["principal"].keys()),
                {"principal_id", "display_name", "kind", "identity_id"},
            )
            self.assertEqual(
                set(result["owner"].keys()),
                {"owner_id", "owner_kind", "owner_display_name", "owner_archive_id", "operator_count", "subject_count"},
            )
            self.assertEqual(
                set(result["ai_write_policy"].keys()),
                {"default", "canonical_requires", "summary"},
            )
            self.assertIsNone(result["principal"]["identity_id"])
            self.assertIsNone(result["owner"]["owner_id"])
            self.assertIsNone(result["ai_write_policy"]["default"])
            self.assertEqual(result["ai_write_policy"]["summary"], "unavailable")

    def test_init_then_doctor_passes_strict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root)
            self.assertEqual(init_code, 0, init_output)

            archive_yml = archive_cli.load_yaml((archive_root / "archive.yml").read_text(encoding="utf-8"))
            self.assertEqual(archive_yml["ai_write_policy"]["canonical_requires"], "human_minting")

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)
            self.assertIn("0 error(s), 0 warning(s)", doctor_output)

    def test_init_gitignore_protects_local_profiles_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:gitignore")
            self.assertEqual(init_code, 0, init_output)

            gitignore = (archive_root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("profiles/local/", gitignore)
            self.assertIn("keyrings/local/", gitignore)
            self.assertIn(".archive-local/", gitignore)
            self.assertIn("*.kdbx", gitignore)
            self.assertIn("credentials.json", gitignore)
            self.assertIn("**/db/archive-index.sqlite", gitignore)

    def test_init_writes_archive_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:identity")
            self.assertEqual(init_code, 0, init_output)

            identity = archive_cli.load_yaml((archive_root / "archive-identity.yml").read_text(encoding="utf-8"))
            self.assertEqual(identity["identity"]["archive_id"], "archive:personal:identity")
            self.assertEqual(identity["identity"]["scope"], "personal")
            self.assertEqual(identity["identity"]["principal_id"], "person:test")
            self.assertEqual(identity["ownership"]["owner_id"], "person:test")
            self.assertEqual(identity["ownership"]["owner_kind"], "person")
            self.assertEqual(identity["ownership"]["operators"][0]["operator_id"], "person:test")
            self.assertEqual(identity["ownership"]["transfer_policy"]["receipt_action"], "transfer_archive_ownership")
            self.assertEqual(identity["trusted_counterparties"], [])

    def test_init_family_archive_keeps_owner_and_operator_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "family-archive"
            code, output = self.run_cli(
                [
                    "init",
                    str(archive_root),
                    "--type",
                    "family",
                    "--archive-id",
                    "archive:family:test",
                    "--principal-id",
                    "family:test",
                    "--principal-kind",
                    "family",
                    "--principal-name",
                    "Test Family",
                    "--name",
                    "Test Family Archive",
                ]
            )
            self.assertEqual(code, 0, output)

            identity = archive_cli.load_yaml((archive_root / "archive-identity.yml").read_text(encoding="utf-8"))
            self.assertEqual(identity["ownership"]["owner_id"], "family:test")
            self.assertEqual(identity["ownership"]["owner_kind"], "family")
            self.assertEqual(identity["ownership"]["owner_display_name"], "Test Family")
            self.assertEqual(identity["ownership"]["owner_archive_id"], "archive:family:test")
            self.assertEqual(identity["ownership"]["operators"][0]["operator_id"], "person:member-a")
            self.assertEqual(identity["ownership"]["operators"][0]["role"], "parent_operator")
            self.assertTrue(identity["ownership"]["transfer_policy"]["ownership_transfer_allowed"])

    def test_onboard_dry_run_returns_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "onboard-personal"
            code, output = self.run_cli(
                [
                    "onboard",
                    "--target-root",
                    str(archive_root),
                    "--type",
                    "personal",
                    "--archive-id",
                    "archive:personal:onboard",
                    "--principal-id",
                    "person:onboard",
                    "--principal-name",
                    "Onboard Person",
                    "--provider-profile",
                    "full_provider_plan",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["docker_runtime"]["container_os"], "linux")
            self.assertEqual(result["provider_profile"], "full_provider_plan")
            self.assertIn("github", result["provider_bindings"]["enabled_providers"])
            self.assertFalse(archive_root.exists())

    def test_onboard_approve_creates_archive_and_applies_provider_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "onboard-family"
            code, output = self.run_cli(
                [
                    "onboard",
                    "--target-root",
                    str(archive_root),
                    "--type",
                    "family",
                    "--archive-id",
                    "archive:family:onboard",
                    "--principal-id",
                    "family:onboard",
                    "--principal-name",
                    "Onboard Household",
                    "--provider-profile",
                    "local_only",
                    "--approve",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["doctor"]["errors"], 0)
            self.assertEqual(result["doctor"]["warnings"], 0)
            self.assertTrue((archive_root / "archive.yml").is_file())
            self.assertTrue((archive_root / "provider-bindings.yml").is_file())

            provider_data = archive_cli.load_yaml((archive_root / "provider-bindings.yml").read_text(encoding="utf-8"))
            enabled = {
                item["provider"]
                for item in provider_data["bindings"]
                if item.get("enabled") is True
            }
            disabled = {
                item["provider"]
                for item in provider_data["bindings"]
                if item.get("enabled") is False
            }
            self.assertEqual(enabled, {"external_ssd", "keepassxc"})
            self.assertIn("github", disabled)
            self.assertEqual(provider_data["onboarding"]["provider_profile"], "local_only")
            self.assertNotIn("ghp_", (archive_root / "provider-bindings.yml").read_text(encoding="utf-8"))

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_onboard_blocks_nonempty_target_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "existing"
            archive_root.mkdir()
            (archive_root / "keep.txt").write_text("existing\n", encoding="utf-8")
            code, output = self.run_cli(
                [
                    "onboard",
                    "--target-root",
                    str(archive_root),
                    "--type",
                    "personal",
                    "--archive-id",
                    "archive:personal:blocked",
                    "--principal-id",
                    "person:blocked",
                    "--approve",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("empty or absent" in blocker for blocker in result["blockers"]))
            self.assertEqual((archive_root / "keep.txt").read_text(encoding="utf-8"), "existing\n")

    def test_onboard_blocks_file_target_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "not-a-directory"
            archive_root.write_text("existing file\n", encoding="utf-8")
            code, output = self.run_cli(
                [
                    "onboard",
                    "--target-root",
                    str(archive_root),
                    "--type",
                    "personal",
                    "--archive-id",
                    "archive:personal:blocked-file",
                    "--principal-id",
                    "person:blocked-file",
                    "--approve",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("folder or absent" in blocker for blocker in result["blockers"]))
            self.assertEqual(archive_root.read_text(encoding="utf-8"), "existing file\n")

    def test_doctor_missing_archive_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "missing"
            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("archive_root_missing", output)

    def test_validate_fake_life_archive_passes_json(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["validate", str(archive_root), "--format", "json"])
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["warnings"], 0)

    def test_list_zettels_json_returns_all_statuses(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["list-zettels", str(archive_root), "--status", "all", "--format", "json"])
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertEqual(result["count"], 5)
        statuses = {item["status"] for item in result["zettels"]}
        self.assertIn("canonical", statuses)
        self.assertIn("draft", statuses)
        self.assertNotIn("\\", result["zettels"][0]["path"])
        self.assertIn("T", result["zettels"][0]["created_at"])

    def test_read_zettel_by_id_and_path(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        zettel_id = "zet_20240504_fake_lunch_thought"
        code, output = self.run_cli(["read-zettel", str(archive_root), "--zettel-id", zettel_id, "--format", "json"])
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertEqual(result["frontmatter"]["id"], zettel_id)
        self.assertIn("private personal reflection", result["body"])

        windows_style_path = result["path"].replace("/", "\\")
        path_code, path_output = self.run_cli(["read-zettel", str(archive_root), "--path", windows_style_path, "--format", "json"])
        self.assertEqual(path_code, 0, path_output)
        path_result = json.loads(path_output)
        self.assertEqual(path_result["path"], result["path"])

    def test_read_zettel_rejects_non_zettel_path(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["read-zettel", str(archive_root), "--path", "archive.yml"])
        self.assertEqual(code, 1)
        self.assertIn("inbox/ or zettels", output)

    def test_create_draft_writes_to_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:create-draft")
            self.assertEqual(init_code, 0, init_output)

            code, output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "CLI draft note",
                    "--body",
                    "# CLI draft note\n\nCreated by a CLI test.",
                    "--facet",
                    "domain=test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertEqual(result["status"], "draft")
            self.assertTrue(result["path"].startswith("inbox/"))
            self.assertTrue((archive_root / result["path"]).is_file())
            self.assertEqual(result["frontmatter"]["facets"]["domain"], "test")

    def test_create_draft_rejects_unsafe_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:unsafe-draft")
            self.assertEqual(init_code, 0, init_output)

            code, output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Unsafe draft",
                    "--body",
                    "This mentions X:\\example\\secret.txt.",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("absolute path", output)

    def test_create_draft_dry_run_returns_preview_and_writes_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:draft-dry-run")
            self.assertEqual(init_code, 0, init_output)

            code, output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "AI assisted draft",
                    "--body",
                    "A safe draft body.",
                    "--dry-run",
                    "--expected-archive-id",
                    "archive:personal:draft-dry-run",
                    "--expected-type",
                    "personal",
                    "--profile-id",
                    "profile:personal:test",
                    "--profile-operator-id",
                    "person:test",
                    "--profile-authority-mode",
                    "draft_only",
                    "--creation-mode",
                    "ai_assisted",
                    "--created-by",
                    "ai_runtime:codex",
                    "--source",
                    "user_conversation",
                    "--assisted-by",
                    "ai_runtime:codex",
                    "--supervised-by",
                    "person:test",
                    "--derived-from",
                    "object:example-script",
                    "--source-ref",
                    "local_ai_session:session:abc123",
                    "--local-ai-session",
                    "session:abc123",
                    "--draft-id",
                    "zet_20260524_010203_ai_assisted_draft",
                    "--created-at",
                    "2026-05-24T01:02:03+09:00",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["lifecycle_action"], "create_draft")
            self.assertEqual(result["proposed_path"], "inbox/zet_20260524_010203_ai_assisted_draft.md")
            self.assertRegex(result["body_sha256"], r"^[0-9a-f]{64}$")
            self.assertFalse((archive_root / result["proposed_path"]).exists())
            self.assertEqual(result["approval_replay"]["draft_id"], "zet_20260524_010203_ai_assisted_draft")
            self.assertEqual(result["approval_replay"]["expected_archive_id"], "archive:personal:draft-dry-run")
            self.assertEqual(result["approval_replay"]["profile_id"], "profile:personal:test")
            frontmatter = result["frontmatter_preview"]
            self.assertEqual(frontmatter["provenance"]["creation_mode"], "ai_assisted")
            self.assertEqual(frontmatter["provenance"]["derived_from"], ["object:example-script"])
            self.assertEqual(frontmatter["source_refs"][0]["type"], "local_ai_session")
            self.assertEqual(frontmatter["local_ai_sessions"][0]["session_ref"], "session:abc123")

    def test_create_draft_replay_writes_approved_inbox_draft_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:draft-replay")
            self.assertEqual(init_code, 0, init_output)
            body = "Approved safe draft body."
            expected_hash = hashlib.sha256((body.rstrip() + "\n").encode("utf-8")).hexdigest()

            code, output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Approved AI draft",
                    "--body",
                    body,
                    "--expected-archive-id",
                    "archive:personal:draft-replay",
                    "--expected-type",
                    "personal",
                    "--profile-id",
                    "profile:personal:test",
                    "--profile-operator-id",
                    "person:test",
                    "--profile-authority-mode",
                    "draft_only",
                    "--creation-mode",
                    "ai_assisted",
                    "--created-by",
                    "ai_runtime:codex",
                    "--source",
                    "user_conversation",
                    "--assisted-by",
                    "ai_runtime:codex",
                    "--supervised-by",
                    "person:test",
                    "--derived-from",
                    "object:example-script",
                    "--source-ref",
                    "local_ai_session:session:approved",
                    "--local-ai-session",
                    "session:approved",
                    "--draft-id",
                    "zet_20260524_020304_approved_ai_draft",
                    "--created-at",
                    "2026-05-24T02:03:04+09:00",
                    "--expected-body-sha256",
                    expected_hash,
                    "--draft-approved-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["path"], "inbox/zet_20260524_020304_approved_ai_draft.md")
            draft_path = archive_root / result["path"]
            self.assertTrue(draft_path.is_file())
            match = archive_cli.FRONTMATTER_RE.match(draft_path.read_text(encoding="utf-8"))
            self.assertIsNotNone(match)
            assert match is not None
            frontmatter = archive_cli.load_yaml(match.group(1))
            self.assertEqual(frontmatter["provenance"]["created_by"], "ai_runtime:codex")
            self.assertEqual(frontmatter["provenance"]["creation_mode"], "ai_assisted")
            self.assertEqual(frontmatter["provenance"]["assisted_by"], ["ai_runtime:codex"])
            self.assertEqual(frontmatter["provenance"]["supervised_by"], ["person:test"])
            self.assertEqual(frontmatter["provenance"]["derived_from"], ["object:example-script"])
            self.assertEqual(frontmatter["source_refs"][0]["value"], "session:approved")
            self.assertEqual(frontmatter["local_ai_sessions"][0]["profile_id"], "profile:personal:test")
            self.assertEqual(frontmatter["draft_creation"]["approved_by"], "person:test")
            self.assertEqual(frontmatter["draft_creation"]["approval_scope"], "inbox_draft_only")
            self.assertEqual(frontmatter["draft_creation"]["approved_body_sha256"], expected_hash)

    def test_create_draft_body_hash_normalizes_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:draft-crlf")
            self.assertEqual(init_code, 0, init_output)

            base_args = [
                "create-draft",
                str(archive_root),
                "--title",
                "Line ending draft",
                "--dry-run",
                "--format",
                "json",
            ]
            lf_code, lf_output = self.run_cli(base_args + ["--body", "Line one\nLine two"])
            crlf_code, crlf_output = self.run_cli(base_args + ["--body", "Line one\r\nLine two"])
            self.assertEqual(lf_code, 0, lf_output)
            self.assertEqual(crlf_code, 0, crlf_output)
            self.assertEqual(json.loads(lf_output)["body_sha256"], json.loads(crlf_output)["body_sha256"])

    def test_create_draft_blocks_ai_creation_without_assisted_by(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:draft-ai-identity")
            self.assertEqual(init_code, 0, init_output)

            for created_by in ["person:test", "cli:archive", "mcp:zettel-kasten-archive-mcp"]:
                code, output = self.run_cli(
                    [
                        "create-draft",
                        str(archive_root),
                        "--title",
                        "AI identity draft",
                        "--body",
                        "Safe body.",
                        "--dry-run",
                        "--creation-mode",
                        "ai_assisted",
                        "--created-by",
                        created_by,
                        "--format",
                        "json",
                    ]
                )
                self.assertEqual(code, 1, output)
                self.assertIn("assisting AI runtime", "; ".join(json.loads(output)["blockers"]))

            pass_code, pass_output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "AI identity pass",
                    "--body",
                    "Safe body.",
                    "--dry-run",
                    "--creation-mode",
                    "ai_assisted",
                    "--created-by",
                    "person:test",
                    "--assisted-by",
                    "ai_runtime:codex",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(pass_code, 0, pass_output)
            self.assertTrue(json.loads(pass_output)["ok"])

    def test_create_draft_blocks_empty_body_and_bad_created_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:draft-sanity")
            self.assertEqual(init_code, 0, init_output)

            empty_code, empty_output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Empty draft",
                    "--body",
                    "   ",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(empty_code, 1, empty_output)
            self.assertIn("non-whitespace", "; ".join(json.loads(empty_output)["blockers"]))

            date_code, date_output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Bad date draft",
                    "--body",
                    "Safe body.",
                    "--dry-run",
                    "--created-at",
                    "not-an-iso-date",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(date_code, 1, date_output)
            self.assertIn("ISO 8601", "; ".join(json.loads(date_output)["blockers"]))

    def test_create_draft_blocks_archive_id_type_and_body_hash_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:draft-mismatch")
            self.assertEqual(init_code, 0, init_output)

            id_code, id_output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Mismatch",
                    "--body",
                    "Safe body.",
                    "--dry-run",
                    "--expected-archive-id",
                    "archive:personal:other",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(id_code, 1)
            self.assertIn("Expected archive id mismatch", json.loads(id_output)["blockers"][0])

            type_code, type_output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Type mismatch",
                    "--body",
                    "Safe body.",
                    "--dry-run",
                    "--expected-type",
                    "company",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(type_code, 1)
            self.assertIn("Expected archive type mismatch", json.loads(type_output)["blockers"][0])

            hash_code, hash_output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Hash mismatch",
                    "--body",
                    "Safe body.",
                    "--dry-run",
                    "--expected-body-sha256",
                    "0" * 64,
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(hash_code, 1)
            self.assertIn("SHA-256", "; ".join(json.loads(hash_output)["blockers"]))

    def test_create_draft_rejects_unsafe_provenance_and_source_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:unsafe-provenance")
            self.assertEqual(init_code, 0, init_output)

            code, output = self.run_cli(
                [
                    "create-draft",
                    str(archive_root),
                    "--title",
                    "Unsafe refs",
                    "--body",
                    "Safe body.",
                    "--dry-run",
                    "--derived-from",
                    "X:\\example\\private.txt",
                    "--source-ref",
                    "object:s3://example-bucket/private.txt",
                    "--local-ai-session",
                    "gs://example-bucket/session",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertIn("Unsafe local path or provider locator", "; ".join(result["blockers"]))

    def test_promote_dry_run_checks_inbox_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            code, output = self.run_cli(
                [
                    "promote",
                    str(archive_root),
                    "--path",
                    "inbox\\zet_20260519_draft_ai_lunch_note.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["draft_path"], "inbox/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["proposed_canonical_path"], "zettels/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["proposed_receipt_path"], "receipts/promotion/zet_20260519_draft_ai_lunch_note.promotion.json")
            self.assertEqual(len(result["checklist"]), len(PROMOTION_CHECKLIST_IDS))
            self.assertTrue(all(item["status"] == "passed" for item in result["checklist"]))
            self.assertEqual(result["receipt_preview"]["action"], "promote_zettel")
            self.assertTrue(result["receipt_preview"]["dry_run"])
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse((archive_root / "receipts" / "promotion" / "zet_20260519_draft_ai_lunch_note.promotion.json").exists())

    def test_promote_dry_run_blocks_unreviewed_fleeting_capture(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "promote",
                str(archive_root),
                "--path",
                "inbox/zet_20260519_draft_ai_lunch_note.md",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 1)
        result = json.loads(output)
        self.assertFalse(result["ok"])
        self.assertIn("Note kind cannot be promoted to canonical memory: fleeting_capture.", result["blockers"])
        self.assertTrue(any(item["status"] == "needs_human_review" for item in result["checklist"]))
        self.assertEqual(result["receipt_preview"]["receipt_path"], result["proposed_receipt_path"])

    def test_promote_real_requires_approval_and_reviewer(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "promote",
                str(archive_root),
                "--path",
                "inbox/zet_20260519_draft_ai_lunch_note.md",
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("--approve", output)

        reviewed_code, reviewed_output = self.run_cli(
            [
                "promote",
                str(archive_root),
                "--path",
                "inbox/zet_20260519_draft_ai_lunch_note.md",
                "--approve",
            ]
        )
        self.assertEqual(reviewed_code, 1)
        self.assertIn("--reviewed-by", reviewed_output)

    def test_promote_real_writes_canonical_receipt_and_keeps_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            draft_path = self.make_fake_lunch_draft_promotion_ready(archive_root)

            code, output = self.run_cli(
                [
                    "promote",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["draft_path"], "inbox/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["canonical_path"], "zettels/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["receipt_path"], "receipts/promotion/zet_20260519_draft_ai_lunch_note.promotion.json")

            canonical_path = archive_root / result["canonical_path"]
            receipt_path = archive_root / result["receipt_path"]
            self.assertTrue(canonical_path.is_file())
            self.assertTrue(receipt_path.is_file())
            self.assertTrue(draft_path.is_file())

            canonical_text = canonical_path.read_text(encoding="utf-8")
            match = archive_cli.FRONTMATTER_RE.match(canonical_text)
            self.assertIsNotNone(match)
            assert match is not None
            frontmatter = archive_cli.load_yaml(match.group(1))
            self.assertEqual(frontmatter["status"], "canonical")
            self.assertEqual(frontmatter["promotion"]["stage"], "promoted")
            self.assertEqual(frontmatter["promotion"]["reviewed_by"], "person:test")
            self.assertEqual(frontmatter["promotion"]["checklist_version"], "zettel-promotion/v0.2")
            self.assertIn("reviewed_at", frontmatter["promotion"])
            self.assertIn("updated_at", frontmatter)

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["receipt_id"], "receipt:promotion:zet_20260519_draft_ai_lunch_note")
            self.assertEqual(receipt["action"], "promote_zettel")
            self.assertFalse(receipt["dry_run"])
            self.assertEqual(receipt["reviewed_by"], "person:test")
            self.assertEqual(receipt["source"]["path"], "inbox/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(receipt["target"]["path"], "zettels/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(receipt["zettel"]["id"], "zet_20260519_draft_ai_lunch_note")
            self.assertEqual(receipt["result"]["created_paths"], result["created_paths"])

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_promote_real_blocks_dry_run_blockers_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "promote",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Promotion blocked by dry-run", output)
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse((archive_root / "receipts" / "promotion" / "zet_20260519_draft_ai_lunch_note.promotion.json").exists())

    def test_promote_real_requires_allow_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root, title="Fake thought while eating alone")

            code, output = self.run_cli(
                [
                    "promote",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("--allow-warnings", output)
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse((archive_root / "receipts" / "promotion" / "zet_20260519_draft_ai_lunch_note.promotion.json").exists())

            allowed_code, allowed_output = self.run_cli(
                [
                    "promote",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--allow-warnings",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(allowed_code, 0, allowed_output)
            result = json.loads(allowed_output)
            self.assertTrue(any("same_title" in warning for warning in result["warnings"]))

    def test_promote_real_fails_when_target_or_receipt_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            canonical_path = archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md"
            canonical_path.write_text("existing canonical", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "promote",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Proposed canonical path already exists", output)
            self.assertEqual(canonical_path.read_text(encoding="utf-8"), "existing canonical")

        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            receipt_path = archive_root / "receipts" / "promotion" / "zet_20260519_draft_ai_lunch_note.promotion.json"
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text("{}\n", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "promote",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Promotion receipt path already exists", output)
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertEqual(receipt_path.read_text(encoding="utf-8"), "{}\n")

    def test_promote_dry_run_blocks_canonical_zettel(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "promote",
                str(archive_root),
                "--path",
                "zettels/zet_20240504_fake_lunch_thought.md",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 1)
        result = json.loads(output)
        self.assertFalse(result["ok"])
        self.assertIn("Only drafts inside inbox/ can be promoted.", result["blockers"])

    def test_mint_zettel_dry_run_checks_inbox_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox\\zet_20260519_draft_ai_lunch_note.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["draft_path"], "inbox/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["authority_mode"], "basic")
            self.assertEqual(result["proposed_canonical_path"], "zettels/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["proposed_mint_receipt_path"], "receipts/mint/zet_20260519_draft_ai_lunch_note.mint.json")
            self.assertEqual(result["proposed_draft_snapshot_path"], "receipts/mint/drafts/zet_20260519_draft_ai_lunch_note.draft.md")
            self.assertEqual(len(result["checklist"]), len(PROMOTION_CHECKLIST_IDS))
            self.assertTrue(all(item["status"] == "passed" for item in result["checklist"]))
            self.assertEqual(result["receipt_preview"]["action"], "mint_zettel")
            self.assertTrue(result["receipt_preview"]["dry_run"])
            self.assertEqual(result["receipt_preview"]["authority_mode"], "basic")
            self.assertIn("source_refs", result["receipt_preview"])
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse((archive_root / "receipts" / "mint" / "zet_20260519_draft_ai_lunch_note.mint.json").exists())
            self.assertFalse((archive_root / "receipts" / "mint" / "drafts" / "zet_20260519_draft_ai_lunch_note.draft.md").exists())

            id_code, id_output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--zettel-id",
                    "zet_20260519_draft_ai_lunch_note",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(id_code, 0, id_output)
            id_result = json.loads(id_output)
            self.assertEqual(id_result["draft_path"], "inbox/zet_20260519_draft_ai_lunch_note.md")

    def test_mint_zet_alias_matches_legacy_mint_zettel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            code, output = self.run_cli(
                [
                    "mint-zet",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["zettel_id"], "zet_20260519_draft_ai_lunch_note")
            self.assertEqual(result["proposed_canonical_path"], "zettels/zet_20260519_draft_ai_lunch_note.md")

    def test_mint_receipts_include_draft_provenance_refs_and_ai_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            draft_path = self.make_fake_lunch_draft_promotion_ready(archive_root)
            text = draft_path.read_text(encoding="utf-8")
            match = archive_cli.FRONTMATTER_RE.match(text)
            self.assertIsNotNone(match)
            assert match is not None
            frontmatter = archive_cli.load_yaml(match.group(1))
            body = text[match.end() :].lstrip()
            frontmatter["source_refs"] = [
                {"type": "local_ai_session", "value": "session:mint-preview", "role": "prompt_context"}
            ]
            frontmatter["provenance"]["derived_from"] = ["object:source-script"]
            frontmatter["local_ai_sessions"] = [
                {
                    "runtime": "codex",
                    "session_ref": "session:mint-preview",
                    "profile_id": "profile:personal:test",
                    "archive_id": "archive:personal:fake-life",
                    "authority_mode": "draft_only",
                }
            ]
            draft_path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")

            dry_code, dry_output = self.run_cli(
                [
                    "mint-zet",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(dry_code, 0, dry_output)
            dry_result = json.loads(dry_output)
            preview = dry_result["receipt_preview"]
            self.assertIn({"type": "derived_from", "value": "object:source-script"}, preview["source_refs"])
            self.assertEqual(preview["local_ai_sessions"][0]["session_ref"], "session:mint-preview")

            real_code, real_output = self.run_cli(
                [
                    "mint-zet",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(real_code, 0, real_output)
            real_result = json.loads(real_output)
            receipt = json.loads((archive_root / real_result["mint_receipt_path"]).read_text(encoding="utf-8"))
            self.assertIn({"type": "derived_from", "value": "object:source-script"}, receipt["source_refs"])
            self.assertEqual(receipt["local_ai_sessions"][0]["profile_id"], "profile:personal:test")

    def test_mint_zettel_dry_run_prefers_minting_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            rules_path = archive_root / "zettel-kasten" / "zettel-rules.yml"
            rules = archive_cli.load_yaml(rules_path.read_text(encoding="utf-8"))
            rules["minting_rules"] = dict(rules["promotion_rules"])
            rules["minting_rules"]["default_target_path"] = "minted-zettels/"
            rules_path.write_text(archive_cli.dump_yaml(rules), encoding="utf-8")

            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertEqual(result["proposed_canonical_path"], "minted-zettels/zet_20260519_draft_ai_lunch_note.md")

    def test_mint_zettel_dry_run_falls_back_to_legacy_promotion_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            rules_path = archive_root / "zettel-kasten" / "zettel-rules.yml"
            rules = archive_cli.load_yaml(rules_path.read_text(encoding="utf-8"))
            rules.pop("minting_rules", None)
            rules_path.write_text(archive_cli.dump_yaml(rules), encoding="utf-8")

            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertEqual(result["proposed_canonical_path"], "zettels/zet_20260519_draft_ai_lunch_note.md")

    def test_mint_zettel_real_requires_approval_and_reviewer(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "mint-zettel",
                str(archive_root),
                "--path",
                "inbox/zet_20260519_draft_ai_lunch_note.md",
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("--approve", output)

        reviewed_code, reviewed_output = self.run_cli(
            [
                "mint-zettel",
                str(archive_root),
                "--path",
                "inbox/zet_20260519_draft_ai_lunch_note.md",
                "--approve",
            ]
        )
        self.assertEqual(reviewed_code, 1)
        self.assertIn("--reviewed-by", reviewed_output)

    def test_mint_zettel_real_writes_canonical_receipt_snapshot_and_keeps_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            draft_path = self.make_fake_lunch_draft_promotion_ready(archive_root)
            draft_text_before = draft_path.read_text(encoding="utf-8")

            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["draft_path"], "inbox/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["canonical_path"], "zettels/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["mint_receipt_path"], "receipts/mint/zet_20260519_draft_ai_lunch_note.mint.json")
            self.assertEqual(result["draft_snapshot_path"], "receipts/mint/drafts/zet_20260519_draft_ai_lunch_note.draft.md")

            canonical_path = archive_root / result["canonical_path"]
            receipt_path = archive_root / result["mint_receipt_path"]
            snapshot_path = archive_root / result["draft_snapshot_path"]
            self.assertTrue(canonical_path.is_file())
            self.assertTrue(receipt_path.is_file())
            self.assertTrue(snapshot_path.is_file())
            self.assertTrue(draft_path.is_file())
            self.assertEqual(draft_path.read_text(encoding="utf-8"), draft_text_before)
            self.assertEqual(snapshot_path.read_text(encoding="utf-8"), draft_text_before)

            canonical_text = canonical_path.read_text(encoding="utf-8")
            match = archive_cli.FRONTMATTER_RE.match(canonical_text)
            self.assertIsNotNone(match)
            assert match is not None
            frontmatter = archive_cli.load_yaml(match.group(1))
            self.assertEqual(frontmatter["status"], "canonical")
            self.assertEqual(frontmatter["mint"]["stage"], "minted")
            self.assertEqual(frontmatter["mint"]["authority_mode"], "basic")
            self.assertEqual(frontmatter["mint"]["reviewed_by"], "person:test")
            self.assertEqual(frontmatter["mint"]["receipt_path"], result["mint_receipt_path"])
            self.assertEqual(frontmatter["mint"]["draft_snapshot_path"], result["draft_snapshot_path"])
            self.assertEqual(frontmatter["mint"]["checklist_version"], "zet-mint/v0.2")
            self.assertIn("minted_at", frontmatter["mint"])
            self.assertEqual(frontmatter["promotion"]["stage"], "promoted")
            self.assertEqual(frontmatter["promotion"]["reviewed_by"], "person:test")
            self.assertEqual(frontmatter["promotion"]["checklist_version"], "zettel-promotion/v0.2")

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(archive_cli.validate_schema(receipt, "mint-receipt.schema.json"), [])
            self.assertEqual(receipt["receipt_id"], "receipt:mint:zet_20260519_draft_ai_lunch_note")
            self.assertEqual(receipt["action"], "mint_zettel")
            self.assertFalse(receipt["dry_run"])
            self.assertEqual(receipt["authority_mode"], "basic")
            self.assertEqual(receipt["reviewed_by"], "person:test")
            self.assertEqual(receipt["source"]["path"], "inbox/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(receipt["target"]["path"], result["canonical_path"])
            self.assertEqual(receipt["snapshot"]["path"], result["draft_snapshot_path"])
            self.assertRegex(receipt["source"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(receipt["target"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(receipt["snapshot"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(receipt["result"]["created_paths"], result["created_paths"])

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_mint_zettel_real_blocks_dry_run_blockers_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Minting blocked by dry-run", output)
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse((archive_root / "receipts" / "mint" / "zet_20260519_draft_ai_lunch_note.mint.json").exists())
            self.assertFalse((archive_root / "receipts" / "mint" / "drafts" / "zet_20260519_draft_ai_lunch_note.draft.md").exists())

    def test_mint_zettel_real_requires_allow_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root, title="Fake thought while eating alone")

            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("--allow-warnings", output)
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse((archive_root / "receipts" / "mint" / "zet_20260519_draft_ai_lunch_note.mint.json").exists())

            allowed_code, allowed_output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--allow-warnings",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(allowed_code, 0, allowed_output)
            result = json.loads(allowed_output)
            self.assertTrue(any("same_title" in warning for warning in result["warnings"]))

    def test_mint_zettel_real_fails_when_target_receipt_or_snapshot_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            canonical_path = archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md"
            canonical_path.write_text("existing canonical", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Proposed canonical path already exists", output)
            self.assertEqual(canonical_path.read_text(encoding="utf-8"), "existing canonical")

        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            receipt_path = archive_root / "receipts" / "mint" / "zet_20260519_draft_ai_lunch_note.mint.json"
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text("{}\n", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Mint receipt path already exists", output)
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertEqual(receipt_path.read_text(encoding="utf-8"), "{}\n")

        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root)
            snapshot_path = archive_root / "receipts" / "mint" / "drafts" / "zet_20260519_draft_ai_lunch_note.draft.md"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text("existing snapshot", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "mint-zettel",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Draft snapshot path already exists", output)
            self.assertFalse((archive_root / "zettels" / "zet_20260519_draft_ai_lunch_note.md").exists())
            self.assertFalse((archive_root / "receipts" / "mint" / "zet_20260519_draft_ai_lunch_note.mint.json").exists())
            self.assertEqual(snapshot_path.read_text(encoding="utf-8"), "existing snapshot")

    def test_promote_dry_run_reports_same_title_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.make_fake_lunch_draft_promotion_ready(archive_root, title="Fake thought while eating alone")
            code, output = self.run_cli(
                [
                    "promote",
                    str(archive_root),
                    "--path",
                    "inbox/zet_20260519_draft_ai_lunch_note.md",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(any(item["reason"] == "same_title" for item in result["near_duplicates"]))
            self.assertTrue(any("same_title" in warning for warning in result["warnings"]))

    def test_search_requires_generated_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(["search", str(archive_root), "lunch", "--format", "json"])
            self.assertEqual(code, 1)
            self.assertIn("Archive index is missing", output)

    def test_index_then_search_finds_zettels_objects_and_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")

            first_code, first_output = self.run_cli(["index", str(archive_root), "--format", "json"])
            self.assertEqual(first_code, 0, first_output)
            first_result = json.loads(first_output)
            self.assertTrue(first_result["ok"])
            self.assertEqual(first_result["index_path"], "db/archive-index.sqlite")
            self.assertGreaterEqual(first_result["zettels"], 5)
            self.assertGreaterEqual(first_result["objects"], 2)
            self.assertGreaterEqual(first_result["views"], 1)
            self.assertGreaterEqual(first_result["source_map_entries"], 2)
            self.assertTrue((archive_root / "db" / "archive-index.sqlite").is_file())

            second_code, second_output = self.run_cli(["index", str(archive_root), "--format", "json"])
            self.assertEqual(second_code, 0, second_output)
            self.assertEqual(json.loads(second_output), first_result)

            zettel_code, zettel_output = self.run_cli(["search", str(archive_root), "lunch", "--format", "json"])
            self.assertEqual(zettel_code, 0, zettel_output)
            zettel_result = json.loads(zettel_output)
            self.assertGreaterEqual(zettel_result["count"], 1)
            self.assertEqual(zettel_result["results"][0]["type"], "zettel")
            self.assertNotIn("\\", zettel_result["results"][0]["path"])

            object_code, object_output = self.run_cli(["search", str(archive_root), "fake-school-record", "--format", "json"])
            self.assertEqual(object_code, 0, object_output)
            object_result = json.loads(object_output)
            self.assertTrue(any(item["type"] == "object" for item in object_result["results"]))

            view_code, view_output = self.run_cli(["search", str(archive_root), "Homebase", "--format", "json"])
            self.assertEqual(view_code, 0, view_output)
            view_result = json.loads(view_output)
            self.assertTrue(any(item["type"] == "view" for item in view_result["results"]))

            source_code, source_output = self.run_cli(["search", str(archive_root), "fake-school-record", "--format", "json"])
            self.assertEqual(source_code, 0, source_output)
            source_result = json.loads(source_output)
            self.assertTrue(any(item["type"] == "source_map" for item in source_result["results"]))

    def test_sources_cli_lists_registered_sources(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["sources", str(archive_root), "--format", "json"])
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["source_bindings_present"])
        self.assertGreaterEqual(result["source_count"], 2)
        fake_source = next(item for item in result["sources"] if item["source_id"] == "local:fake-sample-objects")
        self.assertTrue(fake_source["source_map_present"])
        self.assertEqual(fake_source["mapped_items"], 2)

    def test_add_source_dry_run_does_not_write_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:add-source-dry-run")
            self.assertEqual(init_code, 0, init_output)
            before = (archive_root / "source-bindings.yml").read_text(encoding="utf-8")

            code, output = self.run_cli(
                [
                    "add-source",
                    str(archive_root),
                    "--source-id",
                    "local:desktop",
                    "--type",
                    "local_folder",
                    "--local-root",
                    str(Path(tmp) / "Desktop"),
                    "--write-local-profile",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["source_binding"]["root_ref"], "ARCHIVE_SOURCE_LOCAL_DESKTOP_ROOT")
            self.assertIn("source-bindings.yml", result["would_change"])
            self.assertIn("profiles/local/source-roots.local.yml", result["would_change"])
            self.assertEqual((archive_root / "source-bindings.yml").read_text(encoding="utf-8"), before)
            self.assertFalse((archive_root / "profiles" / "local" / "source-roots.local.yml").exists())

    def test_add_source_approve_writes_binding_and_ignored_local_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:add-source-approve")
            self.assertEqual(init_code, 0, init_output)
            source_root = Path(tmp) / "Desktop"
            source_root.mkdir()

            code, output = self.run_cli(
                [
                    "add-source",
                    str(archive_root),
                    "--source-id",
                    "local:desktop",
                    "--type",
                    "local_folder",
                    "--description",
                    "Desktop folder selected by user.",
                    "--local-root",
                    str(source_root),
                    "--write-local-profile",
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["source_id"], "local:desktop")
            bindings = archive_cli.load_yaml((archive_root / "source-bindings.yml").read_text(encoding="utf-8"))
            self.assertTrue(any(item["source_id"] == "local:desktop" for item in bindings["sources"]))
            profile_path = archive_root / "profiles" / "local" / "source-roots.local.yml"
            self.assertTrue(profile_path.is_file())
            profile = archive_cli.load_yaml(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["sources"]["local:desktop"]["path"], str(source_root.resolve()))

            scan_code, scan_output = self.run_cli(
                [
                    "scan-source",
                    str(archive_root),
                    "--source",
                    "local:desktop",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(scan_code, 0, scan_output)
            self.assertEqual(json.loads(scan_output)["source_root_resolution"]["method"], "ignored_local_profile")

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_add_source_blocks_duplicate_and_absolute_root_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:add-source-blocks")
            self.assertEqual(init_code, 0, init_output)

            dup_code, dup_output = self.run_cli(
                [
                    "add-source",
                    str(archive_root),
                    "--source-id",
                    "local:personal-documents",
                    "--type",
                    "local_folder",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(dup_code, 1)
            self.assertIn("Source already exists", dup_output)

            bad_code, bad_output = self.run_cli(
                [
                    "add-source",
                    str(archive_root),
                    "--source-id",
                    "local:absolute",
                    "--type",
                    "local_folder",
                    "--root-ref",
                    "C:\\Users\\example\\Documents",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(bad_code, 1)
            self.assertIn("root_ref must be an env/root ref", bad_output)

    def test_source_mounts_returns_docker_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:mount-plan")
            self.assertEqual(init_code, 0, init_output)

            code, output = self.run_cli(["source-mounts", str(archive_root), "--format", "json"])
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertEqual(result["strategy"], "docker_compose_override_or_host_native_cli")
            local_source = next(item for item in result["sources"] if item["source_id"] == "local:personal-documents")
            self.assertTrue(local_source["needs_host_mount"])
            self.assertIn("/sources/local_personal_documents", local_source["docker_scan_command"])
            object_source = next(item for item in result["sources"] if item["source_id"] == "object:manifest")
            self.assertFalse(object_source["needs_host_mount"])

    def test_pilot_plan_returns_personal_and_team_steps_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            personal_root = Path(tmp) / "personal-life"
            team_root = Path(tmp) / "team-archive"
            code, output = self.run_cli(
                [
                    "pilot-plan",
                    "--personal-root",
                    str(personal_root),
                    "--team-root",
                    str(team_root),
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["action"], "plan_real_archive_pilot")
            self.assertEqual(len(result["archives"]), 2)
            self.assertFalse(personal_root.exists())
            self.assertFalse(team_root.exists())
            personal = next(item for item in result["archives"] if item["role"] == "personal_life")
            team = next(item for item in result["archives"] if item["role"] == "team")
            self.assertIn("cloudflare_r2", personal["enabled_providers"])
            self.assertIn("github", team["enabled_providers"])
            self.assertTrue(any(source["source_id"] == "notion:personal-export" for source in personal["suggested_sources"]))
            self.assertTrue(any(source["source_id"] == "google_drive:team-export" for source in team["suggested_sources"]))

    def test_pilot_plan_blocks_nested_personal_and_team_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            personal_root = Path(tmp) / "archive"
            team_root = personal_root / "team"
            code, output = self.run_cli(
                [
                    "pilot-plan",
                    "--personal-root",
                    str(personal_root),
                    "--team-root",
                    str(team_root),
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1, output)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertIn("Personal and team archive roots must not be nested inside each other.", result["blockers"])

    def test_preflight_passes_fake_archive(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["preflight", str(archive_root), "--format", "json"])
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["doctor"]["errors"], 0)
        self.assertEqual(result["doctor"]["warnings"], 0)
        self.assertEqual(result["blockers"], [])

    def test_preflight_require_source_maps_blocks_missing_map(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["preflight", str(archive_root), "--require-source-maps", "--format", "json"])
        self.assertEqual(code, 1, output)
        result = json.loads(output)
        self.assertFalse(result["ok"])
        self.assertIn("object:manifest", result["sources"]["missing_source_maps"])
        self.assertTrue(any(item["code"] == "source_map_missing" for item in result["findings"]))

    def test_preflight_blocks_drive_or_filesystem_root_local_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            profile = archive_root / "profiles" / "local" / "source-roots.local.yml"
            profile.parent.mkdir(parents=True)
            broad_root = Path(archive_root.anchor) if archive_root.anchor else Path("/")
            profile.write_text(
                archive_cli.dump_yaml(
                    {
                        "version": "source-roots-local/v0.1",
                        "sources": {
                            "local:fake-sample-objects": {
                                "root_ref": "ARCHIVE_SOURCE_FAKE_ROOT",
                                "path": str(broad_root),
                                "path_is_local_only": True,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            code, output = self.run_cli(["preflight", str(archive_root), "--format", "json"])
            self.assertEqual(code, 1, output)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertTrue(any(item["code"] == "local_source_root_too_broad" for item in result["findings"]))

    def test_recovery_plan_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            before = sorted(path.relative_to(archive_root).as_posix() for path in archive_root.rglob("*"))
            code, output = self.run_cli(["recovery-plan", str(archive_root), "--format", "json"])
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["action"], "archive_recovery_plan")
            self.assertIn("db/archive-index.sqlite", result["excluded_from_restore_copy"])
            after = sorted(path.relative_to(archive_root).as_posix() for path in archive_root.rglob("*"))
            self.assertEqual(after, before)

    def test_restore_drill_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            target = Path(tmp) / "restore-copy"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            code, output = self.run_cli(["restore-drill", str(archive_root), "--target", str(target), "--dry-run", "--format", "json"])
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertFalse(target.exists())
            self.assertFalse((archive_root / "receipts" / "recovery").exists())

    def test_restore_drill_approve_copies_valid_archive_and_unblocks_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            target = Path(tmp) / "restore-copy"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)

            blocked_code, blocked_output = self.run_cli(["preflight", str(archive_root), "--require-restore-drill", "--format", "json"])
            self.assertEqual(blocked_code, 1, blocked_output)
            self.assertIn("restore_drill_required", blocked_output)

            code, output = self.run_cli(
                [
                    "restore-drill",
                    str(archive_root),
                    "--target",
                    str(target),
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertFalse(result["dry_run"])
            self.assertTrue(result["ok"])
            self.assertTrue((target / "archive.yml").is_file())
            self.assertTrue((target / "db" / "archive-index.sqlite").is_file())
            self.assertFalse((target / ".git").exists())

            receipt_path = archive_root / result["receipt_path"]
            self.assertTrue(receipt_path.is_file())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(
                archive_cli.validate_schema(receipt, "restore-drill-receipt.schema.json"),
                [],
            )

            original_doctor_code, original_doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(original_doctor_code, 0, original_doctor_output)

            restored_doctor_code, restored_doctor_output = self.run_cli(["doctor", str(target), "--strict"])
            self.assertEqual(restored_doctor_code, 0, restored_doctor_output)

            preflight_code, preflight_output = self.run_cli(["preflight", str(archive_root), "--require-restore-drill", "--format", "json"])
            self.assertEqual(preflight_code, 0, preflight_output)
            preflight = json.loads(preflight_output)
            self.assertIsNotNone(preflight["restore_drill"]["latest_successful"])

    def test_restore_drill_blocks_unsafe_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            bad_targets = [
                archive_root / "inside",
                Path(archive_root.anchor) if archive_root.anchor else Path("/"),
            ]
            nonempty = Path(tmp) / "nonempty"
            nonempty.mkdir()
            (nonempty / "already.txt").write_text("nope", encoding="utf-8")
            bad_targets.append(nonempty)
            for target in bad_targets:
                with self.subTest(target=str(target)):
                    code, output = self.run_cli(["restore-drill", str(archive_root), "--target", str(target), "--dry-run", "--format", "json"])
                    self.assertEqual(code, 1, output)
                    result = json.loads(output)
                    self.assertFalse(result["ok"])
                    self.assertGreater(len(result["blockers"]), 0)

    def test_scan_source_dry_run_is_metadata_only_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:source-dry-run")
            self.assertEqual(init_code, 0, init_output)
            source_root = Path(tmp) / "scattered-docs"
            source_root.mkdir()
            (source_root / "note.txt").write_text("private content should not be read", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "scan-source",
                    str(archive_root),
                    "--source",
                    "local:personal-documents",
                    "--source-root",
                    str(source_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["scan_mode"], "metadata_only")
            self.assertEqual(result["item_count"], 1)
            self.assertFalse(result["items"][0]["provenance"]["content_read"])
            self.assertNotIn(str(source_root), output)
            self.assertFalse((archive_root / result["proposed_source_map_path"]).exists())
            self.assertFalse((archive_root / result["proposed_receipt_path"]).exists())

    def test_scan_source_approve_writes_source_map_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:source-approve")
            self.assertEqual(init_code, 0, init_output)
            source_root = Path(tmp) / "scattered-docs"
            source_root.mkdir()
            (source_root / "plan.txt").write_text("fake plan", encoding="utf-8")

            code, output = self.run_cli(
                [
                    "scan-source",
                    str(archive_root),
                    "--source",
                    "local:personal-documents",
                    "--source-root",
                    str(source_root),
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            source_map_path = archive_root / result["source_map_path"]
            receipt_path = archive_root / result["receipt_path"]
            self.assertTrue(source_map_path.is_file())
            self.assertTrue(receipt_path.is_file())
            entry = json.loads(source_map_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(entry["relative_path"], "plan.txt")
            self.assertFalse(entry["provenance"]["full_hash_calculated"])
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertFalse(receipt["dry_run"])
            self.assertEqual(receipt["action"], "scan_archive_source")
            self.assertEqual(receipt["reviewed_by"], "person:test")
            self.assertEqual(
                archive_cli.validate_schema(receipt, "source-scan-receipt.schema.json"),
                [],
            )
            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_scan_source_supports_notion_and_google_drive_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:external-source-map")
            self.assertEqual(init_code, 0, init_output)
            source_path = archive_root / "source-bindings.yml"
            data = archive_cli.load_yaml(source_path.read_text(encoding="utf-8"))
            data["sources"].extend(
                [
                    {
                        "source_id": "notion:export",
                        "source_type": "notion_export",
                        "enabled": True,
                        "root_ref": "NOTION_EXPORT_ROOT",
                        "scope_policy": {"mode": "metadata_only", "include": ["**/*"], "exclude": [], "max_items": 2000},
                        "visibility": {"scope": "private", "source_visibility": "private"},
                    },
                    {
                        "source_id": "google-drive:export",
                        "source_type": "google_drive_export",
                        "enabled": True,
                        "root_ref": "GOOGLE_DRIVE_EXPORT_MANIFEST",
                        "scope_policy": {"mode": "metadata_only", "include": ["**/*"], "exclude": [], "max_items": 2000},
                        "visibility": {"scope": "private", "source_visibility": "private"},
                    },
                ]
            )
            source_path.write_text(archive_cli.dump_yaml(data), encoding="utf-8")

            notion_root = KIT_ROOT / "examples" / "external-imports" / "notion-export"
            notion_code, notion_output = self.run_cli(
                [
                    "scan-source",
                    str(archive_root),
                    "--source",
                    "notion:export",
                    "--source-root",
                    str(notion_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(notion_code, 0, notion_output)
            notion_result = json.loads(notion_output)
            self.assertEqual(notion_result["source_type"], "notion_export")
            self.assertEqual(notion_result["item_count"], 1)

            manifest = KIT_ROOT / "examples" / "external-imports" / "google-drive-export" / "manifest.json"
            gdrive_code, gdrive_output = self.run_cli(
                [
                    "scan-source",
                    str(archive_root),
                    "--source",
                    "google-drive:export",
                    "--source-root",
                    str(manifest),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(gdrive_code, 0, gdrive_output)
            gdrive_result = json.loads(gdrive_output)
            self.assertEqual(gdrive_result["source_type"], "google_drive_export")
            self.assertEqual(gdrive_result["items"][0]["external_url"], "https://drive.google.com/file/d/fake-research-note/view")

    def test_doctor_flags_source_binding_absolute_path_and_source_map_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            source_path = archive_root / "source-bindings.yml"
            data = archive_cli.load_yaml(source_path.read_text(encoding="utf-8"))
            data["sources"][0]["root_ref"] = "C:\\Users\\example\\Documents"
            source_path.write_text(archive_cli.dump_yaml(data), encoding="utf-8")
            bad_map = archive_root / "source-maps" / "bad.jsonl"
            bad_map.write_text(
                json.dumps(
                    {
                        "source_id": "local:fake-sample-objects",
                        "item_id": "bad",
                        "item_kind": "file",
                        "relative_path": "../secret.txt",
                        "visibility": {"scope": "private", "source_visibility": "private"},
                        "scan_status": "seen",
                        "provenance": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("source_binding_sensitive_path", output)
            self.assertIn("source_map_relative_path_unsafe", output)

    def test_pack_view_creates_workpack_with_zettels_and_object_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                [
                    "pack",
                    str(archive_root),
                    "--view",
                    "view.fake.education.gilwon",
                    "--purpose",
                    "Portable education context for testing.",
                    "--mode",
                    "reference",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["view_id"], "view.fake.education.gilwon")
            self.assertEqual(result["zettels"], 1)
            self.assertEqual(result["objects"], 1)
            self.assertTrue(result["package_path"].startswith("workpacks/"))
            package_root = archive_root / result["package_path"]
            self.assertTrue((package_root / "package.yml").is_file())
            self.assertTrue((package_root / "zettels" / "zet_20110228_fake_school_record.md").is_file())
            self.assertTrue((package_root / "manifests" / "files.jsonl").is_file())
            self.assertTrue((package_root / "views" / "view_fake_education_gilwon.yml").is_file())
            package = archive_cli.load_yaml((package_root / "package.yml").read_text(encoding="utf-8"))
            self.assertFalse(package["ownership_gate"]["ownership_transfer"])
            self.assertEqual(package["ownership_gate"]["current_owner"], "person:fake-user")

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_parcel_alias_creates_workpack_compat_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                [
                    "parcel",
                    str(archive_root),
                    "--view",
                    "view.fake.education.gilwon",
                    "--purpose",
                    "Portable education context through the parcel alias.",
                    "--mode",
                    "reference",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["package_path"].startswith("workpacks/"))
            self.assertTrue((archive_root / result["package_path"] / "package.yml").is_file())

    def test_pack_unknown_view_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                [
                    "pack",
                    str(archive_root),
                    "--view",
                    "view.fake.missing",
                    "--purpose",
                    "Should fail.",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("View id not found", output)

    def test_import_workpack_dry_run_previews_target_writes_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = self.copy_fake_archive(Path(tmp) / "source")
            pack_code, pack_output = self.run_cli(
                [
                    "pack",
                    str(source_root),
                    "--view",
                    "view.fake.education.gilwon",
                    "--purpose",
                    "Portable education context for import dry-run.",
                    "--mode",
                    "reference",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(pack_code, 0, pack_output)
            package_root = source_root / json.loads(pack_output)["package_path"]

            target_root = Path(tmp) / "target"
            init_code, init_output = self.init_personal_archive(target_root, "archive:personal:import-target")
            self.assertEqual(init_code, 0, init_output)

            code, output = self.run_cli(["import", str(target_root), str(package_root), "--dry-run", "--format", "json"])
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(len(result["zettels"]), 1)
            self.assertEqual(result["zettels"][0]["target_path"], "inbox/zet_20110228_fake_school_record.md")
            self.assertEqual(result["zettels"][0]["action"], "create_inbox_draft")
            self.assertEqual(len(result["objects"]), 1)
            self.assertEqual(result["objects"][0]["action"], "append_manifest_record")
            self.assertFalse(result["ownership_gate"]["ownership_transfer"])
            self.assertTrue(result["proposed_receipt_path"].startswith("receipts/import/"))
            self.assertFalse((target_root / "inbox" / "zet_20110228_fake_school_record.md").exists())
            self.assertFalse((target_root / result["proposed_receipt_path"]).exists())

    def test_admit_alias_previews_workpack_import_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = self.copy_fake_archive(Path(tmp) / "source")
            pack_code, pack_output = self.run_cli(
                [
                    "parcel",
                    str(source_root),
                    "--view",
                    "view.fake.education.gilwon",
                    "--purpose",
                    "Portable education context for admit dry-run.",
                    "--mode",
                    "reference",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(pack_code, 0, pack_output)
            package_root = source_root / json.loads(pack_output)["package_path"]

            target_root = Path(tmp) / "target"
            init_code, init_output = self.init_personal_archive(target_root, "archive:personal:admit-target")
            self.assertEqual(init_code, 0, init_output)

            code, output = self.run_cli(["admit", str(target_root), str(package_root), "--dry-run", "--format", "json"])
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["zettels"][0]["target_path"], "inbox/zet_20110228_fake_school_record.md")
            self.assertFalse((target_root / "inbox" / "zet_20110228_fake_school_record.md").exists())

    def test_import_workpack_dry_run_requires_trust_when_package_requires_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = self.copy_fake_archive(Path(tmp) / "source")
            pack_code, pack_output = self.run_cli(
                [
                    "pack",
                    str(source_root),
                    "--view",
                    "view.fake.education.gilwon",
                    "--purpose",
                    "Trust-gated import dry-run test.",
                    "--mode",
                    "reference",
                    "--target-archive",
                    "archive:personal:trusted-target",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(pack_code, 0, pack_output)
            package_root = source_root / json.loads(pack_output)["package_path"]

            target_root = Path(tmp) / "target"
            init_code, init_output = self.init_personal_archive(target_root, "archive:personal:trusted-target")
            self.assertEqual(init_code, 0, init_output)
            target_identity_path = target_root / "archive-identity.yml"
            target_identity = archive_cli.load_yaml(target_identity_path.read_text(encoding="utf-8"))
            target_identity["trusted_counterparties"].append(
                {
                    "identity_id": "identity:archive:personal:fake-life",
                    "archive_id": "archive:personal:fake-life",
                    "principal_id": "person:fake-user",
                    "expected_fingerprint": "SHA256:fake-user-primary",
                    "trust_level": "out_of_band_verified",
                }
            )
            target_identity_path.write_text(archive_cli.dump_yaml(target_identity), encoding="utf-8")

            missing_code, missing_output = self.run_cli(["import", str(target_root), str(package_root), "--dry-run"])
            self.assertEqual(missing_code, 1)
            self.assertIn("Counterparty fingerprint is required", missing_output)

            code, output = self.run_cli(
                [
                    "import",
                    str(target_root),
                    str(package_root),
                    "--dry-run",
                    "--counterparty-id",
                    "archive:personal:fake-life",
                    "--counterparty-fingerprint",
                    "SHA256:fake-user-primary",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["trust_gate"]["status"], "verified")
            self.assertEqual(result["scope_gate"]["included_zettels"], ["zettels/zet_20110228_fake_school_record.md"])

    def test_import_workpack_without_dry_run_is_unavailable(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        workpack = archive_root / "workpacks" / "fake-company-derived-onboarding"
        code, output = self.run_cli(["import", str(archive_root), str(workpack)])
        self.assertEqual(code, 1)
        self.assertIn("Only --dry-run", output)

    def test_import_workpack_dry_run_reports_duplicate_zettel_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            pack_code, pack_output = self.run_cli(
                [
                    "pack",
                    str(archive_root),
                    "--view",
                    "view.fake.education.gilwon",
                    "--purpose",
                    "Duplicate import dry-run test.",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(pack_code, 0, pack_output)
            package_root = archive_root / json.loads(pack_output)["package_path"]

            code, output = self.run_cli(["import", str(archive_root), str(package_root), "--dry-run", "--format", "json"])
            self.assertEqual(code, 1)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("already has zettel id" in blocker for blocker in result["blockers"]))
            self.assertIn("zettel_id_exists", result["zettels"][0]["conflicts"])

    def test_import_external_notion_dry_run_previews_inbox_draft_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:notion-import")
            self.assertEqual(init_code, 0, init_output)
            export_root = KIT_ROOT / "examples" / "external-imports" / "notion-export"

            code, output = self.run_cli(
                [
                    "import-external",
                    str(archive_root),
                    "--source",
                    "notion",
                    "--export",
                    str(export_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["source_system"], "notion")
            self.assertEqual(result["item_count"], 1)
            item = result["items"][0]
            self.assertEqual(item["title"], "Family Archive Plan")
            self.assertTrue(item["target_path"].startswith("inbox/zet_import_notion_"))
            self.assertTrue(result["proposed_receipt_path"].endswith(".external-import.json"))
            self.assertFalse((archive_root / item["target_path"]).exists())
            self.assertFalse((archive_root / result["proposed_receipt_path"]).exists())

    def test_import_external_google_drive_manifest_apply_writes_draft_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:gdrive-import")
            self.assertEqual(init_code, 0, init_output)
            manifest = KIT_ROOT / "examples" / "external-imports" / "google-drive-export" / "manifest.json"

            code, output = self.run_cli(
                [
                    "import-external",
                    str(archive_root),
                    "--source",
                    "google_drive",
                    "--export",
                    str(manifest),
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["imported_count"], 1)
            draft_paths = [path for path in result["created_paths"] if path.startswith("inbox/")]
            self.assertEqual(len(draft_paths), 1)
            draft_path = archive_root / draft_paths[0]
            self.assertTrue(draft_path.is_file())
            draft_text = draft_path.read_text(encoding="utf-8")
            self.assertIn("external_import:", draft_text)
            self.assertIn("gdrive:file:fake-research-note", draft_text)
            self.assertIn("https://drive.google.com/file/d/fake-research-note/view", draft_text)
            receipt_path = archive_root / result["receipt_path"]
            self.assertTrue(receipt_path.is_file())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["action"], "import_external_archive")
            self.assertEqual(receipt["source_system"], "google_drive")
            self.assertFalse(receipt["source_export"]["external_api_called"])

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_import_external_requires_explicit_mode_and_reviewer_for_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:external-guards")
            self.assertEqual(init_code, 0, init_output)
            export_root = KIT_ROOT / "examples" / "external-imports" / "notion-export"

            code, output = self.run_cli(
                [
                    "import-external",
                    str(archive_root),
                    "--source",
                    "notion",
                    "--export",
                    str(export_root),
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("--dry-run or --approve", output)

            code, output = self.run_cli(
                [
                    "import-external",
                    str(archive_root),
                    "--source",
                    "notion",
                    "--export",
                    str(export_root),
                    "--approve",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("--reviewed-by", output)

    def test_import_external_second_run_blocks_on_existing_receipt_or_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:external-duplicate")
            self.assertEqual(init_code, 0, init_output)
            export_root = KIT_ROOT / "examples" / "external-imports" / "notion-export"

            first_code, first_output = self.run_cli(
                [
                    "import-external",
                    str(archive_root),
                    "--source",
                    "notion",
                    "--export",
                    str(export_root),
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(first_code, 0, first_output)

            code, output = self.run_cli(
                [
                    "import-external",
                    str(archive_root),
                    "--source",
                    "notion",
                    "--export",
                    str(export_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("already has imported zettel id" in blocker for blocker in result["blockers"]))

    def test_share_dry_run_checks_scope_and_trust(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "share",
                str(archive_root),
                "--view",
                "view.fake.company.derived",
                "--target-archive",
                "archive:company:fake-blue",
                "--counterparty-id",
                "archive:company:fake-blue",
                "--counterparty-fingerprint",
                "SHA256:fake-company-blue",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["trust_gate"]["status"], "verified")
        self.assertEqual(len(result["scope_gate"]["included"]), 1)
        self.assertEqual(result["scope_gate"]["included"][0]["path"], "zettels/zet_20240505_fake_company_onboarding_insight.md")
        self.assertEqual(result["scope_gate"]["excluded"], [])
        self.assertFalse(result["ownership_gate"]["ownership_transfer"])
        self.assertEqual(result["ownership_gate"]["current_owner"], "person:fake-user")
        self.assertTrue(result["proposed_receipt_path"].startswith("receipts/share/"))

    def test_share_dry_run_requires_counterparty_fingerprint_and_blocks_mismatch(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        missing_code, missing_output = self.run_cli(
            [
                "share",
                str(archive_root),
                "--view",
                "view.fake.company.derived",
                "--target-archive",
                "archive:company:fake-blue",
                "--counterparty-id",
                "archive:company:fake-blue",
                "--dry-run",
            ]
        )
        self.assertEqual(missing_code, 1)
        self.assertIn("Counterparty fingerprint is required", missing_output)

        mismatch_code, mismatch_output = self.run_cli(
            [
                "share",
                str(archive_root),
                "--view",
                "view.fake.company.derived",
                "--target-archive",
                "archive:company:fake-blue",
                "--counterparty-id",
                "archive:company:fake-blue",
                "--counterparty-fingerprint",
                "SHA256:attacker",
                "--dry-run",
            ]
        )
        self.assertEqual(mismatch_code, 1)
        self.assertIn("Counterparty fingerprint does not match", mismatch_output)

    def test_share_dry_run_excludes_sensitive_categories_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            frontmatter = {
                "id": "zet_20260521_fake_medical_note",
                "title": "Fake medical note",
                "created_at": "2026-05-21T00:00:00+09:00",
                "updated_at": "2026-05-21T00:00:00+09:00",
                "archive_id": "archive:personal:fake-life",
                "status": "canonical",
                "kind": "permanent_note",
                "facets": {"domain": "medical", "record_type": "journal"},
                "assets": [],
                "edges": [],
                "provenance": {
                    "created_by": "test",
                    "created_in": "archive:personal:fake-life",
                    "source": "test",
                    "derived_from": [],
                },
                "visibility": {"scope": "private", "allowed_archives": [], "source_visibility": "private"},
                "promotion": {"stage": "promoted"},
            }
            (archive_root / "zettels" / "zet_20260521_fake_medical_note.md").write_text(
                "---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\nSensitive fake medical note.\n",
                encoding="utf-8",
            )
            (archive_root / "views" / "sensitive.yml").write_text(
                archive_cli.dump_yaml(
                    {
                        "id": "view.fake.sensitive.medical",
                        "name": "Sensitive medical view",
                        "for": "ai_context",
                        "filters": {"facets.domain": "medical"},
                    }
                ),
                encoding="utf-8",
            )

            code, output = self.run_cli(
                [
                    "share",
                    str(archive_root),
                    "--view",
                    "view.fake.sensitive.medical",
                    "--target-archive",
                    "archive:company:fake-blue",
                    "--counterparty-id",
                    "archive:company:fake-blue",
                    "--counterparty-fingerprint",
                    "SHA256:fake-company-blue",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertEqual(result["scope_gate"]["included"], [])
            self.assertEqual(result["scope_gate"]["excluded"][0]["path"], "zettels/zet_20260521_fake_medical_note.md")
            self.assertIn("medical", result["scope_gate"]["excluded"][0]["sensitive_categories"])

    def test_delegate_zet_dry_run_previews_receipt_with_hashes(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "delegate-zet",
                str(archive_root),
                "--view",
                "view.fake.company.derived",
                "--target-archive",
                "archive:company:fake-blue",
                "--counterparty-id",
                "archive:company:fake-blue",
                "--counterparty-fingerprint",
                "SHA256:fake-company-blue",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["lifecycle_action"], "delegate")
        self.assertEqual(result["target_policy"], "counterparty_bound")
        self.assertTrue(result["proposed_delegate_receipt_path"].startswith("receipts/delegate/"))
        self.assertEqual(result["delegate_receipt_preview"]["action"], "delegate_zet")
        self.assertEqual(result["delegate_receipt_preview"]["lifecycle_action"], "delegate")
        self.assertEqual(result["delegation_capability"]["target_policy"], "counterparty_bound")
        self.assertEqual(result["delegation_capability"]["settlement_condition"]["mode"], "none")
        self.assertEqual(len(result["delegated_zets"]), 1)
        self.assertEqual(len(result["delegated_zets"][0]["sha256"]), 64)
        self.assertEqual(
            archive_cli.validate_schema(result["delegate_receipt_preview"], "delegate-receipt.schema.json"),
            [],
        )
        self.assertFalse((archive_root / result["proposed_delegate_receipt_path"]).exists())

    def test_delegate_zet_counterparty_bound_requires_target_archive(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "delegate-zet",
                str(archive_root),
                "--view",
                "view.fake.company.derived",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 1)
        result = json.loads(output)
        self.assertFalse(result["ok"])
        self.assertEqual(result["target_policy"], "counterparty_bound")
        self.assertTrue(any("target_archive is required" in blocker for blocker in result["blockers"]))
        self.assertFalse((archive_root / result["proposed_delegate_receipt_path"]).exists())

    def test_delegate_zet_real_requires_approve_and_reviewed_by(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "delegate-zet",
                str(archive_root),
                "--view",
                "view.fake.company.derived",
                "--target-archive",
                "archive:company:fake-blue",
                "--counterparty-id",
                "archive:company:fake-blue",
                "--counterparty-fingerprint",
                "SHA256:fake-company-blue",
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("--dry-run or --approve", output)

        reviewed_code, reviewed_output = self.run_cli(
            [
                "delegate-zet",
                str(archive_root),
                "--view",
                "view.fake.company.derived",
                "--target-archive",
                "archive:company:fake-blue",
                "--counterparty-id",
                "archive:company:fake-blue",
                "--counterparty-fingerprint",
                "SHA256:fake-company-blue",
                "--approve",
            ]
        )
        self.assertEqual(reviewed_code, 1)
        self.assertIn("--reviewed-by", reviewed_output)

    def test_delegate_zet_approve_writes_real_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                [
                    "delegate-zet",
                    str(archive_root),
                    "--view",
                    "view.fake.company.derived",
                    "--target-archive",
                    "archive:company:fake-blue",
                    "--counterparty-id",
                    "archive:company:fake-blue",
                    "--counterparty-fingerprint",
                    "SHA256:fake-company-blue",
                    "--approve",
                    "--reviewed-by",
                    "person:delegate-reviewer",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["target_policy"], "counterparty_bound")
            self.assertEqual(result["reviewed_by"], "person:delegate-reviewer")
            receipt_path = archive_root / result["delegate_receipt_path"]
            self.assertTrue(receipt_path.is_file())

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertFalse(receipt["dry_run"])
            self.assertEqual(receipt["reviewed_by"], "person:delegate-reviewer")
            self.assertEqual(receipt["result"]["created_paths"], [result["delegate_receipt_path"]])
            self.assertEqual(receipt["delegation_capability"]["issue_state"], "issued")
            self.assertNotEqual(receipt["delegation_capability"]["nonce"], "<generated-on-real-delegate>")
            self.assertEqual(receipt["delegation_capability"]["registry_state"]["claim_registry"], "not_implemented")
            self.assertEqual(archive_cli.validate_schema(receipt, "delegate-receipt.schema.json"), [])

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

            duplicate_code, duplicate_output = self.run_cli(
                [
                    "delegate-zet",
                    str(archive_root),
                    "--view",
                    "view.fake.company.derived",
                    "--target-archive",
                    "archive:company:fake-blue",
                    "--counterparty-id",
                    "archive:company:fake-blue",
                    "--counterparty-fingerprint",
                    "SHA256:fake-company-blue",
                    "--approve",
                    "--reviewed-by",
                    "person:delegate-reviewer",
                ]
            )
            self.assertEqual(duplicate_code, 1)
            self.assertIn("zet delegation blocked by dry-run", duplicate_output)

    def test_delegate_zet_claimable_once_approve_writes_receipt_without_target_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                [
                    "delegate-zet",
                    str(archive_root),
                    "--view",
                    "view.fake.company.derived",
                    "--target-policy",
                    "claimable_once",
                    "--approve",
                    "--reviewed-by",
                    "person:delegate-reviewer",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertFalse(result["dry_run"])
            self.assertIsNone(result["target_archive"])
            self.assertEqual(result["target_policy"], "claimable_once")
            receipt = json.loads((archive_root / result["delegate_receipt_path"]).read_text(encoding="utf-8"))
            self.assertIsNone(receipt["target_archive"])
            self.assertEqual(receipt["delegation_capability"]["claim_state"], "unclaimed_receipt_only")
            self.assertEqual(receipt["delegation_capability"]["spent_state"], "not_spent_receipt_only")
            self.assertEqual(receipt["delegation_capability"]["registry_state"]["spent_registry"], "not_implemented")
            self.assertEqual(archive_cli.validate_schema(receipt, "delegate-receipt.schema.json"), [])

    def test_delegate_zet_claimable_once_dry_run_defers_target_trust(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(
            [
                "delegate-zet",
                str(archive_root),
                "--view",
                "view.fake.company.derived",
                "--target-policy",
                "claimable_once",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["target_archive"])
        self.assertEqual(result["target_policy"], "claimable_once")
        self.assertEqual(result["trust_gate"]["status"], "deferred_until_attestation")
        capability = result["delegation_capability"]
        self.assertEqual(capability["target_policy"], "claimable_once")
        self.assertEqual(capability["claim_limit"], 1)
        self.assertEqual(capability["claim_state"], "unclaimed_preview")
        self.assertEqual(capability["spent_state"], "not_spent_preview")
        self.assertEqual(capability["settlement_condition"]["mode"], "none")
        self.assertEqual(
            archive_cli.validate_schema(result["delegate_receipt_preview"], "delegate-receipt.schema.json"),
            [],
        )
        self.assertFalse((archive_root / result["proposed_delegate_receipt_path"]).exists())

    def test_delegate_zet_sensitive_policy_matches_share_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            frontmatter = {
                "id": "zet_20260521_fake_medical_note",
                "title": "Fake medical note",
                "created_at": "2026-05-21T00:00:00+09:00",
                "updated_at": "2026-05-21T00:00:00+09:00",
                "archive_id": "archive:personal:fake-life",
                "status": "canonical",
                "kind": "permanent_note",
                "facets": {"domain": "medical", "record_type": "journal"},
                "assets": [],
                "edges": [],
                "provenance": {
                    "created_by": "test",
                    "created_in": "archive:personal:fake-life",
                    "source": "test",
                    "derived_from": [],
                },
                "visibility": {"scope": "private", "allowed_archives": [], "source_visibility": "private"},
                "promotion": {"stage": "promoted"},
            }
            (archive_root / "zettels" / "zet_20260521_fake_medical_note.md").write_text(
                "---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\nSensitive fake medical note.\n",
                encoding="utf-8",
            )
            (archive_root / "views" / "sensitive.yml").write_text(
                archive_cli.dump_yaml(
                    {
                        "id": "view.fake.sensitive.medical",
                        "name": "Sensitive medical view",
                        "for": "ai_context",
                        "filters": {"facets.domain": "medical"},
                    }
                ),
                encoding="utf-8",
            )

            blocked_code, blocked_output = self.run_cli(
                [
                    "delegate-zet",
                    str(archive_root),
                    "--view",
                    "view.fake.sensitive.medical",
                    "--target-archive",
                    "archive:company:fake-blue",
                    "--counterparty-id",
                    "archive:company:fake-blue",
                    "--counterparty-fingerprint",
                    "SHA256:fake-company-blue",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(blocked_code, 1)
            blocked = json.loads(blocked_output)
            self.assertEqual(blocked["delegated_zets"], [])
            self.assertEqual(blocked["scope_gate"]["excluded"][0]["path"], "zettels/zet_20260521_fake_medical_note.md")

            allowed_code, allowed_output = self.run_cli(
                [
                    "delegate-zet",
                    str(archive_root),
                    "--view",
                    "view.fake.sensitive.medical",
                    "--target-archive",
                    "archive:company:fake-blue",
                    "--counterparty-id",
                    "archive:company:fake-blue",
                    "--counterparty-fingerprint",
                    "SHA256:fake-company-blue",
                    "--allow-sensitive",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(allowed_code, 0, allowed_output)
            allowed = json.loads(allowed_output)
            self.assertEqual(len(allowed["delegated_zets"]), 1)
            self.assertTrue(any("Sensitive zettel allowed" in warning for warning in allowed["warnings"]))

            claimable_blocked_code, claimable_blocked_output = self.run_cli(
                [
                    "delegate-zet",
                    str(archive_root),
                    "--view",
                    "view.fake.sensitive.medical",
                    "--target-policy",
                    "claimable_once",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(claimable_blocked_code, 1)
            claimable_blocked = json.loads(claimable_blocked_output)
            self.assertEqual(claimable_blocked["delegated_zets"], [])
            self.assertEqual(claimable_blocked["trust_gate"]["status"], "deferred_until_attestation")

    def test_attest_and_anchor_zet_dry_run_preview_receipts_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = self.copy_fake_archive(Path(tmp) / "source")
            target_root = self.copy_fake_archive_as_company_target(Path(tmp) / "target")
            delegate_code, delegate_output = self.run_cli(
                [
                    "delegate-zet",
                    str(source_root),
                    "--view",
                    "view.fake.company.derived",
                    "--target-archive",
                    "archive:company:fake-blue",
                    "--counterparty-id",
                    "archive:company:fake-blue",
                    "--counterparty-fingerprint",
                    "SHA256:fake-company-blue",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(delegate_code, 0, delegate_output)
            delegate_result = json.loads(delegate_output)
            delegate_path = self.write_json_receipt(
                target_root,
                delegate_result["proposed_delegate_receipt_path"],
                delegate_result["delegate_receipt_preview"],
            )

            attest_code, attest_output = self.run_cli(
                [
                    "attest-zet",
                    str(target_root),
                    "--delegate-receipt",
                    archive_cli.archive_relative_path(delegate_path, target_root),
                    "--counterparty-id",
                    "archive:personal:fake-life",
                    "--counterparty-fingerprint",
                    "SHA256:fake-user-primary",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(attest_code, 0, attest_output)
            attest_result = json.loads(attest_output)
            self.assertEqual(attest_result["lifecycle_action"], "attest")
            self.assertEqual(attest_result["trust_gate"]["status"], "verified")
            self.assertEqual(len(attest_result["delegated_zets"]), 1)
            self.assertEqual(
                archive_cli.validate_schema(attest_result["attestation_receipt_preview"], "attestation-receipt.schema.json"),
                [],
            )
            self.assertFalse((target_root / attest_result["proposed_attestation_receipt_path"]).exists())

            attestation_path = self.write_json_receipt(
                target_root,
                attest_result["proposed_attestation_receipt_path"],
                attest_result["attestation_receipt_preview"],
            )
            anchor_code, anchor_output = self.run_cli(
                [
                    "anchor-zet",
                    str(target_root),
                    "--attestation-receipt",
                    archive_cli.archive_relative_path(attestation_path, target_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(anchor_code, 0, anchor_output)
            anchor_result = json.loads(anchor_output)
            self.assertEqual(anchor_result["lifecycle_action"], "anchor")
            self.assertEqual(len(anchor_result["anchored_zets"]), 1)
            self.assertEqual(anchor_result["anchor_metadata_preview"]["foreign_provenance_policy"]["do_not_claim_authorship"], True)
            self.assertEqual(
                archive_cli.validate_schema(anchor_result["anchor_metadata_preview"], "anchor-metadata.schema.json"),
                [],
            )
            self.assertFalse((target_root / anchor_result["proposed_anchor_metadata_path"]).exists())

    def test_claimable_once_attest_binds_claimant_and_anchor_preserves_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = self.copy_fake_archive(Path(tmp) / "source")
            target_root = self.copy_fake_archive_as_company_target(Path(tmp) / "target")
            delegate_code, delegate_output = self.run_cli(
                [
                    "delegate-zet",
                    str(source_root),
                    "--view",
                    "view.fake.company.derived",
                    "--target-policy",
                    "claimable_once",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(delegate_code, 0, delegate_output)
            delegate_result = json.loads(delegate_output)
            delegate_path = self.write_json_receipt(
                target_root,
                delegate_result["proposed_delegate_receipt_path"],
                delegate_result["delegate_receipt_preview"],
            )

            attest_code, attest_output = self.run_cli(
                [
                    "attest-zet",
                    str(target_root),
                    "--delegate-receipt",
                    archive_cli.archive_relative_path(delegate_path, target_root),
                    "--counterparty-id",
                    "archive:personal:fake-life",
                    "--counterparty-fingerprint",
                    "SHA256:fake-user-primary",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(attest_code, 0, attest_output)
            attest_result = json.loads(attest_output)
            self.assertEqual(attest_result["verification"]["target_policy"], "claimable_once")
            self.assertTrue(attest_result["verification"]["target_archive_match"])
            self.assertEqual(attest_result["claim_binding"]["claimed_by_archive"], "archive:company:fake-blue")
            self.assertEqual(attest_result["claim_binding"]["spent_state_after_attestation"], "spent_preview")
            self.assertEqual(attest_result["settlement_condition"]["mode"], "none")
            self.assertEqual(
                archive_cli.validate_schema(attest_result["attestation_receipt_preview"], "attestation-receipt.schema.json"),
                [],
            )

            attestation_path = self.write_json_receipt(
                target_root,
                attest_result["proposed_attestation_receipt_path"],
                attest_result["attestation_receipt_preview"],
            )
            anchor_code, anchor_output = self.run_cli(
                [
                    "anchor-zet",
                    str(target_root),
                    "--attestation-receipt",
                    archive_cli.archive_relative_path(attestation_path, target_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(anchor_code, 0, anchor_output)
            anchor_result = json.loads(anchor_output)
            self.assertEqual(anchor_result["claim_binding"]["claimed_by_archive"], "archive:company:fake-blue")
            self.assertEqual(anchor_result["claim_binding"]["spent_state_after_attestation"], "spent_preview")
            self.assertEqual(anchor_result["anchored_zets"][0]["provenance"]["claim_binding"]["target_policy"], "claimable_once")
            self.assertEqual(
                archive_cli.validate_schema(anchor_result["anchor_metadata_preview"], "anchor-metadata.schema.json"),
                [],
            )
            self.assertFalse((target_root / anchor_result["proposed_anchor_metadata_path"]).exists())

    def test_attest_and_anchor_zet_dry_run_block_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = self.copy_fake_archive(Path(tmp) / "source")
            target_root = self.copy_fake_archive_as_company_target(Path(tmp) / "target")
            delegate_code, delegate_output = self.run_cli(
                [
                    "delegate-zet",
                    str(source_root),
                    "--view",
                    "view.fake.company.derived",
                    "--target-archive",
                    "archive:company:fake-blue",
                    "--counterparty-id",
                    "archive:company:fake-blue",
                    "--counterparty-fingerprint",
                    "SHA256:fake-company-blue",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(delegate_code, 0, delegate_output)
            delegate_result = json.loads(delegate_output)
            delegate_path = self.write_json_receipt(
                target_root,
                delegate_result["proposed_delegate_receipt_path"],
                delegate_result["delegate_receipt_preview"],
            )

            bad_fingerprint_code, bad_fingerprint_output = self.run_cli(
                [
                    "attest-zet",
                    str(target_root),
                    "--delegate-receipt",
                    archive_cli.archive_relative_path(delegate_path, target_root),
                    "--counterparty-id",
                    "archive:personal:fake-life",
                    "--counterparty-fingerprint",
                    "SHA256:attacker",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(bad_fingerprint_code, 1)
            bad_fingerprint = json.loads(bad_fingerprint_output)
            self.assertTrue(any("fingerprint does not match" in blocker for blocker in bad_fingerprint["blockers"]))

            mismatch_code, mismatch_output = self.run_cli(
                [
                    "attest-zet",
                    str(source_root),
                    "--delegate-receipt",
                    str(delegate_path),
                    "--counterparty-id",
                    "archive:personal:fake-life",
                    "--counterparty-fingerprint",
                    "SHA256:fake-user-primary",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(mismatch_code, 1)
            mismatch = json.loads(mismatch_output)
            self.assertTrue(any("target_archive does not match" in blocker for blocker in mismatch["blockers"]))

            attest_code, attest_output = self.run_cli(
                [
                    "attest-zet",
                    str(target_root),
                    "--delegate-receipt",
                    archive_cli.archive_relative_path(delegate_path, target_root),
                    "--counterparty-id",
                    "archive:personal:fake-life",
                    "--counterparty-fingerprint",
                    "SHA256:fake-user-primary",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(attest_code, 0, attest_output)
            attest_result = json.loads(attest_output)
            attestation_path = self.write_json_receipt(
                target_root,
                attest_result["proposed_attestation_receipt_path"],
                attest_result["attestation_receipt_preview"],
            )
            anchor_mismatch_code, anchor_mismatch_output = self.run_cli(
                [
                    "anchor-zet",
                    str(source_root),
                    "--attestation-receipt",
                    str(attestation_path),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(anchor_mismatch_code, 1)
            anchor_mismatch = json.loads(anchor_mismatch_output)
            self.assertTrue(any("attesting_archive does not match" in blocker for blocker in anchor_mismatch["blockers"]))

    def test_transfer_ownership_dry_run_previews_family_to_child_receipt_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_family_archive(Path(tmp) / "family-archive")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "person:child-template",
                    "--operator-after",
                    "person:child-template",
                    "--approved-by",
                    "person:member-a",
                    "--approved-by",
                    "person:member-b",
                    "--counterparty-id",
                    "person:child-template",
                    "--counterparty-fingerprint",
                    "SHA256:example-child-primary",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["previous_owner"], "family:example-household")
            self.assertEqual(result["new_owner"], "person:child-template")
            self.assertEqual(result["new_owner_kind"], "person")
            self.assertEqual(result["subject"], "person:child-template")
            self.assertEqual(result["trust_gate"]["status"], "verified")
            self.assertTrue(result["ownership_gate"]["ownership_transfer"])
            self.assertEqual(result["ownership_gate"]["operators_before"], ["person:member-a", "person:member-b"])
            self.assertEqual(result["ownership_gate"]["operators_after"], ["person:child-template"])
            self.assertEqual(result["receipt_preview"]["action"], "transfer_archive_ownership")
            self.assertEqual(result["receipt_preview"]["operators_after"], ["person:child-template"])
            self.assertEqual(result["provider_change_plan"]["status"], "manual_required")
            self.assertIn("provider_change_plan", result["receipt_preview"])
            self.assertTrue(any(item["provider"] == "github" for item in result["provider_change_plan"]["providers"]))
            schema_issues = archive_cli.validate_schema(
                result["receipt_preview"],
                "ownership-transfer-receipt.schema.json",
            )
            self.assertEqual(schema_issues, [])
            for field in [
                "receipt_id",
                "action",
                "dry_run",
                "source_archive",
                "previous_owner",
                "new_owner",
                "operators_before",
                "operators_after",
                "scope_manifest",
                "approval_actors",
                "trust_gate",
                "ownership_gate",
                "lineage",
                "blockers",
                "warnings",
            ]:
                self.assertIn(field, result["receipt_preview"])
            self.assertFalse((archive_root / result["proposed_receipt_path"]).exists())

            identity = archive_cli.load_yaml((archive_root / "archive-identity.yml").read_text(encoding="utf-8"))
            self.assertEqual(identity["ownership"]["owner_id"], "family:example-household")

    def test_transfer_ownership_dry_run_previews_business_unit_spinout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_business_unit_archive(Path(tmp) / "business-unit-archive")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "company:fake-spinout",
                    "--new-owner-kind",
                    "company",
                    "--new-owner-archive",
                    "archive:company:fake-spinout",
                    "--operator-after",
                    "role:spinout-admin",
                    "--operator-after",
                    "person:fake-founder",
                    "--approved-by",
                    "role:business-unit-admin",
                    "--subject",
                    "business_unit:fake-space",
                    "--counterparty-id",
                    "company:fake-spinout",
                    "--counterparty-fingerprint",
                    "SHA256:fake-spinout-primary",
                    "--reason",
                    "business_unit_spinout",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertEqual(result["previous_owner"], "company:fake-blue")
            self.assertEqual(result["new_owner"], "company:fake-spinout")
            self.assertEqual(result["subject"], "business_unit:fake-space")
            self.assertEqual(result["trust_gate"]["status"], "verified")
            self.assertEqual(result["ownership_gate"]["operators_after"], ["role:spinout-admin", "person:fake-founder"])
            self.assertEqual(result["lineage"]["reason"], "business_unit_spinout")
            self.assertEqual(result["provider_change_plan"]["status"], "manual_required")
            self.assertEqual(
                archive_cli.validate_schema(result["receipt_preview"], "ownership-transfer-receipt.schema.json"),
                [],
            )
            self.assertFalse((archive_root / result["proposed_receipt_path"]).exists())

    def test_transfer_ownership_dry_run_blocks_missing_operator_and_trust(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_family_archive(Path(tmp) / "family-archive")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "person:child-template",
                    "--approved-by",
                    "person:member-a",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("--operator-after" in blocker for blocker in result["blockers"]))
            self.assertTrue(any("Counterparty fingerprint is required" in blocker for blocker in result["blockers"]))

    def test_transfer_ownership_dry_run_blocks_fingerprint_mismatch_and_unknown_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_family_archive(Path(tmp) / "family-archive")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "person:child-template",
                    "--operator-after",
                    "person:child-template",
                    "--approved-by",
                    "person:unknown",
                    "--counterparty-id",
                    "person:child-template",
                    "--counterparty-fingerprint",
                    "SHA256:attacker",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            result = json.loads(output)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Approval actor is not the current owner or an operator" in blocker for blocker in result["blockers"]))
            self.assertTrue(any("Counterparty fingerprint does not match" in blocker for blocker in result["blockers"]))

    def test_transfer_ownership_real_requires_approve_and_reviewed_by(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_family_archive(Path(tmp) / "family-archive")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "person:child-template",
                    "--operator-after",
                    "person:child-template",
                    "--approved-by",
                    "person:member-a",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Real ownership transfer requires --approve", output)
            identity = archive_cli.load_yaml((archive_root / "archive-identity.yml").read_text(encoding="utf-8"))
            self.assertEqual(identity["ownership"]["owner_id"], "family:example-household")

            reviewed_code, reviewed_output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "person:child-template",
                    "--operator-after",
                    "person:child-template",
                    "--approved-by",
                    "person:member-a",
                    "--approve",
                ]
            )
            self.assertEqual(reviewed_code, 1)
            self.assertIn("Real ownership transfer requires --reviewed-by", reviewed_output)

    def test_transfer_ownership_real_applies_family_to_child_and_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_family_archive(Path(tmp) / "family-archive")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "person:child-template",
                    "--operator-after",
                    "person:child-template",
                    "--approved-by",
                    "person:member-a",
                    "--approved-by",
                    "person:member-b",
                    "--counterparty-id",
                    "person:child-template",
                    "--counterparty-fingerprint",
                    "SHA256:example-child-primary",
                    "--approve",
                    "--reviewed-by",
                    "person:member-a",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            self.assertTrue(result["ok"])
            self.assertFalse(result["dry_run"])
            self.assertEqual(result["previous_owner"], "family:example-household")
            self.assertEqual(result["new_owner"], "person:child-template")
            self.assertEqual(result["provider_change_plan"]["status"], "manual_required")
            receipt_path = archive_root / result["receipt_path"]
            self.assertTrue(receipt_path.is_file())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertFalse(receipt["dry_run"])
            self.assertEqual(receipt["reviewed_by"], "person:member-a")
            self.assertEqual(receipt["result"]["changed_paths"], ["archive-identity.yml", result["receipt_path"]])
            self.assertFalse(receipt["result"]["provider_changes_applied"])
            self.assertIn("provider_change_plan", receipt)
            self.assertEqual(
                archive_cli.validate_schema(receipt, "ownership-transfer-receipt.schema.json"),
                [],
            )

            identity = archive_cli.load_yaml((archive_root / "archive-identity.yml").read_text(encoding="utf-8"))
            self.assertEqual(identity["ownership"]["owner_id"], "person:child-template")
            self.assertEqual(identity["ownership"]["owner_kind"], "person")
            self.assertEqual(identity["ownership"]["operators"][0]["operator_id"], "person:child-template")
            self.assertEqual(identity["ownership"]["operators"][0]["role"], "owner_operator")
            self.assertIn("ownership_transfers", identity["lineage"])
            self.assertEqual(identity["lineage"]["ownership_transfers"][-1]["receipt_path"], result["receipt_path"])

            doctor_code, doctor_output = self.run_cli(["doctor", str(archive_root), "--strict"])
            self.assertEqual(doctor_code, 0, doctor_output)

    def test_transfer_ownership_real_applies_business_unit_spinout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_business_unit_archive(Path(tmp) / "business-unit-archive")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "company:fake-spinout",
                    "--new-owner-kind",
                    "company",
                    "--new-owner-archive",
                    "archive:company:fake-spinout",
                    "--operator-after",
                    "role:spinout-admin",
                    "--operator-after",
                    "person:fake-founder",
                    "--approved-by",
                    "role:business-unit-admin",
                    "--subject",
                    "business_unit:fake-space",
                    "--counterparty-id",
                    "company:fake-spinout",
                    "--counterparty-fingerprint",
                    "SHA256:fake-spinout-primary",
                    "--reason",
                    "business_unit_spinout",
                    "--approve",
                    "--reviewed-by",
                    "role:business-unit-admin",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            result = json.loads(output)
            identity = archive_cli.load_yaml((archive_root / "archive-identity.yml").read_text(encoding="utf-8"))
            self.assertEqual(identity["ownership"]["owner_id"], "company:fake-spinout")
            self.assertEqual(identity["ownership"]["owner_kind"], "company")
            self.assertEqual(identity["ownership"]["owner_archive_id"], "archive:company:fake-spinout")
            self.assertEqual(
                [item["operator_id"] for item in identity["ownership"]["operators"]],
                ["role:spinout-admin", "person:fake-founder"],
            )
            receipt = json.loads((archive_root / result["receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(receipt["lineage"]["reason"], "business_unit_spinout")
            self.assertEqual(receipt["provider_change_plan"]["status"], "manual_required")

    def test_transfer_ownership_real_blocks_dry_run_failures_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_family_archive(Path(tmp) / "family-archive")
            before_identity = (archive_root / "archive-identity.yml").read_text(encoding="utf-8")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "person:child-template",
                    "--operator-after",
                    "person:child-template",
                    "--approved-by",
                    "person:unknown",
                    "--counterparty-id",
                    "person:child-template",
                    "--counterparty-fingerprint",
                    "SHA256:attacker",
                    "--approve",
                    "--reviewed-by",
                    "person:member-a",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Ownership transfer blocked by dry-run", output)
            self.assertEqual((archive_root / "archive-identity.yml").read_text(encoding="utf-8"), before_identity)
            self.assertFalse(any((archive_root / "receipts" / "lineage").glob("*.ownership-transfer.json")))

    def test_transfer_ownership_real_blocks_existing_receipt_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.init_transfer_ready_family_archive(Path(tmp) / "family-archive")
            receipt_path = (
                archive_root
                / "receipts"
                / "lineage"
                / "archive_family_example_household__to__person_child_template.ownership-transfer.json"
            )
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text("{}\n", encoding="utf-8")
            before_identity = (archive_root / "archive-identity.yml").read_text(encoding="utf-8")
            code, output = self.run_cli(
                [
                    "transfer-ownership",
                    str(archive_root),
                    "--new-owner",
                    "person:child-template",
                    "--operator-after",
                    "person:child-template",
                    "--approved-by",
                    "person:member-a",
                    "--counterparty-id",
                    "person:child-template",
                    "--counterparty-fingerprint",
                    "SHA256:example-child-primary",
                    "--approve",
                    "--reviewed-by",
                    "person:member-a",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("Proposed ownership transfer receipt already exists", output)
            self.assertEqual((archive_root / "archive-identity.yml").read_text(encoding="utf-8"), before_identity)
            self.assertEqual(receipt_path.read_text(encoding="utf-8"), "{}\n")

    def test_providers_cli_returns_binding_summary_and_manual_plan(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["providers", str(archive_root), "--format", "json"])
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["bindings_present"])
        self.assertGreaterEqual(result["binding_count"], 8)
        self.assertEqual(result["provider_change_plan"]["status"], "manual_required")
        self.assertTrue(any(item["provider"] == "neon" for item in result["providers"]))

    def test_doctor_validates_ownership_transfer_receipt_examples(self) -> None:
        archive_root = KIT_ROOT / "examples" / "fake-life-archive"
        code, output = self.run_cli(["doctor", str(archive_root), "--strict"])
        self.assertEqual(code, 0, output)
        self.assertIn("0 error(s), 0 warning(s)", output)

    def test_doctor_flags_malformed_ownership_transfer_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            receipt_path = (
                archive_root
                / "receipts"
                / "lineage"
                / "broken.ownership-transfer.json"
            )
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(
                json.dumps(
                    {
                        "receipt_id": "receipt:ownership-transfer:broken",
                        "action": "wrong_action",
                        "dry_run": True,
                        "source_archive": "archive:family:broken",
                        "previous_owner": {"owner_id": "family:old", "owner_kind": "family"},
                        "new_owner": {"owner_id": "person:new", "owner_kind": "person"},
                        "operators_before": [],
                        "operators_after": [],
                        "approval_actors": [],
                        "trust_gate": {},
                        "ownership_gate": {},
                        "lineage": {},
                        "blockers": [],
                        "warnings": [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("ownership-transfer-receipt.schema.json", output)
            self.assertIn("$.scope_manifest is required", output)
            self.assertIn("ownership_transfer_receipt_action_invalid", output)

    def test_doctor_flags_provider_binding_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            provider_path = archive_root / "provider-bindings.yml"
            data = archive_cli.load_yaml(provider_path.read_text(encoding="utf-8"))
            data["bindings"][0]["auth"] = {"token": "example-provider-token"}
            provider_path.write_text(archive_cli.dump_yaml(data), encoding="utf-8")

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("provider_bindings_secret_field", output)

    def test_doctor_json_paths_are_posix_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:path-test")
            self.assertEqual(init_code, 0, init_output)
            (archive_root / "views" / "homebase.yml").unlink()

            code, output = self.run_cli(["doctor", str(archive_root), "--json"])
            self.assertEqual(code, 1)
            diagnostics = json.loads(output)
            missing_paths = {
                item["path"]
                for item in diagnostics
                if item["code"] == "required_file_missing"
            }
            self.assertIn("views/homebase.yml", missing_paths)
            self.assertNotIn("views\\homebase.yml", missing_paths)

    def test_doctor_flags_posix_local_absolute_paths_inside_zettels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:absolute-path-test")
            self.assertEqual(init_code, 0, init_output)
            frontmatter = {
                "id": "zet_20260520_bad_absolute_path",
                "title": "Bad absolute path",
                "created_at": "2026-05-20T00:00:00+09:00",
                "updated_at": "2026-05-20T00:00:00+09:00",
                "archive_id": "archive:personal:absolute-path-test",
                "status": "draft",
                "kind": "fleeting_capture",
                "facets": {},
                "assets": [],
                "edges": [],
                "provenance": {
                    "created_by": "test",
                    "created_in": "archive:personal:absolute-path-test",
                    "source": "test",
                    "derived_from": [],
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
            zettel_path = archive_root / "inbox" / "zet_20260520_bad_absolute_path.md"
            zettel_path.write_text(
                "---\n"
                + archive_cli.dump_yaml(frontmatter)
                + "---\n\nThis draft mentions /tmp/example/private.txt.\n",
                encoding="utf-8",
            )

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("provider_url_in_zettel", output)

    def test_doctor_warns_when_gitignore_lacks_local_profile_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:gitignore-warn")
            self.assertEqual(init_code, 0, init_output)

            gitignore = archive_root / ".gitignore"
            lines = [
                line
                for line in gitignore.read_text(encoding="utf-8").splitlines()
                if line not in {"profiles/local/", "keyrings/local/"}
            ]
            gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 0, output)
            self.assertIn("local_profile_gitignore_incomplete", output)

    def test_doctor_flags_secret_like_file_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:secret-file")
            self.assertEqual(init_code, 0, init_output)

            (archive_root / ".env").write_text("TOKEN=secretvalue1234567890\n", encoding="utf-8")
            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("secret_file_detected", output)

    def test_doctor_flags_secret_like_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:secret-value")
            self.assertEqual(init_code, 0, init_output)

            config = archive_root / "workbench" / "local-config.yml"
            config.write_text("api_key: sk_test_1234567890abcdef\n", encoding="utf-8")
            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("secret_value_detected", output)

    def test_doctor_warns_when_local_profile_contains_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:local-profile")
            self.assertEqual(init_code, 0, init_output)

            profile = archive_root / "profiles" / "local" / "life.yml"
            profile.parent.mkdir(parents=True)
            profile.write_text(
                archive_cli.dump_yaml(
                    {
                        "profile_id": "keyring:local:test",
                        "name": "Local test profile",
                        "env": {
                            "required": ["ARCHIVE_ROOT"],
                            "ARCHIVE_ROOT": "X:/example/archive",
                        },
                    }
                ),
                encoding="utf-8",
            )
            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 0, output)
            self.assertIn("local_profile_env_values", output)

    def test_doctor_schema_flags_missing_archive_principal_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:schema-archive")
            self.assertEqual(init_code, 0, init_output)

            path = archive_root / "archive.yml"
            data = archive_cli.load_yaml(path.read_text(encoding="utf-8"))
            del data["principal"]["display_name"]
            path.write_text(archive_cli.dump_yaml(data), encoding="utf-8")

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("schema_required", output)
            self.assertIn("$.principal.display_name", output)

    def test_doctor_schema_flags_malformed_object_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:schema-object")
            self.assertEqual(init_code, 0, init_output)

            manifest = archive_root / "objects" / "manifests" / "files.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "object_id": "sha256:" + "a" * 64,
                        "sha256": "a" * 64,
                        "logical_key": "objects/sample/example.txt",
                        "locations": "not-a-list",
                    },
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("schema_required", output)
            self.assertIn("$.provenance", output)
            self.assertIn("schema_type", output)
            self.assertIn("$.locations", output)

    def test_doctor_schema_flags_malformed_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:schema-view")
            self.assertEqual(init_code, 0, init_output)

            path = archive_root / "views" / "homebase.yml"
            data = archive_cli.load_yaml(path.read_text(encoding="utf-8"))
            del data["context_policy"]
            path.write_text(archive_cli.dump_yaml(data), encoding="utf-8")

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("schema_required", output)
            self.assertIn("$.context_policy", output)

    def test_doctor_schema_flags_malformed_workpack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:schema-workpack")
            self.assertEqual(init_code, 0, init_output)

            package = archive_root / "workpacks" / "bad-package" / "package.yml"
            package.parent.mkdir(parents=True)
            package.write_text(
                archive_cli.dump_yaml(
                    {
                        "package_id": "workpack_bad",
                        "source_archive": "archive:personal:schema-workpack",
                        "mode": "teleport",
                        "purpose": "Exercise schema validation.",
                        "contents": {},
                        "permissions": {},
                        "provenance": {},
                    }
                ),
                encoding="utf-8",
            )

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("schema_enum", output)
            self.assertIn("$.mode", output)

    def test_doctor_schema_flags_malformed_zettel_kasten_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "personal-archive"
            init_code, init_output = self.init_personal_archive(archive_root, "archive:personal:schema-layer")
            self.assertEqual(init_code, 0, init_output)

            path = archive_root / "zettel-kasten" / "actions.yml"
            data = archive_cli.load_yaml(path.read_text(encoding="utf-8"))
            data["actions"] = "not-a-list"
            path.write_text(archive_cli.dump_yaml(data), encoding="utf-8")

            code, output = self.run_cli(["doctor", str(archive_root)])
            self.assertEqual(code, 1)
            self.assertIn("schema_type", output)
            self.assertIn("$.actions", output)


if __name__ == "__main__":
    unittest.main()

