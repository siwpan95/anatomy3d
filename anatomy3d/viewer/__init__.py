# -*- coding: utf-8 -*-
"""anatomy3d.viewer —— 查看器层（M2 实装：GLB 加载 / 拾取 / 显隐 / OIT / 标注）。

当前仅声明与既有 3dworld 引擎能力的对接面（骨架），实现随 M2 里程碑落地。
能力对照（3dworld 引擎既有件 → 本仓用途）::

    engine/gltf.py   glTF 2.0/GLB 全支持          -> 解剖模型加载
    engine/picking.py 屏幕射线 -> AABB/三角形求交 -> 器官点选
    engine/oit.py    Weighted Blended OIT         -> 器官半透明透视（剥皮式）
    engine/fonts.py  CJK 字体解析                 -> 中文标注
    engine/hud.py    HUD/labels                   -> 结构标签
"""
