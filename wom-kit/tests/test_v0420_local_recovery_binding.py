"""Recovery transformations retain identity without inventing write authority.

Use real synthetic private controls and observed field states. No client data,
provider, native prompt or credential store is accessed. These tests do not
claim that local recovery has a public session-owned execution route yet.
"""

from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest

import test_local_recovery_execution as fixture
from wom_kit import local_recovery_execution as recovery
from wom_kit.exact_human_approval import exact_human_approval_context_sha256
from wom_kit.exact_operation_manifest import ExactOperationManifest
from wom_kit.work_session_binding import WorkSessionBinding


class LocalRecoveryBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-recovery-binding-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(fixture.FIXTURE, self.root)
        helper = fixture.LocalRecoveryExecutionTests()
        self.title = helper.title_plan(self.root)
        self.ledger = helper.ledger_plan(self.root, count=2)
        self.binding = self.make_binding()

    def make_binding(self, *, app="1", session="3", revision=1):
        return WorkSessionBinding.build(
            client_app_ref="client_app_" + app * 32,
            workstream_ref="workstream_" + "2" * 32,
            work_session_ref="work_session_" + session * 32,
            revision=revision,
            archive_identity_sha256=self.title.manifest.archive_identity_sha256,
            client_app_label_sha256="sha256:" + "4" * 64,
            workstream_label_sha256="sha256:" + "5" * 64,
        )

    def bind(self, plan, binding):
        manifest = plan.manifest
        return replace(plan, manifest=ExactOperationManifest.build(
            operation=manifest.operation,
            archive_identity_sha256=manifest.archive_identity_sha256,
            items=manifest.items,
            operation_evidence=manifest.operation_evidence,
            work_session_binding=binding,
        ))

    def combine(self, *members):
        return recovery.combine_local_recovery_plans(
            members or (self.title, self.ledger), domain="synthetic_combined")

    def observed_subset(self, plan):
        recovery.persist_local_recovery_control(plan)
        loaded = recovery.load_local_recovery_plan(
            self.root, manifest_sha256=plan.manifest.manifest_sha256)
        # Simulate one successfully published ledger before interruption. The
        # other two fields remain pre-state, so compensation must select one.
        spec = loaded.specs[1]
        path = self.root / spec.target_relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(spec.post_value)
        return recovery.build_observed_post_subset_revert_plan(loaded)

    def test_same_session_composite_and_revert_keep_exact_binding(self):
        plan = self.combine(self.bind(self.title, self.binding),
                            self.bind(self.ledger, self.binding))
        self.assertEqual(plan.manifest.work_session_binding, self.binding)
        self.assertEqual(len(plan.specs), 3)
        self.assertEqual(plan.manifest.items[0].fields, self.title.manifest.items[0].fields)
        reverted = recovery._operation_manifest(plan, mode="revert")
        self.assertEqual(reverted.work_session_binding, self.binding)
        self.assertEqual(reverted.items, plan.manifest.items)
        self.assertEqual(reverted.operation_evidence, plan.manifest.operation_evidence)
        self.assertNotEqual(reverted.manifest_sha256, plan.manifest.manifest_sha256)
        for mode in ("apply", "revert"):
            self.assertNotEqual(
                recovery.local_recovery_context(plan, mode=mode).plan_sha256,
                recovery.local_recovery_context(self.combine(), mode=mode).plan_sha256,
            )

    def test_different_or_missing_session_cannot_be_merged_in_either_order(self):
        title = self.bind(self.title, self.binding)
        for binding in (None, self.make_binding(app="6"),
                        self.make_binding(session="7"), self.make_binding(revision=2)):
            other = self.bind(self.ledger, binding)
            for members in ((title, other), (other, title)):
                with self.subTest(binding=binding, reversed=members[0] is other):
                    with self.assertRaisesRegex(
                            recovery.LocalRecoveryError, "^local_recovery_plan_invalid$"):
                        self.combine(*members)

    def test_private_control_round_trip_preserves_bound_manifest_and_context(self):
        plan = self.bind(self.title, self.binding)
        relative = recovery.persist_local_recovery_control(plan)
        before = (self.root / relative).read_bytes()
        loaded = recovery.load_local_recovery_plan(
            self.root, manifest_sha256=plan.manifest.manifest_sha256)
        self.assertEqual(loaded.manifest.document(), plan.manifest.document())
        for mode in ("apply", "revert"):
            self.assertEqual(recovery.local_recovery_context(loaded, mode=mode),
                             recovery.local_recovery_context(plan, mode=mode))
        recovery.persist_local_recovery_control(loaded)
        self.assertEqual((self.root / relative).read_bytes(), before)

    def test_partial_compensation_preserves_parent_identity_and_exact_fields(self):
        parent = self.combine(self.bind(self.title, self.binding),
                              self.bind(self.ledger, self.binding))
        subset, report = self.observed_subset(parent)
        self.assertEqual(report["selected_post_field_count"], 1)
        self.assertEqual(report["already_pre_field_count"], 2)
        self.assertEqual(subset.manifest.work_session_binding, self.binding)
        self.assertEqual(subset.manifest.items[0].fields, parent.manifest.items[1].fields)
        self.assertEqual(recovery._subset_parent_plan(subset).manifest, parent.manifest)
        self.assertEqual(recovery._operation_manifest(subset, mode="revert").work_session_binding,
                         self.binding)
        for binding in (None, self.make_binding(app="6"), self.make_binding(revision=2)):
            with self.subTest(binding=binding):
                with self.assertRaisesRegex(
                        recovery.LocalRecoveryError, "^local_recovery_partial_revert_blocked$"):
                    recovery._subset_parent_plan(self.bind(subset, binding))

    def test_unbound_parent_cannot_be_relabelled_by_a_subset(self):
        subset, _report = self.observed_subset(self.combine())
        self.assertIsNone(subset.manifest.work_session_binding)
        self.assertIsNotNone(recovery._subset_parent_plan(subset))
        with self.assertRaisesRegex(
                recovery.LocalRecoveryError, "^local_recovery_partial_revert_blocked$"):
            recovery._subset_parent_plan(self.bind(subset, self.binding))

    def test_legacy_unbound_approval_and_control_bytes_keep_checkpoint_digests(self):
        # Captured by executing the actual 35fb4e58 module against these same
        # fixtures before this change; not recomputed from the implementation.
        expected = {
            "composite": "sha256:7552d1c308504fd4504dd51c3e3d96137ce56bd8933931e1bc6f717091669324",
            "revert": "sha256:525033158c3f3edb45dc77d08883a579e49a735c0fb6f59b88b1a278ea6ad95d",
            "subset": "sha256:fc078c77c0589f0be09f0e3c08ff450ba2508ceaae6e13c2d1f8c311251a8e6e",
            "control": "sha256:716b235776d32d6d5aef25b8896dc9fc9a27d1af4fd4bbd1cfdddce02d94e401",
            "apply_context": "sha256:5fd3ff834bf5e72bc9d35a5848efb82eded09c61c6fdc06347ab2d7b14059549",
            "revert_context": "sha256:88ca64e99a8b17fff47ef1b0ed74287bb5e970f15bba6a2918d4ef4df045e204",
        }
        plan = self.combine()
        subset, _report = self.observed_subset(plan)
        actual = {
            "composite": plan.manifest.manifest_sha256,
            "revert": recovery._operation_manifest(plan, mode="revert").manifest_sha256,
            "subset": subset.manifest.manifest_sha256,
            "control": recovery._control_document(plan)["control_sha256"],
            "apply_context": exact_human_approval_context_sha256(
                recovery.local_recovery_context(plan, mode="apply")),
            "revert_context": exact_human_approval_context_sha256(
                recovery.local_recovery_context(plan, mode="revert")),
        }
        self.assertEqual(actual, expected)
        self.assertNotIn("work_session_binding", plan.manifest.document())


if __name__ == "__main__":
    unittest.main()
