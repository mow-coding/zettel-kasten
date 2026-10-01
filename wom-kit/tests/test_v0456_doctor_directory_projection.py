"""v0.4.57: Doctor no longer reports a false doctor_cache_snapshot_stale on Windows.

NTFS updates the times and end-of-file of a child DIRECTORY copied into its
parent's index lazily (measured stale in 14 of 20 trials after a change inside
the child; any handle open or lstat refreshes it). Doctor's native first
barrier hashed those copies, so a refresh between the baseline and the check
looked like a concurrent change. Child directories now keep only name, volume,
file id, attributes and reparse tag in that projection; files keep everything.
"""

import unittest

from wom_kit.archive_cli import Doctor

SCHEMA = "windows_directory_generation_observation_v1"


def _token(file_id: str, attributes: int, times: tuple[int, int, int, int]) -> tuple:
    return (SCHEMA, 7, file_id, attributes, *times, 0, True)


class DoctorDirectoryProjectionTests(unittest.TestCase):
    def test_a_lazily_updated_child_directory_time_is_not_a_change(self):
        before = {"offload-proofs": _token("a" * 32, 0x10, (1, 100, 100, 0)),
                  "plan.json": _token("b" * 32, 0x20, (1, 5, 5, 42))}
        after = {"offload-proofs": _token("a" * 32, 0x10, (1, 160, 161, 4096)),
                 "plan.json": _token("b" * 32, 0x20, (1, 5, 5, 42))}
        self.assertEqual(Doctor._inventory_native_directory_entry_digest(before)[0],
                         Doctor._inventory_native_directory_entry_digest(after)[0])

    def test_a_file_change_or_a_replaced_directory_is_still_a_change(self):
        before = {"offload-proofs": _token("a" * 32, 0x10, (1, 100, 100, 0)),
                  "plan.json": _token("b" * 32, 0x20, (1, 5, 5, 42))}
        file_changed = {**before, "plan.json": _token("b" * 32, 0x20, (1, 6, 6, 43))}
        directory_replaced = {**before, "offload-proofs": _token("c" * 32, 0x10, (1, 100, 100, 0))}
        baseline = Doctor._inventory_native_directory_entry_digest(before)[0]
        self.assertNotEqual(baseline, Doctor._inventory_native_directory_entry_digest(file_changed)[0])
        self.assertNotEqual(baseline, Doctor._inventory_native_directory_entry_digest(directory_replaced)[0])


if __name__ == "__main__":
    unittest.main()
