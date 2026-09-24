"""v0.4.41: move verified-recovered Notion pages to the Notion trash.

A real recovery runs first against a fake Notion (no network, no secret);
the trash engine then moves only verified-recovered, unchanged pages to the
trash, never deletes, journals each PATCH so a rerun resumes, and can move
the pages it trashed back out.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import notion_page_trash as trash
from wom_kit.notion_page_recovery import ProviderResponse, _execute_recovery, plan_recovery

import test_notion_page_recovery as recovery_fixtures

PAGES = [str(uuid.UUID(int=number)) for number in (1, 2, 3)]


class TrashProvider:
    """Fake Notion holding per-page state; PATCH flips in_trash."""

    def __init__(self, edited: dict[str, str] | None = None, *, patch_status: int = 200) -> None:
        self.in_trash = {page: False for page in PAGES}
        self.edited = {page: "2026-08-09T00:00:00.000Z" for page in PAGES}
        self.edited.update(edited or {})
        self.patch_status = patch_status
        self.patches: list[tuple[str, bool]] = []
        self.gets = 0

    def retrieve_page(self, page_id, credential, *, api_version):
        self.gets += 1
        if page_id == PAGES[2]:
            return ProviderResponse(404, {"reason_code": "not_found"})
        return ProviderResponse(200, {"object": "page", "id": page_id, "in_trash": self.in_trash[page_id],
                                      "last_edited_time": self.edited[page_id]})

    def move_page_to_trash(self, page_id, credential, *, api_version, in_trash=True):
        self.patches.append((page_id, in_trash))
        if self.patch_status != 200:
            return ProviderResponse(self.patch_status, {"reason_code": "synthetic"})
        self.in_trash[page_id] = in_trash
        return ProviderResponse(200, {"object": "page", "id": page_id, "in_trash": in_trash,
                                      "last_edited_time": self.edited[page_id]})


class NotionPageTrashTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-notion-trash-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.manifest = recovery_fixtures.make_manifest((3,))
        recovery_fixtures.ensure_archive_identity(self.root, self.manifest["archive_id"])
        provider = recovery_fixtures.FakeProvider(
            metadata={page: [recovery_fixtures.ok_metadata(page)] for page in PAGES[:2]}
            | {PAGES[2]: [ProviderResponse(404, {"reason_code": "not_found"})]},
            markdown={page: [recovery_fixtures.ok_markdown(page, f"# synthetic {page}\n")] for page in PAGES[:2]},
        )
        plan = plan_recovery(self.root, self.manifest, max_items=3)
        recovered = _execute_recovery(
            self.root, self.manifest, expected_plan_sha256=plan["plan_sha256"], reviewed_by="reviewer-1",
            max_items=3, provider=provider, credential_broker=recovery_fixtures.FakeBroker(),
            request_pacer=lambda: None, sleep=lambda _delay: None, jitter=lambda: 0.0,
            clock=recovery_fixtures.fixed_clock,
        )
        self.assertEqual(recovered["counts"]["outcomes"]["recovered"], 2, recovered)

    def run_trash(self, provider: TrashProvider, *, restore: bool = False) -> dict:
        plan = trash.plan_trash(self.root, self.manifest, max_items=3, restore=restore)
        self.assertTrue(plan["ok"], plan)
        return trash.execute_trash(
            self.root, self.manifest, expected_plan_sha256=plan["plan_sha256"], max_items=3, restore=restore,
            provider=provider, credential_broker=recovery_fixtures.FakeBroker(),
            clock=lambda: datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc),
        )

    def test_plan_lists_only_verified_recovered_pages_without_echoing_ids(self) -> None:
        plan = trash.plan_trash(self.root, self.manifest, max_items=3)
        self.assertEqual(plan["counts"]["eligible_item_count"], 2)
        self.assertEqual(plan["counts"]["not_eligible_item_count"], 1)
        self.assertFalse(plan["permanent_delete"])
        self.assertEqual(plan["provider_calls"], 0)
        for page in PAGES:
            self.assertNotIn(page, json.dumps(plan))

    def test_trash_moves_unchanged_pages_skips_changed_and_resumes(self) -> None:
        # Page 2 was edited in the same minute its recovery completed (12:00).
        provider = TrashProvider(edited={PAGES[1]: "2026-08-10T12:00:00.000Z"})
        result = self.run_trash(provider)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["counts"]["trashed"], 1)
        self.assertEqual(result["counts"]["changed_since_recovery"], 1)
        self.assertEqual(provider.patches, [(PAGES[0], True)])
        self.assertTrue(provider.in_trash[PAGES[0]])
        self.assertTrue((self.root / result["receipt_path"]).is_file())
        for page in PAGES:
            self.assertNotIn(page, json.dumps(result))
        again = self.run_trash(provider)
        self.assertEqual(again["counts"]["skipped_settled"], 2)
        self.assertEqual(len(provider.patches), 1)

    def test_a_token_without_update_capability_stops_after_one_refused_patch(self) -> None:
        provider = TrashProvider(patch_status=403)
        result = self.run_trash(provider)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "notion_update_capability_missing")
        self.assertEqual(len(provider.patches), 1)
        self.assertFalse(any(provider.in_trash.values()))

    def test_restore_moves_trashed_pages_back(self) -> None:
        provider = TrashProvider()
        self.assertEqual(self.run_trash(provider)["counts"]["trashed"], 2)
        restored = self.run_trash(provider, restore=True)
        self.assertEqual(restored["counts"]["restored"], 2, restored)
        self.assertFalse(any(provider.in_trash.values()))

    def test_a_changed_plan_is_refused_before_any_call(self) -> None:
        provider = TrashProvider()
        result = trash.execute_trash(
            self.root, self.manifest, expected_plan_sha256="sha256:" + "0" * 64, max_items=3,
            provider=provider, credential_broker=recovery_fixtures.FakeBroker(),
        )
        self.assertEqual(result["blockers"], ["notion_page_trash_plan_changed"])
        self.assertEqual(provider.gets, 0)

    def test_same_minute_rule(self) -> None:
        self.assertTrue(trash.changed_since_recovery("2026-08-10T12:00:00.000Z", "2026-08-10T12:00:40Z"))
        self.assertTrue(trash.changed_since_recovery("2026-08-10T12:05:00.000Z", "2026-08-10T12:00:40Z"))
        self.assertFalse(trash.changed_since_recovery("2026-08-10T11:59:00.000Z", "2026-08-10T12:00:40Z"))
        self.assertTrue(trash.changed_since_recovery(None, "2026-08-10T12:00:40Z"))


if __name__ == "__main__":
    unittest.main()
