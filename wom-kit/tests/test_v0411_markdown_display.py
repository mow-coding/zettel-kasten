from __future__ import annotations

import hashlib
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from wom_kit import archive_cli, archive_services
from wom_kit.markdown_display import (
    WOM_SAFE_MARKDOWN_DISPLAY_SCHEMA,
    _backslash_escape_mask,
    _protect_angle_syntax,
    _protect_inline_links,
    project_wom_safe_markdown,
)


class WomSafeMarkdownDisplayTests(unittest.TestCase):
    def test_korean_range_tildes_are_safe_in_all_spacing_forms(self) -> None:
        source = "3~5, 서울~부산, v0.4.3~v0.4.7, 8 ~ 10, A~B와 C~D\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "3\\~5, 서울\\~부산, v0.4.3\\~v0.4.7, 8 \\~ 10, A\\~B와 C\\~D\n",
        )
        self.assertEqual(result["metadata"]["counts"]["single_tilde_count"], 6)

    def test_intentional_balanced_markup_is_preserved(self) -> None:
        source = "~~의도한 삭선~~과 **의도한 굵게**는 유지한다.\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(result["text"], source)
        counts = result["metadata"]["counts"]
        self.assertEqual(counts["intentional_strikethrough_pair_count"], 1)
        self.assertEqual(counts["intentional_strong_pair_count"], 1)
        self.assertEqual(counts["inserted_backslash_count"], 0)

    def test_unpaired_double_tilde_and_strong_runs_are_escaped(self) -> None:
        source = "~~완료되지 않은 삭선과 **완료되지 않은 굵게\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "\\~\\~완료되지 않은 삭선과 \\*\\*완료되지 않은 굵게\n",
        )
        counts = result["metadata"]["counts"]
        self.assertEqual(counts["unpaired_double_tilde_run_count"], 1)
        self.assertEqual(counts["unpaired_strong_run_count"], 1)
        self.assertEqual(counts["inserted_backslash_count"], 4)

    def test_only_unpaired_runs_are_escaped_when_markup_is_mixed(self) -> None:
        source = "~~good~~ then ~~open; **bold** then **open\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "~~good~~ then \\~\\~open; **bold** then \\*\\*open\n",
        )

    def test_delimiters_do_not_pair_across_a_blank_line(self) -> None:
        source = "~~first paragraph\n\nsecond paragraph~~\n**third\n\nfourth**\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "\\~\\~first paragraph\n\nsecond paragraph\\~\\~\n"
            "\\*\\*third\n\nfourth\\*\\*\n",
        )

    def test_delimiters_do_not_pair_across_distinct_block_kinds(self) -> None:
        cases = {
            "**open\n# heading**\n": "\\*\\*open\n# heading\\*\\*\n",
            "**open\n> quote**\n": "\\*\\*open\n> quote\\*\\*\n",
            "**open\n- item**\n": "\\*\\*open\n- item\\*\\*\n",
            "~~open\n# heading~~\n": "\\~\\~open\n# heading\\~\\~\n",
            "**open\n***\nclose**\n": "\\*\\*open\n***\nclose\\*\\*\n",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(project_wom_safe_markdown(source)["text"], expected)

    def test_intentional_markup_may_span_one_list_item_or_lazy_quote_paragraph(self) -> None:
        for source in (
            "- **bold\n  continued**\n",
            "- **bold\ncontinued**\n",
            "> **bold\nlazy continuation**\n",
            "> **open\n===\nclose**\n",
            "- **open\n===\nclose**\n",
            "1. **open\n===\nclose**\n",
            "> - **open\n===\nclose**\n",
            "> - **open\n> ===\n> close**\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(project_wom_safe_markdown(source)["text"], source)

    def test_list_interrupt_exceptions_remain_one_paragraph(self) -> None:
        cases = (
            "**bold\n2. continuation**\n",
            "**bold\n- \ncontinuation**\n",
            "- **open\n  2. middle\nclose**\n",
            "- **open\n  2. middle\n  close**\n",
            "- **open\n  2. middle\n    close**\n",
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertEqual(project_wom_safe_markdown(source)["text"], source)

        interrupted = "**open\n1. item**\n"
        self.assertEqual(
            project_wom_safe_markdown(interrupted)["text"],
            "\\*\\*open\n1. item\\*\\*\n",
        )

    def test_inline_code_is_byte_for_byte_preserved(self) -> None:
        source = "범위 `3~5 **not markup** ~~literal~~` 밖은 3~5이다.\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "범위 `3~5 **not markup** ~~literal~~` 밖은 3\\~5이다.\n",
        )
        self.assertEqual(result["metadata"]["counts"]["inline_code_span_count"], 1)

    def test_variable_length_and_multiline_code_spans_are_preserved(self) -> None:
        source = "``code ` 3~5 ** ~~`` and `line\nbreak ~ **` then 서울~부산\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "``code ` 3~5 ** ~~`` and `line\nbreak ~ **` then 서울\\~부산\n",
        )
        self.assertEqual(result["metadata"]["counts"]["inline_code_span_count"], 2)

    def test_urls_link_destinations_and_html_syntax_remain_byte_exact(self) -> None:
        source = (
            "<https://example.test/a~b> and https://example.test/c~d\n"
            "[range link](https://example.test/e~f \"title~literal\") 3~5\n"
            "[escaped close](https://example.test/g\\)h~i)\n"
            "<span title=\"a > b~c\" data-range=\"7~9\">서울~부산</span>\n"
            "<script>const range = \"11~13\";</script>\n"
        )

        result = project_wom_safe_markdown(source)

        self.assertIn("<https://example.test/a~b>", result["text"])
        self.assertIn("https://example.test/c~d", result["text"])
        self.assertIn(
            "[range link](https://example.test/e~f \"title~literal\") 3\\~5",
            result["text"],
        )
        self.assertIn(
            "[escaped close](https://example.test/g\\)h~i)",
            result["text"],
        )
        self.assertIn(
            '<span title="a > b~c" data-range="7~9">서울\\~부산</span>',
            result["text"],
        )
        self.assertIn(
            '<script>const range = "11~13";</script>',
            result["text"],
        )

    def test_pseudo_links_and_escaped_angle_openers_remain_ordinary_text(self) -> None:
        cases = {
            "](a~b) middle ](c~d)\n": "](a\\~b) middle ](c\\~d)\n",
            r"\](a~b) middle \](c~d)" + "\n": (
                r"\](a\~b) middle \](c\~d)" + "\n"
            ),
            r"\<ab:a~b> middle \<ab:c~d>" + "\n": (
                r"\<ab:a\~b> middle \<ab:c\~d>" + "\n"
            ),
            "<a~b@c..d> middle <e~f@g..h>\n": (
                "<a\\~b@c..d> middle <e\\~f@g..h>\n"
            ),
            "<a~b@c-.d> middle <e~f@g-.h>\n": (
                "<a\\~b@c-.d> middle <e\\~f@g-.h>\n"
            ),
            "before <!-- a~b middle **open\n": (
                "before <!-- a\\~b middle \\*\\*open\n"
            ),
            "before <![CDATA[a~b middle **open\n": (
                "before <![CDATA[a\\~b middle \\*\\*open\n"
            ),
            "before <?a~b middle **open\n": (
                "before <?a\\~b middle \\*\\*open\n"
            ),
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(project_wom_safe_markdown(source)["text"], expected)

    def test_actual_links_images_and_empty_labels_still_protect_destinations(self) -> None:
        source = (
            "[link](a~b) ![image](c~d) [](e~f) <a~b@c.d> "
            "[outer ![nested](g~h)](i~j) outside 3~5\n"
        )

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "[link](a~b) ![image](c~d) [](e~f) <a~b@c.d> "
            "[outer ![nested](g~h)](i~j) outside 3\\~5\n",
        )

    def test_nested_non_image_link_invalidates_only_its_open_ancestors(self) -> None:
        source = (
            "[prior](p~q) "
            "[outer [inner](a~b)](c~d) "
            "[later ![image](e~f)](g~h) outside 1~2\n"
        )

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "[prior](p~q) "
            "[outer [inner](a~b)](c\\~d) "
            "[later ![image](e~f)](g~h) outside 1\\~2\n",
        )

    def test_image_description_may_contain_a_link_but_outer_link_may_not(self) -> None:
        image = "![outer [inner](a~b)](c~d)\n"
        outer_link = "[outer ![img [inner](a~b)](c~d)](e~f)\n"

        self.assertEqual(project_wom_safe_markdown(image)["text"], image)
        self.assertEqual(
            project_wom_safe_markdown(outer_link)["text"],
            "[outer ![img [inner](a~b)](c~d)](e\\~f)\n",
        )

    def test_nested_link_tracking_has_linear_deterministic_operation_count(self) -> None:
        for target_kib in (8, 16, 32, 64):
            count = (target_kib * 1024) // 8
            source = ("[" * count) + ("[a](x) " * count)
            self.assertEqual(len(source.encode("utf-8")), target_kib * 1024)
            protected = [False] * len(source)
            escaped = _backslash_escape_mask(source)

            operations = _protect_inline_links(source, protected, escaped)

            with self.subTest(target_kib=target_kib):
                self.assertLessEqual(operations, len(source) * 10)
                self.assertEqual(project_wom_safe_markdown(source)["text"], source)

    def test_failed_link_suffix_scans_are_counted_and_linear(self) -> None:
        previous_operations: int | None = None
        for target_kib in (8, 16, 32, 64):
            repetitions = (target_kib * 1024) // 5
            source = ("[x](" * repetitions) + ("a" * repetitions)
            protected = [False] * len(source)
            escaped = _backslash_escape_mask(source)

            operations = _protect_inline_links(source, protected, escaped)

            with self.subTest(target_kib=target_kib):
                self.assertLessEqual(operations, len(source) * 10)
                if previous_operations is not None:
                    self.assertLessEqual(
                        operations,
                        previous_operations * 2 + 64,
                    )
                self.assertFalse(any(protected))
                self.assertEqual(
                    project_wom_safe_markdown(source)["text"],
                    source,
                )
            previous_operations = operations

    def test_angle_syntax_tracking_has_linear_deterministic_operation_count(self) -> None:
        for target_kib in (8, 16, 32, 64):
            for source_kind, source in (
                ("angle_openers", "<" * (target_kib * 1024)),
                ("unclosed_comments", "<!--" * (target_kib * 256)),
            ):
                protected = [False] * len(source)
                escaped = _backslash_escape_mask(source)

                operations = _protect_angle_syntax(source, protected, escaped)

                with self.subTest(
                    target_kib=target_kib,
                    source_kind=source_kind,
                ):
                    self.assertLessEqual(operations, len(source) * 12)
                    self.assertFalse(any(protected))
                    self.assertEqual(
                        project_wom_safe_markdown(source)["text"],
                        source,
                    )

    def test_link_destination_and_title_phases_preserve_literal_tildes(self) -> None:
        cases = {
            '[x](dest "title \\" quoted~value") outside 3~5\n': (
                '[x](dest "title \\" quoted~value") outside 3\\~5\n'
            ),
            "[x](dest 'title \\' quoted~value') outside 3~5\n": (
                "[x](dest 'title \\' quoted~value') outside 3\\~5\n"
            ),
            '[x](foo"bar~baz) outside 3~5\n': (
                '[x](foo"bar~baz) outside 3\\~5\n'
            ),
            "[x](foo'bar~baz) outside 3~5\n": (
                "[x](foo'bar~baz) outside 3\\~5\n"
            ),
            '[x](<foo)c~>) outside 3~5\n': (
                '[x](<foo)c~>) outside 3\\~5\n'
            ),
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(project_wom_safe_markdown(source)["text"], expected)

    def test_all_inline_link_title_forms_may_span_nonblank_lines(self) -> None:
        cases = (
            '[x](dest "title\nmore~value") outside 3~5\n',
            "[x](dest 'title\nmore~value') outside 3~5\n",
            "[x](dest (title\nmore~value)) outside 3~5\n",
        )
        for source in cases:
            with self.subTest(source=source):
                expected = source.replace("outside 3~5", "outside 3\\~5")
                self.assertEqual(project_wom_safe_markdown(source)["text"], expected)

    def test_multiline_reference_destination_and_title_are_preserved(self) -> None:
        cases = (
            "[foo]: /url '\ntitle~value **literal\n'\noutside 3~5\n",
            '[foo]: /url\n  "title~value **literal"\noutside 3~5\n',
            "   [foo]:\n      /url\n      'title~value **literal'\noutside 3~5\n",
        )
        for source in cases:
            with self.subTest(source=source):
                expected = source.replace("outside 3~5", "outside 3\\~5")
                self.assertEqual(project_wom_safe_markdown(source)["text"], expected)

    def test_reference_definitions_cannot_interrupt_or_restart_a_paragraph(self) -> None:
        cases = {
            "foo\n[a]: url~x\n[b]: url~y\n": (
                "foo\n[a]: url\\~x\n[b]: url\\~y\n"
            ),
            "[a]: url~x\nfoo\n[b]: url~y\n": (
                "[a]: url~x\nfoo\n[b]: url\\~y\n"
            ),
            "> [a]: url~x\n> [b]: url~y\n": (
                "> [a]: url~x\n> [b]: url~y\n"
            ),
            "> foo\n> [a]: url~x\n": (
                "> foo\n> [a]: url\\~x\n"
            ),
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(project_wom_safe_markdown(source)["text"], expected)

    def test_commonmark_does_not_treat_unicode_line_separators_as_lines(self) -> None:
        for separator in ("\u2028", "\u2029"):
            source = f"**{separator}text** outside 3~5\n"
            with self.subTest(codepoint=ord(separator)):
                self.assertEqual(
                    project_wom_safe_markdown(source)["text"],
                    f"**{separator}text** outside 3\\~5\n",
                )

    def test_raw_html_block_body_is_not_rewritten(self) -> None:
        source = (
            "<div data-range=\"1~2\">\n"
            "raw 3~5 **literal\n"
            "</div>\n"
            "\n"
            "outside 6~8\n"
        )

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "<div data-range=\"1~2\">\n"
            "raw 3~5 **literal\n"
            "</div>\n"
            "\n"
            "outside 6\\~8\n",
        )

    def test_multiline_inline_html_attribute_is_not_rewritten(self) -> None:
        source = 'before <span\n data-range="3~5">text</span> after 6~8\n'

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            'before <span\n data-range="3~5">text</span> after 6\\~8\n',
        )

    def test_inline_html_may_have_multiple_multiline_attributes(self) -> None:
        source = (
            'before <tag\n a="1~2"\n b="3~4">text</tag> outside 5~6\n'
        )

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            'before <tag\n a="1~2"\n b="3~4">text</tag> outside 5\\~6\n',
        )

    def test_invalid_html_attribute_name_does_not_hide_markdown_text(self) -> None:
        source = (
            '<a h*#ref="hi">\n'
            'range 3~5 **open\n'
            '\n'
            'outside 6~8\n'
        )

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            '<a h*#ref="hi">\n'
            'range 3\\~5 \\*\\*open\n'
            '\n'
            'outside 6\\~8\n',
        )

    def test_lowercase_cdata_is_not_misclassified_as_raw_html(self) -> None:
        source = "<![cdata[\nrange 3~5 **open\n]]>\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "<![cdata[\nrange 3\\~5 \\*\\*open\n]]>\n",
        )

    def test_raw_html_block_ends_with_its_quote_container(self) -> None:
        source = (
            "> <script>\n"
            "> const range = \"1~2\";\n"
            "outside 3~5\n"
        )

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "> <script>\n"
            "> const range = \"1~2\";\n"
            "outside 3\\~5\n",
        )

    def test_type_six_html_block_ends_on_container_blank_payload(self) -> None:
        source = "> <div>\n> raw 1~2\n>\n> outside 3~5\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "> <div>\n> raw 1~2\n>\n> outside 3\\~5\n",
        )

    def test_fenced_and_indented_code_are_byte_for_byte_preserved(self) -> None:
        source = (
            "앞 1~2\n"
            "```markdown\n"
            "3~5 **broken ~~broken\n"
            "```\n"
            "~~~ text ` allowed ~~~\n"
            "서울~부산 **literal\n"
            "~~~~\n"
            "    indented 8~10 **literal\n"
            "뒤 4~6\n"
        )

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "앞 1\\~2\n"
            "```markdown\n"
            "3~5 **broken ~~broken\n"
            "```\n"
            "~~~ text ` allowed ~~~\n"
            "서울~부산 **literal\n"
            "~~~~\n"
            "    indented 8~10 **literal\n"
            "뒤 4\\~6\n",
        )
        counts = result["metadata"]["counts"]
        self.assertEqual(counts["fenced_code_block_count"], 2)
        self.assertEqual(counts["indented_code_line_count"], 1)

    def test_fenced_and_indented_code_inside_containers_are_preserved(self) -> None:
        source = (
            "> ```markdown\n"
            "> 3~5 **literal\n"
            "> ```\n"
            "- ~~~text\n"
            "  서울~부산 **literal\n"
            "  ~~~\n"
            ">     quoted indented 8~10 **literal\n"
            "outside 1~2\n"
        )

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "> ```markdown\n"
            "> 3~5 **literal\n"
            "> ```\n"
            "- ~~~text\n"
            "  서울~부산 **literal\n"
            "  ~~~\n"
            ">     quoted indented 8~10 **literal\n"
            "outside 1\\~2\n",
        )
        counts = result["metadata"]["counts"]
        self.assertEqual(counts["fenced_code_block_count"], 2)
        self.assertEqual(counts["indented_code_line_count"], 1)

    def test_unclosed_container_fence_ends_with_its_container(self) -> None:
        source = "> ```\n> code 1~2\n범위 3~5일, 다음 8~10일\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(
            result["text"],
            "> ```\n> code 1~2\n범위 3\\~5일, 다음 8\\~10일\n",
        )

    def test_four_space_line_cannot_interrupt_an_open_paragraph(self) -> None:
        source = "문단 시작\n    이어지는 범위 3~5\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(result["text"], "문단 시작\n    이어지는 범위 3\\~5\n")
        self.assertEqual(
            result["metadata"]["counts"]["indented_code_line_count"],
            0,
        )

    def test_existing_backslash_escapes_are_preserved_and_projection_is_idempotent(self) -> None:
        source = r"이미 \~ 안전하고 \*\* 그대로이며 새 범위는 3~5" + "\n"

        first = project_wom_safe_markdown(source)
        second = project_wom_safe_markdown(first["text"])

        self.assertEqual(first["text"], r"이미 \~ 안전하고 \*\* 그대로이며 새 범위는 3\~5" + "\n")
        self.assertEqual(second["text"], first["text"])
        self.assertGreaterEqual(first["metadata"]["counts"]["existing_backslash_escape_count"], 3)

    def test_even_backslash_parity_does_not_hide_an_unescaped_tilde(self) -> None:
        source = "literal slash then range: \\\\~\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(result["text"], "literal slash then range: \\\\\\~\n")

    def test_triple_or_longer_tilde_runs_are_not_gfm_strikethrough(self) -> None:
        source = "inline ~~~not strike~~~ and ~~~~also not strike~~~~\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(result["text"], source)

    def test_longer_commonmark_emphasis_runs_are_not_destroyed(self) -> None:
        for source in ("**굵게***\n", "***굵고 기울게***\n", "***굵게**\n"):
            with self.subTest(source=source):
                self.assertEqual(project_wom_safe_markdown(source)["text"], source)

    def test_backslash_parity_scan_is_linear_in_shape(self) -> None:
        source = ("\\" * 16_000) + "~\n"

        result = project_wom_safe_markdown(source)

        self.assertEqual(result["text"], ("\\" * 16_001) + "~\n")

    def test_source_value_is_unchanged_and_hashes_are_deterministic(self) -> None:
        source = "원본 3~5와 **broken\r\n두 번째 줄\r\n"
        original_copy = source[:]

        first = project_wom_safe_markdown(source)
        second = project_wom_safe_markdown(source)

        self.assertEqual(source, original_copy)
        self.assertEqual(first, second)
        metadata = first["metadata"]
        self.assertEqual(metadata["schema"], WOM_SAFE_MARKDOWN_DISPLAY_SCHEMA)
        self.assertTrue(metadata["display_only"])
        self.assertTrue(metadata["canonical_source_unchanged"])
        self.assertTrue(metadata["changed"])
        self.assertEqual(metadata["source_sha256"], hashlib.sha256(source.encode("utf-8")).hexdigest())
        self.assertEqual(
            metadata["projected_sha256"],
            hashlib.sha256(first["text"].encode("utf-8")).hexdigest(),
        )

    def test_empty_and_already_safe_input_have_content_free_metadata(self) -> None:
        for source in ("", "그냥 안전한 문장\n"):
            with self.subTest(source=source):
                result = project_wom_safe_markdown(source)
                self.assertEqual(result["text"], source)
                metadata = result["metadata"]
                self.assertFalse(metadata["changed"])
                self.assertEqual(
                    set(metadata),
                    {
                        "schema",
                        "profile",
                        "display_only",
                        "canonical_source_unchanged",
                        "changed",
                        "source_sha256",
                        "projected_sha256",
                        "counts",
                    },
                )
                if source:
                    self.assertNotIn(source, repr(metadata))

    def test_non_string_input_is_rejected_without_coercion(self) -> None:
        with self.assertRaisesRegex(TypeError, "source must be str"):
            project_wom_safe_markdown(b"3~5")  # type: ignore[arg-type]


class WomSafeMarkdownReadZettelIntegrationTests(unittest.TestCase):
    fixture = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "fake-life-archive"
    )

    def make_archive(self, parent: Path) -> tuple[Path, Path, str]:
        root = parent / "archive"
        shutil.copytree(self.fixture, root)
        zettel_id = "zet_20240504_fake_lunch_thought"
        path = root / "zettels" / f"{zettel_id}.md"
        frontmatter, _body = archive_services.split_zettel_text(
            path.read_text(encoding="utf-8")
        )
        body = (
            "# 사람용 보기\n\n"
            "기간은 3~5일이고 서울~부산을 오간다. **열린 강조\n\n"
            "**의도한 굵게**와 ~~의도한 삭선~~은 유지한다.\n\n"
            "`코드 3~5 **그대로`\n"
        )
        path.write_text(
            "---\n"
            + archive_cli.dump_yaml(frontmatter)
            + "---\n\n"
            + body,
            encoding="utf-8",
            newline="",
        )
        return root, path, zettel_id

    def test_document_view_projects_safely_without_mutating_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, path, zettel_id = self.make_archive(Path(tmp))
            before = path.read_bytes()
            canonical = archive_services.read_zettel(
                root,
                zettel_id=zettel_id,
                section="body",
            )
            document = archive_services.read_zettel(
                root,
                zettel_id=zettel_id,
                section="document",
            )

            self.assertEqual(path.read_bytes(), before)
            self.assertIn("3~5", canonical["body"])
            self.assertIn("서울~부산", canonical["body"])
            self.assertIn("**열린 강조", canonical["body"])
            self.assertNotIn("display", canonical)
            self.assertIn("3\\~5", document["body"])
            self.assertIn("서울\\~부산", document["body"])
            self.assertIn("\\*\\*열린 강조", document["body"])
            self.assertIn("**의도한 굵게**", document["body"])
            self.assertIn("~~의도한 삭선~~", document["body"])
            self.assertIn("`코드 3~5 **그대로`", document["body"])
            self.assertEqual(document["display"]["profile"], "wom_safe_markdown")
            self.assertTrue(document["display"]["display_only"])
            self.assertTrue(document["display"]["canonical_source_unchanged"])
            self.assertEqual(
                document["integrity"]["body_sha256"],
                canonical["integrity"]["body_sha256"],
            )
            self.assertTrue(
                document["integrity"]["returned_body_is_display_projection"]
            )
            self.assertNotEqual(
                document["integrity"]["body_sha256"],
                document["integrity"]["returned_body_sha256"],
            )

    def test_body_pages_remain_hash_bound_canonical_source_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _path, zettel_id = self.make_archive(Path(tmp))
            result = archive_services.read_zettel(
                root,
                zettel_id=zettel_id,
                section="document",
                body_max_chars=12,
            )
            canonical = archive_services.read_zettel(
                root,
                zettel_id=zettel_id,
                section="body",
            )

            self.assertNotIn("display", result)
            self.assertFalse(
                result["integrity"]["returned_body_is_display_projection"]
            )
            self.assertEqual(result["body"], canonical["body"][:12])

    def test_document_text_cli_emits_the_safe_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, path, zettel_id = self.make_archive(Path(tmp))
            before = path.read_bytes()
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = archive_cli.main(
                    [
                        "read-zettel",
                        str(root),
                        "--zettel-id",
                        zettel_id,
                        "--section",
                        "document",
                    ]
                )

            self.assertEqual(code, 0, stderr.getvalue())
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("3\\~5", stdout.getvalue())
            self.assertIn("\\*\\*열린 강조", stdout.getvalue())
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
