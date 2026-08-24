from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.3.320.md"
PACKAGED_RELEASE = (
    KIT / "src" / "wom_kit" / "_resources" / "release-notes" / "v0.3.320.md"
)
HISTORICAL_RELEASE = KIT / "docs" / "releases" / "v0.3.319.md"
HISTORICAL_PACKAGED_RELEASE = PACKAGED_RELEASE.with_name("v0.3.319.md")
CONTRACT = KIT / "docs" / "credential-capability-contract.md"
DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-15-v03320-credential-capability-broker.md"
)
MINUTES = (
    ROOT / "meeting-minutes" / "2026-08-15-v03320-credential-capability-broker.md"
)
SCHEMA = KIT / "schemas" / "credential-capability-v0.1.schema.json"
PACKAGED_SCHEMA = (
    KIT
    / "src"
    / "wom_kit"
    / "_resources"
    / "schemas"
    / "credential-capability-v0.1.schema.json"
)
SKILL_ROOT = KIT / "templates" / "ai-runtime" / "wom-archive"
PACKAGED_SKILL_ROOT = (
    KIT
    / "src"
    / "wom_kit"
    / "_resources"
    / "templates"
    / "ai-runtime"
    / "wom-archive"
)


class V03320ReleaseDocsTests(unittest.TestCase):
    def test_v03320_public_bytes_are_immutable_historical_evidence(self) -> None:
        expected = {
            RELEASE: "4c6710abb93331870df4c18f59976b2cc2a5ef524d9c697647c91c3c77b9a991",
            CONTRACT: "cd7400af193bcaac86c3c41af1cfc9ee206365767e63fcba9de823e766073031",
            DECISION: "ae50c1650381d5f9dad46bd77286565062a290cd9af15b17b7d8b9f50a17ec2d",
            MINUTES: "ce4f9077eee04f55686a4e113e773c9df103810cd9de97cad514fe00f5dfaa80",
        }
        for path, expected_sha256 in expected.items():
            with self.subTest(path=path.name):
                relative = path.relative_to(ROOT).as_posix()
                worktree_diff = subprocess.run(
                    ["git", "diff", "--quiet", "HEAD", "--", relative],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(worktree_diff.returncode, 0)
                committed = subprocess.check_output(
                    ["git", "cat-file", "blob", f"HEAD:{relative}"],
                    cwd=ROOT,
                )
                self.assertEqual(hashlib.sha256(committed).hexdigest(), expected_sha256)

    def test_v03319_public_bytes_are_immutable(self) -> None:
        expected = {
            HISTORICAL_RELEASE: (
                "7d8a53a84cef25bd58c0a9678dee304e067255f28978c4f3e8bf97dbcd3f0219"
            ),
            KIT
            / "docs"
            / "letter132-credential-console-keyboard-readiness-and-causal-evidence.md": (
                "058654fe41f175baab4eab90efbb3bfe9f2635bb35b4f3254bdc6a60bdd614d6"
            ),
            KIT
            / "docs"
            / "archive-infra-decision-log-2026-08-14-v03319-letter132-credential-input-evidence.md": (
                "e5299b6c57d0964157dfb8b098b0ea03538eba84feabc5f26a9938b77fafa4fa"
            ),
            ROOT
            / "meeting-minutes"
            / "2026-08-14-letter132-credential-input-evidence.md": (
                "15a30baca7f4bd0587975cc6a8f85319ddb412190e424544175f8bf923073a29"
            ),
        }
        for path, expected_sha256 in expected.items():
            with self.subTest(path=path.name):
                relative = path.relative_to(ROOT).as_posix()
                worktree_diff = subprocess.run(
                    ["git", "diff", "--quiet", "HEAD", "--", relative],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(worktree_diff.returncode, 0)
                committed = subprocess.check_output(
                    ["git", "cat-file", "blob", f"HEAD:{relative}"],
                    cwd=ROOT,
                )
                self.assertEqual(
                    hashlib.sha256(committed).hexdigest(),
                    expected_sha256,
                )

    def test_v03320_is_source_history_not_the_current_packaged_release(self) -> None:
        self.assertEqual(__version__, "0.4.4")
        self.assertTrue(RELEASE.is_file())
        self.assertFalse(PACKAGED_RELEASE.exists())
        self.assertEqual(SCHEMA.read_bytes(), PACKAGED_SCHEMA.read_bytes())
        self.assertTrue(HISTORICAL_RELEASE.is_file())
        self.assertFalse(HISTORICAL_PACKAGED_RELEASE.exists())

    def test_release_contract_decision_and_minutes_define_exact_authority(self) -> None:
        documents = {
            "release": RELEASE.read_text(encoding="utf-8"),
            "contract": CONTRACT.read_text(encoding="utf-8"),
            "decision": DECISION.read_text(encoding="utf-8"),
            "minutes": MINUTES.read_text(encoding="utf-8"),
        }
        combined = " ".join(" ".join(text.split()) for text in documents.values())
        for token in (
            "wom-kit/credential-capability/v0.1",
            "cap_",
            "128",
            "notion_page_recovery_read",
            "wom:workflow:notion-page-recovery",
            "approve_once",
            "GET",
            "retrieve_page",
            "retrieve_page_as_markdown",
            "read_content",
            "request_sha256",
            "plan_sha256",
            "reviewed_by",
            "max_uses",
            "900",
            "claim deadline",
            "exactly one transport attempt",
            "profiles/local/credential-capabilities/claims/",
            "HMAC",
            "permanently spends",
            "finalization",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_three_way_audit_projection_is_exact(self) -> None:
        contract = " ".join(CONTRACT.read_text(encoding="utf-8").split())
        release = " ".join(RELEASE.read_text(encoding="utf-8").split())
        for text in (contract, release):
            for token in (
                "HMAC-authenticated claim ledger",
                "request_sha256",
                "plan_sha256",
                "budgets",
                "final status",
                "authorized-request count",
                "wom-kit/credential-capability-reference/v0.1",
                "schema, capability id, and capability digest",
                "wom-credential-capability-use-summary/v0.1",
                "claim-created state",
            ):
                with self.subTest(document=text[:24], token=token):
                    self.assertIn(token, text)
            self.assertIn("request/plan digests", text)
            self.assertIn("authenticated claim", text)

        forbidden_overclaims = (
            "recovery receipt and parent result record a wom-credential-capability-use-summary",
            "recovery receipt records the authorized-request count",
            "recovery receipt records the final status",
            "recovery receipt records request_sha256",
            "recovery receipt records plan_sha256",
        )
        for path in (RELEASE, CONTRACT, DECISION, MINUTES):
            lowered = " ".join(path.read_text(encoding="utf-8").lower().split())
            for forbidden in forbidden_overclaims:
                with self.subTest(document=path.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, lowered)

    def test_verified_replay_and_parent_projection_remain_fail_closed(self) -> None:
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in (RELEASE, CONTRACT, DECISION)
        )
        for token in (
            "provider_pending_count",
            "never-provider",
            "never-broker",
            "status: not_required",
            "claim_created: false",
            "creates no capability claim",
            "reads no credential",
            "calls no provider",
            "credential_capability_audit_finalize_failed",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_aside_is_a_product_reference_not_reused_implementation(self) -> None:
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in (RELEASE, CONTRACT, DECISION, MINUTES)
        )
        for token in (
            "https://aside.com/",
            "https://aside.com/policy/terms",
            "proprietary product",
            "secrets invisible to AI",
            "task-scoped",
            "human confirmation",
            "access log",
            "No Aside code",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)
        for forbidden in (
            "Aside open source",
            "copied Aside",
            "Aside protocol implementation",
        ):
            self.assertNotIn(forbidden, combined)

    def test_current_surfaces_keep_v03320_as_previous_history(self) -> None:
        current_paths = (
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            ROOT / "VERSIONING.md",
            KIT / "README.md",
            KIT / "cli" / "README.md",
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "runtime-canonical-entrypoints.md",
            KIT / "docs" / "version-truth-source.md",
            KIT / "docs" / "ai-command-path-routing.md",
            KIT / "docs" / "capability-matrix.md",
            KIT / "docs" / "public-documentation-map.md",
            KIT / "docs" / "public-documentation-map.ko.md",
        )
        v0400_history_paths = tuple(
            path
            for path in current_paths
            if path
            not in (
                ROOT / "VERSIONING.md",
                KIT / "docs" / "python-tool-install.md",
                KIT / "docs" / "python-tool-install.ko.md",
            )
        )
        for path in v0400_history_paths:
            with self.subTest(document=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("0.4.0", text)

        previous_history_paths = tuple(
            path
            for path in current_paths
            if path
            not in (
                ROOT / "VERSIONING.md",
                KIT / "docs" / "ai-command-path-routing.md",
                KIT / "docs" / "python-tool-install.md",
                KIT / "docs" / "python-tool-install.ko.md",
            )
        )
        for path in previous_history_paths:
            with self.subTest(previous_history=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("0.3.320", text)

        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in (RELEASE, CONTRACT, DECISION, MINUTES)
        )
        for token in (
            "no new CLI",
            "no new popup",
            "not a password manager",
        ):
            with self.subTest(token=token):
                self.assertIn(token.casefold(), combined.casefold())

        install = (KIT / "docs" / "python-tool-install.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("wom_kit-0.4.4-py3-none-any.whl", install)

    def test_runtime_skill_and_operator_contract_are_synchronized(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        normalized_skill = " ".join(skill.split())
        self.assertLessEqual(len(skill.splitlines()), 200)
        self.assertLessEqual(len(skill.split()), 1400)
        for token in (
            "fresh plan-bound one-use capability",
            "durably claimed before secret read",
            "verified local replay creates no claim",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized_skill)

        operator = (
            SKILL_ROOT / "references" / "operator-contract.md"
        ).read_text(encoding="utf-8")
        for token in (
            "Approved Notion Recovery Capability",
            "wom-kit/credential-capability/v0.1",
            "wom-kit/credential-capability-reference/v0.1",
            "wom-credential-capability-use-summary/v0.1",
            "exactly one transport attempt",
        ):
            with self.subTest(token=token):
                self.assertIn(token, operator)

        for relative in (
            Path("SKILL.md"),
            Path("references/operator-contract.md"),
        ):
            with self.subTest(resource=relative.as_posix()):
                self.assertEqual(
                    (SKILL_ROOT / relative).read_bytes(),
                    (PACKAGED_SKILL_ROOT / relative).read_bytes(),
                )

    def test_new_public_docs_are_secret_free_and_evidence_bounded(self) -> None:
        for path in (RELEASE, CONTRACT, DECISION, MINUTES):
            text = path.read_text(encoding="utf-8")
            for forbidden in (
                "C:\\Users\\",
                "Bearer ",
                "ntn_",
                "secret_",
                "protected archive",
            ):
                with self.subTest(document=path.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, text)
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in (RELEASE, CONTRACT, DECISION, MINUTES)
        )
        for token in (
            "do not prove merge",
            "external CI",
            "GitHub Release",
            "fresh installation",
            "live credential registration",
            "provider acceptance",
            "completed 620-page recovery",
        ):
            with self.subTest(token=token):
                self.assertIn(token.casefold(), combined.casefold())


if __name__ == "__main__":
    unittest.main()
