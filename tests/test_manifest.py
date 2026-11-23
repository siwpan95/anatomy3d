# -*- coding: utf-8 -*-
"""契约层单测：manifest 校验的红绿双向覆盖（与 selfcheck 互补，供 unittest 发现）。"""
import unittest

from anatomy3d.contracts.manifest import validate_manifest


def good_manifest():
    return {
        "manifest_version": 1,
        "source": "bodyparts3d",
        "systems": [
            {
                "name": "skeleton",
                "structures": [
                    {
                        "id": "FMA24965",
                        "names": {"en": "Femur", "la": "Femur", "zh": "股骨"},
                        "kind": "bone",
                        "mesh": {"glb": "skeleton.glb", "node": "Femur"},
                        "parents": [],
                    }
                ],
            }
        ],
    }


class TestManifestValidation(unittest.TestCase):
    def test_valid_passes(self):
        self.assertEqual(validate_manifest(good_manifest()), [])

    def test_wrong_version_fails(self):
        m = good_manifest()
        m["manifest_version"] = 99
        self.assertTrue(validate_manifest(m))

    def test_duplicate_id_fails(self):
        m = good_manifest()
        m["systems"][0]["structures"].append(dict(m["systems"][0]["structures"][0]))
        problems = validate_manifest(m)
        self.assertTrue(any("重复" in p for p in problems))

    def test_dangling_parent_reported(self):
        m = good_manifest()
        m["systems"][0]["structures"][0]["parents"] = ["FMA99999"]   # 清单内不存在
        problems = validate_manifest(m)
        self.assertTrue(any("悬空" in p for p in problems))

    def test_invalid_kind_fails(self):
        m = good_manifest()
        m["systems"][0]["structures"][0]["kind"] = "robot"
        self.assertTrue(validate_manifest(m))


if __name__ == "__main__":
    unittest.main()
