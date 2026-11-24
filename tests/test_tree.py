# -*- coding: utf-8 -*-
"""结构树单测（P24）：构建/过滤/渲染/导航。"""
import unittest

from anatomy3d.viewer.tree import StructureTree, SYSTEM_MAP

H = {"nodes": [
    {"clean": "Femur", "system": "1: Skeletal system",
     "parents": ["Bonus collection", "Skeletal", "Lower limb"]},
    {"clean": "Femur", "system": "9: Regions of human body",
     "parents": ["Bonus collection", "Regions", "Thigh"]},
    {"clean": "Heart", "system": "5: Cardiovascular system",
     "parents": ["Bonus collection", "Cardiovascular"]},
    {"clean": "Orphan", "system": "1: Skeletal system", "parents": []},
]}


class TestStructureTree(unittest.TestCase):
    def test_system_filter_and_dedupe(self):
        t = StructureTree(H, "skeletal")
        leaves = t.leaf_names()
        self.assertIn("Femur", leaves)
        self.assertNotIn("Heart", leaves)
        self.assertEqual(leaves.count("Femur"), 1)

    def test_render_and_navigate(self):
        t = StructureTree(H, "skeletal")
        lines = t.render(max_rows=10)
        self.assertTrue(lines[0].startswith(">"))
        self.assertTrue(any("Lower limb" in x for x in lines))
        t.move(1)
        self.assertTrue(t.render(max_rows=10)[1].startswith(">"))

    def test_leaf_select(self):
        t = StructureTree(H, "skeletal")
        for _ in range(len(t.leaf_names()) + 2):
            t.render(max_rows=10)
            if t.selected_leaf() == "Femur":
                break
            t.move(1)
        self.assertEqual(t.selected_leaf(), "Femur")

    def test_empty_tree(self):
        t = StructureTree({"nodes": []}, None)
        self.assertEqual(t.render(), ["(empty tree)"])

    def test_system_map_covers_inspect_roots(self):
        self.assertEqual(SYSTEM_MAP["5: Cardiovascular system"], "cardiovascular")
        self.assertEqual(len(SYSTEM_MAP), 9)


if __name__ == "__main__":
    unittest.main()
