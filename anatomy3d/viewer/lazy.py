# -*- coding: utf-8 -*-
"""anatomy3d.viewer.lazy —— 按节点懒加载的纯逻辑层（headless 可测）。

为什么需要它（问题记录 P12）：3dworld ``GLTF.build_scene()`` 内部 ``meshes()``
会为**全部** 1092 个节点构建 MeshData（356 万三角形 → 实测 21 分钟未完成）。
正确姿势是只对待显示节点调用 ``primitive_meshdata(primitive)``。

本模块不 import pyglet / world3d：只处理「显示哪些节点、节点对应哪个结构」，
可在无 GL 环境下单测；真正的 GPU 构建在 viewer/app.py。
"""
from __future__ import annotations

import re


def sanitize_node(name: str) -> str:
    """glTF 节点名 sanitize 形态：空格→下划线（先例 P8⑤双形态查找）。"""
    return re.sub(r"\s+", "_", name.strip())


def gltf_name_alias(name: str) -> str:
    """去掉 Blender glTF 导出器给重名节点追加的 ``.001`` 后缀（P17）。"""
    return re.sub(r"\.\d{3}$", "", str(name).strip())


class LazyAtlas:
    """glTF 文档 + structure-manifest 的懒加载视图。"""

    def __init__(self, gltf_json: dict, manifest: dict | None = None,
                 budget: int = 64):
        self.json = gltf_json
        self.manifest = manifest or {}
        self.budget = max(1, int(budget))
        self.nodes = self.json.get("nodes", [])
        # 只索引「有 mesh 的节点」——无 mesh 的分组节点不需要构建
        self.mesh_nodes = [
            (i, n.get("name", f"node_{i}"))
            for i, n in enumerate(self.nodes) if "mesh" in n
        ]
        self._built: set[int] = set()
        self._name_to_index = {}
        for i, name in self.mesh_nodes:
            self._name_to_index[name] = i
            san = sanitize_node(name)
            if san != name:
                self._name_to_index[san] = i
            alias = gltf_name_alias(name)
            if alias != name:
                self._name_to_index[alias] = i
                self._name_to_index[sanitize_node(alias)] = i
        self._index_to_structure: dict[int, dict] = {}
        self._build_structure_index()

    def _build_structure_index(self) -> None:
        # structure.mesh.node 可能是原名或 sanitize 形态，两种都认
        for system in self.manifest.get("systems", []):
            for s in system.get("structures", []):
                node = (s.get("mesh") or {}).get("node")
                if not node:
                    continue
                for form in (node, sanitize_node(node)):
                    idx = self._name_to_index.get(form)
                    if idx is not None:
                        self._index_to_structure[idx] = s
                # 结构 id 也允许直接指节点（未来 glTF 节点名可写 id）
                idx = self._name_to_index.get(s.get("id", ""))
                if idx is not None:
                    self._index_to_structure[idx] = s

    def structure_for_node(self, index: int) -> dict | None:
        return self._index_to_structure.get(index)

    def plan(self, names: list[str] | None = None, budget: int | None = None):
        """返回 ``(selected, unmatched, skipped_count)``。

        - ``names`` 给定：按名字选择（支持 sanitize 双形态），未命中的进 ``unmatched``；
        - 未给定：按 GLB 节点顺序取前 budget 个（确定性，便于复现）；
        - ``budget`` 上限硬约束——这是 P12 的核心闸门。
        """
        limit = max(1, int(budget or self.budget))
        selected, unmatched = [], []
        if names:
            seen = set()
            for name in names:
                idx = self._name_to_index.get(name) or self._name_to_index.get(sanitize_node(name))
                if idx is None:
                    unmatched.append(name)
                elif idx not in seen and len(selected) < limit:
                    seen.add(idx)
                    selected.append((idx, self._name_to_index_name(idx)))
            skipped = max(0, len(self._name_to_index) - len(selected))
        else:
            selected = self.mesh_nodes[:limit]
            skipped = max(0, len(self.mesh_nodes) - len(selected))
        return selected, unmatched, skipped

    def _name_to_index_name(self, index: int) -> str:
        return self.nodes[index].get("name", f"node_{index}")

    def mark_built(self, index: int) -> None:
        self._built.add(index)

    def is_built(self, index: int) -> bool:
        return index in self._built

    def built_count(self) -> int:
        return len(self._built)

    def summary(self) -> str:
        return (f"LazyAtlas: mesh_nodes={len(self.mesh_nodes)} "
                f"built={self.built_count()} budget={self.budget} "
                f"manifest_structures={sum(len(s.get('structures', [])) for s in self.manifest.get('systems', []))}")
