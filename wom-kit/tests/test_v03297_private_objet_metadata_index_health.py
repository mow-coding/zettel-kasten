from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Any
import unittest
from unittest import mock

from wom_kit import private_objet_metadata_index_health as health
from wom_kit import private_objet_metadata_index_session as session
from wom_kit.private_objet_metadata_index import (
    PrivateObjetIndexInspection,
    _compile_private_objet_index_projection as compile_private_objet_index_projection,
    install_private_objet_index_projection,
)
from wom_kit.private_objet_metadata_index_authority import (
    _PrivateObjetIndexAuthorityCapture as PrivateObjetIndexAuthorityCapture,
    _capture_private_objet_index_authority as capture_private_objet_index_authority,
)


NONEMPTY_COUNTS = session.PrivateObjetMetadataCounts(2, 5, 2, 4, 1, 2)


def authority_capture(
    *,
    empty: bool,
    fingerprint_sha256: str,
) -> PrivateObjetIndexAuthorityCapture:
    compiler_input = {
        "private_manifest_state": "absent" if empty else "present_nonempty"
    }
    return PrivateObjetIndexAuthorityCapture(
        _compiler_input_bytes=json.dumps(compiler_input).encode("ascii"),
        _fingerprint_bytes=b"{}",
        fingerprint_sha256=fingerprint_sha256,
        comparison_token=("authority", fingerprint_sha256, "stable"),
    )


def inspection(
    *,
    counts: session.PrivateObjetMetadataCounts = NONEMPTY_COUNTS,
    fingerprint_sha256: str = "sha256:" + ("a" * 64),
    private_values: tuple[object, ...] = (),
) -> PrivateObjetIndexInspection:
    return PrivateObjetIndexInspection(
        observation_count=counts.observation_count,
        alias_count=counts.alias_count,
        distinct_object_count=counts.distinct_object_count,
        projection_count=counts.projection_count,
        blocked_alias_derivation_count=counts.blocked_alias_derivation_count,
        blocked_label_projection_count=counts.blocked_label_projection_count,
        observation_rows_sha256="sha256:" + ("b" * 64),
        alias_rows_sha256="sha256:" + ("c" * 64),
        projection_rows_sha256="sha256:" + ("d" * 64),
        authority_fingerprint_sha256=fingerprint_sha256,
        metadata_row=private_values,
    )


class FakeReadAPI:
    def __init__(
        self,
        *,
        table_names: tuple[str, ...] = (
            "objet_name_aliases",
            "objet_source_metadata",
            "private_objet_index_metadata",
            "private_objet_label_projections",
        ),
        singleton_count: int = 1,
        inspected: PrivateObjetIndexInspection | BaseException | None = None,
    ) -> None:
        self.table_names = table_names
        self.singleton_count = singleton_count
        self.inspected = inspected or inspection()
        self.inspection_calls = 0

    def fetch_all(
        self,
        _sql: str,
        _parameters: object = (),
    ) -> tuple[tuple[object, ...], ...]:
        return tuple((name,) for name in self.table_names)

    def scalar(self, _sql: str, _parameters: object = ()) -> object:
        return self.singleton_count

    def inspect_private_objet_index_semantics(
        self,
        *,
        expected: object | None = None,
    ) -> object:
        self.inspection_calls += 1
        if isinstance(self.inspected, BaseException):
            raise self.inspected
        return self.inspected


def public_health(
    *,
    blockers: list[str] | None = None,
    stale_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "index_health",
        "archive_id": "archive-safe",
        "index_path": "db/archive-index.sqlite",
        "index_state": "current",
        "summary": {"legacy": True},
        "samples": {"legacy": []},
        "stale_reasons": stale_reasons or [],
        "privacy_guards": {"writes": False},
        "would_change": [],
        "next_safe_actions": ["legacy"],
        "blockers": blockers or [],
        "warnings": [],
    }


def decision_for(case_id: str) -> session.PrivateObjetMetadataHealthDecision:
    counts = NONEMPTY_COUNTS if case_id in {"C9", "C11"} else None
    envelope = session.build_private_objet_metadata_health_envelope(
        case_id,
        counts=counts,
    )
    return health._decision(case_id, envelope)


class PrivateObjetHealthProbeTests(unittest.TestCase):
    def test_real_empty_authority_missing_and_current_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / session.PRIVATE_INDEX_RELATIVE_PATH
            db_path.parent.mkdir(parents=True)

            missing = health.evaluate_private_objet_metadata_index_health(
                root,
                "synthetic-private-index",
            )
            self.assertEqual(missing.case_id, "C5")
            self.assertEqual(missing.envelope["diagnostic_codes"], [])

            authority = capture_private_objet_index_authority(
                root,
                "synthetic-private-index",
            )
            projection = compile_private_objet_index_projection(
                authority.compiler_input
            )
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("PRAGMA foreign_keys=ON")
                self.assertEqual(
                    connection.execute("PRAGMA foreign_keys").fetchone()[0],
                    1,
                )
                connection.execute("BEGIN IMMEDIATE")
                install_private_objet_index_projection(
                    connection,
                    projection,
                )
                connection.commit()
            finally:
                connection.close()

            current = health.evaluate_private_objet_metadata_index_health(
                root,
                "synthetic-private-index",
            )
            self.assertEqual(current.case_id, "C10")
            self.assertEqual(
                [current.envelope[key] for key in session.PRIVATE_HEALTH_KEYS[12:18]],
                [0, 0, 0, 0, 0, 0],
            )
            self.assertEqual(current.envelope["diagnostic_codes"], [])

    def test_missing_table_and_missing_singleton_are_c8_not_c7(self) -> None:
        missing_table = FakeReadAPI(
            table_names=(
                "objet_name_aliases",
                "objet_source_metadata",
                "private_objet_index_metadata",
            )
        )
        probe = health._probe_private_projection(missing_table)  # type: ignore[arg-type]
        envelope = health._envelope_from_probe(
            probe,
            authority_capture(
                empty=False,
                fingerprint_sha256="sha256:" + ("a" * 64),
            ),
        )
        self.assertEqual(
            envelope,
            session.build_private_objet_metadata_health_envelope("C8"),
        )
        self.assertEqual(missing_table.inspection_calls, 0)

        missing_singleton = FakeReadAPI(singleton_count=0)
        probe = health._probe_private_projection(  # type: ignore[arg-type]
            missing_singleton
        )
        envelope = health._envelope_from_probe(
            probe,
            authority_capture(
                empty=False,
                fingerprint_sha256="sha256:" + ("a" * 64),
            ),
        )
        self.assertEqual(
            envelope["diagnostic_codes"],
            ["private_objet_metadata_missing"],
        )
        self.assertIs(envelope["private_layer_complete"], False)
        self.assertEqual(missing_singleton.inspection_calls, 0)

    def test_valid_stale_empty_and_nonempty_projection_derivations(self) -> None:
        stale_api = FakeReadAPI(
            inspected=inspection(
                fingerprint_sha256="sha256:" + ("a" * 64)
            )
        )
        stale = health._envelope_from_probe(
            health._probe_private_projection(stale_api),  # type: ignore[arg-type]
            authority_capture(
                empty=False,
                fingerprint_sha256="sha256:" + ("e" * 64),
            ),
        )
        self.assertEqual(health._case_id_from_envelope(stale), "C9")
        self.assertEqual(
            [stale[key] for key in session.PRIVATE_HEALTH_KEYS[12:18]],
            list(NONEMPTY_COUNTS.as_values()),
        )
        self.assertIsNone(stale["empty_authority"])

        empty_counts = session.PrivateObjetMetadataCounts(0, 0, 0, 0, 0, 0)
        empty_api = FakeReadAPI(
            inspected=inspection(
                counts=empty_counts,
                fingerprint_sha256="sha256:" + ("f" * 64),
            )
        )
        empty = health._envelope_from_probe(
            health._probe_private_projection(empty_api),  # type: ignore[arg-type]
            authority_capture(
                empty=True,
                fingerprint_sha256="sha256:" + ("f" * 64),
            ),
        )
        self.assertEqual(health._case_id_from_envelope(empty), "C10")
        self.assertEqual(
            [empty[key] for key in session.PRIVATE_HEALTH_KEYS[12:18]],
            [0, 0, 0, 0, 0, 0],
        )

        current_api = FakeReadAPI()
        current = health._envelope_from_probe(
            health._probe_private_projection(current_api),  # type: ignore[arg-type]
            authority_capture(
                empty=False,
                fingerprint_sha256="sha256:" + ("a" * 64),
            ),
        )
        self.assertEqual(health._case_id_from_envelope(current), "C11")
        self.assertIs(current["empty_authority"], False)

    def test_current_fingerprint_with_contradictory_empty_state_blocks(self) -> None:
        api = FakeReadAPI()
        probe = health._probe_private_projection(api)  # type: ignore[arg-type]
        authority = authority_capture(
            empty=True,
            fingerprint_sha256="sha256:" + ("a" * 64),
        )
        with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
            health._envelope_from_probe(probe, authority)
        self.assertEqual(
            caught.exception.code,
            "private_objet_metadata_projection_invalid",
        )

    def test_projection_probe_rejects_invalid_singleton_and_inspector(self) -> None:
        for api in (
            FakeReadAPI(singleton_count=True),  # type: ignore[arg-type]
            FakeReadAPI(singleton_count=2),
            FakeReadAPI(inspected=object()),  # type: ignore[arg-type]
        ):
            with self.subTest(api=api):
                with self.assertRaises(
                    session.PrivateObjetIndexSessionError
                ) as caught:
                    health._probe_private_projection(api)  # type: ignore[arg-type]
                self.assertEqual(
                    caught.exception.code,
                    "private_objet_metadata_projection_invalid",
                )

    def test_same_transaction_final_probe_is_repeated(self) -> None:
        api = FakeReadAPI()
        capture = authority_capture(
            empty=False,
            fingerprint_sha256="sha256:" + ("a" * 64),
        )

        def run_session(
            _root: object,
            consumer: object,
            *,
            capture_authority: object,
            inspect_health: object,
            final_check: object,
        ) -> dict[str, object]:
            captured = capture_authority()  # type: ignore[operator]
            result = inspect_health(api, captured)  # type: ignore[operator]
            self.assertIsNone(consumer(api, result))  # type: ignore[operator]
            self.assertIs(final_check(api, captured), True)  # type: ignore[operator]
            return result

        with (
            mock.patch.object(
                health,
                "_capture_private_objet_index_authority",
                return_value=capture,
            ),
            mock.patch.object(
                health,
                "_with_private_objet_index_read_session",
                side_effect=run_session,
            ),
            mock.patch.object(
                health,
                "_compile_private_objet_index_projection",
                return_value=mock.sentinel.expected_projection,
            ),
        ):
            decision = health.evaluate_private_objet_metadata_index_health(
                Path("synthetic-root"),
                "archive-safe",
            )
        self.assertEqual(decision.case_id, "C11")
        self.assertEqual(api.inspection_calls, 3)


class PrivateObjetHealthDecisionTests(unittest.TestCase):
    def test_session_failures_map_to_closed_content_free_cases(self) -> None:
        expected = {
            "private_objet_metadata_snapshot_changed": "C1",
            "private_objet_metadata_authority_blocked": "C3",
            "private_objet_metadata_authority_invalid": "C4",
            "private_objet_metadata_projection_unavailable": "C6",
            "private_objet_metadata_projection_invalid": "C7",
            "private_objet_metadata_missing": "C8",
        }
        for code, case_id in expected.items():
            with self.subTest(code=code):
                with mock.patch.object(
                    health,
                    "_with_private_objet_index_read_session",
                    side_effect=session.PrivateObjetIndexSessionError(code),
                ):
                    decision = (
                        health.evaluate_private_objet_metadata_index_health(
                            Path("not-read"),
                            "archive-safe",
                        )
                    )
                self.assertEqual(decision.case_id, case_id)
                self.assertEqual(
                    tuple(decision.envelope),
                    session.PRIVATE_HEALTH_KEYS,
                )

    def test_unexpected_exception_is_sanitized_as_unavailable(self) -> None:
        exception_token = "_".join(
            ("WOMV03297", "PRIVATE", "EXCEPTION", "CANARY", "N1")
        )
        with mock.patch.object(
            health,
            "_with_private_objet_index_read_session",
            side_effect=RuntimeError(exception_token),
        ):
            decision = health.evaluate_private_objet_metadata_index_health(
                Path("not-read"),
                "archive-safe",
            )
        rendered = json.dumps(decision.envelope, sort_keys=True)
        self.assertEqual(decision.case_id, "C6")
        self.assertNotIn(exception_token, rendered)
        self.assertEqual(
            decision.envelope["diagnostic_codes"],
            ["private_objet_metadata_projection_unavailable"],
        )

    def test_every_c1_c11_decision_composes_exact_top_level_delta(self) -> None:
        expected = {
            "C1": (
                ["private_objet_metadata_snapshot_changed"],
                [],
                "blocked",
            ),
            "C2": (
                ["private_objet_metadata_projection_unavailable"],
                [],
                "blocked",
            ),
            "C3": (
                ["private_objet_metadata_authority_blocked"],
                [],
                "blocked",
            ),
            "C4": (
                ["private_objet_metadata_authority_invalid"],
                [],
                "blocked",
            ),
            "C5": (
                ["archive_index_missing"],
                ["index_health_blocked"],
                "blocked",
            ),
            "C6": (
                ["private_objet_metadata_projection_unavailable"],
                [],
                "blocked",
            ),
            "C7": (
                ["private_objet_metadata_projection_invalid"],
                [],
                "blocked",
            ),
            "C8": (
                [],
                ["private_objet_metadata_missing"],
                "stale_or_incomplete",
            ),
            "C9": (
                [],
                ["private_objet_metadata_stale"],
                "stale_or_incomplete",
            ),
            "C10": ([], [], "current"),
            "C11": ([], [], "current"),
        }
        for case_id, (blockers, stale_reasons, index_state) in expected.items():
            with self.subTest(case_id=case_id):
                result = health.compose_private_objet_metadata_index_health(
                    public_health(),
                    decision_for(case_id),
                )
                self.assertEqual(
                    tuple(result),
                    (*health.PUBLIC_INDEX_HEALTH_KEYS, "private_objet_metadata"),
                )
                self.assertEqual(result["blockers"], blockers)
                self.assertEqual(result["stale_reasons"], stale_reasons)
                self.assertEqual(result["index_state"], index_state)
                self.assertIs(result["ok"], index_state == "current")
                self.assertEqual(
                    tuple(result["private_objet_metadata"]),
                    session.PRIVATE_HEALTH_KEYS,
                )

    def test_c5_legacy_missing_codes_are_deduplicated_once(self) -> None:
        result = health.compose_private_objet_metadata_index_health(
            public_health(
                blockers=["archive_index_missing"],
                stale_reasons=["index_health_blocked"],
            ),
            decision_for("C5"),
        )
        self.assertEqual(result["blockers"], ["archive_index_missing"])
        self.assertEqual(result["stale_reasons"], ["index_health_blocked"])
        self.assertEqual(
            result["private_objet_metadata"]["diagnostic_codes"],
            [],
        )

    def test_legacy_values_and_order_are_preserved_except_composed_fields(
        self,
    ) -> None:
        source = public_health(
            blockers=["legacy_blocker"],
            stale_reasons=["legacy_stale"],
        )
        result = health.compose_private_objet_metadata_index_health(
            source,
            decision_for("C9"),
        )
        for key in health.PUBLIC_INDEX_HEALTH_KEYS:
            if key not in {
                "ok",
                "index_state",
                "stale_reasons",
                "blockers",
                "next_safe_actions",
            }:
                self.assertEqual(result[key], source[key])
        self.assertEqual(result["blockers"], ["legacy_blocker"])
        self.assertEqual(
            result["stale_reasons"],
            ["legacy_stale", "private_objet_metadata_stale"],
        )
        self.assertEqual(result["index_state"], "blocked")
        self.assertIs(result["ok"], False)
        self.assertEqual(result["next_safe_actions"][0], "legacy")
        self.assertIn(
            "archive index <archive-root> --progress --format json",
            result["next_safe_actions"][1],
        )
        self.assertIn(
            "archive index-health <archive-root> --dry-run --progress --format json",
            result["next_safe_actions"][2],
        )

    def test_invalid_public_shape_and_mutated_decision_fail_closed(self) -> None:
        wrong_order = public_health()
        value = wrong_order.pop("warnings")
        wrong_order["warnings"] = value
        # Moving an already-last key is a no-op; move a middle key instead.
        value = wrong_order.pop("summary")
        wrong_order["summary"] = value
        with self.assertRaises(ValueError):
            health.compose_private_objet_metadata_index_health(
                wrong_order,
                decision_for("C11"),
            )

        valid = decision_for("C11")
        mutated = replace(valid, translation="blocked")
        with self.assertRaises(ValueError):
            health.compose_private_objet_metadata_index_health(
                public_health(),
                mutated,
            )

    def test_private_runtime_values_and_digests_do_not_enter_envelope(self) -> None:
        prefix = "_".join(("WOMV03297", "PRIVATE")) + "_"
        plain_tokens = tuple(
            prefix + suffix
            for suffix in (
                "FILENAME_" + "CANARY_N1.DAT",
                "LABEL_" + "CANARY_N1",
                "PATH_" + "CANARY_N1",
                "PROVIDER_" + "CANARY_N1",
                "SOURCE_" + "CANARY_N1",
                "REVIEWER_" + "CANARY_N1",
            )
        )

        def digest_token(core: str) -> str:
            return "sha256:" + hashlib.sha256(
                (prefix + core).encode("utf-8")
            ).hexdigest()

        fingerprint = digest_token("AUTHORITY_" + "FINGERPRINT_CANARY_N1")
        private_digests = (
            digest_token("OBJECT_" + "ID_CANARY_N1"),
            digest_token("RECEIPT_" + "CANARY_N1"),
            digest_token("OBSERVATION_" + "ROWS_CANARY_N1"),
            digest_token("ALIAS_" + "ROWS_CANARY_N1"),
            digest_token("PROJECTION_" + "ROWS_CANARY_N1"),
        )
        api = FakeReadAPI(
            inspected=replace(
                inspection(
                    fingerprint_sha256=fingerprint,
                    private_values=(*plain_tokens, *private_digests),
                ),
                observation_rows_sha256=private_digests[2],
                alias_rows_sha256=private_digests[3],
                projection_rows_sha256=private_digests[4],
            )
        )
        envelope = health._envelope_from_probe(
            health._probe_private_projection(api),  # type: ignore[arg-type]
            authority_capture(
                empty=False,
                fingerprint_sha256=fingerprint,
            ),
        )
        rendered = json.dumps(envelope, sort_keys=True)
        self.assertEqual(health._case_id_from_envelope(envelope), "C11")
        for token in (*plain_tokens, *private_digests, fingerprint, prefix):
            self.assertNotIn(token, rendered)


if __name__ == "__main__":
    unittest.main()
