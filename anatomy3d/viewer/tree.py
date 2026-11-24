# -*- coding: utf-8 -*-
"""结构树 —— scene_hierarchy.json 父链 → 可折叠文本树（headless 可测，无 pyglet 依赖）。

数据源：``data/scene_hierarchy.json``（import_inspect.py 产物，parents 填充 4566/4569）。
树的分支 = part-of 路径上的集合名，叶子 = 网格对象（clean 名）。

交互约定（app.py 接线）：
  · T 键开关树面板（HUD 多行性能面板复用，右上角向下堆叠）；
  · 上下方向键移动游标，Enter 定位（app 侧拿到叶子名后 _build + 高亮）；
  · 行数恒定 = viewport 行数，set_perf 不因内容变化重排。

设计纪律：纯数据层不 import pyglet —— ``--smoke``/单测无 GL 上下文可跑（P12 同款）。
"""
from __future__ import annotations

import json
import os

# inspect 顶层集合 → assets GLB 系统名（1-9 键确定性清单的对应关系）
SYSTEM_MAP = {
    "1: Skeletal system": "skeletal",
    "2: Muscular insertions": "muscular-insertions",
    "3: Joints": "arthrology",
    "4: Muscular system": "muscular",
    "5: Cardiovascular system": "cardiovascular",
    "6: Lymphoid organs": "visceral",
    "7: Nervous system & Sense organs": "nervous",
    "8: Visceral systems": "visceral",
    "9: Regions of human body": "regions",
}


class _TreeNode:
    __slots__ = ("name", "children", "leaf")

    def __init__(self, name: str, leaf: str | None = None):
        self.name = name            # 分支显示名 / 叶子 clean 名
        self.leaf = leaf            # 叶子挂载的对象名（GLB node 名），分支为 None
        self.children: list[_TreeNode] = []

    def child(self, name: str) -> "_TreeNode | None":
        for c in self.children:
            if c.name == name and c.leaf is None:
                return c
        return None


class StructureTree:
    """一棵按当前系统过滤的 part-of 树 + 游标状态。"""

    def __init__(self, hierarchy: dict, system: str | None = None):
        self.root = _TreeNode(system or "(all)")
        self.cursor = 0
        self._rows: list[tuple[_TreeNode, int, bool]] = []   # (node, depth, cursor_on)
        self._insert_nodes(hierarchy, system)

    # ---------- 构建 ----------

    def _insert_nodes(self, hierarchy: dict, system: str | None) -> None:
        """把 system 过滤后的对象按 parents 链插入树；重复对象名去重。"""
        seen: set[str] = set()
        for n in hierarchy.get("nodes", []):
            if system is not None:
                sys_key = SYSTEM_MAP.get(n.get("system") or "")
                if sys_key != system:
                    continue
            name = n.get("clean") or n.get("name") or ""
            if not name or name in seen:
                continue
            seen.add(name)
            parents = n.get("parents") or []
            # 剥掉首段的仓库级根（"Bonus collection"），从语义层开始建链
            chain = [p for p in parents if p != "Bonus collection"]
            node = self.root
            for seg in chain:
                c = node.child(seg)
                if c is None:
                    c = _TreeNode(seg)
                    node.children.append(c)
                node = c
            node.children.append(_TreeNode(name, leaf=name))

    @classmethod
    def load(cls, repo: str, system: str | None = None) -> "StructureTree | None":
        """从仓内 data/scene_hierarchy.json 加载；缺文件返回 None（查看器自行降级）。"""
        path = os.path.join(repo, "data", "scene_hierarchy.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            hierarchy = json.load(f)
        return cls(hierarchy, system)

    # ---------- 渲染与导航 ----------

    def render(self, max_rows: int = 14, default_depth: int = 2) -> list[str]:
        """返回至多 max_rows 行的树文本；以游标行为中心开窗。"""
        rows: list[tuple[_TreeNode, int]] = []

        def walk(node: _TreeNode, depth: int) -> None:
            for c in node.children:
                rows.append((c, depth))
                if depth + 1 < default_depth or c.leaf is not None:
                    pass
                walk(c, depth + 1)

        walk(self.root, 0)
        if not rows:
            self._rows = []
            return ["(empty tree)"]
        # 游标夹取 + 视窗
        self.cursor = max(0, min(self.cursor, len(rows) - 1))
        start = max(0, min(self.cursor - max_rows // 2, len(rows) - max_rows))
        window = rows[start:start + max_rows]
        self._rows = list(window)
        lines = []
        for i, (node, depth) in enumerate(window):
            mark = ">" if (start + i) == self.cursor else " "
            prefix = "  " * depth + ("• " if node.leaf else "+ ")
            lines.append(f"{mark}{prefix}{node.name}")
        return lines

    def move(self, delta: int) -> None:
        total = max(1, len(self._rows) or 1)
        self.cursor = max(0, self.cursor + delta)
        _ = total   # render 时再夹取真实长度

    def selected_leaf(self) -> str | None:
        """游标行若是叶子，返回对象名（供 app 定位构建）；分支行返回 None。"""
        if 0 <= self.cursor < len(self._rows):
            node = self._rows[self.cursor][0]
            return node.leaf
        return None

    def leaf_names(self) -> list[str]:
        """树内全部叶子对象名（headless 断言 / app 侧过滤用）。"""
        out: list[str] = []

        def walk(n: _TreeNode) -> None:
            if n.leaf is not None:
                out.append(n.leaf)
            for c in n.children:
                walk(c)

        walk(self.root)
        return out


def selfcheck() -> bool:
    """能红能绿：构建/过滤/渲染/导航全链路断言。"""
    ok = True

    def check(label, cond):
        nonlocal ok
        print(("  [OK] " if cond else "  [FAIL] ") + label)
        ok = ok and cond

    h = {"nodes": [
        {"clean": "Femur", "system": "1: Skeletal system",
         "parents": ["Bonus collection", "Skeletal", "Lower limb"]},
        {"clean": "Femur", "system": "9: Regions of human body",
         "parents": ["Bonus collection", "Regions", "Thigh"]},   # 跨系统重复 → 过滤后去重
        {"clean": "Heart", "system": "5: Cardiovascular system",
         "parents": ["Bonus collection", "Cardiovascular", "Thorax"]},
        {"clean": "Orphan object", "system": "1: Skeletal system", "parents": []},
    ]}
    t = StructureTree(h, "skeletal")
    leaves = t.leaf_names()
    check("按系统过滤（femur 收、heart 不收）",
          "Femur" in leaves and "Heart" not in leaves)
    check("跨系统重复去重", leaves.count("Femur") == 1)
    check("无父链对象挂根", "Orphan object" in leaves)
    lines = t.render(max_rows=10)
    check("渲染产行", any("Femur" in x for x in lines) and any("Lower limb" in x for x in lines))
    check("游标标记", lines[0].startswith(">"))
    t.move(1)
    lines2 = t.render(max_rows=10)
    check("移动游标", lines2[1].startswith(">"))
    t.cursor = 0
    t.render(max_rows=10)
    check("分支行 selected_leaf=None", t.selected_leaf() is None)
    # 把游标移到 Femur 叶子行再取
    for i in range(len(t._rows) + 2):
        t.render(max_rows=10)
        if t.selected_leaf() == "Femur":
            break
        t.move(1)
    check("叶子行取对象名", t.selected_leaf() == "Femur")
    missing = StructureTree({"nodes": []}, None)
    check("空树渲染不炸", missing.render() == ["(empty tree)"])
    print("[tree selfcheck] %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if selfcheck() else 1)
