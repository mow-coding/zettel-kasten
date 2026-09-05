"""Session extensions preserve historical approval bytes and checkpoint replay."""

import copy
import hashlib
import hmac
import json
from pathlib import Path
import sys
import tempfile
import unittest

TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

import test_exact_operation_manifest as fixtures
from test_v0420_work_session_binding import binding_fixture
from wom_kit import exact_operation_manifest as m
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation
from wom_kit.operation_approval_binding import exact_operation_manifest_approval_binding


# Captured from the unmodified v0.4.19 implementation before this extension.
LEGACY_MANIFEST = "sha256:7d40e68927aee5f74b86d7519399c1b7750d82f9cdee8d494104b30fe1d3e84f"
LEGACY_EXECUTION = "sha256:27fdf809e0bd3abeac28f5e42d37b699b79b1a010c6f01965ab8e88dc9d8f9e9"
LEGACY_CHECKPOINTS = (
    "sha256:04c85736d6d24d418fdaafaa3987c87cb407c79668edda3a8f29fb8ff318f239",
    "sha256:3aad0afeef5279f6b752e757ed31849242abc5932fcfa4c45b04cfc28413d5f2",
    "sha256:fdb030187ceebde2627b968e400c235d96d3f05341a7b6af5a2f806792125389",
    "sha256:5098179d6982e1fb4d102bf0fcd3e9448ac84ca40393f4190f9a438697d1b92f",
)
LEGACY_RESULT = "sha256:00f770aade550bbacb5d03835e38bfe88ca2851363c9ddd9963b1604a38b3c84"


def authority_fixture():
    return m.ExactOperationApprovalAuthority.from_reference({
        "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
        "approval_id": "approval_" + "1" * 32,
        "context_sha256": "sha256:" + "2" * 64,
        "approval_authority_sha256": "sha256:" + "3" * 64,
        "one_use": True,
    })


def fixture(scoped=True):
    manifest, payloads, target, verifier = fixtures.ExactOperationManifestTests().fixture()
    if scoped:
        manifest = m.ExactOperationManifest.build(
            operation=manifest.operation,
            archive_identity_sha256=manifest.archive_identity_sha256,
            items=manifest.items,
            work_session_binding=binding_fixture(manifest.archive_identity_sha256),
        )
    return manifest, payloads, target, verifier


class SessionManifestTests(unittest.TestCase):
    def test_manifest_and_approval_bind_same_archive_and_exact_session_revision(self):
        manifest, _, _, _ = fixture()
        binding = manifest.work_session_binding
        self.assertEqual(m.ExactOperationManifest.from_document(manifest.document()), manifest)
        expected_extension = m._digest_document({
            "schema": m.EXTENSION_SCHEMA, "work_session_binding": binding.document(),
        })
        self.assertEqual(manifest.extension_sha256, expected_extension)
        self.assertEqual(manifest.approval_digest_context()["work_session_binding_sha256"], binding.binding_sha256)
        approval = exact_operation_manifest_approval_binding(
            manifest, operation=ExactHumanApprovalOperation.create_draft,
            archive_id=fixtures.ExactOperationManifestTests.archive_id,
        )
        self.assertEqual(approval.plan_sha256, manifest.manifest_sha256)
        self.assertNotEqual(manifest.manifest_sha256, LEGACY_MANIFEST)
        revised = m.ExactOperationManifest.build(
            operation=manifest.operation, archive_identity_sha256=manifest.archive_identity_sha256,
            items=manifest.items,
            work_session_binding=binding_fixture(manifest.archive_identity_sha256, revision=2),
        )
        self.assertNotEqual(revised.manifest_sha256, manifest.manifest_sha256)
        self.assertNotEqual(m.exact_operation_execution_sha256(revised), m.exact_operation_execution_sha256(manifest))
        with self.assertRaises(m.ExactOperationManifestError):
            m.ExactOperationManifest.build(
                operation=manifest.operation, archive_identity_sha256="sha256:" + "f" * 64,
                items=manifest.items, work_session_binding=binding,
            )

    def test_extension_reader_rejects_null_partial_extra_and_rehashed_forgery(self):
        manifest, _, _, _ = fixture()
        document = manifest.document()
        changes = [
            {"work_session_binding": None},
            {"work_session_binding": {**document["work_session_binding"], "display_name": "private_label_marker"}},
            {"extension_sha256": None},
            {"extension_sha256": "sha256:" + "f" * 64},
            {"private_label": "private_label_marker"},
        ]
        cases = [{**document, **change} for change in changes]
        for removed in ("work_session_binding", "extension_sha256"):
            cases.append({key: value for key, value in document.items() if key != removed})
        # A valid binding from another archive cannot be laundered by hashing
        # the outer document again. The manifest cross-checks archive identity.
        forged = copy.deepcopy(document)
        other = binding_fixture("sha256:" + "f" * 64)
        forged["work_session_binding"] = other.document()
        forged["extension_sha256"] = m._work_session_extension_sha256(other)
        forged["manifest_sha256"] = m._digest_document({key: value for key, value in forged.items() if key != "manifest_sha256"})
        cases.append(forged)
        for case in cases:
            with self.subTest(keys=set(case)), self.assertRaises(m.ExactOperationManifestError) as captured:
                m.ExactOperationManifest.from_document(case)
            self.assertNotIn("private_label", str(captured.exception))

    def test_legacy_approval_execution_checkpoint_bytes_and_replay_are_unchanged(self):
        manifest, payloads, target, verifier = fixture(scoped=False)
        authority = authority_fixture()
        document_before = m._canonical_json_bytes(manifest.document())
        context_before = m._canonical_json_bytes(manifest.approval_digest_context())
        self.assertEqual(manifest.manifest_sha256, LEGACY_MANIFEST)
        self.assertEqual(m.exact_operation_execution_sha256(manifest, approval_authority=authority), LEGACY_EXECUTION)
        store = fixtures._CheckpointStore()
        with self.assertRaises(m.ExactOperationManifestError):
            m.apply_exact_operation(
                manifest, payloads=payloads, writer=fixtures._Writer(target, fail_after_write=True),
                verifier=verifier, checkpoint_store=store, approval_authority=authority,
            )
        row_before = m._canonical_json_bytes(store.rows[LEGACY_EXECUTION][0])
        self.assertEqual(store.rows[LEGACY_EXECUTION][0]["checkpoint_sha256"], LEGACY_CHECKPOINTS[0])
        # Starting a current session is not permission to retrofit old approval.
        binding_fixture(manifest.archive_identity_sha256, revision=5)
        reloaded = m.ExactOperationManifest.from_document(json.loads(document_before))
        self.assertIsNone(reloaded.work_session_binding)
        self.assertIsNone(reloaded.extension_sha256)
        result = m.apply_exact_operation(
            reloaded, payloads=payloads, writer=fixtures._Writer(target), verifier=verifier,
            checkpoint_store=store, approval_authority=authority, resume=True,
        )
        self.assertEqual(result["result_sha256"], LEGACY_RESULT)
        self.assertEqual(tuple(row["checkpoint_sha256"] for row in store.rows[LEGACY_EXECUTION]), LEGACY_CHECKPOINTS)
        self.assertEqual(m._canonical_json_bytes(store.rows[LEGACY_EXECUTION][0]), row_before)
        self.assertEqual(m._canonical_json_bytes(reloaded.document()), document_before)
        self.assertEqual(m._canonical_json_bytes(reloaded.approval_digest_context()), context_before)
        self.assertNotIn("work_session", json.dumps([reloaded.document(), store.rows, result]))
        self.assertNotIn("extension_sha256", result)

    def test_real_checkpoint_store_carries_binding_through_resume_receipt_and_revert(self):
        manifest, payloads, target, verifier = fixture()
        authority = authority_fixture()
        execution = m.exact_operation_execution_sha256(manifest, approval_authority=authority)
        expected = m._work_session_digest_fields(manifest)
        with tempfile.TemporaryDirectory(prefix="wom-session-checkpoints-") as temporary:
            root = Path(temporary) / "archive"
            root.mkdir()
            with m.exact_operation_writer_lock(root) as lock:
                store = m.FileExactOperationCheckpointStore(root, writer_lock=lock)
                with self.assertRaises(m.ExactOperationManifestError):
                    m.apply_exact_operation(manifest, payloads=payloads, writer=fixtures._Writer(target, fail_after_write=True), verifier=verifier, checkpoint_store=store, approval_authority=authority)
            with m.exact_operation_writer_lock(root) as lock:
                store = m.FileExactOperationCheckpointStore(root, writer_lock=lock)
                result = m.apply_exact_operation(manifest, payloads=payloads, writer=fixtures._Writer(target), verifier=verifier, checkpoint_store=store, approval_authority=authority, resume=True)
                for row in store.load(execution, heartbeat=lambda: None):
                    self.assertEqual({key: row[key] for key in expected}, expected)
                receipt = store.load_final_receipt(execution)
                self.assertEqual({key: receipt["result"][key] for key in expected}, expected)
                for result_value in (
                    result,
                    m.verify_exact_operation(manifest, verifier=verifier, state="post"),
                    m.inspect_exact_operation_state(manifest, verifier=verifier, checkpoint_store=store, approval_authority=authority),
                ):
                    self.assertEqual({key: result_value[key] for key in expected}, expected)
                reverted = m.revert_exact_operation_fields(
                    manifest, selected_fields=(("item:one", "title"),), payloads=payloads,
                    writer=fixtures._Writer(target), verifier=verifier,
                    checkpoint_store=store, approval_authority=authority,
                )
                self.assertEqual({key: reverted[key] for key in expected}, expected)
                self.assertEqual(target.values[("zettel", "private/target-0.md", "body")], b"post-0-body")
                self.assertEqual(target.values[("zettel", "private/target-0.md", "title")], b"pre-0-title")
            loaded = m.load_exact_operation_final_receipt_read_only(root, execution)
            self.assertEqual(loaded, receipt)

    def test_checkpoint_cannot_drop_or_substitute_session_even_after_self_rehash(self):
        manifest, payloads, target, verifier = fixture()
        store = fixtures._CheckpointStore()
        authority = authority_fixture()
        execution = m.exact_operation_execution_sha256(manifest, approval_authority=authority)
        with self.assertRaises(m.ExactOperationManifestError):
            m.apply_exact_operation(manifest, payloads=payloads, writer=fixtures._Writer(target, fail_after_write=True), verifier=verifier, checkpoint_store=store, approval_authority=authority)
        baseline = copy.deepcopy(store.rows[execution][0])
        cases = []
        for key in ("work_session_binding_sha256", "extension_sha256"):
            for value in (None, "sha256:" + "f" * 64):
                cases.append({**baseline, key: value})
            cases.append({name: value for name, value in baseline.items() if name != key})
        cases.append({name: value for name, value in baseline.items() if name not in m._work_session_digest_fields(manifest)})
        for row in cases:
            row["checkpoint_sha256"] = m._digest_document({key: value for key, value in row.items() if key != "checkpoint_sha256"})
            store.rows[execution] = [row]
            writer = fixtures._Writer(target)
            with self.subTest(keys=set(row)), self.assertRaises(m.ExactOperationManifestError):
                m.apply_exact_operation(manifest, payloads=payloads, writer=writer, verifier=verifier, checkpoint_store=store, approval_authority=authority, resume=True)
            self.assertEqual(writer.write_count, 0)

    def test_final_receipt_strict_optional_pair_and_checkpoint_equality(self):
        manifest, payloads, target, verifier = fixture()
        store = fixtures._CheckpointStore()
        m.apply_exact_operation(manifest, payloads=payloads, writer=fixtures._Writer(target), verifier=verifier, checkpoint_store=store)
        execution = m.exact_operation_execution_sha256(manifest)
        result = store.results[execution]
        for key in ("work_session_binding_sha256", "extension_sha256"):
            missing = {name: value for name, value in result.items() if name != key}
            missing["result_sha256"] = m._digest_document({name: value for name, value in missing.items() if name != "result_sha256"})
            with self.assertRaises(m.ExactOperationManifestError):
                m._validate_stable_result_document(missing)
        forged = {**result, "work_session_binding_sha256": "sha256:" + "f" * 64}
        forged["result_sha256"] = m._digest_document({name: value for name, value in forged.items() if name != "result_sha256"})
        with self.assertRaises(m.ExactOperationManifestError):
            m._validate_final_checkpoint_evidence(store.rows[execution], result=forged)
        basis = {"schema": m.FINAL_RECEIPT_SCHEMA, "result": result, "display_name": "private_label_marker"}
        with self.assertRaises(m.ExactOperationManifestError):
            m.validate_exact_operation_final_receipt_document({**basis, "receipt_sha256": m._digest_document(basis)})

    def test_completion_authentication_covers_session_pair_without_new_authority(self):
        manifest, payloads, target, verifier = fixture()
        authority = authority_fixture()
        reference = {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": authority.approval_id,
            "context_sha256": authority.context_sha256,
            "approval_authority_sha256": authority.approval_authority_sha256,
            "one_use": True,
        }
        observed_payloads = []

        def authenticate(payload):
            observed_payloads.append(payload)
            return {
                "approval_reference": reference,
                "terminal_mac": "hmac-sha256:" + hmac.new(bytes(range(32)), payload, hashlib.sha256).hexdigest(),
            }

        store = fixtures._CheckpointStore()
        m.apply_exact_operation(
            manifest, payloads=payloads, writer=fixtures._Writer(target),
            verifier=verifier, checkpoint_store=store, approval_authority=authority,
            completion_authenticator=authenticate,
        )
        self.assertEqual(len(observed_payloads), 1)
        result = next(iter(store.results.values()))
        self.assertEqual(m.exact_operation_completion_authentication_payload(result), observed_payloads[0])
        for key, value in m._work_session_digest_fields(manifest).items():
            self.assertEqual(json.loads(observed_payloads[0])["result"][key], value)
            substituted = copy.deepcopy(result)
            substituted[key] = "sha256:" + "f" * 64
            substituted["result_sha256"] = m._digest_document({name: field for name, field in substituted.items() if name != "result_sha256"})
            with self.assertRaises(m.ExactOperationManifestError):
                m._validate_stable_result_document(substituted)


if __name__ == "__main__":
    unittest.main()
