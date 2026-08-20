from __future__ import annotations

import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import pytest
from jsonschema import Draft202012Validator

from wom_kit import archive_cli, archive_services, saved_view_workflows


PRIVATE_NAME = "Canary Private View Name"
PRIVATE_VALUE = "canary-private-domain"
KIT_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_ROOT = KIT_ROOT / "schemas"
PERSONAL_TEMPLATE_ROOT = KIT_ROOT / "templates" / "personal"
ZETTEL_KASTEN_TEMPLATE_ROOT = KIT_ROOT / "zettel-kasten"


def _archive(root: Path) -> Path:
    """Build a bounded historical archive fixture from checked-in templates."""

    shutil.copytree(PERSONAL_TEMPLATE_ROOT, root)
    shutil.copytree(
        ZETTEL_KASTEN_TEMPLATE_ROOT,
        root / "zettel-kasten",
    )
    (root / "views").mkdir(exist_ok=True)
    (root / "zettels").mkdir(exist_ok=True)
    frontmatter = {
        "id": "zet_20260807_saved_view",
        "title": "Private title that must never echo",
        "status": "canonical",
        "kind": "note",
        "facets": {"domain": PRIVATE_VALUE, "record_type": "memory"},
    }
    (root / "zettels" / "zet_20260807_saved_view.md").write_text(
        "---\n"
        + archive_services.dump_yaml(frontmatter)
        + "---\n\nPrivate body that must never echo.\n",
        encoding="utf-8",
    )
    indexed = archive_services.index_archive(root)
    assert indexed["ok"] is True
    return root


def _request(root: Path, *, view_id: str = "view.ai.private-canary") -> str:
    relative = ".wom-scratch/private/saved-views/canary.json"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": saved_view_workflows.SAVED_VIEW_WRITE_REQUEST_SCHEMA,
                "view_id": view_id,
                "name": PRIVATE_NAME,
                "filters": {"facets.domain": PRIVATE_VALUE},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return relative


def _create(root: Path, request: str) -> tuple[dict[str, object], dict[str, object]]:
    """Install one bounded pre-v0.4 write receipt without invoking a writer."""

    plan, private = saved_view_workflows._write_plan_core(root, request)
    assert plan["ok"] is True
    target_path = archive_services.archive_internal_path(
        root, private["paths"]["target"]
    )
    archive_services._write_bytes_create_if_absent(target_path, private["view_bytes"])
    saved_view_workflows._write_receipt(
        private,
        reviewer="person:historical-unit-test",
        plan_sha256=plan["summary"]["plan_sha256"],
        action="create",
    )
    result = {
        "ok": True,
        "state": "historical_created",
        "files_written": [private["paths"]["target"], private["paths"]["receipt"]],
    }
    return plan, result


def _revert_private(root: Path, receipt: str) -> tuple[dict[str, object], dict[str, object]]:
    plan, private = saved_view_workflows._revert_plan_core(root, receipt)
    assert plan["ok"] is True
    return plan, private


def _write_historical_revert_journal(private: dict[str, object]) -> None:
    journal = {
        "schema": saved_view_workflows.SAVED_VIEW_REVERT_JOURNAL_SCHEMA,
        "archive_id": private["archive_id"],
        "source_receipt_path": private["source_receipt"],
        "source_receipt_sha256": private["source_receipt_sha256"],
        "target_path": private["target_relative"],
        "view_sha256": private["view_sha256"],
        "revert_receipt_path": private["revert_receipt_relative"],
        "created_at": "2026-08-19T00:00:00+00:00",
    }
    archive_services._write_bytes_create_if_absent(
        private["journal_path"],
        saved_view_workflows._canonical_json_bytes(journal),
    )


def _write_historical_revert_receipt(
    private: dict[str, object],
    *,
    plan_sha256: str,
) -> None:
    receipt = {
        "schema": saved_view_workflows.SAVED_VIEW_REVERT_RECEIPT_SCHEMA,
        "lifecycle_action": "saved_view_revert",
        "archive_id": private["archive_id"],
        "source_receipt_path": private["source_receipt"],
        "source_receipt_sha256": private["source_receipt_sha256"],
        "target_path": private["target_relative"],
        "view_sha256": private["view_sha256"],
        "revert_plan_sha256": plan_sha256,
        "reviewed_by": "person:historical-unit-test",
        "created_at": "2026-08-19T00:00:00+00:00",
    }
    archive_services._write_bytes_create_if_absent(
        private["revert_receipt_path"],
        saved_view_workflows._canonical_json_bytes(receipt),
    )


def _run_cli(args: list[str]) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        code = archive_cli.main(args)
    return code, output.getvalue()


def test_write_is_digest_bound_private_and_idempotent(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    before = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}

    plan = saved_view_workflows.saved_view_write_plan(root, request_path=request)

    assert plan["state"] == "create"
    assert plan["summary"]["matching_zettel_count"] == 1
    assert plan["privacy_guards"]["writes"] is False
    assert {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} == before
    assert PRIVATE_NAME not in json.dumps(plan)
    assert PRIVATE_VALUE not in json.dumps(plan)

    result = saved_view_workflows.saved_view_write(
        root,
        request_path=request,
        expected_plan_sha256=plan["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
        affirm_view_reviewed=True,
    )

    assert result["state"] == "blocked"
    assert result["blockers"] == ["compound_exact_human_approval_binding_required"]
    assert result["files_written"] == []

    _historical_plan, historical = _create(root, request)
    target, receipt = historical["files_written"]
    target_text = (root / target).read_text(encoding="utf-8")
    receipt_text = (root / receipt).read_text(encoding="utf-8")
    assert PRIVATE_NAME in target_text
    assert PRIVATE_VALUE in target_text
    assert PRIVATE_NAME not in receipt_text
    assert PRIVATE_VALUE not in receipt_text
    assert PRIVATE_NAME not in json.dumps(result)
    assert PRIVATE_VALUE not in json.dumps(result)

    replay = saved_view_workflows.saved_view_write(
        root,
        request_path=request,
        expected_plan_sha256=plan["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
        affirm_view_reviewed=True,
    )
    assert replay["ok"] is False
    assert replay["state"] == "blocked"
    assert saved_view_workflows.saved_view_write_plan(
        root, request_path=request
    )["state"] == "already_recorded"


def test_write_requires_review_and_fresh_exact_plan(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    plan = saved_view_workflows.saved_view_write_plan(root, request_path=request)
    target = root / plan["summary"]["target_path"]

    missing_review = saved_view_workflows.saved_view_write(
        root,
        request_path=request,
        expected_plan_sha256=plan["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
        affirm_view_reviewed=False,
    )
    assert missing_review["ok"] is False
    assert missing_review["blockers"] == [
        "compound_exact_human_approval_binding_required"
    ]
    assert not target.exists()

    (root / "views" / "concurrent.yml").write_text(
        archive_services.dump_yaml(
            {
                "id": "view.human.concurrent",
                "name": "Concurrent",
                "filters": {"facets.record_type": "memory"},
            }
        ),
        encoding="utf-8",
    )
    stale = saved_view_workflows.saved_view_write(
        root,
        request_path=request,
        expected_plan_sha256=plan["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
        affirm_view_reviewed=True,
    )
    assert stale["ok"] is False
    assert stale["blockers"] == ["compound_exact_human_approval_binding_required"]
    refreshed = saved_view_workflows.saved_view_write_plan(
        root, request_path=request
    )
    assert refreshed["summary"]["plan_sha256"] != plan["summary"]["plan_sha256"]
    assert not target.exists()


def test_missing_receipt_finalization_requires_a_new_review(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    plan = saved_view_workflows.saved_view_write_plan(root, request_path=request)

    _public, private = saved_view_workflows._write_plan_core(root, request)
    target_path = archive_services.archive_internal_path(
        root, private["paths"]["target"]
    )
    archive_services._write_bytes_create_if_absent(target_path, private["view_bytes"])

    recovery = saved_view_workflows.saved_view_write_plan(root, request_path=request)
    assert recovery["state"] == "finalize_receipt"
    assert recovery["summary"]["plan_sha256"] != plan["summary"]["plan_sha256"]
    finalized = saved_view_workflows.saved_view_write(
        root,
        request_path=request,
        expected_plan_sha256=recovery["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
        affirm_view_reviewed=True,
    )
    assert finalized["state"] == "blocked"
    assert finalized["blockers"] == ["compound_exact_human_approval_binding_required"]
    assert not (root / private["paths"]["receipt"]).exists()


def test_exact_revert_records_evidence_and_refuses_changed_target(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    _plan, created = _create(root, request)
    target, receipt = created["files_written"]

    revert_plan = saved_view_workflows.saved_view_revert_plan(
        root,
        receipt_path=receipt,
    )
    assert revert_plan["ok"] is True
    assert revert_plan["state"] == "revert"
    assert PRIVATE_NAME not in json.dumps(revert_plan)
    assert PRIVATE_VALUE not in json.dumps(revert_plan)

    (root / target).write_text("changed by a human\n", encoding="utf-8")
    blocked = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    assert blocked["ok"] is False
    assert "saved_view_revert_target_changed" in blocked["blockers"]
    assert (root / target).exists()


def test_exact_revert_round_trip_is_idempotent(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    _plan, created = _create(root, request)
    target, receipt = created["files_written"]
    plan = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)

    result = saved_view_workflows.saved_view_revert(
        root,
        receipt_path=receipt,
        expected_plan_sha256=plan["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
    )

    assert result["state"] == "blocked"
    assert result["blockers"] == ["compound_exact_human_approval_binding_required"]
    assert (root / target).is_file()

    historical_plan, private = _revert_private(root, receipt)
    _write_historical_revert_journal(private)
    private["target_path"].unlink()
    _write_historical_revert_receipt(
        private,
        plan_sha256=historical_plan["summary"]["plan_sha256"],
    )
    private["journal_path"].unlink()
    revert_receipt = private["revert_receipt_path"]
    evidence = revert_receipt.read_text(encoding="utf-8")
    assert PRIVATE_NAME not in evidence
    assert PRIVATE_VALUE not in evidence
    replay = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    assert replay["ok"] is True
    assert replay["state"] == "already_reverted"


def test_revert_interruption_before_delete_resumes_from_journal(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    _plan, created = _create(root, request)
    target, receipt = created["files_written"]
    plan = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    target_path = root / target
    _historical_plan, private = _revert_private(root, receipt)
    _write_historical_revert_journal(private)

    recovery = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    assert recovery["state"] == "resume_revert"
    assert target_path.is_file()
    result = saved_view_workflows.saved_view_revert(
        root,
        receipt_path=receipt,
        expected_plan_sha256=recovery["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
    )
    assert result["state"] == "blocked"
    assert result["blockers"] == ["compound_exact_human_approval_binding_required"]
    assert target_path.exists()


def test_revert_interruption_after_delete_finalizes_receipt(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    _plan, created = _create(root, request)
    target, receipt = created["files_written"]
    plan = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    _historical_plan, private = _revert_private(root, receipt)
    _write_historical_revert_journal(private)
    private["target_path"].unlink()

    recovery = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    assert recovery["state"] == "finalize_revert_receipt"
    assert not (root / target).exists()
    result = saved_view_workflows.saved_view_revert(
        root,
        receipt_path=receipt,
        expected_plan_sha256=recovery["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
    )
    assert result["state"] == "blocked"
    assert result["blockers"] == ["compound_exact_human_approval_binding_required"]
    assert not private["revert_receipt_path"].exists()


def test_revert_interruption_during_journal_cleanup_converges(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    _plan, created = _create(root, request)
    target, receipt = created["files_written"]
    plan = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    _historical_plan, private = _revert_private(root, receipt)
    journal_path = private["journal_path"]
    _write_historical_revert_journal(private)
    private["target_path"].unlink()
    _write_historical_revert_receipt(
        private,
        plan_sha256=plan["summary"]["plan_sha256"],
    )

    assert not (root / target).exists()
    assert journal_path.is_file()
    recovery = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    assert recovery["state"] == "finalize_journal_cleanup"
    result = saved_view_workflows.saved_view_revert(
        root,
        receipt_path=receipt,
        expected_plan_sha256=recovery["summary"]["plan_sha256"],
        reviewed_by="person:unit-test",
    )
    assert result["state"] == "blocked"
    assert result["blockers"] == ["compound_exact_human_approval_binding_required"]
    assert result["files_written"] == []
    assert journal_path.exists()


def test_invalid_existing_revert_evidence_blocks_preview(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    _plan, created = _create(root, request)
    _target, receipt = created["files_written"]
    plan = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)
    evidence_path = root / plan["summary"]["revert_receipt_path"]
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("{}\n", encoding="utf-8")

    blocked = saved_view_workflows.saved_view_revert_plan(root, receipt_path=receipt)

    assert blocked["ok"] is False
    assert "saved_view_revert_evidence_mismatch" in blocked["blockers"]


def test_authority_change_during_read_fails_closed(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    path = root / "views" / "racing.yml"
    path.write_text(
        "id: view.racing\nname: Racing\nfilters:\n  facets.domain: "
        + PRIVATE_VALUE
        + "\n",
        encoding="utf-8",
    )
    original_read_bytes = Path.read_bytes

    def mutate_after_read(candidate: Path) -> bytes:
        data = original_read_bytes(candidate)
        if candidate == path:
            candidate.write_bytes(data + b"# changed\n")
        return data

    with mock.patch.object(Path, "read_bytes", new=mutate_after_read):
        authority = archive_services.saved_view_authority_scan(root)

    assert authority["ok"] is False
    assert "saved_view_authority_changed_during_scan" in authority["issue_codes"]


def test_public_request_and_receipt_schemas_accept_emitted_artifacts(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    _plan, created = _create(root, request)
    _target, receipt = created["files_written"]
    request_payload = json.loads((root / request).read_text(encoding="utf-8"))
    write_payload = json.loads((root / receipt).read_text(encoding="utf-8"))
    revert_plan, private = _revert_private(root, receipt)
    _write_historical_revert_journal(private)
    private["target_path"].unlink()
    _write_historical_revert_receipt(
        private,
        plan_sha256=revert_plan["summary"]["plan_sha256"],
    )
    revert_payload = json.loads(
        private["revert_receipt_path"].read_text(encoding="utf-8")
    )

    for schema_name, payload in (
        ("saved-view-write-request.schema.json", request_payload),
        ("saved-view-write-receipt.schema.json", write_payload),
        ("saved-view-revert-receipt.schema.json", revert_payload),
    ):
        schema = json.loads((SCHEMAS_ROOT / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(payload)


@pytest.mark.parametrize(
    ("filename", "content", "expected_code"),
    [
        ("invalid.yml", "id: [\n", "saved_view_authority_yaml_invalid"),
        (
            "unsupported.yml",
            "id: view.bad.filter\nname: Bad\nfilters:\n  status: canonical\n",
            "saved_view_authority_filter_unsupported",
        ),
    ],
)
def test_invalid_authority_blocks_health_recommendation_and_write(
    tmp_path: Path,
    filename: str,
    content: str,
    expected_code: str,
) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    (root / "views" / filename).write_text(content, encoding="utf-8")

    health = archive_services.view_health(root, dry_run=True)
    recommendation = archive_services.view_recommendation_plan(root, dry_run=True)
    write = saved_view_workflows.saved_view_write_plan(root, request_path=request)

    for result in (health, recommendation, write):
        assert result["ok"] is False
        assert expected_code in result["blockers"]


def test_duplicate_ids_block_complete_authority(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    for name in ("one.yml", "two.yml"):
        (root / "views" / name).write_text(
            archive_services.dump_yaml(
                {
                    "id": "view.duplicate",
                    "name": name,
                    "filters": {"facets.domain": PRIVATE_VALUE},
                }
            ),
            encoding="utf-8",
        )

    authority = archive_services.saved_view_authority_scan(root)
    plan = saved_view_workflows.saved_view_write_plan(root, request_path=request)

    assert authority["ok"] is False
    assert "saved_view_authority_duplicate_id" in authority["issue_codes"]
    assert plan["ok"] is False
    assert "saved_view_authority_duplicate_id" in plan["blockers"]


def test_request_is_closed_bounded_and_navigation_only(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    relative = _request(root)
    path = root / relative
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["filters"] = {"facets.notion_status": "internal-value"}
    path.write_text(json.dumps(payload), encoding="utf-8")

    internal = saved_view_workflows.saved_view_write_plan(root, request_path=relative)
    outside = saved_view_workflows.saved_view_write_plan(
        root,
        request_path="views/not-private.json",
    )

    assert "saved_view_request_filter_axis_not_navigation" in internal["blockers"]
    assert "saved_view_input_path_invalid" in outside["blockers"]


def test_cli_round_trip_is_json_and_content_free(tmp_path: Path) -> None:
    root = _archive(tmp_path / "archive")
    request = _request(root)
    code, output = _run_cli(
        [
            "saved-view-write",
            str(root),
            "--request",
            request,
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert code == 0
    plan = json.loads(output)
    assert plan["state"] == "create"
    assert PRIVATE_NAME not in output
    assert PRIVATE_VALUE not in output
    code, output = _run_cli(
        [
            "saved-view-write",
            str(root),
            "--request",
            request,
            "--approve",
            "--expected-plan-sha256",
            plan["summary"]["plan_sha256"],
            "--reviewed-by",
            "person:unit-test",
            "--affirm-view-reviewed",
            "--format",
            "json",
        ]
    )
    assert code == 1
    result = json.loads(output)
    assert result["state"] == "blocked"
    assert result["reason_codes"] == [
        "compound_exact_human_approval_binding_required"
    ]
    assert result["files_written"] == []
    assert result["private_values_echoed"] is False
    assert PRIVATE_NAME not in output
    assert PRIVATE_VALUE not in output
