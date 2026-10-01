"""Beta letter 179: a long Git backup preview stopped with receipt_inventory_drifted and no writer.

On Windows a directory's st_size flips between 0 and its real size with no
activity (Python 3.12's lstat uses GetFileInformationByName), and the preview
compared it. Reproduced on Windows with the real CLI and nothing writing. The
recheck now ignores directory size and permission bits, still catches an added
or rewritten receipt, and says what drifted by kind and WOM category, never by
path.

Synthetic archive; no client data.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import git_backup_plan as planner


class ReceiptDriftTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        receipts = self.root / "receipts"
        for role in ("mint", "edges", "providers"):
            for index in range(20):
                path = receipts / role / f"receipt-{index:03d}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"{}\n")
        _inventory, cache, blockers = planner._receipt_inventory(self.root)
        self.assertEqual(blockers, [])
        self.cache = cache

    def test_a_directory_whose_size_flips_is_not_drift(self):
        real_lstat = os.lstat

        def flipping_lstat(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if os.path.isdir(path):
                values = list(info)
                values[6] = 49152 if info.st_size == 0 else 0  # st_size
                return os.stat_result(values, {name: getattr(info, name) for name in
                                               ("st_mtime_ns", "st_ctime_ns", "st_atime_ns", "st_file_attributes",
                                                "st_birthtime_ns") if hasattr(info, name)})
            return info

        with patch.object(planner.os, "lstat", side_effect=flipping_lstat):
            self.assertEqual(planner._receipt_inventory_recheck(self.root, self.cache), [])
            drift = planner._receipt_inventory_drift(self.root, self.cache)
        self.assertEqual(drift["drifted_entry_count"], 0)

    def test_an_added_or_rewritten_receipt_is_still_drift_and_named_by_category(self):
        target = self.root / "receipts" / "mint" / "receipt-000.json"
        target.write_bytes(b'{"changed": true}\n')
        (self.root / "receipts" / "edges" / "new.json").write_bytes(b"{}\n")
        os.utime(self.root / "receipts" / "edges", ns=(1, 1))  # make the membership change visible
        self.assertEqual(planner._receipt_inventory_recheck(self.root, self.cache), ["receipt_inventory_drifted"])
        drift = planner._receipt_inventory_drift(self.root, self.cache)
        self.assertGreaterEqual(drift["drifted_entry_count"], 2)
        self.assertIn("file_size_changed", drift["by_class"])
        self.assertIn("directory_entries_changed", drift["by_class"])
        self.assertIn("mint", drift["by_role"])
        self.assertIn("edges", drift["by_role"])
        self.assertTrue(drift["content_change_possible"])
        self.assertTrue(drift["membership_change_possible"])
        self.assertFalse(drift["paths_echoed"])
        self.assertNotIn(str(self.root), repr(drift))
        self.assertNotIn("receipt-000", repr(drift))

    def test_a_removed_receipt_is_entry_missing(self):
        (self.root / "receipts" / "providers" / "receipt-005.json").unlink()
        drift = planner._receipt_inventory_drift(self.root, self.cache)
        self.assertIn("entry_missing", drift["by_class"])
        # the folder that lost the file changed too: both are counted under its category
        self.assertEqual(drift["by_role"].get("providers"), drift["drifted_entry_count"])
        self.assertIn("directory_entries_changed", drift["by_class"])


if __name__ == "__main__":
    unittest.main()
