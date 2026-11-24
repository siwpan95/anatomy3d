# -*- coding: utf-8 -*-
"""TA2 近似匹配器单测（P23）：分层匹配链 + 误匹配拒绝。"""
import unittest

from anatomy3d.knowledge.ta2_match import MatchIndex, clean_zanatomy, normalize


class TestClean(unittest.TestCase):
    def test_suffix_variants(self):
        self.assertEqual(clean_zanatomy("Heart.l"), "Heart")
        self.assertEqual(clean_zanatomy("Adductor pollicis.e1l"), "Adductor pollicis")
        self.assertEqual(clean_zanatomy("Bucinator.o1r"), "Bucinator")
        self.assertEqual(clean_zanatomy("Right pulmonary artery'"), "Right pulmonary artery")

    def test_paren(self):
        # 尾部注记：剥掉
        self.assertEqual(clean_zanatomy("Cingulate gyrus (Posteroventral part*)"),
                         "Cingulate gyrus")
        # 整名包裹：去壳保留内容
        self.assertEqual(clean_zanatomy("(Accessory parotid gland)"),
                         "Accessory parotid gland")
        # 剥完不为空的防御：纯括号内容剥壳而非清空
        self.assertNotEqual(clean_zanatomy("(Abdominal part of pectoralis major muscle)"), "")

    def test_star_tail(self):
        self.assertEqual(clean_zanatomy("Anterior occipital sulcus*"), "Anterior occipital sulcus")


class TestNormalize(unittest.TestCase):
    def test_pairs(self):
        self.assertEqual(normalize("Pulmonary arteries"), normalize("Pulmonary artery"))
        self.assertEqual(normalize("Left-Ventricle"), normalize("left ventricle"))
        self.assertEqual(normalize("Heart"), "heart")


class TestMatch(unittest.TestCase):
    def setUp(self):
        self.idx = MatchIndex.from_pairs([
            ("Adductor pollicis", "T1"),
            ("Pulmonary artery", "T2"),
            ("Cingulate gyrus", "T3"),
            ("Accessory parotid gland", "T4"),
        ])

    def test_levels(self):
        r = self.idx.match("Adductor pollicis")
        self.assertEqual((r.value, r.level), ("T1", "exact"))
        r = self.idx.match("Adductor pollicis.e1l")
        self.assertEqual((r.value, r.level), ("T1", "suffix"))
        r = self.idx.match("Pulmonary arteries")
        self.assertEqual((r.value, r.level), ("T2", "normalized"))
        r = self.idx.match("Pulonary artery")           # P10 真实拼写错
        self.assertEqual((r.value, r.level), ("T2", "edit1"))
        r = self.idx.match("(Accessory parotid gland).r")
        self.assertEqual(r.value, "T4")

    def test_rejections(self):
        self.assertIsNone(self.idx.match("Femur"))
        self.assertIsNone(self.idx.match(""))
        self.assertIsNone(self.idx.match("Pulonarry artery"))  # ED2 不命中

    def test_first_wins(self):
        idx = MatchIndex()
        idx.add("Heart", "A")
        idx.add("Heart", "B")
        self.assertEqual(idx.match("heart").value, "A")


if __name__ == "__main__":
    unittest.main()
