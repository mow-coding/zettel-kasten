"""Beta letter 184, part 2: a conversation's zettel-objet links in its own Git backup.

One conversation wrote 43 zettel-objet links under its work-session grant and
could not back them up through the session-scoped Git route, because nothing
proved the changed zettels were its own. Since v0.4.66 the route selects, for
the session that owns MAC-verified link approvals: the changed zettel (only
when HEAD is the recorded preimage and the worktree is exactly this
session's links), the link receipt, the before-snapshot and the usage record.
The shared objet ledger and the objet bytes stay out.

Real temporary Git, registry, grants, claims and link writes through the CLI;
synthetic files only.
"""
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from wom_kit import archive_cli as cli
from wom_kit import archive_services
from wom_kit import git_backup_session_scope as scope
from wom_kit import presenter_fingerprint
from wom_kit import work_session_link_git_provenance as links
from wom_kit.work_session_binding import WorkSessionBinding

import test_v0424_session_permission_modes as permission_fixture

KIT = Path(__file__).resolve().parents[1]
SOURCE_ZETTEL = "zet_20240504_fake_lunch_thought"
NEWLINE = bytes([10])


class _LinkFixture(unittest.TestCase):
    _Base = permission_fixture.SessionPermissionModeTests
    setUp = _Base.setUp
    call = _Base.call
    session_call = _Base.session_call
    establish = _Base.establish
    routing = _Base.routing
    manifested_source = _Base.manifested_source
    set_mode = _Base.set_mode
    env = _Base.env
    presenter_env = _Base.presenter_env

    def seed(self, *zettel_ids):
        """Committed and pushed baseline: canonical zettels of this archive."""
        root = self.root
        archive_id = yaml.safe_load((root / "archive.yml").read_text(encoding="utf-8"))["archive_id"]
        template = (KIT / "examples" / "fake-life-archive" / "zettels" / (SOURCE_ZETTEL + ".md")).read_text(
            encoding="utf-8").replace("archive:personal:fake-life", archive_id)
        (root / "zettels").mkdir(exist_ok=True)
        for zettel_id in zettel_ids:
            (root / "zettels" / (zettel_id + ".md")).write_bytes(
                template.replace(SOURCE_ZETTEL, zettel_id).encode("utf-8"))
        (root / ".gitignore").write_bytes(b"profiles/local/" + NEWLINE + b"db/" + NEWLINE + b"*.lock" + NEWLINE)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed archive")
        self.git("push", str(self.fixture.remote), "HEAD:refs/heads/main")

    def granted(self, name):
        task = self.establish(name)
        self.set_mode(task, "allow_all")
        return task

    def link(self, task, zettel_id, raw, *, with_grant=True):
        """One real zettel-objet-link write; returns its applied result."""
        object_id = self.manifested_source(raw)
        self.assertTrue(archive_services.index_archive(self.root).get("ok"))
        common = ["zettel-objet-link", str(self.root), "--zettel-id", zettel_id, "--object-id", object_id,
                  "--role", "evidence", "--format", "json"]
        clean = {name: value for name, value in os.environ.items() if not name.startswith("WOM_")}
        environment = {**clean, **(self.env(task) if with_grant else {})}

        def run(*flags):
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                code = cli.main([*common, *flags])
            return code, json.loads(output.getvalue())
        with patch.dict(os.environ, environment, clear=True), \
                patch.object(presenter_fingerprint, "observe", return_value=None):
            code, preview = run("--dry-run")
            self.assertEqual(code, 0, preview)
            code, applied = run("--approve", "--expected-plan-sha256", preview["summary"]["plan_sha256"],
                                "--reviewed-by", "person:synthetic-link-reviewer")
        self.assertEqual(code, 0, applied)
        self.assertEqual(applied["state"], "written")
        self.assertEqual(applied["exact_human_approval"]["live_dialog_shown"], not with_grant)
        return applied

    def preview(self, task):
        return self.call("git-backup-reconcile-plan", *task["refs"], "--work-session-ref", task["session"],
                         "--dry-run", "--credential-mode", "stored", ok=None)

    def apply(self, task, ok=None):
        return self.call("git-backup-reconcile-plan", *task["refs"], "--work-session-ref", task["session"],
                         "--approve", "--credential-mode", "stored", "--reviewed-by",
                         "person:synthetic-git-reviewer", ok=ok)

    def status(self):
        return self.git("status", "--porcelain", "-uall").stdout

    def committed(self):
        return set(self.git("show", "--name-only", "--format=", "HEAD").stdout.split())


class LinkBackupTests(_LinkFixture):
    def test_links_are_selected_committed_and_everything_shared_stays_out(self):
        self.seed("zet_20260101_alpha", "zet_20260101_beta")
        task = self.granted("links")
        first = self.link(task, "zet_20260101_alpha", b"synthetic objet one" + NEWLINE)
        second = self.link(task, "zet_20260101_alpha", b"synthetic objet two" + NEWLINE)   # a chain of two
        third = self.link(task, "zet_20260101_beta", b"synthetic objet three" + NEWLINE)
        preview = self.preview(task)
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["status"], "session_output_selection_classified")
        self.assertEqual(preview["authenticated_link_approval_count"], 3)
        self.assertEqual(preview["accepted_link_receipt_count"], 3)
        self.assertEqual(preview["selected_linked_zettel_count"], 2)
        self.assertEqual(preview["linked_zettel_not_selected_count"], 0)
        # 2 zettels + 3 link receipts + 3 usage records + before-snapshots (one per distinct preimage)
        self.assertGreaterEqual(preview["selected_link_output_count"], 2 + 3 + 3 + 2)
        coverage = preview["session_backup_coverage"]
        self.assertEqual(coverage["selected_by_kind"]["linked_zettel_document"], 2)
        self.assertEqual(coverage["selected_by_kind"]["zettel_objet_link_receipt"], 3)
        self.assertEqual(coverage["selected_by_kind"]["session_object_usage_record"], 3)
        rows = {row["operation"]: row for row in coverage["session_operations"]["operations"]}
        self.assertEqual(rows["zettel_objet_link"]["git_changes"], "session_ownership_provable")
        self.assertEqual(coverage["shared_by_design_changed_path_count"], 1)
        self.assertNotIn("zet_20260101", json.dumps(preview))

        applied = self.apply(task)
        self.assertTrue(applied.get("ok"), applied)
        self.assertEqual(applied["status"], "session_documents_backed_up")
        self.assertEqual(applied["selected_linked_zettel_count"], 2)
        committed = self.committed()
        self.assertIn("zettels/zet_20260101_alpha.md", committed)
        self.assertIn("zettels/zet_20260101_beta.md", committed)
        for result in (first, second, third):
            self.assertIn(result["summary"]["receipt_path"], committed)
        self.assertEqual(sum(path.startswith("receipts/session-object-usage/") for path in committed), 3)
        # the shared ledger and the objet bytes are never part of a session backup
        self.assertFalse(any(path.startswith("objects/") for path in committed))
        remaining = self.status()
        self.assertIn("objects/manifests/files.jsonl", remaining)
        self.assertNotIn("zettels/", remaining)
        self.assertNotIn("zettel-links/link.", remaining)
        # the commit reached the remote
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.fixture.git(self.fixture.remote, "rev-parse", "refs/heads/main").stdout.strip(), head)
        resumed = self.call("git-backup-reconcile-plan", *task["refs"], "--resume", ok=None)
        self.assertTrue(resumed.get("original_operation_already_completed"), resumed)

    def test_a_zettel_with_any_other_pending_edit_is_not_selected(self):
        self.seed("zet_20260102_before", "zet_20260102_after")
        task = self.granted("edits")
        # an uncommitted edit that existed before the link: HEAD is not the recorded preimage
        early = self.root / "zettels" / "zet_20260102_before.md"
        early.write_bytes(early.read_bytes() + b"an earlier uncommitted line" + NEWLINE)
        self.link(task, "zet_20260102_before", b"synthetic objet four" + NEWLINE)
        # an edit made after the link: the worktree is not the recorded postimage
        self.link(task, "zet_20260102_after", b"synthetic objet five" + NEWLINE)
        late = self.root / "zettels" / "zet_20260102_after.md"
        late.write_bytes(late.read_bytes() + b"a later uncommitted line" + NEWLINE)
        preview = self.preview(task)
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["selected_linked_zettel_count"], 0)
        self.assertEqual(preview["linked_zettel_not_selected_count"], 2)
        self.assertEqual(preview["accepted_link_receipt_count"], 2)
        applied = self.apply(task)
        self.assertTrue(applied.get("ok"), applied)
        self.assertFalse(any(path.startswith("zettels/") for path in self.committed()))
        self.assertIn(" M zettels/zet_20260102_before.md", self.status())
        self.assertIn(" M zettels/zet_20260102_after.md", self.status())

    def test_another_conversation_and_window_approved_links_are_never_attributed(self):
        self.seed("zet_20260103_mine", "zet_20260103_theirs", "zet_20260103_shared", "zet_20260103_window")
        mine, theirs = self.granted("mine"), self.granted("theirs")
        self.link(mine, "zet_20260103_mine", b"synthetic objet six" + NEWLINE)
        self.link(theirs, "zet_20260103_theirs", b"synthetic objet seven" + NEWLINE)
        # both conversations linked the same zettel: its change is not one session's
        self.link(mine, "zet_20260103_shared", b"synthetic objet eight" + NEWLINE)
        self.link(theirs, "zet_20260103_shared", b"synthetic objet nine" + NEWLINE)
        # approved through a window: the claim carries no session
        self.link(mine, "zet_20260103_window", b"synthetic objet ten" + NEWLINE, with_grant=False)
        preview = self.preview(mine)
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["authenticated_link_approval_count"], 2)
        self.assertEqual(preview["selected_linked_zettel_count"], 1)
        self.assertEqual(preview["linked_zettel_not_selected_count"], 1)
        applied = self.apply(mine)
        self.assertTrue(applied.get("ok"), applied)
        committed = self.committed()
        self.assertEqual({path for path in committed if path.startswith("zettels/")},
                         {"zettels/zet_20260103_mine.md"})
        remaining = self.status()
        for name in ("zet_20260103_theirs", "zet_20260103_shared", "zet_20260103_window"):
            self.assertIn(" M zettels/" + name + ".md", remaining)

    def test_forged_duplicate_receipt_and_tampered_usage_record_prove_nothing(self):
        self.seed("zet_20260104_real", "zet_20260104_other", "zet_20260104_tampered")
        task = self.granted("forgery")
        real = self.link(task, "zet_20260104_real", b"synthetic objet eleven" + NEWLINE)
        tampered = self.link(task, "zet_20260104_tampered", b"synthetic objet twelve" + NEWLINE)
        receipt_path = self.root.joinpath(*real["summary"]["receipt_path"].split("/"))
        # a receipt rewritten to point at another zettel breaks the receipt's own
        # path bindings: it is not a valid receipt and is ignored
        forged = json.loads(receipt_path.read_text(encoding="utf-8"))
        forged["zettel_path"] = "zettels/zet_20260104_other.md"
        invalid = receipt_path.parent / "link.ffffffffffffffffffffffff.g0001.json"
        invalid.write_text(json.dumps(forged), encoding="utf-8")
        # a usage record whose bytes no longer match its MAC
        approval_id = tampered["exact_human_approval"]["exact_human_approval"]["approval_id"]             if "exact_human_approval" in tampered["exact_human_approval"] else tampered["exact_human_approval"]["approval_id"]
        usage = self.root / "receipts" / "session-object-usage" / (approval_id + "-0.json")
        document = json.loads(usage.read_bytes())
        document["payload"]["object_ids"] = ["sha256:" + "a" * 64]
        from wom_kit.session_object_usage import encoded
        usage.write_bytes(encoded(document))
        preview = self.preview(task)
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["authenticated_link_approval_count"], 1)   # the tampered one is gone
        self.assertEqual(preview["accepted_link_receipt_count"], 1)         # the invalid forgery is ignored
        self.assertEqual(preview["selected_linked_zettel_count"], 1)        # only the real link's zettel
        self.assertEqual(preview["linked_zettel_candidate_count"], 1)
        # a second VALID receipt naming the same approval: neither proves anything
        (receipt_path.parent / "link.eeeeeeeeeeeeeeeeeeeeeeee.g0001.json").write_bytes(receipt_path.read_bytes())
        invalid.unlink()
        preview = self.preview(task)
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["accepted_link_receipt_count"], 0)
        self.assertEqual(preview.get("selected_linked_zettel_count", 0), 0)
        coverage = preview["session_backup_coverage"]["selected_by_kind"]
        self.assertNotIn("linked_zettel_document", coverage)
        self.assertNotIn("zettel_objet_link_receipt", coverage)
        self.assertIn(" M zettels/zet_20260104_real.md", self.status())

    def test_the_git_claim_reaudits_the_link_claims_before_writing(self):
        self.seed("zet_20260105_audit")
        task = self.granted("audit")
        self.link(task, "zet_20260105_audit", b"synthetic objet thirteen" + NEWLINE)
        head = self.git("rev-parse", "HEAD").stdout.strip()
        calls = []
        original = links._ClaimAuthenticator.run

        def refusing(authenticator, consumer):
            calls.append(type(authenticator.claim).__name__)
            return consumer(lambda *_arguments: None)       # the claim audit attributes nothing
        with patch.object(links._ClaimAuthenticator, "run", refusing):
            refused = self.apply(task)
        self.assertTrue(calls)
        self.assertFalse(refused.get("ok"), refused)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), head)   # nothing was committed
        self.assertIn(" M zettels/zet_20260105_audit.md", self.status())
        self.assertIs(links._ClaimAuthenticator.run, original)


class TransitionTests(unittest.TestCase):
    PRE = (KIT / "examples" / "fake-life-archive" / "zettels" / (SOURCE_ZETTEL + ".md")).read_bytes()

    def post(self, assets, *, body_suffix="", title=None, keep_updated_at=False):
        text = self.PRE.decode("utf-8")
        match = archive_services.FRONTMATTER_RE.match(text)
        frontmatter = dict(archive_services.parse_approval_zettel_content_boundary(text)["frontmatter"])
        frontmatter["assets"] = [*frontmatter.get("assets", []),
                                 *({"object_id": object_id, "role": role} for object_id, role in assets)]
        if not keep_updated_at:
            frontmatter["updated_at"] = "2026-10-06T00:00:00+00:00"
        if title is not None:
            frontmatter["title"] = title
        return ("---" + chr(10) + archive_services.dump_yaml(frontmatter) + "---" + chr(10)
                + text[match.end():] + body_suffix).encode("utf-8")

    def chain(self, *pairs):
        return [{"object_id": object_id, "role": role} for object_id, role in pairs]

    def test_only_appended_assets_and_updated_at_may_differ(self):
        one, two = "sha256:" + "1" * 64, "sha256:" + "2" * 64
        check = links._transition_is_only_these_links
        self.assertTrue(check(self.PRE, self.post([(one, "evidence")]), self.chain((one, "evidence"))))
        self.assertTrue(check(self.PRE, self.post([(one, "evidence"), (two, "source")]),
                              self.chain((one, "evidence"), (two, "source"))))
        # wrong objet, wrong role, wrong order, an extra asset, a changed body, a changed field, not a zettel
        self.assertFalse(check(self.PRE, self.post([(two, "evidence")]), self.chain((one, "evidence"))))
        self.assertFalse(check(self.PRE, self.post([(one, "source")]), self.chain((one, "evidence"))))
        self.assertFalse(check(self.PRE, self.post([(two, "source"), (one, "evidence")]),
                               self.chain((one, "evidence"), (two, "source"))))
        self.assertFalse(check(self.PRE, self.post([(one, "evidence"), (two, "source")]),
                               self.chain((one, "evidence"))))
        self.assertFalse(check(self.PRE, self.post([(one, "evidence")], body_suffix="another line" + chr(10)),
                               self.chain((one, "evidence"))))
        self.assertFalse(check(self.PRE, self.post([(one, "evidence")], title="Another title"),
                               self.chain((one, "evidence"))))
        self.assertFalse(check(b"not a zettel", self.post([(one, "evidence")]), self.chain((one, "evidence"))))
        self.assertFalse(check(self.PRE, b"not a zettel", self.chain((one, "evidence"))))


class ChainTests(unittest.TestCase):
    def link(self, before, after):
        return {"before_sha256": "sha256:" + before * 64, "after_sha256": "sha256:" + after * 64}

    def test_chain_must_run_from_head_to_worktree_through_own_links_only(self):
        a, b, c = self.link("a", "b"), self.link("b", "c"), self.link("c", "d")
        sha = lambda letter: "sha256:" + letter * 64
        self.assertEqual(links._chain([b, a], sha("a"), sha("c")), [a, b])
        self.assertEqual(links._chain([a, b, c], sha("a"), sha("d")), [a, b, c])
        self.assertIsNone(links._chain([a, c], sha("a"), sha("d")))          # a missing step
        self.assertIsNone(links._chain([a, b], sha("b"), sha("b")))          # nothing changed
        self.assertIsNone(links._chain([a, self.link("a", "c")], sha("a"), sha("c")))   # two links from one preimage
        self.assertIsNone(links._chain([self.link("a", "b"), self.link("b", "a")], sha("a"), sha("c")))  # a loop


class ScopeCodecTests(unittest.TestCase):
    def binding(self, session="c"):
        return WorkSessionBinding.from_document({
            "schema": "wom-kit/work-session-binding/v1",
            "archive_identity_sha256": "sha256:" + "a" * 64,
            "client_app_ref": "client_app_" + "b" * 32,
            "workstream_ref": "workstream_" + "d" * 32,
            "work_session_ref": "work_session_" + session * 32,
            "session_revision": 1,
        }) if False else None

    def proof(self, binding_document, **changes):
        proof = {"change_ref": "change:000001", "producer": scope._LINK_PRODUCER,
                 "output_kind": "zettel_objet_link_receipt", "whole_file_sha256": "sha256:" + "1" * 64,
                 "whole_file_bytes": 10, "head_file_sha256": None, "head_file_bytes": None,
                 "document_path_sha256": "sha256:" + "2" * 64, "link_evidence_sha256": "sha256:" + "3" * 64,
                 "link_count": 1, "original_work_session_binding": binding_document}
        proof.update(changes)
        return proof

    def test_link_proof_shape_is_closed(self):
        import test_v0420_git_backup_session_scope as scope_fixtures
        fixture = scope_fixtures.SessionScopeTests()
        fixture.setUp()
        binding = WorkSessionBinding.from_document(fixture.scope.document()["work_session_binding"])
        good = self.proof(binding.document())
        scope._validate_link_proof(good, binding)
        zettel = self.proof(binding.document(), output_kind="linked_zettel_document",
                            head_file_sha256="sha256:" + "4" * 64, head_file_bytes=9, link_count=2)
        scope._validate_link_proof(zettel, binding)
        for bad in (
            self.proof(binding.document(), output_kind="unknown_kind"),
            self.proof(binding.document(), link_count=2),                      # a receipt has one link
            self.proof(binding.document(), head_file_sha256="sha256:" + "4" * 64, head_file_bytes=9),
            self.proof(binding.document(), output_kind="linked_zettel_document"),   # a zettel needs its preimage
            self.proof(binding.document(), link_count=0),
            {**good, "label": "PRIVATE"},
            {key: value for key, value in good.items() if key != "link_evidence_sha256"},
        ):
            with self.subTest(bad=sorted(set(bad) ^ set(good)) or bad["output_kind"]), \
                    self.assertRaises(scope.GitBackupSessionScopeError):
                scope._validate_link_proof(bad, binding)
        self.assertTrue(scope._is_link_proof(good))
        self.assertFalse(scope._is_link_proof({"producer": "authenticated_local_recovery_document_output"}))

    def test_link_proofs_need_the_scope_first_inspection_paths(self):
        import test_v0420_git_backup_session_scope as scope_fixtures
        fixture = scope_fixtures.SessionScopeTests()
        fixture.setUp()
        value = fixture.scope.document()
        binding = WorkSessionBinding.from_document(value["work_session_binding"])
        arguments = dict(task_route_ref=value["task_route_ref"], actor_sha256=value["actor_sha256"],
                         registry_preimage_sha256=value["registry_preimage_sha256"], claim_ref=value["claim_ref"],
                         work_session_binding=binding, selection_sha256=value["selection_sha256"],
                         selected_change_count=1, excluded_change_count=0,
                         producer_proofs=[self.proof(binding.document())])
        with self.assertRaises(scope.GitBackupSessionScopeError):
            scope._GitBackupSessionScope.build(**arguments)
        built = scope._GitBackupSessionScope.build(**arguments, inspection_paths=["receipts/x.json"])
        self.assertEqual(built.document()["schema"], "wom-kit/git-backup-session-scope/v5")
        self.assertEqual(built.operation_evidence().schema, "wom-kit/git-backup-session-scope-evidence/v5")
        # the historical scope still decodes byte for byte
        self.assertEqual(scope._GitBackupSessionScope.from_document(value)._raw, fixture.scope._raw)


if __name__ == "__main__":
    unittest.main()
