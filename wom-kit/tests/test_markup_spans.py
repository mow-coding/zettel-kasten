"""Body fixtures are synthetic; protected byte spans are exact literals."""
import unittest
from wom_kit import completion_workflows as workflows


class MarkupSpanTests(unittest.TestCase):
    def normalize(self, body):
        return workflows._normalize_markup_body(body)

    def test_root_fence_inline_code_and_comment_are_unchanged_while_sibling_normalizes(self):
        literals = ["```html\r\n<span>literal</span>\r\n```\r\n",
                    "Use `<span>inline literal</span>` here.\n",
                    "<!-- <span>comment literal</span> -->\n"]
        for literal in literals:
            with self.subTest(literal=literal):
                body = literal + "\n<span>Visible live text</span>\n"
                result = self.normalize(body)
                self.assertTrue(result["changed"], result)
                self.assertEqual(result["blocker_codes"], [])
                self.assertIn(literal, result["normalized_body"])
                self.assertNotIn("<span>Visible", result["normalized_body"])

    def test_nested_columns_and_callout_preserve_visible_order_without_invented_content(self):
        body = '<column_list><column>First</column><column><callout icon="★">Second</callout></column></column_list>\n'
        result = self.normalize(body)
        self.assertTrue(result["changed"], result)
        self.assertEqual(result["blocker_codes"], [])
        after = result["normalized_body"]
        self.assertLess(after.index("First"), after.index("Second"))
        self.assertIn("★", after)
        self.assertNotIn("<column", after)
        self.assertNotIn("<callout", after)

    def test_placeholder_and_unbalanced_container_never_become_recovered_content(self):
        for body in ("<unknown:column_list/>\n", "<callout></callout>\n", "<column_list><column>Text</column_list>"):
            with self.subTest(body=body):
                result = self.normalize(body)
                self.assertFalse(result["changed"])
                self.assertEqual(result["normalized_body"], body)
                self.assertIn("markup_container_source_or_structure_required", result["blocker_codes"])

    def test_fake_fence_close_in_different_container_does_not_expose_literal_tags(self):
        literal = '```html\n> ```\n<span>Still literal</span>\n```\n'
        result = self.normalize(literal + "\n<span>Live sibling</span>\n")
        self.assertIn(literal, result["normalized_body"])
        self.assertNotIn("<span>Live sibling", result["normalized_body"])

    def test_cell_inline_markup_preserves_label_and_escaped_pipes(self):
        body = '<table><tr><th>Label</th><th>Value</th></tr><tr><td><strong>A</strong><br/>B</td><td><em>C | D</em></td></tr></table>'
        result = self.normalize(body)
        self.assertTrue(result["changed"], result)
        self.assertIn("<strong>A</strong>", result["normalized_body"])
        self.assertIn("C \\| D", result["normalized_body"])


if __name__ == "__main__":
    unittest.main()
