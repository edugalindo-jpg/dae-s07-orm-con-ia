"""The duel itself is code, so it has tests: the oracle must agree with the
reference answers, and the assistant's answers must fail in the way the lab says."""
import importlib.util
import unittest

from django.core.management import call_command
from django.test import TestCase

from blog.duel.runner import run_all

HAS_TEACHER = importlib.util.find_spec("teacher") is not None


class DuelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_blog", verbosity=0)

    def statuses(self, source):
        return {verdict.key: verdict.status for verdict in run_all(source)}

    @unittest.skipUnless(HAS_TEACHER, "carpeta teacher/ ausente")
    def test_reference_solutions_are_all_correct_and_cheap(self):
        self.assertEqual(set(self.statuses("solutions").values()), {"ok"})

    def test_the_team_answers_are_all_correct_and_cheap(self):
        self.assertEqual(set(self.statuses("team").values()), {"ok"})

    def test_the_assistant_fails_where_the_lab_says(self):
        self.assertEqual(
            self.statuses("ai"),
            {
                "q1": "ok",
                "q2": "ok",
                "q3": "wrong",   # excludes the boundary dates
                "q4": "costly",  # right result, filtered in Python (N+1)
                "q5": "wrong",   # counts multiplied: no distinct=True
                "q6": "error",   # invented field `author__country`
                "q7": "ok",
                "q8": "wrong",   # drafts are not "never published"
            },
        )

    def test_single_question(self):
        verdicts = run_all("ai", only="q4")
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0].queries, 1 + 15)
