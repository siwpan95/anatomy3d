# -*- coding: utf-8 -*-
"""懒加载核心单测（headless，无 pyglet / GL 依赖）。"""
import json
import os
import unittest

from anatomy3d.viewer.lazy import LazyAtlas, sanitize_node

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fake_doc(n=10):
    nodes = []
    for i in range(n):
        node = {"name": f"Organ {i}"}
        if i % 2 == 0:                     # 一半有 mesh，一半是分组节点
            node["mesh"] = i // 2
        nodes.append(node)
    return {"nodes": nodes, "scenes": [{"nodes": [0]}]}


def fake_manifest():
    return {
        "manifest_version": 1,
        "source": "test",
        "systems": [{
            "name": "test",
            "structures": [
                {"id": "TA2:1:test:organ_2", "names": {"en": "Organ 2"},
                 "mesh": {"glb": "x.glb", "node": "Organ 2"}},
                {"id": "TA2:2:test:organ_4", "names": {"en": "Organ 4"},
                 "mesh": {"glb": "x.glb", "node": "Organ_4"}},  # sanitize 形态
            ],
        }],
    }


class TestLazyAtlas(unittest.TestCase):
    def test_only_mesh_nodes_indexed(self):
        a = LazyAtlas(fake_doc(10))
        self.assertEqual(len(a.mesh_nodes), 5)
        self.assertEqual([i for i, _ in a.mesh_nodes], [0, 2, 4, 6, 8])

    def test_budget_is_hard_cap(self):
        a = LazyAtlas(fake_doc(100), budget=3)
        selected, unmatched, skipped = a.plan()
        self.assertEqual(len(selected), 3)
        self.assertEqual(skipped, 47)
        self.assertEqual(unmatched, [])

    def test_name_lookup_both_forms(self):
        a = LazyAtlas(fake_doc(), fake_manifest())
        self.assertEqual(a.structure_for_node(2)["id"], "TA2:1:test:organ_2")
        self.assertEqual(a.structure_for_node(4)["id"], "TA2:2:test:organ_4")

    def test_plan_by_names(self):
        a = LazyAtlas(fake_doc(), budget=2)
        selected, unmatched, skipped = a.plan(names=["Organ 4", "Organ_6", "NoSuch"])
        self.assertEqual([i for i, _ in selected], [4, 6])
        self.assertEqual(unmatched, ["NoSuch"])

    def test_built_tracking(self):
        a = LazyAtlas(fake_doc())
        self.assertFalse(a.is_built(2))
        a.mark_built(2)
        self.assertTrue(a.is_built(2))
        self.assertEqual(a.built_count(), 1)

    def test_real_manifest_loads(self):
        path = os.path.join(REPO, "assets", "anatomy.manifest.json")
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
        a = LazyAtlas(fake_doc(20), manifest)
        self.assertGreater(a.budget, 0)
        self.assertEqual(sum(len(s["structures"]) for s in manifest["systems"]), 5954)

    def test_sanitize(self):
        self.assertEqual(sanitize_node("Right atrium"), "Right_atrium")


if __name__ == "__main__":
    unittest.main()
