# -*- coding: utf-8 -*-
"""3dworld 引擎桥接（M2 实装）。

设计约束：3dworld 是独立仓（组合流水线纪律「桥接独占跨仓导入」），本仓
不 vendor、不 fork 它的引擎层，而是通过声明对接面（下方 Protocol）+
运行期可选注入（`ANATOMY3D_TDWORLD_SRC` 环境变量指路）复用。

为什么当前是 Protocol 而不是 import：M0 阶段不引入 pyglet 依赖链，
selfcheck 必须无头可跑；M2 落地时按此接口实装，契约面先冻结防止
实现期接口漂移。
"""
from __future__ import annotations

import os
from typing import Protocol


class AnatomyViewer(Protocol):
    """查看器对接面（M2 实现目标形状）。"""

    def load_system(self, glb_path: str) -> int:
        """加载一个系统的 GLB，返回结构节点数。"""
        ...

    def pick(self, x: int, y: int) -> str | None:
        """屏幕坐标拾取，返回命中的 structure id（未命中 None）。"""
        ...

    def set_visibility(self, structure_id: str, visible: bool) -> None:
        """结构级显隐。"""
        ...

    def set_opacity(self, structure_id: str, opacity: float) -> None:
        """结构级透明度（OIT 管线）。"""
        ...

    def set_clip_plane(self, normal: tuple[float, float, float], offset: float) -> None:
        """单平面剖面裁剪（M4：shader clip plane）。"""
        ...


def resolve_tdworld_src() -> str | None:
    """定位 3dworld 源码（不写死盘符，铁律 5）。

    优先级：环境变量 ``ANATOMY3D_TDWORLD_SRC`` → 与本仓并排的 ``../3dworld``。
    找不到返回 None（调用方如实报错，不猜路径）。
    """
    override = os.environ.get("ANATOMY3D_TDWORLD_SRC")
    if override and os.path.isdir(override):
        return override
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sibling = os.path.join(os.path.dirname(repo_root), "3dworld")
    if os.path.isdir(sibling):
        return sibling
    return None
