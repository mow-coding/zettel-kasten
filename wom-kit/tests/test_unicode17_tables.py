from __future__ import annotations

import ast
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
from types import MappingProxyType
import unittest

from wom_kit import _unicode17_tables as unicode17

try:
    import unicodedata2
except ImportError:  # pragma: no cover - the assertion reports the missing runtime pin.
    unicodedata2 = None  # type: ignore[assignment]


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = KIT_ROOT / "tests" / "fixtures" / "unicode-17.0.0"
GENERATOR_PATH = KIT_ROOT / "tools" / "generate_unicode17_tables.py"
GENERATED_MODULE_PATH = KIT_ROOT / "src" / "wom_kit" / "_unicode17_tables.py"
GITATTRIBUTES_PATH = KIT_ROOT.parent / ".gitattributes"

SOURCE_EXPECTATIONS = {
    "CaseFolding.txt": {
        "url": "https://www.unicode.org/Public/17.0.0/ucd/CaseFolding.txt",
        "bytes": 87_539,
        "sha256": "ff8d8fefbf123574205085d6714c36149eb946d717a0c585c27f0f4ef58c4183",
    },
    "PropList.txt": {
        "url": "https://www.unicode.org/Public/17.0.0/ucd/PropList.txt",
        "bytes": 145_465,
        "sha256": "130dcddcaadaf071008bdfce1e7743e04fdfbc910886f017d9f9ac931d8c64dd",
    },
    "NormalizationTest.txt": {
        "url": "https://www.unicode.org/Public/17.0.0/ucd/NormalizationTest.txt",
        "bytes": 2_827_429,
        "sha256": "5019ffd530751a741900c849c0e010332f142a3612234639bd200b82138a87db",
    },
}
EXPECTED_CASE_FOLDING_STATUS_COUNTS = {
    "C": 1_481,
    "F": 104,
    "S": 31,
    "T": 2,
}
EXPECTED_WHITE_SPACE = frozenset(
    {
        *range(0x0009, 0x000E),
        0x0020,
        0x0085,
        0x00A0,
        0x1680,
        *range(0x2000, 0x200B),
        0x2028,
        0x2029,
        0x202F,
        0x205F,
        0x3000,
    }
)
EXPECTED_EFFECTIVE_WHITE_SPACE = frozenset(
    {
        0x0020,
        0x00A0,
        0x1680,
        *range(0x2000, 0x200B),
        0x202F,
        0x205F,
        0x3000,
    }
)
EXPECTED_BIDI_CONTROL = frozenset(
    {
        0x061C,
        0x200E,
        0x200F,
        *range(0x202A, 0x202F),
        *range(0x2066, 0x206A),
    }
)
EXPECTED_LICENSE_SHA256 = (
    "abf84f74dea2812799e1dbef7f0581adf7db244881e4febb8684f441568da0ad"
)


def _load_generator_module():
    module_name = "_wom_unicode17_generator_test"
    spec = importlib.util.spec_from_file_location(module_name, GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unicode 17 generator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator_module()


def _data_fields(line: str) -> list[str]:
    payload = line.split("#", 1)[0].strip()
    if not payload:
        return []
    fields = [field.strip() for field in payload.split(";")]
    while fields and fields[-1] == "":
        fields.pop()
    return fields


def _parse_code_point_range(value: str) -> range:
    if ".." in value:
        first_text, last_text = value.split("..", 1)
    else:
        first_text = last_text = value
    return range(int(first_text, 16), int(last_text, 16) + 1)


def _parse_case_folding_fixture() -> tuple[dict[int, tuple[int, ...]], dict[str, int]]:
    mappings: dict[int, tuple[int, ...]] = {}
    counts = {status: 0 for status in ("C", "F", "S", "T")}
    source = (FIXTURES_ROOT / "CaseFolding.txt").read_text(encoding="utf-8")
    for line in source.splitlines():
        fields = _data_fields(line)
        if not fields:
            continue
        source_text, status, mapping_text = fields
        counts[status] += 1
        if status in {"C", "F"}:
            mappings[int(source_text, 16)] = tuple(
                int(token, 16) for token in mapping_text.split()
            )
    return mappings, counts


def _parse_property_fixture(property_name: str) -> frozenset[int]:
    code_points: set[int] = set()
    source = (FIXTURES_ROOT / "PropList.txt").read_text(encoding="utf-8")
    for line in source.splitlines():
        fields = _data_fields(line)
        if not fields:
            continue
        range_text, row_property = fields
        if row_property == property_name:
            code_points.update(_parse_code_point_range(range_text))
    return frozenset(code_points)


def _decode_code_point_sequence(value: str) -> str:
    return "".join(chr(int(token, 16)) for token in value.split())


def _full_case_fold_cf(value: str) -> str:
    code_points: list[int] = []
    for character in value:
        source = ord(character)
        code_points.extend(unicode17.CASE_FOLDING_CF.get(source, (source,)))
    return "".join(chr(code_point) for code_point in code_points)


def _q(value: str) -> str:
    if unicodedata2 is None:
        raise RuntimeError("unicodedata2==17.0.1 is required")
    return unicodedata2.normalize(
        "NFC",
        _full_case_fold_cf(unicodedata2.normalize("NFD", value)),
    )


class Unicode17TableTests(unittest.TestCase):
    def require_unicode17_engine(self):
        self.assertIsNotNone(
            unicodedata2,
            "focused Unicode tests require runtime dependency unicodedata2==17.0.1",
        )
        if unicodedata2 is None:
            raise AssertionError("unreachable")
        self.assertEqual(unicodedata2.unidata_version, "17.0.0")
        return unicodedata2

    def test_official_source_bytes_are_exact_and_lf_only(self) -> None:
        for filename, expected in SOURCE_EXPECTATIONS.items():
            data = (FIXTURES_ROOT / filename).read_bytes()
            self.assertEqual(
                len(data),
                expected["bytes"],
                f"official Unicode source byte count changed: {filename}",
            )
            self.assertEqual(
                hashlib.sha256(data).hexdigest(),
                expected["sha256"],
                f"official Unicode source digest changed: {filename}",
            )
            self.assertNotIn(
                b"\r",
                data,
                f"official Unicode source is not LF-only: {filename}",
            )
            self.assertTrue(data.endswith(b"\n"))
            data.decode("utf-8", errors="strict")

        attributes = GITATTRIBUTES_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "wom-kit/tests/fixtures/unicode-17.0.0/*.txt text eol=lf\n",
            attributes,
        )

    def test_generated_module_matches_verified_sources_byte_for_byte(self) -> None:
        expected = GENERATOR.generated_module_bytes(FIXTURES_ROOT)
        actual = GENERATED_MODULE_PATH.read_bytes()
        self.assertTrue(
            actual == expected,
            "committed Unicode 17 module differs from deterministic generator output",
        )
        self.assertNotIn(b"\r", actual)
        self.assertTrue(actual.endswith(b"\n"))
        actual.decode("utf-8", errors="strict")

    def test_generator_rejects_mismatch_before_output_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            for filename in SOURCE_EXPECTATIONS:
                shutil.copyfile(
                    FIXTURES_ROOT / filename,
                    fixtures / filename,
                )
            corrupted_path = fixtures / "CaseFolding.txt"
            corrupted = bytearray(corrupted_path.read_bytes())
            corrupted[100] ^= 0x01
            corrupted_path.write_bytes(corrupted)

            output = root / "generated.py"
            sentinel = b"must remain unchanged\n"
            output.write_bytes(sentinel)
            with self.assertRaises(GENERATOR.SourceValidationError):
                GENERATOR.write_generated_module(fixtures, output)
            self.assertEqual(output.read_bytes(), sentinel)

    def test_runtime_contract_is_immutable_and_pinned(self) -> None:
        self.assertEqual(unicode17.UNICODE_VERSION, "17.0.0")
        self.assertIs(type(unicode17.CASE_FOLDING_CF), MappingProxyType)
        self.assertIs(type(unicode17.UCD_SOURCE_METADATA), MappingProxyType)
        self.assertIs(type(unicode17.CASE_FOLDING_STATUS_COUNTS), MappingProxyType)
        self.assertIsInstance(unicode17.WHITE_SPACE_CODE_POINTS, frozenset)
        self.assertIsInstance(
            unicode17.EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS,
            frozenset,
        )
        self.assertIsInstance(unicode17.BIDI_CONTROL_CODE_POINTS, frozenset)
        with self.assertRaises(TypeError):
            unicode17.CASE_FOLDING_CF[0x0041] = (0x0041,)  # type: ignore[index]
        with self.assertRaises(TypeError):
            unicode17.UCD_SOURCE_METADATA["CaseFolding.txt"]["bytes"] = 0  # type: ignore[index]
        with self.assertRaises(AttributeError):
            unicode17.WHITE_SPACE_CODE_POINTS.add(0x0041)  # type: ignore[attr-defined]

        self.assertEqual(
            dict(unicode17.UCD_SOURCE_METADATA),
            SOURCE_EXPECTATIONS,
        )
        self.assertEqual(
            dict(unicode17.CASE_FOLDING_STATUS_COUNTS),
            EXPECTED_CASE_FOLDING_STATUS_COUNTS,
        )

    def test_case_folding_table_matches_all_official_c_and_f_rows(self) -> None:
        official_mappings, status_counts = _parse_case_folding_fixture()
        self.assertEqual(status_counts, EXPECTED_CASE_FOLDING_STATUS_COUNTS)
        self.assertEqual(len(official_mappings), 1_585)
        self.assertEqual(dict(unicode17.CASE_FOLDING_CF), official_mappings)
        self.assertEqual(unicode17.CASE_FOLDING_CF.get(0x0041), (0x0061,))
        self.assertEqual(
            unicode17.CASE_FOLDING_CF.get(0x00DF),
            (0x0073, 0x0073),
        )

        for code_point in range(0x110000):
            if 0xD800 <= code_point <= 0xDFFF:
                continue
            expected = official_mappings.get(code_point, (code_point,))
            actual = unicode17.CASE_FOLDING_CF.get(code_point, (code_point,))
            if actual != expected:
                self.fail(
                    "Unicode C/F lookup mismatch at scalar "
                    f"U+{code_point:06X}"
                )

    def test_property_sets_match_official_prop_list(self) -> None:
        white_space = _parse_property_fixture("White_Space")
        bidi_control = _parse_property_fixture("Bidi_Control")
        self.assertEqual(white_space, EXPECTED_WHITE_SPACE)
        self.assertEqual(bidi_control, EXPECTED_BIDI_CONTROL)
        self.assertEqual(unicode17.WHITE_SPACE_CODE_POINTS, white_space)
        self.assertEqual(unicode17.BIDI_CONTROL_CODE_POINTS, bidi_control)
        self.assertEqual(
            unicode17.EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS,
            EXPECTED_EFFECTIVE_WHITE_SPACE,
        )
        self.assertEqual(len(white_space), 25)
        self.assertEqual(len(EXPECTED_EFFECTIVE_WHITE_SPACE), 17)
        self.assertEqual(len(bidi_control), 12)

    def test_normalization_test_has_full_unicode17_conformance(self) -> None:
        engine = self.require_unicode17_engine()
        row_count = 0
        source = (FIXTURES_ROOT / "NormalizationTest.txt").read_text(
            encoding="utf-8"
        )
        for line in source.splitlines():
            payload = line.split("#", 1)[0].strip()
            if not payload or payload.startswith("@"):
                continue
            fields = [field.strip() for field in payload.split(";")]
            c1, c2, c3, c4, c5 = (
                _decode_code_point_sequence(field) for field in fields[:5]
            )
            row_count += 1
            checks = (
                ("NFC", c1, c2),
                ("NFC", c2, c2),
                ("NFC", c3, c2),
                ("NFC", c4, c4),
                ("NFC", c5, c4),
                ("NFD", c1, c3),
                ("NFD", c2, c3),
                ("NFD", c3, c3),
                ("NFD", c4, c5),
                ("NFD", c5, c5),
                ("NFKC", c1, c4),
                ("NFKC", c2, c4),
                ("NFKC", c3, c4),
                ("NFKC", c4, c4),
                ("NFKC", c5, c4),
                ("NFKD", c1, c5),
                ("NFKD", c2, c5),
                ("NFKD", c3, c5),
                ("NFKD", c4, c5),
                ("NFKD", c5, c5),
            )
            for check_index, (form, value, expected) in enumerate(checks):
                if engine.normalize(form, value) != expected:
                    self.fail(
                        "Unicode normalization conformance mismatch at "
                        f"row {row_count}, check {check_index}"
                    )
            q_values = {_q(value) for value in (c1, c2, c3)}
            if len(q_values) != 1:
                self.fail(
                    "canonical-equivalent Q values differ at "
                    f"normalization row {row_count}"
                )
        self.assertGreater(row_count, 19_000)

    def test_full_fold_expansion_bound_and_q_idempotence(self) -> None:
        engine = self.require_unicode17_engine()
        maximum = 0
        maximum_scalars: set[int] = set()
        for code_point in range(0x110000):
            if 0xD800 <= code_point <= 0xDFFF:
                continue
            value = chr(code_point)
            nfd_folded = engine.normalize(
                "NFD",
                _full_case_fold_cf(engine.normalize("NFD", value)),
            )
            length = len(nfd_folded)
            if length > maximum:
                maximum = length
                maximum_scalars = {code_point}
            elif length == maximum:
                maximum_scalars.add(code_point)
            q_value = engine.normalize("NFC", nfd_folded)
            if _q(q_value) != q_value:
                self.fail(
                    "canonical caseless Q is not idempotent at scalar "
                    f"U+{code_point:06X}"
                )

        self.assertEqual(maximum, 4)
        self.assertIn(0x1F82, maximum_scalars)
        canary = chr(0x1F82)
        self.assertEqual(
            len(
                engine.normalize(
                    "NFD",
                    _full_case_fold_cf(engine.normalize("NFD", canary)),
                )
            ),
            4,
        )
        self.assertEqual(maximum * 512, 2_048)

    def test_full_unicode_license_v3_notice_is_preserved(self) -> None:
        license_bytes = unicode17.UNICODE_LICENSE_V3.encode("utf-8")
        self.assertEqual(len(license_bytes), 1_995)
        self.assertEqual(
            hashlib.sha256(license_bytes).hexdigest(),
            EXPECTED_LICENSE_SHA256,
        )
        self.assertTrue(
            unicode17.UNICODE_LICENSE_V3.startswith("UNICODE LICENSE V3\n")
        )
        self.assertTrue(
            unicode17.UNICODE_LICENSE_V3.endswith(
                "authorization of the copyright holder.\n"
            )
        )
        self.assertEqual(
            unicode17.UNICODE_LICENSE_V3_SOURCE_URL,
            "https://www.unicode.org/license.txt",
        )

    def test_runtime_table_module_contains_no_file_or_network_logic(self) -> None:
        source = GENERATED_MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(GENERATED_MODULE_PATH))
        imported_modules: set[str] = set()
        called_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    imported_modules.add(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_names.add(node.func.id)
                else:
                    self.fail("generated Unicode module has an indirect call")
        self.assertEqual(imported_modules, {"__future__", "types", "typing"})
        self.assertEqual(called_names, {"MappingProxyType", "frozenset"})


if __name__ == "__main__":
    unittest.main()
