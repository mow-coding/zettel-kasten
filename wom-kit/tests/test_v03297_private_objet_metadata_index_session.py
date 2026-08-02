from __future__ import annotations

from dataclasses import dataclass, replace
import inspect
import json
from pathlib import Path
import sqlite3
import tempfile
from types import MappingProxyType
import unittest
from unittest import mock

from wom_kit import private_objet_metadata_index_session as session


NONEMPTY_COUNTS = session.PrivateObjetMetadataCounts(2, 5, 2, 4, 1, 2)
EMPTY_COUNTS = session.PrivateObjetMetadataCounts(0, 0, 0, 0, 0, 0)


@dataclass(frozen=True)
class SyntheticAuthorityCapture:
    comparison_token: tuple[str, int]
    fingerprint_sha256: str = "sha256:" + ("a" * 64)
    private_manifest_state: str = "present_nonempty"


class RecordingConnection:
    def __init__(
        self,
        connection: sqlite3.Connection,
        events: list[tuple[str, str]],
        *,
        rollback_fails: bool = False,
    ) -> None:
        self._connection = connection
        self._events = events
        self._rollback_fails = rollback_fails
        self.rollback_calls = 0
        self.close_calls = 0

    @property
    def row_factory(self) -> object:
        return self._connection.row_factory

    @row_factory.setter
    def row_factory(self, value: object) -> None:
        self._events.append(("setup", "row_factory"))
        self._connection.row_factory = value

    @property
    def in_transaction(self) -> bool:
        return self._connection.in_transaction

    def execute(
        self,
        sql: str,
        parameters: object = (),
    ) -> sqlite3.Cursor:
        normalized = " ".join(sql.split())
        self._events.append(("execute", normalized))
        return self._connection.execute(sql, parameters)  # type: ignore[arg-type]

    def set_authorizer(self, callback: object) -> None:
        self._events.append(
            ("authorizer", "clear" if callback is None else "install")
        )
        self._connection.set_authorizer(callback)  # type: ignore[arg-type]

    def rollback(self) -> None:
        self.rollback_calls += 1
        self._events.append(("lifecycle", "rollback"))
        if self._rollback_fails:
            raise sqlite3.OperationalError("SYNTHETIC_PRIVATE_ROLLBACK_CANARY")
        self._connection.rollback()

    def close(self) -> None:
        self.close_calls += 1
        self._events.append(("lifecycle", "close"))
        self._connection.close()


def create_synthetic_archive(
    root: Path,
    *,
    wal: bool = False,
) -> sqlite3.Connection | None:
    db_path = root / session.PRIVATE_INDEX_RELATIVE_PATH
    db_path.parent.mkdir(parents=True)
    connection = sqlite3.connect(db_path)
    if wal:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute("CREATE TABLE private_probe(value INTEGER NOT NULL)")
    connection.execute("INSERT INTO private_probe(value) VALUES (1)")
    connection.commit()
    if wal:
        return connection
    connection.close()
    return None


def current_health() -> dict[str, object]:
    return session.build_private_objet_metadata_health_envelope(
        "C11",
        counts=NONEMPTY_COUNTS,
    )


def run_session(
    root: Path,
    *,
    captures: list[SyntheticAuthorityCapture] | None = None,
    consumer: object | None = None,
    inspect_health: object | None = None,
    final_check: object | None = None,
) -> dict[str, object]:
    capture_values = iter(
        captures
        or [
            SyntheticAuthorityCapture(("authority", 1)),
            SyntheticAuthorityCapture(("authority", 1)),
        ]
    )

    def default_consumer(
        api: session.PrivateObjetIndexReadAPI,
        health: object,
    ) -> None:
        assert api.scalar("SELECT COUNT(*) FROM private_probe") == 1
        assert isinstance(health, MappingProxyType)
        return None

    return session._with_private_objet_index_read_session(
        root,
        consumer or default_consumer,  # type: ignore[arg-type]
        capture_authority=lambda: next(capture_values),
        inspect_health=inspect_health  # type: ignore[arg-type]
        or (lambda _api, _authority: current_health()),
        final_check=final_check  # type: ignore[arg-type]
        or (
            lambda api, _authority: (
                api.scalar("SELECT COUNT(*) FROM private_probe") == 1
            )
        ),
    )


class PrivateObjetMetadataHealthContractTests(unittest.TestCase):
    def observation(self, **changes: object) -> session.PrivateObjetMetadataHealthObservation:
        values: dict[str, object] = {
            "authority_token_a": ("authority", 1),
            "authority_token_b": ("authority", 1),
            "authority_validity": "valid",
            "db_identity_token_a": ("db", 1),
            "db_identity_token_b": ("db", 1),
            "db_present": True,
            "projection_unavailable": False,
            "db_path_safe": True,
            "required_private_tables_present": True,
            "singleton_present": True,
            "schema_matches": True,
            "count_digest_matches": True,
            "fingerprint_matches": True,
            "empty_authority": False,
            "counts": NONEMPTY_COUNTS,
        }
        values.update(changes)
        return session.PrivateObjetMetadataHealthObservation(**values)  # type: ignore[arg-type]

    def test_all_c1_c11_envelopes_have_exact_19_key_order_and_closed_diagnostics(
        self,
    ) -> None:
        for case_id in [f"C{index}" for index in range(1, 12)]:
            with self.subTest(case_id=case_id):
                counts = NONEMPTY_COUNTS if case_id in {"C9", "C11"} else None
                envelope = session.build_private_objet_metadata_health_envelope(
                    case_id,
                    counts=counts,
                )
                self.assertEqual(tuple(envelope), session.PRIVATE_HEALTH_KEYS)
                self.assertEqual(len(envelope), 19)
                self.assertEqual(
                    envelope["schema"],
                    session.PRIVATE_HEALTH_SCHEMA,
                )
                diagnostics = envelope["diagnostic_codes"]
                self.assertIs(type(diagnostics), list)
                self.assertLessEqual(len(diagnostics), 1)  # type: ignore[arg-type]
                self.assertTrue(
                    set(diagnostics).issubset(  # type: ignore[arg-type]
                        session.PRIVATE_HEALTH_DIAGNOSTIC_CODES
                    )
                )
                self.assertEqual(
                    session.validate_private_objet_metadata_health_envelope(
                        envelope
                    ),
                    envelope,
                )

    def test_exact_null_false_and_zero_semantics(self) -> None:
        c7 = session.build_private_objet_metadata_health_envelope("C7")
        c8 = session.build_private_objet_metadata_health_envelope("C8")
        c10 = session.build_private_objet_metadata_health_envelope("C10")
        for envelope in (c7, c8):
            self.assertIsNone(envelope["empty_authority"])
            self.assertIs(envelope["private_layer_complete"], False)
            self.assertTrue(
                all(envelope[key] is None for key in session.PRIVATE_HEALTH_KEYS[12:18])
            )
        self.assertIs(c10["empty_authority"], True)
        self.assertEqual(
            [c10[key] for key in session.PRIVATE_HEALTH_KEYS[12:18]],
            [0, 0, 0, 0, 0, 0],
        )
        mutated = dict(c10)
        mutated["observation_count"] = False
        with self.assertRaises(session.PrivateObjetIndexSessionError):
            session.validate_private_objet_metadata_health_envelope(mutated)

    def test_classifier_reaches_every_case_in_strict_first_match_order(self) -> None:
        cases = {
            "C1": self.observation(authority_token_b=("authority", 2)),
            "C2": self.observation(db_identity_token_b=("db", 2)),
            "C3": self.observation(authority_validity="blocked"),
            "C4": self.observation(authority_validity="invalid"),
            "C5": self.observation(db_present=False),
            "C6": self.observation(projection_unavailable=True),
            "C7": self.observation(schema_matches=False),
            "C8": self.observation(required_private_tables_present=False),
            "C9": self.observation(fingerprint_matches=False),
            "C10": self.observation(empty_authority=True, counts=None),
            "C11": self.observation(),
        }
        for expected, observation in cases.items():
            with self.subTest(expected=expected):
                decision = session.classify_private_objet_metadata_health(observation)
                self.assertEqual(decision.case_id, expected)
                self.assertEqual(tuple(decision.envelope), session.PRIVATE_HEALTH_KEYS)

    def test_c7_and_c8_are_disjoint_even_when_whole_manifest_mismatches(self) -> None:
        missing_table = self.observation(
            required_private_tables_present=False,
            schema_matches=False,
            count_digest_matches=False,
        )
        missing_singleton = self.observation(
            singleton_present=False,
            schema_matches=False,
            count_digest_matches=False,
        )
        all_present_schema_tamper = self.observation(schema_matches=False)
        all_present_digest_tamper = self.observation(count_digest_matches=False)
        unsafe_path = self.observation(db_path_safe=False)
        self.assertEqual(
            session.classify_private_objet_metadata_health(missing_table).case_id,
            "C8",
        )
        self.assertEqual(
            session.classify_private_objet_metadata_health(missing_singleton).case_id,
            "C8",
        )
        for observation in (
            all_present_schema_tamper,
            all_present_digest_tamper,
            unsafe_path,
        ):
            self.assertEqual(
                session.classify_private_objet_metadata_health(observation).case_id,
                "C7",
            )

    def test_c1_precedes_simultaneous_db_identity_drift(self) -> None:
        decision = session.classify_private_objet_metadata_health(
            self.observation(
                authority_token_b=("authority", 2),
                db_identity_token_b=("db", 2),
            )
        )
        self.assertEqual(decision.case_id, "C1")
        self.assertEqual(
            decision.envelope["diagnostic_codes"],
            ["private_objet_metadata_snapshot_changed"],
        )

    def test_c5_c7_c8_top_level_diagnostic_placement_is_exact(self) -> None:
        blockers, stale = session.append_private_objet_metadata_top_level_diagnostics(
            "C5",
            blockers=("already", "archive_index_missing"),
            stale_reasons=("index_health_blocked",),
        )
        self.assertEqual(blockers, ["already", "archive_index_missing"])
        self.assertEqual(stale, ["index_health_blocked"])
        self.assertEqual(
            session.append_private_objet_metadata_top_level_diagnostics("C7"),
            (["private_objet_metadata_projection_invalid"], []),
        )
        self.assertEqual(
            session.append_private_objet_metadata_top_level_diagnostics("C8"),
            ([], ["private_objet_metadata_missing"]),
        )

    def test_count_contract_is_exact_and_boolean_is_not_integer(self) -> None:
        for values in (
            (True, 0, 0, 0, 0, 0),
            (1, 6, 1, 2, 0, 0),
            (2, 0, 2, 4, 0, 0),
            (2, 5, 2, 3, 1, 1),
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    session.PrivateObjetMetadataCounts(*values)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            session.build_private_objet_metadata_health_envelope(
                "C11",
                counts=EMPTY_COUNTS,
            )


class PrivateObjetIndexReadSessionTests(unittest.TestCase):
    def test_uri_is_percent_encoded_absolute_mode_ro_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive space # percent %"
            create_synthetic_archive(root)
            uri = session._private_objet_index_read_uri(
                root / session.PRIVATE_INDEX_RELATIVE_PATH
            )
        self.assertTrue(uri.startswith("file:"))
        self.assertTrue(uri.endswith("?mode=ro"))
        self.assertIn("%20", uri)
        self.assertIn("%23", uri)
        self.assertIn("%25", uri)
        self.assertNotIn("immutable", uri)
        self.assertNotIn("mode=rw", uri)

    def test_lifecycle_uses_restricted_api_and_returns_only_validated_health(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)
            real_open = session._open_private_objet_index_connection
            events: list[tuple[str, str]] = []
            proxies: list[RecordingConnection] = []
            saved_api: list[session.PrivateObjetIndexReadAPI] = []
            captures = iter(
                [
                    SyntheticAuthorityCapture(("authority", 1)),
                    SyntheticAuthorityCapture(("authority", 1)),
                ]
            )

            def open_recording(db_path: Path) -> RecordingConnection:
                events.append(("lifecycle", "open"))
                proxy = RecordingConnection(real_open(db_path), events)
                proxies.append(proxy)
                return proxy

            def capture() -> SyntheticAuthorityCapture:
                events.append(("authority", "capture"))
                return next(captures)

            def inspect_health(
                api: session.PrivateObjetIndexReadAPI,
                authority: object,
            ) -> dict[str, object]:
                events.append(("callback", "health"))
                self.assertIsInstance(authority, SyntheticAuthorityCapture)
                self.assertTrue(api.snapshot_active)
                return current_health()

            def consume(
                api: session.PrivateObjetIndexReadAPI,
                health: object,
            ) -> None:
                events.append(("callback", "consumer"))
                saved_api.append(api)
                self.assertIsInstance(health, MappingProxyType)
                self.assertFalse(hasattr(api, "connection"))
                self.assertFalse(hasattr(api, "execute"))
                self.assertEqual(api.scalar("SELECT value FROM private_probe"), 1)
                return None

            def final_check(
                api: session.PrivateObjetIndexReadAPI,
                authority: object,
            ) -> bool:
                events.append(("callback", "final"))
                self.assertIsInstance(authority, SyntheticAuthorityCapture)
                return api.scalar("SELECT COUNT(*) FROM private_probe") == 1

            with mock.patch.object(
                session,
                "_open_private_objet_index_connection",
                side_effect=open_recording,
            ):
                result = session._with_private_objet_index_read_session(
                    root,
                    consume,
                    capture_authority=capture,
                    inspect_health=inspect_health,
                    final_check=final_check,
                )

        self.assertEqual(result, current_health())
        self.assertIsNot(result, current_health())
        self.assertEqual(len(proxies), 1)
        self.assertEqual(proxies[0].rollback_calls, 1)
        self.assertEqual(proxies[0].close_calls, 1)
        self.assertEqual(
            [event for event in events if event[0] == "authority"],
            [("authority", "capture"), ("authority", "capture")],
        )
        execute_events = [value for kind, value in events if kind == "execute"]
        self.assertIn("PRAGMA query_only=ON", execute_events)
        self.assertIn("PRAGMA query_only", execute_events)
        self.assertIn("PRAGMA temp_store=MEMORY", execute_events)
        self.assertIn("PRAGMA temp_store", execute_events)
        self.assertEqual(execute_events.count("BEGIN"), 1)
        self.assertIn(
            "SELECT name FROM sqlite_schema ORDER BY name LIMIT 1",
            execute_events,
        )
        self.assertEqual(
            [event for event in events if event[0] == "authorizer"],
            [("authorizer", "install"), ("authorizer", "clear")],
        )
        self.assertEqual(
            events[-2:],
            [("lifecycle", "rollback"), ("lifecycle", "close")],
        )
        with self.assertRaises(session.PrivateObjetIndexSessionError):
            saved_api[0].scalar("SELECT 1")

    def test_open_failure_has_no_write_or_immutable_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)
            calls: list[tuple[object, dict[str, object]]] = []

            def fail_connect(
                database: object,
                **kwargs: object,
            ) -> sqlite3.Connection:
                calls.append((database, kwargs))
                raise sqlite3.OperationalError("SYNTHETIC_PRIVATE_OPEN_CANARY")

            with mock.patch.object(
                session.sqlite3,
                "connect",
                side_effect=fail_connect,
            ):
                with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
                    run_session(root)
        self.assertEqual(caught.exception.code, "private_objet_metadata_projection_unavailable")
        self.assertEqual(len(calls), 1)
        database, kwargs = calls[0]
        self.assertIsInstance(database, str)
        self.assertTrue(database.endswith("?mode=ro"))  # type: ignore[union-attr]
        self.assertNotIn("immutable", database)  # type: ignore[operator]
        self.assertIs(kwargs["uri"], True)

    def test_arbitrary_borrowed_connection_is_not_an_api_parameter(self) -> None:
        parameters = inspect.signature(
            session._with_private_objet_index_read_session
        ).parameters
        self.assertNotIn("connection", parameters)
        self.assertNotIn("immutable", parameters)

    def test_db_absent_returns_exact_c5_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            (root / "db").mkdir(parents=True)
            consumer = mock.Mock(
                side_effect=AssertionError("C5 has no SQLite consumer")
            )
            inspector = mock.Mock(
                side_effect=AssertionError("C5 has no SQLite inspector")
            )
            final = mock.Mock(
                side_effect=AssertionError("C5 has no SQLite final check")
            )
            with mock.patch.object(
                session,
                "_open_private_objet_index_connection",
                side_effect=AssertionError("DB absent must not open SQLite"),
            ):
                result = run_session(
                    root,
                    consumer=consumer,
                    inspect_health=inspector,
                    final_check=final,
                )
        self.assertEqual(
            result,
            session.build_private_objet_metadata_health_envelope("C5"),
        )
        self.assertEqual(result["diagnostic_codes"], [])
        self.assertEqual(result["projection_validity"], "missing")
        self.assertEqual(result["index_state"], "missing")
        consumer.assert_not_called()
        inspector.assert_not_called()
        final.assert_not_called()

    def test_consumer_non_none_return_is_closed_and_cleanup_runs_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)
            real_open = session._open_private_objet_index_connection
            events: list[tuple[str, str]] = []
            proxy = RecordingConnection(real_open(root / session.PRIVATE_INDEX_RELATIVE_PATH), events)
            with mock.patch.object(
                session,
                "_open_private_objet_index_connection",
                return_value=proxy,
            ):
                with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
                    run_session(
                        root,
                        consumer=lambda _api, _health: {"private": "forbidden"},
                    )
        self.assertEqual(caught.exception.code, "private_objet_metadata_projection_invalid")
        self.assertEqual(proxy.rollback_calls, 1)
        self.assertEqual(proxy.close_calls, 1)

    def test_callback_exception_is_sanitized_and_cleanup_runs_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)
            real_open = session._open_private_objet_index_connection
            events: list[tuple[str, str]] = []
            proxy = RecordingConnection(real_open(root / session.PRIVATE_INDEX_RELATIVE_PATH), events)

            def fail(_api: object, _health: object) -> None:
                raise RuntimeError("SYNTHETIC_PRIVATE_CALLBACK_CANARY")

            with mock.patch.object(
                session,
                "_open_private_objet_index_connection",
                return_value=proxy,
            ):
                with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
                    run_session(root, consumer=fail)
        self.assertEqual(caught.exception.code, "private_objet_metadata_projection_unavailable")
        self.assertNotIn("CANARY", str(caught.exception))
        self.assertEqual(proxy.rollback_calls, 1)
        self.assertEqual(proxy.close_calls, 1)

    def test_rollback_failure_still_closes_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)
            real_open = session._open_private_objet_index_connection
            events: list[tuple[str, str]] = []
            proxy = RecordingConnection(
                real_open(root / session.PRIVATE_INDEX_RELATIVE_PATH),
                events,
                rollback_fails=True,
            )
            with mock.patch.object(
                session,
                "_open_private_objet_index_connection",
                return_value=proxy,
            ):
                with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
                    run_session(root)
        self.assertEqual(caught.exception.code, "private_objet_metadata_projection_unavailable")
        self.assertNotIn("CANARY", str(caught.exception))
        self.assertEqual(proxy.rollback_calls, 1)
        self.assertEqual(proxy.close_calls, 1)

    def test_authority_drift_blocks_with_c1_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)
            with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
                run_session(
                    root,
                    captures=[
                        SyntheticAuthorityCapture(("authority", 1)),
                        SyntheticAuthorityCapture(("authority", 2)),
                    ],
                )
        self.assertEqual(caught.exception.code, "private_objet_metadata_snapshot_changed")

    def test_invalid_projection_still_observes_c1_and_c2_precedence(
        self,
    ) -> None:
        invalid_health = {
            **current_health(),
            "extra": "forbidden",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "authority-drift"
            create_synthetic_archive(root)
            with self.assertRaises(
                session.PrivateObjetIndexSessionError
            ) as authority_caught:
                run_session(
                    root,
                    captures=[
                        SyntheticAuthorityCapture(("authority", 1)),
                        SyntheticAuthorityCapture(("authority", 2)),
                    ],
                    inspect_health=lambda _api, _authority: invalid_health,
                )
            self.assertEqual(
                authority_caught.exception.code,
                "private_objet_metadata_snapshot_changed",
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "identity-drift"
            create_synthetic_archive(root)
            db_path = root / session.PRIVATE_INDEX_RELATIVE_PATH
            first = session._capture_sqlite_identity_token(db_path)
            second = replace(
                first,
                database=replace(
                    first.database,
                    inode=first.database.inode + 1,  # type: ignore[operator]
                ),
            )
            with mock.patch.object(
                session,
                "_capture_sqlite_identity_token",
                side_effect=[first, second],
            ):
                with self.assertRaises(
                    session.PrivateObjetIndexSessionError
                ) as identity_caught:
                    run_session(
                        root,
                        inspect_health=lambda _api, _authority: invalid_health,
                    )
            self.assertEqual(
                identity_caught.exception.code,
                "private_objet_metadata_projection_unavailable",
            )

    def test_unavailable_projection_still_observes_c1_precedence(
        self,
    ) -> None:
        capture_calls = 0

        def unavailable_health(
            _api: session.PrivateObjetIndexReadAPI,
            _authority: object,
        ) -> dict[str, object]:
            raise session.PrivateObjetIndexSessionError(
                "private_objet_metadata_projection_unavailable"
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)

            def capture() -> SyntheticAuthorityCapture:
                nonlocal capture_calls
                capture_calls += 1
                return SyntheticAuthorityCapture(
                    ("authority", capture_calls)
                )

            with self.assertRaises(
                session.PrivateObjetIndexSessionError
            ) as caught:
                session._with_private_objet_index_read_session(
                    root,
                    lambda _api, _health: None,
                    capture_authority=capture,
                    inspect_health=unavailable_health,
                    final_check=lambda _api, _authority: True,
                )

        self.assertEqual(capture_calls, 2)
        self.assertEqual(
            caught.exception.code,
            "private_objet_metadata_snapshot_changed",
        )

    def test_snapshot_b_capture_failure_is_c1_and_cleanup_runs_once(self) -> None:
        class ClosedAuthorityFailure(RuntimeError):
            code = "private_objet_metadata_authority_invalid"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)
            real_open = session._open_private_objet_index_connection
            events: list[tuple[str, str]] = []
            proxy = RecordingConnection(
                real_open(root / session.PRIVATE_INDEX_RELATIVE_PATH),
                events,
            )
            capture_calls = 0

            def capture() -> SyntheticAuthorityCapture:
                nonlocal capture_calls
                capture_calls += 1
                if capture_calls == 1:
                    return SyntheticAuthorityCapture(("authority", 1))
                raise ClosedAuthorityFailure("SYNTHETIC_PRIVATE_AUTHORITY_CANARY")

            with mock.patch.object(
                session,
                "_open_private_objet_index_connection",
                return_value=proxy,
            ):
                with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
                    session._with_private_objet_index_read_session(
                        root,
                        lambda _api, _health: None,
                        capture_authority=capture,
                        inspect_health=lambda _api, _authority: current_health(),
                        final_check=lambda _api, _authority: True,
                    )
        self.assertEqual(caught.exception.code, "private_objet_metadata_snapshot_changed")
        self.assertNotIn("CANARY", str(caught.exception))
        self.assertEqual(proxy.rollback_calls, 1)
        self.assertEqual(proxy.close_calls, 1)

    def test_snapshot_b_capture_failure_is_c1_for_db_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            (root / "db").mkdir(parents=True)
            capture_calls = 0

            def capture() -> SyntheticAuthorityCapture:
                nonlocal capture_calls
                capture_calls += 1
                if capture_calls == 1:
                    return SyntheticAuthorityCapture(("authority", 1))
                raise RuntimeError("SYNTHETIC_PRIVATE_B_CANARY")

            with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
                session._with_private_objet_index_read_session(
                    root,
                    lambda _api, _health: None,
                    capture_authority=capture,
                    inspect_health=lambda _api, _authority: current_health(),
                    final_check=lambda _api, _authority: True,
                )
        self.assertEqual(caught.exception.code, "private_objet_metadata_snapshot_changed")

    def test_db_replacement_and_sidecar_presence_drift_are_blocked(self) -> None:
        for mutation in ("database", "wal"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "archive"
                create_synthetic_archive(root)
                db_path = root / session.PRIVATE_INDEX_RELATIVE_PATH
                first = session._capture_sqlite_identity_token(db_path)
                if mutation == "database":
                    second = replace(
                        first,
                        database=replace(
                            first.database,
                            inode=first.database.inode + 1,  # type: ignore[operator]
                        ),
                    )
                else:
                    second = replace(
                        first,
                        wal=session._PathIdentity(True, 1, 1),
                    )
                with mock.patch.object(
                    session,
                    "_capture_sqlite_identity_token",
                    side_effect=[first, second],
                ):
                    with self.assertRaises(
                        session.PrivateObjetIndexSessionError
                    ) as caught:
                        run_session(root)
                self.assertEqual(
                    caught.exception.code,
                    "private_objet_metadata_projection_unavailable",
                )

    def test_coherent_uncheckpointed_wal_and_same_identity_append_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            writer = create_synthetic_archive(root, wal=True)
            self.assertIsNotNone(writer)
            assert writer is not None
            db_path = root / session.PRIVATE_INDEX_RELATIVE_PATH
            self.assertTrue(db_path.with_name(db_path.name + "-wal").is_file())
            self.assertTrue(db_path.with_name(db_path.name + "-shm").is_file())
            before = session._capture_sqlite_identity_token(db_path)
            counts_seen: list[int] = []

            def consume(
                api: session.PrivateObjetIndexReadAPI,
                _health: object,
            ) -> None:
                counts_seen.append(
                    api.scalar("SELECT COUNT(*) FROM private_probe")  # type: ignore[arg-type]
                )
                writer.execute("INSERT INTO private_probe(value) VALUES (2)")
                writer.commit()
                counts_seen.append(
                    api.scalar("SELECT COUNT(*) FROM private_probe")  # type: ignore[arg-type]
                )
                return None

            try:
                result = run_session(root, consumer=consume)
                after = session._capture_sqlite_identity_token(db_path)
            finally:
                writer.close()
        self.assertEqual(result["index_state"], "current")
        self.assertEqual(counts_seen, [1, 1])
        self.assertEqual(before, after)

    def test_clean_wal_without_sidecars_blocks_before_query_consumption(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            writer = create_synthetic_archive(root, wal=True)
            self.assertIsNotNone(writer)
            assert writer is not None
            writer.close()
            db_path = root / session.PRIVATE_INDEX_RELATIVE_PATH
            wal_path = db_path.with_name(db_path.name + "-wal")
            shm_path = db_path.with_name(db_path.name + "-shm")
            self.assertTrue(
                session._database_header_advertises_wal(db_path)
            )
            self.assertFalse(wal_path.exists())
            self.assertFalse(shm_path.exists())
            consumed: list[str] = []

            with mock.patch.object(
                session,
                "_open_private_objet_index_connection",
                wraps=session._open_private_objet_index_connection,
            ) as opened:
                with self.assertRaises(
                    session.PrivateObjetIndexSessionError
                ) as caught:
                    run_session(
                        root,
                        consumer=lambda _api, _health: consumed.append(
                            "consumer"
                        ),
                        inspect_health=lambda _api, _authority: (
                            consumed.append("health") or current_health()
                        ),
                    )
            self.assertEqual(
                caught.exception.code,
                "private_objet_metadata_projection_unavailable",
            )
            opened.assert_not_called()
            self.assertEqual(consumed, [])
            self.assertFalse(wal_path.exists())
            self.assertFalse(shm_path.exists())

    def test_final_check_failure_and_invalid_health_fail_closed(self) -> None:
        scenarios = (
            {
                "final_check": lambda _api, _authority: False,
                "inspect_health": None,
            },
            {
                "final_check": None,
                "inspect_health": lambda _api, _authority: {
                    **current_health(),
                    "extra": "forbidden",
                },
            },
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "archive"
                create_synthetic_archive(root)
                with self.assertRaises(session.PrivateObjetIndexSessionError) as caught:
                    run_session(root, **scenario)  # type: ignore[arg-type]
                self.assertEqual(
                    caught.exception.code,
                    "private_objet_metadata_projection_invalid",
                )

    def test_restricted_api_rejects_write_statements(self) -> None:
        statements = (
            "PRAGMA query_only=OFF",
            "PRAGMA journal_mode=DELETE",
            "WITH changed AS (SELECT 1) UPDATE private_probe SET value=2",
            "ATTACH DATABASE ':memory:' AS other",
            "CREATE TEMP TABLE stolen(value)",
            "DELETE FROM private_probe",
        )
        for statement in statements:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "archive"
                create_synthetic_archive(root)

                def consumer(
                    api: session.PrivateObjetIndexReadAPI,
                    _health: object,
                ) -> None:
                    api.fetch_all(statement)

                with self.assertRaises(
                    session.PrivateObjetIndexSessionError
                ) as caught:
                    run_session(root, consumer=consumer)
                self.assertEqual(
                    caught.exception.code,
                    "private_objet_metadata_projection_invalid",
                )
                connection = sqlite3.connect(
                    root / session.PRIVATE_INDEX_RELATIVE_PATH
                )
                try:
                    self.assertEqual(
                        connection.execute(
                            "SELECT COUNT(*) FROM private_probe"
                        ).fetchone()[0],
                        1,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT value FROM private_probe"
                        ).fetchone()[0],
                        1,
                    )
                finally:
                    connection.close()

    def test_sqlite_authorizer_denies_all_mutating_action_classes(self) -> None:
        action_names = (
            "SQLITE_INSERT",
            "SQLITE_UPDATE",
            "SQLITE_DELETE",
            "SQLITE_CREATE_TABLE",
            "SQLITE_CREATE_TEMP_TABLE",
            "SQLITE_ATTACH",
            "SQLITE_DETACH",
            "SQLITE_TRANSACTION",
            "SQLITE_PRAGMA",
        )
        for name in action_names:
            with self.subTest(name=name):
                self.assertEqual(
                    session._sqlite_read_authorizer(
                        getattr(sqlite3, name),
                        None,
                        None,
                        None,
                        None,
                    ),
                    sqlite3.SQLITE_DENY,
                )
        self.assertEqual(
            session._sqlite_read_authorizer(
                sqlite3.SQLITE_SELECT,
                None,
                None,
                None,
                None,
            ),
            sqlite3.SQLITE_OK,
        )

    def test_fixed_batch_a_inspector_gets_connection_without_exposing_it(self) -> None:
        from wom_kit import private_objet_metadata_index

        sentinel = object()
        raw_connections: list[sqlite3.Connection] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            create_synthetic_archive(root)

            def inspect_fixed(
                connection: sqlite3.Connection,
                *,
                expected: object | None = None,
            ) -> object:
                self.assertIsNone(expected)
                raw_connections.append(connection)
                return sentinel

            def inspect_health(
                api: session.PrivateObjetIndexReadAPI,
                _authority: object,
            ) -> dict[str, object]:
                self.assertIs(
                    api.inspect_private_objet_index_semantics(),
                    sentinel,
                )
                return current_health()

            with mock.patch.object(
                private_objet_metadata_index,
                "inspect_private_objet_index_semantics",
                side_effect=inspect_fixed,
            ):
                result = run_session(root, inspect_health=inspect_health)
        self.assertEqual(result, current_health())
        self.assertEqual(len(raw_connections), 1)

    def test_module_contains_no_immutable_or_write_fallback_contract(self) -> None:
        source = inspect.getsource(session)
        self.assertNotIn("immutable=1", source)
        self.assertNotIn("mode=rw", source)
        self.assertNotIn("mode=rwc", source)
        self.assertEqual(json.dumps(current_health()).count("sha256:"), 0)


if __name__ == "__main__":
    unittest.main()
