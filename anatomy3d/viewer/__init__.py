# -*- coding: utf-8 -*-
"""anatomy3d.viewer —— 查看器层。

- :class:`LazyAtlas`：headless 可测的「节点选择 + 结构映射」核心（P12 性能闸门）
- ``anatomy3d.viewer.app``：pyglet 查看器入口，只在运行时导入 3dworld

``app`` 故意不在此 __init__ 里导入——它需要 pyglet + GL 上下文，
selfcheck 必须在无 GL 环境下可跑。

能力对照（3dworld 引擎既有件 → 本仓用途）::

    engine/gltf.py   glTF 2.0/GLB 全支持     -> 解剖模型加载（按节点懒构建）
    engine/picking.py 屏幕射线 -> 求交        -> 器官点选
    engine/oit.py    Weighted Blended OIT    -> 器官半透明透视（后续里程碑）
    engine/fonts.py  CJK 字体解析            -> 中文标注（后续里程碑）
    engine/hud.py    HUD/labels              -> 结构标签
"""
from .lazy import LazyAtlas, gltf_name_alias, sanitize_node

__all__ = ["LazyAtlas", "gltf_name_alias", "sanitize_node"]
