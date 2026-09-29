from pathlib import Path
import json
import tempfile
import unittest

from wom_kit import provider_tiro
from wom_kit.provider_artifacts import ProviderArtifactError, digest


class TiroTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = json.dumps({"schema": provider_tiro.BUNDLE_SCHEMA, "notes": [{"guid": "synthetic-note"}],
            "paragraphs_by_note": {"synthetic-note": [{"transcript": {"type": "text", "content": "Original transcript"}, "startAt": 1, "speaker": "synthetic"}]}}).encode()

    def test_original_audio_and_ai_are_separate_and_intake_ready(self):
        (self.root / "synthetic.wav").write_bytes(b"synthetic-wave")
        result = provider_tiro.stage_bundle(self.root, raw_bundle=self.raw, batch_id="test",
            audio_sources=[{"note_guid": "synthetic-note", "local_path": "synthetic.wav", "source_sha256": digest(b"synthetic-wave"), "mime": "audio/wav"}],
            enrichments=[{"note_guid": "synthetic-note", "source_sha256": digest(self.raw), "model_provenance": {"provider": "synthetic", "model": "fixture", "run_id": "test"}, "content": "Derived summary"}])
        self.assertEqual(result["audio_staged"], 1)
        self.assertEqual(result["audio_unconfirmed"], 0)
        self.assertEqual(result["enrichment_staged"], 1)
        request = json.loads((self.root / result["intake_request"]).read_text())
        self.assertEqual((self.root / request["items"][0]["local_path"]).read_bytes(), self.raw)
        self.assertEqual(len(request["items"]), 5)
        self.assertFalse(result["capture_completed"])

    def test_missing_audio_is_unconfirmed_not_falsely_unavailable(self):
        result = provider_tiro.stage_bundle(self.root, raw_bundle=self.raw, batch_id="test")
        self.assertEqual(result["audio_unconfirmed"], 1)

    def test_audio_wrong_note_and_changed_bytes_are_rejected(self):
        (self.root / "synthetic.wav").write_bytes(b"changed")
        with self.assertRaisesRegex(ProviderArtifactError, "source_changed"):
            provider_tiro.stage_bundle(self.root, raw_bundle=self.raw, batch_id="test", audio_sources=[{
                "note_guid": "synthetic-note", "local_path": "synthetic.wav", "source_sha256": digest(b"original")}])

    def test_ai_without_source_binding_is_rejected(self):
        with self.assertRaisesRegex(ProviderArtifactError, "provenance_invalid"):
            provider_tiro.stage_bundle(self.root, raw_bundle=self.raw, batch_id="test", enrichments=[{
                "note_guid": "synthetic-note", "content": "no source"}])
