from __future__ import annotations

import ctypes
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import wom_kit.private_metadata_win32 as win32


WINDOWS = os.name == "nt" and sys.platform == "win32"
WINDOWS_NTFS = pytest.mark.skipif(
    not WINDOWS,
    reason="real Win32/NTFS mutation probe",
)


def _archive_root(tmp_path: Path) -> Path:
    root = tmp_path / "archive"
    (root / "objects" / "manifests").mkdir(parents=True)
    return root


def _require_ntfs(root: Path) -> None:
    status = win32._approval_environment_status(root)
    if not status.supported:
        pytest.skip(
            "real NTFS mutation profile is unavailable on this runner"
        )


def _probe_guard(
    root: Path,
) -> win32.PrivateMetadataMutationGuard:
    return win32.PrivateMetadataMutationGuard._for_low_level_ntfs_probe(
        root
    )


def _hold_manifests(
    guard: win32.PrivateMetadataMutationGuard,
) -> None:
    guard.hold_chain(guard.archive_root / "objects" / "manifests")


def _dispose_source(
    guard: win32.PrivateMetadataMutationGuard,
    source: win32.Win32BoundFile,
    *,
    locks: win32.PrivateMetadataLockPair,
) -> None:
    residue = win32.handoff_to_residue_authority(guard, source)
    win32.dispose_bound_residue(guard, residue, locks=locks)


def _create_directory_reparse_link(target: Path, link: Path) -> str:
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except OSError:
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            pytest.skip("directory reparse-link creation unavailable")
        return "junction"


def _remove_directory_reparse_link(link: Path, kind: str) -> None:
    if kind == "symlink":
        link.unlink()
    else:
        os.rmdir(link)


def test_exact_public_profile_and_path_literals() -> None:
    assert (
        win32.WINDOWS_NTFS_MUTATION_PROFILE
        == "windows_ntfs_win32_process_interruption/v0.1"
    )
    assert (
        win32.OBJECT_MANIFEST_LOCK_RELATIVE_PATH
        == "objects/manifests/.files.jsonl.lock"
    )
    assert (
        win32.PRIVATE_METADATA_LOCK_RELATIVE_PATH
        == "objects/manifests/.private-source-metadata.jsonl.lock"
    )
    assert (
        win32.PRIVATE_JOURNAL_RELATIVE_PATH
        == "objects/manifests/.private-source-metadata-write.journal.json"
    )
    assert (
        win32.PRIVATE_MANIFEST_RELATIVE_PATH
        == "objects/manifests/private-source-metadata.jsonl"
    )
    assert (
        win32.PRIVATE_RECEIPT_DIRECTORY_RELATIVE_PATH
        == "receipts/objects/private-source-metadata"
    )


def test_exact_access_and_share_profiles() -> None:
    assert win32.FileHandleProfile.AUTHORITY_READ.value == (
        0x80000000 | 0x00000080,
        0x00000001,
    )
    assert win32.FileHandleProfile.COORDINATION_LOCK.value == (
        0x80000000 | 0x40000000 | 0x00000080,
        0x00000001 | 0x00000002,
    )
    assert win32.FileHandleProfile.MUTATION_SOURCE.value == (
        0x80000000 | 0x40000000 | 0x00010000 | 0x00000080,
        0x00000001,
    )
    assert win32.FileHandleProfile.NARROW_READ.value == (
        0x80000000 | 0x00000080,
        0x00000001,
    )
    assert win32.FileHandleProfile.TRANSITIONAL_READ.value == (
        0x80000000 | 0x00000080,
        0x00000001 | 0x00000002 | 0x00000004,
    )
    assert win32.FileHandleProfile.RESIDUE_DISPOSITION.value == (
        0x80000000 | 0x00010000 | 0x00000080,
        0x00000001,
    )


def test_owned_paths_are_exact_and_authority_key_derived() -> None:
    key = "a" * 64
    assert win32.owned_temp_relative_path(
        win32.OwnedTempKind.JOURNAL,
        key,
    ) == (
        "objects/manifests/"
        f".private-source-metadata-write.{key}.journal.tmp"
    )
    assert win32.owned_temp_relative_path(
        win32.OwnedTempKind.MANIFEST,
        key,
    ) == (
        "objects/manifests/"
        f".private-source-metadata-write.{key}.manifest.tmp"
    )
    assert win32.owned_temp_relative_path(
        win32.OwnedTempKind.RECEIPT,
        key,
    ) == (
        "receipts/objects/private-source-metadata/"
        f".{key}.receipt.tmp"
    )
    assert win32.receipt_relative_path(key) == (
        "receipts/objects/private-source-metadata/"
        f"{key}.json"
    )
    for invalid in (
        "A" * 64,
        "a" * 63,
        "a" * 65,
        "../" + ("a" * 64),
        "g" * 64,
    ):
        with pytest.raises(
            ValueError,
            match="private_metadata_authority_key_invalid",
        ):
            win32.owned_temp_relative_path(
                win32.OwnedTempKind.JOURNAL,
                invalid,
            )


def test_non_windows_refusal_is_content_free_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "not-created"
    monkeypatch.setattr(win32, "_WINDOWS_AVAILABLE", False)
    status = win32.approval_support_status(missing)
    assert status == win32.ApprovalSupportStatus(
        supported=False,
        reason="private_metadata_approval_platform_not_supported",
        mutation_platform_profile=(
            "windows_ntfs_win32_process_interruption/v0.1"
        ),
        filesystem_name=None,
        local_volume=None,
    )
    assert not missing.exists()
    with pytest.raises(win32.Win32SafetyError) as captured:
        win32.PrivateMetadataMutationGuard(missing)
    assert captured.value.reason == (
        "private_metadata_approval_platform_not_supported"
    )
    assert str(captured.value) == captured.value.reason
    assert str(missing) not in str(captured.value)
    assert not missing.exists()


def test_error_surface_never_reflects_a_private_path() -> None:
    private_canary = r"C:\private\person-name-secret-token"
    error = win32.Win32SafetyError(
        win32.FINAL_VERIFICATION_FAILED,
        operation="synthetic",
        winerror=32,
    )
    assert str(error) == "private_metadata_final_verification_failed"
    assert private_canary not in str(error)


@WINDOWS_NTFS
def test_current_runner_reports_ntfs_and_production_approval_is_open(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    status = win32.approval_support_status(root)
    _require_ntfs(root)
    assert status.supported is True
    assert status.reason is None
    assert status.filesystem_name == "NTFS"
    assert status.local_volume is True
    with win32.PrivateMetadataMutationGuard(root) as guard:
        assert guard.archive_root == root
        assert guard.held_paths == (root,)


@WINDOWS_NTFS
def test_guard_holds_every_identity_and_denies_directory_rename(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    objects = root / "objects"
    moved = root / "objects-moved"
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        assert guard.held_paths == (
            root,
            root / "objects",
            root / "objects" / "manifests",
        )
        guard.validate_all()
        with pytest.raises(OSError) as captured:
            os.rename(objects, moved)
        assert captured.value.winerror in {5, 32}
        guard.validate_all()
    os.rename(objects, moved)
    os.rename(moved, objects)


@WINDOWS_NTFS
def test_guard_raw_close_failure_retains_exact_map_for_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    guard = _probe_guard(root)
    _hold_manifests(guard)
    handles_before = dict(guard._handles)
    paths_before = dict(guard._paths)
    identities_before = dict(guard._identities)
    order_before = list(guard._order)
    target_handle = handles_before[order_before[-1]]
    api = win32._api()
    original_close = api.close_handle
    target_attempts = 0

    def fail_target_once(handle: int) -> object:
        nonlocal target_attempts
        if int(handle) == int(target_handle):
            target_attempts += 1
            if target_attempts == 1:
                ctypes.set_last_error(5)
                return False
        return original_close(handle)

    monkeypatch.setattr(api, "close_handle", fail_target_once)
    with pytest.raises(win32.Win32SafetyError) as captured:
        guard.close()
    assert captured.value.reason == (
        win32.MUTATION_GUARD_IDENTITY_CHANGED
    )
    assert captured.value.operation == "mutation_guard_close"
    assert guard._closed is False
    assert guard._handles == handles_before
    assert guard._paths == paths_before
    assert guard._identities == identities_before
    assert guard._order == order_before

    guard.close()
    assert target_attempts == 2
    assert guard._closed is True
    assert guard._handles == {}
    assert guard._paths == {}
    assert guard._identities == {}
    assert guard._order == []


@WINDOWS_NTFS
def test_guard_rejects_final_component_reparse_directory(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    real = root / "real"
    real.mkdir()
    linked = root / "linked"
    kind = _create_directory_reparse_link(real, linked)
    try:
        with _probe_guard(root) as guard:
            with pytest.raises(win32.Win32SafetyError) as captured:
                guard.hold_directory(linked)
            assert captured.value.reason == (
                "private_metadata_mutation_guard_identity_changed"
            )
            assert linked.exists()
    finally:
        _remove_directory_reparse_link(linked, kind)


@WINDOWS_NTFS
def test_object_manifest_lock_directory_bootstrap_binds_exact_chain_before_lock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    _require_ntfs(root)
    with _probe_guard(root) as guard:
        object_identity, manifests_identity = (
            win32.bootstrap_object_manifest_lock_directories(guard)
        )
        assert guard.held_paths == (
            root,
            root / "objects",
            root / "objects" / "manifests",
        )
        assert guard.validate_directory(root / "objects") == object_identity
        assert (
            guard.validate_directory(root / "objects" / "manifests")
            == manifests_identity
        )
        object_lock = win32.PersistentCoordinationLock(
            guard,
            win32.CoordinationLockKind.OBJECT_MANIFEST,
        )
        object_lock.acquire()
        try:
            object_lock.validate()
            assert object_lock.created is True
        finally:
            object_lock.release()
    assert (
        root / win32.OBJECT_MANIFEST_LOCK_RELATIVE_PATH
    ).is_file()


@WINDOWS_NTFS
def test_object_manifest_bootstrap_does_not_weaken_general_directory_creator(
    tmp_path: Path,
) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    _require_ntfs(root)
    with _probe_guard(root) as guard:
        win32.bootstrap_object_manifest_lock_directories(guard)
        with pytest.raises(win32.Win32SafetyError) as captured:
            win32.create_guarded_directory(guard, root / "receipts")
        assert captured.value.reason == (
            "private_metadata_lock_identity_changed"
        )
        assert captured.value.operation == (
            "private_metadata_lock_pair_required"
        )
    assert not (root / "receipts").exists()


@WINDOWS_NTFS
def test_object_manifest_lock_directory_bootstrap_reopens_safe_race_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    _require_ntfs(root)
    api = win32._api()
    create_directory = api.create_directory
    calls = 0

    def race_once(path: str, security_attributes: object) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            (root / "objects").mkdir()
            ctypes.set_last_error(
                win32.win32_error_constants()["ERROR_ALREADY_EXISTS"]
            )
            return 0
        return int(create_directory(path, security_attributes))

    monkeypatch.setattr(api, "create_directory", race_once)
    with _probe_guard(root) as guard:
        win32.bootstrap_object_manifest_lock_directories(guard)
        assert guard.held_paths == (
            root,
            root / "objects",
            root / "objects" / "manifests",
        )
        guard.validate_all()
    assert calls == 2


@WINDOWS_NTFS
@pytest.mark.parametrize(
    ("relative_path", "expected_held_paths"),
    [
        ("objects", ("",)),
        ("objects/manifests", ("", "objects")),
    ],
)
def test_object_manifest_lock_directory_bootstrap_rejects_reparse_escape(
    tmp_path: Path,
    relative_path: str,
    expected_held_paths: tuple[str, ...],
) -> None:
    root = tmp_path / "archive"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    _require_ntfs(root)
    link = root / Path(relative_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    kind = _create_directory_reparse_link(outside, link)
    try:
        with _probe_guard(root) as guard:
            with pytest.raises(win32.Win32SafetyError) as captured:
                win32.bootstrap_object_manifest_lock_directories(guard)
            assert captured.value.reason == (
                "private_metadata_mutation_guard_identity_changed"
            )
            assert guard.held_paths == tuple(
                root if not value else root / Path(value)
                for value in expected_held_paths
            )
    finally:
        _remove_directory_reparse_link(link, kind)
    assert list(outside.iterdir()) == []


@WINDOWS_NTFS
def test_persistent_lock_prefix_and_pair_lifecycle(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    object_lock_path = root / win32.OBJECT_MANIFEST_LOCK_RELATIVE_PATH
    private_lock_path = root / win32.PRIVATE_METADATA_LOCK_RELATIVE_PATH
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        object_lock = win32.PersistentCoordinationLock(
            guard,
            win32.CoordinationLockKind.OBJECT_MANIFEST,
        )
        object_lock.acquire()
        first_identity = object_lock.validate()
        assert object_lock.created is True
        assert object_lock.bound is not None
        assert object_lock.bound.read_all(max_bytes=0) == b""
        assert object_lock_path.stat().st_nlink == 1
        assert not private_lock_path.exists()
        object_lock.release()

        with win32.PrivateMetadataLockPair(guard) as pair:
            object_identity, private_identity = pair.validate()
            assert object_identity == first_identity
            assert private_identity != object_identity
            assert pair.object_manifest.created is False
            assert pair.private_metadata.created is True
            assert pair.object_manifest.bound is not None
            assert pair.private_metadata.bound is not None
            assert pair.object_manifest.bound.read_all(max_bytes=0) == b""
            assert pair.private_metadata.bound.read_all(max_bytes=0) == b""
            assert object_lock_path.stat().st_nlink == 1
            assert private_lock_path.stat().st_nlink == 1
            with pytest.raises(OSError) as captured:
                os.remove(object_lock_path)
            assert captured.value.winerror in {5, 32}
            pair.validate()
    assert object_lock_path.exists()
    assert private_lock_path.exists()
    assert object_lock_path.read_bytes() == b""
    assert private_lock_path.read_bytes() == b""


@WINDOWS_NTFS
def test_mutation_requires_both_locks(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with pytest.raises(win32.Win32SafetyError) as captured:
            win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex="b" * 64,
                data=b"x",
            )
        assert captured.value.reason == (
            "private_metadata_lock_identity_changed"
        )
        assert captured.value.operation == (
            "private_metadata_lock_pair_required"
        )


@WINDOWS_NTFS
def test_guarded_receipt_directory_bootstrap_is_exact_and_persistent(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            receipts = root / "receipts"
            objects = receipts / "objects"
            private = objects / "private-source-metadata"
            win32.create_guarded_directory(guard, receipts)
            win32.create_guarded_directory(guard, objects)
            win32.create_guarded_directory(guard, private)
            assert private.is_dir()
            assert list(private.iterdir()) == []
            assert guard.is_held(receipts)
            assert guard.is_held(objects)
            assert guard.is_held(private)
            guard.validate_all()
    assert (root / "receipts" / "objects").is_dir()
    assert (
        root
        / "receipts"
        / "objects"
        / "private-source-metadata"
    ).is_dir()


@WINDOWS_NTFS
def test_create_new_temp_flushes_and_denies_substitution_profiles(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "c" * 64
    relative = win32.owned_temp_relative_path(
        win32.OwnedTempKind.MANIFEST,
        key,
    )
    path = root / Path(relative)
    data = b'{"synthetic":true}\n'
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            assert source.information().link_count == 1
            assert source.read_all(max_bytes=len(data)) == data

            transitional = win32.open_bound_file(
                guard,
                relative,
                profile=win32.FileHandleProfile.TRANSITIONAL_READ,
            )
            assert transitional.identity == source.identity
            transitional.close()

            with pytest.raises(win32.Win32SafetyError) as narrow_failure:
                win32.open_bound_file(
                    guard,
                    relative,
                    profile=win32.FileHandleProfile.NARROW_READ,
                )
            assert narrow_failure.value.winerror == 32

            for attempt in (
                lambda: path.open("r+b"),
                lambda: os.remove(path),
                lambda: os.rename(path, path.with_suffix(".swapped")),
                ):
                    with pytest.raises(OSError) as captured:
                        attempt()
                    assert (
                        captured.value.winerror in {5, 32}
                        or captured.value.errno == 13
                    )

            with pytest.raises(win32.Win32SafetyError) as duplicate:
                win32.materialize_owned_temp(
                    guard,
                    kind=win32.OwnedTempKind.MANIFEST,
                    authority_key_hex=key,
                    data=data,
                )
            assert duplicate.value.reason == (
                "private_metadata_owned_temp_materialization_failed"
            )
            assert duplicate.value.winerror == 80
            _dispose_source(guard, source, locks=locks)
            assert not path.exists()


@WINDOWS_NTFS
def test_owned_manifest_temp_accepts_one_pass_bounded_stream(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "6" * 64
    chunks = (
        b'{"row":1}\n',
        b'{"row":2}\n',
        b'{"row":3}\n',
    )
    expected = b"".join(chunks)
    yielded: list[int] = []

    def one_pass() -> object:
        for index, chunk in enumerate(chunks):
            yielded.append(index)
            yield chunk

    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=one_pass(),
                expected_byte_count=len(expected),
                expected_sha256=(
                    "sha256:" + hashlib.sha256(expected).hexdigest()
                ),
            )
            assert yielded == [0, 1, 2]
            assert list(
                source.iter_chunks(
                    max_bytes=len(expected),
                    chunk_size=5,
                )
            ) == [
                expected[index : index + 5]
                for index in range(0, len(expected), 5)
            ]
            assert source.read_all(max_bytes=len(expected)) == expected
            _dispose_source(guard, source, locks=locks)


@WINDOWS_NTFS
def test_fixed_journal_hardlink_publication_is_exact_one_two_one(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "d" * 64
    data = b'{"journal":"synthetic"}\n'
    source_path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.JOURNAL,
            key,
        )
    )
    final_path = root / win32.PRIVATE_JOURNAL_RELATIVE_PATH
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.JOURNAL,
                authority_key_hex=key,
                data=data,
            )
            original_identity = source.identity
            final = win32.publish_hard_link(
                guard,
                source,
                destination_relative_path=(
                    win32.PRIVATE_JOURNAL_RELATIVE_PATH
                ),
                survivor_profile=(
                    win32.FileHandleProfile.RESIDUE_DISPOSITION
                ),
                expected_bytes=data,
            )
            assert source.closed is True
            assert not source_path.exists()
            assert final.identity == original_identity
            assert final.information().link_count == 1
            assert final.read_all(max_bytes=len(data)) == data
            win32.dispose_bound_residue(guard, final, locks=locks)
            assert not final_path.exists()


@WINDOWS_NTFS
def test_hardlink_publication_never_overwrites_planted_destination(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    planted = b'{"planted":"evidence"}\n'
    final_path = root / win32.PRIVATE_JOURNAL_RELATIVE_PATH
    final_path.write_bytes(planted)
    key = "e" * 64
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.JOURNAL,
                authority_key_hex=key,
                data=b'{"new":"journal"}\n',
            )
            with pytest.raises(win32.Win32SafetyError) as captured:
                win32.publish_hard_link(
                    guard,
                    source,
                    destination_relative_path=(
                        win32.PRIVATE_JOURNAL_RELATIVE_PATH
                    ),
                    survivor_profile=(
                        win32.FileHandleProfile.RESIDUE_DISPOSITION
                    ),
                    expected_bytes=b'{"new":"journal"}\n',
                )
            assert captured.value.reason == (
                "private_metadata_hardlink_publication_failed"
            )
            assert final_path.read_bytes() == planted
            _dispose_source(guard, source, locks=locks)


@WINDOWS_NTFS
def test_receipt_hardlink_hands_to_narrow_authority(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "f" * 64
    data = b'{"receipt":"synthetic"}\n'
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            receipts = root / "receipts"
            objects = receipts / "objects"
            private = objects / "private-source-metadata"
            win32.create_guarded_directory(guard, receipts)
            win32.create_guarded_directory(guard, objects)
            win32.create_guarded_directory(guard, private)
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.RECEIPT,
                authority_key_hex=key,
                data=data,
            )
            final = win32.publish_hard_link(
                guard,
                source,
                destination_relative_path=win32.receipt_relative_path(key),
                survivor_profile=win32.FileHandleProfile.NARROW_READ,
                expected_bytes=data,
            )
            assert final.profile is win32.FileHandleProfile.NARROW_READ
            assert final.information().link_count == 1
            assert final.read_all(max_bytes=len(data)) == data
            assert not (
                private / f".{key}.receipt.tmp"
            ).exists()
            final.close()
    assert (root / win32.receipt_relative_path(key)).read_bytes() == data


@WINDOWS_NTFS
def test_disabled_manifest_replacement_gate_is_closed_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    after_bytes = b'{"row":1}\n'
    authority_key = "1" * 64
    final_path = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    monkeypatch.setattr(
        win32,
        "_MINIMAL_RENAME_PROFILE_APPROVAL_ENABLED",
        False,
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=authority_key,
                data=after_bytes,
            )
            with pytest.raises(win32.Win32SafetyError) as captured:
                win32.replace_private_manifest(
                    guard,
                    source,
                    authority_key_hex=authority_key,
                    replace_if_exists=False,
                    before_authority=None,
                    expected_bytes=after_bytes,
                )
            assert captured.value.reason == (
                "private_metadata_required_win32_primitive_unavailable"
            )
            assert captured.value.operation == (
                "file_rename_info_minimal_buffer_hazard"
            )
            assert source.closed is False
            assert not final_path.exists()
            _dispose_source(guard, source, locks=locks)


@WINDOWS_NTFS
def test_manifest_replacement_rejects_other_owned_temp_families_before_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    accepted_key = "a" * 64
    other_key = "b" * 64
    data = b'{"synthetic":"wrong-owned-temp-family"}\n'
    final_path = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    api = win32._api()
    original_set_file_information = api.set_file_information
    rename_calls: list[tuple[int, int]] = []

    def reject_unexpected_rename(
        handle: int,
        information_class: int,
        buffer: object,
        buffer_size: int,
    ) -> object:
        if information_class == win32._FILE_RENAME_INFO_CLASS:
            rename_calls.append((handle, buffer_size))
            raise AssertionError("rename API reached for substituted temp")
        return original_set_file_information(
            handle,
            information_class,
            buffer,
            buffer_size,
        )

    monkeypatch.setattr(
        api,
        "set_file_information",
        reject_unexpected_rename,
    )

    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            receipts = root / "receipts"
            receipt_objects = receipts / "objects"
            receipt_private = (
                receipt_objects / "private-source-metadata"
            )
            win32.create_guarded_directory(guard, receipts)
            win32.create_guarded_directory(guard, receipt_objects)
            win32.create_guarded_directory(guard, receipt_private)
            candidates = (
                win32.materialize_owned_temp(
                    guard,
                    kind=win32.OwnedTempKind.JOURNAL,
                    authority_key_hex=accepted_key,
                    data=data,
                ),
                win32.materialize_owned_temp(
                    guard,
                    kind=win32.OwnedTempKind.RECEIPT,
                    authority_key_hex=accepted_key,
                    data=data,
                ),
                win32.materialize_owned_temp(
                    guard,
                    kind=win32.OwnedTempKind.MANIFEST,
                    authority_key_hex=other_key,
                    data=data,
                ),
            )
            for source in candidates:
                with pytest.raises(win32.Win32SafetyError) as captured:
                    win32.replace_private_manifest(
                        guard,
                        source,
                        authority_key_hex=accepted_key,
                        replace_if_exists=False,
                        before_authority=None,
                        expected_bytes=data,
                    )
                assert captured.value.reason == (
                    "private_metadata_owned_temp_substituted"
                )
                assert captured.value.operation == (
                    "manifest_source_not_canonical_owned_temp"
                )
                assert source.closed is False
                _dispose_source(guard, source, locks=locks)

    assert rename_calls == []
    assert not final_path.exists()


@WINDOWS_NTFS
def test_production_manifest_replacement_uses_bound_source_and_logical_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    authority_key = "c" * 64
    after_bytes = b'{"synthetic":"production-wrapper"}\n'
    source_path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            authority_key,
        )
    )
    final_path = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    poisoned_path = Path(str(final_path) + ".poison")
    duplicated_path = Path(str(final_path) + ".jsonl")
    api = win32._api()
    original_set_file_information = api.set_file_information
    calls: list[dict[str, object]] = []

    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=authority_key,
                data=after_bytes,
            )
            source_identity = source.identity
            source_handle = source.raw_handle
            assert source.path == source_path

            def instrument_set_file_information(
                handle: int,
                information_class: int,
                buffer: object,
                buffer_size: int,
            ) -> object:
                if information_class == win32._FILE_RENAME_INFO_CLASS:
                    layout = api.FileRenameInfoLayout
                    file_name_length = ctypes.c_uint32.from_buffer(
                        buffer,
                        layout.file_name_length.offset,
                    ).value
                    file_name_offset = int(layout.file_name.offset)
                    logical_size = (
                        file_name_offset + file_name_length
                    )
                    calls.append(
                        {
                            "handle": handle,
                            "information_class": information_class,
                            "buffer_size": buffer_size,
                            "backing_size": len(buffer),
                            "file_name_length": file_name_length,
                            "logical_size": logical_size,
                            "file_name": bytes(
                                buffer[
                                    file_name_offset:logical_size
                                ]
                            ),
                            "nul_guard": bytes(
                                buffer[
                                    logical_size : logical_size + 2
                                ]
                            ),
                        }
                    )
                return original_set_file_information(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                )

            monkeypatch.setattr(
                api,
                "set_file_information",
                instrument_set_file_information,
            )
            final = win32.replace_private_manifest(
                guard,
                source,
                authority_key_hex=authority_key,
                replace_if_exists=False,
                before_authority=None,
                expected_bytes=after_bytes,
            )

            assert len(calls) == 1
            call = calls[0]
            assert call["handle"] == source_handle
            assert call["information_class"] == (
                win32._FILE_RENAME_INFO_CLASS
            )
            assert call["buffer_size"] == call["logical_size"]
            assert call["backing_size"] == call["logical_size"] + 2
            assert call["file_name"] == win32._extended_path(
                final_path
            ).encode("utf-16-le")
            assert call["file_name_length"] == len(call["file_name"])
            assert call["nul_guard"] == b"\x00\x00"
            assert final.path == final_path
            assert final.identity == source_identity
            assert final.read_all(
                max_bytes=len(after_bytes)
            ) == after_bytes
            assert source.closed is True
            assert not source_path.exists()
            assert not poisoned_path.exists()
            assert not duplicated_path.exists()
            assert sorted(
                path.name
                for path in (root / "objects" / "manifests").iterdir()
                if not path.name.endswith(".lock")
            ) == ["private-source-metadata.jsonl"]
            final.close()

    assert final_path.read_bytes() == after_bytes


@WINDOWS_NTFS
def test_file_rename_info_buffer_has_exact_logical_size_and_nul_guard(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    destination = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    rename_info = win32.file_rename_info_buffer(
        destination,
        replace_if_exists=True,
    )
    api = win32._api()
    layout = api.FileRenameInfoLayout
    encoded = win32._extended_path(destination).encode("utf-16-le")
    assert rename_info.file_name_offset == layout.file_name.offset
    assert rename_info.file_name_length == len(encoded)
    assert rename_info.logical_size == (
        rename_info.file_name_offset + len(encoded)
    )
    assert rename_info.backing_size == rename_info.logical_size + 2
    assert len(rename_info.backing) == rename_info.backing_size
    assert rename_info.api_buffer_size == rename_info.logical_size
    assert ctypes.c_ubyte.from_buffer(
        rename_info.backing,
        layout.replace_if_exists.offset,
    ).value == 1
    assert ctypes.c_void_p.from_buffer(
        rename_info.backing,
        layout.root_directory.offset,
    ).value is None
    assert ctypes.c_uint32.from_buffer(
        rename_info.backing,
        layout.file_name_length.offset,
    ).value == len(encoded)
    assert bytes(
        rename_info.backing[
            rename_info.file_name_offset : rename_info.logical_size
        ]
    ) == encoded
    assert not encoded.endswith(b"\x00\x00")
    assert bytes(
        rename_info.backing[
            rename_info.logical_size : rename_info.backing_size
        ]
    ) == b"\x00\x00"


@WINDOWS_NTFS
def test_nul_guard_prevents_adjacent_duplicate_suffix_consumption(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    intended = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    poisoned = Path(str(intended) + ".poison")
    duplicated = Path(str(intended) + ".jsonl")
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex="7" * 64,
                data=b'{"synthetic":"poison-tail-probe"}\n',
            )
            rename_info = win32.file_rename_info_buffer(
                intended,
                replace_if_exists=False,
            )
            poison_tail = ".poison".encode("utf-16-le") + b"\x00\x00"
            backing = ctypes.create_string_buffer(
                rename_info.backing_size + len(poison_tail)
            )
            ctypes.memmove(
                ctypes.addressof(backing),
                ctypes.addressof(rename_info.backing),
                rename_info.backing_size,
            )
            ctypes.memmove(
                ctypes.addressof(backing) + rename_info.backing_size,
                poison_tail,
                len(poison_tail),
            )
            assert ctypes.c_uint32.from_buffer(
                backing,
                win32._api().FileRenameInfoLayout.file_name_length.offset,
            ).value == rename_info.file_name_length
            assert bytes(
                backing[
                    rename_info.logical_size : rename_info.backing_size
                ]
            ) == b"\x00\x00"

            ctypes.set_last_error(0)
            succeeded = win32._api().set_file_information(
                source.raw_handle,
                win32._FILE_RENAME_INFO_CLASS,
                backing,
                rename_info.api_buffer_size,
            )
            assert succeeded
            source.close()
            assert intended.exists()
            assert not poisoned.exists()
            assert not duplicated.exists()
            assert sorted(
                path.name
                for path in (root / "objects" / "manifests").iterdir()
                if not path.name.endswith(".lock")
            ) == ["private-source-metadata.jsonl"]


@WINDOWS_NTFS
def test_present_target_handle_blocks_ordinary_file_rename_info(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    final_path = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    final_path.write_bytes(b'{"old":true}\n')
    new_bytes = b'{"new":true}\n'
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            old_transitional = win32.open_bound_file(
                guard,
                win32.PRIVATE_MANIFEST_RELATIVE_PATH,
                profile=win32.FileHandleProfile.TRANSITIONAL_READ,
            )
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex="3" * 64,
                data=new_bytes,
            )
            rename_info = win32.file_rename_info_buffer(
                final_path,
                replace_if_exists=True,
            )
            ctypes.set_last_error(0)
            succeeded = win32._api().set_file_information(
                source.raw_handle,
                win32._FILE_RENAME_INFO_CLASS,
                rename_info.backing,
                rename_info.api_buffer_size,
            )
            assert not succeeded
            assert ctypes.get_last_error() == 5
            assert old_transitional.read_all(
                max_bytes=len(b'{"old":true}\n')
            ) == b'{"old":true}\n'
            old_transitional.close()
            _dispose_source(guard, source, locks=locks)
    assert final_path.read_bytes() == b'{"old":true}\n'


@WINDOWS_NTFS
def test_absent_no_replace_preserves_raced_in_target_with_error_183(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    final_path = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    planted = b'{"raced_in":"preserve"}\n'
    new_bytes = b'{"new":"must_not_replace"}\n'
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex="4" * 64,
                data=new_bytes,
            )
            assert win32.path_is_absent(
                guard,
                final_path,
                reason=win32.MANIFEST_REPLACEMENT_FAILED,
                operation="synthetic_absence",
            )
            final_path.write_bytes(planted)
            rename_info = win32.file_rename_info_buffer(
                final_path,
                replace_if_exists=False,
            )
            ctypes.set_last_error(0)
            succeeded = win32._api().set_file_information(
                source.raw_handle,
                win32._FILE_RENAME_INFO_CLASS,
                rename_info.backing,
                rename_info.api_buffer_size,
            )
            assert not succeeded
            assert ctypes.get_last_error() == 183
            assert final_path.read_bytes() == planted
            _dispose_source(guard, source, locks=locks)


@WINDOWS_NTFS
def test_residue_disposition_deletes_only_retained_identity(
    tmp_path: Path,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "5" * 64
    relative = win32.owned_temp_relative_path(
        win32.OwnedTempKind.MANIFEST,
        key,
    )
    other = root / "objects" / "manifests" / "unowned-evidence"
    other.write_bytes(b"preserve")
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=b"owned",
            )
            residue = win32.handoff_to_residue_authority(
                guard,
                source,
            )
            win32.dispose_bound_residue(guard, residue, locks=locks)
            assert not (root / Path(relative)).exists()
            assert other.read_bytes() == b"preserve"


@WINDOWS_NTFS
@pytest.mark.parametrize(
    ("fault_mode", "checkpoint"),
    (
        ("zero_write", win32.MutationCheckpoint.OWNED_TEMP_WRITE),
        ("partial_then_fail", win32.MutationCheckpoint.OWNED_TEMP_WRITE),
        ("flush", win32.MutationCheckpoint.OWNED_TEMP_FLUSH),
    ),
)
def test_owned_temp_fault_transfers_exact_live_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_mode: str,
    checkpoint: win32.MutationCheckpoint,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "7" * 64
    relative = win32.owned_temp_relative_path(
        win32.OwnedTempKind.MANIFEST,
        key,
    )
    path = root / Path(relative)
    data = b"0123456789abcdef"
    api = win32._api()
    original_write = api.write_file
    original_flush = api.flush_file_buffers
    write_calls = 0

    if fault_mode in {"zero_write", "partial_then_fail"}:

        def fault_write(
            handle: int,
            buffer: object,
            requested: int,
            written_pointer: object,
            overlapped: object,
        ) -> object:
            nonlocal write_calls
            write_calls += 1
            written = ctypes.cast(
                written_pointer,
                ctypes.POINTER(api._wintypes.DWORD),
            )
            if fault_mode == "zero_write":
                written.contents.value = 0
                return True
            if write_calls == 1:
                return original_write(
                    handle,
                    buffer,
                    max(1, requested // 2),
                    written_pointer,
                    overlapped,
                )
            ctypes.set_last_error(5)
            return False

        monkeypatch.setattr(api, "write_file", fault_write)
    else:

        def fault_flush(handle: int) -> bool:
            del handle
            ctypes.set_last_error(5)
            return False

        monkeypatch.setattr(api, "flush_file_buffers", fault_flush)

    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.materialize_owned_temp(
                    guard,
                    kind=win32.OwnedTempKind.MANIFEST,
                    authority_key_hex=key,
                    data=data,
                )
            failure = captured.value
            assert failure.checkpoint is checkpoint
            assert failure.effect is win32.MutationEffect.STATE_CHANGE_PROVED
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].role == "manifest_temp"
            assert transfers[0].bound.closed is False
            with pytest.raises(RuntimeError):
                failure.take_authorities()
            if fault_mode == "flush":
                monkeypatch.setattr(
                    api,
                    "flush_file_buffers",
                    original_flush,
                )
            residue = win32.handoff_to_residue_authority(
                guard,
                transfers[0].bound,
            )
            win32.dispose_bound_residue(guard, residue, locks=locks)
            assert not path.exists()


@WINDOWS_NTFS
def test_create_new_api_failure_proves_no_name_and_no_obligation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "3" * 64
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    api = win32._api()
    original_create = api.create_file
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:

            def fail_create(*args: object) -> object:
                del args
                ctypes.set_last_error(5)
                return api.invalid_handle_value

            monkeypatch.setattr(api, "create_file", fail_create)
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.materialize_owned_temp(
                    guard,
                    kind=win32.OwnedTempKind.MANIFEST,
                    authority_key_hex=key,
                    data=b"never-created",
                )
            failure = captured.value
            assert (
                failure.checkpoint
                is win32.MutationCheckpoint.OWNED_TEMP_CREATE
            )
            assert failure.effect is win32.MutationEffect.NO_CHANGE_PROVED
            assert failure.take_authorities() == ()
            assert not path.exists()
            monkeypatch.setattr(api, "create_file", original_create)


@WINDOWS_NTFS
def test_create_new_post_open_refusal_transfers_raw_handle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "4" * 64
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    original_validate = win32._validate_regular_information
    injected = False

    def fail_post_create_validation(
        information: object,
        *,
        reason: str,
        operation: str,
        expected_link_count: int | None,
        expected_volume_serial: int | None,
    ) -> None:
        nonlocal injected
        if operation == "owned_temp_create_new" and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.OWNED_TEMP_MATERIALIZATION_FAILED,
                operation="owned_temp_post_create_validation",
            )
        original_validate(
            information,
            reason=reason,
            operation=operation,
            expected_link_count=expected_link_count,
            expected_volume_serial=expected_volume_serial,
        )

    monkeypatch.setattr(
        win32,
        "_validate_regular_information",
        fail_post_create_validation,
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.materialize_owned_temp(
                    guard,
                    kind=win32.OwnedTempKind.MANIFEST,
                    authority_key_hex=key,
                    data=b"created-before-refusal",
                )
            failure = captured.value
            assert injected
            assert (
                failure.checkpoint
                is win32.MutationCheckpoint.OWNED_TEMP_CREATE
            )
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_PROVED
            )
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].role == "manifest_temp"
            assert isinstance(
                transfers[0].bound,
                win32.Win32UnverifiedCreatedFile,
            )
            assert transfers[0].bound.closed is False
            assert path.exists()
            win32.dispose_unverified_created_file(
                guard,
                transfers[0].bound,
            )
            assert not path.exists()


@WINDOWS_NTFS
def test_unverified_created_close_fault_requires_terminal_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "f" * 64
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    original_validate = win32._validate_regular_information
    validation_injected = False

    def fail_post_create_validation(
        information: object,
        *,
        reason: str,
        operation: str,
        expected_link_count: int | None,
        expected_volume_serial: int | None,
    ) -> None:
        nonlocal validation_injected
        if operation == "owned_temp_create_new" and not validation_injected:
            validation_injected = True
            raise win32.Win32SafetyError(
                win32.OWNED_TEMP_MATERIALIZATION_FAILED,
                operation="owned_temp_post_create_validation",
            )
        original_validate(
            information,
            reason=reason,
            operation=operation,
            expected_link_count=expected_link_count,
            expected_volume_serial=expected_volume_serial,
        )

    monkeypatch.setattr(
        win32,
        "_validate_regular_information",
        fail_post_create_validation,
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            with pytest.raises(win32.Win32MutationFailure) as creation:
                win32.materialize_owned_temp(
                    guard,
                    kind=win32.OwnedTempKind.MANIFEST,
                    authority_key_hex=key,
                    data=b"created-before-refusal",
                )
            created = creation.value.take_authorities()[0].bound
            assert isinstance(created, win32.Win32UnverifiedCreatedFile)
            original_close = win32.Win32UnverifiedCreatedFile.close
            close_injected = False

            def fail_created_close(
                bound: win32.Win32UnverifiedCreatedFile,
                *,
                reason: str = win32.FINAL_VERIFICATION_FAILED,
                operation: str = "created_handle_close",
            ) -> None:
                nonlocal close_injected
                if operation == "unverified_created_file_close":
                    close_injected = True
                    raise win32.Win32SafetyError(
                        reason,
                        operation=operation,
                    )
                original_close(
                    bound,
                    reason=reason,
                    operation=operation,
                )

            monkeypatch.setattr(
                win32.Win32UnverifiedCreatedFile,
                "close",
                fail_created_close,
            )
            with pytest.raises(win32.Win32MutationFailure) as disposal:
                win32.dispose_unverified_created_file(guard, created)
            failure = disposal.value
            assert close_injected
            assert failure.reason == win32.RESIDUE_DISPOSITION_FAILED
            assert (
                failure.checkpoint is win32.MutationCheckpoint.RESIDUE_API
            )
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_PROVED
            )
            assert failure.terminal_release_required is True
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].bound is created
            assert transfers[0].terminal_release_first is True
            assert transfers[0].name_state == "delete_pending"
            win32.release_terminal_bound_authority(
                created,
                reason=failure.reason,
                operation="unverified_created_test_terminal",
            )
            assert created.closed is True
            assert not path.exists()
            locks.validate()
            guard.validate_all()


@WINDOWS_NTFS
@pytest.mark.parametrize(
    "fault_operation",
    (
        "hardlink_transitional_open",
        "hardlink_source_disposition",
        "hardlink_source_close",
        "hardlink_source_absence",
        "hardlink_survivor_handoff_reopen",
        "hardlink_transitional_close",
    ),
)
def test_hardlink_post_api_fault_transfers_every_live_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_operation: str,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "8" * 64
    data = b'{"journal":"fault-transfer"}\n'
    source_path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.JOURNAL,
            key,
        )
    )
    final_path = root / win32.PRIVATE_JOURNAL_RELATIVE_PATH
    original_open = win32._open_bound_file_absolute
    original_disposition = win32._set_disposition
    original_close = win32.Win32BoundFile.close
    original_absent = win32.path_is_absent
    injected = False
    faulted_close_bound: object | None = None

    def fault_open(*args: object, **kwargs: object) -> object:
        nonlocal injected
        if kwargs.get("operation") == fault_operation and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        return original_open(*args, **kwargs)

    def fault_disposition(
        bound: object,
        *,
        reason: str,
        operation: str,
    ) -> None:
        nonlocal injected
        if operation == fault_operation and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.RESIDUE_DISPOSITION_FAILED,
                operation=fault_operation,
            )
        original_disposition(
            bound,
            reason=reason,
            operation=operation,
        )

    def fault_close(
        bound: object,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal injected, faulted_close_bound
        if operation == fault_operation and not injected:
            injected = True
            faulted_close_bound = bound
            raise win32.Win32SafetyError(
                reason,
                operation=fault_operation,
            )
        original_close(bound, reason=reason, operation=operation)

    def fault_absent(
        guard: object,
        path: Path,
        *,
        reason: str,
        operation: str,
    ) -> bool:
        nonlocal injected
        if operation == fault_operation and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        return original_absent(
            guard,
            path,
            reason=reason,
            operation=operation,
        )

    monkeypatch.setattr(win32, "_open_bound_file_absolute", fault_open)
    monkeypatch.setattr(win32, "_set_disposition", fault_disposition)
    monkeypatch.setattr(win32.Win32BoundFile, "close", fault_close)
    monkeypatch.setattr(win32, "path_is_absent", fault_absent)

    transferred_bounds: list[win32.Win32BoundFile] = []
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.JOURNAL,
                authority_key_hex=key,
                data=data,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.publish_hard_link(
                    guard,
                    source,
                    destination_relative_path=(
                        win32.PRIVATE_JOURNAL_RELATIVE_PATH
                    ),
                    survivor_profile=(
                        win32.FileHandleProfile.RESIDUE_DISPOSITION
                    ),
                    expected_bytes=data,
                )
            failure = captured.value
            assert injected
            assert (
                failure.checkpoint
                is win32.MutationCheckpoint.HARDLINK_POSTCHECK
            )
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_PROVED
            )
            transfers = failure.take_authorities()
            assert transfers
            assert all(not transfer.bound.closed for transfer in transfers)
            if fault_operation == "hardlink_source_close":
                assert failure.reason == win32.RESIDUE_DISPOSITION_FAILED
                assert failure.terminal_release_required is True
                terminal = [
                    transfer
                    for transfer in transfers
                    if transfer.terminal_release_first
                ]
                assert len(terminal) == 1
                assert terminal[0].bound is source
                assert terminal[0].name_state == "delete_pending"
                survivors = [
                    transfer
                    for transfer in transfers
                    if transfer is not terminal[0]
                ]
                assert len(survivors) == 1
                assert (
                    survivors[0].expected_link_count_after_terminal_release
                    == 1
                )
                win32.release_terminal_bound_authority(source)
                assert source.closed is True
                assert not source_path.exists()
                survivor = survivors[0].bound
                survivor.expected_link_count = 1
                assert survivor.information().link_count == 1
            elif fault_operation == "hardlink_transitional_close":
                assert failure.reason == win32.FINAL_VERIFICATION_FAILED
                assert failure.terminal_release_required is True
                terminal = [
                    transfer
                    for transfer in transfers
                    if transfer.terminal_release_first
                ]
                assert len(terminal) == 1
                assert terminal[0].bound is faulted_close_bound
                assert terminal[0].name_state == "owned_present"
                survivors = [
                    transfer
                    for transfer in transfers
                    if transfer is not terminal[0]
                ]
                assert len(survivors) == 1
                assert survivors[0].bound is not terminal[0].bound
                win32.release_terminal_bound_authority(
                    terminal[0].bound,
                    reason=failure.reason,
                    operation="hardlink_transitional_test_terminal",
                )
                assert terminal[0].bound.closed is True
                assert (
                    survivors[0].bound.read_all(max_bytes=len(data))
                    == data
                )
            with pytest.raises(RuntimeError):
                failure.take_authorities()
            for transfer in transfers:
                if all(
                    existing is not transfer.bound
                    for existing in transferred_bounds
                ):
                    transferred_bounds.append(transfer.bound)
            assert source_path.exists() or final_path.exists()
            for bound in reversed(transferred_bounds):
                if not bound.closed:
                    original_close(
                        bound,
                        operation="fault_transfer_test_cleanup",
                    )
    source_path.unlink(missing_ok=True)
    final_path.unlink(missing_ok=True)


@WINDOWS_NTFS
@pytest.mark.parametrize(
    "fault_operation",
    (
        "manifest_transitional_open",
        "manifest_temp_absence",
        "manifest_renamed_source_close",
        "manifest_narrow_handoff_reopen",
        "manifest_transitional_close",
    ),
)
def test_manifest_post_api_fault_transfers_final_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_operation: str,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "9" * 64
    data = b'{"manifest":"fault-transfer"}\n'
    source_path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    final_path = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    original_open = win32._open_bound_file_absolute
    original_close = win32.Win32BoundFile.close
    original_absent = win32.path_is_absent
    injected = False
    faulted_close_bound: object | None = None

    def fault_open(*args: object, **kwargs: object) -> object:
        nonlocal injected
        if kwargs.get("operation") == fault_operation and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        return original_open(*args, **kwargs)

    def fault_close(
        bound: object,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal injected, faulted_close_bound
        if operation == fault_operation and not injected:
            injected = True
            faulted_close_bound = bound
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        original_close(bound, reason=reason, operation=operation)

    def fault_absent(
        guard: object,
        path: Path,
        *,
        reason: str,
        operation: str,
    ) -> bool:
        nonlocal injected
        if operation == fault_operation and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        return original_absent(
            guard,
            path,
            reason=reason,
            operation=operation,
        )

    monkeypatch.setattr(win32, "_open_bound_file_absolute", fault_open)
    monkeypatch.setattr(win32.Win32BoundFile, "close", fault_close)
    monkeypatch.setattr(win32, "path_is_absent", fault_absent)

    transferred_bounds: list[win32.Win32BoundFile] = []
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.replace_private_manifest(
                    guard,
                    source,
                    authority_key_hex=key,
                    replace_if_exists=False,
                    before_authority=None,
                    expected_bytes=data,
                )
            failure = captured.value
            assert injected
            assert (
                failure.checkpoint
                is win32.MutationCheckpoint.MANIFEST_POSTCHECK
            )
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_PROVED
            )
            transfers = failure.take_authorities()
            assert transfers
            assert {transfer.role for transfer in transfers} == {
                "private_manifest"
            }
            assert all(not transfer.bound.closed for transfer in transfers)
            if fault_operation in {
                "manifest_renamed_source_close",
                "manifest_transitional_close",
            }:
                assert failure.terminal_release_required is True
                terminal = [
                    transfer
                    for transfer in transfers
                    if transfer.terminal_release_first
                ]
                assert len(terminal) == 1
                assert terminal[0].bound is faulted_close_bound
                assert terminal[0].name_state == "renamed_final"
                assert len(transfers) == 2
                win32.release_terminal_bound_authority(
                    terminal[0].bound,
                    reason=failure.reason,
                    operation="manifest_close_test_terminal",
                )
                assert terminal[0].bound.closed is True
                assert final_path.read_bytes() == data
            with pytest.raises(RuntimeError):
                failure.take_authorities()
            for transfer in transfers:
                if all(
                    existing is not transfer.bound
                    for existing in transferred_bounds
                ):
                    transferred_bounds.append(transfer.bound)
            assert final_path.exists()
            assert not source_path.exists()
            for bound in reversed(transferred_bounds):
                if not bound.closed:
                    original_close(
                        bound,
                        operation="manifest_fault_transfer_test_cleanup",
                    )
    source_path.unlink(missing_ok=True)
    final_path.unlink(missing_ok=True)


@WINDOWS_NTFS
def test_manifest_old_target_close_fault_terminalizes_before_source_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "a" * 64
    before_bytes = b'{"manifest":"before"}\n'
    after_bytes = b'{"manifest":"after"}\n'
    final_path = root / win32.PRIVATE_MANIFEST_RELATIVE_PATH
    final_path.write_bytes(before_bytes)
    source_path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    original_close = win32.Win32BoundFile.close
    injected = False

    def fault_close(
        bound: object,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal injected
        if (
            operation == "manifest_old_target_boundary_close"
            and not injected
        ):
            injected = True
            raise win32.Win32SafetyError(
                reason,
                operation=operation,
            )
        original_close(bound, reason=reason, operation=operation)

    monkeypatch.setattr(win32.Win32BoundFile, "close", fault_close)
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            before = win32.open_bound_file(
                guard,
                win32.PRIVATE_MANIFEST_RELATIVE_PATH,
                profile=win32.FileHandleProfile.NARROW_READ,
            )
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=after_bytes,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.replace_private_manifest(
                    guard,
                    source,
                    authority_key_hex=key,
                    replace_if_exists=True,
                    before_authority=before,
                    expected_bytes=after_bytes,
                )
            failure = captured.value
            assert injected
            assert failure.reason == win32.MANIFEST_REPLACEMENT_FAILED
            assert (
                failure.checkpoint
                is win32.MutationCheckpoint.MANIFEST_PRECONDITION
            )
            assert failure.effect is win32.MutationEffect.NO_CHANGE_PROVED
            assert failure.terminal_release_required is True
            transfers = failure.take_authorities()
            assert len(transfers) == 2
            terminal = [
                transfer
                for transfer in transfers
                if transfer.terminal_release_first
            ]
            assert len(terminal) == 1
            assert terminal[0].bound is before
            assert terminal[0].role == "private_manifest"
            retained_source = next(
                transfer
                for transfer in transfers
                if transfer is not terminal[0]
            )
            assert retained_source.bound is source
            assert retained_source.role == "manifest_temp"
            win32.release_terminal_bound_authority(
                terminal[0].bound,
                reason=failure.reason,
                operation="manifest_old_target_test_terminal",
            )
            assert before.closed is True
            assert final_path.read_bytes() == before_bytes
            assert source.read_all(max_bytes=len(after_bytes)) == after_bytes
            _dispose_source(guard, source, locks=locks)
            assert not source_path.exists()
    final_path.unlink(missing_ok=True)


@WINDOWS_NTFS
@pytest.mark.parametrize(
    ("fault_operation", "expected_transfer_count"),
    (
        ("residue_handoff_transitional_reopen", 1),
        ("residue_handoff_current_close", 2),
        ("residue_handoff_open_reopen", 1),
        ("residue_handoff_transitional_close", 2),
    ),
)
def test_residue_handoff_fault_transfers_all_live_handles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_operation: str,
    expected_transfer_count: int,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "1" * 64
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    original_open = win32._open_bound_file_absolute
    original_close = win32.Win32BoundFile.close
    injected = False
    faulted_close_bound: object | None = None

    def fault_open(*args: object, **kwargs: object) -> object:
        nonlocal injected
        if kwargs.get("operation") == fault_operation and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        return original_open(*args, **kwargs)

    def fault_close(
        bound: object,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal injected, faulted_close_bound
        if operation == fault_operation and not injected:
            injected = True
            faulted_close_bound = bound
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        original_close(bound, reason=reason, operation=operation)

    monkeypatch.setattr(win32, "_open_bound_file_absolute", fault_open)
    monkeypatch.setattr(win32.Win32BoundFile, "close", fault_close)
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=b"handoff",
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.handoff_to_residue_authority(guard, source)
            failure = captured.value
            assert injected
            assert failure.checkpoint is win32.MutationCheckpoint.HANDOFF
            assert failure.effect is win32.MutationEffect.NO_CHANGE_PROVED
            transfers = failure.take_authorities()
            assert len(transfers) == expected_transfer_count
            assert {transfer.role for transfer in transfers} == {
                "manifest_temp"
            }
            assert all(not transfer.bound.closed for transfer in transfers)
            if fault_operation in {
                "residue_handoff_current_close",
                "residue_handoff_transitional_close",
            }:
                assert failure.terminal_release_required is True
                terminal = [
                    transfer
                    for transfer in transfers
                    if transfer.terminal_release_first
                ]
                assert len(terminal) == 1
                assert terminal[0].bound is faulted_close_bound
                win32.release_terminal_bound_authority(
                    terminal[0].bound,
                    reason=failure.reason,
                    operation="residue_handoff_test_terminal",
                )
                assert terminal[0].bound.closed is True
            for transfer in reversed(transfers):
                if not transfer.bound.closed:
                    original_close(
                        transfer.bound,
                        operation="residue_handoff_fault_test_cleanup",
                    )
    path.unlink(missing_ok=True)


@WINDOWS_NTFS
@pytest.mark.parametrize(
    ("fault_operation", "expected_transfer_count"),
    (
        ("narrow_handoff_open_reopen", 1),
        ("narrow_handoff_transitional_close", 2),
    ),
)
def test_narrow_handoff_fault_transfers_all_live_handles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_operation: str,
    expected_transfer_count: int,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    relative = win32.PRIVATE_MANIFEST_RELATIVE_PATH
    path = root / relative
    path.write_bytes(b"narrow-handoff")
    original_open = win32._open_bound_file_absolute
    original_close = win32.Win32BoundFile.close
    injected = False
    faulted_close_bound: object | None = None

    def fault_open(*args: object, **kwargs: object) -> object:
        nonlocal injected
        if kwargs.get("operation") == fault_operation and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        return original_open(*args, **kwargs)

    def fault_close(
        bound: object,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal injected, faulted_close_bound
        if operation == fault_operation and not injected:
            injected = True
            faulted_close_bound = bound
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        original_close(bound, reason=reason, operation=operation)

    monkeypatch.setattr(win32, "_open_bound_file_absolute", fault_open)
    monkeypatch.setattr(win32.Win32BoundFile, "close", fault_close)
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            transitional = win32.open_bound_file(
                guard,
                relative,
                profile=win32.FileHandleProfile.TRANSITIONAL_READ,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.handoff_to_narrow_authority(
                    guard,
                    transitional,
                )
            failure = captured.value
            assert injected
            assert failure.checkpoint is win32.MutationCheckpoint.HANDOFF
            transfers = failure.take_authorities()
            assert len(transfers) == expected_transfer_count
            assert {transfer.role for transfer in transfers} == {
                "private_manifest"
            }
            assert all(not transfer.bound.closed for transfer in transfers)
            if fault_operation == "narrow_handoff_transitional_close":
                assert failure.terminal_release_required is True
                terminal = [
                    transfer
                    for transfer in transfers
                    if transfer.terminal_release_first
                ]
                assert len(terminal) == 1
                assert terminal[0].bound is faulted_close_bound
                win32.release_terminal_bound_authority(
                    terminal[0].bound,
                    reason=failure.reason,
                    operation="narrow_handoff_test_terminal",
                )
                assert terminal[0].bound.closed is True
            for transfer in reversed(transfers):
                if not transfer.bound.closed:
                    original_close(
                        transfer.bound,
                        operation="narrow_handoff_fault_test_cleanup",
                    )
    path.unlink(missing_ok=True)


@WINDOWS_NTFS
@pytest.mark.parametrize(
    ("fault_operation", "expected_transfer_count"),
    (
        ("twin_survivor_transitional_reopen", 2),
        ("twin_survivor_narrow_close", 3),
        ("twin_residue_narrow_close", 2),
        ("twin_residue_disposition_open", 1),
    ),
)
def test_twin_handoff_fault_transfers_all_live_handles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_operation: str,
    expected_transfer_count: int,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "2" * 64
    data = b"twin-handoff"
    temp_relative = win32.owned_temp_relative_path(
        win32.OwnedTempKind.JOURNAL,
        key,
    )
    temp_path = root / Path(temp_relative)
    final_path = root / win32.PRIVATE_JOURNAL_RELATIVE_PATH
    temp_path.write_bytes(data)
    os.link(temp_path, final_path)
    original_open = win32._open_bound_file_absolute
    original_close = win32.Win32BoundFile.close
    injected = False
    faulted_close_bound: object | None = None

    def fault_open(*args: object, **kwargs: object) -> object:
        nonlocal injected
        if kwargs.get("operation") == fault_operation and not injected:
            injected = True
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        return original_open(*args, **kwargs)

    def fault_close(
        bound: object,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal injected, faulted_close_bound
        if operation == fault_operation and not injected:
            injected = True
            faulted_close_bound = bound
            raise win32.Win32SafetyError(
                win32.FINAL_VERIFICATION_FAILED,
                operation=fault_operation,
            )
        original_close(bound, reason=reason, operation=operation)

    monkeypatch.setattr(win32, "_open_bound_file_absolute", fault_open)
    monkeypatch.setattr(win32.Win32BoundFile, "close", fault_close)
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            survivor = win32.open_bound_file(
                guard,
                win32.PRIVATE_JOURNAL_RELATIVE_PATH,
                profile=win32.FileHandleProfile.NARROW_READ,
                expected_link_count=2,
            )
            residue_name = win32.open_bound_file(
                guard,
                temp_relative,
                profile=win32.FileHandleProfile.NARROW_READ,
                expected_link_count=2,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.handoff_same_identity_twin_to_residue(
                    guard,
                    survivor,
                    residue_name,
                    expected_bytes=data,
                )
            failure = captured.value
            assert injected
            assert failure.checkpoint is win32.MutationCheckpoint.HANDOFF
            transfers = failure.take_authorities()
            assert len(transfers) == expected_transfer_count
            assert all(not transfer.bound.closed for transfer in transfers)
            if fault_operation in {
                "twin_survivor_narrow_close",
                "twin_residue_narrow_close",
            }:
                assert failure.terminal_release_required is True
                terminal = [
                    transfer
                    for transfer in transfers
                    if transfer.terminal_release_first
                ]
                assert len(terminal) == 1
                assert terminal[0].bound is faulted_close_bound
                win32.release_terminal_bound_authority(
                    terminal[0].bound,
                    reason=failure.reason,
                    operation="twin_handoff_test_terminal",
                )
                assert terminal[0].bound.closed is True
            for transfer in reversed(transfers):
                if not transfer.bound.closed:
                    original_close(
                        transfer.bound,
                        operation="twin_handoff_fault_test_cleanup",
                    )
    temp_path.unlink(missing_ok=True)
    final_path.unlink(missing_ok=True)


@WINDOWS_NTFS
def test_residue_source_close_failure_restores_owned_present_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "5" * 64
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=b"delete-pending",
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            api = win32._api()
            original_close = api.close_handle
            target_attempts = 0
            original_preclear_sha256 = (
                residue._sha256_for_expected_link_count
            )
            digest_link_counts: list[int | None] = []

            def fail_raw_close_once(handle: int) -> object:
                nonlocal target_attempts
                if int(handle) == int(target_handle):
                    target_attempts += 1
                    if target_attempts == 1:
                        ctypes.set_last_error(5)
                        return False
                return original_close(handle)

            def track_preclear_digest(
                *,
                max_bytes: int,
                expected_link_count: int | None,
                reason: str,
            ) -> str:
                digest_link_counts.append(expected_link_count)
                return original_preclear_sha256(
                    max_bytes=max_bytes,
                    expected_link_count=expected_link_count,
                    reason=reason,
                )

            monkeypatch.setattr(
                api,
                "close_handle",
                fail_raw_close_once,
            )
            monkeypatch.setattr(
                residue,
                "_sha256_for_expected_link_count",
                track_preclear_digest,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert target_attempts == 1
            assert digest_link_counts == [0, 1]
            assert failure.terminal_release_required is True
            assert (
                failure.checkpoint
                is win32.MutationCheckpoint.RESIDUE_API
            )
            assert (
                failure.effect
                is win32.MutationEffect.NO_CHANGE_PROVED
            )
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].bound is residue
            assert transfers[0].name_state == "owned_present"
            assert residue.closed is False
            assert residue.read_all(max_bytes=64) == b"delete-pending"
            win32.release_terminal_bound_authority(residue)
            assert target_attempts == 2
            assert path.read_bytes() == b"delete-pending"


@WINDOWS_NTFS
def test_residue_restore_clear_api_failure_keeps_delete_pending_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "6" * 64
    data = b"clear-api-failure"
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            api = win32._api()
            original_close = api.close_handle
            original_set = api.set_file_information
            close_attempts = 0
            clear_attempts = 0

            def fail_raw_close_once(handle: int) -> object:
                nonlocal close_attempts
                if int(handle) == int(target_handle):
                    close_attempts += 1
                    if close_attempts == 1:
                        ctypes.set_last_error(5)
                        return False
                return original_close(handle)

            def fail_clear_disposition(
                handle: int,
                information_class: int,
                buffer: object,
                buffer_size: int,
            ) -> object:
                nonlocal clear_attempts
                disposition = getattr(buffer, "_obj", None)
                if (
                    int(handle) == int(target_handle)
                    and information_class
                    == win32._FILE_DISPOSITION_INFO_CLASS
                    and disposition is not None
                    and int(disposition.delete_file) == 0
                ):
                    clear_attempts += 1
                    ctypes.set_last_error(5)
                    return False
                return original_set(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                )

            monkeypatch.setattr(api, "close_handle", fail_raw_close_once)
            monkeypatch.setattr(
                api,
                "set_file_information",
                fail_clear_disposition,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert close_attempts == 1
            assert clear_attempts == 1
            assert (
                failure.checkpoint
                is win32.MutationCheckpoint.RESIDUE_API
            )
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_POSSIBLE
            )
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].bound is residue
            assert transfers[0].name_state == "delete_pending"
            assert failure.terminal_release_required is True
            assert residue.closed is False

            # Exact terminal release is explicit and does not depend on GC.
            win32.release_terminal_bound_authority(residue)
            assert close_attempts == 2
            assert residue.closed is True
            assert not path.exists()


@WINDOWS_NTFS
@pytest.mark.parametrize(
    "restore_fault",
    ("presence", "identity", "bytes"),
)
def test_residue_restore_revalidation_failure_is_preserved_unverified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_fault: str,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = {
        "presence": "7",
        "identity": "8",
        "bytes": "9",
    }[restore_fault] * 64
    data = f"restore-{restore_fault}-failure".encode("ascii")
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            api = win32._api()
            original_close = api.close_handle
            original_set = api.set_file_information
            original_validate = (
                residue._information_for_expected_link_count
            )
            original_absent = (
                win32._prove_exact_bound_name_after_cancellation
            )
            original_preclear_sha256 = (
                residue._sha256_for_expected_link_count
            )
            close_attempts = 0
            clear_attempts = 0
            digest_link_counts: list[int | None] = []

            def fail_raw_close_once(handle: int) -> object:
                nonlocal close_attempts
                if int(handle) == int(target_handle):
                    close_attempts += 1
                    if close_attempts == 1:
                        ctypes.set_last_error(5)
                        return False
                return original_close(handle)

            def track_clear_disposition(
                handle: int,
                information_class: int,
                buffer: object,
                buffer_size: int,
            ) -> object:
                nonlocal clear_attempts
                result = original_set(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                )
                disposition = getattr(buffer, "_obj", None)
                if (
                    int(handle) == int(target_handle)
                    and information_class
                    == win32._FILE_DISPOSITION_INFO_CLASS
                    and disposition is not None
                    and int(disposition.delete_file) == 0
                    and result
                ):
                    clear_attempts += 1
                return result

            def fail_restored_identity(
                *,
                expected_link_count: int | None,
                reason: str,
                operation: str,
            ) -> object:
                if (
                    restore_fault == "identity"
                    and clear_attempts
                    and expected_link_count == 1
                ):
                    raise win32.Win32SafetyError(
                        win32.RESIDUE_DISPOSITION_FAILED,
                        operation="residue_disposition_restore_identity",
                    )
                return original_validate(
                    expected_link_count=expected_link_count,
                    reason=reason,
                    operation=operation,
                )

            def fail_restored_presence(
                guard_arg: object,
                bound_arg: object,
                *,
                reason: str,
            ) -> None:
                if (
                    restore_fault == "presence"
                    and clear_attempts
                ):
                    raise win32.Win32SafetyError(
                        win32.RESIDUE_DISPOSITION_FAILED,
                        operation="residue_disposition_restore_name_missing",
                    )
                return original_absent(
                    guard_arg,
                    bound_arg,
                    reason=reason,
                )

            def track_preclear_digest(
                *,
                max_bytes: int,
                expected_link_count: int | None,
                reason: str,
            ) -> str:
                digest_link_counts.append(expected_link_count)
                digest = original_preclear_sha256(
                    max_bytes=max_bytes,
                    expected_link_count=expected_link_count,
                    reason=reason,
                )
                if restore_fault == "bytes" and expected_link_count == 1:
                    return "sha256:" + ("0" * 64)
                return digest

            monkeypatch.setattr(api, "close_handle", fail_raw_close_once)
            monkeypatch.setattr(
                api,
                "set_file_information",
                track_clear_disposition,
            )
            monkeypatch.setattr(
                residue,
                "_information_for_expected_link_count",
                fail_restored_identity,
            )
            monkeypatch.setattr(
                win32,
                "_prove_exact_bound_name_after_cancellation",
                fail_restored_presence,
            )
            monkeypatch.setattr(
                residue,
                "_sha256_for_expected_link_count",
                track_preclear_digest,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert close_attempts == 1
            assert clear_attempts == 1
            assert digest_link_counts == (
                [0] if restore_fault == "identity" else [0, 1]
            )
            assert (
                failure.checkpoint
                is win32.MutationCheckpoint.RESIDUE_API
            )
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_POSSIBLE
            )
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].bound is residue
            assert transfers[0].name_state == "state_unknown"
            assert failure.terminal_release_required is True
            assert residue.closed is False

            win32.release_terminal_bound_authority(residue)
            assert close_attempts == 2
            assert path.read_bytes() == data


@WINDOWS_NTFS
@pytest.mark.parametrize("proof_fails", (False, True))
def test_delete_file_true_api_failure_is_no_change_only_after_exact_reproof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    proof_fails: bool,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = ("e" if proof_fails else "f") * 64
    data = b"failed-true-call"
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            api = win32._api()
            original_set = api.set_file_information
            original_sha256 = residue._sha256_for_expected_link_count
            true_attempts = 0
            proof_digest_attempts = 0

            def fail_true_call(
                handle: int,
                information_class: int,
                buffer: object,
                buffer_size: int,
            ) -> object:
                nonlocal true_attempts
                disposition = getattr(buffer, "_obj", None)
                if (
                    int(handle) == int(target_handle)
                    and information_class
                    == win32._FILE_DISPOSITION_INFO_CLASS
                    and disposition is not None
                    and int(disposition.delete_file) == 1
                ):
                    true_attempts += 1
                    ctypes.set_last_error(5)
                    return False
                return original_set(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                )

            def maybe_fail_proof_digest(
                *,
                max_bytes: int,
                expected_link_count: int | None,
                reason: str,
            ) -> str:
                nonlocal proof_digest_attempts
                proof_digest_attempts += 1
                digest = original_sha256(
                    max_bytes=max_bytes,
                    expected_link_count=expected_link_count,
                    reason=reason,
                )
                return (
                    "sha256:" + ("0" * 64)
                    if proof_fails
                    else digest
                )

            monkeypatch.setattr(api, "set_file_information", fail_true_call)
            monkeypatch.setattr(
                residue,
                "_sha256_for_expected_link_count",
                maybe_fail_proof_digest,
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert true_attempts == 1
            assert proof_digest_attempts == 1
            assert failure.terminal_release_required is True
            assert failure.checkpoint is win32.MutationCheckpoint.RESIDUE_API
            assert failure.effect is (
                win32.MutationEffect.STATE_CHANGE_POSSIBLE
                if proof_fails
                else win32.MutationEffect.NO_CHANGE_PROVED
            )
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].name_state == (
                "state_unknown" if proof_fails else "owned_present"
            )
            win32.release_terminal_bound_authority(residue)
            assert path.read_bytes() == data


@WINDOWS_NTFS
def test_delete_file_true_api_failure_no_change_postproof_order_is_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "0" * 64
    data = b"failed-true-ordered-no-change-proof"
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            api = win32._api()
            original_set = api.set_file_information
            original_information = (
                residue._information_for_expected_link_count
            )
            original_sha256 = residue._sha256_for_expected_link_count
            original_name = win32._prove_exact_bound_name
            original_guard_validate = guard.validate_all
            original_locks_validate = locks.validate
            events: list[str] = []
            true_failed = False
            guard_recorded = False

            def fail_true_call(
                handle: int,
                information_class: int,
                buffer: object,
                buffer_size: int,
            ) -> object:
                nonlocal true_failed
                disposition = getattr(buffer, "_obj", None)
                if (
                    int(handle) == int(target_handle)
                    and information_class
                    == win32._FILE_DISPOSITION_INFO_CLASS
                    and disposition is not None
                    and int(disposition.delete_file) == 1
                ):
                    true_failed = True
                    ctypes.set_last_error(5)
                    return False
                return original_set(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                )

            def track_information(
                *,
                expected_link_count: int | None,
                reason: str,
                operation: str,
            ) -> object:
                observed = original_information(
                    expected_link_count=expected_link_count,
                    reason=reason,
                    operation=operation,
                )
                if (
                    true_failed
                    and operation
                    == "residue_disposition_failed_no_change_handle"
                ):
                    events.append("same_handle")
                return observed

            def track_sha256(
                *,
                max_bytes: int,
                expected_link_count: int | None,
                reason: str,
            ) -> str:
                observed = original_sha256(
                    max_bytes=max_bytes,
                    expected_link_count=expected_link_count,
                    reason=reason,
                )
                if true_failed:
                    events.append("same_bytes")
                return observed

            def track_name(*args: object, **kwargs: object) -> None:
                original_name(*args, **kwargs)
                if true_failed:
                    events.append("exact_name")

            def track_guard() -> None:
                nonlocal guard_recorded
                original_guard_validate()
                if true_failed and not guard_recorded:
                    guard_recorded = True
                    events.append("guard")

            def track_locks() -> None:
                original_locks_validate()
                if true_failed:
                    events.append("locks")

            monkeypatch.setattr(api, "set_file_information", fail_true_call)
            monkeypatch.setattr(
                residue,
                "_information_for_expected_link_count",
                track_information,
            )
            monkeypatch.setattr(
                residue,
                "_sha256_for_expected_link_count",
                track_sha256,
            )
            monkeypatch.setattr(win32, "_prove_exact_bound_name", track_name)
            monkeypatch.setattr(guard, "validate_all", track_guard)
            monkeypatch.setattr(locks, "validate", track_locks)

            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert events == [
                "same_handle",
                "same_bytes",
                "exact_name",
                "guard",
                "locks",
            ]
            assert failure.effect is win32.MutationEffect.NO_CHANGE_PROVED
            assert failure.terminal_release_required is True
            transfers = failure.take_authorities()
            assert [transfer.name_state for transfer in transfers] == [
                "owned_present"
            ]
            win32.release_terminal_bound_authority(residue)
            assert path.read_bytes() == data


@WINDOWS_NTFS
@pytest.mark.parametrize(
    "proof_fault",
    ("identity", "type", "link", "size", "bytes", "name", "guard", "locks"),
)
def test_delete_file_true_api_failure_each_unproved_seam_is_state_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    proof_fault: str,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = {
        "identity": "1",
        "type": "2",
        "link": "3",
        "size": "4",
        "bytes": "5",
        "name": "6",
        "guard": "7",
        "locks": "8",
    }[proof_fault] * 64
    data = f"failed-true-{proof_fault}".encode("ascii")
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            api = win32._api()
            original_set = api.set_file_information
            original_query = win32._query_information
            original_sha256 = residue._sha256_for_expected_link_count
            original_name = win32._prove_exact_bound_name
            original_guard_validate = guard.validate_all
            original_locks_validate = locks.validate
            original_clear = win32._clear_disposition
            true_failed = False
            fault_injected = False
            name_attempts = 0
            clear_attempts = 0

            def fail_true_call(
                handle: int,
                information_class: int,
                buffer: object,
                buffer_size: int,
            ) -> object:
                nonlocal true_failed
                disposition = getattr(buffer, "_obj", None)
                if (
                    int(handle) == int(target_handle)
                    and information_class
                    == win32._FILE_DISPOSITION_INFO_CLASS
                    and disposition is not None
                    and int(disposition.delete_file) == 1
                ):
                    true_failed = True
                    ctypes.set_last_error(5)
                    return False
                return original_set(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                )

            def alter_same_handle_information(handle: int) -> object:
                nonlocal fault_injected
                observed = original_query(handle)
                if (
                    true_failed
                    and not fault_injected
                    and int(handle) == int(target_handle)
                    and proof_fault in {"identity", "type", "link", "size"}
                ):
                    fault_injected = True
                    return win32.Win32FileInformation(
                        identity=(
                            win32.Win32FileIdentity(
                                observed.identity.volume_serial,
                                observed.identity.file_index + 1,
                            )
                            if proof_fault == "identity"
                            else observed.identity
                        ),
                        attributes=observed.attributes,
                        link_count=(
                            observed.link_count + 1
                            if proof_fault == "link"
                            else observed.link_count
                        ),
                        byte_count=(
                            observed.byte_count + 1
                            if proof_fault == "size"
                            else observed.byte_count
                        ),
                        file_type=(
                            0 if proof_fault == "type" else observed.file_type
                        ),
                    )
                return observed

            def alter_same_handle_digest(
                *,
                max_bytes: int,
                expected_link_count: int | None,
                reason: str,
            ) -> str:
                nonlocal fault_injected
                observed = original_sha256(
                    max_bytes=max_bytes,
                    expected_link_count=expected_link_count,
                    reason=reason,
                )
                if proof_fault == "bytes" and not fault_injected:
                    fault_injected = True
                    return "sha256:" + ("0" * 64)
                return observed

            def fail_exact_name(*args: object, **kwargs: object) -> None:
                nonlocal fault_injected, name_attempts
                name_attempts += 1
                if proof_fault == "name" and not fault_injected:
                    fault_injected = True
                    raise win32.Win32SafetyError(
                        win32.RESIDUE_DISPOSITION_FAILED,
                        operation="synthetic_failed_true_name",
                    )
                original_name(*args, **kwargs)

            def fail_guard_once() -> None:
                nonlocal fault_injected
                if (
                    true_failed
                    and proof_fault == "guard"
                    and not fault_injected
                ):
                    fault_injected = True
                    raise win32.Win32SafetyError(
                        win32.RESIDUE_DISPOSITION_FAILED,
                        operation="synthetic_failed_true_guard",
                    )
                original_guard_validate()

            def fail_locks_once() -> None:
                nonlocal fault_injected
                if (
                    true_failed
                    and proof_fault == "locks"
                    and not fault_injected
                ):
                    fault_injected = True
                    raise win32.Win32SafetyError(
                        win32.RESIDUE_DISPOSITION_FAILED,
                        operation="synthetic_failed_true_locks",
                    )
                original_locks_validate()

            def count_clear(*args: object, **kwargs: object) -> None:
                nonlocal clear_attempts
                clear_attempts += 1
                original_clear(*args, **kwargs)

            monkeypatch.setattr(api, "set_file_information", fail_true_call)
            monkeypatch.setattr(
                win32,
                "_query_information",
                alter_same_handle_information,
            )
            monkeypatch.setattr(
                residue,
                "_sha256_for_expected_link_count",
                alter_same_handle_digest,
            )
            monkeypatch.setattr(
                win32,
                "_prove_exact_bound_name",
                fail_exact_name,
            )
            monkeypatch.setattr(guard, "validate_all", fail_guard_once)
            monkeypatch.setattr(locks, "validate", fail_locks_once)
            monkeypatch.setattr(win32, "_clear_disposition", count_clear)

            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert fault_injected
            assert clear_attempts == 0
            assert name_attempts == (
                0
                if proof_fault
                in {"identity", "type", "link", "size", "bytes"}
                else 1
            )
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_POSSIBLE
            )
            assert failure.terminal_release_required is True
            transfers = failure.take_authorities()
            assert [transfer.name_state for transfer in transfers] == [
                "state_unknown"
            ]
            win32.release_terminal_bound_authority(residue)
            assert path.read_bytes() == data


@WINDOWS_NTFS
def test_delete_file_true_changed_state_but_returned_false_never_opens_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "9" * 64
    data = b"set-delete-pending-but-report-false"
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            api = win32._api()
            original_set = api.set_file_information
            original_name = win32._prove_exact_bound_name
            original_clear = win32._clear_disposition
            name_attempts = 0
            clear_attempts = 0

            def set_true_but_report_false(
                handle: int,
                information_class: int,
                buffer: object,
                buffer_size: int,
            ) -> object:
                disposition = getattr(buffer, "_obj", None)
                if (
                    int(handle) == int(target_handle)
                    and information_class
                    == win32._FILE_DISPOSITION_INFO_CLASS
                    and disposition is not None
                    and int(disposition.delete_file) == 1
                ):
                    assert original_set(
                        handle,
                        information_class,
                        buffer,
                        buffer_size,
                    )
                    ctypes.set_last_error(5)
                    return False
                return original_set(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                )

            def count_name(*args: object, **kwargs: object) -> None:
                nonlocal name_attempts
                name_attempts += 1
                original_name(*args, **kwargs)

            def count_clear(*args: object, **kwargs: object) -> None:
                nonlocal clear_attempts
                clear_attempts += 1
                original_clear(*args, **kwargs)

            monkeypatch.setattr(
                api,
                "set_file_information",
                set_true_but_report_false,
            )
            monkeypatch.setattr(win32, "_prove_exact_bound_name", count_name)
            monkeypatch.setattr(win32, "_clear_disposition", count_clear)

            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert name_attempts == 0
            assert clear_attempts == 0
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_POSSIBLE
            )
            assert failure.terminal_release_required is True
            transfers = failure.take_authorities()
            assert [transfer.name_state for transfer in transfers] == [
                "state_unknown"
            ]
            win32.release_terminal_bound_authority(residue)
            assert not path.exists()


@WINDOWS_NTFS
def test_publication_twin_never_enters_single_link_disposition_compensation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "a" * 64
    data = b"two-link-compensation-is-forbidden"
    relative = win32.owned_temp_relative_path(
        win32.OwnedTempKind.MANIFEST,
        key,
    )
    source_path = root / Path(relative)
    survivor_path = root / "objects" / "manifests" / "synthetic-twin.keep"
    api = win32._api()

    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            assert api.create_hard_link(
                win32._extended_path(survivor_path),
                win32._extended_path(source_path),
                None,
            )
            source.expected_link_count = 2
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            original_close = api.close_handle
            original_clear = win32._clear_disposition
            close_attempts = 0
            clear_attempts = 0

            def fail_raw_close_once(handle: int) -> object:
                nonlocal close_attempts
                if int(handle) == int(target_handle):
                    close_attempts += 1
                    if close_attempts == 1:
                        ctypes.set_last_error(5)
                        return False
                return original_close(handle)

            def count_clear(*args: object, **kwargs: object) -> None:
                nonlocal clear_attempts
                clear_attempts += 1
                original_clear(*args, **kwargs)

            monkeypatch.setattr(api, "close_handle", fail_raw_close_once)
            monkeypatch.setattr(win32, "_clear_disposition", count_clear)
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert clear_attempts == 0
            assert failure.terminal_release_required is True
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_POSSIBLE
            )
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].name_state == "delete_pending"
            win32.release_terminal_bound_authority(residue)
            assert close_attempts == 2
            assert not source_path.exists()
            assert survivor_path.read_bytes() == data
            assert survivor_path.stat().st_nlink == 1
    survivor_path.unlink(missing_ok=True)


@WINDOWS_NTFS
@pytest.mark.parametrize("binding_fault", ("byte_count", "sha256"))
def test_disposition_compensation_requires_exact_planned_content_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    binding_fault: str,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = ("b" if binding_fault == "byte_count" else "c") * 64
    data = b"planned-content-binding"
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            if binding_fault == "byte_count":
                residue.expected_byte_count = len(data) + 1
            else:
                residue.expected_sha256 = "sha256:" + ("0" * 64)
            target_handle = residue.raw_handle
            api = win32._api()
            original_close = api.close_handle
            original_clear = win32._clear_disposition
            close_attempts = 0
            clear_attempts = 0

            def fail_raw_close_once(handle: int) -> object:
                nonlocal close_attempts
                if int(handle) == int(target_handle):
                    close_attempts += 1
                    if close_attempts == 1:
                        ctypes.set_last_error(5)
                        return False
                return original_close(handle)

            def count_clear(*args: object, **kwargs: object) -> None:
                nonlocal clear_attempts
                clear_attempts += 1
                original_clear(*args, **kwargs)

            monkeypatch.setattr(api, "close_handle", fail_raw_close_once)
            monkeypatch.setattr(win32, "_clear_disposition", count_clear)
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            failure = captured.value
            assert close_attempts == 1
            assert clear_attempts == 0
            assert failure.terminal_release_required is True
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].name_state == "delete_pending"
            win32.release_terminal_bound_authority(residue)
            assert close_attempts == 2
            assert not path.exists()


@WINDOWS_NTFS
def test_disposition_compensation_postcheck_order_is_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "d" * 64
    data = b"ordered-compensation"
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            target_handle = residue.raw_handle
            api = win32._api()
            original_close = api.close_handle
            original_clear = win32._clear_disposition
            original_information = (
                residue._information_for_expected_link_count
            )
            original_sha256 = residue._sha256_for_expected_link_count
            original_name = win32._prove_exact_bound_name_after_cancellation
            original_guard_validate = guard.validate_all
            original_locks_validate = locks.validate
            events: list[str] = []
            close_failed = False
            clear_succeeded = False
            name_completed = False
            guard_recorded = False
            locks_recorded = False

            def fail_raw_close_once(handle: int) -> object:
                nonlocal close_failed
                if int(handle) == int(target_handle) and not close_failed:
                    close_failed = True
                    ctypes.set_last_error(5)
                    return False
                return original_close(handle)

            def track_information(
                *,
                expected_link_count: int | None,
                reason: str,
                operation: str,
            ) -> object:
                if operation == "residue_disposition_restore_precheck":
                    events.append("same_handle_pre")
                elif operation == "residue_disposition_restore_postcheck":
                    events.append("same_handle_post")
                return original_information(
                    expected_link_count=expected_link_count,
                    reason=reason,
                    operation=operation,
                )

            def track_sha256(
                *,
                max_bytes: int,
                expected_link_count: int | None,
                reason: str,
            ) -> str:
                if close_failed and expected_link_count == 0:
                    events.append("same_handle_pre_bytes")
                elif clear_succeeded and expected_link_count == 1:
                    events.append("same_handle_post_bytes")
                return original_sha256(
                    max_bytes=max_bytes,
                    expected_link_count=expected_link_count,
                    reason=reason,
                )

            def track_clear(*args: object, **kwargs: object) -> None:
                nonlocal clear_succeeded
                original_clear(*args, **kwargs)
                events.append("delete_file_false")
                clear_succeeded = True

            def track_name(*args: object, **kwargs: object) -> None:
                nonlocal name_completed
                original_name(*args, **kwargs)
                events.append("exact_name")
                name_completed = True

            def track_guard() -> None:
                nonlocal guard_recorded
                original_guard_validate()
                if name_completed and not guard_recorded:
                    events.append("guard")
                    guard_recorded = True

            def track_locks() -> object:
                nonlocal locks_recorded
                result = original_locks_validate()
                if guard_recorded and not locks_recorded:
                    events.append("locks")
                    locks_recorded = True
                return result

            monkeypatch.setattr(api, "close_handle", fail_raw_close_once)
            monkeypatch.setattr(
                residue,
                "_information_for_expected_link_count",
                track_information,
            )
            monkeypatch.setattr(
                residue,
                "_sha256_for_expected_link_count",
                track_sha256,
            )
            monkeypatch.setattr(win32, "_clear_disposition", track_clear)
            monkeypatch.setattr(
                win32,
                "_prove_exact_bound_name_after_cancellation",
                track_name,
            )
            monkeypatch.setattr(guard, "validate_all", track_guard)
            monkeypatch.setattr(locks, "validate", track_locks)
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.dispose_bound_residue(
                    guard,
                    residue,
                    locks=locks,
                )
            assert events == [
                "same_handle_pre",
                "same_handle_pre_bytes",
                "delete_file_false",
                "same_handle_post",
                "same_handle_post_bytes",
                "exact_name",
                "guard",
                "locks",
            ]
            failure = captured.value
            assert (
                failure.effect is win32.MutationEffect.NO_CHANGE_PROVED
            )
            failure.take_authorities()
            win32.release_terminal_bound_authority(residue)
            assert path.read_bytes() == data


@WINDOWS_NTFS
def test_delete_pending_close_fault_requires_immediate_terminal_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    key = "e" * 64
    data = b"delete-pending-terminal"
    path = root / Path(
        win32.owned_temp_relative_path(
            win32.OwnedTempKind.MANIFEST,
            key,
        )
    )
    original_close = win32.Win32BoundFile.close
    injected = False

    def fail_delete_pending_close(
        bound: win32.Win32BoundFile,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal injected
        if operation == "delete_pending_source_close" and not injected:
            injected = True
            raise win32.Win32SafetyError(
                reason,
                operation=operation,
            )
        original_close(bound, reason=reason, operation=operation)

    monkeypatch.setattr(
        win32.Win32BoundFile,
        "close",
        fail_delete_pending_close,
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        with win32.PrivateMetadataLockPair(guard) as locks:
            source = win32.materialize_owned_temp(
                guard,
                kind=win32.OwnedTempKind.MANIFEST,
                authority_key_hex=key,
                data=data,
            )
            residue = win32.handoff_to_residue_authority(guard, source)
            win32._set_disposition(
                residue,
                reason=win32.RESIDUE_DISPOSITION_FAILED,
                operation="delete_pending_test_disposition",
            )
            with pytest.raises(win32.Win32MutationFailure) as captured:
                win32.complete_delete_pending_residue(guard, residue)
            failure = captured.value
            assert injected
            assert failure.reason == win32.RESIDUE_DISPOSITION_FAILED
            assert failure.terminal_release_required is True
            assert (
                failure.effect
                is win32.MutationEffect.STATE_CHANGE_PROVED
            )
            transfers = failure.take_authorities()
            assert len(transfers) == 1
            assert transfers[0].bound is residue
            assert transfers[0].terminal_release_first is True
            assert transfers[0].name_state == "delete_pending"
            win32.release_terminal_bound_authority(
                residue,
                reason=failure.reason,
                operation="delete_pending_test_terminal",
            )
            assert residue.closed is True
            assert not path.exists()
            locks.validate()
            guard.validate_all()


@WINDOWS_NTFS
@pytest.mark.parametrize(
    "fault_operation",
    ("unlock_file_ex", "coordination_lock_close"),
)
def test_lock_release_fault_is_retryable_without_split_unlock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault_operation: str,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    api = win32._api()
    original_unlock = api.unlock_file
    original_close = win32.Win32BoundFile.close
    injected = False

    def fail_unlock(*args: object) -> object:
        nonlocal injected
        if fault_operation == "unlock_file_ex" and not injected:
            injected = True
            ctypes.set_last_error(5)
            return False
        return original_unlock(*args)

    def fail_lock_close(
        bound: object,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal injected
        if (
            fault_operation == "coordination_lock_close"
            and operation == fault_operation
            and not injected
        ):
            injected = True
            raise win32.Win32SafetyError(
                win32.LOCK_IDENTITY_CHANGED,
                operation=operation,
            )
        original_close(bound, reason=reason, operation=operation)

    monkeypatch.setattr(api, "unlock_file", fail_unlock)
    monkeypatch.setattr(
        win32.Win32BoundFile,
        "close",
        fail_lock_close,
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        pair = win32.PrivateMetadataLockPair(guard)
        pair.acquire()
        with pytest.raises(win32.Win32SafetyError) as captured:
            pair.release()
        assert injected
        assert captured.value.reason == win32.LOCK_IDENTITY_CHANGED
        assert pair._acquired is True
        if fault_operation == "unlock_file_ex":
            monkeypatch.setattr(api, "unlock_file", original_unlock)
        else:
            monkeypatch.setattr(
                win32.Win32BoundFile,
                "close",
                original_close,
            )
        pair.release()
        assert pair._acquired is False
        guard.validate_all()


@WINDOWS_NTFS
@pytest.mark.parametrize(
    ("failing_lock", "failing_call"),
    (
        ("object_manifest", 3),
        ("private_metadata", 2),
    ),
)
def test_lock_pair_partial_acquire_unwinds_inner_then_outer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failing_lock: str,
    failing_call: int,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    original_close = win32.Win32BoundFile.close
    close_order: list[str] = []

    def record_lock_close(
        bound: win32.Win32BoundFile,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        if operation == "coordination_lock_close":
            close_order.append(bound.path.name)
        original_close(bound, reason=reason, operation=operation)

    monkeypatch.setattr(
        win32.Win32BoundFile,
        "close",
        record_lock_close,
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        pair = win32.PrivateMetadataLockPair(guard)
        failing = getattr(pair, failing_lock)
        original_validate = failing.validate
        validate_calls = 0

        def fail_one_post_acquire_validation() -> win32.Win32FileIdentity:
            nonlocal validate_calls
            validate_calls += 1
            if validate_calls == failing_call:
                raise win32.Win32SafetyError(
                    win32.LOCK_IDENTITY_CHANGED,
                    operation="synthetic_pair_post_acquire_validation",
                )
            return original_validate()

        monkeypatch.setattr(
            failing,
            "validate",
            fail_one_post_acquire_validation,
        )
        with pytest.raises(win32.Win32SafetyError) as captured:
            pair.acquire()
        assert captured.value.reason == win32.LOCK_IDENTITY_CHANGED
        assert validate_calls >= failing_call
        assert close_order[:2] == [
            Path(win32.PRIVATE_METADATA_LOCK_RELATIVE_PATH).name,
            Path(win32.OBJECT_MANIFEST_LOCK_RELATIVE_PATH).name,
        ]
        assert pair._acquired is False
        assert pair.private_metadata.bound is None
        assert pair.object_manifest.bound is None
        assert pair.private_metadata._locked is False
        assert pair.object_manifest._locked is False
        assert guard._active_lock_kinds == set()

        # The same pair can be acquired again immediately; no hidden lock was
        # left to a finalizer or process exit.
        pair.acquire()
        pair.validate()
        pair.release()
        assert pair._acquired is False
        assert guard._active_lock_kinds == set()
        guard.validate_all()


@WINDOWS_NTFS
def test_lock_pair_partial_acquire_inner_close_fault_terminalizes_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _archive_root(tmp_path)
    _require_ntfs(root)
    original_close = win32.Win32BoundFile.close
    original_terminal_release = win32.release_terminal_bound_authority
    events: list[str] = []
    close_injected = False

    def fault_inner_lock_close(
        bound: win32.Win32BoundFile,
        *,
        reason: str = win32.FINAL_VERIFICATION_FAILED,
        operation: str = "bound_handle_close",
    ) -> None:
        nonlocal close_injected
        if (
            operation == "coordination_lock_close"
            and bound.path.name
            == Path(win32.PRIVATE_METADATA_LOCK_RELATIVE_PATH).name
            and not close_injected
        ):
            close_injected = True
            events.append("private_close_fault")
            raise win32.Win32SafetyError(
                win32.LOCK_IDENTITY_CHANGED,
                operation=operation,
            )
        if (
            operation == "coordination_lock_close"
            and bound.path.name
            == Path(win32.OBJECT_MANIFEST_LOCK_RELATIVE_PATH).name
        ):
            events.append("object_close")
        original_close(bound, reason=reason, operation=operation)

    def record_terminal_release(
        bound: win32.Win32BoundFile,
        *,
        reason: str = win32.RESIDUE_DISPOSITION_FAILED,
        operation: str = "residue_terminal_authority_release",
    ) -> None:
        if (
            bound.path.name
            == Path(win32.PRIVATE_METADATA_LOCK_RELATIVE_PATH).name
        ):
            events.append("private_terminal")
        original_terminal_release(
            bound,
            reason=reason,
            operation=operation,
        )

    monkeypatch.setattr(
        win32.Win32BoundFile,
        "close",
        fault_inner_lock_close,
    )
    monkeypatch.setattr(
        win32,
        "release_terminal_bound_authority",
        record_terminal_release,
    )
    with _probe_guard(root) as guard:
        _hold_manifests(guard)
        pair = win32.PrivateMetadataLockPair(guard)
        original_validate = pair.object_manifest.validate
        validate_calls = 0

        def fail_after_both_locks_live() -> win32.Win32FileIdentity:
            nonlocal validate_calls
            validate_calls += 1
            result = original_validate()
            if validate_calls == 3:
                raise win32.Win32SafetyError(
                    win32.LOCK_IDENTITY_CHANGED,
                    operation="synthetic_pair_final_object_validation",
                )
            return result

        monkeypatch.setattr(
            pair.object_manifest,
            "validate",
            fail_after_both_locks_live,
        )
        with pytest.raises(win32.Win32SafetyError) as captured:
            pair.acquire()
        assert captured.value.reason == win32.LOCK_IDENTITY_CHANGED
        assert close_injected
        assert events[:3] == [
            "private_close_fault",
            "private_terminal",
            "object_close",
        ]
        assert pair._acquired is False
        assert pair.private_metadata.bound is None
        assert pair.object_manifest.bound is None
        assert pair.private_metadata._locked is False
        assert pair.object_manifest._locked is False
        assert guard._active_lock_kinds == set()

        retry = win32.PrivateMetadataLockPair(
            guard,
            fail_immediately=True,
        )
        retry.acquire()
        retry.validate()
        retry.release()
        assert guard._active_lock_kinds == set()
        guard.validate_all()


def test_module_has_no_forbidden_path_mutation_or_process_seam() -> None:
    source = Path(win32.__file__).read_text(encoding="utf-8")
    forbidden_call_patterns = (
        r"\bos\.replace\s*\(",
        r"\bos\.rename\s*\(",
        r"\bos\.unlink\s*\(",
        r"\bos\.remove\s*\(",
        r"\bos\.link\s*\(",
        r"\bshutil\.",
        r"\bsubprocess\.",
        r"\bNt[A-Za-z0-9_]*\s*\(",
        r"\bZw[A-Za-z0-9_]*\s*\(",
    )
    for pattern in forbidden_call_patterns:
        assert re.search(pattern, source) is None, pattern
    assert "FILE_RENAME_INFO_CLASS = 3" in source
    assert "FILE_DISPOSITION_INFO_CLASS = 4" in source


def test_exact_numeric_error_contract() -> None:
    assert win32.win32_error_constants() == {
        "ERROR_ACCESS_DENIED": 5,
        "ERROR_SHARING_VIOLATION": 32,
        "ERROR_ALREADY_EXISTS": 183,
    }
