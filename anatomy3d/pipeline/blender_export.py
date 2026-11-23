# -*- coding: utf-8 -*-
"""Blender 无头导出管线（M1 骨架）。

定位
----
把 Z-Anatomy（Blender 应用模板）转成「按系统拆分的 GLB + structure manifest」。
本模块当前只落**参数形状与流程编排**，真正调用 Blender 的执行体在 M1 里程碑
实装（需要 Blender 4.x 可执行文件，非 pip 依赖）。

流程（对齐社区先例 Anatria-3D 验证过的路径）::

    1. staging：把源 .blend 载入干净临时场景烘焙（原场景带 driver 网络与
       依赖环，直导会在 glTF 导出器内 IndexError —— 见 tools/pipeline/README.md 坑点①）
    2. curves → mesh：脉管树是 bevelled 曲线，按 MESH 收集会静默丢掉整棵血管树（坑点②）
    3. 按系统 collection 拆分导出 GLB（选择是按 collection 不是按对象名，
       collection 层级即解剖层级，手抄对象名清单会漂移）
    4. 产出 manifest：节点名（TA2 英文术语）→ join TA2.csv 得三语名
       （约 9% 对象不在 TA2，须过滤而非裸发 —— 坑点④）
    5. gltf-transform：dedup / weld / draco 压缩（可选，M1 后期）

Windows 注意（坑点③）：Blender 安装路径与工程路径要短，
glTF 插件在 MAX_PATH 260 字符下会以误导性 ImportError 假死。
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field


@dataclass
class ExportJob:
    """一次导出任务的全部参数（M1 实装时的输入契约）。"""

    blend_path: str                    # Z-Anatomy Startup.blend 或模板 zip 内路径
    blender_exe: str | None = None     # 默认取 PATH 里的 blender
    out_dir: str = "assets"            # GLB 与 manifest 产出目录
    systems: list[str] = field(default_factory=list)   # 空列表 = 全部系统
    draco: bool = False                # M1 后期启用（viewer 侧需同步支持解码）

    def resolve_blender(self) -> str | None:
        """定位 Blender 可执行文件；找不到返回 None（不猜路径、不写死盘符）。"""
        if self.blender_exe and shutil.which(self.blender_exe):
            return self.blender_exe
        return shutil.which("blender")

    def command_preview(self) -> list[str]:
        """生成 M1 实装后将执行的命令行预览（当前阶段用于人工核对参数形状）。"""
        blender = self.resolve_blender() or "<blender-not-found>"
        return [
            blender,
            "--background",
            self.blend_path,
            "--python", "tools/pipeline/blender_export.py",
            "--out", self.out_dir,
            "--systems", ",".join(self.systems) or "<all>",
        ]


def check_pipeline_prereqs(job: ExportJob) -> list[str]:
    """前置检查：返回问题清单（空 = 可跑）。M1 实装时作为执行闸门。"""
    problems: list[str] = []
    if not job.resolve_blender():
        problems.append("未在 PATH 找到 blender 可执行文件（Blender 4.x 未安装或未暴露）")
    import os

    if not os.path.exists(job.blend_path):
        problems.append(f"源 .blend 不存在: {job.blend_path}")
    return problems
