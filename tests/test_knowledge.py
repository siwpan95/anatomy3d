# -*- coding: utf-8 -*-
"""M3/M4 单测：三语富化与 quiz 红绿。"""
import json
import os
import unittest

from anatomy3d.knowledge.quiz import Quiz
from anatomy3d.knowledge.zh import Knowledge

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def manifest():
    return {
        "manifest_version": 1,
        "source": "test",
        "systems": [{
            "name": "test",
            "structures": [
                {"id": "TA2:1:test:heart", "ta2_id": "4076",
                 "names": {"en": "Heart"}, "kind": "organ",
                 "definition": {"zh": "泵血器官"}},
                {"id": "TA2:2:test:liver", "ta2_id": "5001",
                 "names": {"en": "Liver"}, "kind": "organ"},
                {"id": "TA2:3:test:femur", "ta2_id": "6001",
                 "names": {"en": "Femur"}, "kind": "bone"},
            ],
        }],
    }


class TestKnowledge(unittest.TestCase):
    def test_real_index_loaded(self):
        k = Knowledge()
        self.assertGreater(len(k.zh), 700)
        self.assertEqual(k.zh_for("Heart"), "心")
        self.assertIsNotNone(k.latin_for("4076"))

    def test_normalize(self):
        k = Knowledge()
        self.assertEqual(k.zh_for("HEART"), "心")
        self.assertIsNotNone(k.zh_for("Aorta (thoracic)"))

    def test_definition(self):
        self.assertIn("泵血", Knowledge().definition_for("Heart"))

    def test_enrich_manifest(self):
        enriched, stats = Knowledge().enrich_manifest(manifest())
        s = enriched["systems"][0]["structures"][0]
        self.assertEqual(s["names"]["zh"], "心")
        self.assertTrue(s["names"].get("la"))
        self.assertEqual(stats["structures"], 3)
        self.assertEqual(manifest()["systems"][0]["structures"][0]["names"], {"en": "Heart"})  # 原对象未变


class TestQuiz(unittest.TestCase):
    def test_question_shape(self):
        q = Quiz(manifest(), seed=3)
        question = q.next()
        self.assertIn("请指出", question["prompt"])
        self.assertEqual(len(question["options"]), 3)
        self.assertTrue(any(o["id"] == question["answer_id"] for o in question["options"]))

    def test_answer_scoring(self):
        q = Quiz(manifest(), seed=3)
        question = q.next()
        bad = q.answer("wrong-id")
        self.assertFalse(bad["correct"])
        self.assertEqual(bad["score"], "0/1")
        self.assertIn("正确答案", bad["message"])

    def test_no_zh_no_question(self):
        m = manifest()
        for s in m["systems"][0]["structures"]:
            s["names"] = {"en": "Unmapped obscure structure " + s["id"]}
        self.assertIsNone(Quiz(m).next())


if __name__ == "__main__":
    unittest.main()
