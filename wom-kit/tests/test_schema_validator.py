from __future__ import annotations

import unittest

from wom_kit.schema_validator import validate_value


class SchemaValidatorTests(unittest.TestCase):
    def test_additional_properties_false_rejects_top_and_nested_extras(self) -> None:
        schema = {
            "type": "object",
            "required": ["nested"],
            "properties": {
                "nested": {
                    "type": "object",
                    "required": ["allowed"],
                    "properties": {"allowed": {"type": "boolean"}},
                    "additionalProperties": False,
                }
            },
            "additionalProperties": False,
        }
        top_issues = validate_value(
            {"nested": {"allowed": True}, "extra": True},
            schema,
            "$",
        )
        nested_issues = validate_value(
            {"nested": {"allowed": True, "extra": True}},
            schema,
            "$",
        )

        self.assertEqual(
            [(item.code, item.data_path) for item in top_issues],
            [("schema_additional_property", "$.extra")],
        )
        self.assertEqual(
            [(item.code, item.data_path) for item in nested_issues],
            [("schema_additional_property", "$.nested.extra")],
        )

    def test_additional_property_schema_is_applied_to_each_unknown_value(self) -> None:
        schema = {
            "type": "object",
            "properties": {"known": {"type": "string"}},
            "additionalProperties": {"type": "integer"},
        }

        self.assertEqual(
            validate_value({"known": "ok", "count": 2}, schema, "$"),
            [],
        )
        issues = validate_value(
            {"known": "ok", "count": "two"},
            schema,
            "$",
        )
        self.assertEqual(
            [(item.code, item.data_path) for item in issues],
            [("schema_type", "$.count")],
        )

    def test_malformed_additional_properties_declaration_fails_closed(self) -> None:
        issues = validate_value(
            {"known": True},
            {
                "type": "object",
                "properties": {"known": {"type": "boolean"}},
                "additionalProperties": "false",
            },
            "$",
        )

        self.assertEqual(
            [(item.code, item.data_path) for item in issues],
            [("schema_unsupported", "$")],
        )

    def test_existing_open_object_contract_and_core_keywords_still_validate(self) -> None:
        schema = {
            "type": "object",
            "required": ["status", "items"],
            "properties": {
                "status": {"type": "string", "const": "ready"},
                "items": {
                    "type": "array",
                    "items": {"type": "integer"},
                },
            },
        }

        self.assertEqual(
            validate_value(
                {"status": "ready", "items": [1, 2], "legacy_extra": True},
                schema,
                "$",
            ),
            [],
        )
        self.assertTrue(
            validate_value(
                {"status": "wrong", "items": [1, "two"]},
                schema,
                "$",
            )
        )


if __name__ == "__main__":
    unittest.main()
