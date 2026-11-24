# -*- coding: utf-8 -*-
"""场景清单导入器 —— Z-Anatomy inspect.json → 层级索引 hierarchy.json（stdlib only）。

用法::

    python tools/pipeline/import_inspect.py \
        --inspect data/scene_inspect.json \
        --manifest assets/anatomy.manifest.json \
        --out data/scene_hierarchy.json
    python tools/pipeline/import_inspect.py --selfcheck   # 能红能绿自检，不写文件

输入 `inspect.json`（由 Blender 无头 inspect 模式产出）是**纯元数据**，含：
  · collections[] —— 1944 个集合，每个有 name / path（真实层级）/ children / mesh_count
  · objects[]     —— 4569 个网格对象，每个有 name / collections[]（扁平集合名成员）/
                     vertices / polygons / hide_viewport / hide_render

产出 `hierarchy.json`（结构如下），供 manifest 的软字段 `parents[]` 与知识层消费::

    {
      "source": "z-anatomy", "kind": "scene-hierarchy", "version": 1,
      "stats": {"collections": 1944, "objects": 4569, "resolved": 14814,
                "unresolved": 2, "manifest_join": 2109, "parents_filled": 0},
      "nodes": [
        {"name": " Posterior transverse collateral sulcus.l",
         "clean": "posterior transverse collateral sulcus",
         "system": "7: Nervous system & Sense organs",
         "paths": ["7: Nervous system & Sense organs",
                   "Bonus collection/Nervous system/.../Brain/Cerebrum/Telencephalon", ...],
         "parents": ["Bonus collection", "Nervous system", "...", "Telencephalon"],
         "vertices": 102, "polygons": 160,
         "hidden": {"viewport": false, "render": true},
         "manifest_id": "TA2:...:..." or null}
      ]
    }

设计纪律（与 M1 契约 v1 对齐）：
  · 只加字段、不改既有 manifest —— hierarchy.json 是旁路数据，manfiest 保持冻结；
  · 名字清洗复用 build_manifest 的后缀规则（.l/.r/.j/.ol/.or 与尾 `'` 逐层剥离），
    以便与 manifest 的 TA2 join 对齐；
  · parents 取**最长**的解析路径（语义最具体），其余路径留档在 paths[]；
  · 能红能绿：selfcheck 注入坏数据（集合缺 path / 对象 name 缺失 / join 全失败）必须被抓。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from anatomy3d.knowledge.ta2_match import MatchIndex, clean_zanatomy  # noqa: E402

# 与 build_manifest.py 一致的后缀清洗
SUFFIX_RE = re.compile(r"\s*[.](?:[a-z]{1,3})\s*$")
PRIME_RE = re.compile(r"\s*'\s*$")
SYSTEM_RE = re.compile(r"^\d+:")


def clean_name(name: str, max_pass: int = 3) -> str:
    """逐层剥离 Z-Anatomy 命名后缀，返回用于 join / 索引的规范名。"""
    cur = str(name).strip()
    for _ in range(max_pass):
        stripped = SUFFIX_RE.sub("", PRIME_RE.sub("", cur)).strip()
        if stripped == cur:
            break
        cur = stripped
    return cur


def system_of(memberships: list[str]) -> str | None:
    """取 'N: ...' 形态的顶层系统集合名（每个对象理论上唯一）。"""
    for m in memberships:
        if SYSTEM_RE.match(m):
            return m
    return None


def load_ta2_pairs(path: str) -> list[tuple[str, str]]:
    """TA2.csv → [(English, TA2ID)]（与 build_manifest 同款解析，BOM+引号+分号）。"""
    pairs = []
    rows = [ln.strip().strip('"').split(";") for ln in open(path, encoding="utf-8-sig") if ln.strip()]
    header = None
    for row in rows:
        if row and row[0].strip().lower().startswith("ta2id"):
            header = row
            break
    if header is None:
        return pairs
    cols = {n.strip().lower(): i for i, n in enumerate(header)}
    for row in rows:
        if row is header or len(row) <= max(cols["ta2id"], cols["english"]):
            continue
        en, tid = row[cols["english"]].strip(), row[cols["ta2id"]].strip()
        if en and tid:
            pairs.append((en, tid))
    return pairs


def build_hierarchy(inspect: dict, manifest: dict | None = None,
                    ta2_pairs: list[tuple[str, str]] | None = None) -> dict:
    """把场景清单转成层级索引；返回 (hierarchy dict)。纯函数，便于 selfcheck。"""
    cols = inspect.get("collections", [])
    objs = inspect.get("objects", [])

    # 集合 name → path（已验证无重名；防御性地保留列表取首个）
    by_name: dict[str, str] = {}
    for c in cols:
        n, p = c.get("name"), c.get("path")
        if not n or not p:
            raise ValueError("集合条目缺 name/path: %r" % (c,))
        by_name.setdefault(n, p)

    # manifest node 规范名 → id（旁路 join，只为标注，不改 manifest）。
    # P23：改用分层匹配（exact→suffix→normalized→edit1），join 率 56%→90%+。
    join_index = MatchIndex()
    if manifest:
        for s in manifest.get("systems", []):
            for st in s.get("structures", []):
                node = (st.get("mesh") or {}).get("node", "")
                if node:
                    join_index.add(node, st.get("id", ""))

    # TA2 全表索引：对 manifest join 未命中的对象做概念级匹配（P23 第二层）——
    # 命中即「结构增量候选」（manifest 无此节点，但有 TA2 id 可追溯），输出候选表。
    ta2_index = MatchIndex.from_pairs(ta2_pairs) if ta2_pairs else None
    nodes = []
    candidates = []
    resolved = unresolved = 0
    parents_filled = 0
    level_count: dict[str, int] = defaultdict(int)
    for o in objs:
        name = o.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("对象缺 name: %r" % (o,))
        members = o.get("collections") or []
        paths = []
        for m in members:
            p = by_name.get(m)
            if p:
                paths.append(p)
                resolved += 1
            else:
                unresolved += 1
        # canonical = 最长路径（语义最具体）；parents = 其分段
        canonical = max(paths, key=lambda x: (len(x.split("/")), len(x))) if paths else ""
        parents = canonical.split("/") if canonical else []
        if parents:
            parents_filled += 1
        clean = clean_zanatomy(name)
        m = join_index.match(clean) if manifest else None
        mid = m.value if m else None
        if m:
            level_count[m.level] += 1
        ta2_id = ta2_level = ta2_term = None
        if mid is None and ta2_index is not None:
            tm = ta2_index.match(clean)
            if tm:
                ta2_id, ta2_level, ta2_term = tm.value, tm.level, tm.term
                candidates.append({
                    "clean": clean, "system": system_of(members),
                    "ta2_id": ta2_id, "level": ta2_level, "polys": o.get("polygons", 0),
                    "parents": " > ".join(parents),
                })
        nodes.append({
            "name": name,
            "clean": clean,
            "system": system_of(members),
            "paths": sorted(set(paths)),
            "parents": parents,
            "vertices": o.get("vertices", 0),
            "polygons": o.get("polygons", 0),
            "hidden": {"viewport": bool(o.get("hide_viewport")),
                       "render": bool(o.get("hide_render"))},
            "manifest_id": mid,
            "match_level": m.level if m else None,
            "match_term": m.term if m else None,
            "ta2_id": ta2_id,
            "ta2_level": ta2_level,
        })

    joined = sum(1 for n in nodes if n["manifest_id"])
    return {
        "source": "z-anatomy",
        "kind": "scene-hierarchy",
        "version": 1,
        "stats": {
            "collections": len(cols),
            "objects": len(objs),
            "resolved": resolved,
            "unresolved": unresolved,
            "manifest_join": joined,
            "parents_filled": parents_filled,
            "manifest_nodes": len(join_index),
            "match_levels": dict(level_count),
            "ta2_candidates": len(candidates),
        },
        "nodes": nodes,
        "ta2_candidates": candidates,
    }


def selfcheck() -> int:
    """能红能绿：构造最小合法 + 三类注入坏数据，断言校验生效。"""
    ok = True

    def check(label, cond):
        nonlocal ok
        print(("  [OK] " if cond else "  [FAIL] ") + label)
        ok = ok and cond

    good = {
        "collections": [
            {"name": "1: Skeletal system", "path": "1: Skeletal system"},
            {"name": "Skull", "path": "Bonus collection/Skeletal/Skull"},
        ],
        "objects": [{"name": " Frontal bone.l", "collections": ["1: Skeletal system", "Skull"],
                     "vertices": 10, "polygons": 12, "hide_viewport": False, "hide_render": True}],
    }
    man = {"systems": [{"name": "skeletal", "structures": [
        {"id": "TA2:1:skeletal:frontal_bone", "mesh": {"node": "Frontal bone"}}]}]}
    h = build_hierarchy(good, man)
    check("合法输入产出 1 节点", len(h["nodes"]) == 1)
    check("后缀清洗 .l 剥离", h["nodes"][0]["clean"] == "Frontal bone")
    check("系统识别", h["nodes"][0]["system"] == "1: Skeletal system")
    check("父链取最长路径", h["nodes"][0]["parents"] == ["Bonus collection", "Skeletal", "Skull"])
    check("manifest join 命中", h["nodes"][0]["manifest_id"] == "TA2:1:skeletal:frontal_bone")
    check("stats 计数", h["stats"]["objects"] == 1 and h["stats"]["resolved"] == 2)

    # 红：集合缺 path
    try:
        build_hierarchy({"collections": [{"name": "X"}], "objects": []}, None)
        check("坏数据-集合缺path 被抓", False)
    except ValueError:
        check("坏数据-集合缺path 被抓", True)
    # 红：对象缺 name
    try:
        build_hierarchy({"collections": [], "objects": [{"polygons": 1}]}, None)
        check("坏数据-对象缺name 被抓", False)
    except ValueError:
        check("坏数据-对象缺name 被抓", True)
    # 红：join 全失败时 stats 如实为 0（不冒充命中）
    h2 = build_hierarchy(good, {"systems": []})
    check("join 全失败 stats=0", h2["stats"]["manifest_join"] == 0)

    print("[selfcheck] %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Z-Anatomy 场景清单 → 层级索引（旁路，不改 manifest）")
    ap.add_argument("--inspect", default="data/scene_inspect.json")
    ap.add_argument("--manifest", default="assets/anatomy.manifest.json")
    ap.add_argument("--ta2", default="vendor-ref/TA2.csv",
                    help="TA2 全表（对 manifest 未命中对象做概念级匹配，产出增量候选）")
    ap.add_argument("--candidates", default="data/scene_ta2_candidates.csv")
    ap.add_argument("--out", default="data/scene_hierarchy.json")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

    try:
        insp = json.load(open(args.inspect, encoding="utf-8"))
    except OSError as e:
        print("[FAIL] 读不到 inspect: %s" % e)
        return 2
    man = None
    try:
        man = json.load(open(args.manifest, encoding="utf-8"))
    except OSError:
        print("[WARN] 读不到 manifest，跳过 join 标注（层级索引仍生成）")
    ta2_pairs = None
    try:
        ta2_pairs = load_ta2_pairs(args.ta2)
        print("[INFO] TA2 全表 %d 条" % len(ta2_pairs))
    except OSError as e:
        print("[WARN] 读不到 TA2 全表，跳过概念级匹配: %s" % e)

    h = build_hierarchy(insp, man, ta2_pairs)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)
    st = h["stats"]
    print("[OK] 已生成 %s" % args.out)
    print("[STATS] collections=%d objects=%d resolved=%d unresolved=%d "
          "manifest_join=%d/%d parents_filled=%d ta2_candidates=%d"
          % (st["collections"], st["objects"], st["resolved"], st["unresolved"],
             st["manifest_join"], st["objects"], st["parents_filled"], st["ta2_candidates"]))
    if st.get("match_levels"):
        print("[STATS] join_levels=%s" % st["match_levels"])

    if h.get("ta2_candidates"):
        import csv as _csv
        with open(args.candidates, "w", encoding="utf-8-sig", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=["clean", "system", "ta2_id", "level", "polys", "parents"])
            w.writeheader()
            w.writerows(h["ta2_candidates"])
        print("[OK] 结构增量候选 %d 条 → %s" % (len(h["ta2_candidates"]), args.candidates))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
