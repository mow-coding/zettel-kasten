"""Public session identity contains no display data and grants no authority."""

import copy
import json
from dataclasses import FrozenInstanceError, replace
import unittest

from wom_kit.work_session_binding import (
    WorkSessionBinding, WorkSessionBindingError, new_work_session_ref,
)


def binding_fixture(archive_identity_sha256="sha256:" + "a" * 64, **changes):
    fields = {
        "client_app_ref": "client_app_" + "1" * 32,
        "workstream_ref": "workstream_" + "2" * 32,
        "work_session_ref": "work_session_" + "3" * 32,
        "revision": 1,
        "archive_identity_sha256": archive_identity_sha256,
        "client_app_label_sha256": "sha256:" + "b" * 64,
        "workstream_label_sha256": "sha256:" + "c" * 64,
    }
    return WorkSessionBinding.build(**(fields | changes))


class WorkSessionBindingTests(unittest.TestCase):
    def test_round_trip_is_frozen_and_does_not_retain_mutable_input(self):
        binding = binding_fixture()
        document = binding.document()
        rebuilt = WorkSessionBinding.from_document(document)
        self.assertEqual(rebuilt, binding)
        document["revision"] = 2
        self.assertEqual(rebuilt.revision, 1)
        with self.assertRaises(FrozenInstanceError):
            rebuilt.revision = 2
        self.assertEqual(set(rebuilt.document()), {
            "schema", "client_app_ref", "workstream_ref", "work_session_ref",
            "revision", "archive_identity_sha256", "client_app_label_sha256",
            "workstream_label_sha256", "binding_sha256",
        })

    def test_every_identity_dimension_is_digest_bound(self):
        binding = binding_fixture()
        for name, value in {
            "client_app_ref": "client_app_" + "4" * 32,
            "workstream_ref": "workstream_" + "4" * 32,
            "work_session_ref": "work_session_" + "4" * 32,
            "revision": 2,
            "archive_identity_sha256": "sha256:" + "d" * 64,
            "client_app_label_sha256": "sha256:" + "d" * 64,
            "workstream_label_sha256": "sha256:" + "d" * 64,
        }.items():
            with self.subTest(field=name):
                with self.assertRaises(WorkSessionBindingError):
                    replace(binding, **{name: value})
                self.assertNotEqual(binding_fixture(**{name: value}).binding_sha256, binding.binding_sha256)

    def test_strict_fields_types_refs_and_private_failure_redaction(self):
        baseline = binding_fixture().document()
        cases = [{**baseline, "display_name": "private_person_marker"}]
        for name in baseline:
            case = dict(baseline)
            del case[name]
            cases.append(case)
        for name in ("client_app_ref", "workstream_ref", "work_session_ref"):
            for value in ("private_person_marker", "workstream_" + "f" * 31, None, True, 1):
                cases.append({**baseline, name: value})
        for value in (True, False, 0, -1, 1.0, "1", 2**63, None):
            cases.append({**baseline, "revision": value})
        for value in ("f" * 64, "sha256:" + "F" * 64, None, "private_token_marker"):
            cases.append({**baseline, "binding_sha256": value})
        for case in cases:
            with self.subTest(keys=set(case)), self.assertRaises(WorkSessionBindingError) as captured:
                WorkSessionBinding.from_document(copy.deepcopy(case))
            self.assertEqual(str(captured.exception), "work_session_binding_invalid")
            self.assertNotIn("private_", repr(captured.exception))
        self.assertNotIn("private_", json.dumps(baseline))

    def test_random_refs_are_distinct_typed_and_do_not_encode_labels(self):
        for kind in ("client_app", "workstream", "work_session"):
            generated = {new_work_session_ref(kind) for _ in range(128)}
            self.assertEqual(len(generated), 128)
            for value in generated:
                self.assertRegex(value, rf"^{kind}_[0-9a-f]{{32}}$")
        with self.assertRaises(WorkSessionBindingError):
            new_work_session_ref("private_person_marker")


if __name__ == "__main__":
    unittest.main()
