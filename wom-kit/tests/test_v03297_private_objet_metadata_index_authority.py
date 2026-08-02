from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from unittest import mock

import pytest

from wom_kit import archive_services
from wom_kit import private_objet_metadata_index as generated_index
from wom_kit import private_objet_metadata_index_authority as authority
from wom_kit import private_objet_metadata_writer as writer
from wom_kit import private_objet_metadata_writer_contract as contract
from wom_kit.private_objet_metadata_index_authority import (
    EMPTY_SHA256,
    PrivateObjetAuthorityError,
    _inventory_bytes,
    capture_private_objet_index_authority,
)


ARCHIVE_ID = "synthetic-private-index"
OBJECT_HEX = "1" * 64
OBJECT_ID = "sha256:" + OBJECT_HEX
OBSERVATION = "sha256:" + ("3" * 64)


def _intake() -> dict[str, object]:
    return {
        "schema": contract.INTAKE_SCHEMA,
        "object_id": OBJECT_ID,
        "privacy_class": "private_archive",
        "name_observation": {
            "original_filename": "private-canary.hwpx",
            "name_input_profile": "literal_unicode",
        },
        "media_observation": {
            "value": "application/octet-stream",
            "basis": "source_declared",
        },
        "size_bytes_observed": 123,
        "size_bytes_basis": "source_observed",
        "source_provenance": {
            "source_system": "synthetic",
            "source_record_id": None,
            "source_attachment_id": "private-source-canary",
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


def _prepare_archive(root: Path) -> Path:
    root = root.resolve()
    (root / "objects" / "manifests").mkdir(parents=True)
    (root / "private").mkdir()
    (root / "archive.yml").write_text(
        f"archive_id: {ARCHIVE_ID}\n",
        encoding="utf-8",
    )
    object_row = {
        "object_id": OBJECT_ID,
        "sha256": OBJECT_HEX,
        "logical_key": f"objects/sha256/11/{OBJECT_HEX}",
        "locations": [{"provider": "synthetic"}],
        "provenance": {"source": "synthetic"},
    }
    (root / "objects" / "manifests" / "files.jsonl").write_bytes(
        json.dumps(
            object_row,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    return root


def _install_one_valid_observation(
    root: Path,
) -> tuple[dict[str, object], Path, Path]:
    root = _prepare_archive(root)
    intake = _intake()
    intake_bytes = contract.canonical_json_bytes(intake)
    intake_path = root / "private" / "intake.json"
    intake_path.write_bytes(intake_bytes)
    intake_sha256 = "sha256:" + hashlib.sha256(intake_bytes).hexdigest()
    dry_run = archive_services.private_objet_source_metadata_write(
        root,
        intake="private/intake.json",
        expected_intake_sha256=intake_sha256,
        dry_run=True,
        approve=False,
    )
    assert dry_run["action"] == "append"
    row_result = contract.build_private_metadata_row(intake)
    assert row_result["accepted"] is True
    private_path = root.joinpath(
        *PurePosixPath(contract.PRIVATE_MANIFEST_PATH).parts
    )
    private_path.write_bytes(row_result["stored_row_bytes"])
    receipt = writer._receipt_for_append_plan(
        dry_run["plan"],
        reviewed_by="operator:unit-test",
        privacy_class="private_archive",
    )
    receipt_path = root.joinpath(
        *PurePosixPath(dry_run["plan"]["receipt_relative_path"]).parts
    )
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_bytes(contract.stored_json_bytes(receipt))
    return row_result, private_path, receipt_path


def _assert_closed(
    exc: PrivateObjetAuthorityError,
    *,
    validity: str,
) -> None:
    assert exc.validity == validity
    assert exc.code == f"private_objet_metadata_authority_{validity}"
    assert str(exc) == exc.code
    assert exc.__cause__ is None
    assert "\\" not in str(exc)
    assert "/" not in str(exc)


def test_empty_absent_receipt_directory_exact_vector_and_no_object_read(
    tmp_path: Path,
) -> None:
    with mock.patch.object(
        writer,
        "_observe_object_manifest",
        side_effect=AssertionError("zero rows must not read files.jsonl"),
    ):
        capture = capture_private_objet_index_authority(
            tmp_path,
            ARCHIVE_ID,
        )

    assert len(capture.fingerprint_bytes) == 2203
    assert capture.fingerprint_sha256 == (
        "sha256:5f0d6ddd0167c3c368abcf1405370615184dce6346bbf17421841e0d0c735e3e"
    )
    assert capture.compiler_input == {
        "observations": [],
        "private_manifest_state": "absent",
        "private_manifest_sha256": None,
        "private_manifest_bytes": 0,
        "private_manifest_rows": 0,
        "receipt_inventory_state": "absent",
        "receipt_inventory_entries": [],
        "receipt_inventory_sha256": EMPTY_SHA256,
        "receipt_count": 0,
        "object_manifest_state": "not_applicable_zero_private_rows",
        "object_manifest_sha256": None,
        "object_manifest_bytes": 0,
        "object_manifest_rows": 0,
        "writer_journal_state": "absent",
    }
    assert generated_index.build_private_objet_authority_fingerprint(
        capture.compiler_input
    ) == (capture.fingerprint_bytes, capture.fingerprint_sha256)


def test_empty_present_receipt_directory_exact_distinct_vector(
    tmp_path: Path,
) -> None:
    receipt_directory = (
        tmp_path / "receipts" / "objects" / "private-source-metadata"
    )
    receipt_directory.mkdir(parents=True)
    capture = capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)

    assert len(capture.fingerprint_bytes) == 2217
    assert capture.fingerprint_sha256 == (
        "sha256:b32eff237d0b398e5d7e1446077fd353dd457d9bbd91998a0a2770462d4b9108"
    )
    assert capture.receipt_inventory_state == "present_empty"
    assert generated_index.build_private_objet_authority_fingerprint(
        capture.compiler_input
    ) == (capture.fingerprint_bytes, capture.fingerprint_sha256)


@pytest.mark.parametrize("raw", [b"", b" ", b"\n", b"\r\n", b" \n"])
def test_present_empty_or_blank_private_manifest_is_invalid(
    tmp_path: Path,
    raw: bytes,
) -> None:
    manifest = (
        tmp_path
        / "objects"
        / "manifests"
        / "private-source-metadata.jsonl"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(raw)

    with pytest.raises(PrivateObjetAuthorityError) as caught:
        capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(caught.value, validity="invalid")


def test_valid_one_row_capture_is_semantically_bound_and_defensive(
    tmp_path: Path,
) -> None:
    row_result, _, receipt_path = _install_one_valid_observation(tmp_path)
    capture = capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    compiler_input = capture.compiler_input
    observation = compiler_input["observations"][0]

    assert compiler_input["private_manifest_state"] == "present_nonempty"
    assert compiler_input["private_manifest_rows"] == 1
    assert compiler_input["receipt_inventory_state"] == "present_nonempty"
    assert compiler_input["receipt_count"] == 1
    assert compiler_input["object_manifest_state"] == "present"
    assert observation == {
        "manifest_row_ordinal": 1,
        "authority_key_sha256": contract.authority_key_sha256(
            OBSERVATION
        ),
        "canonical_row_sha256": row_result["canonical_row_sha256"],
        "receipt_sha256": (
            "sha256:" + hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        ),
        "source_record": row_result["row"],
    }
    assert generated_index.build_private_objet_authority_fingerprint(
        capture.compiler_input
    ) == (capture.fingerprint_bytes, capture.fingerprint_sha256)
    projection = generated_index.compile_private_objet_index_projection(
        capture.compiler_input
    )
    assert projection.authority_fingerprint_bytes == capture.fingerprint_bytes
    assert (
        projection.authority_fingerprint_sha256
        == capture.fingerprint_sha256
    )
    assert len(projection.observation_rows) == 1
    original_token = capture.comparison_token
    original_fingerprint = capture.fingerprint_sha256
    compiler_input["observations"][0]["source_record"]["privacy_class"] = (
        "restricted"
    )
    compiler_input["receipt_inventory_entries"].clear()
    assert capture.comparison_token == original_token
    assert capture.fingerprint_sha256 == original_fingerprint
    assert capture.compiler_input["receipt_count"] == 1
    assert (
        capture.compiler_input["observations"][0]["source_record"][
            "privacy_class"
        ]
        == "private_archive"
    )
    with pytest.raises(TypeError):
        json.dumps(capture)
    assert not hasattr(capture, "to_public_dict")
    assert "private-canary" not in repr(capture)


def test_missing_receipt_and_orphan_receipt_are_invalid(
    tmp_path: Path,
) -> None:
    _, _, receipt_path = _install_one_valid_observation(tmp_path)
    receipt_path.unlink()
    with pytest.raises(PrivateObjetAuthorityError) as missing:
        capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(missing.value, validity="invalid")

    orphan = receipt_path.parent / (("a" * 64) + ".json")
    orphan.write_bytes(b"{}\n")
    with pytest.raises(PrivateObjetAuthorityError) as orphaned:
        capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(orphaned.value, validity="invalid")


def test_receipt_semantic_mismatch_is_invalid_and_sanitized(
    tmp_path: Path,
) -> None:
    _, _, receipt_path = _install_one_valid_observation(tmp_path)
    receipt = json.loads(receipt_path.read_bytes())
    receipt["archive_id"] = "private-secret-archive-path"
    receipt_path.write_bytes(contract.stored_json_bytes(receipt))

    with pytest.raises(PrivateObjetAuthorityError) as caught:
        capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(caught.value, validity="invalid")
    assert "private-secret" not in str(caught.value)


def test_missing_object_manifest_is_blocked(
    tmp_path: Path,
) -> None:
    _install_one_valid_observation(tmp_path)
    (
        tmp_path / "objects" / "manifests" / "files.jsonl"
    ).unlink()

    with pytest.raises(PrivateObjetAuthorityError) as caught:
        capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(caught.value, validity="blocked")


@pytest.mark.parametrize("duplicate", [False, True])
def test_object_manifest_mismatch_or_duplicate_is_invalid(
    tmp_path: Path,
    duplicate: bool,
) -> None:
    _install_one_valid_observation(tmp_path)
    object_path = tmp_path / "objects" / "manifests" / "files.jsonl"
    object_row = json.loads(object_path.read_bytes())
    if duplicate:
        object_path.write_bytes(
            object_path.read_bytes() + object_path.read_bytes()
        )
    else:
        object_row["sha256"] = "9" * 64
        object_path.write_bytes(
            json.dumps(
                object_row,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )

    with pytest.raises(PrivateObjetAuthorityError) as caught:
        capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(caught.value, validity="invalid")


def test_writer_journal_must_be_exactly_absent(
    tmp_path: Path,
) -> None:
    journal = tmp_path.joinpath(*PurePosixPath(contract.JOURNAL_PATH).parts)
    journal.parent.mkdir(parents=True)
    journal.write_bytes(b"private journal contents must not leak\n")

    with pytest.raises(PrivateObjetAuthorityError) as caught:
        capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(caught.value, validity="invalid")
    assert "journal contents" not in str(caught.value)


def test_nonregular_canonical_receipt_path_is_blocked(
    tmp_path: Path,
) -> None:
    receipt = (
        tmp_path
        / "receipts"
        / "objects"
        / "private-source-metadata"
        / (("a" * 64) + ".json")
    )
    receipt.mkdir(parents=True)

    with pytest.raises(PrivateObjetAuthorityError) as caught:
        capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(caught.value, validity="blocked")


def test_inventory_digest_uses_utf8_path_order_and_exact_framing() -> None:
    entries = [
        ["receipts/\u00e9.json", "sha256:" + ("1" * 64)],
        ["receipts/z.json", "sha256:" + ("2" * 64)],
    ]
    raw = _inventory_bytes(entries)
    assert raw == (
        b'["receipts/z.json","sha256:'
        + (b"2" * 64)
        + b'"]\n["receipts/\\u00e9.json","sha256:'
        + (b"1" * 64)
        + b'"]'
    )
    assert not raw.endswith(b"\n")


def test_same_content_replacement_keeps_fingerprint_but_changes_token(
    tmp_path: Path,
) -> None:
    _, manifest, _ = _install_one_valid_observation(tmp_path)
    first = capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    original = manifest.read_bytes()
    replacement = manifest.with_name("replacement.private.jsonl")
    replacement.write_bytes(original)
    os.replace(replacement, manifest)
    second = capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)

    assert second.fingerprint_bytes == first.fingerprint_bytes
    assert second.fingerprint_sha256 == first.fingerprint_sha256
    assert second.comparison_token != first.comparison_token


def test_repeated_stable_capture_has_same_token(tmp_path: Path) -> None:
    _install_one_valid_observation(tmp_path)
    first = capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    second = capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    assert second.comparison_token == first.comparison_token


def test_internal_snapshot_change_is_blocked_not_private_invalid(
    tmp_path: Path,
) -> None:
    with mock.patch.object(
        authority,
        "_authority_path_tokens",
        side_effect=[
            (("private", ("absent",)),),
            (("private", ("present", 1)),),
        ],
    ):
        with pytest.raises(PrivateObjetAuthorityError) as caught:
            capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(caught.value, validity="blocked")


def test_low_level_failure_text_and_cause_are_not_exposed(
    tmp_path: Path,
) -> None:
    with mock.patch.object(
        authority,
        "_verify_package_pins",
        side_effect=OSError(r"C:\private\secret\pin-source.py"),
    ):
        with pytest.raises(PrivateObjetAuthorityError) as caught:
            capture_private_objet_index_authority(tmp_path, ARCHIVE_ID)
    _assert_closed(caught.value, validity="blocked")
    assert "secret" not in str(caught.value)
