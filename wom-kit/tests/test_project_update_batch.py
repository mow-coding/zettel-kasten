from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services, project_update_git_runner


class ProjectUpdateBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mirror_fixture = tempfile.TemporaryDirectory()
        self.addCleanup(self.mirror_fixture.cleanup)
        self.unused_mirror = Path(self.mirror_fixture.name).resolve()
        self.runner = (
            project_update_git_runner.TrustedProjectUpdateGitRunner
            .resolve_preapproval()
        )
        self.runner.close_transport_boundary()
        self.addCleanup(self.runner.close)

    @staticmethod
    def git(repository: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def create_repository(self, root: Path, files: dict[str, bytes]) -> Path:
        repository = root / "repository"
        repository.mkdir()
        self.git(repository, "init", "-b", "main")
        self.git(repository, "config", "user.name", "archive-test")
        self.git(
            repository,
            "config",
            "user.email",
            "archive-test.invalid",
        )
        for relative_path, value in files.items():
            path = repository / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        self.git(repository, "add", ".")
        self.git(repository, "commit", "-m", "batch fixture")
        return repository

    @staticmethod
    def blob_oid(value: bytes) -> str:
        hasher = hashlib.sha1()
        hasher.update(f"blob {len(value)}\0".encode("ascii"))
        hasher.update(value)
        return hasher.hexdigest()

    @staticmethod
    def batch_record(object_id: str, value: bytes) -> bytes:
        return (
            f"{object_id} blob {len(value)}\n".encode("ascii")
            + value
            + b"\n"
        )

    def test_tree_loader_uses_one_persistent_cat_file_batch(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required for the batch regression")
        with tempfile.TemporaryDirectory() as tmp:
            files = {
                "a.txt": b"alpha\n",
                "nested/b.txt": b"beta\n",
                "nested/c.txt": b"gamma\n",
            }
            repository = self.create_repository(Path(tmp), files)
            commands: list[list[str]] = []
            real_popen = subprocess.Popen

            def recording_popen(
                command: list[str],
                *args: Any,
                **kwargs: Any,
            ) -> subprocess.Popen[bytes]:
                commands.append(list(command))
                return real_popen(command, *args, **kwargs)

            with patch.object(
                archive_services.subprocess,
                "Popen",
                side_effect=recording_popen,
            ):
                entries = archive_services._wom_kit_project_update_tree_blobs(
                    repository,
                    "HEAD",
                    runner=self.runner,
                )

            self.assertIsNotNone(entries)
            assert entries is not None
            self.assertEqual(
                {path: spec[2] for path, spec in entries.items()},
                files,
            )
            cat_file_commands = [
                command[command.index("cat-file") :]
                for command in commands
                if "cat-file" in command
            ]
            self.assertEqual(cat_file_commands, [["cat-file", "--batch"]])

    def test_duplicate_blob_oids_are_requested_once_and_reused(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required for the duplicate-blob regression")
        with tempfile.TemporaryDirectory() as tmp:
            shared = b"same tracked bytes\n"
            repository = self.create_repository(
                Path(tmp),
                {"first.txt": shared, "second.txt": shared},
            )
            requests: list[list[str]] = []

            def fake_batch(
                command: list[str],
                **kwargs: Any,
            ) -> tuple[int, bytes]:
                del command
                object_ids = kwargs["input_bytes"].decode("ascii").splitlines()
                requests.append(object_ids)
                return 0, b"".join(
                    self.batch_record(object_id, shared)
                    for object_id in object_ids
                )

            with patch.object(
                archive_services,
                "_wom_kit_project_update_run_batch_capped",
                side_effect=fake_batch,
            ):
                entries = archive_services._wom_kit_project_update_tree_blobs(
                    repository,
                    "HEAD",
                    runner=self.runner,
                )

            self.assertIsNotNone(entries)
            assert entries is not None
            self.assertEqual(requests, [[self.blob_oid(shared)]])
            self.assertEqual(entries["first.txt"][2], shared)
            self.assertEqual(entries["second.txt"][2], shared)
            self.assertIs(entries["first.txt"][2], entries["second.txt"][2])

    def test_batch_parser_rejects_malformed_truncated_or_mismatched_output(
        self,
    ) -> None:
        value = b"verified blob\n"
        object_id = self.blob_oid(value)
        other_object_id = "f" * 40
        valid = self.batch_record(object_id, value)
        invalid_outputs = {
            "wrong_type": (
                f"{object_id} tree {len(value)}\n".encode("ascii")
                + value
                + b"\n"
            ),
            "wrong_oid": (
                f"{other_object_id} blob {len(value)}\n".encode("ascii")
                + value
                + b"\n"
            ),
            "declared_size_too_small": (
                f"{object_id} blob {len(value) - 1}\n".encode("ascii")
                + value
                + b"\n"
            ),
            "declared_size_too_large": (
                f"{object_id} blob {len(value) + 1}\n".encode("ascii")
                + value
                + b"\n"
            ),
            "truncated_body": (
                f"{object_id} blob {len(value)}\n".encode("ascii")
                + value[:-1]
            ),
            "missing_header_newline": (
                f"{object_id} blob {len(value)}".encode("ascii")
            ),
            "extra_trailing_frame": valid + b"unexpected\n",
            "body_hash_mismatch": (
                f"{object_id} blob {len(value)}\n".encode("ascii")
                + b"X"
                + value[1:]
                + b"\n"
            ),
        }
        for case_name, output in invalid_outputs.items():
            with (
                self.subTest(case=case_name),
                patch.object(
                    archive_services,
                    "_wom_kit_project_update_run_batch_capped",
                    return_value=(0, output),
                ),
            ):
                self.assertIsNone(
                    archive_services._wom_kit_project_update_git_blob_batch(
                        self.unused_mirror,
                        {object_id: 1},
                        runner=self.runner,
                    )
                )

    def test_batch_parser_rejects_file_and_logical_total_overflow(self) -> None:
        object_id = self.blob_oid(b"small")
        oversized_file_header = (
            f"{object_id} blob "
            f"{archive_services.WOM_KIT_PROJECT_UPDATE_MAX_TRACKED_FILE_BYTES + 1}\n"
        ).encode("ascii")
        logical_total_header = (
            f"{object_id} blob "
            f"{archive_services.WOM_KIT_PROJECT_UPDATE_MAX_TRACKED_FILE_BYTES}\n"
        ).encode("ascii")
        for case_name, output, path_count in (
            ("file", oversized_file_header, 1),
            ("logical_total", logical_total_header, 9),
        ):
            with (
                self.subTest(case=case_name),
                patch.object(
                    archive_services,
                    "_wom_kit_project_update_run_batch_capped",
                    return_value=(0, output),
                ),
            ):
                self.assertIsNone(
                    archive_services._wom_kit_project_update_git_blob_batch(
                        self.unused_mirror,
                        {object_id: path_count},
                        runner=self.runner,
                    )
                )

    def test_batch_transport_enforces_output_cap_and_timeout(self) -> None:
        environment = dict(os.environ)
        overflow = archive_services._wom_kit_project_update_run_batch_capped(
            [
                sys.executable,
                "-c",
                (
                    "import sys; sys.stdin.buffer.read(); "
                    "sys.stdout.buffer.write(b'x' * 1024); "
                    "sys.stdout.buffer.flush()"
                ),
            ],
            environment=environment,
            timeout_seconds=5,
            max_output_bytes=16,
            input_bytes=b"request\n",
        )
        self.assertIsNone(overflow)

        timed_out = archive_services._wom_kit_project_update_run_batch_capped(
            [
                sys.executable,
                "-c",
                "import sys,time; sys.stdin.buffer.read(); time.sleep(10)",
            ],
            environment=environment,
            timeout_seconds=0.05,
            max_output_bytes=16,
            input_bytes=b"request\n",
        )
        self.assertIsNone(timed_out)


if __name__ == "__main__":
    unittest.main()
