"""Classified junk never enters preservation; uncertainty is not a backup rule."""
import json
import os
import unittest

from wom_kit import activity_cleanup as cleanup
from . import test_activity_cleanup as fixture


class ClassificationTests(unittest.TestCase):
    setUp = fixture.ActivityCleanupTests.setUp

    @unittest.skipUnless(os.name == "nt", "native official pipeline")
    def test_actual_official_pipeline_uploads_source_but_never_temporary_bytes(self):
        cache = self.external / "synthetic-regenerable-cache.bin"
        cache.write_bytes(b"synthetic disposable bytes never for remote storage")
        self.document["items"].append({"path": str(cache), "role": "temporary",
            "reason": "Synthetic generated cache; disposal is within the requested activity cleanup",
            "disposition": "discard", "discard_intent": True})
        # The existing full pipeline asserts exactly one PUT, one remote byte
        # verification and the source's exact bytes, despite two deleted files.
        fixture.ActivityCleanupTests.test_official_intake_upload_offload_external_cleanup_pipeline(self)
        self.assertFalse(cache.exists())

    def test_temporary_default_preservation_is_blocked_before_upload(self):
        self.document["items"][0].update(role="temporary", reason="Reproducible synthetic cache")
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        candidate = cleanup.plan(self.root, self.request, key_provider=self.key)
        self.assertFalse(candidate["public"]["ok"])
        self.assertIn("activity_cleanup_temporary_upload_requires_reclassification", candidate["public"]["blockers"])
        self.backend.preserve.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "native deletion of synthetic files")
    def test_mixed_activity_preserves_source_discards_junk_and_holds_unknown(self):
        # A misleading filename must not override the AI's evidence-backed role.
        source = self.external / "temp-unique-original.bin"
        self.source.rename(source)
        cache = self.external / "rebuildable.bin"
        cache.write_bytes(b"synthetic disposable build output")
        unknown = self.external / "unknown.bin"
        unknown.write_bytes(b"not classified yet")
        self.document["items"] = [
            {"path": str(source), "role": "source", "reason": "Unique synthetic source despite its name", "disposition": "preserve"},
            {"path": str(cache), "role": "temporary", "reason": "Synthetic build output; retained source and build instructions regenerate it", "disposition": "discard", "discard_intent": True},
            {"path": str(unknown), "role": "unknown", "reason": "Dependency on another activity is not yet established", "disposition": "retain"},
        ]
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        candidate = cleanup.plan(self.root, self.request, key_provider=self.key)
        self.assertTrue(candidate["public"]["ok"])
        partition = candidate["public"]["classification"]
        self.assertEqual([partition[key] for key in ("preserve_count", "discard_without_upload_count", "retain_without_upload_count")], [1, 1, 1])
        result = fixture.ActivityCleanupTests.execute(self, candidate)
        self.assertEqual(result["state"], "partial", result)
        self.assertFalse(source.exists())
        self.assertFalse(cache.exists())
        self.assertEqual(unknown.read_bytes(), b"not classified yet")
        self.assertEqual(self.backend.preserve.call_count, 1)
        self.assertEqual(self.backend.preserve.call_args.args[0]["path"], str(source))
        self.assertEqual(self.backend.verify.call_count, 1)
        self.assertEqual(self.backend.finish_local_preservation.call_count, 1)
        self.assertEqual(result["items"][2]["code"], "activity_cleanup_classification_retained_no_upload")
        self.assertNotIn("unknown.bin", json.dumps(result))
        self.assertNotIn("Unique synthetic source", json.dumps(result))
