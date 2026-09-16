"""Real claims/MACs and common checkpoint receipts; synthetic Git assertions.

Preparation uses a real temporary Git repository. Common execution targets and
terminal OIDs are intentionally synthetic: these tests prove authentication,
not commit-object or remote verification, and never exercise a public workflow.
"""

from copy import deepcopy
from dataclasses import replace
import inspect
import json
from pathlib import Path
import unittest
from unittest import mock

import test_exact_operation_manifest as common_fixtures
import test_git_backup_writer as git_fixtures
import test_v0420_git_backup_session_scope as scope_fixtures
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_git_terminal as terminal
from wom_kit.exact_human_approval_windows import _ExactHumanApprovalDecision


COMMITS = ("1" * 40, "2" * 40)
PRIVATE = "SYNTHETIC_PRIVATE_MARKER"


class GitTerminalGrammarTests(unittest.TestCase):
    def test_fixed_errors_and_private_signatures(self):
        class PrivateString(str):
            def __hash__(self):
                raise AssertionError(PRIVATE)

        for value in ([], {}, None, True, PRIVATE, PrivateString("work_session_git_terminal_invalid")):
            error = terminal.WorkSessionGitTerminalError(value)
            self.assertEqual(str(error), "work_session_git_terminal_invalid")
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)
        for function in (terminal._build_git_terminal_record, terminal._authenticate_git_terminal_record,
                         terminal._authenticate_git_terminal_record_with_claim):
            self.assertTrue({"approve", "native", "key_provider", "completed", "remote_verified",
                             "actor", "scope", "approval_id", "allowed_statuses"}.isdisjoint(inspect.signature(function).parameters))


class GitTerminalAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = git_fixtures.GitBackupWriterTests(methodName="runTest")
        cls.fixture.setUp()
        cls.addClassCleanup(cls.fixture.tearDown)
        cls.root = cls.fixture.root
        cls.prepared = cls.fixture.plan_and_prepare(group_count=2)

    def setUp(self):
        self.context = writer._git_backup_approval_context(
            self.prepared, reviewer_claim="person:" + PRIVATE,
        )
        self.claim = self.new_claim()
        self.key = git_fixtures._KeyProvider()

    def new_claim(self):
        decision = _ExactHumanApprovalDecision(
            approved=True, synthetic_acknowledged=False, reason_code="exact_human_approval_approved",
            plan_sha256=self.context.plan_sha256, target_binding_sha256=self.context.target_binding_sha256,
        )
        claim = approval._claim_exact_human_approval_core(
            self.root, self.context, decision, bytes(range(32)),
        )
        self.addCleanup(claim.close)
        return claim

    def common(self, *, authenticated=True):
        target = common_fixtures._Target()
        for item in self.prepared.manifest.items:
            target.identities[(item.target_kind, item.target_ref)] = item.target_identity_sha256
            for field in item.fields:
                target.values[(item.target_kind, item.target_ref, field.field_ref)] = writer._PENDING
        authority = exact.ExactOperationApprovalAuthority.from_reference(self.claim.public_reference())

        def authenticate(payload):
            return {"approval_reference": self.claim.assert_ready_for_context(self.context),
                    "terminal_mac": self.claim.exact_terminal_record_mac(payload)}

        with exact.ExactOperationWriterLock(self.root) as held:
            result = exact.apply_exact_operation(
                self.prepared.manifest, payloads=writer._GitBackupPayloads(self.prepared),
                writer=common_fixtures._Writer(target), verifier=common_fixtures._Verifier(target),
                checkpoint_store=exact.FileExactOperationCheckpointStore(self.root, writer_lock=held),
                approval_authority=authority,
                completion_authenticator=authenticate if authenticated else None,
            )
        return result

    def build(self, *, commits=COMMITS, claim=None, context=None):
        return terminal._build_git_terminal_record(
            self.prepared, context=self.context if context is None else context,
            claim=self.claim if claim is None else claim, commit_oids=commits,
        )

    def audit(self, record, *, context=None, prepared=None):
        return self.key.use_key(
            self.root,
            lambda key: terminal._authenticate_git_terminal_record(
                self.prepared if prepared is None else prepared,
                context=self.context if context is None else context,
                record=record, receipt_authentication_key=key,
            ),
            create_if_missing=False,
        )

    def claim_audit(self, record, *, claim=None, context=None):
        return terminal._authenticate_git_terminal_record_with_claim(
            self.prepared, context=self.context if context is None else context, record=record,
            claim=self.claim if claim is None else claim,
        )

    def assert_private_error(self, caught):
        error = caught.exception
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for marker in (PRIVATE, str(self.root), self.prepared.remote_url, "tracked.txt"):
            self.assertNotIn(marker, str(error) + repr(error))

    def evidence_bytes(self):
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for base in (self.root / "profiles" / "local", self.root / "receipts")
            if base.exists() for path in base.rglob("*") if path.is_file()
        }

    def test_roundtrip_authenticates_original_evidence_but_never_git_state_or_writes(self):
        result = self.common()
        record = self.build()
        with self.assertRaises(terminal.WorkSessionGitTerminalError):
            self.audit(record)  # A started claim is not a historical success.
        self.claim.finalize_succeeded()
        before = self.evidence_bytes()
        with mock.patch.object(writer.planning, "_local_git_raw", side_effect=AssertionError(PRIVATE)), \
             mock.patch.object(writer.planning, "_run_transport_capped", side_effect=AssertionError(PRIVATE)), \
             mock.patch.object(workflow, "_production_key_provider", side_effect=AssertionError(PRIVATE)), \
             mock.patch.object(approval, "_claim_exact_human_approval_core", side_effect=AssertionError(PRIVATE)), \
             mock.patch.object(exact, "apply_exact_operation", side_effect=AssertionError(PRIVATE)), \
             mock.patch.object(git_fixtures._Native, "show", side_effect=AssertionError(PRIVATE)):
            verified = self.audit(terminal._GitTerminalRecord(record._raw))
        self.assertEqual(self.evidence_bytes(), before)
        summary = verified.authentication_summary()
        self.assertTrue(summary["authentication_verified"])
        self.assertTrue(summary["common_completion_authentication_verified"])
        for name in ("commit_anchors_verified", "remote_ref_independently_verified", "backup_completion_verified"):
            self.assertFalse(summary[name])
        document = record._document()
        self.assertEqual(document["payload"]["commit_oids"], list(COMMITS))
        self.assertEqual(document["payload"]["terminal_commit_oid"], COMMITS[-1])
        self.assertEqual(document["payload"]["common_final_receipt_sha256"], result["final_receipt_sha256"])
        self.assertEqual(document["payload"]["exact_remote_ref_binding_sha256"], writer._sha256_json({
            "schema": "wom-kit/git-terminal-exact-remote-ref/v1",
            "remote_url": self.prepared.remote_url, "target_ref": self.prepared.target_ref,
        }))
        document["payload"]["commit_oids"].reverse()
        self.assertEqual(record._document()["payload"]["commit_oids"], list(COMMITS))
        for marker in (PRIVATE, str(self.root), self.prepared.remote_url, "tracked.txt"):
            self.assertNotIn(marker, record._raw.decode() + repr(record) + repr(verified) + json.dumps(summary))
        self.assertTrue(all(value is False for value in self.key.create_if_missing))

    def test_succeeded_or_failed_claim_cannot_create_new_signed_assertions(self):
        self.common()
        self.claim.finalize_succeeded()
        before = self.evidence_bytes()
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            self.build()
        self.assert_private_error(caught)
        self.assertEqual(self.evidence_bytes(), before)
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            self.build(claim=object())
        self.assert_private_error(caught)
        failed = self.new_claim()
        failed.finalize_failed("synthetic_failure")
        before = self.evidence_bytes()
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            self.build(claim=failed)
        self.assert_private_error(caught)
        self.assertEqual(self.evidence_bytes(), before)

    def test_scoped_manifest_evidence_is_bound_without_attesting_producer_ownership(self):
        # The scope fixture contains deliberately unauthenticated producer rows.
        # Authenticating this terminal assertion does not authenticate those rows.
        self.prepared, _selection = scope_fixtures.prepare_scoped_fixture(self.fixture)
        self.context = writer._git_backup_approval_context(
            self.prepared, reviewer_claim="person:" + PRIVATE,
        )
        self.claim = self.new_claim()
        self.common()
        record = self.build(commits=(COMMITS[0],))
        evidence = self.prepared.manifest.operation_evidence.document()
        payload = record._document()["payload"]
        self.assertEqual(payload["operation_evidence_sha256"], writer._sha256_json(evidence))
        self.assertEqual(payload["work_session_binding_sha256"],
                         self.prepared.manifest.work_session_binding.binding_sha256)
        self.assertEqual(self.prepared.manifest.work_session_binding.revision, 7)
        self.claim.finalize_succeeded()
        self.assertFalse(self.audit(record).authentication_summary()["backup_completion_verified"])
        changed = record._document()
        changed["payload"]["operation_evidence_sha256"] = None
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            self.audit(terminal._GitTerminalRecord(approval._canonical_bytes(changed)))
        self.assert_private_error(caught)
        for marker in ("task_route_", "claim_", "authenticated_work_session_completion_receipt"):
            self.assertNotIn(marker, record._raw.decode())

    def test_corrupt_common_checkpoint_blocks_signing_and_historical_authentication_without_repair(self):
        result = self.common()
        record = self.build()
        path = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints" / (result["execution_sha256"][7:] + ".jsonl")
        raw = path.read_bytes()
        path.write_bytes(PRIVATE.encode())
        try:
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.build()
            self.assert_private_error(caught)
            self.claim.finalize_succeeded()
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.audit(record)
            self.assert_private_error(caught)
            self.assertEqual(path.read_bytes(), PRIVATE.encode())
        finally:
            path.write_bytes(raw)

    def test_missing_or_unsigned_legacy_common_result_is_not_upgraded(self):
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            self.build()
        self.assert_private_error(caught)
        self.common(authenticated=False)
        before = self.evidence_bytes()
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            self.build()
        self.assert_private_error(caught)
        self.assertEqual(self.evidence_bytes(), before)
        self.assertFalse((self.root / "receipts" / "ops" / "git-backups").exists())

    def test_mac_order_remote_scope_context_execution_and_receipt_substitutions_reject(self):
        self.common()
        record = self.build()
        self.claim.finalize_succeeded()
        original = record._document()
        cases = []
        bad_mac = deepcopy(original)
        bad_mac["terminal_mac"] = "hmac-sha256:" + "0" * 64
        cases.append(bad_mac)
        for field in ("manifest_sha256", "context_sha256", "execution_sha256",
                      "common_final_receipt_sha256", "common_result_sha256", "selection_sha256",
                      "operation_evidence_sha256", "work_session_binding_sha256",
                      "exact_remote_ref_binding_sha256"):
            changed = deepcopy(original)
            changed["payload"][field] = "sha256:" + "f" * 64
            cases.append(changed)
        changed = deepcopy(original)
        changed["payload"]["commit_oids"].reverse()
        changed["payload"]["terminal_commit_oid"] = changed["payload"]["commit_oids"][-1]
        cases.append(changed)
        changed = deepcopy(original)
        changed["payload"]["approval_reference"]["approval_id"] = "approval_" + "f" * 32
        cases.append(changed)
        before = self.evidence_bytes()
        for index, changed in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.audit(terminal._GitTerminalRecord(approval._canonical_bytes(changed)))
            self.assert_private_error(caught)
        self.assertEqual(self.evidence_bytes(), before)

    def test_wrong_original_context_key_and_corrupt_claim_refuse_without_private_chains(self):
        self.common()
        record = self.build()
        self.claim.finalize_succeeded()
        for context in (
            replace(self.context, reviewer_claim="person:replacement-" + PRIVATE),
            replace(self.context, warning_codes=("different_warning",)),
            replace(self.context, target_binding_sha256="sha256:" + "c" * 64),
        ):
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.audit(record, context=context)
            self.assert_private_error(caught)
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            terminal._authenticate_git_terminal_record(
                self.prepared, context=self.context, record=record,
                receipt_authentication_key=memoryview(bytes(32)),
            )
        self.assert_private_error(caught)
        path = self.root / approval.CLAIMS_RELATIVE_ROOT / (self.claim.approval_id + ".json")
        raw = path.read_bytes()
        path.write_bytes(PRIVATE.encode())
        try:
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.audit(record)
            self.assert_private_error(caught)
            self.assertEqual(path.read_bytes(), PRIVATE.encode())
        finally:
            path.write_bytes(raw)

    def test_rehashed_common_receipt_with_changed_completion_mac_is_not_resigned(self):
        result = self.common()
        path = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (result["execution_sha256"][7:] + ".json")
        raw = path.read_bytes()
        changed = json.loads(raw)
        changed["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "0" * 64
        changed["result"]["result_sha256"] = exact._digest_document({
            key: value for key, value in changed["result"].items() if key != "result_sha256"
        })
        changed["receipt_sha256"] = exact._digest_document({
            key: value for key, value in changed.items() if key != "receipt_sha256"
        })
        mutated = writer._canonical(changed) + b"\n"
        path.write_bytes(mutated)
        try:
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.build()
            self.assert_private_error(caught)
            self.assertEqual(path.read_bytes(), mutated)
        finally:
            path.write_bytes(raw)

    def test_strict_codec_rejects_plaintext_extras_duplicates_bad_oids_and_noncanonical_bytes(self):
        self.common()
        record = self.build()
        changed = record._document()
        changed["payload"]["private_path"] = PRIVATE
        variants = [approval._canonical_bytes(changed), record._raw[:-1],
                    record._raw.replace(b'{"payload":', b'{"schema":"duplicate","payload":', 1),
                    b'{"schema":"' + PRIVATE.encode() + b'"}', b"[1]", b"\xff",
                    b"x" * (terminal.MAX_RECORD_BYTES + 1)]
        for raw in variants:
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                terminal._GitTerminalRecord(raw)
            self.assert_private_error(caught)
        for commits in ([], (), (COMMITS[0],), (COMMITS[0], COMMITS[0]), ("0" * 40, COMMITS[1]),
                        (PRIVATE, COMMITS[1]), ("3" * 64, COMMITS[1]), (self.prepared.initial_head_oid, COMMITS[1])):
            with self.subTest(commits_count=len(commits)), self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.build(commits=commits)
            self.assert_private_error(caught)

    def test_later_worktree_bytes_do_not_turn_historical_authentication_into_current_state(self):
        self.common()
        record = self.build()
        self.claim.finalize_succeeded()
        path = self.root / "later-unrelated-private.txt"
        path.write_bytes(PRIVATE.encode())
        before = self.evidence_bytes()
        verified = self.audit(record)
        self.assertTrue(verified.authentication_summary()["authentication_verified"])
        self.assertFalse(verified.authentication_summary()["backup_completion_verified"])
        self.assertEqual(path.read_bytes(), PRIVATE.encode())
        self.assertEqual(self.evidence_bytes(), before)

    def test_audit_callback_cannot_replace_the_callers_record_inside_authenticated_result(self):
        self.common()
        record = self.build()
        original = record._raw
        altered = record._document()
        altered["payload"]["commit_oids"].reverse()
        altered["payload"]["terminal_commit_oid"] = altered["payload"]["commit_oids"][-1]
        replacement = approval._canonical_bytes(altered)
        self.claim.finalize_succeeded()
        native_audit = approval._audit_exact_human_approval_terminal_record_core
        calls = 0

        def change_caller_after_audit(*args, **kwargs):
            nonlocal calls
            result = native_audit(*args, **kwargs)
            calls += 1
            if calls == 1:
                object.__setattr__(record, "_raw", replacement)
            return result

        before = self.evidence_bytes()
        with mock.patch.object(approval, "_audit_exact_human_approval_terminal_record_core",
                               side_effect=change_caller_after_audit):
            verified = self.audit(record)
        self.assertEqual(calls, 2)
        self.assertIsNot(verified._record, record)
        self.assertEqual(verified._record._raw, original)
        self.assertEqual(record._raw, replacement)
        self.assertEqual(self.evidence_bytes(), before)
        with self.assertRaises(terminal.WorkSessionGitTerminalError):
            self.audit(record)

    def test_original_claim_verifies_started_and_succeeded_without_signing_or_key_provider(self):
        self.common()
        record = self.build()
        for state in ("started", "succeeded"):
            if state == "succeeded":
                self.claim.finalize_succeeded()
            before = self.evidence_bytes()
            native_audit = self.claim.exact_terminal_record_matches
            with self.subTest(state=state), mock.patch.object(
                self.claim, "exact_terminal_record_matches", wraps=native_audit,
            ) as audit, mock.patch.object(
                self.claim, "exact_terminal_record_mac", side_effect=AssertionError("No signing"),
            ), mock.patch.object(
                self.claim, "assert_ready_for_context", side_effect=AssertionError("Separate writer guard"),
            ), mock.patch.object(
                git_fixtures._KeyProvider, "use_key", side_effect=AssertionError("No nested key consumer"),
            ), mock.patch.object(
                workflow, "_production_key_provider", side_effect=AssertionError("No provider"),
            ):
                verified = self.claim_audit(record)
            self.assertEqual(audit.call_count, 2)
            for call in audit.call_args_list:
                self.assertEqual(call.args[0], self.claim.public_reference())
                self.assertEqual(call.args[4], frozenset({"started", "succeeded"}))
            self.assertEqual(self.claim.status, state)
            self.assertTrue(verified.authentication_summary()["authentication_verified"])
            self.assertFalse(verified.authentication_summary()["backup_completion_verified"])
            self.assertEqual(self.evidence_bytes(), before)

    def test_claim_verifier_rejects_wrong_claim_context_record_mac_and_terminal_claim_states(self):
        self.common()
        record = self.build()
        other = self.new_claim()  # Same exact context, different original authority.
        class ClaimSubclass(approval._ClaimedExactHumanApproval):
            pass
        for claim in (other, object(), object.__new__(ClaimSubclass)):
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.claim_audit(record, claim=claim)
            self.assert_private_error(caught)
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            self.claim_audit(record, context=replace(self.context, reviewer_claim="person:wrong-" + PRIVATE))
        self.assert_private_error(caught)
        for name in ("terminal_mac", "common_final_receipt_sha256"):
            changed = record._document()
            if name == "terminal_mac":
                changed[name] = "hmac-sha256:" + "0" * 64
            else:
                changed["payload"][name] = "sha256:" + "f" * 64
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.claim_audit(terminal._GitTerminalRecord(approval._canonical_bytes(changed)))
            self.assert_private_error(caught)
        self.claim.finalize_failed("synthetic_failure")
        before = self.evidence_bytes()
        with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
            self.claim_audit(record)
        self.assert_private_error(caught)
        self.assertEqual(self.evidence_bytes(), before)

    def test_claim_verifier_detaches_before_claim_audit_callback_and_rejects_missing_claim(self):
        self.common()
        record = self.build()
        original = record._raw
        altered = record._document()
        altered["payload"]["commit_oids"].reverse()
        altered["payload"]["terminal_commit_oid"] = altered["payload"]["commit_oids"][-1]
        replacement = approval._canonical_bytes(altered)
        native_audit = self.claim.exact_terminal_record_matches
        calls = 0

        def mutate_caller(*args, **kwargs):
            nonlocal calls
            result = native_audit(*args, **kwargs)
            calls += 1
            if calls == 1:
                object.__setattr__(record, "_raw", replacement)
            return result

        before = self.evidence_bytes()
        with mock.patch.object(self.claim, "exact_terminal_record_matches", side_effect=mutate_caller):
            verified = self.claim_audit(record)
        self.assertEqual(calls, 2)
        self.assertIsNot(verified._record, record)
        self.assertEqual(verified._record._raw, original)
        self.assertEqual(record._raw, replacement)
        self.assertEqual(self.evidence_bytes(), before)
        path = self.root / approval.CLAIMS_RELATIVE_ROOT / (self.claim.approval_id + ".json")
        raw = path.read_bytes()
        path.unlink()
        try:
            with self.assertRaises(terminal.WorkSessionGitTerminalError) as caught:
                self.claim_audit(verified._record)
            self.assert_private_error(caught)
            self.assertFalse(path.exists())
        finally:
            path.write_bytes(raw)


if __name__ == "__main__":
    unittest.main()
