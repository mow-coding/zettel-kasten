from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import sqlite3
from unittest import mock

from jsonschema import Draft202012Validator
import pytest

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import private_objet_finder as finder
from wom_kit import private_objet_metadata_index as generated_index
from wom_kit import private_objet_metadata_index_health as private_health
from wom_kit import private_objet_metadata_index_session as private_session
from wom_kit import private_objet_metadata_writer as writer
from wom_kit import private_objet_metadata_writer_contract as contract
from wom_kit.private_objet_metadata_index_authority import (
    capture_private_objet_index_authority,
)


ARCHIVE_ID = "synthetic-private-finder"
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


def _prepare_archive(root: Path, *, nonempty: bool) -> Path:
    root = root.resolve()
    (root / "objects" / "manifests").mkdir(parents=True)
    (root / "private").mkdir()
    (root / "archive.yml").write_text(
        f"archive_id: {ARCHIVE_ID}\n",
        encoding="utf-8",
    )
    if nonempty:
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


def _install_private_authority(root: Path) -> None:
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
    row_result = contract.build_private_metadata_row(intake)
    assert dry_run["action"] == "append"
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


def _install_projection(root: Path, *, nonempty: bool) -> Path:
    root = _prepare_archive(root, nonempty=nonempty)
    if nonempty:
        _install_private_authority(root)
    authority = capture_private_objet_index_authority(root, ARCHIVE_ID)
    projection = generated_index.compile_private_objet_index_projection(
        authority.compiler_input
    )
    db_path = root / "db" / "archive-index.sqlite"
    db_path.parent.mkdir()
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        generated_index.install_private_objet_index_projection(
            connection,
            projection,
        )
        connection.commit()
    finally:
        connection.close()
    return root


def _snapshot_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _finder_argv(
    root: Path,
    query: str,
    *,
    profile: str = "literal_unicode",
    output_format: str = "json",
) -> list[str]:
    return [
        "find-objet",
        str(root),
        "--audience",
        "private_archive",
        "--query-profile",
        profile,
        "--query",
        query,
        "--format",
        output_format,
    ]


def test_request_and_result_schemas_are_draft_2020_12() -> None:
    schema_root = Path(__file__).parents[1] / "schemas"
    request_schema = json.loads(
        (
            schema_root
            / "private-objet-finder-request-v0.1.schema.json"
        ).read_text(encoding="utf-8")
    )
    result_schema = json.loads(
        (
            schema_root
            / "private-objet-finder-result-v0.1.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(request_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(request_schema).validate(
        {
            "schema": finder.REQUEST_SCHEMA_ID,
            "archive_root": "C:/archive",
            "audience": "private_archive",
            "query_profile": "literal_unicode",
            "query_transport": "argv",
            "query": "private-canary.hwpx",
            "limit": 20,
            "format": "json",
        }
    )
    fallback = json.loads(finder.FALLBACK_JSON_LITERAL)
    Draft202012Validator(result_schema).validate(fallback)
    assert finder.validate_private_objet_finder_result(fallback) is True


def test_request_shape_blockers_follow_the_closed_order() -> None:
    request = {
        "schema": finder.REQUEST_SCHEMA_ID,
        "archive_root": "C:/archive",
        "audience": "private_archive",
        "query_profile": "literal_unicode",
        "query_transport": "argv",
        "query": "x",
        "limit": 20,
        "format": "json",
    }
    unsupported = dict(request, schema="unsupported", extra=False)
    invalid = dict(request, limit="20", extra=False)
    extra = dict(request, extra=False)
    missing = dict(request)
    del missing["query"]
    assert finder.validate_private_objet_finder_request(unsupported) == (
        "find_objet_request_schema_unsupported"
    )
    assert finder.validate_private_objet_finder_request(invalid) == (
        "find_objet_request_type_invalid"
    )
    assert finder.validate_private_objet_finder_request(extra) == (
        "find_objet_request_extra_property"
    )
    assert finder.validate_private_objet_finder_request(missing) == (
        "find_objet_request_type_invalid"
    )


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        ([], "find_objet_archive_root_missing"),
        (["root", "extra"], "find_objet_archive_root_extra"),
        (["root", "--unknown"], "find_objet_unknown_option"),
        (
            ["root", "--audience"],
            "find_objet_option_value_missing",
        ),
        (
            [
                "root",
                "--audience",
                "private_archive",
                "--query-profile",
                "literal_unicode",
            ],
            "find_objet_query_transport_missing",
        ),
    ],
)
def test_private_safe_scanner_has_deterministic_blockers(
    tokens: list[str],
    expected: str,
) -> None:
    parsed = finder._scan_invocation(tokens)
    assert parsed.first_failure == expected


def test_argv_query_is_never_reflected_on_failure(capsys: pytest.CaptureFixture[str]) -> None:
    secret = "DO-NOT-REFLECT-PRIVATE-QUERY"
    rc = archive_cli.main(
        [
            "find-objet",
            "root",
            "--query",
            secret,
            "--query-profile",
            "literal_unicode",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert rc == 2
    assert captured.err == ""
    assert secret not in captured.out
    assert result["diagnostic_codes"] == [
        "find_objet_audience_missing"
    ]
    assert result["privacy"]["argv_query_exposure_possible"] is True


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["root", "--query", "one"], True),
        (
            ["root", "--query", "one", "--query", "two"],
            False,
        ),
        (
            ["root", "--query", "one", "--query"],
            False,
        ),
        (
            ["root", "--query", "one", "--query-stdin"],
            False,
        ),
        (["root", "--query-stdin"], False),
        (["root"], False),
    ],
)
def test_early_request_query_present_truth_table(
    tokens: list[str],
    expected: bool,
) -> None:
    parsed = finder._scan_invocation(tokens)
    assert finder._query_present_for_early_failure(parsed) is expected


def test_help_reads_no_stdin_archive_or_sqlite(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        mock.patch.object(
            finder,
            "_read_stdin_payload",
            side_effect=AssertionError("help must not read stdin"),
        ),
        mock.patch.object(
            finder,
            "_derive_archive_boundary",
            side_effect=AssertionError("help must not inspect archive"),
        ),
    ):
        rc = archive_cli.main(["find-objet", "--query-stdin", "--help"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert captured.out == finder.HELP_TEXT + "\n"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"value\n", None),
        (b"value\r\n", None),
        (b"value", None),
        (b"\xef\xbb\xbfvalue\n", "find_objet_query_stdin_bom_forbidden"),
        (b"first\nsecond\n", "find_objet_query_stdin_second_line_forbidden"),
        (
            b"x" * 6145,
            "find_objet_query_raw_utf8_limit_exceeded",
        ),
    ],
)
def test_stdin_bounded_line_contract(
    raw: bytes,
    expected: str | None,
) -> None:
    _query, failures, present = finder._read_stdin_payload(io.BytesIO(raw))
    assert present is True
    assert (
        finder._first_request_blocker(failures)
        if failures
        else None
    ) == expected


def test_query_profiles_reuse_the_pinned_normalizer() -> None:
    literal, literal_error = finder._query_plan(
        "private-canary.hwpx",
        "literal_unicode",
    )
    encoded, encoded_error = finder._query_plan(
        "private%2Dcanary.hwpx",
        "utf8_percent_encoded_component",
    )
    assert literal_error is None
    assert encoded_error is None
    assert literal is not None
    assert encoded is not None
    assert literal.values == encoded.values
    assert finder._query_plan(
        "private%252Dcanary.hwpx",
        "utf8_percent_encoded_component",
    )[1] == "find_objet_query_residual_percent_triplet"


def test_current_nonempty_index_found_and_read_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _install_projection(tmp_path, nonempty=True)
    before = _snapshot_files(root)
    rc = archive_cli.main(_finder_argv(root, "private-canary.hwpx"))
    captured = capsys.readouterr()
    after = _snapshot_files(root)
    result = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert before == after
    assert result["status"] == "found"
    assert result["private_health_case"] == "C11"
    assert result["distinct_object_count"] == 1
    assert result["results"][0]["object_id"] == OBJECT_ID
    assert result["results"][0]["safe_label"]["selected_label"] == (
        "private-canary.hwpx"
    )
    assert result["results"][0]["matched_alias_count"] >= 1
    assert result["privacy"] == {
        "wom_request_value_reflected": False,
        "wom_request_value_stored": False,
        "stored_private_projection_exposed": True,
        "source_identifier_exposed": False,
        "local_path_exposed": False,
        "provider_locator_exposed": False,
        "secret_value_exposed": False,
        "argv_query_exposure_possible": True,
    }
    assert finder.validate_private_objet_finder_result(result) is True


def test_current_empty_index_is_complete_scoped_negative(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _install_projection(tmp_path, nonempty=False)
    rc = archive_cli.main(_finder_argv(root, "absent.hwpx"))
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert result["status"] == "not_found_in_index"
    assert result["private_health_case"] == "C10"
    assert result["diagnostic_codes"] == [
        "find_objet_exact_match_not_found"
    ]
    assert result["warnings"] == [
        "find_objet_argv_query_exposure_possible",
        "find_objet_negative_scope_limited",
    ]
    assert finder.validate_private_objet_finder_result(result) is True


def test_missing_database_is_search_incomplete(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _prepare_archive(tmp_path, nonempty=False)
    (root / "db").mkdir()
    rc = archive_cli.main(_finder_argv(root, "absent.hwpx"))
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert rc == 1
    assert captured.err == ""
    assert result["status"] == "search_incomplete"
    assert result["private_health_case"] == "C5"
    assert result["diagnostic_codes"] == [
        "find_objet_private_index_database_absent"
    ]
    assert finder.validate_private_objet_finder_result(result) is True


@pytest.mark.parametrize(
    ("phase", "completed", "checked_layers"),
    [
        ("before_consumer", False, finder.LAYERS[:4]),
        ("private_alias_index", False, finder.LAYERS[:5]),
        ("private_label_projection", False, finder.LAYERS),
        ("private_alias_index", True, finder.LAYERS),
    ],
)
def test_c7_consumer_phase_has_exact_closed_layer_array(
    phase: str,
    completed: bool,
    checked_layers: tuple[str, ...],
) -> None:
    envelope = private_session.build_private_objet_metadata_health_envelope(
        "C7"
    )
    decision = private_health._decision("C7", envelope)
    result = finder._semantic_result(
        decision,
        None,
        consumer_phase=phase,
        consumer_completed=completed,
        observed_case="C7",
        limit=20,
        argv_exposure_possible=False,
    )
    assert result["checked_layers"] == list(checked_layers)
    assert finder.validate_private_objet_finder_result(result) is True


def test_boundary_failure_is_closed_and_private(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "private-root-name-must-not-leak"
    rc = archive_cli.main(_finder_argv(missing, "private-query"))
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert rc == 2
    assert captured.err == ""
    assert "private-root-name-must-not-leak" not in captured.out
    assert "private-query" not in captured.out
    assert result["diagnostic_codes"] == [
        "find_objet_archive_boundary_unsafe"
    ]


def test_result_validator_is_total_and_rejects_cross_branch_mutations() -> None:
    fallback = json.loads(finder.FALLBACK_JSON_LITERAL)
    for value in (None, True, 1, "x", [], {"x": 1}):
        assert finder.validate_private_objet_finder_result(value) is False
    for key, replacement in (
        ("status", "found"),
        ("ok", True),
        ("returned", 1),
        ("checked_layers", []),
        ("diagnostic_codes", []),
        ("blockers", []),
    ):
        mutated = copy.deepcopy(fallback)
        mutated[key] = replacement
        assert finder.validate_private_objet_finder_result(mutated) is False
    extra = copy.deepcopy(fallback)
    extra["extra"] = False
    assert finder.validate_private_objet_finder_result(extra) is False
    nested_extra = copy.deepcopy(fallback)
    nested_extra["privacy"]["extra"] = False
    assert finder.validate_private_objet_finder_result(nested_extra) is False


def test_fixed_serialization_fallback_is_single_stdout_literal() -> None:
    delivered: list[str] = []
    with (
        mock.patch.object(
            finder,
            "validate_private_objet_finder_result",
            return_value=False,
        ),
        mock.patch.object(
            finder,
            "_deliver_literal",
            side_effect=lambda value: delivered.append(value) or True,
        ),
    ):
        rc = finder._deliver_result({"unsafe": "private"}, "json")
    assert rc == 2
    assert delivered == [finder.FALLBACK_JSON_LITERAL]
    assert '"unsafe"' not in delivered[0]
