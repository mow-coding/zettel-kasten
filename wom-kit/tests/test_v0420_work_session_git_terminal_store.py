"""Real claim/common receipt storage; terminal OIDs remain synthetic assertions."""

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import test_git_backup_writer as git_fixtures
import test_v0420_work_session_git_terminal as terminal_fixtures
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_git_terminal as terminal
from wom_kit import work_session_git_terminal_store as storage


class GitTerminalStoreGrammarTests(unittest.TestCase):
    def test_errors_retain_only_fixed_codes(self):
        class PrivateString(str):
            def __hash__(self):
                raise AssertionError("SYNTHETIC_PRIVATE")
        for value in ([], {}, None, True, "SYNTHETIC_PRIVATE", PrivateString("work_session_git_terminal_store_missing")):
            error = storage.GitTerminalStoreError(value)
            self.assertEqual(str(error), "work_session_git_terminal_store_invalid")
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)


class GitTerminalStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.git_fixture = git_fixtures.GitBackupWriterTests(methodName="runTest")
        cls.git_fixture.setUp()
        cls.addClassCleanup(cls.git_fixture.tearDown)
        cls.prepared = cls.git_fixture.plan_and_prepare(group_count=2)

    def setUp(self):
        self.fixture = terminal_fixtures.GitTerminalAuthenticationTests(methodName="runTest")
        self.fixture.fixture = self.git_fixture
        self.fixture.root = self.git_fixture.root
        self.fixture.prepared = self.prepared
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.result = self.fixture.common()
        self.record = self.fixture.build()
        self.path = self.root.joinpath(*storage.RECEIPT_ROOT) / (self.result["execution_sha256"][7:] + ".json")

    def save(self, held, *, record=None, claim=None):
        return storage._save_git_terminal_record_held(
            self.prepared, context=self.fixture.context,
            claim=self.fixture.claim if claim is None else claim,
            record=self.record if record is None else record, held=held,
        )

    def load(self, held, *, claim=None):
        return storage._load_git_terminal_record_held(
            self.prepared, claim=self.fixture.claim if claim is None else claim, held=held,
        )

    def assert_private(self, caught, *, code=None):
        error = caught.exception
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for value in (str(self.root), self.prepared.remote_url, "SYNTHETIC_PRIVATE", "tracked.txt"):
            self.assertNotIn(value, str(error) + repr(error))

    def evidence(self):
        # The Windows archive lock is byte-range locked by this test's held
        # guard. Compare all actual claim/checkpoint/receipt bytes, not that
        # deliberately unreadable control lock (verified by held.verify_held).
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for base in (self.root / "profiles" / "local", self.root / "receipts")
            if base.exists() for path in base.rglob("*")
            if path.is_file() and path.relative_to(self.root).as_posix() != exact.EXACT_OPERATION_WRITER_LOCK
        }

    def test_roundtrip_repeat_no_signing_and_succeeded_load_is_data_only(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.evidence()
            with mock.patch.object(self.fixture.claim, "exact_terminal_record_mac", side_effect=AssertionError("No signing")), \
                 mock.patch.object(git_fixtures._KeyProvider, "use_key", side_effect=AssertionError("No provider")), \
                 mock.patch.object(writer.planning, "_local_git_raw", side_effect=AssertionError("No Git")):
                saved = self.save(held)
                raw, before_stat = self.path.read_bytes(), self.path.stat()
                with mock.patch.object(storage.registry, "_write_private_pending", side_effect=AssertionError("No rewrite")), \
                     mock.patch.object(storage.durable, "_atomic_move_file_no_replace", side_effect=AssertionError("No replace")):
                    repeated = self.save(held)
                    loaded = self.load(held)
            self.assertEqual(saved._raw, self.record._raw)
            self.assertEqual(repeated._raw, saved._raw)
            self.assertEqual(loaded._raw, saved._raw)
            self.assertIsNot(loaded, self.record)
            self.assertEqual(self.path.read_bytes(), raw)
            self.assertEqual(self.path.stat().st_ino, before_stat.st_ino)
            self.assertEqual(self.path.stat().st_mtime_ns, before_stat.st_mtime_ns)
            after = self.evidence()
            for name, value in before.items():
                self.assertEqual(after[name], value)
            self.assertEqual(set(after) - set(before), {str(self.path.relative_to(self.root))})
            document = json.loads(raw)
            self.assertEqual(set(document), {"schema", "terminal_record", "receipt_sha256"})
            self.assertEqual(document["schema"], storage.ENVELOPE_SCHEMA)
            for marker in (str(self.root), self.prepared.remote_url, "SYNTHETIC_PRIVATE", "tracked.txt"):
                self.assertNotIn(marker, raw.decode() + repr(loaded))
            self.fixture.claim.finalize_succeeded()
            self.assertEqual(self.load(held)._raw, saved._raw)
            before = self.evidence()
            with self.assertRaises(storage.GitTerminalStoreError) as caught:
                self.save(held)
            self.assert_private(caught, code="work_session_git_terminal_store_authentication_invalid")
            self.assertEqual(self.evidence(), before)

    def test_missing_load_does_not_create_and_wrong_lock_or_claim_refuses(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.evidence()
            with self.assertRaises(storage.GitTerminalStoreError) as caught:
                self.load(held)
            self.assert_private(caught, code="work_session_git_terminal_store_missing")
            self.assertEqual(self.evidence(), before)
            with self.assertRaises(storage.GitTerminalStoreError) as caught:
                self.load(held, claim=object())
            self.assert_private(caught)
        with self.assertRaises(storage.GitTerminalStoreError) as caught:
            self.load(held)
        self.assert_private(caught, code="work_session_git_terminal_store_lock_required")
        with tempfile.TemporaryDirectory() as temporary:
            foreign = Path(temporary)
            with exact.ExactOperationWriterLock(foreign) as other:
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.save(other)
                self.assert_private(caught, code="work_session_git_terminal_store_lock_required")

    def test_unsigned_v1_is_preserved_and_never_upgraded(self):
        raw = writer._canonical({"schema": writer.GIT_BACKUP_DOMAIN_RECEIPT_SCHEMA,
                                 "status": "completed", "legacy_marker": "SYNTHETIC_PRIVATE"}) + b"\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(raw)
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.evidence()
            for operation in (self.load, self.save):
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    operation(held)
                self.assert_private(caught, code="work_session_git_terminal_store_conflict")
            self.assertEqual(self.path.read_bytes(), raw)
            self.assertEqual(self.evidence(), before)

    def test_loader_rechecks_the_held_lock_after_its_final_read(self):
        native_read = storage._read
        calls = 0
        with exact.ExactOperationWriterLock(self.root) as held:
            self.save(held)
            def read_then_release(*args, **kwargs):
                nonlocal calls
                result = native_read(*args, **kwargs)
                calls += 1
                if calls == 2:
                    held.__exit__(None, None, None)
                return result
            with mock.patch.object(storage, "_read", side_effect=read_then_release):
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.load(held)
            self.assert_private(caught, code="work_session_git_terminal_store_lock_required")
        self.assertEqual(calls, 2)

    def test_different_authenticated_assertions_cannot_replace_original_execution(self):
        replacement = self.fixture.build(commits=tuple(reversed(terminal_fixtures.COMMITS)))
        with exact.ExactOperationWriterLock(self.root) as held:
            self.save(held)
            before = self.evidence()
            with self.assertRaises(storage.GitTerminalStoreError) as caught:
                self.save(held, record=replacement)
            self.assert_private(caught, code="work_session_git_terminal_store_conflict")
            self.assertEqual(self.evidence(), before)
            self.assertEqual(self.load(held)._raw, self.record._raw)

    def test_corrupt_noncanonical_or_hardlinked_existing_bytes_are_not_repaired(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            self.save(held)
            raw = self.path.read_bytes()
            altered = json.loads(raw)
            altered["private_path"] = "SYNTHETIC_PRIVATE"
            for bad in (raw[:-1], writer._canonical(altered) + b"\n", b'{"schema":1,"schema":2}\n', b"not-json"):
                self.path.write_bytes(bad)
                for operation in (self.load, self.save):
                    with self.assertRaises(storage.GitTerminalStoreError) as caught:
                        operation(held)
                    self.assert_private(caught)
                self.assertEqual(self.path.read_bytes(), bad)
            self.path.write_bytes(raw)
            link = self.path.with_suffix(".hardlink")
            os.link(self.path, link)
            try:
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.load(held)
                self.assert_private(caught)
                self.assertEqual(self.path.read_bytes(), raw)
            finally:
                link.unlink()

    def test_cut_before_rename_retains_pending_original_and_publishes_no_final(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.evidence()
            with mock.patch.object(storage.durable, "_atomic_move_file_no_replace", side_effect=OSError("SYNTHETIC_PRIVATE")):
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.save(held)
            self.assert_private(caught, code="work_session_git_terminal_store_durability_unknown")
            self.assertFalse(self.path.exists())
            added = set(self.evidence()) - set(before)
            self.assertEqual(len(added), 1)
            pending = self.root / next(iter(added))
            self.assertTrue(pending.name.startswith(".pending_"))
            self.assertEqual(pending.read_bytes(), storage._encode(self.record))

    def test_cut_after_rename_repeats_only_durability_authentication_and_readback(self):
        native_move = storage.durable._atomic_move_file_no_replace
        def move_then_cut(*args, **kwargs):
            native_move(*args, **kwargs)
            raise OSError("SYNTHETIC_PRIVATE_AFTER_RENAME")
        with exact.ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(storage.durable, "_atomic_move_file_no_replace", side_effect=move_then_cut):
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.save(held)
            self.assert_private(caught, code="work_session_git_terminal_store_durability_unknown")
            raw = self.path.read_bytes()
            with mock.patch.object(storage.registry, "_write_private_pending", side_effect=AssertionError("No rewrite")), \
                 mock.patch.object(storage.durable, "_atomic_move_file_no_replace", side_effect=AssertionError("No replace")):
                self.assertEqual(self.save(held)._raw, self.record._raw)
            self.assertEqual(self.path.read_bytes(), raw)

    def test_identical_repeat_reads_again_after_directory_flush(self):
        native_flush = storage.durable._require_directory_durable
        with exact.ExactOperationWriterLock(self.root) as held:
            self.save(held)
            raw = self.path.read_bytes()
            def flush_then_change(path):
                result = native_flush(path)
                self.path.write_bytes(raw[:-1])
                return result
            with mock.patch.object(storage.durable, "_require_directory_durable", side_effect=flush_then_change):
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.save(held)
            self.assert_private(caught)
            self.assertEqual(self.path.read_bytes(), raw[:-1])

    def test_common_evidence_changed_after_publication_preserves_record_but_fails(self):
        common_path = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT / (self.result["execution_sha256"][7:] + ".json")
        common_raw = common_path.read_bytes()
        native_move = storage.durable._atomic_move_file_no_replace
        def move_then_change(*args, **kwargs):
            native_move(*args, **kwargs)
            common_path.write_bytes(b"SYNTHETIC_PRIVATE_CORRUPT_COMMON")
        with exact.ExactOperationWriterLock(self.root) as held:
            try:
                with mock.patch.object(storage.durable, "_atomic_move_file_no_replace", side_effect=move_then_change):
                    with self.assertRaises(storage.GitTerminalStoreError) as caught:
                        self.save(held)
                self.assert_private(caught, code="work_session_git_terminal_store_authentication_invalid")
                self.assertEqual(self.path.read_bytes(), storage._encode(self.record))
                self.assertEqual(self.fixture.claim.status, "started")
                # Loading is data-only and must not mislabel this as authenticated.
                self.assertEqual(self.load(held)._raw, self.record._raw)
            finally:
                common_path.write_bytes(common_raw)

    def test_pending_readback_and_caller_object_mutation_cannot_publish_unchecked_bytes(self):
        native_write = storage.registry._write_private_pending
        def corrupt_pending(path, raw, **kwargs):
            native_write(path, raw, **kwargs)
            path.write_bytes(raw[:-1])
        with exact.ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(storage.registry, "_write_private_pending", side_effect=corrupt_pending):
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.save(held)
            self.assert_private(caught, code="work_session_git_terminal_store_changed")
            self.assertFalse(self.path.exists())
            original = self.record._raw
            native_audit = self.fixture.claim.exact_terminal_record_matches
            def mutate_caller(*args, **kwargs):
                result = native_audit(*args, **kwargs)
                object.__setattr__(self.record, "_raw", b"SYNTHETIC_PRIVATE_REPLACEMENT")
                return result
            with mock.patch.object(self.fixture.claim, "exact_terminal_record_matches", side_effect=mutate_caller):
                saved = self.save(held)
            self.assertEqual(saved._raw, original)
            self.assertEqual(self.load(held)._raw, original)

    def test_first_create_parent_flush_failure_and_identity_drift_preserve_existing_evidence(self):
        # Use an independent archive: earlier storage cases deliberately retain
        # their original records and cut artifacts in the shared fixture.
        fresh = git_fixtures.GitBackupWriterTests(methodName="runTest")
        fresh.setUp()
        self.addCleanup(fresh.tearDown)
        self.git_fixture = fresh
        self.prepared = fresh.plan_and_prepare(group_count=2)
        self.setUp()
        self.assertFalse(self.path.parent.exists())
        native_flush = storage.durable._require_directory_durable
        flushed = []

        def fail_owner_flush(path):
            flushed.append(Path(path).name)
            if Path(path).name == "ops":
                raise OSError("SYNTHETIC_PRIVATE_PARENT_FLUSH")
            return native_flush(path)

        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.evidence()
            with mock.patch.object(storage.durable, "_require_directory_durable", side_effect=fail_owner_flush):
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.save(held)
            self.assert_private(caught, code="work_session_git_terminal_store_durability_unknown")
            self.assertEqual(flushed[:2], ["git-backups", "ops"])
            self.assertFalse(self.path.exists())
            self.assertEqual(self.evidence(), before)

            native_safe = storage.durable._safe_directory
            drift = False
            observed_drift = 0
            def flush_then_drift(path):
                nonlocal drift
                result = native_flush(path)
                if Path(path).name == "git-backups":
                    drift = True
                return result
            def changed_identity(path, *args, **kwargs):
                nonlocal observed_drift
                observed = native_safe(path, *args, **kwargs)
                if drift and Path(path).name == "git-backups":
                    observed_drift += 1
                    fields = {name: getattr(observed, name) for name in dir(observed) if name.startswith("st_")}
                    return SimpleNamespace(**{**fields, "st_ino": observed.st_ino + 1})
                return observed
            with mock.patch.object(storage.durable, "_require_directory_durable", side_effect=flush_then_drift), \
                 mock.patch.object(storage.durable, "_safe_directory", side_effect=changed_identity):
                with self.assertRaises(storage.GitTerminalStoreError) as caught:
                    self.save(held)
            self.assert_private(caught, code="work_session_git_terminal_store_durability_unknown")
            self.assertGreater(observed_drift, 0)
            self.assertFalse(self.path.exists())
            self.assertEqual(self.evidence(), before)
            flushed.clear()
            def observe_flush(path):
                flushed.append(Path(path).name)
                return native_flush(path)
            with mock.patch.object(storage.durable, "_require_directory_durable", side_effect=observe_flush):
                self.save(held)
            self.assertEqual(flushed[:4], ["git-backups", "ops", "receipts", self.root.name])
            self.assertEqual(self.load(held)._raw, self.record._raw)


if __name__ == "__main__":
    unittest.main()
