from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock
import uuid

import wom_kit.notion_page_recovery as recovery_module
from wom_kit import archive_services
from wom_kit.archive_services import (
    notion_source_map_archive_json_records,
    notion_source_map_hashes_from_value,
    notion_source_map_object_ids_from_value,
)
from wom_kit.notion_page_recovery import (
    ArchiveInterprocessRequestPacer,
    _FilesystemRecoveryStorage as FilesystemRecoveryStorage,
    FixedIntervalRequestPacer,
    ManifestValidationError,
    MAX_UNKNOWN_BLOCK_IDS,
    OUTCOMES,
    ProviderResponse,
    REQUEST_SCHEMA,
    _execute_recovery as execute_recovery,
    parse_manifest,
    plan_recovery,
)
from wom_kit.schema_validator import validate_schema


ZERO_SHA = "sha256:" + ("0" * 64)
ONE_SHA = "sha256:" + ("1" * 64)
_TEST_ARCHIVE_IDENTITY_LOCK = threading.Lock()


def make_manifest(group_counts: tuple[int, ...] = (2,)) -> dict:
    groups = []
    items = []
    item_number = 1
    for group_number, expected_count in enumerate(group_counts, start=1):
        group_id = f"group-{group_number}"
        groups.append(
            {
                "group_id": group_id,
                "expected_count": expected_count,
                "scope_binding": {
                    "credential_id": f"cred_notion_group_{group_number:08d}",
                    "workspace_fingerprint": ZERO_SHA if group_number == 1 else ONE_SHA,
                    "scope_receipt_sha256": ONE_SHA if group_number == 1 else ZERO_SHA,
                    "revision": f"scope-r{group_number}",
                    "persisted": True,
                    "workspace_evidence_verified": True,
                },
            }
        )
        for _ in range(expected_count):
            items.append(
                {
                    "item_id": f"reviewed-{item_number:04d}",
                    "group_id": group_id,
                    "page_id": str(uuid.UUID(int=item_number)),
                }
            )
            item_number += 1
    return {
        "schema": REQUEST_SCHEMA,
        "batch_id": "letter118-reviewed-pages",
        "archive_id": "private-archive",
        "expected_item_count": sum(group_counts),
        "groups": groups,
        "items": items,
    }


def ensure_archive_identity(root: Path, archive_id: str) -> None:
    with _TEST_ARCHIVE_IDENTITY_LOCK:
        root.mkdir(parents=True, exist_ok=True)
        path = root / "archive.yml"
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(f"archive_id: {json.dumps(archive_id)}\n")
        except FileExistsError:
            pass


class FakeBroker:
    def __init__(self, secret: object = "TOKEN-MUST-NOT-LEAK") -> None:
        self.secret = secret
        self.calls = 0
        self.scopes = []
        self.lock = threading.Lock()

    def resolve(self, scope_binding):
        with self.lock:
            self.calls += 1
            self.scopes.append(scope_binding)
        return self.secret


class FailingBroker:
    def __init__(self, message: str) -> None:
        self.message = message
        self.calls = 0

    def resolve(self, _scope_binding):
        self.calls += 1
        raise RuntimeError(self.message)


class FakeProvider:
    def __init__(self, metadata=None, markdown=None, *, expected_credential="TOKEN-MUST-NOT-LEAK") -> None:
        self.metadata = {key: list(value) for key, value in (metadata or {}).items()}
        self.markdown = {key: list(value) for key, value in (markdown or {}).items()}
        self.expected_credential = expected_credential
        self.metadata_calls = 0
        self.markdown_calls = 0
        self.lock = threading.Lock()

    def _take(self, mapping, key):
        values = mapping.get(key)
        if not values:
            raise AssertionError("unexpected provider call")
        if len(values) == 1:
            return values[0]
        return values.pop(0)

    def retrieve_page(self, page_id, credential, *, api_version):
        self.assert_adapter_inputs(credential, api_version)
        with self.lock:
            self.metadata_calls += 1
            return self._take(self.metadata, page_id)

    def retrieve_page_as_markdown(self, page_or_block_id, credential, *, api_version):
        self.assert_adapter_inputs(credential, api_version)
        with self.lock:
            self.markdown_calls += 1
            return self._take(self.markdown, page_or_block_id)

    def assert_adapter_inputs(self, credential, api_version):
        if credential != self.expected_credential:
            raise AssertionError("wrong credential")
        if api_version != "2026-03-11":
            raise AssertionError("wrong API version")


class NeverProvider:
    def __init__(self) -> None:
        self.calls = 0

    def retrieve_page(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("provider must not be called")

    def retrieve_page_as_markdown(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("provider must not be called")


class RecordingPacer:
    def __init__(self) -> None:
        self.calls = 0

    def before_request(self) -> None:
        self.calls += 1


class DriftBeforeProviderPacer:
    def __init__(self, root: Path, *, drift_on_call: int = 1) -> None:
        self.root = root
        self.drift_on_call = drift_on_call
        self.calls = 0

    def before_request(self) -> None:
        self.calls += 1
        if self.calls == self.drift_on_call:
            (self.root / "archive.yml").write_text(
                "archive_id: changed-archive\n",
                encoding="utf-8",
            )


class DriftAfterFinalMetadataProvider(FakeProvider):
    def __init__(self, root: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.root = root

    def retrieve_page(self, page_id, credential, *, api_version):
        response = super().retrieve_page(
            page_id,
            credential,
            api_version=api_version,
        )
        if self.metadata_calls == 2:
            (self.root / "archive.yml").write_text(
                "archive_id: changed-archive\n",
                encoding="utf-8",
            )
        return response


class ShortWriteHandle:
    def __init__(self, handle, *, maximum: int) -> None:
        self.handle = handle
        self.maximum = maximum

    def write(self, payload):
        if self.maximum == 0:
            return 0
        return self.handle.write(payload[: self.maximum])

    def __getattr__(self, name):
        return getattr(self.handle, name)


def short_write_opener(original, *, maximum: int):
    @contextmanager
    def opened(*args, **kwargs):
        with original(*args, **kwargs) as handle:
            yield ShortWriteHandle(handle, maximum=maximum)

    return opened


class RevalidatingCredential:
    def __init__(self, *, fail_on: int | None = None) -> None:
        self.fail_on = fail_on
        self.revalidation_calls = 0
        self.close_calls = 0

    def revalidate_authority(self) -> None:
        self.revalidation_calls += 1
        if self.fail_on == self.revalidation_calls:
            raise RuntimeError("PRIVATE AUTHORITY DETAIL")

    def close(self) -> None:
        self.close_calls += 1


class CapabilityCredential(RevalidatingCredential):
    def __init__(self, *, fail_on: int | None = None) -> None:
        super().__init__()
        self.capability_fail_on = fail_on
        self.authorization_calls: list[str] = []

    def authorize_provider_request(self, endpoint_class: str) -> None:
        self.authorization_calls.append(endpoint_class)
        if self.capability_fail_on == len(self.authorization_calls):
            raise RuntimeError("PRIVATE CAPABILITY DETAIL")


class MutableOwningCredential:
    def __init__(self) -> None:
        self.buffer = bytearray(b"secret-owned-by-broker")
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        for index in range(len(self.buffer)):
            self.buffer[index] = 0


class ReparseStat:
    def __init__(self, original) -> None:
        self._original = original
        self.st_file_attributes = int(
            getattr(original, "st_file_attributes", 0)
        ) | 0x00000400

    def __getattr__(self, name):
        return getattr(self._original, name)


def _interprocess_pacer_worker(root: str, ready, start, result) -> None:
    try:
        pacer = ArchiveInterprocessRequestPacer(root)
        ready.put("ready")
        if not start.wait(timeout=10):
            result.put("start_timeout")
            return
        pacer.before_request()
        result.put("ok")
    except BaseException:
        result.put("failed")


def ok_metadata(page_id: str, **extra) -> ProviderResponse:
    return ProviderResponse(
        200,
        {
            "id": page_id,
            "object": "page",
            "in_trash": False,
            "last_edited_time": "2026-08-09T00:00:00.000Z",
            **extra,
        },
    )


def ok_markdown(
    page_or_block_id: str,
    markdown: str,
    *,
    truncated=False,
    unknown=(),
    **extra,
) -> ProviderResponse:
    return ProviderResponse(
        200,
        {
            "object": "page_markdown",
            "id": page_or_block_id,
            "markdown": markdown,
            "truncated": truncated,
            "unknown_block_ids": list(unknown),
            **extra,
        },
    )


def fixed_clock() -> datetime:
    return datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


class NotionPageRecoveryManifestTests(unittest.TestCase):
    def test_577_plus_43_arithmetic_and_scope_binding_are_validated(self) -> None:
        manifest = make_manifest((577, 43))
        parsed = parse_manifest(manifest)
        self.assertEqual(parsed.expected_item_count, 620)
        self.assertEqual([group.expected_count for group in parsed.groups], [577, 43])
        self.assertEqual(len(parsed.items), 620)

        mismatched = deepcopy(manifest)
        mismatched["groups"][1]["expected_count"] = 42
        with self.assertRaises(ManifestValidationError) as context:
            parse_manifest(mismatched)
        self.assertIn("group_expected_count_sum_mismatch", context.exception.codes)
        self.assertIn("group_actual_count_mismatch", context.exception.codes)

    def test_unknown_unsafe_fields_uuid_and_duplicates_are_rejected_without_value_echo(self) -> None:
        manifest = make_manifest((2,))
        manifest["items"][0]["body"] = "PRIVATE BODY https://provider.example/a"
        manifest["items"][1]["page_id"] = manifest["items"][0]["page_id"]
        manifest["groups"][0]["scope_binding"]["token"] = "SECRET-TOKEN"
        with self.assertRaises(ManifestValidationError) as context:
            parse_manifest(manifest)
        rendered = str(context.exception) + json.dumps(context.exception.codes)
        self.assertIn("item_additional_properties_forbidden", context.exception.codes)
        self.assertIn("scope_binding_additional_properties_forbidden", context.exception.codes)
        self.assertIn("duplicate_page_id", context.exception.codes)
        self.assertNotIn("PRIVATE BODY", rendered)
        self.assertNotIn("SECRET-TOKEN", rendered)
        self.assertNotIn("provider.example", rendered)

        invalid_uuid = make_manifest((1,))
        invalid_uuid["items"][0]["page_id"] = "https://provider.example/page"
        with self.assertRaises(ManifestValidationError) as uuid_context:
            parse_manifest(invalid_uuid)
        self.assertEqual(str(uuid_context.exception), "manifest_invalid")
        self.assertIn("page_id_invalid", uuid_context.exception.codes)

        invalid_credential = make_manifest((1,))
        invalid_credential["groups"][0]["scope_binding"]["credential_id"] = (
            "credential:notion-unresolvable"
        )
        with self.assertRaises(ManifestValidationError) as credential_context:
            parse_manifest(invalid_credential)
        self.assertIn("credential_id_invalid", credential_context.exception.codes)

    def test_scope_receipt_must_be_persisted_and_workspace_verified(self) -> None:
        manifest = make_manifest((1,))
        manifest["groups"][0]["scope_binding"]["persisted"] = False
        manifest["groups"][0]["scope_binding"]["workspace_evidence_verified"] = False
        with self.assertRaises(ManifestValidationError) as context:
            parse_manifest(manifest)
        self.assertIn("scope_receipt_not_persisted", context.exception.codes)
        self.assertIn("workspace_evidence_not_verified", context.exception.codes)

    def test_dry_run_is_deterministic_and_creates_no_files(self) -> None:
        manifest = make_manifest((1,))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "does-not-exist-yet"
            first = plan_recovery(root, manifest, max_items=1)
            second = plan_recovery(root, deepcopy(manifest), max_items=1)
            self.assertEqual(first["request_sha256"], second["request_sha256"])
            self.assertEqual(first["plan_sha256"], second["plan_sha256"])
            self.assertEqual(first["provider_calls"], 0)
            self.assertEqual(first["credential_reads"], 0)
            self.assertEqual(first["writes"], 0)
            self.assertEqual(
                first["approved_execution_capabilities"],
                {
                    "credential_reads_may_occur": True,
                    "provider_get_requests_may_occur": True,
                    "archive_writes_may_occur": True,
                    "verified_replay_is_optimization_only": True,
                },
            )
            self.assertFalse(root.exists())
            self.assertEqual(
                set(first),
                {
                    "ok",
                    "dry_run",
                    "lifecycle_action",
                    "reason_code",
                    "request_sha256",
                    "plan_sha256",
                    "approved_execution_capabilities",
                    "counts",
                    "provider_calls",
                    "credential_reads",
                    "writes",
                    "privacy_guards",
                    "blockers",
                },
            )

    def test_max_items_offset_and_plan_digest_prevent_scope_drift(self) -> None:
        manifest = make_manifest((3,))
        with tempfile.TemporaryDirectory() as temp:
            one = plan_recovery(temp, manifest, max_items=1, offset=0)
            two = plan_recovery(temp, manifest, max_items=2, offset=0)
            later = plan_recovery(temp, manifest, max_items=1, offset=1)
            self.assertNotEqual(one["plan_sha256"], two["plan_sha256"])
            self.assertNotEqual(one["plan_sha256"], later["plan_sha256"])

    def test_plan_digest_binds_live_capability_approval_not_replay_expectation(self) -> None:
        manifest = make_manifest((1,))
        with tempfile.TemporaryDirectory() as temp:
            approved = plan_recovery(temp, manifest, max_items=1)
            with mock.patch.dict(
                recovery_module.APPROVED_EXECUTION_CAPABILITIES,
                {"archive_writes_may_occur": False},
            ):
                weakened = plan_recovery(temp, manifest, max_items=1)
        self.assertNotEqual(approved["plan_sha256"], weakened["plan_sha256"])
        self.assertTrue(
            approved["approved_execution_capabilities"][
                "verified_replay_is_optimization_only"
            ]
        )

    def test_default_pacer_enforces_at_most_three_requests_per_second(self) -> None:
        current = [0.0]
        delays = []

        def monotonic() -> float:
            return current[0]

        def pace_sleep(delay: float) -> None:
            delays.append(delay)
            current[0] += delay

        pacer = FixedIntervalRequestPacer(monotonic=monotonic, sleep=pace_sleep)
        for _ in range(4):
            pacer.before_request()
        self.assertEqual(len(delays), 3)
        for delay in delays:
            self.assertAlmostEqual(delay, 1.0 / 3.0)
        self.assertNotIn("0.0", repr(pacer))
        with self.assertRaisesRegex(ValueError, "provider_request_rate_invalid"):
            FixedIntervalRequestPacer(requests_per_second=3.01)

    def test_official_unknown_block_id_limit_is_exactly_one_hundred(self) -> None:
        page_id = str(uuid.UUID(int=1))
        one_hundred = [str(uuid.UUID(int=index + 100)) for index in range(100)]
        base = {
            "object": "page_markdown",
            "id": page_id,
            "markdown": "exact",
            "truncated": True,
        }
        self.assertEqual(MAX_UNKNOWN_BLOCK_IDS, 100)
        self.assertIsNotNone(
            recovery_module._parse_markdown_response(
                {**base, "unknown_block_ids": one_hundred}, expected_id=page_id
            )
        )
        self.assertIsNone(
            recovery_module._parse_markdown_response(
                {**base, "unknown_block_ids": one_hundred + [str(uuid.UUID(int=999))]},
                expected_id=page_id,
            )
        )


class NotionPageRecoveryPacerTests(unittest.TestCase):
    def test_archive_pacer_is_lazy_and_corrupt_state_fails_closed_without_echo(self) -> None:
        current = [10.0]

        def monotonic() -> float:
            return current[0]

        def pace_sleep(delay: float) -> None:
            current[0] += delay

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            root.mkdir()
            pacer = ArchiveInterprocessRequestPacer(
                root, monotonic=monotonic, sleep=pace_sleep
            )
            self.assertFalse((root / "profiles").exists())
            self.assertNotIn(str(root), repr(pacer))

            pacer.before_request()
            private = root / "profiles" / "local" / "notion-page-recovery"
            lock_path = private / ".provider-get-rate-v1.lock"
            state_path = private / ".provider-get-rate-v1.state"
            self.assertEqual(lock_path.read_bytes(), b"\0")
            self.assertEqual(len(state_path.read_bytes()), 16)

            state_path.write_bytes(b"corrupt")
            with self.assertRaises(RuntimeError) as context:
                pacer.before_request()
            self.assertEqual(str(context.exception), "provider_pacer_failed")
            self.assertNotIn(str(root), str(context.exception))
            self.assertEqual(state_path.read_bytes(), b"corrupt")

    def test_archive_pacer_rejects_symlink_state_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            root.mkdir()
            current = [1.0]
            pacer = ArchiveInterprocessRequestPacer(
                root,
                monotonic=lambda: current[0],
                sleep=lambda delay: current.__setitem__(0, current[0] + delay),
            )
            pacer.before_request()
            state_path = (
                root
                / "profiles"
                / "local"
                / "notion-page-recovery"
                / ".provider-get-rate-v1.state"
            )
            outside = Path(temp) / "outside-state"
            sentinel = b"outside-must-remain-byte-identical"
            outside.write_bytes(sentinel)
            state_path.unlink()
            try:
                os.symlink(outside, state_path)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {type(exc).__name__}")
            with self.assertRaisesRegex(RuntimeError, "^provider_pacer_failed$"):
                pacer.before_request()
            self.assertEqual(outside.read_bytes(), sentinel)

    def test_two_processes_share_one_archive_rate_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            root.mkdir()
            context = multiprocessing.get_context("spawn")
            ready = context.Queue()
            start = context.Event()
            result = context.Queue()
            processes = [
                context.Process(
                    target=_interprocess_pacer_worker,
                    args=(str(root), ready, start, result),
                )
                for _ in range(2)
            ]
            for process in processes:
                process.start()
            self.assertEqual([ready.get(timeout=15) for _ in processes], ["ready", "ready"])
            started = time.monotonic()
            start.set()
            outcomes = [result.get(timeout=15) for _ in processes]
            elapsed = time.monotonic() - started
            for process in processes:
                process.join(timeout=15)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(outcomes, ["ok", "ok"])
            # The second grant cannot complete until one 1/3-second interval
            # after the first archive-wide grant. Keep tolerance for schedulers.
            self.assertGreaterEqual(elapsed, 0.25)


class NotionPageRecoveryExecutionTests(unittest.TestCase):
    def _execute(self, root: Path, manifest: dict, provider, broker=None, **kwargs):
        ensure_archive_identity(root, manifest["archive_id"])
        plan = plan_recovery(
            root,
            manifest,
            max_items=kwargs.get("max_items", manifest["expected_item_count"]),
            offset=kwargs.get("offset", 0),
        )
        return execute_recovery(
            root,
            manifest,
            expected_plan_sha256=kwargs.pop("expected_plan_sha256", plan["plan_sha256"]),
            reviewed_by=kwargs.pop("reviewed_by", "reviewer-1"),
            max_items=kwargs.pop("max_items", manifest["expected_item_count"]),
            offset=kwargs.pop("offset", 0),
            provider=provider,
            credential_broker=broker or FakeBroker(),
            request_pacer=kwargs.pop("request_pacer", lambda: None),
            sleep=kwargs.pop("sleep", lambda _delay: None),
            jitter=kwargs.pop("jitter", lambda: 0.0),
            clock=kwargs.pop("clock", fixed_clock),
            **kwargs,
        )

    def _assert_zero_live_access_and_writes(
        self,
        result: dict,
        provider: NeverProvider,
        broker: FakeBroker,
    ) -> None:
        self.assertEqual(provider.calls, 0)
        self.assertEqual(broker.calls, 0)
        for operation in (
            "provider_calls",
            "paced_request_count",
            "credential_resolution_attempts",
            "credential_reads",
            "retry_count",
            "objects_created",
            "manifest_rows_created",
            "projection_rows_created",
            "resume_rows_created",
        ):
            with self.subTest(operation=operation):
                self.assertEqual(result["operations"][operation], 0)
        self.assertFalse(result["receipt_created"])

    def test_invalid_credential_capability_reference_blocks_before_live_access(self) -> None:
        manifest = make_manifest((1,))
        private_marker = "PRIVATE-CAPABILITY-REFERENCE-MUST-NOT-ECHO"
        provider = NeverProvider()
        broker = FakeBroker()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(
                root,
                manifest,
                provider,
                broker,
                credential_capability_reference={"private": private_marker},
            )

            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["blockers"],
                ["credential_capability_reference_invalid"],
            )
            self._assert_zero_live_access_and_writes(result, provider, broker)
            self.assertNotIn(
                private_marker,
                json.dumps(result, ensure_ascii=False),
            )

    def test_archive_identity_drift_after_pacer_blocks_before_live_provider(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "PRIVATE PROVIDER BODY")]},
        )
        broker = FakeBroker()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pacer = DriftBeforeProviderPacer(root)
            result = self._execute(
                root,
                manifest,
                provider,
                broker,
                request_pacer=pacer,
            )

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status_class"], "partial")
            self.assertEqual(
                result["blockers"],
                ["notion_page_recovery_archive_identity_changed"],
            )
            self.assertEqual(pacer.calls, 1)
            self.assertEqual(provider.metadata_calls, 0)
            self.assertEqual(provider.markdown_calls, 0)
            self.assertEqual(broker.calls, 1)
            self.assertEqual(result["operations"]["paced_request_count"], 1)
            self.assertEqual(result["operations"]["provider_calls"], 0)
            self.assertEqual(result["operations"]["credential_reads"], 1)
            for operation in (
                "objects_created",
                "manifest_rows_created",
                "projection_rows_created",
                "resume_rows_created",
            ):
                self.assertEqual(result["operations"][operation], 0)
            self.assertFalse(result["receipt_created"])
            public = json.dumps(result, ensure_ascii=False)
            self.assertNotIn("changed-archive", public)
            self.assertNotIn("TOKEN-MUST-NOT-LEAK", public)
            self.assertNotIn("PRIVATE PROVIDER BODY", public)

    def test_archive_identity_drift_during_get_blocks_before_durable_commit(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        raw_text = "PRIVATE BODY AFTER IDENTITY DRIFT"
        broker = FakeBroker()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = DriftAfterFinalMetadataProvider(
                root,
                metadata={page_id: [ok_metadata(page_id), ok_metadata(page_id)]},
                markdown={page_id: [ok_markdown(page_id, raw_text)]},
            )
            result = self._execute(root, manifest, provider, broker)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status_class"], "partial")
            self.assertEqual(
                result["blockers"],
                ["notion_page_recovery_archive_identity_changed"],
            )
            self.assertEqual(result["operations"]["provider_calls"], 3)
            self.assertEqual(result["operations"]["paced_request_count"], 3)
            self.assertEqual(result["operations"]["credential_reads"], 1)
            for operation in (
                "objects_created",
                "manifest_rows_created",
                "projection_rows_created",
                "resume_rows_created",
            ):
                self.assertEqual(result["operations"][operation], 0)
            self.assertFalse(result["receipt_created"])
            self.assertEqual(list((root / "objects" / "sha256").glob("*/*")), [])
            public = json.dumps(result, ensure_ascii=False)
            self.assertNotIn("changed-archive", public)
            self.assertNotIn(raw_text, public)
            self.assertNotIn("TOKEN-MUST-NOT-LEAK", public)

    def test_archive_identity_drift_preserves_prior_commit_and_provider_counts(self) -> None:
        manifest = make_manifest((2,))
        first_page_id = manifest["items"][0]["page_id"]
        second_page_id = manifest["items"][1]["page_id"]
        provider = FakeProvider(
            metadata={
                first_page_id: [ok_metadata(first_page_id)],
                second_page_id: [ok_metadata(second_page_id)],
            },
            markdown={
                first_page_id: [ok_markdown(first_page_id, "first durable body")],
                second_page_id: [ok_markdown(second_page_id, "PRIVATE PENDING BODY")],
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pacer = DriftBeforeProviderPacer(root, drift_on_call=4)
            result = self._execute(
                root,
                manifest,
                provider,
                request_pacer=pacer,
            )

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status_class"], "partial")
            self.assertEqual(
                result["blockers"],
                ["notion_page_recovery_archive_identity_changed"],
            )
            self.assertEqual(result["counts"]["processed_item_count"], 1)
            self.assertEqual(result["counts"]["pending_item_count"], 1)
            self.assertEqual(result["counts"]["outcomes"]["recovered"], 1)
            self.assertEqual(result["operations"]["provider_calls"], 3)
            self.assertEqual(result["operations"]["paced_request_count"], 4)
            self.assertEqual(result["operations"]["objects_created"], 1)
            self.assertEqual(result["operations"]["manifest_rows_created"], 1)
            self.assertEqual(result["operations"]["projection_rows_created"], 1)
            self.assertEqual(result["operations"]["resume_rows_created"], 2)
            self.assertEqual(provider.metadata_calls, 2)
            self.assertEqual(provider.markdown_calls, 1)
            self.assertFalse(result["receipt_created"])
            public = json.dumps(result, ensure_ascii=False)
            self.assertNotIn("changed-archive", public)
            self.assertNotIn("PRIVATE PENDING BODY", public)

    def test_archive_identity_drift_blocks_verified_replay_without_live_access_or_write(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "stable replay body")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)
            durable_before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for parent in (root / "objects", root / "receipts")
                for path in parent.rglob("*")
                if path.is_file()
            }
            (root / "archive.yml").write_text(
                "archive_id: changed-archive\n",
                encoding="utf-8",
            )
            never = NeverProvider()
            broker = FakeBroker()

            replay = self._execute(root, manifest, never, broker)

            self.assertFalse(replay["ok"], replay)
            self.assertEqual(replay["status_class"], "blocked")
            self.assertEqual(
                replay["blockers"],
                ["notion_page_recovery_archive_identity_changed"],
            )
            self._assert_zero_live_access_and_writes(replay, never, broker)
            durable_after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for parent in (root / "objects", root / "receipts")
                for path in parent.rglob("*")
                if path.is_file()
            }
            self.assertEqual(durable_after, durable_before)
            self.assertNotIn("changed-archive", json.dumps(replay, ensure_ascii=False))

    def test_unchanged_archive_identity_allows_exact_happy_path(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "exact unchanged body")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(root, manifest, provider)

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status_class"], "written")
            self.assertEqual(result["blockers"], [])
            self.assertEqual(
                (root / "archive.yml").read_text(encoding="utf-8"),
                'archive_id: "private-archive"\n',
            )
            self.assertEqual(result["operations"]["provider_calls"], 3)
            self.assertTrue(result["receipt_created"])

    def test_credential_authority_drift_blocks_before_provider_without_detail_echo(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        credential = RevalidatingCredential(fail_on=1)
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "PRIVATE AUTHORITY BODY")]},
            expected_credential=credential,
        )
        broker = FakeBroker(secret=credential)
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(Path(temp), manifest, provider, broker)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status_class"], "partial")
            self.assertEqual(result["blockers"], ["credential_authority_changed"])
            self.assertEqual(credential.revalidation_calls, 1)
            self.assertEqual(credential.close_calls, 1)
            self.assertEqual(provider.metadata_calls, 0)
            self.assertEqual(provider.markdown_calls, 0)
            self.assertEqual(result["operations"]["paced_request_count"], 1)
            self.assertEqual(result["operations"]["provider_calls"], 0)
            self.assertEqual(result["operations"]["credential_reads"], 1)
            public = json.dumps(result, ensure_ascii=False)
            self.assertNotIn("PRIVATE AUTHORITY DETAIL", public)
            self.assertNotIn("PRIVATE AUTHORITY BODY", public)

    def test_credential_authority_is_revalidated_before_every_retry_and_get(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        credential = RevalidatingCredential()
        provider = FakeProvider(
            metadata={
                page_id: [
                    ProviderResponse(429, None, {"Retry-After": "0"}),
                    ok_metadata(page_id),
                    ok_metadata(page_id),
                ]
            },
            markdown={page_id: [ok_markdown(page_id, "authority retry body")]},
            expected_credential=credential,
        )
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(
                Path(temp),
                manifest,
                provider,
                FakeBroker(secret=credential),
            )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["operations"]["provider_calls"], 4)
            self.assertEqual(result["operations"]["paced_request_count"], 4)
            self.assertEqual(credential.revalidation_calls, 4)
            self.assertEqual(credential.close_calls, 1)

    def test_credential_capability_authorizes_each_fixed_endpoint_class(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        credential = CapabilityCredential()
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id), ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "capability body")]},
            expected_credential=credential,
        )
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(
                Path(temp),
                manifest,
                provider,
                FakeBroker(secret=credential),
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(
            credential.authorization_calls,
            ["retrieve_page", "retrieve_page_as_markdown", "retrieve_page"],
        )
        self.assertEqual(credential.revalidation_calls, 3)
        self.assertEqual(credential.close_calls, 1)

    def test_credential_capability_failure_blocks_before_provider_without_detail(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        credential = CapabilityCredential(fail_on=1)
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "PRIVATE CAPABILITY BODY")]},
            expected_credential=credential,
        )
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(
                Path(temp),
                manifest,
                provider,
                FakeBroker(secret=credential),
            )

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status_class"], "partial")
        self.assertEqual(
            result["blockers"],
            ["credential_capability_authorization_failed"],
        )
        self.assertEqual(credential.authorization_calls, ["retrieve_page"])
        self.assertEqual(credential.revalidation_calls, 1)
        self.assertEqual(credential.close_calls, 1)
        self.assertEqual(provider.metadata_calls, 0)
        self.assertEqual(provider.markdown_calls, 0)
        self.assertEqual(result["operations"]["provider_calls"], 0)
        public = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("PRIVATE CAPABILITY DETAIL", public)
        self.assertNotIn("PRIVATE CAPABILITY BODY", public)

    def test_verified_replay_performs_zero_credential_authority_revalidation(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        credential = RevalidatingCredential()
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "authority replay body")]},
            expected_credential=credential,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(
                root,
                manifest,
                provider,
                FakeBroker(secret=credential),
            )
            self.assertTrue(first["ok"], first)
            self.assertEqual(credential.revalidation_calls, 3)
            credential.revalidation_calls = 0
            never = NeverProvider()
            broker = FakeBroker(secret=credential)

            replay = self._execute(root, manifest, never, broker)

            self.assertTrue(replay["ok"], replay)
            self.assertEqual(replay["status_class"], "no_change")
            self.assertEqual(credential.revalidation_calls, 0)
            self.assertEqual(broker.calls, 0)
            self.assertEqual(never.calls, 0)
            self.assertEqual(replay["operations"]["provider_calls"], 0)
            self.assertEqual(replay["operations"]["credential_reads"], 0)

    def test_short_exclusive_writes_publish_exact_object_and_receipt(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        raw_text = "short writes still preserve exact bytes"
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, raw_text)]},
        )
        original_open = recovery_module._open_archive_exclusive_temp
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            recovery_module,
            "_open_archive_exclusive_temp",
            short_write_opener(original_open, maximum=3),
        ):
            root = Path(temp)
            result = self._execute(root, manifest, provider)

            self.assertTrue(result["ok"], result)
            digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            self.assertEqual(
                (root / "objects" / "sha256" / digest[:2] / digest).read_bytes(),
                raw_text.encode("utf-8"),
            )
            receipt = next(
                (root / "receipts" / "notion-page-recovery").glob(
                    "*.receipt.json"
                )
            ).read_bytes()
            self.assertTrue(receipt.endswith(b"\n"))
            self.assertIsInstance(json.loads(receipt), dict)
            self.assertEqual(result["operations"]["objects_created"], 1)
            self.assertTrue(result["receipt_created"])

    def test_short_replace_write_repairs_exact_jsonl(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "replace exact body")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)
            target = next(
                (root / "receipts" / "notion-page-recovery").glob(
                    "*.resume.jsonl"
                )
            )
            exact = target.read_bytes()
            target.write_bytes(exact + b'{"partial":')
            original_open = recovery_module._open_archive_exclusive_temp
            with mock.patch.object(
                recovery_module,
                "_open_archive_exclusive_temp",
                short_write_opener(original_open, maximum=2),
            ):
                FilesystemRecoveryStorage(root)._repair_torn_jsonl(target)

            self.assertEqual(target.read_bytes(), exact)

    def test_short_append_writes_publish_exact_jsonl_rows_and_counts(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "append exact body")]},
        )
        original_open = recovery_module._open_archive_append
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            recovery_module,
            "_open_archive_append",
            short_write_opener(original_open, maximum=2),
        ):
            root = Path(temp)
            result = self._execute(root, manifest, provider)

            self.assertTrue(result["ok"], result)
            jsonl_paths = list((root / "objects").rglob("*.jsonl")) + list(
                (root / "receipts").rglob("*.jsonl")
            )
            self.assertGreaterEqual(len(jsonl_paths), 3)
            for path in jsonl_paths:
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"), path)
                for line in payload.splitlines():
                    self.assertIsInstance(json.loads(line), dict)
            self.assertEqual(result["operations"]["manifest_rows_created"], 1)
            self.assertEqual(result["operations"]["projection_rows_created"], 1)
            self.assertEqual(result["operations"]["resume_rows_created"], 2)

    def test_zero_progress_object_write_fails_closed_with_honest_operations(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        raw_text = "PRIVATE ZERO PROGRESS BODY"
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, raw_text)]},
        )
        original_open = recovery_module._open_archive_exclusive_temp
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            recovery_module,
            "_open_archive_exclusive_temp",
            short_write_opener(original_open, maximum=0),
        ):
            root = Path(temp)
            result = self._execute(root, manifest, provider)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status_class"], "partial")
            self.assertEqual(result["blockers"], ["durable_write_failed"])
            self.assertEqual(result["operations"]["provider_calls"], 3)
            self.assertEqual(result["operations"]["credential_reads"], 1)
            for operation in (
                "objects_created",
                "manifest_rows_created",
                "projection_rows_created",
                "resume_rows_created",
            ):
                self.assertEqual(result["operations"][operation], 0)
            self.assertFalse(result["receipt_created"])
            self.assertEqual(list((root / "objects" / "sha256").glob("*/*")), [])
            public = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(raw_text, public)
            self.assertNotIn("TOKEN-MUST-NOT-LEAK", public)

    def test_execute_stores_exact_utf8_bytes_and_projects_page_object_and_sha(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        raw_text = "# 제목\r\n\r\n원본 줄 1\n원본 줄 2\n"
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, raw_text)]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(root, manifest, provider)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["counts"]["outcomes"]["recovered"], 1)
            digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            object_path = root / "objects" / "sha256" / digest[:2] / digest
            self.assertEqual(object_path.read_bytes(), raw_text.encode("utf-8"))

            projection_path = next((root / "receipts" / "import").glob("*.jsonl"))
            projection = json.loads(projection_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(projection["page_id"], page_id)
            self.assertEqual(projection["object_id"], f"sha256:{digest}")
            self.assertEqual(projection["sha256"], digest)
            self.assertEqual(projection["object_id"], f"sha256:{projection['sha256']}")
            self.assertEqual(projection["item_id"], manifest["items"][0]["item_id"])
            self.assertEqual(
                projection["scope_revision"],
                manifest["groups"][0]["scope_binding"]["revision"],
            )

            manifest_row = json.loads(
                (root / "objects" / "manifests" / "files.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
            self.assertEqual(validate_schema(manifest_row, "object-manifest-entry.schema.json"), [])
            self.assertEqual(
                manifest_row["logical_key"], f"objects/sha256/{digest[:2]}/{digest}"
            )
            self.assertEqual(manifest_row["locations"][0]["availability"], "available")
            self.assertNotIn(page_id, json.dumps(manifest_row, ensure_ascii=False))
            self.assertNotIn(
                manifest["items"][0]["item_id"],
                json.dumps(manifest_row, ensure_ascii=False),
            )

            blockers = []
            warnings = []
            relative_ledger = projection_path.relative_to(root).as_posix()
            records, summary = notion_source_map_archive_json_records(
                root,
                relative_ledger,
                role="ledger",
                max_rows=10,
                blockers=blockers,
                warnings=warnings,
            )
            self.assertEqual(blockers, [])
            self.assertEqual(warnings, [])
            self.assertEqual(summary["status"], "read")
            self.assertEqual(records, [projection])
            self.assertTrue(notion_source_map_hashes_from_value(projection)["page_refs"])
            self.assertIn(
                f"sha256:{digest}", notion_source_map_object_ids_from_value(projection)
            )

    def test_central_manifest_uses_zero_byte_standard_coordination_lock(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "lock contract bytes")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(root, manifest, provider)
            self.assertTrue(result["ok"], result)
            lock_path = root / "objects" / "manifests" / ".files.jsonl.lock"
            self.assertTrue(lock_path.is_file())
            self.assertEqual(lock_path.read_bytes(), b"")
            with archive_services._ObjetCaptureManifestLock(root):
                pass
            self.assertEqual(lock_path.read_bytes(), b"")

    def test_same_object_from_two_pages_has_one_central_authority_and_duplicate_rows_block(self) -> None:
        manifest = make_manifest((2,))
        first_page, second_page = [item["page_id"] for item in manifest["items"]]
        exact_markdown = "identical exact markdown bytes"
        provider = FakeProvider(
            metadata={
                first_page: [ok_metadata(first_page)],
                second_page: [ok_metadata(second_page)],
            },
            markdown={
                first_page: [ok_markdown(first_page, exact_markdown)],
                second_page: [ok_markdown(second_page, exact_markdown)],
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(root, manifest, provider)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["operations"]["objects_created"], 1)
            self.assertEqual(result["operations"]["manifest_rows_created"], 1)
            self.assertEqual(result["operations"]["projection_rows_created"], 2)
            manifest_path = root / "objects" / "manifests" / "files.jsonl"
            manifest_lines = manifest_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(manifest_lines), 1)
            central_row = json.loads(manifest_lines[0])
            central_text = json.dumps(central_row, ensure_ascii=False)
            self.assertNotIn(first_page, central_text)
            self.assertNotIn(second_page, central_text)

            projection_path = next((root / "receipts" / "import").glob("*.jsonl"))
            projections = [
                json.loads(line)
                for line in projection_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(projections), 2)
            self.assertEqual(
                {row["page_id"] for row in projections},
                {first_page, second_page},
            )
            self.assertEqual(
                len({row["object_id"] for row in projections}),
                1,
            )

            manifest_path.write_text(
                manifest_lines[0] + "\n" + manifest_lines[0] + "\n",
                encoding="utf-8",
            )
            blocked_plan = plan_recovery(root, manifest, max_items=2)
            self.assertFalse(blocked_plan["ok"], blocked_plan)
            self.assertEqual(
                blocked_plan["blockers"], ["recovery_authority_conflict"]
            )
            never = NeverProvider()
            broker = FakeBroker()
            blocked = self._execute(root, manifest, never, broker)
            self.assertFalse(blocked["ok"], blocked)
            self.assertEqual(blocked["blockers"], ["recovery_authority_conflict"])
            self.assertEqual(blocked["operations"]["provider_calls"], 0)
            self.assertEqual(
                blocked["operations"]["credential_resolution_attempts"], 0
            )
            self.assertEqual(blocked["operations"]["credential_reads"], 0)
            self.assertEqual(never.calls, 0)
            self.assertEqual(broker.calls, 0)

    def test_unknown_blocks_are_each_stored_exactly_and_unresolved_is_partial(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        child_id = str(uuid.UUID(int=999))
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={
                page_id: [
                    ok_markdown(
                        page_id, "root bytes", truncated=True, unknown=(child_id,)
                    )
                ],
                child_id: [ok_markdown(child_id, "child bytes")],
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(root, manifest, provider)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["operations"]["objects_created"], 2)
            for body in (b"root bytes", b"child bytes"):
                digest = hashlib.sha256(body).hexdigest()
                self.assertEqual(
                    (root / "objects" / "sha256" / digest[:2] / digest).read_bytes(), body
                )

        unresolved = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={
                page_id: [
                    ok_markdown(page_id, "root", truncated=True, unknown=(child_id,))
                ],
                child_id: [ProviderResponse(404, {"message": "PRIVATE PROVIDER BODY"})],
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(Path(temp), manifest, unresolved)
            self.assertFalse(result["ok"])
            self.assertEqual(result["counts"]["outcomes"]["partial"], 1)
            self.assertEqual(result["operations"]["objects_created"], 0)
            self.assertNotIn("PRIVATE PROVIDER BODY", json.dumps(result))

    def test_deleted_requires_explicit_in_trash_and_404_remains_ambiguous(self) -> None:
        manifest = make_manifest((3,))
        first, second, third = [item["page_id"] for item in manifest["items"]]
        provider = FakeProvider(
            metadata={
                first: [
                    ProviderResponse(
                        200, {"object": "page", "id": first, "in_trash": True}
                    )
                ],
                second: [ProviderResponse(404, {"message": "not found"})],
                third: [ProviderResponse(403, {"message": "forbidden"})],
            }
        )
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(Path(temp), manifest, provider)
            counts = result["counts"]["outcomes"]
            self.assertEqual(counts["deleted"], 1)
            self.assertEqual(counts["not_found_or_not_shared"], 1)
            self.assertEqual(counts["forbidden"], 1)
            self.assertEqual(counts["recovered"], 0)
            self.assertEqual(provider.markdown_calls, 0)

    def test_401_breaks_the_batch_without_touching_later_items(self) -> None:
        manifest = make_manifest((2,))
        first = manifest["items"][0]["page_id"]
        provider = FakeProvider(metadata={first: [ProviderResponse(401, {"message": "bad"})]})
        broker = FakeBroker()
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(Path(temp), manifest, provider, broker)
            self.assertFalse(result["ok"])
            self.assertIn("batch_credential_unauthorized", result["blockers"])
            self.assertEqual(result["counts"]["outcomes"]["retryable_error"], 1)
            self.assertEqual(result["counts"]["pending_item_count"], 1)
            self.assertEqual(provider.metadata_calls, 1)
            self.assertEqual(broker.calls, 1)

    def test_retry_after_and_bounded_get_retries_are_injected(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={
                page_id: [
                    ProviderResponse(529, None, {"Retry-After": "7"}),
                    ProviderResponse(409, None),
                    ok_metadata(page_id),
                ]
            },
            markdown={
                page_id: [
                    ProviderResponse(503, None),
                    ok_markdown(page_id, "eventual bytes", next_cursor="RAW-CURSOR"),
                ]
            },
        )
        delays = []
        pacer = RecordingPacer()
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(
                Path(temp),
                manifest,
                provider,
                sleep=delays.append,
                request_pacer=pacer,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(delays, [7.0, 2.0, 1.0])
            self.assertEqual(result["operations"]["retry_count"], 3)
            self.assertEqual(result["operations"]["provider_calls"], 6)
            self.assertEqual(result["operations"]["paced_request_count"], 6)
            self.assertEqual(pacer.calls, 6)
            all_private_text = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in Path(temp).rglob("*")
                if path.is_file() and "objects\\sha256" not in str(path)
            )
            self.assertNotIn("RAW-CURSOR", all_private_text)

    def test_normal_metadata_markdown_unknown_and_post_metadata_are_all_paced(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        child_id = str(uuid.UUID(int=888))
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={
                page_id: [
                    ok_markdown(page_id, "root", truncated=True, unknown=(child_id,))
                ],
                child_id: [ok_markdown(child_id, "child")],
            },
        )
        pacer = RecordingPacer()
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(
                Path(temp), manifest, provider, request_pacer=pacer
            )
        self.assertTrue(result["ok"], result)
        # before metadata + root markdown + unknown child + after metadata
        self.assertEqual(provider.metadata_calls, 2)
        self.assertEqual(provider.markdown_calls, 2)
        self.assertEqual(result["operations"]["provider_calls"], 4)
        self.assertEqual(result["operations"]["paced_request_count"], 4)
        self.assertEqual(pacer.calls, 4)
        rendered = json.dumps(result)
        self.assertNotIn("next_allowed", rendered)
        self.assertNotIn("monotonic", rendered)
        self.assertNotIn("pace_timestamp", rendered)

    def test_page_last_edited_time_is_checked_before_and_after_markdown(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        before = ok_metadata(page_id, last_edited_time="2026-08-09T00:00:00.000Z")
        after = ok_metadata(page_id, last_edited_time="2026-08-09T00:00:01.000Z")
        provider = FakeProvider(
            metadata={page_id: [before, after]},
            markdown={
                page_id: [ok_markdown(page_id, "mixed snapshot must not persist")]
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(root, manifest, provider)
            self.assertFalse(result["ok"])
            self.assertEqual(result["counts"]["outcomes"]["retryable_error"], 1)
            self.assertEqual(result["operations"]["objects_created"], 0)
            self.assertEqual(provider.metadata_calls, 2)
            self.assertEqual(provider.markdown_calls, 1)
            self.assertFalse((root / "objects" / "manifests" / "files.jsonl").exists())

    def test_non_retryable_400_is_partial_not_retryable_error(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(metadata={page_id: [ProviderResponse(400, {"body": "PRIVATE"})]})
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(Path(temp), manifest, provider)
            self.assertEqual(result["counts"]["outcomes"]["partial"], 1)
            self.assertEqual(result["counts"]["outcomes"]["retryable_error"], 0)
            self.assertEqual(provider.metadata_calls, 1)

    def test_retry_after_above_run_ceiling_stops_without_short_sleep(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ProviderResponse(429, None, {"Retry-After": "120"})]}
        )
        delays = []
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(
                Path(temp),
                manifest,
                provider,
                sleep=delays.append,
                max_retry_delay_seconds=60,
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["counts"]["outcomes"]["retryable_error"], 1)
            self.assertEqual(delays, [])
            self.assertEqual(result["operations"]["retry_count"], 0)
            self.assertEqual(provider.metadata_calls, 1)

    def test_plan_drift_and_bad_reviewer_block_before_provider_secret_or_write(self) -> None:
        manifest = make_manifest((1,))
        provider = NeverProvider()
        broker = FakeBroker()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "uncreated"
            result = execute_recovery(
                root,
                manifest,
                expected_plan_sha256=ZERO_SHA,
                reviewed_by="reviewer@example.com",
                max_items=1,
                provider=provider,
                credential_broker=broker,
                sleep=lambda _delay: None,
                jitter=lambda: 0.0,
                clock=fixed_clock,
            )
            self.assertFalse(result["ok"])
            self.assertIn("expected_plan_sha256_mismatch", result["blockers"])
            self.assertIn("reviewed_by_invalid", result["blockers"])
            self.assertEqual(provider.calls, 0)
            self.assertEqual(broker.calls, 0)
            self.assertFalse(root.exists())

    def test_result_receipt_and_private_control_files_do_not_leak_sensitive_payloads(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        markers = [
            "TOKEN-MUST-NOT-LEAK",
            "PRIVATE-TITLE-MUST-NOT-LEAK",
            "person@example.com",
            "https://api.notion.example/private",
            "RAW-CURSOR-MUST-NOT-LEAK",
        ]
        provider = FakeProvider(
            metadata={
                page_id: [
                    ok_metadata(
                        page_id,
                        title=markers[1],
                        email=markers[2],
                        url=markers[3],
                    )
                ]
            },
            markdown={
                page_id: [
                    ok_markdown(page_id, "PRIVATE BODY", next_cursor=markers[4])
                ]
            },
            expected_credential=markers[0],
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(root, manifest, provider, FakeBroker(markers[0]))
            self.assertTrue(result["ok"], result)
            public_text = json.dumps(result, ensure_ascii=False)
            receipt_text = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in (root / "receipts" / "notion-page-recovery").glob("*.receipt.json")
            )
            control_text = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in [
                    root / "objects" / "manifests" / "files.jsonl",
                    *list((root / "receipts" / "notion-page-recovery").glob("*.resume.jsonl")),
                    *list((root / "receipts" / "import").glob("*.jsonl")),
                ]
                if path.exists()
            )
            for marker in markers:
                self.assertNotIn(marker, public_text)
                self.assertNotIn(marker, receipt_text)
                self.assertNotIn(marker, control_text)
            self.assertNotIn("PRIVATE BODY", public_text)
            self.assertNotIn("PRIVATE BODY", receipt_text)
            self.assertNotIn("PRIVATE BODY", control_text)

    def test_replay_revalidates_object_manifest_and_projection_then_calls_provider_zero(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "stable original")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)
            plan = plan_recovery(root, manifest, max_items=1)
            self.assertEqual(plan["counts"]["recovered_verified_count"], 1)

            never = NeverProvider()
            broker = FakeBroker()
            replay = self._execute(root, manifest, never, broker)
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(replay["status_class"], "no_change")
            self.assertEqual(replay["counts"]["replayed_recovered_count"], 1)
            self.assertEqual(replay["operations"]["provider_calls"], 0)
            self.assertEqual(replay["operations"]["credential_reads"], 0)
            self.assertEqual(never.calls, 0)
            self.assertEqual(broker.calls, 0)

    def test_complete_invalid_jsonl_rows_fail_closed_unchanged_before_live_access(self) -> None:
        private_marker = "PRIVATE-STATE-MUST-NOT-ECHO"
        corruptions = {
            "malformed_complete": (
                b'{"private":"PRIVATE-STATE-MUST-NOT-ECHO"\n'
            ),
            "malformed_complete_cr": (
                b'{"private":"PRIVATE-STATE-MUST-NOT-ECHO"\r'
            ),
            "non_object_complete": (
                b'["PRIVATE-STATE-MUST-NOT-ECHO"]\n'
            ),
            "non_object_without_newline": (
                b'["PRIVATE-STATE-MUST-NOT-ECHO"]'
            ),
            "duplicate_key_complete": (
                b'{"nested":{"private":"PRIVATE-STATE-MUST-NOT-ECHO",'
                b'"private":"other"}}\n'
            ),
            "duplicate_key_without_newline": (
                b'{"nested":{"private":"PRIVATE-STATE-MUST-NOT-ECHO",'
                b'"private":"other"}}'
            ),
        }
        for surface in ("central_manifest", "projection", "resume"):
            for corruption_name, corruption in corruptions.items():
                with self.subTest(surface=surface, corruption=corruption_name):
                    manifest = make_manifest((1,))
                    page_id = manifest["items"][0]["page_id"]
                    initial_provider = FakeProvider(
                        metadata={page_id: [ok_metadata(page_id)]},
                        markdown={page_id: [ok_markdown(page_id, "stable original")]},
                    )
                    with tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        first = self._execute(root, manifest, initial_provider)
                        self.assertTrue(first["ok"], first)
                        paths = {
                            "central_manifest": (
                                root / "objects" / "manifests" / "files.jsonl"
                            ),
                            "projection": next(
                                (root / "receipts" / "import").glob("*.jsonl")
                            ),
                            "resume": next(
                                (root / "receipts" / "notion-page-recovery").glob(
                                    "*.resume.jsonl"
                                )
                            ),
                        }
                        target = paths[surface]
                        poisoned = target.read_bytes() + corruption
                        target.write_bytes(poisoned)

                        never = NeverProvider()
                        broker = FakeBroker()
                        blocked = self._execute(root, manifest, never, broker)

                        self.assertFalse(blocked["ok"], blocked)
                        self.assertEqual(blocked["blockers"], ["private_state_invalid"])
                        self._assert_zero_live_access_and_writes(
                            blocked,
                            never,
                            broker,
                        )
                        self.assertEqual(target.read_bytes(), poisoned)
                        self.assertNotIn(
                            private_marker,
                            json.dumps(blocked, ensure_ascii=False),
                        )

    def test_non_newline_trailing_json_fragment_remains_repairable(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        for surface in ("central_manifest", "projection", "resume"):
            with self.subTest(surface=surface):
                provider = FakeProvider(
                    metadata={page_id: [ok_metadata(page_id)]},
                    markdown={page_id: [ok_markdown(page_id, "stable original")]},
                )
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    first = self._execute(root, manifest, provider)
                    self.assertTrue(first["ok"], first)
                    paths = {
                        "central_manifest": (
                            root / "objects" / "manifests" / "files.jsonl"
                        ),
                        "projection": next(
                            (root / "receipts" / "import").glob("*.jsonl")
                        ),
                        "resume": next(
                            (root / "receipts" / "notion-page-recovery").glob(
                                "*.resume.jsonl"
                            )
                        ),
                    }
                    target = paths[surface]
                    original = target.read_bytes()
                    self.assertTrue(original.endswith(b"\n"))
                    target.write_bytes(original + b'{"partial":')

                    FilesystemRecoveryStorage(root)._repair_torn_jsonl(target)

                    self.assertEqual(target.read_bytes(), original)

    def test_exact_existing_replay_receipt_is_idempotent(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "stable original")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)

            never = NeverProvider()
            broker = FakeBroker()
            replay = self._execute(root, manifest, never, broker)
            self.assertTrue(replay["ok"], replay)
            self.assertTrue(replay["receipt_created"])
            receipt_paths = set(
                (root / "receipts" / "notion-page-recovery").glob(
                    "*.receipt.json"
                )
            )

            second_never = NeverProvider()
            second_broker = FakeBroker()
            exact_replay = self._execute(
                root,
                manifest,
                second_never,
                second_broker,
            )

            self.assertTrue(exact_replay["ok"], exact_replay)
            self.assertEqual(exact_replay["status_class"], "no_change")
            self.assertFalse(exact_replay["receipt_created"])
            self.assertEqual(
                set(
                    (root / "receipts" / "notion-page-recovery").glob(
                        "*.receipt.json"
                    )
                ),
                receipt_paths,
            )
            self._assert_zero_live_access_and_writes(
                exact_replay,
                second_never,
                second_broker,
            )

    def test_poisoned_expected_replay_receipt_blocks_unchanged_without_live_access(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "stable original")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)
            before_replay_receipts = set(
                (root / "receipts" / "notion-page-recovery").glob(
                    "*.receipt.json"
                )
            )

            replay = self._execute(root, manifest, NeverProvider(), FakeBroker())
            self.assertTrue(replay["ok"], replay)
            after_replay_receipts = set(
                (root / "receipts" / "notion-page-recovery").glob(
                    "*.receipt.json"
                )
            )
            new_receipts = after_replay_receipts - before_replay_receipts
            self.assertEqual(len(new_receipts), 1)
            expected_receipt = new_receipts.pop()
            original = expected_receipt.read_bytes()
            self.assertGreater(len(original), 1)
            poisoned = bytes((original[0] ^ 1,)) + original[1:]
            self.assertEqual(len(poisoned), len(original))
            expected_receipt.write_bytes(poisoned)

            never = NeverProvider()
            broker = FakeBroker()
            blocked = self._execute(root, manifest, never, broker)

            self.assertFalse(blocked["ok"], blocked)
            self.assertIn("recovery_authority_conflict", blocked["blockers"])
            self._assert_zero_live_access_and_writes(blocked, never, broker)
            self.assertEqual(expected_receipt.read_bytes(), poisoned)
            self.assertEqual(
                set(
                    (root / "receipts" / "notion-page-recovery").glob(
                        "*.receipt.json"
                    )
                ),
                after_replay_receipts,
            )

    def test_unsafe_existing_receipt_verification_maps_to_authority_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            storage = FilesystemRecoveryStorage(root)
            receipt = {"schema": "safe-test-receipt", "ok": True}
            self.assertTrue(storage.write_receipt(ZERO_SHA, receipt))

            with mock.patch.object(
                recovery_module,
                "_file_matches_exact_payload",
                side_effect=recovery_module.RecoveryStorageError(
                    "archive_path_unsafe"
                ),
            ):
                with self.assertRaises(
                    recovery_module.RecoveryStorageError
                ) as context:
                    storage.write_receipt(ZERO_SHA, receipt)

            self.assertEqual(
                context.exception.code,
                "recovery_authority_conflict",
            )

    def test_approved_plan_allows_live_recovery_when_replay_optimization_disappears(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        original = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "approved live fallback")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, original)
            self.assertTrue(first["ok"], first)
            approved_plan = plan_recovery(root, manifest, max_items=1)
            self.assertEqual(
                approved_plan["counts"]["recovered_verified_count"], 1
            )
            self.assertEqual(
                approved_plan["approved_execution_capabilities"],
                {
                    "credential_reads_may_occur": True,
                    "provider_get_requests_may_occur": True,
                    "archive_writes_may_occur": True,
                    "verified_replay_is_optimization_only": True,
                },
            )

            object_path = next((root / "objects" / "sha256").glob("*/*"))
            object_path.unlink()
            after_loss = plan_recovery(root, manifest, max_items=1)
            self.assertEqual(after_loss["plan_sha256"], approved_plan["plan_sha256"])
            self.assertEqual(after_loss["counts"]["recovered_verified_count"], 0)

            live_provider = FakeProvider(
                metadata={page_id: [ok_metadata(page_id)]},
                markdown={
                    page_id: [ok_markdown(page_id, "approved live fallback")]
                },
            )
            broker = FakeBroker()
            resumed = execute_recovery(
                root,
                manifest,
                expected_plan_sha256=approved_plan["plan_sha256"],
                reviewed_by="reviewer-1",
                max_items=1,
                provider=live_provider,
                credential_broker=broker,
                request_pacer=lambda: None,
                sleep=lambda _delay: None,
                jitter=lambda: 0.0,
                clock=fixed_clock,
            )
            self.assertTrue(resumed["ok"], resumed)
            self.assertGreater(resumed["operations"]["provider_calls"], 0)
            self.assertEqual(
                resumed["operations"]["credential_resolution_attempts"], 1
            )
            self.assertEqual(resumed["operations"]["credential_reads"], 1)
            self.assertEqual(broker.calls, 1)

    def test_poisoned_manifest_authority_blocks_without_value_reflection(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "stable original")]},
        )
        private_markers = (
            "PRIVATE-BODY-MUST-NOT-REFLECT",
            "secret_1234567890abcdef",
            "https://provider.example/private",
            page_id,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)

            manifest_path = root / "objects" / "manifests" / "files.jsonl"
            poisoned = json.loads(manifest_path.read_text(encoding="utf-8"))
            poisoned["mime"] = private_markers[0]
            poisoned["locations"][0]["provider"] = private_markers[1]
            poisoned["locations"][0]["path"] = private_markers[2]
            manifest_path.write_text(
                json.dumps(poisoned, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            preview = plan_recovery(root, manifest, max_items=1)
            self.assertFalse(preview["ok"], preview)
            self.assertEqual(preview["blockers"], ["recovery_authority_conflict"])

            never = NeverProvider()
            broker = FakeBroker()
            blocked = self._execute(root, manifest, never, broker)
            self.assertFalse(blocked["ok"], blocked)
            self.assertEqual(blocked["blockers"], ["recovery_authority_conflict"])
            self.assertEqual(blocked["operations"]["provider_calls"], 0)
            self.assertEqual(blocked["operations"]["credential_reads"], 0)
            self.assertEqual(never.calls, 0)
            self.assertEqual(broker.calls, 0)
            self.assertEqual(len(manifest_path.read_text(encoding="utf-8").splitlines()), 1)
            rendered = json.dumps(blocked, ensure_ascii=False)
            for marker in private_markers:
                self.assertNotIn(marker, rendered)

    def test_poisoned_projection_authority_blocks_without_value_reflection(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "stable original")]},
        )
        private_markers = (
            "PRIVATE-BODY-MUST-NOT-REFLECT",
            "secret_1234567890abcdef",
            "https://provider.example/private",
            page_id,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)

            projection_path = next((root / "receipts" / "import").glob("*.jsonl"))
            poisoned = json.loads(projection_path.read_text(encoding="utf-8"))
            poisoned["body_detail"] = private_markers[0]
            poisoned["secret_detail"] = private_markers[1]
            poisoned["provider_detail"] = private_markers[2]
            projection_path.write_text(
                json.dumps(poisoned, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            preview = plan_recovery(root, manifest, max_items=1)
            self.assertFalse(preview["ok"], preview)
            self.assertEqual(preview["blockers"], ["recovery_authority_conflict"])

            never = NeverProvider()
            broker = FakeBroker()
            blocked = self._execute(root, manifest, never, broker)
            self.assertFalse(blocked["ok"], blocked)
            self.assertEqual(blocked["blockers"], ["recovery_authority_conflict"])
            self.assertEqual(blocked["operations"]["provider_calls"], 0)
            self.assertEqual(blocked["operations"]["credential_reads"], 0)
            self.assertEqual(never.calls, 0)
            self.assertEqual(broker.calls, 0)
            self.assertEqual(
                len(projection_path.read_text(encoding="utf-8").splitlines()), 1
            )
            rendered = json.dumps(blocked, ensure_ascii=False)
            for marker in private_markers:
                self.assertNotIn(marker, rendered)

    def test_multiple_equal_projection_authorities_fail_closed(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "stable original")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)
            projection_path = next((root / "receipts" / "import").glob("*.jsonl"))
            original = json.loads(projection_path.read_text(encoding="utf-8"))
            duplicate = deepcopy(original)
            duplicate["completed_at"] = "2026-08-11T00:00:00Z"
            projection_path.write_text(
                "\n".join(
                    json.dumps(row, sort_keys=True, separators=(",", ":"))
                    for row in (original, duplicate)
                )
                + "\n",
                encoding="utf-8",
            )

            preview = plan_recovery(root, manifest, max_items=1)
            self.assertFalse(preview["ok"], preview)
            self.assertEqual(preview["blockers"], ["recovery_authority_conflict"])

    def test_repair_ignores_only_retry_local_authority_timestamps(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "recover after manifest crash")]},
        )

        def failpoint(phase: str) -> None:
            if phase == "after_manifest":
                raise RuntimeError("PRIVATE CRASH DETAIL")

        later_clock = lambda: datetime(2026, 8, 11, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(
                root,
                manifest,
                provider,
                storage=FilesystemRecoveryStorage(root, failpoint=failpoint),
            )
            self.assertFalse(first["ok"])
            manifest_path = root / "objects" / "manifests" / "files.jsonl"
            original_row = json.loads(manifest_path.read_text(encoding="utf-8"))

            never = NeverProvider()
            broker = FakeBroker()
            repaired = self._execute(
                root,
                manifest,
                never,
                broker,
                clock=later_clock,
            )
            self.assertTrue(repaired["ok"], repaired)
            self.assertEqual(repaired["counts"]["replayed_recovered_count"], 1)
            self.assertEqual(repaired["operations"]["provider_calls"], 0)
            self.assertEqual(repaired["operations"]["credential_reads"], 0)
            self.assertEqual(repaired["operations"]["manifest_rows_created"], 0)
            self.assertEqual(repaired["operations"]["projection_rows_created"], 1)
            self.assertEqual(never.calls, 0)
            self.assertEqual(broker.calls, 0)
            final_rows = manifest_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(final_rows), 1)
            self.assertEqual(json.loads(final_rows[0]), original_row)

    def test_replay_does_not_trust_a_tampered_content_object(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        initial = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "verified original")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, initial)
            self.assertTrue(first["ok"], first)
            object_file = next((root / "objects" / "sha256").glob("*/*"))
            object_file.write_bytes(b"tampered")

            replacement = FakeProvider(
                metadata={page_id: [ok_metadata(page_id)]},
                markdown={page_id: [ok_markdown(page_id, "verified original")]},
            )
            second = self._execute(root, manifest, replacement)
            self.assertFalse(second["ok"])
            self.assertGreater(replacement.metadata_calls, 0)
            self.assertIn("content_address_collision", second["blockers"])

    def test_crash_after_object_checkpoint_is_repaired_without_provider(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "recover after crash")]},
        )

        def failpoint(phase: str) -> None:
            if phase == "after_objects_checkpoint":
                raise RuntimeError("PRIVATE CRASH DETAIL")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(
                root,
                manifest,
                provider,
                storage=FilesystemRecoveryStorage(root, failpoint=failpoint),
            )
            self.assertFalse(first["ok"])
            self.assertNotIn("PRIVATE CRASH DETAIL", json.dumps(first))

            never = NeverProvider()
            broker = FakeBroker()
            repaired = self._execute(root, manifest, never, broker)
            self.assertTrue(repaired["ok"], repaired)
            self.assertEqual(repaired["counts"]["replayed_recovered_count"], 1)
            self.assertEqual(repaired["operations"]["provider_calls"], 0)
            self.assertEqual(repaired["operations"]["credential_reads"], 0)

    def test_concurrent_execution_serializes_one_provider_retrieval(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "one retrieval")]},
        )
        broker = FakeBroker()
        results = []
        failures = []
        start = threading.Barrier(2)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def worker() -> None:
                try:
                    start.wait(timeout=5)
                    results.append(self._execute(root, manifest, provider, broker))
                except BaseException as exc:  # preserve assertion details from worker
                    failures.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertFalse(failures, failures)
            self.assertEqual(len(results), 2)
            self.assertTrue(all(result["ok"] for result in results), results)
            self.assertEqual(provider.metadata_calls, 2)
            self.assertEqual(provider.markdown_calls, 1)
            self.assertEqual(broker.calls, 1)
            self.assertEqual(
                sorted(result["status_class"] for result in results), ["no_change", "written"]
            )

    def test_all_count_buckets_sum_to_the_manifest_total(self) -> None:
        manifest = make_manifest((2, 1))
        selected_page = manifest["items"][1]["page_id"]
        provider = FakeProvider(metadata={selected_page: [ProviderResponse(404, None)]})
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(
                Path(temp),
                manifest,
                provider,
                max_items=1,
                offset=1,
            )
            counts = result["counts"]
            self.assertEqual(
                sum(counts["outcomes"].values())
                + counts["pending_item_count"]
                + counts["unselected_item_count"],
                manifest["expected_item_count"],
            )
            self.assertEqual(counts["total_accounted_count"], 3)
            self.assertEqual(set(counts["outcomes"]), set(OUTCOMES))

    def test_credential_exception_detail_is_sanitized(self) -> None:
        manifest = make_manifest((1,))
        provider = NeverProvider()
        secret_message = "TOKEN https://provider.example person@example.com PRIVATE"
        with tempfile.TemporaryDirectory() as temp:
            result = self._execute(
                Path(temp),
                manifest,
                provider,
                FailingBroker(secret_message),
            )
            rendered = json.dumps(result)
            self.assertIn("credential_resolution_failed", result["blockers"])
            self.assertNotIn(secret_message, rendered)
            self.assertEqual(
                result["operations"]["credential_resolution_attempts"], 1
            )
            self.assertEqual(result["operations"]["credential_reads"], 0)
            self.assertEqual(provider.calls, 0)

    def test_exact_provider_response_identity_is_required_before_persistence(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        cases = (
            (
                "metadata_non_200_success_shape",
                FakeProvider(
                    metadata={
                        page_id: [
                            ProviderResponse(
                                201,
                                {
                                    "object": "page",
                                    "id": page_id,
                                    "in_trash": False,
                                    "last_edited_time": "2026-08-09T00:00:00.000Z",
                                },
                            )
                        ]
                    }
                ),
            ),
            (
                "metadata_timestamp_malformed",
                FakeProvider(
                    metadata={
                        page_id: [ok_metadata(page_id, last_edited_time="not-a-time")]
                    }
                ),
            ),
            (
                "metadata_object",
                FakeProvider(
                    metadata={
                        page_id: [
                            ProviderResponse(
                                200,
                                {
                                    "object": "database",
                                    "id": page_id,
                                    "in_trash": False,
                                    "last_edited_time": "2026-08-09T00:00:00.000Z",
                                },
                            )
                        ]
                    }
                ),
            ),
            (
                "markdown_id",
                FakeProvider(
                    metadata={page_id: [ok_metadata(page_id)]},
                    markdown={
                        page_id: [
                            ok_markdown(str(uuid.UUID(int=999)), "wrong identity")
                        ]
                    },
                ),
            ),
            (
                "post_metadata_identity",
                FakeProvider(
                    metadata={
                        page_id: [
                            ok_metadata(page_id),
                            ok_metadata(str(uuid.UUID(int=999))),
                        ]
                    },
                    markdown={page_id: [ok_markdown(page_id, "not committed")]},
                ),
            ),
        )
        for label, provider in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                result = self._execute(root, manifest, provider)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["counts"]["outcomes"]["partial"], 1)
                self.assertEqual(result["operations"]["objects_created"], 0)
                self.assertFalse((root / "objects" / "sha256").exists())

    def test_canonical_zet_sentinel_stays_byte_identical_after_recovery(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "recovered source objet")]},
        )
        sentinel = (
            b"\xef\xbb\xbf---\r\nid: zet_private_sentinel\r\n---\r\n"
            b"CANONICAL-ZET-MUST-STAY-BYTE-IDENTICAL\r\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            canonical = root / "zettels" / "zet_private_sentinel.md"
            canonical.parent.mkdir()
            canonical.write_bytes(sentinel)
            before = hashlib.sha256(canonical.read_bytes()).hexdigest()
            result = self._execute(root, manifest, provider)
            self.assertTrue(result["ok"], result)
            self.assertEqual(canonical.read_bytes(), sentinel)
            self.assertEqual(hashlib.sha256(canonical.read_bytes()).hexdigest(), before)

    def test_verified_replay_does_not_create_or_touch_global_pacer_state(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "replay source")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)
            pacing_root = root / "profiles" / "local" / "notion-page-recovery"
            self.assertFalse(pacing_root.exists())

            never_provider = NeverProvider()
            never_broker = FailingBroker("must not resolve on replay")
            replay = self._execute(
                root,
                manifest,
                never_provider,
                never_broker,
                request_pacer=None,
            )
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(replay["status_class"], "no_change")
            self.assertEqual(replay["operations"]["provider_calls"], 0)
            self.assertEqual(replay["operations"]["credential_reads"], 0)
            self.assertEqual(never_provider.calls, 0)
            self.assertEqual(never_broker.calls, 0)
            self.assertFalse(pacing_root.exists())

    def test_default_execute_paces_all_three_provider_gets_archive_wide(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, "default pacer live path")]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self._execute(root, manifest, provider, request_pacer=None)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["operations"]["provider_calls"], 3)
            self.assertEqual(result["operations"]["paced_request_count"], 3)
            private = root / "profiles" / "local" / "notion-page-recovery"
            self.assertEqual(
                (private / ".provider-get-rate-v1.lock").read_bytes(), b"\0"
            )
            self.assertEqual(
                len((private / ".provider-get-rate-v1.state").read_bytes()), 16
            )
            rendered = json.dumps(result)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("provider-get-rate", rendered)

    def test_existing_reparse_output_surface_blocks_before_credential_or_provider(self) -> None:
        manifest = make_manifest((1,))
        provider = NeverProvider()
        broker = FakeBroker()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            objects = root / "objects"
            objects.mkdir()
            original_lstat = os.lstat

            def lstat_with_reparse(path):
                information = original_lstat(path)
                if Path(path) == objects:
                    return ReparseStat(information)
                return information

            with mock.patch.object(
                recovery_module.os, "lstat", side_effect=lstat_with_reparse
            ):
                result = self._execute(root, manifest, provider, broker)
            self.assertFalse(result["ok"], result)
            self.assertIn("archive_path_unsafe", result["blockers"])
            self.assertEqual(provider.calls, 0)
            self.assertEqual(broker.calls, 0)
            self.assertFalse((root / "receipts").exists())

    def test_symlink_object_destination_never_writes_outside_archive(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        body = "digest-selected-prefix"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, body)]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "archive"
            outside = Path(temp) / "outside"
            root.mkdir()
            outside.mkdir()
            prefix = root / "objects" / "sha256" / digest[:2]
            prefix.parent.mkdir(parents=True)
            try:
                os.symlink(outside, prefix, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {type(exc).__name__}")
            result = self._execute(root, manifest, provider)
            self.assertFalse(result["ok"], result)
            self.assertIn("archive_path_unsafe", result["blockers"])
            self.assertEqual(list(outside.iterdir()), [])

    def test_reparse_digest_prefix_blocks_before_object_write_and_closes_secret(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        body = "reparse-prefix-body"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        credential = MutableOwningCredential()
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, body)]},
            expected_credential=credential,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prefix = root / "objects" / "sha256" / digest[:2]
            prefix.mkdir(parents=True)
            original_lstat = os.lstat

            def lstat_with_reparse(path):
                information = original_lstat(path)
                if Path(path) == prefix:
                    return ReparseStat(information)
                return information

            with mock.patch.object(
                recovery_module.os, "lstat", side_effect=lstat_with_reparse
            ):
                result = self._execute(
                    root, manifest, provider, FakeBroker(credential)
                )
            self.assertFalse(result["ok"], result)
            self.assertIn("archive_path_unsafe", result["blockers"])
            self.assertEqual(list(prefix.iterdir()), [])
            self.assertEqual(credential.close_calls, 1)
            self.assertEqual(credential.buffer, bytearray(len(credential.buffer)))

    def test_reparse_replay_object_blocks_without_provider_or_secret_read(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        body = "verified-then-reparse"
        provider = FakeProvider(
            metadata={page_id: [ok_metadata(page_id)]},
            markdown={page_id: [ok_markdown(page_id, body)]},
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._execute(root, manifest, provider)
            self.assertTrue(first["ok"], first)
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            object_path = root / "objects" / "sha256" / digest[:2] / digest
            original_lstat = os.lstat

            def lstat_with_reparse(path):
                information = original_lstat(path)
                if Path(path) == object_path:
                    return ReparseStat(information)
                return information

            never_provider = NeverProvider()
            never_broker = FailingBroker("must not read a replay secret")
            with mock.patch.object(
                recovery_module.os, "lstat", side_effect=lstat_with_reparse
            ):
                replay = self._execute(
                    root, manifest, never_provider, never_broker
                )
            self.assertFalse(replay["ok"], replay)
            self.assertIn("archive_path_unsafe", replay["blockers"])
            self.assertEqual(never_provider.calls, 0)
            self.assertEqual(never_broker.calls, 0)

    def test_resolved_mutable_credential_is_closed_once_on_every_provider_outcome(self) -> None:
        manifest = make_manifest((1,))
        page_id = manifest["items"][0]["page_id"]
        providers = (
            (
                "success",
                lambda credential: FakeProvider(
                    metadata={page_id: [ok_metadata(page_id)]},
                    markdown={page_id: [ok_markdown(page_id, "close after success")]},
                    expected_credential=credential,
                ),
            ),
            (
                "partial",
                lambda credential: FakeProvider(
                    metadata={page_id: [ProviderResponse(400, None)]},
                    expected_credential=credential,
                ),
            ),
            (
                "unauthorized",
                lambda credential: FakeProvider(
                    metadata={page_id: [ProviderResponse(401, None)]},
                    expected_credential=credential,
                ),
            ),
        )
        for label, build_provider in providers:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                credential = MutableOwningCredential()
                provider = build_provider(credential)
                self._execute(
                    Path(temp),
                    manifest,
                    provider,
                    FakeBroker(credential),
                    max_attempts=1,
                )
                self.assertEqual(credential.close_calls, 1)
                self.assertEqual(credential.buffer, bytearray(len(credential.buffer)))


if __name__ == "__main__":
    unittest.main()
