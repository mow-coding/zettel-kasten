from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = KIT_ROOT / "cli" / "archive.py"


def _load_wrapper_definitions() -> types.ModuleType:
    source = WRAPPER_PATH.read_text(encoding="utf-8")
    definitions, marker, _ = source.partition(
        '\nif any(\n    name == "wom_kit"'
    )
    if not marker:
        raise AssertionError("wrapper bootstrap boundary was not found")
    module = types.ModuleType("wom_archive_bridge_test_subject")
    module.__file__ = str(WRAPPER_PATH)
    previous_dont_write_bytecode = sys.dont_write_bytecode
    try:
        exec(compile(definitions, str(WRAPPER_PATH), "exec"), module.__dict__)
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
    return module


def _blob_oid(value: bytes) -> str:
    framed = f"blob {len(value)}\0".encode("ascii") + value
    return hashlib.sha1(framed).hexdigest()


def _batch_response(
    blobs: dict[str, bytes],
    *,
    order: list[str] | None = None,
) -> bytes:
    ordered = sorted(blobs) if order is None else order
    return b"".join(
        (
            f"{object_id} blob {len(blobs[object_id])}\n".encode("ascii")
            + blobs[object_id]
            + b"\n"
        )
        for object_id in ordered
    )


class ArchiveBridgeResourceBatchingTests(unittest.TestCase):
    def test_runtime_resource_verifier_uses_exactly_three_git_children(
        self,
    ) -> None:
        module = _load_wrapper_definitions()
        resource_bytes = b'{"fixture":true}\n'
        source_logical = "schemas/runtime-fixture.schema.json"
        packaged_logical = "schemas/runtime-fixture.schema.json"
        manifest_bytes = (
            json.dumps(
                {
                    "schema": "wom-kit/package-resource-manifest/v0.1",
                    "version": "0.3.291",
                    "source_of_truth": "wom-kit source resource directories",
                    "file_count": 1,
                    "files": [
                        {
                            "source": source_logical,
                            "packaged": packaged_logical,
                            "bytes": len(resource_bytes),
                            "sha256": hashlib.sha256(
                                resource_bytes
                            ).hexdigest(),
                        }
                    ],
                },
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        init_bytes = b'"""Packaged WOM resources."""\n'
        unrelated_bytes = b"unrelated tree entry\n"

        manifest_path = module.RESOURCE_MANIFEST_GIT_PATH
        source_path = "wom-kit/schemas/runtime-fixture.schema.json"
        packaged_path = (
            "wom-kit/src/wom_kit/_resources/schemas/"
            "runtime-fixture.schema.json"
        )
        init_path = "wom-kit/src/wom_kit/_resources/__init__.py"
        unrelated_path = "README.md"
        path_bytes = {
            manifest_path: manifest_bytes,
            source_path: resource_bytes,
            packaged_path: resource_bytes,
            init_path: init_bytes,
            unrelated_path: unrelated_bytes,
        }
        tree_output = b"".join(
            (
                f"100644 blob {_blob_oid(value)}\t{relative_path}\0"
            ).encode("utf-8")
            for relative_path, value in sorted(path_bytes.items())
        )
        index_output = b"".join(
            (
                f"100644 {_blob_oid(value)} 0\t{relative_path}\0"
            ).encode("utf-8")
            for relative_path, value in sorted(path_bytes.items())
        )
        batch_blobs = {
            _blob_oid(manifest_bytes): manifest_bytes,
            _blob_oid(resource_bytes): resource_bytes,
        }
        expected_batch_input = b"".join(
            object_id.encode("ascii") + b"\n"
            for object_id in sorted(batch_blobs)
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            for relative_path, value in path_bytes.items():
                if relative_path == unrelated_path:
                    continue
                destination = project_root.joinpath(
                    *relative_path.split("/")
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(value)
            module.PROJECT_ROOT = project_root

            calls: list[tuple[list[str], bytes | None]] = []

            def fake_git_output(
                args: list[str],
                *,
                max_bytes: int = module.MAX_GIT_OUTPUT_BYTES,
                input_bytes: bytes | None = None,
            ) -> bytes | None:
                del max_bytes
                calls.append((list(args), input_bytes))
                if args == [
                    "ls-tree",
                    "-r",
                    "-z",
                    "--full-tree",
                    "BOUND_REF",
                ]:
                    return tree_output
                if args == ["cat-file", "--batch"]:
                    self.assertEqual(input_bytes, expected_batch_input)
                    return _batch_response(batch_blobs)
                if args == ["ls-files", "--stage", "-z"]:
                    self.assertIsNone(input_bytes)
                    return index_output
                self.fail(f"unexpected Git child invocation: {args!r}")

            module._git_output = fake_git_output
            started = time.perf_counter()
            self.assertTrue(
                module._runtime_resources_match_ref("BOUND_REF")
            )
            elapsed = time.perf_counter() - started

        self.assertEqual(len(calls), 3)
        self.assertEqual(
            [call[0][0] for call in calls],
            ["ls-tree", "cat-file", "ls-files"],
        )
        self.assertNotIn("--", calls[0][0])
        self.assertNotIn("--", calls[2][0])
        self.assertLess(elapsed, 5.0)

    def test_blob_batch_parser_fails_closed_on_response_corruption(
        self,
    ) -> None:
        module = _load_wrapper_definitions()
        first = b"first payload\n"
        second = b"second\x00payload"
        blobs = {
            _blob_oid(first): first,
            _blob_oid(second): second,
        }
        expected_sizes = {
            object_id: len(value)
            for object_id, value in blobs.items()
        }
        valid = _batch_response(blobs)
        with patch.object(module, "_git_output", return_value=valid):
            self.assertEqual(module._git_blob_batch(expected_sizes), blobs)

        ordered = sorted(blobs)
        first_id = ordered[0]
        first_header = (
            f"{first_id} blob {len(blobs[first_id])}\n".encode("ascii")
        )
        first_separator = len(first_header) + len(blobs[first_id])
        changed_body = bytearray(valid)
        changed_body[len(first_header)] ^= 1
        corruptions = {
            "truncated": valid[:-1],
            "extra_response_bytes": valid + b"EXTRA",
            "wrong_order": _batch_response(
                blobs,
                order=list(reversed(ordered)),
            ),
            "wrong_type": valid.replace(b" blob ", b" tree ", 1),
            "wrong_size": valid.replace(
                first_header,
                (
                    f"{first_id} blob {len(blobs[first_id]) + 1}\n"
                ).encode("ascii"),
                1,
            ),
            "missing_body_separator": (
                valid[:first_separator] + valid[first_separator + 1 :]
            ),
            "body_hash_mismatch": bytes(changed_body),
        }
        for case_name, response in corruptions.items():
            with self.subTest(case=case_name), patch.object(
                module,
                "_git_output",
                return_value=response,
            ):
                self.assertIsNone(module._git_blob_batch(expected_sizes))

    def test_capped_runner_writes_only_bounded_explicit_stdin(self) -> None:
        module = _load_wrapper_definitions()
        payload = b"$() `not shell syntax` ; & | <literal>\x00"
        command = [
            sys.executable,
            "-I",
            "-S",
            "-c",
            (
                "import sys;"
                "sys.stdout.buffer.write(sys.stdin.buffer.read()[::-1])"
            ),
        ]
        self.assertEqual(
            module._run_capped(
                command,
                len(payload),
                input_bytes=payload,
            ),
            payload[::-1],
        )
        self.assertIsNone(
            module._run_capped(
                command,
                len(payload),
                input_bytes=b"x" * (module.MAX_GIT_STDIN_BYTES + 1),
            )
        )


if __name__ == "__main__":
    unittest.main()
