from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from unittest import mock

import pytest

from wom_kit import private_objet_metadata_writer as writer
from wom_kit import private_objet_metadata_writer_contract as contract


OBJECT_ID = "sha256:" + ("1" * 64)
OBSERVATION = "sha256:" + ("3" * 64)


def _intake() -> dict[str, object]:
    return {
        "schema": contract.INTAKE_SCHEMA,
        "object_id": OBJECT_ID,
        "privacy_class": "private_archive",
        "name_observation": {
            "original_filename": "synthetic-authority.txt",
            "name_input_profile": "literal_unicode",
        },
        "media_observation": {
            "value": "text/plain",
            "basis": "source_declared",
        },
        "size_bytes_observed": 1,
        "size_bytes_basis": "source_observed",
        "source_provenance": {
            "source_system": "synthetic",
            "source_record_id": None,
            "source_attachment_id": "synthetic-authority",
            "source_snapshot_sha256": "sha256:" + ("2" * 64),
            "observation_evidence_sha256": OBSERVATION,
            "evidence_kind": "source_attachment_metadata",
            "captured_at": "2026-08-01T00:00:00Z",
        },
        "review_evidence": {
            "review_evidence_sha256": "sha256:" + ("4" * 64),
            "review_status": "human_reviewed",
        },
    }


def test_object_manifest_history_requires_exact_lf_prefix_state() -> None:
    first_hex = "1" * 64
    second_hex = "a" * 64
    rows = [
        {
            "object_id": "sha256:" + first_hex,
            "sha256": first_hex,
            "logical_key": f"objects/sha256/11/{first_hex}",
            "locations": [{"provider": "synthetic"}],
            "provenance": {"source": "first"},
        },
        {
            "object_id": "sha256:" + second_hex,
            "sha256": second_hex,
            "logical_key": f"objects/sha256/aa/{second_hex}",
            "locations": [{"provider": "synthetic"}],
            "provenance": {"source": "second"},
        },
    ]
    stored_rows = [
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
        for row in rows
    ]
    current_raw = b"".join(stored_rows)
    _, prefix_authority = writer._classify_object_manifest(current_raw)
    snapshot = writer._FileSnapshot(
        path=Path("objects/manifests/files.jsonl"),
        raw=current_raw,
        state=writer._present_state(current_raw, 2, 1),
        identity=(7, 1),
    )
    exact_prefix = writer._present_state(stored_rows[0], 1, 1)
    assert writer._object_manifest_state_is_exact_historical_prefix(
        snapshot,
        exact_prefix,
        prefix_authority=prefix_authority,
        object_id=OBJECT_ID,
    )

    wrong_sha = deepcopy(exact_prefix)
    wrong_sha["sha256"] = "sha256:" + ("f" * 64)
    wrong_bytes = deepcopy(exact_prefix)
    wrong_bytes["byte_count"] += 1
    wrong_rows = deepcopy(exact_prefix)
    wrong_rows["row_count"] += 1
    wrong_link = deepcopy(exact_prefix)
    wrong_link["link_count"] = 2
    non_lf_prefix = stored_rows[0] + stored_rows[1][:1]
    non_lf_boundary = writer._present_state(non_lf_prefix, 1, 1)

    for label, state in (
        ("sha256", wrong_sha),
        ("byte_count", wrong_bytes),
        ("row_count", wrong_rows),
        ("link_count", wrong_link),
        ("lf_boundary", non_lf_boundary),
    ):
        assert not writer._object_manifest_state_is_exact_historical_prefix(
            snapshot,
            state,
            prefix_authority=prefix_authority,
            object_id=OBJECT_ID,
        ), label

    duplicate_raw = stored_rows[0] + json.dumps(
        {
            **rows[0],
            "logical_key": f"objects/sha256/11/{first_hex}",
            "provenance": {"source": "later-duplicate"},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    _, duplicate_authority = writer._classify_object_manifest(duplicate_raw)
    duplicate_snapshot = writer._FileSnapshot(
        path=snapshot.path,
        raw=duplicate_raw,
        state=writer._present_state(duplicate_raw, 2, 1),
        identity=(7, 2),
    )
    assert not writer._object_manifest_state_is_exact_historical_prefix(
        duplicate_snapshot,
        writer._object_manifest_historical_state(
            duplicate_authority,
            1,
        ),
        prefix_authority=duplicate_authority,
        object_id=OBJECT_ID,
    )


def test_object_manifest_prefix_authority_work_is_linear_without_mocks() -> None:
    totals: list[int] = []
    for row_total in (32, 64, 128):
        object_ids: list[str] = []
        stored_rows: list[bytes] = []
        for index in range(row_total):
            object_hex = f"{index + 1:064x}"
            object_ids.append("sha256:" + object_hex)
            stored_rows.append(
                json.dumps(
                    {
                        "object_id": object_ids[-1],
                        "sha256": object_hex,
                        "logical_key": (
                            f"objects/sha256/{object_hex[:2]}/{object_hex}"
                        ),
                        "locations": [{"provider": "synthetic"}],
                        "provenance": {"source": "linear-work-proof"},
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        raw = b"".join(stored_rows)
        work = writer._ObjectManifestAuthorityWork()
        count, prefix_authority = writer._classify_object_manifest(
            raw,
            work=work,
        )
        snapshot = writer._FileSnapshot(
            path=Path("objects/manifests/files.jsonl"),
            raw=raw,
            state=writer._present_state(raw, row_total, 1),
            identity=(9, row_total),
        )

        assert count == row_total
        for row_number, object_id in enumerate(object_ids, start=1):
            assert writer._object_manifest_state_is_exact_historical_prefix(
                snapshot,
                writer._object_manifest_historical_state(
                    prefix_authority,
                    row_number,
                ),
                prefix_authority=prefix_authority,
                object_id=object_id,
                work=work,
            )

        assert work.parsed_bytes == len(raw)
        assert work.parsed_rows == row_total
        assert work.prefix_lookups == row_total
        assert work.prefix_lookup_units == row_total
        totals.append(
            work.parsed_bytes
            + work.parsed_rows
            + work.prefix_lookup_units
        )

    assert totals[1] / totals[0] < 2.1
    assert totals[2] / totals[1] < 2.1


def test_bound_snapshot_accepts_only_explicit_two_link_profile() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        parent = root / "objects" / "manifests"
        parent.mkdir(parents=True)
        source = parent / "journal.json"
        twin = parent / "journal.tmp"
        raw = b'{"synthetic":true}\n'
        source.write_bytes(raw)
        os.link(source, twin)

        with pytest.raises(writer._SnapshotError) as captured:
            writer._read_regular_snapshot(
                root,
                source,
                maximum_bytes=1024,
                allow_absent=False,
                classify=lambda _: 1,
            )
        assert captured.value.reason == "unexpected_hardlink"

        snapshot = writer._read_regular_snapshot(
            root,
            source,
            maximum_bytes=1024,
            allow_absent=False,
            classify=lambda _: 1,
            allowed_link_counts=(1, 2),
        )
        twin_snapshot = writer._read_regular_snapshot(
            root,
            twin,
            maximum_bytes=1024,
            allow_absent=False,
            classify=lambda _: 1,
            allowed_link_counts=(1, 2),
        )
        assert snapshot.state["link_count"] == 2
        assert twin_snapshot.state["link_count"] == 2
        assert snapshot.identity == twin_snapshot.identity
        assert snapshot.raw == twin_snapshot.raw == raw


def test_complete_authority_chain_rejects_duplicate_observation_identity() -> None:
    built = contract.build_private_metadata_row(_intake())
    assert built["accepted"] is True
    row = built["row"]
    stored_row = built["stored_row_bytes"]
    assert isinstance(row, dict)
    assert isinstance(stored_row, bytes)

    prefix_chain = {
        "schema": contract.AUTHORITY_CHAIN_SCHEMA,
        "private_manifest_state": writer._absent_state(),
        "entries": [],
    }
    prefix_digest = contract.sha256_digest(
        contract.canonical_json_bytes(prefix_chain)
    )
    after = writer._present_state(stored_row, 1, 1)
    receipt = {
        "authority_chain_before_sha256": prefix_digest,
        "plan_binding": {
            "authority_chain_sha256": prefix_digest,
        },
        "private_manifest_before": writer._absent_state(),
        "private_manifest_after": after,
        "intake_sha256": "sha256:" + ("5" * 64),
        "canonical_row_sha256": contract.sha256_digest(
            contract.canonical_json_bytes(row)
        ),
        "review_evidence_sha256": "sha256:" + ("4" * 64),
    }
    receipt_raw = b'{"synthetic":"receipt"}\n'
    receipt_snapshot = writer._FileSnapshot(
        path=Path("synthetic-receipt.json"),
        raw=receipt_raw,
        state=writer._present_state(receipt_raw, 1, 1),
        identity=(1, 1),
    )

    with (
        mock.patch.object(
            writer,
            "_parse_receipt_at_path",
            return_value=(receipt_snapshot, receipt),
        ) as parse_receipt,
        mock.patch.object(
            contract,
            "validate_private_metadata_authority_chain_semantics",
            return_value={"accepted": True, "issues": []},
        ),
        pytest.raises(writer._SnapshotError) as captured,
    ):
        writer._build_complete_authority_chain(
            Path("."),
            [row, row],
            [stored_row, stored_row],
            private_manifest_state=writer._present_state(
                stored_row + stored_row,
                2,
                1,
            ),
            inventory=[],
        )

    assert captured.value.reason == "duplicate_authority_identity"
    assert parse_receipt.call_count == 1


def test_historical_receipt_rejects_unpaired_two_link_state() -> None:
    built = contract.build_private_metadata_row(_intake())
    assert built["accepted"] is True
    row = built["row"]
    assert isinstance(row, dict)
    authority_key = contract.authority_key_sha256(OBSERVATION)
    relative = contract.receipt_relative_path(authority_key)
    document = {
        "authority_key_sha256": authority_key,
        "observation_evidence_sha256": OBSERVATION,
        "plan_binding": {
            "authority_key_sha256": authority_key,
            "receipt_relative_path": relative,
        },
    }
    raw = b'{"synthetic":"receipt"}\n'
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        expected_path = root.joinpath(*Path(relative).parts)
        expected_path.parent.mkdir(parents=True)
        expected_path.write_bytes(raw)
        snapshot = writer._FileSnapshot(
            path=expected_path,
            raw=raw,
            state=writer._present_state(raw, 1, 2),
            identity=(9, 9),
        )

        with (
            mock.patch.object(
                writer,
                "_observe_receipt",
                return_value=(snapshot, document),
            ),
            mock.patch.object(
                contract,
                "validate_private_metadata_write_receipt_semantics",
                return_value={"accepted": True, "issues": []},
            ),
        ):
            with pytest.raises(writer._SnapshotError) as captured:
                writer._parse_receipt_at_path(root, relative, row)
            assert captured.value.reason == "authority_state_invalid"

            rebound_snapshot, rebound_document = writer._parse_receipt_at_path(
                root,
                relative,
                row,
                allowed_publication_twin_identity=(9, 9),
            )
            assert rebound_snapshot is snapshot
            assert rebound_document is document


def test_object_manifest_requires_one_object_id_before_sha_binding() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        manifests = root / "objects" / "manifests"
        manifests.mkdir(parents=True)
        rows = [
            {
                "object_id": OBJECT_ID,
                "sha256": OBJECT_ID[7:],
                "logical_key": f"objects/sha256/11/{OBJECT_ID[7:]}",
                "locations": [{"provider": "synthetic"}],
                "provenance": {"source": "synthetic"},
            },
            {
                "object_id": OBJECT_ID,
                "sha256": "9" * 64,
                "logical_key": "objects/sha256/99/" + ("9" * 64),
                "locations": [{"provider": "synthetic"}],
                "provenance": {"source": "synthetic"},
            },
        ]
        (manifests / "files.jsonl").write_bytes(
            b"".join(
                contract.canonical_json_bytes(row) + b"\n" for row in rows
            )
        )
        with pytest.raises(writer._SnapshotError) as captured:
            writer._observe_object_manifest(root, OBJECT_ID)
        assert captured.value.reason == "authority_state_invalid"


def test_historical_receipt_binds_opened_path_and_row_derived_key() -> None:
    built = contract.build_private_metadata_row(_intake())
    assert built["accepted"] is True
    row = built["row"]
    assert isinstance(row, dict)
    authority_key = contract.authority_key_sha256(OBSERVATION)
    relative = contract.receipt_relative_path(authority_key)
    wrong_key = "sha256:" + ("9" * 64)
    raw = b'{"synthetic":"receipt"}\n'
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        expected_path = root.joinpath(*Path(relative).parts)
        expected_path.parent.mkdir(parents=True)
        expected_path.write_bytes(raw)
        snapshot = writer._FileSnapshot(
            path=expected_path,
            raw=raw,
            state=writer._present_state(raw, 1, 1),
            identity=(5, 5),
        )
        mismatched = {
            "authority_key_sha256": wrong_key,
            "observation_evidence_sha256": OBSERVATION,
            "plan_binding": {
                "authority_key_sha256": wrong_key,
                "receipt_relative_path": contract.receipt_relative_path(
                    wrong_key
                ),
            },
        }
        with (
            mock.patch.object(
                writer,
                "_observe_receipt",
                return_value=(snapshot, mismatched),
            ),
            mock.patch.object(
                contract,
                "validate_private_metadata_write_receipt_semantics",
                return_value={"accepted": True, "issues": []},
            ),
            pytest.raises(writer._SnapshotError) as captured,
        ):
            writer._parse_receipt_at_path(root, relative, row)
        assert captured.value.reason == "receipt_semantic_mismatch"

        wrong_relative = contract.receipt_relative_path(wrong_key)
        with pytest.raises(writer._SnapshotError) as wrong_path:
            writer._parse_receipt_at_path(root, wrong_relative, row)
        assert wrong_path.value.reason == "receipt_semantic_mismatch"


@pytest.mark.parametrize(
    ("internal_reason", "public_reason"),
    [
        (
            "object_manifest_rows_limit",
            "private_metadata_object_manifest_rows_limit_exceeded",
        ),
        (
            "object_manifest_row_bytes_limit",
            "private_metadata_object_manifest_row_bytes_limit_exceeded",
        ),
        (
            "private_manifest_rows_limit",
            "private_metadata_manifest_rows_limit_exceeded",
        ),
        (
            "private_manifest_row_bytes_limit",
            "private_metadata_manifest_row_bytes_limit_exceeded",
        ),
        (
            "receipt_bytes_limit",
            "private_metadata_receipt_bytes_limit_exceeded",
        ),
        (
            "receipt_count_limit",
            "private_metadata_receipt_count_limit_exceeded",
        ),
        (
            "receipt_total_bytes_limit",
            "private_metadata_receipt_total_bytes_limit_exceeded",
        ),
        (
            "receipt_directory_entries_limit",
            "private_metadata_receipt_directory_entries_limit_exceeded",
        ),
        (
            "receipt_ancestor_directory_entries_limit",
            (
                "private_metadata_receipt_ancestor_directory_entries_"
                "limit_exceeded"
            ),
        ),
        (
            "manifest_directory_entries_limit",
            "private_metadata_manifest_directory_entries_limit_exceeded",
        ),
        (
            "journal_bytes_limit",
            "private_metadata_journal_bytes_limit_exceeded",
        ),
    ],
)
def test_current_bound_reasons_map_without_generic_collapse(
    internal_reason: str,
    public_reason: str,
) -> None:
    assert writer._map_planning_snapshot_error(internal_reason) == (
        "manual_hold",
        public_reason,
    )


def test_manifest_row_bounds_raise_the_exact_internal_reason() -> None:
    object_row = {
        "object_id": OBJECT_ID,
        "sha256": OBJECT_ID[7:],
        "logical_key": f"objects/sha256/11/{OBJECT_ID[7:]}",
        "locations": [{"provider": "synthetic"}],
        "provenance": {"source": "synthetic"},
    }
    object_stored = (
        contract.canonical_json_bytes(object_row) + b"\n"
    )
    with (
        mock.patch.object(writer, "OBJECT_MANIFEST_MAX_ROWS", 0),
        pytest.raises(writer._SnapshotError) as object_rows,
    ):
        writer._classify_object_manifest(object_stored)
    assert object_rows.value.reason == "object_manifest_rows_limit"

    with (
        mock.patch.object(
            writer,
            "OBJECT_MANIFEST_MAX_ROW_BYTES",
            len(object_stored) - 1,
        ),
        pytest.raises(writer._SnapshotError) as object_row_bytes,
    ):
        writer._classify_object_manifest(object_stored)
    assert (
        object_row_bytes.value.reason
        == "object_manifest_row_bytes_limit"
    )

    built = contract.build_private_metadata_row(_intake())
    assert built["accepted"] is True
    private_stored = built["stored_row_bytes"]
    assert isinstance(private_stored, bytes)
    with (
        mock.patch.object(writer, "PRIVATE_MANIFEST_MAX_ROWS", 0),
        pytest.raises(writer._SnapshotError) as private_rows,
    ):
        writer._classify_private_manifest(private_stored)
    assert private_rows.value.reason == "private_manifest_rows_limit"

    with (
        mock.patch.object(
            writer,
            "PRIVATE_MANIFEST_MAX_ROW_BYTES",
            len(private_stored) - 1,
        ),
        pytest.raises(writer._SnapshotError) as private_row_bytes,
    ):
        writer._classify_private_manifest(private_stored)
    assert (
        private_row_bytes.value.reason
        == "private_manifest_row_bytes_limit"
    )


@pytest.mark.parametrize(
    ("constant_name", "constant_value", "expected_reason"),
    [
        ("PRIVATE_RECEIPT_MAX_BYTES", 1, "receipt_bytes_limit"),
        ("PRIVATE_RECEIPT_MAX_COUNT", 0, "receipt_count_limit"),
        (
            "PRIVATE_RECEIPT_TOTAL_BYTES_MAX",
            1,
            "receipt_total_bytes_limit",
        ),
    ],
)
def test_receipt_inventory_stops_at_the_exact_current_bound(
    constant_name: str,
    constant_value: int,
    expected_reason: str,
) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        receipts = (
            root
            / "receipts"
            / "objects"
            / "private-source-metadata"
        )
        receipts.mkdir(parents=True)
        (receipts / (("a" * 64) + ".json")).write_bytes(b"{}\n")
        chain = {
            "private_receipt_directory": {
                "state": "present",
                "entry_count": 1,
            }
        }
        with (
            mock.patch.object(
                writer,
                constant_name,
                constant_value,
            ),
            pytest.raises(writer._SnapshotError) as captured,
        ):
            writer._inventory_receipt_directory(
                root,
                chain,
                allowed_temp_basename="." + ("b" * 64) + ".receipt.tmp",
            )
        assert captured.value.reason == expected_reason


def test_directory_entry_bounds_use_distinct_closed_reasons() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        private = (
            root
            / "receipts"
            / "objects"
            / "private-source-metadata"
        )
        private.mkdir(parents=True)
        (private / "synthetic").write_bytes(b"x")

        with (
            mock.patch.object(
                writer,
                "PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES",
                0,
            ),
            pytest.raises(writer._SnapshotError) as ancestor,
        ):
            writer._observe_receipt_directory_chain(root)
        assert (
            ancestor.value.reason
            == "receipt_ancestor_directory_entries_limit"
        )

        with (
            mock.patch.object(
                writer,
                "PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES",
                10,
            ),
            mock.patch.object(
                writer,
                "PRIVATE_RECEIPT_DIR_MAX_ENTRIES",
                0,
            ),
            pytest.raises(writer._SnapshotError) as receipt_directory,
        ):
            writer._observe_receipt_directory_chain(root)
        assert (
            receipt_directory.value.reason
            == "receipt_directory_entries_limit"
        )

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        manifests = root / "objects" / "manifests"
        manifests.mkdir(parents=True)
        (manifests / "synthetic").write_bytes(b"x")
        with (
            mock.patch.object(
                writer,
                "PRIVATE_MANIFEST_DIR_MAX_ENTRIES",
                0,
            ),
            pytest.raises(writer._SnapshotError) as manifest_directory,
        ):
            writer._validate_persistent_lock_state(root)
        assert (
            manifest_directory.value.reason
            == "manifest_directory_entries_limit"
        )


def test_persistent_actions_require_complete_receipt_chain() -> None:
    complete = {
        key: {"state": "present", "entry_count": 0}
        for key in (
            "receipts_root",
            "objects_parent",
            "private_receipt_directory",
        )
    }
    assert writer._receipt_directory_chain_complete(complete)
    for missing_key in complete:
        chain = deepcopy(complete)
        chain[missing_key] = {"state": "absent", "entry_count": 0}
        assert not writer._receipt_directory_chain_complete(chain)


def test_current_bounds_collect_in_normative_stable_order() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        manifests = root / "objects" / "manifests"
        receipts = (
            root
            / "receipts"
            / "objects"
            / "private-source-metadata"
        )
        manifests.mkdir(parents=True)
        receipts.mkdir(parents=True)
        (manifests / "files.jsonl").write_bytes(b"{}\n")
        (manifests / "private-source-metadata.jsonl").write_bytes(b"{}\n")
        (manifests / ".private-source-metadata-write.journal.json").write_bytes(
            b"xx"
        )
        receipt_name = ("a" * 64) + ".json"
        (receipts / receipt_name).write_bytes(b"xx")
        authority_key = "sha256:" + ("b" * 64)
        temp_paths = contract.owned_temp_relative_paths(authority_key)

        with (
            mock.patch.object(writer, "OBJECT_MANIFEST_MAX_ROWS", 0),
            mock.patch.object(writer, "OBJECT_MANIFEST_MAX_ROW_BYTES", 1),
            mock.patch.object(writer, "PRIVATE_MANIFEST_MAX_ROWS", 0),
            mock.patch.object(writer, "PRIVATE_MANIFEST_MAX_ROW_BYTES", 1),
            mock.patch.object(writer, "PRIVATE_RECEIPT_MAX_BYTES", 1),
            mock.patch.object(writer, "PRIVATE_RECEIPT_MAX_COUNT", 0),
            mock.patch.object(
                writer,
                "PRIVATE_RECEIPT_TOTAL_BYTES_MAX",
                1,
            ),
            mock.patch.object(writer, "PRIVATE_RECEIPT_DIR_MAX_ENTRIES", 0),
            mock.patch.object(
                writer,
                "PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES",
                0,
            ),
            mock.patch.object(
                writer,
                "PRIVATE_MANIFEST_DIR_MAX_ENTRIES",
                0,
            ),
            mock.patch.object(writer, "PRIVATE_JOURNAL_MAX_BYTES", 1),
        ):
            reasons = writer._collect_current_bound_reasons(
                root,
                receipt_relative_path=contract.receipt_relative_path(
                    authority_key
                ),
                owned_temp_relative_paths=temp_paths,
            )
        assert writer._current_bound_public_reasons(reasons) == [
            "private_metadata_object_manifest_rows_limit_exceeded",
            "private_metadata_object_manifest_row_bytes_limit_exceeded",
            "private_metadata_manifest_rows_limit_exceeded",
            "private_metadata_manifest_row_bytes_limit_exceeded",
            "private_metadata_receipt_bytes_limit_exceeded",
            "private_metadata_receipt_count_limit_exceeded",
            "private_metadata_receipt_total_bytes_limit_exceeded",
            "private_metadata_receipt_directory_entries_limit_exceeded",
            (
                "private_metadata_receipt_ancestor_directory_entries_"
                "limit_exceeded"
            ),
            "private_metadata_manifest_directory_entries_limit_exceeded",
            "private_metadata_journal_bytes_limit_exceeded",
        ]


def test_authority_chain_streams_prefix_digests_and_captures_one_receipt() -> None:
    rows: list[dict[str, object]] = []
    stored_rows: list[bytes] = []
    receipts: list[tuple[writer._FileSnapshot, dict[str, object]]] = []
    entries: list[dict[str, object]] = []
    manifest_raw = b""
    for index in range(1, 65):
        intake = deepcopy(_intake())
        observation = "sha256:" + f"{index:064x}"
        intake["source_provenance"]["observation_evidence_sha256"] = (
            observation
        )
        built = contract.build_private_metadata_row(intake)
        assert built["accepted"] is True
        row = built["row"]
        stored = built["stored_row_bytes"]
        assert isinstance(row, dict)
        assert isinstance(stored, bytes)
        rows.append(row)
        stored_rows.append(stored)
        before = (
            writer._absent_state()
            if not manifest_raw
            else writer._present_state(manifest_raw, index - 1, 1)
        )
        prefix_chain = {
            "schema": contract.AUTHORITY_CHAIN_SCHEMA,
            "private_manifest_state": before,
            "entries": deepcopy(entries),
        }
        prefix_digest = contract.sha256_digest(
            contract.canonical_json_bytes(prefix_chain)
        )
        manifest_raw += stored
        after = writer._present_state(manifest_raw, index, 1)
        authority_key = contract.authority_key_sha256(observation)
        relative = contract.receipt_relative_path(authority_key)
        receipt = {
            "authority_chain_before_sha256": prefix_digest,
            "plan_binding": {
                "authority_chain_sha256": prefix_digest,
            },
            "private_manifest_before": before,
            "private_manifest_after": after,
            "intake_sha256": "sha256:" + f"{index + 1000:064x}",
            "canonical_row_sha256": built["canonical_row_sha256"],
            "review_evidence_sha256": intake["review_evidence"][
                "review_evidence_sha256"
            ],
        }
        receipt_raw = json.dumps(index).encode("ascii") + b"\n"
        snapshot = writer._FileSnapshot(
            path=Path(relative),
            raw=receipt_raw,
            state=writer._present_state(receipt_raw, 1, 1),
            identity=(1, index),
        )
        receipts.append((snapshot, receipt))
        entries.append(
            {
                "row_number": index,
                "intake_sha256": receipt["intake_sha256"],
                "canonical_row_sha256": receipt["canonical_row_sha256"],
                "observation_evidence_sha256": observation,
                "review_evidence_sha256": receipt[
                    "review_evidence_sha256"
                ],
                "authority_key_sha256": authority_key,
                "receipt_relative_path": relative,
                "receipt_sha256": snapshot.state["sha256"],
                "manifest_before": before,
                "manifest_after": after,
            }
        )

    inventory = [
        (Path(entry["receipt_relative_path"]).name, 1) for entry in entries
    ]
    capture_relative = entries[31]["receipt_relative_path"]
    with (
        mock.patch.object(
            writer,
            "_parse_receipt_at_path",
            side_effect=receipts,
        ),
        mock.patch.object(
            contract,
            "validate_private_metadata_authority_chain_semantics",
            return_value={"accepted": True, "issues": []},
        ),
        mock.patch.object(
            writer,
            "deepcopy",
            side_effect=AssertionError("quadratic prefix copy"),
        ),
    ):
        chain, digest, captured = writer._build_complete_authority_chain(
            Path("."),
            rows,
            stored_rows,
            private_manifest_state=writer._present_state(
                manifest_raw,
                len(rows),
                1,
            ),
            inventory=inventory,
            capture_receipt_relative=capture_relative,
        )
    assert digest == contract.sha256_digest(
        contract.canonical_json_bytes(chain)
    )
    assert list(captured) == [capture_relative]
    assert len(chain["entries"]) == len(rows)
