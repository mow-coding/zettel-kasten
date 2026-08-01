from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from wom_kit import private_objet_metadata_writer_contract as contract


KIT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = KIT_ROOT / "schemas"
PACKAGED_SCHEMA_ROOT = (
    KIT_ROOT / "src" / "wom_kit" / "_resources" / "schemas"
)
SCHEMA_FILES = {
    contract.INTAKE_SCHEMA:
        "private-objet-source-metadata-intake-v0.1.schema.json",
    contract.PLAN_SCHEMA:
        "private-objet-source-metadata-write-plan-v0.1.schema.json",
    contract.AUTHORITY_CHAIN_SCHEMA:
        "private-objet-source-metadata-authority-chain-v0.1.schema.json",
    contract.RECEIPT_SCHEMA:
        "private-objet-source-metadata-write-receipt-v0.1.schema.json",
    contract.JOURNAL_SCHEMA:
        "private-objet-source-metadata-write-journal-v0.1.schema.json",
}


def _digest(character: str) -> str:
    return "sha256:" + (character * 64)


def _absent_file_state() -> dict[str, object]:
    return {
        "state": "absent",
        "sha256": None,
        "byte_count": 0,
        "row_count": 0,
        "link_count": 0,
    }


def _unavailable_file_state() -> dict[str, object]:
    return {
        "state": "unavailable",
        "sha256": None,
        "byte_count": None,
        "row_count": None,
        "link_count": None,
    }


def _present_file_state(
    digest_character: str = "a",
    *,
    byte_count: int = 1,
    row_count: int = 1,
) -> dict[str, object]:
    return {
        "state": "present",
        "sha256": _digest(digest_character),
        "byte_count": byte_count,
        "row_count": row_count,
        "link_count": 1,
    }


def _present_invalid_file_state(
    digest_character: str = "a",
    *,
    byte_count: int = 1,
) -> dict[str, object]:
    return {
        "state": "present_invalid",
        "sha256": _digest(digest_character),
        "byte_count": byte_count,
        "row_count": None,
        "link_count": 1,
    }


def _intake(
    *,
    filename: str = "example.txt",
    profile: str = "literal_unicode",
    privacy_class: str = "private_archive",
) -> dict[str, object]:
    return {
        "schema": contract.INTAKE_SCHEMA,
        "object_id": _digest("0"),
        "privacy_class": privacy_class,
        "name_observation": {
            "original_filename": filename,
            "name_input_profile": profile,
        },
        "media_observation": {
            "value": "text/plain",
            "basis": "source_declared",
        },
        "size_bytes_observed": 12,
        "size_bytes_basis": "source_observed",
        "source_provenance": {
            "source_system": "synthetic",
            "source_record_id": None,
            "source_attachment_id": "attachment-1",
            "source_snapshot_sha256": _digest("1"),
            "observation_evidence_sha256": _digest("2"),
            "evidence_kind": "source_attachment_metadata",
            "captured_at": "2026-08-01T00:00:00Z",
        },
        "review_evidence": {
            "review_evidence_sha256": _digest("3"),
            "review_status": "human_reviewed",
        },
    }


def _directory_chain_absent() -> dict[str, object]:
    absent = {"state": "absent", "entry_count": 0}
    return {
        "receipts_root": deepcopy(absent),
        "objects_parent": deepcopy(absent),
        "private_receipt_directory": deepcopy(absent),
    }


def _directory_chain_after() -> dict[str, object]:
    return {
        "receipts_root": {"state": "present", "entry_count": 1},
        "objects_parent": {"state": "present", "entry_count": 1},
        "private_receipt_directory": {
            "state": "present",
            "entry_count": 0,
        },
    }


def _directory_chain_complete(
    *,
    receipt_entries: int = 0,
) -> dict[str, object]:
    return {
        "receipts_root": {"state": "present", "entry_count": 1},
        "objects_parent": {"state": "present", "entry_count": 1},
        "private_receipt_directory": {
            "state": "present",
            "entry_count": receipt_entries,
        },
    }


def _resource_binding() -> dict[str, object]:
    return {
        "basis": "append_worst_case_actor",
        "private_manifest_current_bytes": 0,
        "private_manifest_current_rows": 0,
        "canonical_stored_row_bytes": 1,
        "receipt_final_count_current": 0,
        "receipt_final_total_bytes_current": 0,
        "receipt_directory_entries_current": 0,
        "receipt_root_entries_after_bootstrap": 1,
        "receipt_objects_entries_after_bootstrap": 1,
        "manifest_directory_entries_with_both_locks": 2,
        "prospective_private_manifest_bytes": 1,
        "prospective_private_manifest_rows": 1,
        "prospective_receipt_bytes": 6239,
        "prospective_receipt_final_count": 1,
        "prospective_receipt_final_total_bytes": 6239,
        "prospective_receipt_directory_peak_entries": 2,
        "prospective_manifest_directory_peak_entries": 4,
        "prospective_journal_bytes": 7812,
    }


def _no_write_resource_binding(
    *,
    manifest_bytes: int,
    manifest_rows: int,
    receipt_count: int = 0,
    receipt_total_bytes: int = 0,
    receipt_entries: int = 0,
) -> dict[str, object]:
    return {
        "basis": "no_write",
        "private_manifest_current_bytes": manifest_bytes,
        "private_manifest_current_rows": manifest_rows,
        "canonical_stored_row_bytes": 1,
        "receipt_final_count_current": receipt_count,
        "receipt_final_total_bytes_current": receipt_total_bytes,
        "receipt_directory_entries_current": receipt_entries,
        "receipt_root_entries_after_bootstrap": 1,
        "receipt_objects_entries_after_bootstrap": 1,
        "manifest_directory_entries_with_both_locks": 2,
        "prospective_private_manifest_bytes": manifest_bytes,
        "prospective_private_manifest_rows": manifest_rows,
        "prospective_receipt_bytes": 0,
        "prospective_receipt_final_count": receipt_count,
        "prospective_receipt_final_total_bytes": receipt_total_bytes,
        "prospective_receipt_directory_peak_entries": receipt_entries,
        "prospective_manifest_directory_peak_entries": 2,
        "prospective_journal_bytes": 0,
    }


def _plan() -> dict[str, object]:
    authority_key = contract.authority_key_sha256(_digest("2"))
    absent = _absent_file_state()
    return {
        "schema": contract.PLAN_SCHEMA,
        "writer_state_machine_version":
            contract.WRITER_STATE_MACHINE_VERSION,
        "archive_id": "archive-1",
        "intake_sha256": _digest("4"),
        "canonical_row_sha256": _digest("5"),
        "observation_evidence_sha256": _digest("2"),
        "review_evidence_sha256": _digest("3"),
        "object_id": _digest("0"),
        "object_manifest_state": _present_file_state("6"),
        "object_manifest_match_count": 1,
        "private_manifest_before": deepcopy(absent),
        "private_manifest_after": _present_file_state("7"),
        "receipt_directory_chain_before": _directory_chain_absent(),
        "receipt_directory_chain_after": _directory_chain_after(),
        "receipt_state": deepcopy(absent),
        "journal_state": deepcopy(absent),
        "journal_sha256": None,
        "owned_temp_states": {
            "journal_temp": deepcopy(absent),
            "manifest_temp": deepcopy(absent),
            "receipt_temp": deepcopy(absent),
        },
        "planned_receipt_sha256": None,
        "prior_row_state": "absent",
        "receipt_inventory_state": "absent",
        "authority_chain_scope": "complete_current",
        "authority_chain_validation": "valid_complete",
        "authority_chain_sha256": _digest("8"),
        "intake_schema": contract.INTAKE_SCHEMA,
        "durable_schema": contract.DURABLE_SCHEMA,
        "normalization_profile":
            deepcopy(contract.NORMALIZATION_PROFILE_VALUE),
        "action": "append",
        "blocked_context": None,
        "derived_alias_count": 1,
        "existing_exact_row_count": 0,
        "exact_receipt_count": 0,
        "resource_binding": _resource_binding(),
        "private_manifest_relative_path": contract.PRIVATE_MANIFEST_PATH,
        "receipt_directory_relative_path": contract.RECEIPT_DIRECTORY,
        "authority_key_sha256": authority_key,
        "receipt_relative_path":
            contract.receipt_relative_path(authority_key),
    }


def _plan_for_action(action: str) -> dict[str, object]:
    plan = _plan()
    absent = _absent_file_state()
    if action == "append":
        return plan
    if action == "blocked_append":
        plan["action"] = "blocked"
        plan["blocked_context"] = "append"
        plan["private_manifest_after"] = deepcopy(
            plan["private_manifest_before"]
        )
        return plan
    if action == "rollback_required":
        plan.update(
            {
                "action": "rollback_required",
                "private_manifest_after": deepcopy(
                    plan["private_manifest_before"]
                ),
                "receipt_directory_chain_before":
                    _directory_chain_complete(),
                "receipt_directory_chain_after":
                    _directory_chain_complete(),
                "owned_temp_states": {
                    "journal_temp": _present_file_state(
                        "a",
                        byte_count=10,
                    ),
                    "manifest_temp": deepcopy(absent),
                    "receipt_temp": deepcopy(absent),
                },
                "planned_receipt_sha256": _digest("9"),
                "resource_binding": _no_write_resource_binding(
                    manifest_bytes=0,
                    manifest_rows=0,
                ),
            }
        )
        return plan
    if action in {"recovery_required", "blocked_recovery"}:
        manifest = _present_file_state("7")
        journal = _present_file_state("a", byte_count=100)
        plan.update(
            {
                "action": (
                    "recovery_required"
                    if action == "recovery_required"
                    else "blocked"
                ),
                "blocked_context": (
                    None if action == "recovery_required" else "recovery"
                ),
                "private_manifest_before": deepcopy(manifest),
                "private_manifest_after": deepcopy(manifest),
                "receipt_directory_chain_before":
                    _directory_chain_complete(),
                "receipt_directory_chain_after":
                    _directory_chain_complete(),
                "journal_state": journal,
                "journal_sha256": journal["sha256"],
                "planned_receipt_sha256": _digest("9"),
                "prior_row_state": "exact",
                "authority_chain_scope":
                    "prefix_before_interrupted_append",
                "authority_chain_validation": "valid_recovery_prefix",
                "existing_exact_row_count": 1,
                "resource_binding": {
                    **_no_write_resource_binding(
                        manifest_bytes=1,
                        manifest_rows=1,
                    ),
                    "basis": "recovery_exact_journal",
                    "prospective_receipt_bytes": 100,
                    "prospective_receipt_final_count": 1,
                    "prospective_receipt_final_total_bytes": 100,
                    "prospective_receipt_directory_peak_entries": 2,
                    "prospective_journal_bytes": 100,
                },
            }
        )
        return plan
    if action == "already_applied":
        manifest = _present_file_state("7")
        receipt = _present_file_state("9", byte_count=100)
        plan.update(
            {
                "action": "already_applied",
                "private_manifest_before": deepcopy(manifest),
                "private_manifest_after": deepcopy(manifest),
                "receipt_directory_chain_before":
                    _directory_chain_complete(receipt_entries=1),
                "receipt_directory_chain_after":
                    _directory_chain_complete(receipt_entries=1),
                "receipt_state": receipt,
                "planned_receipt_sha256": receipt["sha256"],
                "prior_row_state": "exact",
                "receipt_inventory_state": "exact",
                "existing_exact_row_count": 1,
                "exact_receipt_count": 1,
                "resource_binding": _no_write_resource_binding(
                    manifest_bytes=1,
                    manifest_rows=1,
                    receipt_count=1,
                    receipt_total_bytes=100,
                    receipt_entries=1,
                ),
            }
        )
        return plan
    if action == "manual_hold":
        resource = _no_write_resource_binding(
            manifest_bytes=0,
            manifest_rows=0,
        )
        resource["receipt_root_entries_after_bootstrap"] = 0
        resource["receipt_objects_entries_after_bootstrap"] = 0
        plan.update(
            {
                "action": "manual_hold",
                "private_manifest_after": deepcopy(
                    plan["private_manifest_before"]
                ),
                "receipt_directory_chain_after": deepcopy(
                    plan["receipt_directory_chain_before"]
                ),
                "resource_binding": resource,
            }
        )
        return plan
    raise AssertionError(f"unsupported synthetic action: {action}")


def _manual_hold_prior_plan(
    prior_state: str,
    *,
    manifest_rows: int,
    exact_row_count: int,
) -> dict[str, object]:
    plan = _plan_for_action("manual_hold")
    if manifest_rows:
        manifest = _present_file_state(
            "7",
            byte_count=manifest_rows,
            row_count=manifest_rows,
        )
        plan["private_manifest_before"] = deepcopy(manifest)
        plan["private_manifest_after"] = deepcopy(manifest)
    plan["prior_row_state"] = prior_state
    plan["existing_exact_row_count"] = exact_row_count
    resource = _no_write_resource_binding(
        manifest_bytes=manifest_rows,
        manifest_rows=manifest_rows,
    )
    resource["receipt_root_entries_after_bootstrap"] = 0
    resource["receipt_objects_entries_after_bootstrap"] = 0
    plan["resource_binding"] = resource
    return plan


def _manual_hold_receipt_plan(
    inventory_state: str,
    *,
    exact_receipt_count: int,
    valid_receipt: bool,
    receipt_count: int,
) -> dict[str, object]:
    plan = _plan_for_action("manual_hold")
    receipt = (
        _present_file_state("9", byte_count=100)
        if valid_receipt
        else {
            "state": "present_invalid",
            "sha256": _digest("9"),
            "byte_count": 100,
            "row_count": None,
            "link_count": 1,
        }
    )
    plan["receipt_directory_chain_before"] = (
        _directory_chain_complete(receipt_entries=receipt_count)
    )
    plan["receipt_directory_chain_after"] = deepcopy(
        plan["receipt_directory_chain_before"]
    )
    plan["receipt_state"] = receipt
    plan["receipt_inventory_state"] = inventory_state
    plan["exact_receipt_count"] = exact_receipt_count
    plan["planned_receipt_sha256"] = (
        receipt["sha256"]
        if inventory_state in {"exact", "orphan"}
        else None
    )
    plan["resource_binding"] = _no_write_resource_binding(
        manifest_bytes=0,
        manifest_rows=0,
        receipt_count=receipt_count,
        receipt_total_bytes=100 * receipt_count,
        receipt_entries=receipt_count,
    )
    return plan


def _manual_hold_journal_plan(*, use_temp: bool = False) -> dict[str, object]:
    plan = _plan_for_action("manual_hold")
    journal = _present_file_state("a", byte_count=100)
    if use_temp:
        plan["owned_temp_states"]["journal_temp"] = journal
    else:
        plan["journal_state"] = journal
        plan["journal_sha256"] = journal["sha256"]
    plan["planned_receipt_sha256"] = _digest("9")
    return plan


def _manual_hold_receipt_temp_plan(
    *,
    valid_document: bool = True,
) -> dict[str, object]:
    plan = _plan_for_action("manual_hold")
    receipt_temp = (
        _present_file_state("9", byte_count=100)
        if valid_document
        else _present_invalid_file_state("9", byte_count=100)
    )
    plan["owned_temp_states"]["receipt_temp"] = receipt_temp
    plan["receipt_directory_chain_before"] = (
        _directory_chain_complete(receipt_entries=1)
    )
    plan["receipt_directory_chain_after"] = deepcopy(
        plan["receipt_directory_chain_before"]
    )
    plan["resource_binding"] = _no_write_resource_binding(
        manifest_bytes=0,
        manifest_rows=0,
        receipt_entries=1,
    )
    return plan


def _manual_hold_manifest_temp_plan(
    *,
    valid_document: bool = True,
    row_count: int = 1,
) -> dict[str, object]:
    plan = _plan_for_action("manual_hold")
    manifest_temp = (
        _present_file_state(
            "7",
            byte_count=max(1, row_count),
            row_count=row_count,
        )
        if valid_document
        else _present_invalid_file_state("7")
    )
    plan["owned_temp_states"]["manifest_temp"] = manifest_temp
    plan["resource_binding"][
        "manifest_directory_entries_with_both_locks"
    ] = 3
    plan["resource_binding"][
        "prospective_manifest_directory_peak_entries"
    ] = 3
    return plan


def _receipt() -> dict[str, object]:
    plan = _plan()
    return {
        "schema": contract.RECEIPT_SCHEMA,
        "writer_state_machine_version":
            contract.WRITER_STATE_MACHINE_VERSION,
        "lifecycle": "private_objet_source_metadata_write",
        "action": "applied",
        "artifact_class": "private_archive",
        "archive_id": plan["archive_id"],
        "record_privacy_class": "private_archive",
        "object_id": plan["object_id"],
        "authority_key_sha256": plan["authority_key_sha256"],
        "intake_sha256": plan["intake_sha256"],
        "canonical_row_sha256": plan["canonical_row_sha256"],
        "observation_evidence_sha256":
            plan["observation_evidence_sha256"],
        "review_evidence_sha256": plan["review_evidence_sha256"],
        "reviewed_by": "operator:a",
        "external_writers_quiescent_affirmed": True,
        "mutation_platform_profile": contract.MUTATION_PLATFORM_PROFILE,
        "power_loss_durability_verified": False,
        "plan_binding": plan,
        "plan_sha256":
            contract.sha256_digest(contract.canonical_json_bytes(plan)),
        "object_manifest_state": deepcopy(plan["object_manifest_state"]),
        "authority_chain_before_sha256":
            plan["authority_chain_sha256"],
        "private_manifest_before": deepcopy(
            plan["private_manifest_before"]
        ),
        "private_manifest_after": deepcopy(plan["private_manifest_after"]),
        "intake_schema": contract.INTAKE_SCHEMA,
        "durable_schema": contract.DURABLE_SCHEMA,
        "normalization_profile":
            deepcopy(contract.NORMALIZATION_PROFILE_VALUE),
        "derived_alias_count": 1,
        "closed_actions": {
            "source_artifact_modified": False,
            "object_bytes_opened": False,
            "provider_or_network_called": False,
            "database_or_index_written": False,
        },
    }


def _journal() -> dict[str, object]:
    receipt = _receipt()
    authority_key = receipt["authority_key_sha256"]
    return {
        "schema": contract.JOURNAL_SCHEMA,
        "writer_state_machine_version":
            contract.WRITER_STATE_MACHINE_VERSION,
        "transition": "append",
        "plan_sha256": receipt["plan_sha256"],
        "authority_chain_before_sha256":
            receipt["authority_chain_before_sha256"],
        "authority_key_sha256": authority_key,
        "receipt_relative_path":
            contract.receipt_relative_path(authority_key),
        "receipt_document": receipt,
        "receipt_sha256":
            contract.sha256_digest(contract.stored_json_bytes(receipt)),
        "object_manifest_state": deepcopy(receipt["object_manifest_state"]),
        "private_manifest_before": deepcopy(
            receipt["private_manifest_before"]
        ),
        "private_manifest_after": deepcopy(
            receipt["private_manifest_after"]
        ),
        "owned_temp_relative_paths":
            contract.owned_temp_relative_paths(authority_key),
    }


def _authority_chain() -> dict[str, object]:
    plan = _plan()
    return {
        "schema": contract.AUTHORITY_CHAIN_SCHEMA,
        "private_manifest_state": deepcopy(plan["private_manifest_after"]),
        "entries": [
            {
                "row_number": 1,
                "intake_sha256": plan["intake_sha256"],
                "canonical_row_sha256": plan["canonical_row_sha256"],
                "observation_evidence_sha256":
                    plan["observation_evidence_sha256"],
                "review_evidence_sha256":
                    plan["review_evidence_sha256"],
                "authority_key_sha256": plan["authority_key_sha256"],
                "receipt_relative_path": plan["receipt_relative_path"],
                "receipt_sha256": _digest("9"),
                "manifest_before": deepcopy(
                    plan["private_manifest_before"]
                ),
                "manifest_after": deepcopy(plan["private_manifest_after"]),
            }
        ],
    }


class PrivateMetadataWriterSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas: dict[str, dict[str, object]] = {}
        cls.registry = Registry()
        for schema_id, filename in SCHEMA_FILES.items():
            schema = json.loads(
                (SCHEMA_ROOT / filename).read_text(encoding="utf-8")
            )
            Draft202012Validator.check_schema(schema)
            if schema["$id"] != schema_id:
                raise AssertionError(f"schema id mismatch for {filename}")
            cls.schemas[schema_id] = schema
            cls.registry = cls.registry.with_resource(
                schema_id,
                Resource.from_contents(schema),
            )

    def _oracle(self, schema_id: str, value: object) -> bool:
        return Draft202012Validator(
            self.schemas[schema_id],
            registry=self.registry,
            format_checker=FormatChecker(),
        ).is_valid(value)

    def test_five_exact_schema_ids_are_draft_2020_12(self) -> None:
        self.assertEqual(set(self.schemas), set(SCHEMA_FILES))
        for schema in self.schemas.values():
            self.assertEqual(
                schema["$schema"],
                "https://json-schema.org/draft/2020-12/schema",
            )

    def test_source_and_packaged_schema_bytes_are_identical(self) -> None:
        for filename in SCHEMA_FILES.values():
            self.assertEqual(
                (SCHEMA_ROOT / filename).read_bytes(),
                (PACKAGED_SCHEMA_ROOT / filename).read_bytes(),
                filename,
            )

    def test_runtime_and_schema_oracle_accept_all_five_valid_documents(
        self,
    ) -> None:
        corpus = (
            (
                contract.INTAKE_SCHEMA,
                _intake(),
                contract.validate_private_metadata_intake,
            ),
            (
                contract.PLAN_SCHEMA,
                _plan(),
                contract.validate_private_metadata_write_plan,
            ),
            (
                contract.AUTHORITY_CHAIN_SCHEMA,
                _authority_chain(),
                contract.validate_private_metadata_authority_chain,
            ),
            (
                contract.RECEIPT_SCHEMA,
                _receipt(),
                contract.validate_private_metadata_write_receipt,
            ),
            (
                contract.JOURNAL_SCHEMA,
                _journal(),
                contract.validate_private_metadata_write_journal,
            ),
        )
        for schema_id, document, runtime_validator in corpus:
            self.assertTrue(self._oracle(schema_id, document), schema_id)
            self.assertTrue(
                runtime_validator(document)["accepted"],
                schema_id,
            )

    def test_runtime_and_schema_oracle_reject_closed_shape_mutations(
        self,
    ) -> None:
        corpus = (
            (
                contract.INTAKE_SCHEMA,
                _intake(),
                contract.validate_private_metadata_intake,
            ),
            (
                contract.PLAN_SCHEMA,
                _plan(),
                contract.validate_private_metadata_write_plan,
            ),
            (
                contract.AUTHORITY_CHAIN_SCHEMA,
                _authority_chain(),
                contract.validate_private_metadata_authority_chain,
            ),
            (
                contract.RECEIPT_SCHEMA,
                _receipt(),
                contract.validate_private_metadata_write_receipt,
            ),
            (
                contract.JOURNAL_SCHEMA,
                _journal(),
                contract.validate_private_metadata_write_journal,
            ),
        )
        for schema_id, document, runtime_validator in corpus:
            extra = deepcopy(document)
            extra["unexpected"] = True
            missing = deepcopy(document)
            del missing["schema"]
            wrong_schema = deepcopy(document)
            wrong_schema["schema"] = "wom-kit/wrong/v9"
            for rejected in (extra, missing, wrong_schema):
                self.assertFalse(self._oracle(schema_id, rejected), schema_id)
                self.assertFalse(
                    runtime_validator(rejected)["accepted"],
                    schema_id,
                )

    def test_runtime_and_schema_oracle_reject_every_leaf_wrong_type(
        self,
    ) -> None:
        corpus = (
            (
                contract.INTAKE_SCHEMA,
                _intake(),
                contract.validate_private_metadata_intake,
            ),
            (
                contract.PLAN_SCHEMA,
                _plan(),
                contract.validate_private_metadata_write_plan,
            ),
            (
                contract.AUTHORITY_CHAIN_SCHEMA,
                _authority_chain(),
                contract.validate_private_metadata_authority_chain,
            ),
            (
                contract.RECEIPT_SCHEMA,
                _receipt(),
                contract.validate_private_metadata_write_receipt,
            ),
            (
                contract.JOURNAL_SCHEMA,
                _journal(),
                contract.validate_private_metadata_write_journal,
            ),
        )

        def leaf_paths(
            value: object,
            prefix: tuple[object, ...] = (),
        ) -> list[tuple[object, ...]]:
            if type(value) is dict:
                result: list[tuple[object, ...]] = []
                for key, item in value.items():
                    result.extend(leaf_paths(item, prefix + (key,)))
                return result
            if type(value) is list:
                result = []
                for index, item in enumerate(value):
                    result.extend(leaf_paths(item, prefix + (index,)))
                return result
            return [prefix]

        def replace_leaf(
            document: object,
            path: tuple[object, ...],
        ) -> None:
            current = document
            for key in path[:-1]:
                current = current[key]
            existing = current[path[-1]]
            if type(existing) is str:
                replacement: object = []
            elif type(existing) is bool:
                replacement = "not-a-boolean"
            elif type(existing) is int:
                replacement = False
            elif existing is None:
                replacement = {}
            else:
                raise AssertionError("unexpected fixture leaf type")
            current[path[-1]] = replacement

        for schema_id, document, runtime_validator in corpus:
            for path in leaf_paths(document):
                rejected = deepcopy(document)
                replace_leaf(rejected, path)
                self.assertFalse(
                    self._oracle(schema_id, rejected),
                    f"{schema_id}: {path}",
                )
                self.assertFalse(
                    runtime_validator(rejected)["accepted"],
                    f"{schema_id}: {path}",
                )

    def test_nested_objects_reject_additional_properties(self) -> None:
        corpus = (
            (
                contract.INTAKE_SCHEMA,
                _intake(),
                ("source_provenance",),
                contract.validate_private_metadata_intake,
            ),
            (
                contract.PLAN_SCHEMA,
                _plan(),
                ("resource_binding",),
                contract.validate_private_metadata_write_plan,
            ),
            (
                contract.AUTHORITY_CHAIN_SCHEMA,
                _authority_chain(),
                ("entries", 0),
                contract.validate_private_metadata_authority_chain,
            ),
            (
                contract.RECEIPT_SCHEMA,
                _receipt(),
                ("closed_actions",),
                contract.validate_private_metadata_write_receipt,
            ),
            (
                contract.JOURNAL_SCHEMA,
                _journal(),
                ("receipt_document", "closed_actions"),
                contract.validate_private_metadata_write_journal,
            ),
        )
        for schema_id, document, path, runtime_validator in corpus:
            rejected = deepcopy(document)
            nested = rejected
            for key in path:
                nested = nested[key]
            nested["unexpected"] = True
            self.assertFalse(self._oracle(schema_id, rejected), schema_id)
            self.assertFalse(
                runtime_validator(rejected)["accepted"],
                schema_id,
            )

    def test_json_boolean_is_never_a_numeric_count(self) -> None:
        intake = _intake()
        intake["size_bytes_observed"] = True
        self.assertFalse(self._oracle(contract.INTAKE_SCHEMA, intake))
        self.assertFalse(
            contract.validate_private_metadata_intake(intake)["accepted"]
        )

        plan = _plan()
        plan["resource_binding"]["prospective_receipt_bytes"] = False
        self.assertFalse(self._oracle(contract.PLAN_SCHEMA, plan))
        self.assertFalse(
            contract.validate_private_metadata_write_plan(plan)["accepted"]
        )

    def test_semantic_validators_reject_cross_field_mismatches(self) -> None:
        self.assertTrue(
            contract.validate_private_metadata_write_plan_semantics(
                _plan()
            )["accepted"]
        )
        plan = _plan()
        plan["receipt_relative_path"] = (
            contract.RECEIPT_DIRECTORY + ("f" * 64) + ".json"
        )
        self.assertTrue(
            contract.validate_private_metadata_write_plan(plan)["accepted"]
        )
        self.assertFalse(
            contract.validate_private_metadata_write_plan_semantics(plan)[
                "accepted"
            ]
        )

        receipt = _receipt()
        receipt["archive_id"] = "archive-2"
        self.assertTrue(
            contract.validate_private_metadata_write_receipt(receipt)[
                "accepted"
            ]
        )
        self.assertEqual(
            contract.validate_private_metadata_write_receipt_semantics(
                receipt
            )["issue_codes"],
            ["private_metadata_receipt_plan_authority_chain_mismatch"],
        )

        journal = _journal()
        journal["private_manifest_after"]["sha256"] = _digest("f")
        self.assertTrue(
            contract.validate_private_metadata_write_journal(journal)[
                "accepted"
            ]
        )
        self.assertEqual(
            contract.validate_private_metadata_write_journal_semantics(
                journal
            )["issue_codes"],
            ["private_metadata_journal_cross_field_mismatch"],
        )

    def test_authority_chain_semantics_bind_order_and_receipt_path(self) -> None:
        chain = _authority_chain()
        self.assertTrue(
            contract.validate_private_metadata_authority_chain_semantics(
                chain
            )["accepted"]
        )
        chain["entries"][0]["row_number"] = 2
        self.assertTrue(
            contract.validate_private_metadata_authority_chain(chain)[
                "accepted"
            ]
        )
        self.assertFalse(
            contract.validate_private_metadata_authority_chain_semantics(
                chain
            )["accepted"]
        )

    def test_every_closed_plan_action_has_one_valid_semantic_fixture(
        self,
    ) -> None:
        for action in (
            "append",
            "blocked_append",
            "rollback_required",
            "recovery_required",
            "blocked_recovery",
            "already_applied",
            "manual_hold",
        ):
            plan = _plan_for_action(action)
            self.assertTrue(
                contract.validate_private_metadata_write_plan(plan)[
                    "accepted"
                ],
                action,
            )
            self.assertTrue(
                contract.validate_private_metadata_write_plan_semantics(
                    plan,
                    require_final_size_binding=True,
                )["accepted"],
                action,
            )
            self.assertTrue(
                contract.parse_private_metadata_write_plan_bytes(
                    contract.canonical_json_bytes(plan)
                )["accepted"],
                action,
            )

    def test_manual_hold_valid_closed_state_matrix(self) -> None:
        receipt_link_two = _manual_hold_receipt_plan(
            "exact",
            exact_receipt_count=1,
            valid_receipt=True,
            receipt_count=1,
        )
        receipt_link_two["receipt_state"]["link_count"] = 2
        conflicting_receipt_link_two = _manual_hold_receipt_plan(
            "conflicting",
            exact_receipt_count=0,
            valid_receipt=False,
            receipt_count=1,
        )
        conflicting_receipt_link_two["receipt_state"]["link_count"] = 2
        fixed_journal_link_two = _manual_hold_journal_plan()
        fixed_journal_link_two["journal_state"]["link_count"] = 2
        journal_temp_link_two = _manual_hold_journal_plan(use_temp=True)
        journal_temp_link_two["owned_temp_states"][
            "journal_temp"
        ]["link_count"] = 2
        receipt_temp_link_two = _manual_hold_receipt_temp_plan()
        receipt_temp_link_two["owned_temp_states"][
            "receipt_temp"
        ]["link_count"] = 2

        fixed_invalid_journal_link_two = _plan_for_action("manual_hold")
        fixed_invalid_journal_link_two["journal_state"] = (
            _present_invalid_file_state("a")
        )
        fixed_invalid_journal_link_two["journal_state"]["link_count"] = 2
        fixed_invalid_journal_link_two["journal_sha256"] = (
            fixed_invalid_journal_link_two["journal_state"]["sha256"]
        )
        journal_temp_invalid_link_two = _plan_for_action("manual_hold")
        journal_temp_invalid_link_two["owned_temp_states"][
            "journal_temp"
        ] = _present_invalid_file_state("a")
        journal_temp_invalid_link_two["owned_temp_states"][
            "journal_temp"
        ]["link_count"] = 2
        receipt_temp_invalid_link_two = (
            _manual_hold_receipt_temp_plan(valid_document=False)
        )
        receipt_temp_invalid_link_two["owned_temp_states"][
            "receipt_temp"
        ]["link_count"] = 2

        cases = {
            "clean_absent": _plan_for_action("manual_hold"),
            "prior_exact": _manual_hold_prior_plan(
                "exact",
                manifest_rows=1,
                exact_row_count=1,
            ),
            "prior_collision": _manual_hold_prior_plan(
                "collision",
                manifest_rows=1,
                exact_row_count=0,
            ),
            "prior_multiple_no_exact": _manual_hold_prior_plan(
                "multiple",
                manifest_rows=2,
                exact_row_count=0,
            ),
            "prior_multiple_two_exact": _manual_hold_prior_plan(
                "multiple",
                manifest_rows=2,
                exact_row_count=2,
            ),
            "receipt_exact": _manual_hold_receipt_plan(
                "exact",
                exact_receipt_count=1,
                valid_receipt=True,
                receipt_count=1,
            ),
            "receipt_conflicting": _manual_hold_receipt_plan(
                "conflicting",
                exact_receipt_count=0,
                valid_receipt=False,
                receipt_count=1,
            ),
            "receipt_multiple": _manual_hold_receipt_plan(
                "multiple",
                exact_receipt_count=2,
                valid_receipt=True,
                receipt_count=2,
            ),
            "receipt_orphan": _manual_hold_receipt_plan(
                "orphan",
                exact_receipt_count=1,
                valid_receipt=True,
                receipt_count=1,
            ),
            "fixed_journal_evidence": _manual_hold_journal_plan(),
            "journal_temp_evidence": _manual_hold_journal_plan(
                use_temp=True
            ),
            "receipt_link_two": receipt_link_two,
            "conflicting_receipt_invalid_link_two":
                conflicting_receipt_link_two,
            "fixed_journal_link_two": fixed_journal_link_two,
            "journal_temp_link_two": journal_temp_link_two,
            "receipt_temp_link_two": receipt_temp_link_two,
            "fixed_invalid_journal_link_two":
                fixed_invalid_journal_link_two,
            "journal_temp_invalid_link_two":
                journal_temp_invalid_link_two,
            "receipt_temp_invalid_link_two":
                receipt_temp_invalid_link_two,
            "manifest_temp_multiple_rows":
                _manual_hold_manifest_temp_plan(row_count=2),
            "manifest_temp_invalid":
                _manual_hold_manifest_temp_plan(valid_document=False),
        }
        for label, plan in cases.items():
            self.assertTrue(
                contract.validate_private_metadata_write_plan(plan)[
                    "accepted"
                ],
                label,
            )
            self.assertTrue(
                contract.validate_private_metadata_write_plan_semantics(
                    plan,
                    require_final_size_binding=True,
                )["accepted"],
                label,
            )
            self.assertTrue(
                contract.parse_private_metadata_write_plan_bytes(
                    contract.canonical_json_bytes(plan)
                )["accepted"],
                label,
            )

    def test_manual_hold_mutation_corpus_is_fail_closed(self) -> None:
        corpus: list[tuple[str, dict[str, object]]] = []

        def add(
            label: str,
            plan: dict[str, object],
            mutate: object,
        ) -> None:
            mutate(plan)
            corpus.append((label, plan))

        add(
            "absent_prior_claims_exact",
            _plan_for_action("manual_hold"),
            lambda plan: plan.__setitem__("prior_row_state", "exact"),
        )
        add(
            "absent_prior_has_one_exact_row",
            _plan_for_action("manual_hold"),
            lambda plan: plan.__setitem__("existing_exact_row_count", 1),
        )
        add(
            "absent_receipt_claims_exact_inventory",
            _plan_for_action("manual_hold"),
            lambda plan: plan.__setitem__(
                "receipt_inventory_state",
                "exact",
            ),
        )
        add(
            "absent_receipt_and_journal_carry_planned_digest",
            _plan_for_action("manual_hold"),
            lambda plan: plan.__setitem__(
                "planned_receipt_sha256",
                _digest("9"),
            ),
        )

        exact_prior = _manual_hold_prior_plan(
            "exact",
            manifest_rows=1,
            exact_row_count=1,
        )
        add(
            "exact_prior_count_zero",
            deepcopy(exact_prior),
            lambda plan: plan.__setitem__("existing_exact_row_count", 0),
        )
        add(
            "exact_prior_count_two",
            deepcopy(exact_prior),
            lambda plan: plan.__setitem__("existing_exact_row_count", 2),
        )
        add(
            "count_one_with_collision_state",
            deepcopy(exact_prior),
            lambda plan: plan.__setitem__("prior_row_state", "collision"),
        )
        add(
            "count_one_with_multiple_state",
            deepcopy(exact_prior),
            lambda plan: plan.__setitem__("prior_row_state", "multiple"),
        )

        collision = _manual_hold_prior_plan(
            "collision",
            manifest_rows=1,
            exact_row_count=0,
        )
        add(
            "collision_count_one",
            collision,
            lambda plan: plan.__setitem__("existing_exact_row_count", 1),
        )
        multiple = _manual_hold_prior_plan(
            "multiple",
            manifest_rows=2,
            exact_row_count=0,
        )
        add(
            "multiple_with_only_one_manifest_row",
            multiple,
            lambda plan: (
                plan.__setitem__(
                    "private_manifest_before",
                    _present_file_state("7"),
                ),
                plan.__setitem__(
                    "private_manifest_after",
                    _present_file_state("7"),
                ),
                plan["resource_binding"].__setitem__(
                    "private_manifest_current_bytes",
                    1,
                ),
                plan["resource_binding"].__setitem__(
                    "private_manifest_current_rows",
                    1,
                ),
                plan["resource_binding"].__setitem__(
                    "prospective_private_manifest_bytes",
                    1,
                ),
                plan["resource_binding"].__setitem__(
                    "prospective_private_manifest_rows",
                    1,
                ),
            ),
        )

        exact_receipt = _manual_hold_receipt_plan(
            "exact",
            exact_receipt_count=1,
            valid_receipt=True,
            receipt_count=1,
        )
        add(
            "exact_inventory_count_zero",
            deepcopy(exact_receipt),
            lambda plan: plan.__setitem__("exact_receipt_count", 0),
        )
        add(
            "exact_inventory_count_two",
            deepcopy(exact_receipt),
            lambda plan: plan.__setitem__("exact_receipt_count", 2),
        )
        add(
            "exact_inventory_receipt_absent",
            deepcopy(exact_receipt),
            lambda plan: plan.__setitem__(
                "receipt_state",
                _absent_file_state(),
            ),
        )
        add(
            "exact_receipt_claimed_absent",
            deepcopy(exact_receipt),
            lambda plan: plan.__setitem__(
                "receipt_inventory_state",
                "absent",
            ),
        )
        add(
            "exact_receipt_planned_digest_absent",
            deepcopy(exact_receipt),
            lambda plan: plan.__setitem__(
                "planned_receipt_sha256",
                None,
            ),
        )
        add(
            "exact_receipt_planned_digest_wrong",
            deepcopy(exact_receipt),
            lambda plan: plan.__setitem__(
                "planned_receipt_sha256",
                _digest("f"),
            ),
        )
        add(
            "exact_receipt_global_count_zero",
            deepcopy(exact_receipt),
            lambda plan: plan["resource_binding"].__setitem__(
                "receipt_final_count_current",
                0,
            ),
        )
        add(
            "exact_receipt_total_too_small",
            deepcopy(exact_receipt),
            lambda plan: plan["resource_binding"].__setitem__(
                "receipt_final_total_bytes_current",
                99,
            ),
        )
        add(
            "exact_receipt_directory_count_zero",
            deepcopy(exact_receipt),
            lambda plan: plan[
                "receipt_directory_chain_before"
            ]["private_receipt_directory"].__setitem__("entry_count", 0),
        )

        conflicting = _manual_hold_receipt_plan(
            "conflicting",
            exact_receipt_count=0,
            valid_receipt=False,
            receipt_count=1,
        )
        add(
            "conflicting_receipt_claims_exact_count",
            conflicting,
            lambda plan: plan.__setitem__("exact_receipt_count", 1),
        )
        multiple_receipts = _manual_hold_receipt_plan(
            "multiple",
            exact_receipt_count=2,
            valid_receipt=True,
            receipt_count=2,
        )
        add(
            "multiple_receipt_count_one",
            multiple_receipts,
            lambda plan: plan.__setitem__("exact_receipt_count", 1),
        )
        orphan = _manual_hold_receipt_plan(
            "orphan",
            exact_receipt_count=1,
            valid_receipt=True,
            receipt_count=1,
        )
        add(
            "orphan_receipt_count_zero",
            orphan,
            lambda plan: plan.__setitem__("exact_receipt_count", 0),
        )

        fixed_journal = _manual_hold_journal_plan()
        add(
            "planned_digest_after_fixed_journal_disappears",
            fixed_journal,
            lambda plan: (
                plan.__setitem__("journal_state", _absent_file_state()),
                plan.__setitem__("journal_sha256", None),
            ),
        )
        journal_temp = _manual_hold_journal_plan(use_temp=True)
        add(
            "planned_digest_after_journal_temp_disappears",
            journal_temp,
            lambda plan: plan["owned_temp_states"].__setitem__(
                "journal_temp",
                _absent_file_state(),
            ),
        )

        related_resource_fields = (
            "private_manifest_current_bytes",
            "private_manifest_current_rows",
            "receipt_final_count_current",
            "receipt_final_total_bytes_current",
            "receipt_directory_entries_current",
            "receipt_root_entries_after_bootstrap",
            "receipt_objects_entries_after_bootstrap",
            "manifest_directory_entries_with_both_locks",
            "prospective_private_manifest_bytes",
            "prospective_private_manifest_rows",
            "prospective_receipt_bytes",
            "prospective_receipt_final_count",
            "prospective_receipt_final_total_bytes",
            "prospective_receipt_directory_peak_entries",
            "prospective_manifest_directory_peak_entries",
            "prospective_journal_bytes",
        )
        for field in related_resource_fields:
            add(
                f"manual_resource.{field}",
                _plan_for_action("manual_hold"),
                lambda plan, field=field: plan[
                    "resource_binding"
                ].__setitem__(
                    field,
                    plan["resource_binding"][field] + 1,
                ),
            )

        for label, plan in corpus:
            self.assertTrue(
                contract.validate_private_metadata_write_plan(plan)[
                    "accepted"
                ],
                f"shape unexpectedly rejected {label}",
            )
            self.assertFalse(
                contract.validate_private_metadata_write_plan_semantics(
                    plan,
                    require_final_size_binding=True,
                )["accepted"],
                label,
            )
            self.assertFalse(
                contract.parse_private_metadata_write_plan_bytes(
                    contract.canonical_json_bytes(plan)
                )["accepted"],
                label,
            )

    def test_manual_hold_artifact_observation_mutation_corpus(
        self,
    ) -> None:
        fixed_invalid_journal = _plan_for_action("manual_hold")
        fixed_invalid_journal["journal_state"] = (
            _present_invalid_file_state("a")
        )
        fixed_invalid_journal["journal_sha256"] = (
            fixed_invalid_journal["journal_state"]["sha256"]
        )
        journal_temp_invalid = _plan_for_action("manual_hold")
        journal_temp_invalid["owned_temp_states"]["journal_temp"] = (
            _present_invalid_file_state("a")
        )

        conflicting_present = _manual_hold_receipt_plan(
            "conflicting",
            exact_receipt_count=0,
            valid_receipt=True,
            receipt_count=1,
        )
        fixed_journal_without_planned = _manual_hold_journal_plan()
        fixed_journal_without_planned["planned_receipt_sha256"] = None
        journal_temp_without_planned = _manual_hold_journal_plan(
            use_temp=True
        )
        journal_temp_without_planned["planned_receipt_sha256"] = None
        fixed_journal_before_unavailable = _manual_hold_journal_plan()
        fixed_journal_before_unavailable["planned_receipt_sha256"] = None
        journal_temp_before_unavailable = _manual_hold_journal_plan(
            use_temp=True
        )
        journal_temp_before_unavailable["planned_receipt_sha256"] = None

        corpus = [
            (
                "final_receipt_present_link_three",
                _manual_hold_receipt_plan(
                    "exact",
                    exact_receipt_count=1,
                    valid_receipt=True,
                    receipt_count=1,
                ),
                lambda plan: plan["receipt_state"].__setitem__(
                    "link_count",
                    3,
                ),
            ),
            (
                "fixed_journal_present_link_three",
                _manual_hold_journal_plan(),
                lambda plan: plan["journal_state"].__setitem__(
                    "link_count",
                    3,
                ),
            ),
            (
                "journal_temp_present_link_three",
                _manual_hold_journal_plan(use_temp=True),
                lambda plan: plan["owned_temp_states"][
                    "journal_temp"
                ].__setitem__("link_count", 3),
            ),
            (
                "receipt_temp_present_link_three",
                _manual_hold_receipt_temp_plan(),
                lambda plan: plan["owned_temp_states"][
                    "receipt_temp"
                ].__setitem__("link_count", 3),
            ),
            (
                "manifest_temp_present_link_two",
                _manual_hold_manifest_temp_plan(),
                lambda plan: plan["owned_temp_states"][
                    "manifest_temp"
                ].__setitem__("link_count", 2),
            ),
            (
                "final_receipt_present_invalid_link_three",
                _manual_hold_receipt_plan(
                    "conflicting",
                    exact_receipt_count=0,
                    valid_receipt=False,
                    receipt_count=1,
                ),
                lambda plan: plan["receipt_state"].__setitem__(
                    "link_count",
                    3,
                ),
            ),
            (
                "fixed_journal_present_invalid_link_three",
                fixed_invalid_journal,
                lambda plan: plan["journal_state"].__setitem__(
                    "link_count",
                    3,
                ),
            ),
            (
                "journal_temp_present_invalid_link_three",
                journal_temp_invalid,
                lambda plan: plan["owned_temp_states"][
                    "journal_temp"
                ].__setitem__("link_count", 3),
            ),
            (
                "receipt_temp_present_invalid_link_three",
                _manual_hold_receipt_temp_plan(valid_document=False),
                lambda plan: plan["owned_temp_states"][
                    "receipt_temp"
                ].__setitem__("link_count", 3),
            ),
            (
                "manifest_temp_present_invalid_link_two",
                _manual_hold_manifest_temp_plan(valid_document=False),
                lambda plan: plan["owned_temp_states"][
                    "manifest_temp"
                ].__setitem__("link_count", 2),
            ),
            (
                "exact_receipt_present_row_two",
                _manual_hold_receipt_plan(
                    "exact",
                    exact_receipt_count=1,
                    valid_receipt=True,
                    receipt_count=1,
                ),
                lambda plan: plan["receipt_state"].__setitem__(
                    "row_count",
                    2,
                ),
            ),
            (
                "conflicting_receipt_present_row_two",
                conflicting_present,
                lambda plan: plan["receipt_state"].__setitem__(
                    "row_count",
                    2,
                ),
            ),
            (
                "multiple_receipt_present_row_two",
                _manual_hold_receipt_plan(
                    "multiple",
                    exact_receipt_count=2,
                    valid_receipt=True,
                    receipt_count=2,
                ),
                lambda plan: plan["receipt_state"].__setitem__(
                    "row_count",
                    2,
                ),
            ),
            (
                "orphan_receipt_present_row_two",
                _manual_hold_receipt_plan(
                    "orphan",
                    exact_receipt_count=1,
                    valid_receipt=True,
                    receipt_count=1,
                ),
                lambda plan: plan["receipt_state"].__setitem__(
                    "row_count",
                    2,
                ),
            ),
            (
                "fixed_journal_present_row_two_without_planned",
                fixed_journal_without_planned,
                lambda plan: plan["journal_state"].__setitem__(
                    "row_count",
                    2,
                ),
            ),
            (
                "journal_temp_present_row_two_without_planned",
                journal_temp_without_planned,
                lambda plan: plan["owned_temp_states"][
                    "journal_temp"
                ].__setitem__("row_count", 2),
            ),
            (
                "receipt_temp_present_row_two_without_planned",
                _manual_hold_receipt_temp_plan(),
                lambda plan: plan["owned_temp_states"][
                    "receipt_temp"
                ].__setitem__("row_count", 2),
            ),
            (
                "absent_inventory_final_receipt_unavailable",
                _plan_for_action("manual_hold"),
                lambda plan: plan.__setitem__(
                    "receipt_state",
                    _unavailable_file_state(),
                ),
            ),
            (
                "exact_inventory_final_receipt_unavailable",
                _manual_hold_receipt_plan(
                    "exact",
                    exact_receipt_count=1,
                    valid_receipt=True,
                    receipt_count=1,
                ),
                lambda plan: plan.__setitem__(
                    "receipt_state",
                    _unavailable_file_state(),
                ),
            ),
            (
                "conflicting_receipt_unavailable",
                _manual_hold_receipt_plan(
                    "conflicting",
                    exact_receipt_count=0,
                    valid_receipt=False,
                    receipt_count=1,
                ),
                lambda plan: plan.__setitem__(
                    "receipt_state",
                    _unavailable_file_state(),
                ),
            ),
            (
                "fixed_journal_unavailable",
                fixed_journal_before_unavailable,
                lambda plan: (
                    plan.__setitem__(
                        "journal_state",
                        _unavailable_file_state(),
                    ),
                    plan.__setitem__("journal_sha256", None),
                ),
            ),
            (
                "journal_temp_unavailable",
                journal_temp_before_unavailable,
                lambda plan: plan["owned_temp_states"].__setitem__(
                    "journal_temp",
                    _unavailable_file_state(),
                ),
            ),
            (
                "receipt_temp_unavailable",
                _manual_hold_receipt_temp_plan(),
                lambda plan: plan["owned_temp_states"].__setitem__(
                    "receipt_temp",
                    _unavailable_file_state(),
                ),
            ),
            (
                "manifest_temp_unavailable",
                _manual_hold_manifest_temp_plan(),
                lambda plan: plan["owned_temp_states"].__setitem__(
                    "manifest_temp",
                    _unavailable_file_state(),
                ),
            ),
        ]

        for label, plan, mutate in corpus:
            self.assertTrue(
                contract.validate_private_metadata_write_plan_semantics(
                    plan,
                    require_final_size_binding=True,
                )["accepted"],
                f"baseline unexpectedly rejected {label}",
            )
            self.assertTrue(
                contract.parse_private_metadata_write_plan_bytes(
                    contract.canonical_json_bytes(plan)
                )["accepted"],
                f"stored baseline unexpectedly rejected {label}",
            )
            mutate(plan)
            self.assertTrue(
                contract.validate_private_metadata_write_plan(plan)[
                    "accepted"
                ],
                f"shape unexpectedly rejected {label}",
            )
            self.assertFalse(
                contract.validate_private_metadata_write_plan_semantics(
                    plan,
                    require_final_size_binding=True,
                )["accepted"],
                label,
            )
            self.assertFalse(
                contract.parse_private_metadata_write_plan_bytes(
                    contract.canonical_json_bytes(plan)
                )["accepted"],
                label,
            )

    def test_receipt_and_journal_optional_expected_context_bindings(
        self,
    ) -> None:
        receipt = _receipt()
        journal = _journal()
        exact_context = {
            "expected_archive_id": receipt["archive_id"],
            "expected_intake_sha256": receipt["intake_sha256"],
            "expected_object_manifest_state": deepcopy(
                receipt["object_manifest_state"]
            ),
            "expected_private_manifest_before": deepcopy(
                receipt["private_manifest_before"]
            ),
            "expected_private_manifest_after": deepcopy(
                receipt["private_manifest_after"]
            ),
        }
        self.assertTrue(
            contract.validate_private_metadata_write_receipt_semantics(
                receipt,
                **exact_context,
            )["accepted"]
        )
        self.assertTrue(
            contract.validate_private_metadata_write_journal_semantics(
                journal,
                **exact_context,
            )["accepted"]
        )
        self.assertTrue(
            contract.validate_private_metadata_write_receipt_semantics(
                receipt
            )["accepted"]
        )
        self.assertTrue(
            contract.validate_private_metadata_write_journal_semantics(
                journal
            )["accepted"]
        )

        wrong_object_state = deepcopy(receipt["object_manifest_state"])
        wrong_object_state["sha256"] = _digest("f")
        wrong_before = _present_file_state("f")
        wrong_after = deepcopy(receipt["private_manifest_after"])
        wrong_after["sha256"] = _digest("f")
        mismatches = {
            "expected_archive_id": "archive-2",
            "expected_intake_sha256": _digest("f"),
            "expected_object_manifest_state": wrong_object_state,
            "expected_private_manifest_before": wrong_before,
            "expected_private_manifest_after": wrong_after,
        }
        for key, expected in mismatches.items():
            receipt_result = (
                contract.validate_private_metadata_write_receipt_semantics(
                    receipt,
                    **{key: expected},
                )
            )
            self.assertEqual(
                receipt_result["issue_codes"],
                ["private_metadata_receipt_plan_authority_chain_mismatch"],
                key,
            )
            journal_result = (
                contract.validate_private_metadata_write_journal_semantics(
                    journal,
                    **{key: expected},
                )
            )
            self.assertEqual(
                journal_result["issue_codes"],
                ["private_metadata_journal_cross_field_mismatch"],
                key,
            )

    def test_plan_semantics_reject_action_authority_state_and_resource_mutations(
        self,
    ) -> None:
        def set_forged_authority(plan: dict[str, object]) -> None:
            plan["authority_key_sha256"] = _digest("f")
            plan["receipt_relative_path"] = (
                contract.receipt_relative_path(_digest("f"))
            )

        def set_present_journal(plan: dict[str, object]) -> None:
            journal = _present_file_state("a", byte_count=10)
            plan["journal_state"] = journal
            plan["journal_sha256"] = journal["sha256"]

        def set_manual_chain_validation(plan: dict[str, object]) -> None:
            plan["authority_chain_validation"] = "manual_hold"
            plan["authority_chain_sha256"] = None

        def make_impossible_chain(plan: dict[str, object]) -> None:
            plan["receipt_directory_chain_before"]["objects_parent"] = {
                "state": "present",
                "entry_count": 0,
            }

        mutations = {
            "forged_authority": set_forged_authority,
            "wrong_receipt_path": lambda plan: plan.__setitem__(
                "receipt_relative_path",
                contract.RECEIPT_DIRECTORY + ("f" * 64) + ".json",
            ),
            "wrong_action": lambda plan: plan.__setitem__(
                "action",
                "rollback_required",
            ),
            "wrong_object_match_count": lambda plan: plan.__setitem__(
                "object_manifest_match_count",
                0,
            ),
            "object_hardlink": lambda plan: plan[
                "object_manifest_state"
            ].__setitem__("link_count", 2),
            "after_equals_before": lambda plan: plan.__setitem__(
                "private_manifest_after",
                deepcopy(plan["private_manifest_before"]),
            ),
            "receipt_present": lambda plan: plan.__setitem__(
                "receipt_state",
                _present_file_state("9", byte_count=100),
            ),
            "journal_present": set_present_journal,
            "journal_temp_present": lambda plan: plan[
                "owned_temp_states"
            ].__setitem__(
                "journal_temp",
                _present_file_state("a", byte_count=10),
            ),
            "planned_receipt_present": lambda plan: plan.__setitem__(
                "planned_receipt_sha256",
                _digest("9"),
            ),
            "wrong_prior_row_state": lambda plan: plan.__setitem__(
                "prior_row_state",
                "exact",
            ),
            "wrong_receipt_inventory": lambda plan: plan.__setitem__(
                "receipt_inventory_state",
                "exact",
            ),
            "wrong_authority_scope": lambda plan: plan.__setitem__(
                "authority_chain_scope",
                "prefix_before_interrupted_append",
            ),
            "wrong_authority_validation": set_manual_chain_validation,
            "wrong_exact_row_count": lambda plan: plan.__setitem__(
                "existing_exact_row_count",
                1,
            ),
            "wrong_exact_receipt_count": lambda plan: plan.__setitem__(
                "exact_receipt_count",
                1,
            ),
            "impossible_directory_chain": make_impossible_chain,
            "wrong_directory_projection": lambda plan: plan[
                "receipt_directory_chain_after"
            ]["private_receipt_directory"].__setitem__("entry_count", 1),
        }
        for field in (
            "private_manifest_current_bytes",
            "private_manifest_current_rows",
            "canonical_stored_row_bytes",
            "receipt_final_count_current",
            "receipt_final_total_bytes_current",
            "receipt_directory_entries_current",
            "receipt_root_entries_after_bootstrap",
            "receipt_objects_entries_after_bootstrap",
            "manifest_directory_entries_with_both_locks",
            "prospective_private_manifest_bytes",
            "prospective_private_manifest_rows",
            "prospective_receipt_bytes",
            "prospective_receipt_final_count",
            "prospective_receipt_final_total_bytes",
            "prospective_receipt_directory_peak_entries",
            "prospective_manifest_directory_peak_entries",
            "prospective_journal_bytes",
        ):
            mutations[f"resource.{field}"] = (
                lambda plan, field=field: plan["resource_binding"].__setitem__(
                    field,
                    plan["resource_binding"][field] + 1,
                )
            )

        for label, mutate in mutations.items():
            plan = _plan()
            mutate(plan)
            self.assertTrue(
                contract.validate_private_metadata_write_plan(plan)[
                    "accepted"
                ],
                f"shape unexpectedly rejected {label}",
            )
            self.assertFalse(
                contract.validate_private_metadata_write_plan_semantics(
                    plan,
                    require_final_size_binding=True,
                )["accepted"],
                label,
            )
            self.assertFalse(
                contract.parse_private_metadata_write_plan_bytes(
                    contract.canonical_json_bytes(plan)
                )["accepted"],
                label,
            )

    def test_authority_chain_rederives_key_path_and_manifest_prefix(self) -> None:
        mutations = {}

        def forge_key_and_path(chain: dict[str, object]) -> None:
            entry = chain["entries"][0]
            entry["authority_key_sha256"] = _digest("f")
            entry["receipt_relative_path"] = (
                contract.receipt_relative_path(_digest("f"))
            )

        mutations["forged_authority"] = forge_key_and_path
        mutations["first_before_present"] = lambda chain: chain[
            "entries"
        ][0].__setitem__("manifest_before", _present_file_state("e"))
        mutations["after_row_number_mismatch"] = lambda chain: chain[
            "entries"
        ][0]["manifest_after"].__setitem__("row_count", 2)
        mutations["terminal_manifest_mismatch"] = lambda chain: chain[
            "private_manifest_state"
        ].__setitem__("sha256", _digest("e"))

        for label, mutate in mutations.items():
            chain = _authority_chain()
            mutate(chain)
            self.assertTrue(
                contract.validate_private_metadata_authority_chain(chain)[
                    "accepted"
                ],
                label,
            )
            self.assertFalse(
                contract.validate_private_metadata_authority_chain_semantics(
                    chain
                )["accepted"],
                label,
            )
            self.assertFalse(
                contract.parse_private_metadata_authority_chain_bytes(
                    contract.canonical_json_bytes(chain)
                )["accepted"],
                label,
            )

    def test_receipt_rederives_authority_and_rejects_every_plan_binding_drift(
        self,
    ) -> None:
        def synchronize_forged_authority(
            receipt: dict[str, object],
        ) -> None:
            forged = _digest("f")
            plan = receipt["plan_binding"]
            receipt["authority_key_sha256"] = forged
            plan["authority_key_sha256"] = forged
            plan["receipt_relative_path"] = (
                contract.receipt_relative_path(forged)
            )
            receipt["plan_sha256"] = contract.sha256_digest(
                contract.canonical_json_bytes(plan)
            )

        def mutate_plan_action(receipt: dict[str, object]) -> None:
            plan = receipt["plan_binding"]
            plan["action"] = "manual_hold"
            receipt["plan_sha256"] = contract.sha256_digest(
                contract.canonical_json_bytes(plan)
            )

        def mutate_plan_resource(receipt: dict[str, object]) -> None:
            plan = receipt["plan_binding"]
            plan["resource_binding"]["prospective_journal_bytes"] += 1
            receipt["plan_sha256"] = contract.sha256_digest(
                contract.canonical_json_bytes(plan)
            )

        mutations = {
            "forged_authority": synchronize_forged_authority,
            "archive_id": lambda receipt: receipt.__setitem__(
                "archive_id",
                "archive-2",
            ),
            "object_id": lambda receipt: receipt.__setitem__(
                "object_id",
                _digest("f"),
            ),
            "intake_sha256": lambda receipt: receipt.__setitem__(
                "intake_sha256",
                _digest("f"),
            ),
            "canonical_row_sha256": lambda receipt: receipt.__setitem__(
                "canonical_row_sha256",
                _digest("f"),
            ),
            "observation_evidence_sha256": lambda receipt:
                receipt.__setitem__(
                    "observation_evidence_sha256",
                    _digest("f"),
                ),
            "review_evidence_sha256": lambda receipt: receipt.__setitem__(
                "review_evidence_sha256",
                _digest("f"),
            ),
            "object_manifest_state": lambda receipt: receipt[
                "object_manifest_state"
            ].__setitem__("sha256", _digest("f")),
            "authority_chain_before": lambda receipt: receipt.__setitem__(
                "authority_chain_before_sha256",
                _digest("f"),
            ),
            "private_manifest_before": lambda receipt: receipt.__setitem__(
                "private_manifest_before",
                _present_file_state("f"),
            ),
            "private_manifest_after": lambda receipt: receipt[
                "private_manifest_after"
            ].__setitem__("sha256", _digest("f")),
            "derived_alias_count": lambda receipt: receipt.__setitem__(
                "derived_alias_count",
                0,
            ),
            "nested_action": mutate_plan_action,
            "nested_resource": mutate_plan_resource,
        }
        for label, mutate in mutations.items():
            receipt = _receipt()
            mutate(receipt)
            self.assertTrue(
                contract.validate_private_metadata_write_receipt(receipt)[
                    "accepted"
                ],
                f"shape unexpectedly rejected {label}",
            )
            result = contract.validate_private_metadata_write_receipt_semantics(
                receipt
            )
            self.assertEqual(
                result["issue_codes"],
                ["private_metadata_receipt_plan_authority_chain_mismatch"],
                label,
            )
            parsed = contract.parse_private_metadata_write_receipt_bytes(
                contract.stored_json_bytes(receipt)
            )
            self.assertEqual(
                parsed["issue_codes"],
                ["private_metadata_receipt_plan_authority_chain_mismatch"],
                label,
            )

    def test_journal_cross_field_mutations_keep_one_distinct_reason(
        self,
    ) -> None:
        def synchronize_forged_authority(
            journal: dict[str, object],
        ) -> None:
            forged = _digest("f")
            receipt = journal["receipt_document"]
            plan = receipt["plan_binding"]
            plan["authority_key_sha256"] = forged
            plan["receipt_relative_path"] = (
                contract.receipt_relative_path(forged)
            )
            receipt["authority_key_sha256"] = forged
            receipt["plan_sha256"] = contract.sha256_digest(
                contract.canonical_json_bytes(plan)
            )
            journal["plan_sha256"] = receipt["plan_sha256"]
            journal["authority_key_sha256"] = forged
            journal["receipt_relative_path"] = (
                contract.receipt_relative_path(forged)
            )
            journal["owned_temp_relative_paths"] = (
                contract.owned_temp_relative_paths(forged)
            )
            journal["receipt_sha256"] = contract.sha256_digest(
                contract.stored_json_bytes(receipt)
            )

        mutations = {
            "plan_sha256": lambda journal: journal.__setitem__(
                "plan_sha256",
                _digest("f"),
            ),
            "authority_chain_before": lambda journal: journal.__setitem__(
                "authority_chain_before_sha256",
                _digest("f"),
            ),
            "authority_key": lambda journal: journal.__setitem__(
                "authority_key_sha256",
                _digest("f"),
            ),
            "receipt_path": lambda journal: journal.__setitem__(
                "receipt_relative_path",
                contract.RECEIPT_DIRECTORY + ("f" * 64) + ".json",
            ),
            "receipt_sha256": lambda journal: journal.__setitem__(
                "receipt_sha256",
                _digest("f"),
            ),
            "object_manifest": lambda journal: journal[
                "object_manifest_state"
            ].__setitem__("sha256", _digest("f")),
            "manifest_before": lambda journal: journal.__setitem__(
                "private_manifest_before",
                _present_file_state("f"),
            ),
            "manifest_after": lambda journal: journal[
                "private_manifest_after"
            ].__setitem__("sha256", _digest("f")),
            "journal_temp": lambda journal: journal[
                "owned_temp_relative_paths"
            ].__setitem__(
                0,
                (
                    "objects/manifests/.private-source-metadata-write."
                    + ("f" * 64)
                    + ".journal.tmp"
                ),
            ),
            "manifest_temp": lambda journal: journal[
                "owned_temp_relative_paths"
            ].__setitem__(
                1,
                (
                    "objects/manifests/.private-source-metadata-write."
                    + ("f" * 64)
                    + ".manifest.tmp"
                ),
            ),
            "receipt_temp": lambda journal: journal[
                "owned_temp_relative_paths"
            ].__setitem__(
                2,
                (
                    "receipts/objects/private-source-metadata/."
                    + ("f" * 64)
                    + ".receipt.tmp"
                ),
            ),
            "embedded_receipt": lambda journal: journal[
                "receipt_document"
            ].__setitem__("archive_id", "archive-2"),
            "fully_synchronized_forged_authority":
                synchronize_forged_authority,
        }
        for label, mutate in mutations.items():
            journal = _journal()
            mutate(journal)
            self.assertTrue(
                contract.validate_private_metadata_write_journal(journal)[
                    "accepted"
                ],
                f"shape unexpectedly rejected {label}",
            )
            result = contract.validate_private_metadata_write_journal_semantics(
                journal
            )
            self.assertEqual(
                result["issue_codes"],
                ["private_metadata_journal_cross_field_mismatch"],
                label,
            )
            parsed = contract.parse_private_metadata_write_journal_bytes(
                contract.stored_json_bytes(journal)
            )
            self.assertEqual(
                parsed["issue_codes"],
                ["private_metadata_journal_cross_field_mismatch"],
                label,
            )
class PrivateMetadataWriterPureContractTests(unittest.TestCase):
    def test_strict_intake_parser_rejects_parser_canaries(self) -> None:
        valid = contract.canonical_json_bytes(_intake())
        self.assertTrue(
            contract.parse_private_metadata_intake_bytes(valid)["accepted"]
        )

        duplicate = valid.replace(
            b'"review_status":"human_reviewed"',
            (
                b'"review_status":"human_reviewed",'
                b'"review_status":"human_reviewed"'
            ),
        )
        corpus = (
            b"\xef\xbb\xbf" + valid,
            b"\xff",
            b"{",
            duplicate,
            valid.replace(b'"size_bytes_observed":12', b'"size_bytes_observed":NaN'),
            valid.replace(
                b'"size_bytes_observed":12',
                b'"size_bytes_observed":12345678901234567890',
            ),
            valid.replace(
                b'"original_filename":"example.txt"',
                b'"original_filename":"\\ud800"',
            ),
        )
        for raw in corpus:
            result = contract.parse_private_metadata_intake_bytes(raw)
            self.assertEqual(
                result,
                {
                    "accepted": False,
                    "intake": None,
                    "intake_sha256": None,
                    "issue_codes": ["private_metadata_intake_invalid"],
                },
            )

    def test_intake_byte_bound_is_exact_and_content_free(self) -> None:
        canonical = contract.canonical_json_bytes(_intake())
        at_bound = canonical + (
            b" " * (contract.INTAKE_MAX_BYTES - len(canonical))
        )
        accepted = contract.parse_private_metadata_intake_bytes(at_bound)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(
            accepted["intake_sha256"],
            contract.sha256_digest(at_bound),
        )
        self.assertEqual(
            contract.parse_private_metadata_intake_bytes(at_bound + b" "),
            {
                "accepted": False,
                "intake": None,
                "intake_sha256": None,
                "issue_codes": ["private_metadata_intake_invalid"],
            },
        )

    def test_intake_signed_64_bit_and_media_provenance_boundaries(self) -> None:
        intake = _intake()
        intake["size_bytes_observed"] = contract.MAX_SIGNED_64
        self.assertTrue(
            contract.validate_private_metadata_intake(intake)["accepted"]
        )
        intake["size_bytes_observed"] = contract.MAX_SIGNED_64 + 1
        self.assertFalse(
            contract.validate_private_metadata_intake(intake)["accepted"]
        )

        unknown = _intake()
        unknown["media_observation"] = {"value": None, "basis": "unknown"}
        self.assertTrue(
            contract.validate_private_metadata_intake(unknown)["accepted"]
        )
        unknown["media_observation"]["value"] = "text/plain"
        self.assertFalse(
            contract.validate_private_metadata_intake(unknown)["accepted"]
        )

        record_evidence = _intake()
        record_evidence["source_provenance"]["evidence_kind"] = (
            "source_record_field"
        )
        record_evidence["source_provenance"]["source_record_id"] = "record-1"
        record_evidence["source_provenance"]["source_attachment_id"] = None
        self.assertTrue(
            contract.validate_private_metadata_intake(record_evidence)[
                "accepted"
            ]
        )

    def test_row_builder_has_one_exact_candidate_or_zero_when_blocked(
        self,
    ) -> None:
        literal = contract.build_private_metadata_row(_intake())
        self.assertTrue(literal["accepted"])
        self.assertEqual(
            literal["row"]["label_candidates"],
            [
                {
                    "kind": "original_filename",
                    "value": "example.txt",
                    "privacy_class": "private_archive",
                    "evidence_sha256": _digest("2"),
                    "review_status": "accepted",
                    "review_evidence_sha256": _digest("3"),
                }
            ],
        )
        self.assertEqual(
            literal["canonical_row_sha256"],
            contract.sha256_digest(literal["canonical_json_bytes"]),
        )
        self.assertEqual(
            literal["stored_row_bytes"],
            literal["canonical_json_bytes"] + b"\n",
        )

        encoded = contract.build_private_metadata_row(
            _intake(
                filename="encoded%2Etxt",
                profile="utf8_percent_encoded_component",
                privacy_class="restricted",
            )
        )
        self.assertTrue(encoded["accepted"])
        self.assertEqual(
            encoded["row"]["label_candidates"][0]["kind"],
            "decoded_filename",
        )
        self.assertEqual(
            encoded["row"]["label_candidates"][0]["value"],
            "encoded.txt",
        )
        self.assertEqual(
            encoded["row"]["label_candidates"][0]["privacy_class"],
            "restricted",
        )

        blocked = contract.build_private_metadata_row(
            _intake(filename="folder/name.txt")
        )
        self.assertTrue(blocked["accepted"])
        self.assertEqual(
            blocked["row"]["names"]["derivation_status"],
            "blocked",
        )
        self.assertEqual(blocked["row"]["label_candidates"], [])

    def test_derived_length_overflow_preserves_raw_and_nulls_derivations(
        self,
    ) -> None:
        source = ("\u0344" * 256) + "a"
        result = contract.build_private_metadata_row(
            _intake(filename=source)
        )
        self.assertTrue(result["accepted"])
        names = result["row"]["names"]
        self.assertEqual(
            names["reason_codes"],
            ["derived_name_length_exceeded"],
        )
        self.assertEqual(names["original_filename"], source)
        for field in (
            "decoded_filename",
            "normalized_filename_nfc",
            "normalized_filename_nfd",
            "filename_stem_nfc",
            "extension_ascii_lower",
        ):
            self.assertIsNone(names[field])
        self.assertEqual(result["row"]["label_candidates"], [])

    def test_cjson_stored_json_and_hash_have_pinned_utf8_fixture(
        self,
    ) -> None:
        value = {"\u00e9": "\uac12", "a": [1, True, None]}
        expected_hex = (
            "7b2261223a5b312c747275652c6e756c6c5d2c22c3a9223a22"
            "eab092227d"
        )
        canonical = contract.canonical_json_bytes(value)
        self.assertEqual(canonical.hex(), expected_hex)
        self.assertEqual(
            contract.sha256_digest(canonical),
            (
                "sha256:"
                "4d01307b988a73cc3f3d364b0dd7c7224ab4d822df69984e04df08605d9a506f"
            ),
        )
        self.assertEqual(contract.stored_json_bytes(value), canonical + b"\n")

    def test_authority_key_and_paths_have_pinned_fixture(self) -> None:
        authority_key = contract.authority_key_sha256(_digest("2"))
        self.assertEqual(
            authority_key,
            (
                "sha256:"
                "0ab5cb3539979ed1f930e34c635fcf9e23616c5531b5da13a10a1a955f755ba7"
            ),
        )
        authority_hex = authority_key[7:]
        self.assertEqual(
            contract.receipt_relative_path(authority_key),
            (
                "receipts/objects/private-source-metadata/"
                f"{authority_hex}.json"
            ),
        )
        self.assertEqual(
            contract.owned_temp_relative_paths(authority_key),
            [
                (
                    "objects/manifests/.private-source-metadata-write."
                    f"{authority_hex}.journal.tmp"
                ),
                (
                    "objects/manifests/.private-source-metadata-write."
                    f"{authority_hex}.manifest.tmp"
                ),
                (
                    "receipts/objects/private-source-metadata/."
                    f"{authority_hex}.receipt.tmp"
                ),
            ],
        )

    def test_plan_receipt_journal_parsers_reject_duplicate_and_nonfinite(
        self,
    ) -> None:
        corpus = (
            (
                contract.canonical_json_bytes(_plan()),
                contract.parse_private_metadata_write_plan_bytes,
            ),
            (
                contract.stored_json_bytes(_receipt()),
                contract.parse_private_metadata_write_receipt_bytes,
            ),
            (
                contract.stored_json_bytes(_journal()),
                contract.parse_private_metadata_write_journal_bytes,
            ),
            (
                contract.canonical_json_bytes(_authority_chain()),
                contract.parse_private_metadata_authority_chain_bytes,
            ),
        )
        for valid, parser in corpus:
            self.assertTrue(parser(valid)["accepted"])
            duplicate = valid.replace(
                b'"schema":',
                b'"schema":"duplicate","schema":',
                1,
            )
            self.assertFalse(parser(duplicate)["accepted"])
            self.assertFalse(parser(b"\xef\xbb\xbf" + valid)["accepted"])
            self.assertFalse(parser(valid[:-1] + b"NaN")["accepted"])

    def test_standalone_parsers_require_exact_canonical_storage_bytes(
        self,
    ) -> None:
        plan = _plan()
        receipt = _receipt()
        journal = _journal()
        chain = _authority_chain()
        corpus = (
            (
                contract.parse_private_metadata_write_plan_bytes,
                contract.canonical_json_bytes(plan),
            ),
            (
                contract.parse_private_metadata_write_receipt_bytes,
                contract.stored_json_bytes(receipt),
            ),
            (
                contract.parse_private_metadata_write_journal_bytes,
                contract.stored_json_bytes(journal),
            ),
            (
                contract.parse_private_metadata_authority_chain_bytes,
                contract.canonical_json_bytes(chain),
            ),
        )
        for parser, canonical in corpus:
            self.assertTrue(parser(canonical)["accepted"])
            self.assertFalse(parser(b" " + canonical)["accepted"])
            self.assertFalse(parser(canonical + b"\n")["accepted"])

        self.assertFalse(
            contract.parse_private_metadata_write_receipt_bytes(
                contract.canonical_json_bytes(receipt)
            )["accepted"]
        )
        self.assertFalse(
            contract.parse_private_metadata_write_journal_bytes(
                contract.canonical_json_bytes(journal)
            )["accepted"]
        )

    def test_parser_distinguishes_shape_from_cross_field_refusal(self) -> None:
        malformed_receipt = _receipt()
        del malformed_receipt["schema"]
        self.assertEqual(
            contract.parse_private_metadata_write_receipt_bytes(
                contract.stored_json_bytes(malformed_receipt)
            )["issue_codes"],
            ["private_metadata_write_receipt_invalid"],
        )

        mismatched_receipt = _receipt()
        mismatched_receipt["archive_id"] = "archive-2"
        self.assertEqual(
            contract.parse_private_metadata_write_receipt_bytes(
                contract.stored_json_bytes(mismatched_receipt)
            )["issue_codes"],
            ["private_metadata_receipt_plan_authority_chain_mismatch"],
        )

        malformed_journal = _journal()
        del malformed_journal["schema"]
        self.assertEqual(
            contract.parse_private_metadata_write_journal_bytes(
                contract.stored_json_bytes(malformed_journal)
            )["issue_codes"],
            ["private_metadata_write_journal_invalid"],
        )

        mismatched_journal = _journal()
        mismatched_journal["private_manifest_after"]["sha256"] = _digest("f")
        self.assertEqual(
            contract.parse_private_metadata_write_journal_bytes(
                contract.stored_json_bytes(mismatched_journal)
            )["issue_codes"],
            ["private_metadata_journal_cross_field_mismatch"],
        )

    def test_canonicalizer_rejects_nonfinite_and_surrogate(self) -> None:
        with self.assertRaises(ValueError):
            contract.canonical_json_bytes({"number": float("nan")})
        surrogate = json.loads(r'"\ud800"')
        with self.assertRaises(ValueError):
            contract.canonical_json_bytes({"value": surrogate})


if __name__ == "__main__":
    unittest.main()
