#!/usr/bin/env python3
"""Generate WOM-kit's pinned, runtime-only Unicode 17 lookup tables."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys
from typing import Iterable, Mapping


KIT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES_ROOT = KIT_ROOT / "tests" / "fixtures" / "unicode-17.0.0"
DEFAULT_OUTPUT_PATH = KIT_ROOT / "src" / "wom_kit" / "_unicode17_tables.py"
UNICODE_VERSION = "17.0.0"


@dataclass(frozen=True)
class SourceSpec:
    filename: str
    url: str
    byte_count: int
    sha256: str


SOURCE_SPECS = (
    SourceSpec(
        filename="CaseFolding.txt",
        url="https://www.unicode.org/Public/17.0.0/ucd/CaseFolding.txt",
        byte_count=87_539,
        sha256="ff8d8fefbf123574205085d6714c36149eb946d717a0c585c27f0f4ef58c4183",
    ),
    SourceSpec(
        filename="PropList.txt",
        url="https://www.unicode.org/Public/17.0.0/ucd/PropList.txt",
        byte_count=145_465,
        sha256="130dcddcaadaf071008bdfce1e7743e04fdfbc910886f017d9f9ac931d8c64dd",
    ),
    SourceSpec(
        filename="NormalizationTest.txt",
        url="https://www.unicode.org/Public/17.0.0/ucd/NormalizationTest.txt",
        byte_count=2_827_429,
        sha256="5019ffd530751a741900c849c0e010332f142a3612234639bd200b82138a87db",
    ),
)

EXPECTED_CASE_FOLDING_STATUS_COUNTS = {
    "C": 1_481,
    "F": 104,
    "S": 31,
    "T": 2,
}
EXPECTED_CASE_FOLDING_CF_COUNT = 1_585
EXPECTED_WHITE_SPACE_CODE_POINTS = frozenset(
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
BLOCKED_SEPARATOR_WHITESPACE_CODE_POINTS = frozenset(
    {
        *range(0x0009, 0x000E),
        0x0085,
        0x2028,
        0x2029,
    }
)
EXPECTED_EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS = (
    EXPECTED_WHITE_SPACE_CODE_POINTS - BLOCKED_SEPARATOR_WHITESPACE_CODE_POINTS
)
EXPECTED_BIDI_CONTROL_CODE_POINTS = frozenset(
    {
        0x061C,
        0x200E,
        0x200F,
        *range(0x202A, 0x202F),
        *range(0x2066, 0x206A),
    }
)

UNICODE_LICENSE_V3_SOURCE_URL = "https://www.unicode.org/license.txt"
UNICODE_LICENSE_V3 = """UNICODE LICENSE V3

COPYRIGHT AND PERMISSION NOTICE

Copyright © 1991-2025 Unicode, Inc.

NOTICE TO USER: Carefully read the following legal agreement. BY
DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR
SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE
TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT
DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of data files and any associated documentation (the "Data Files") or
software and any associated documentation (the "Software") to deal in the
Data Files or Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, and/or sell
copies of the Data Files or Software, and to permit persons to whom the
Data Files or Software are furnished to do so, provided that either (a)
this copyright and permission notice appear with all copies of the Data
Files or Software, or (b) this copyright and permission notice appear in
associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF
THIRD PARTY RIGHTS.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE
BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA
FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in these Data Files or Software without prior written
authorization of the copyright holder.
"""


class SourceValidationError(ValueError):
    """Raised before any generated output is written."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_verified_sources(fixtures_root: Path) -> dict[str, bytes]:
    """Read and verify every official source before parsing or writing anything."""

    loaded: dict[str, bytes] = {}
    for spec in SOURCE_SPECS:
        source_path = fixtures_root / spec.filename
        try:
            data = source_path.read_bytes()
        except OSError as exc:
            raise SourceValidationError(
                f"official Unicode source unreadable: {spec.filename}"
            ) from exc
        if len(data) != spec.byte_count:
            raise SourceValidationError(
                f"official Unicode source byte count mismatch: {spec.filename}"
            )
        if sha256_bytes(data) != spec.sha256:
            raise SourceValidationError(
                f"official Unicode source digest mismatch: {spec.filename}"
            )
        if b"\r" in data:
            raise SourceValidationError(
                f"official Unicode source is not LF-only: {spec.filename}"
            )
        try:
            data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SourceValidationError(
                f"official Unicode source is not strict UTF-8: {spec.filename}"
            ) from exc
        loaded[spec.filename] = data
    return loaded


def _data_fields(line: str, *, filename: str, line_number: int) -> list[str]:
    payload = line.split("#", 1)[0].strip()
    if not payload:
        return []
    fields = [field.strip() for field in payload.split(";")]
    while fields and fields[-1] == "":
        fields.pop()
    if not fields or any(field == "" for field in fields):
        raise SourceValidationError(
            f"malformed Unicode data row: {filename}:{line_number}"
        )
    return fields


def _parse_scalar(value: str, *, filename: str, line_number: int) -> int:
    try:
        code_point = int(value, 16)
    except ValueError as exc:
        raise SourceValidationError(
            f"invalid Unicode scalar token: {filename}:{line_number}"
        ) from exc
    if not 0 <= code_point <= 0x10FFFF or 0xD800 <= code_point <= 0xDFFF:
        raise SourceValidationError(
            f"non-scalar Unicode code point: {filename}:{line_number}"
        )
    return code_point


def parse_case_folding(
    data: bytes,
) -> tuple[dict[int, tuple[int, ...]], dict[str, int]]:
    filename = "CaseFolding.txt"
    mappings: dict[int, tuple[int, ...]] = {}
    status_counts = {status: 0 for status in ("C", "F", "S", "T")}
    text = data.decode("utf-8", errors="strict")
    for line_number, line in enumerate(text.splitlines(), start=1):
        fields = _data_fields(line, filename=filename, line_number=line_number)
        if not fields:
            continue
        if len(fields) != 3:
            raise SourceValidationError(
                f"malformed case-folding row: {filename}:{line_number}"
            )
        source_text, status, mapping_text = fields
        if status not in status_counts:
            raise SourceValidationError(
                f"unknown case-folding status: {filename}:{line_number}"
            )
        source = _parse_scalar(
            source_text,
            filename=filename,
            line_number=line_number,
        )
        mapping = tuple(
            _parse_scalar(token, filename=filename, line_number=line_number)
            for token in mapping_text.split()
        )
        if not mapping:
            raise SourceValidationError(
                f"empty case-folding mapping: {filename}:{line_number}"
            )
        status_counts[status] += 1
        if status in {"C", "F"}:
            if source in mappings:
                raise SourceValidationError(
                    f"duplicate C/F case-folding source: {filename}:{line_number}"
                )
            mappings[source] = mapping

    if status_counts != EXPECTED_CASE_FOLDING_STATUS_COUNTS:
        raise SourceValidationError("CaseFolding.txt status counts do not match UCD 17")
    if len(mappings) != EXPECTED_CASE_FOLDING_CF_COUNT:
        raise SourceValidationError("CaseFolding.txt C/F mapping count is not 1,585")
    return mappings, status_counts


def _parse_code_point_range(
    value: str,
    *,
    filename: str,
    line_number: int,
) -> range:
    if ".." in value:
        first_text, last_text = value.split("..", 1)
    else:
        first_text = last_text = value
    first = _parse_scalar(first_text, filename=filename, line_number=line_number)
    last = _parse_scalar(last_text, filename=filename, line_number=line_number)
    if first > last:
        raise SourceValidationError(
            f"reversed Unicode range: {filename}:{line_number}"
        )
    return range(first, last + 1)


def parse_prop_list(data: bytes) -> tuple[frozenset[int], frozenset[int]]:
    filename = "PropList.txt"
    properties: dict[str, set[int]] = {
        "White_Space": set(),
        "Bidi_Control": set(),
    }
    text = data.decode("utf-8", errors="strict")
    for line_number, line in enumerate(text.splitlines(), start=1):
        fields = _data_fields(line, filename=filename, line_number=line_number)
        if not fields:
            continue
        if len(fields) != 2:
            raise SourceValidationError(
                f"malformed property row: {filename}:{line_number}"
            )
        range_text, property_name = fields
        if property_name not in properties:
            continue
        code_points = _parse_code_point_range(
            range_text,
            filename=filename,
            line_number=line_number,
        )
        destination = properties[property_name]
        for code_point in code_points:
            if code_point in destination:
                raise SourceValidationError(
                    f"duplicate property scalar: {filename}:{line_number}"
                )
            destination.add(code_point)

    white_space = frozenset(properties["White_Space"])
    bidi_control = frozenset(properties["Bidi_Control"])
    if white_space != EXPECTED_WHITE_SPACE_CODE_POINTS:
        raise SourceValidationError("PropList.txt White_Space set does not match UCD 17")
    if bidi_control != EXPECTED_BIDI_CONTROL_CODE_POINTS:
        raise SourceValidationError("PropList.txt Bidi_Control set does not match UCD 17")
    return white_space, bidi_control


def _format_code_point(code_point: int) -> str:
    return f"0x{code_point:04X}"


def _format_mapping(mapping: tuple[int, ...]) -> str:
    values = ", ".join(_format_code_point(code_point) for code_point in mapping)
    if len(mapping) == 1:
        values += ","
    return f"({values})"


def _append_frozenset(
    lines: list[str],
    *,
    name: str,
    code_points: Iterable[int],
) -> None:
    lines.append(f"{name}: Final[frozenset[int]] = frozenset(")
    lines.append("    {")
    for code_point in sorted(code_points):
        lines.append(f"        {_format_code_point(code_point)},")
    lines.append("    }")
    lines.append(")")
    lines.append("")


def render_module(
    *,
    case_folding_cf: Mapping[int, tuple[int, ...]],
    status_counts: Mapping[str, int],
    white_space: frozenset[int],
    bidi_control: frozenset[int],
) -> bytes:
    effective_white_space = (
        white_space - BLOCKED_SEPARATOR_WHITESPACE_CODE_POINTS
    )
    if (
        effective_white_space
        != EXPECTED_EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS
    ):
        raise SourceValidationError(
            "effective separator White_Space set does not match WOM v0.1"
        )

    lines = [
        '"""Pinned Unicode 17 tables generated from verified official UCD sources."""',
        "",
        "from __future__ import annotations",
        "",
        "from types import MappingProxyType",
        "from typing import Final, Mapping",
        "",
        "",
        f'UNICODE_VERSION: Final[str] = "{UNICODE_VERSION}"',
        f'UNICODE_LICENSE_V3_SOURCE_URL: Final[str] = "{UNICODE_LICENSE_V3_SOURCE_URL}"',
        'UNICODE_LICENSE_V3: Final[str] = """\\',
        *UNICODE_LICENSE_V3.splitlines(),
        '"""',
        "",
        (
            "UCD_SOURCE_METADATA: "
            "Final[Mapping[str, Mapping[str, str | int]]] = MappingProxyType("
        ),
        "    {",
    ]
    for spec in SOURCE_SPECS:
        lines.extend(
            [
                f'        "{spec.filename}": MappingProxyType(',
                "            {",
                f'                "url": "{spec.url}",',
                f'                "bytes": {spec.byte_count},',
                f'                "sha256": "{spec.sha256}",',
                "            }",
                "        ),",
            ]
        )
    lines.extend(
        [
            "    }",
            ")",
            "",
            (
                "CASE_FOLDING_STATUS_COUNTS: "
                "Final[Mapping[str, int]] = MappingProxyType("
            ),
            "    {",
        ]
    )
    for status in ("C", "F", "S", "T"):
        lines.append(f'        "{status}": {status_counts[status]},')
    lines.extend(
        [
            "    }",
            ")",
            "",
            (
                "CASE_FOLDING_CF: "
                "Final[Mapping[int, tuple[int, ...]]] = MappingProxyType("
            ),
            "    {",
        ]
    )
    for source in sorted(case_folding_cf):
        lines.append(
            f"        {_format_code_point(source)}: "
            f"{_format_mapping(case_folding_cf[source])},"
        )
    lines.extend(["    }", ")", ""])
    _append_frozenset(
        lines,
        name="WHITE_SPACE_CODE_POINTS",
        code_points=white_space,
    )
    _append_frozenset(
        lines,
        name="EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS",
        code_points=effective_white_space,
    )
    _append_frozenset(
        lines,
        name="BIDI_CONTROL_CODE_POINTS",
        code_points=bidi_control,
    )
    lines.extend(
        [
            "__all__ = (",
            '    "BIDI_CONTROL_CODE_POINTS",',
            '    "CASE_FOLDING_CF",',
            '    "CASE_FOLDING_STATUS_COUNTS",',
            '    "EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS",',
            '    "UCD_SOURCE_METADATA",',
            '    "UNICODE_LICENSE_V3",',
            '    "UNICODE_LICENSE_V3_SOURCE_URL",',
            '    "UNICODE_VERSION",',
            '    "WHITE_SPACE_CODE_POINTS",',
            ")",
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8", errors="strict")


def generated_module_bytes(fixtures_root: Path = DEFAULT_FIXTURES_ROOT) -> bytes:
    sources = load_verified_sources(fixtures_root)
    case_folding_cf, status_counts = parse_case_folding(
        sources["CaseFolding.txt"]
    )
    white_space, bidi_control = parse_prop_list(sources["PropList.txt"])
    return render_module(
        case_folding_cf=case_folding_cf,
        status_counts=status_counts,
        white_space=white_space,
        bidi_control=bidi_control,
    )


def write_generated_module(
    fixtures_root: Path = DEFAULT_FIXTURES_ROOT,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> bytes:
    """Validate all sources, then write the one deterministic output."""

    rendered = generated_module_bytes(fixtures_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rendered)
    return rendered


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed module without writing it.",
    )
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=DEFAULT_FIXTURES_ROOT,
        help="Directory containing the three exact official Unicode sources.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Generated Python module path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        expected = generated_module_bytes(args.fixtures_root)
    except SourceValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        try:
            actual = args.output.read_bytes()
        except OSError:
            print("ERROR: generated Unicode 17 module is unreadable", file=sys.stderr)
            return 1
        if actual != expected:
            print("ERROR: generated Unicode 17 module is stale", file=sys.stderr)
            return 1
        print("Unicode 17 generated module is current.")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(expected)
    print(
        "Generated Unicode 17 tables: "
        f"{EXPECTED_CASE_FOLDING_CF_COUNT} C/F mappings, "
        f"{len(EXPECTED_WHITE_SPACE_CODE_POINTS)} White_Space, "
        f"{len(EXPECTED_EFFECTIVE_SEPARATOR_WHITESPACE_CODE_POINTS)} effective, "
        f"{len(EXPECTED_BIDI_CONTROL_CODE_POINTS)} Bidi_Control."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
