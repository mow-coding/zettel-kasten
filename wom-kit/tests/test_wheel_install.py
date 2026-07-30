from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile


KIT_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = KIT_ROOT / "tools" / "check_wheel_install.py"
RESOURCE_PREFIX = "wom_kit/_resources/"
MANIFEST_MEMBER = f"{RESOURCE_PREFIX}resource-manifest.json"

spec = importlib.util.spec_from_file_location("check_wheel_install", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_wheel_install = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_wheel_install
spec.loader.exec_module(check_wheel_install)


BASE_RESOURCES = {
    "schemas/archive.schema.json": b'{"fixture": "schema"}\n',
    "templates/personal/archive.yml": b"name: fixture archive\n",
    "templates/ai-runtime/wom-archive/SKILL.md": b"# Fixture skill\n",
    "templates/ai-runtime/wom-archive/references/operator-contract.md": (
        b"# Fixture operator contract\n"
    ),
    "zettel-kasten/types.yml": b"types: {}\n",
}


def manifest_for(resources: dict[str, bytes]) -> dict[str, object]:
    files = [
        {
            "source": packaged,
            "packaged": packaged,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for packaged, data in sorted(resources.items())
    ]
    return {
        "schema": "wom-kit/package-resource-manifest/v0.1",
        "version": "0.3.289",
        "source_of_truth": "wom-kit source resource directories",
        "file_count": len(files),
        "files": files,
    }


def encode_manifest(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def patch_central_directory_file_size(wheel: Path, member: str, size: int) -> None:
    data = bytearray(wheel.read_bytes())
    member_bytes = member.encode("utf-8")
    cursor = 0
    while True:
        cursor = data.find(b"PK\x01\x02", cursor)
        if cursor < 0:
            raise AssertionError(f"Central directory member not found: {member}")
        if cursor + 46 > len(data):
            raise AssertionError("Truncated central directory fixture.")
        filename_length, extra_length, comment_length = struct.unpack_from(
            "<HHH",
            data,
            cursor + 28,
        )
        name_start = cursor + 46
        name_end = name_start + filename_length
        if data[name_start:name_end] == member_bytes:
            struct.pack_into("<I", data, cursor + 24, size)
            wheel.write_bytes(data)
            return
        cursor = name_end + extra_length + comment_length


def patch_zip_member_name_bytes(wheel: Path, old_name: str, new_name: str) -> None:
    old_bytes = old_name.encode("utf-8")
    new_bytes = new_name.encode("utf-8")
    if len(old_bytes) != len(new_bytes):
        raise AssertionError("ZIP fixture member-name patch must preserve byte length.")
    data = wheel.read_bytes()
    occurrence_count = data.count(old_bytes)
    if occurrence_count != 2:
        raise AssertionError(
            f"Expected local and central member names, found {occurrence_count}: {old_name}"
        )
    wheel.write_bytes(data.replace(old_bytes, new_bytes))


class WheelResourceIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory(prefix="wom-wheel-test-")
        self.temp_root = Path(self.temp_directory.name)
        self.fixture_kit_root = self.temp_root / "wom-kit"
        self.package_resource_root = (
            self.fixture_kit_root / "src" / "wom_kit" / "_resources"
        )
        self.package_resource_root.mkdir(parents=True)
        self.package_root_patch = mock.patch.object(
            check_wheel_install,
            "KIT_ROOT",
            self.fixture_kit_root,
        )
        self.package_root_patch.start()
        self.wheel_number = 0

    def tearDown(self) -> None:
        self.package_root_patch.stop()
        self.temp_directory.cleanup()

    def configure_committed_resources(
        self,
        *,
        manifest_bytes: bytes,
        mirror_resources: dict[str, bytes] | None = None,
    ) -> None:
        (self.package_resource_root / "resource-manifest.json").write_bytes(manifest_bytes)
        for relative, data in (mirror_resources or BASE_RESOURCES).items():
            path = self.package_resource_root / Path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def write_wheel(
        self,
        *,
        manifest_bytes: bytes,
        resources: dict[str, bytes] | None = None,
        extra_members: list[tuple[str, bytes]] | None = None,
        manifest_member: str = MANIFEST_MEMBER,
    ) -> Path:
        self.wheel_number += 1
        wheel = self.temp_root / f"fixture-{self.wheel_number}.whl"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr(manifest_member, manifest_bytes)
                for relative, data in (resources or BASE_RESOURCES).items():
                    archive.writestr(f"{RESOURCE_PREFIX}{relative}", data)
                for name, data in extra_members or []:
                    archive.writestr(name, data)
        return wheel

    def baseline(self) -> tuple[dict[str, object], bytes]:
        manifest = manifest_for(BASE_RESOURCES)
        manifest_bytes = encode_manifest(manifest)
        self.configure_committed_resources(manifest_bytes=manifest_bytes)
        return manifest, manifest_bytes

    def assert_wheel_rejected(
        self,
        wheel: Path,
        *,
        message_contains_any: tuple[str, ...] = (),
    ) -> str:
        with self.assertRaises(check_wheel_install.WheelCheckError) as caught:
            check_wheel_install.assert_wheel_resources(wheel)
        message = str(caught.exception)
        if message_contains_any:
            lowered = message.lower()
            self.assertTrue(
                any(needle.lower() in lowered for needle in message_contains_any),
                f"Expected one of {message_contains_any!r} in {message!r}",
            )
        return message

    def test_valid_wheel_verifies_every_resource_and_reports_exact_counts(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[
                (f"{RESOURCE_PREFIX}__init__.py", b'"""Packaged resources."""\n'),
                ("wom_kit-0.3.289.dist-info/METADATA", b"Name: wom-kit\n"),
            ],
        )

        result = check_wheel_install.assert_wheel_resources(wheel)

        self.assertEqual(
            result,
            {
                "manifested_resource_count": len(BASE_RESOURCES),
                "verified_resource_count": len(BASE_RESOURCES),
                "verified_resource_bytes": sum(map(len, BASE_RESOURCES.values())),
                "wheel_file_count": len(BASE_RESOURCES) + 3,
            },
        )

    def test_duplicate_zip_member_is_rejected_even_outside_resource_tree(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[
                ("wom_kit-0.3.289.dist-info/METADATA", b"first"),
                ("wom_kit-0.3.289.dist-info/METADATA", b"second"),
            ],
        )

        self.assert_wheel_rejected(wheel, message_contains_any=("duplicate",))

    def test_unsafe_or_non_normalized_zip_member_paths_are_rejected(self) -> None:
        unsafe_names = (
            "/absolute.txt",
            "//server/share.txt",
            "C:/windows-absolute.txt",
            "relative//empty-segment.txt",
            "./relative.txt",
            "relative/./dot.txt",
            "relative/../parent.txt",
            r"relative\backslash.txt",
            "relative/",
        )
        for unsafe_name in unsafe_names:
            with self.subTest(member=unsafe_name):
                _, manifest_bytes = self.baseline()
                written_name = unsafe_name.replace("\\", "/")
                wheel = self.write_wheel(
                    manifest_bytes=manifest_bytes,
                    extra_members=[(written_name, b"unsafe")],
                )
                if written_name != unsafe_name:
                    # ZipInfo normalizes backslashes on Windows while writing.
                    # Patch both filename copies so the checker receives the
                    # hostile raw member name that an untrusted ZIP may contain.
                    patch_zip_member_name_bytes(wheel, written_name, unsafe_name)
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=("path", "member", "unsafe", "normalized"),
                )

    def test_windows_case_insensitive_member_alias_is_rejected(self) -> None:
        _, manifest_bytes = self.baseline()
        verified_member = f"{RESOURCE_PREFIX}{next(iter(BASE_RESOURCES))}"
        hostile_alias = verified_member.upper()
        self.assertNotEqual(hostile_alias, verified_member)
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[(hostile_alias, b"MALICIOUS-ALIAS-BYTES")],
        )

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("collision", "windows", "duplicate", "alias"),
        )

    def test_windows_case_collision_is_rejected_outside_resource_tree(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[
                ("example/Readme.txt", b"first"),
                ("EXAMPLE/README.TXT", b"second"),
            ],
        )

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("collision", "windows", "duplicate", "alias"),
        )

    def test_wheel_data_scheme_members_are_rejected_before_relocation(self) -> None:
        _, manifest_bytes = self.baseline()
        verified_member = f"{RESOURCE_PREFIX}{next(iter(BASE_RESOURCES))}"
        scheme_members = (
            f"alternate-1.0.data/purelib/{verified_member}",
            f"alternate-1.0.data/platlib/{verified_member}",
            "alternate-1.0.data/data/payload.txt",
            "alternate-1.0.data/headers/payload.h",
            "alternate-1.0.data/scripts/archive",
            f"alternate-1.0.DATA/purelib/{verified_member}",
        )
        for scheme_member in scheme_members:
            with self.subTest(member=scheme_member):
                wheel = self.write_wheel(
                    manifest_bytes=manifest_bytes,
                    extra_members=[(scheme_member, b"RELOCATED-ALIAS-BYTES")],
                )
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=(
                        "data",
                        "scheme",
                        "relocat",
                        "pure",
                        "wheel",
                    ),
                )

    def test_windows_unsafe_segments_are_rejected(self) -> None:
        unsafe_names = (
            "example/alternate-stream.txt:payload",
            "example/less<than.txt",
            "example/greater>than.txt",
            'example/double"quote.txt',
            "example/pipe|name.txt",
            "example/question?.txt",
            "example/star*.txt",
            "example/trailing-dot.",
            "example/trailing-space ",
            "example/CON",
            "example/con.txt",
            "example/PRN.log",
            "example/AUX",
            "example/NUL.data",
            "example/COM1.txt",
            "example/com9",
            "example/COM¹.txt",
            "example/com²",
            "example/COM³.log",
            "example/LPT1.bin",
            "example/lpt9",
            "example/LPT¹.bin",
            "example/lpt²",
            "example/LPT³.log",
        )
        for unsafe_name in unsafe_names:
            with self.subTest(member=unsafe_name):
                _, manifest_bytes = self.baseline()
                wheel = self.write_wheel(
                    manifest_bytes=manifest_bytes,
                    extra_members=[(unsafe_name, b"unsafe-on-windows")],
                )
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=(
                        "windows",
                        "reserved",
                        "colon",
                        "trailing",
                        "path",
                    ),
                )

    def test_manifest_must_use_the_exact_packaged_path(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            manifest_member=f"lookalike/{MANIFEST_MEMBER}",
        )

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("manifest",),
        )

    def test_malformed_zip_is_normalized_to_wheel_check_error(self) -> None:
        wheel = self.temp_root / "malformed.whl"
        wheel.write_bytes(b"this is not a zip archive")

        message = self.assert_wheel_rejected(
            wheel,
            message_contains_any=("zip", "archive", "wheel"),
        )
        self.assertEqual(message, "Wheel resource integrity check failed.")

    def test_malformed_manifest_utf8_and_json_are_rejected(self) -> None:
        malformed_manifests = {
            "utf8": b"\xff\xfe\xfa",
            "json": b'{"schema": ',
        }
        for case, manifest_bytes in malformed_manifests.items():
            with self.subTest(case=case):
                self.configure_committed_resources(manifest_bytes=manifest_bytes)
                wheel = self.write_wheel(manifest_bytes=manifest_bytes)
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=("utf-8", "utf8", "json", "manifest"),
                )

    def test_duplicate_manifest_json_key_is_rejected(self) -> None:
        manifest = manifest_for(BASE_RESOURCES)
        compact = json.dumps(manifest, ensure_ascii=True, separators=(",", ":"))
        duplicate_key_json = compact.replace(
            '"schema":"wom-kit/package-resource-manifest/v0.1",',
            (
                '"schema":"wom-kit/package-resource-manifest/v0.1",'
                '"schema":"wom-kit/package-resource-manifest/v0.1",'
            ),
            1,
        ).encode("utf-8")
        self.configure_committed_resources(manifest_bytes=duplicate_key_json)
        wheel = self.write_wheel(manifest_bytes=duplicate_key_json)

        self.assert_wheel_rejected(wheel, message_contains_any=("duplicate",))

    def test_manifest_schema_and_types_are_strict(self) -> None:
        baseline = manifest_for(BASE_RESOURCES)

        cases: dict[str, dict[str, object]] = {}

        missing_key = dict(baseline)
        del missing_key["source_of_truth"]
        cases["missing top-level key"] = missing_key

        extra_key = dict(baseline)
        extra_key["unexpected"] = True
        cases["extra top-level key"] = extra_key

        wrong_schema = dict(baseline)
        wrong_schema["schema"] = "wom-kit/package-resource-manifest/v999"
        cases["wrong schema identifier"] = wrong_schema

        wrong_version_type = dict(baseline)
        wrong_version_type["version"] = 289
        cases["wrong version type"] = wrong_version_type

        wrong_source_of_truth_type = dict(baseline)
        wrong_source_of_truth_type["source_of_truth"] = ["not", "a", "string"]
        cases["wrong source-of-truth type"] = wrong_source_of_truth_type

        bool_file_count = dict(baseline)
        bool_file_count["file_count"] = True
        cases["bool is not an integer count"] = bool_file_count

        wrong_file_count = dict(baseline)
        wrong_file_count["file_count"] = len(BASE_RESOURCES) + 1
        cases["file count mismatch"] = wrong_file_count

        wrong_files_type = dict(baseline)
        wrong_files_type["files"] = {"not": "a list"}
        cases["files must be a list"] = wrong_files_type

        first_row = dict(baseline["files"][0])  # type: ignore[index]
        missing_row_key = dict(baseline)
        missing_row_key["files"] = [
            {key: value for key, value in first_row.items() if key != "sha256"},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["missing row key"] = missing_row_key

        extra_row_key = dict(baseline)
        extra_row_key["files"] = [
            {**first_row, "unexpected": "value"},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["extra row key"] = extra_row_key

        bool_byte_count = dict(baseline)
        bool_byte_count["files"] = [
            {**first_row, "bytes": True},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["bool is not a byte count"] = bool_byte_count

        negative_byte_count = dict(baseline)
        negative_byte_count["files"] = [
            {**first_row, "bytes": -1},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["negative byte count"] = negative_byte_count

        wrong_source_type = dict(baseline)
        wrong_source_type["files"] = [
            {**first_row, "source": 123},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["row source must be a string"] = wrong_source_type

        malformed_sha = dict(baseline)
        malformed_sha["files"] = [
            {**first_row, "sha256": "not-a-sha256"},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["malformed sha256"] = malformed_sha

        for case, manifest in cases.items():
            with self.subTest(case=case):
                manifest_bytes = encode_manifest(manifest)
                self.configure_committed_resources(manifest_bytes=manifest_bytes)
                wheel = self.write_wheel(manifest_bytes=manifest_bytes)
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=("manifest", "schema", "field", "file_count"),
                )

    def test_duplicate_manifest_resource_path_is_rejected(self) -> None:
        manifest = manifest_for(BASE_RESOURCES)
        duplicate_row = dict(manifest["files"][0])  # type: ignore[index]
        manifest["files"] = [*manifest["files"], duplicate_row]  # type: ignore[index]
        manifest["file_count"] = len(manifest["files"])  # type: ignore[arg-type]
        manifest_bytes = encode_manifest(manifest)
        self.configure_committed_resources(manifest_bytes=manifest_bytes)
        wheel = self.write_wheel(manifest_bytes=manifest_bytes)

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("duplicate", "resource", "packaged"),
        )

    def test_missing_and_unmanifested_resources_are_rejected(self) -> None:
        _, manifest_bytes = self.baseline()
        missing_resources = dict(BASE_RESOURCES)
        missing_resources.pop(next(iter(missing_resources)))
        missing_wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            resources=missing_resources,
        )
        self.assert_wheel_rejected(
            missing_wheel,
            message_contains_any=("resource", "missing", "set"),
        )

        extra_resources = {
            **BASE_RESOURCES,
            "templates/unmanifested.txt": b"not declared",
        }
        extra_wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            resources=extra_resources,
        )
        self.assert_wheel_rejected(
            extra_wheel,
            message_contains_any=("resource", "unexpected", "set"),
        )

    def test_declared_size_and_sha256_mismatches_are_rejected(self) -> None:
        baseline = manifest_for(BASE_RESOURCES)

        size_manifest = dict(baseline)
        size_row = dict(baseline["files"][0])  # type: ignore[index]
        size_manifest["files"] = [
            {**size_row, "bytes": size_row["bytes"] + 1},  # type: ignore[operator]
            *baseline["files"][1:],  # type: ignore[index]
        ]
        size_bytes = encode_manifest(size_manifest)
        self.configure_committed_resources(manifest_bytes=size_bytes)
        size_wheel = self.write_wheel(manifest_bytes=size_bytes)
        self.assert_wheel_rejected(
            size_wheel,
            message_contains_any=("size", "byte"),
        )

        sha_manifest = dict(baseline)
        sha_row = dict(baseline["files"][0])  # type: ignore[index]
        sha_manifest["files"] = [
            {**sha_row, "sha256": "0" * 64},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        sha_bytes = encode_manifest(sha_manifest)
        self.configure_committed_resources(manifest_bytes=sha_bytes)
        sha_wheel = self.write_wheel(manifest_bytes=sha_bytes)
        self.assert_wheel_rejected(
            sha_wheel,
            message_contains_any=("sha", "digest", "hash"),
        )

    def test_zip_member_size_and_actual_read_size_are_both_checked(self) -> None:
        baseline = manifest_for(BASE_RESOURCES)
        baseline_bytes = encode_manifest(baseline)
        self.configure_committed_resources(manifest_bytes=baseline_bytes)
        relative = next(iter(BASE_RESOURCES))
        member = f"{RESOURCE_PREFIX}{relative}"
        actual_size = len(BASE_RESOURCES[relative])

        wrong_zip_size = self.write_wheel(manifest_bytes=baseline_bytes)
        patch_central_directory_file_size(wrong_zip_size, member, actual_size + 1)
        self.assert_wheel_rejected(
            wrong_zip_size,
            message_contains_any=("size", "byte"),
        )

        actual_read_manifest = dict(baseline)
        actual_read_row = dict(baseline["files"][0])  # type: ignore[index]
        actual_read_manifest["files"] = [
            {**actual_read_row, "bytes": actual_size + 1},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        actual_read_bytes = encode_manifest(actual_read_manifest)
        self.configure_committed_resources(manifest_bytes=actual_read_bytes)
        wrong_actual_read_size = self.write_wheel(manifest_bytes=actual_read_bytes)
        patch_central_directory_file_size(
            wrong_actual_read_size,
            member,
            actual_size + 1,
        )
        self.assert_wheel_rejected(
            wrong_actual_read_size,
            message_contains_any=("size", "byte", "read"),
        )

    def test_semantically_equal_but_byte_different_canonical_manifest_is_rejected(self) -> None:
        manifest = manifest_for(BASE_RESOURCES)
        canonical_bytes = encode_manifest(manifest)
        wheel_bytes = json.dumps(
            manifest,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(json.loads(canonical_bytes), json.loads(wheel_bytes))
        self.assertNotEqual(canonical_bytes, wheel_bytes)
        self.configure_committed_resources(manifest_bytes=canonical_bytes)
        wheel = self.write_wheel(manifest_bytes=wheel_bytes)

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("canonical", "manifest", "byte"),
        )

    def test_resource_bytes_must_equal_the_committed_packaged_mirror(self) -> None:
        _, manifest_bytes = self.baseline()
        mirror_resources = dict(BASE_RESOURCES)
        changed_relative = next(iter(mirror_resources))
        mirror_resources[changed_relative] = b"different committed mirror bytes"
        self.configure_committed_resources(
            manifest_bytes=manifest_bytes,
            mirror_resources=mirror_resources,
        )
        wheel = self.write_wheel(manifest_bytes=manifest_bytes)

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("mirror", "committed", "byte", "resource"),
        )

    def test_missing_canonical_or_mirror_files_are_normalized(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(manifest_bytes=manifest_bytes)

        canonical = self.package_resource_root / "resource-manifest.json"
        canonical.unlink()
        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("manifest", "resource", "read"),
        )

        self.configure_committed_resources(manifest_bytes=manifest_bytes)
        missing_mirror = self.package_resource_root / Path(next(iter(BASE_RESOURCES)))
        missing_mirror.unlink()
        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("mirror", "resource", "read"),
        )

    def test_corrupt_resource_member_read_is_normalized(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(manifest_bytes=manifest_bytes)
        member = f"{RESOURCE_PREFIX}{next(iter(BASE_RESOURCES))}"

        with zipfile.ZipFile(wheel) as archive:
            info = archive.getinfo(member)
            header_offset = info.header_offset
        with wheel.open("r+b") as stream:
            stream.seek(header_offset)
            header = stream.read(30)
            (
                signature,
                _extract_version,
                _flags,
                _compression,
                _time,
                _date,
                _crc,
                _compressed_size,
                _file_size,
                filename_length,
                extra_length,
            ) = struct.unpack("<IHHHHHIIIHH", header)
            self.assertEqual(signature, 0x04034B50)
            payload_offset = header_offset + 30 + filename_length + extra_length
            stream.seek(payload_offset)
            original = stream.read(1)
            self.assertTrue(original)
            stream.seek(payload_offset)
            stream.write(bytes([original[0] ^ 0xFF]))

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("zip", "resource", "read", "crc"),
        )


if __name__ == "__main__":
    unittest.main()
