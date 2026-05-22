"""Small JSON Schema subset validator for archive doctor.

The checked schemas use standard JSON Schema 2020-12 keywords, but the runtime
intentionally supports only the small subset needed for local archive health
checks: type, required, properties, items, and enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any


SCHEMAS_ROOT = Path(__file__).resolve().parents[2] / "schemas"


@dataclass
class SchemaIssue:
    code: str
    message: str
    data_path: str


def load_schema(schema_name: str) -> dict[str, Any]:
    path = SCHEMAS_ROOT / schema_name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(data: Any, schema_name: str) -> list[SchemaIssue]:
    schema = load_schema(schema_name)
    return validate_value(data, schema, "$")


def validate_value(data: Any, schema: dict[str, Any], data_path: str) -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []

    expected_type = schema.get("type")
    if expected_type is not None and not matches_type(data, expected_type):
        issues.append(
            SchemaIssue(
                "schema_type",
                f"{data_path} should be {format_expected_type(expected_type)}, got {type_name(data)}.",
                data_path,
            )
        )
        return issues

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and data not in enum_values:
        issues.append(
            SchemaIssue(
                "schema_enum",
                f"{data_path} should be one of: {', '.join(map(str, enum_values))}.",
                data_path,
            )
        )

    if isinstance(data, dict):
        required = schema.get("required") or []
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in data:
                    issues.append(
                        SchemaIssue(
                            "schema_required",
                            f"{data_path}.{key} is required.",
                            f"{data_path}.{key}",
                        )
                    )

        properties = schema.get("properties") or {}
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in data and isinstance(child_schema, dict):
                    issues.extend(validate_value(data[key], child_schema, f"{data_path}.{key}"))

    if isinstance(data, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                issues.extend(validate_value(item, item_schema, f"{data_path}[{index}]"))

    return issues


def matches_type(data: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(matches_type(data, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(data, dict)
    if expected_type == "array":
        return isinstance(data, list)
    if expected_type == "string":
        return isinstance(data, str) or isinstance(data, (date, datetime))
    if expected_type == "integer":
        return isinstance(data, int) and not isinstance(data, bool)
    if expected_type == "number":
        return (isinstance(data, int) or isinstance(data, float)) and not isinstance(data, bool)
    if expected_type == "boolean":
        return isinstance(data, bool)
    if expected_type == "null":
        return data is None
    return True


def format_expected_type(expected_type: Any) -> str:
    if isinstance(expected_type, list):
        return " or ".join(map(str, expected_type))
    return str(expected_type)


def type_name(data: Any) -> str:
    if isinstance(data, dict):
        return "object"
    if isinstance(data, list):
        return "array"
    if isinstance(data, str):
        return "string"
    if isinstance(data, bool):
        return "boolean"
    if isinstance(data, int):
        return "integer"
    if isinstance(data, float):
        return "number"
    if data is None:
        return "null"
    if isinstance(data, (date, datetime)):
        return "string"
    return type(data).__name__
