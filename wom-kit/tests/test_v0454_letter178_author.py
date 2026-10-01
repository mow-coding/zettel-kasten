"""v0.4.54 (beta letter 178): a letter must say which AI, model and reasoning level wrote it.

The helper AI wrote the model as "not collected" although the person could see
it in the app, and the structure check passed the letter. The request now has a
required author block; a placeholder is refused unless the person could not
tell either, and the refusal says to ask the person.

Synthetic archive; no client data.
"""

import copy
import unittest

from wom_kit import operator_feedback_body as body

import test_operator_feedback_body as fixture


class LetterAuthorTests(unittest.TestCase):
    def check(self, author):
        request = copy.deepcopy(fixture.valid_request())
        if author is None:
            request.pop("author")
        else:
            request["author"] = author
        return body._author_line(request.get("author"))

    def test_a_confirmed_author_is_written_first_in_the_environment_section(self):
        line, blockers = self.check({"ai_product": "OpenAI Codex desktop app", "model": "gpt-6-sol",
                                     "reasoning_level": "high", "source": "confirmed_by_user"})
        self.assertEqual(blockers, [])
        self.assertEqual(line, "작성 AI: OpenAI Codex desktop app · 모델: gpt-6-sol · 추론 수준: high · 출처: 사용자 확인")

    def test_a_missing_author_block_is_refused(self):
        self.assertEqual(self.check(None), (None, ["feedback_body_author_missing"]))
        self.assertEqual(self.check({"ai_product": "Codex"})[1], ["feedback_body_author_missing"])

    def test_a_placeholder_model_is_refused_unless_the_person_could_not_tell(self):
        for placeholder in ("미수집", "unknown", "확인 불가", "N/A", ""):
            with self.subTest(placeholder=placeholder):
                self.assertEqual(self.check({"ai_product": "Codex", "model": placeholder, "reasoning_level": "high",
                                             "source": "confirmed_by_user"})[1], ["feedback_body_author_unconfirmed"])
        line, blockers = self.check({"ai_product": "Codex", "model": "미수집", "reasoning_level": "모름",
                                     "source": "user_could_not_tell"})
        self.assertEqual(blockers, [])
        self.assertIn("모델: 확인 불가 · 추론 수준: 확인 불가 · 출처: 사용자도 확인하지 못함", line)
        # "could not tell" with real values is contradictory
        self.assertEqual(self.check({"ai_product": "Codex", "model": "gpt-6-sol", "reasoning_level": "high",
                                     "source": "user_could_not_tell"})[1], ["feedback_body_author_source_invalid"])
        self.assertEqual(self.check({"ai_product": "unknown", "model": "gpt-6-sol", "reasoning_level": "high",
                                     "source": "confirmed_by_user"})[1], ["feedback_body_author_unconfirmed"])

    def test_the_compose_refusal_tells_the_ai_to_ask_the_person(self):
        case = fixture.OperatorFeedbackBodyTests("test_plan_is_write_free_content_free_and_digest_bound")
        case.setUp()
        self.addCleanup(case.doCleanups)
        request = copy.deepcopy(fixture.valid_request())
        request["author"]["model"] = "not collected"
        case.write_request(request)
        plan = body.plan_operator_feedback_body(case.root, case.request_path)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["blockers"], ["feedback_body_author_unconfirmed"])
        self.assertEqual(plan["next_safe_actions"], [body.AUTHOR_NEXT_SAFE_ACTION])
        request["author"] = {"ai_product": "OpenAI Codex desktop app", "model": "gpt-6-sol",
                             "reasoning_level": "high", "source": "confirmed_by_user"}
        case.write_request(request)
        plan = body.plan_operator_feedback_body(case.root, case.request_path)
        self.assertTrue(plan["ok"], plan)

    def test_the_guidance_names_the_person_and_the_sources(self):
        self.assertIn("Ask the person", body.AUTHOR_NEXT_SAFE_ACTION)
        self.assertIn("user_could_not_tell", body.AUTHOR_NEXT_SAFE_ACTION)
        self.assertEqual(set(body.AUTHOR_SOURCES), {"confirmed_by_user", "read_from_runtime", "user_could_not_tell"})


if __name__ == "__main__":
    unittest.main()
