# -*- coding: utf-8 -*-
"""anatomy3d.cli —— 装配报告入口。

用法::

    python -m anatomy3d.cli --report
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .knowledge.ta2 import load_ta2_index

# 模块就位状态：框架底座阶段如实声明「骨架已就位 / 实装待里程碑」，
# 不虚报。viewer 的真实现（GLB 加载 / 拾取 / OIT）由 M2 里程碑落地。
MODULES = [
    ("contracts", "structure-manifest v1 形状与校验", True),
    ("pipeline", "Blender 无头导出管线（参数与流程占位）", True),
    ("viewer", "GLB 加载 / 拾取 / OIT / 标注（M2 实装）", False),
    ("knowledge", "TA2 三语术语索引（样例数据已通）", True),
]


def build_report() -> str:
    lines = [
        f"anatomy3d {__version__} 装配报告",
        "",
    ]
    for name, desc, ready in MODULES:
        flag = "READY" if ready else "SKELETON"
        lines.append(f"  [{flag:>8}] {name:<10} {desc}")
    # 样例术语索引冒烟：能加载即算就位
    idx = load_ta2_index()
    lines.append("")
    lines.append(f"  TA2 样例索引: {len(idx)} 条（data/ta2_sample.csv）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="anatomy3d")
    parser.add_argument("--report", action="store_true", help="打印装配报告")
    args = parser.parse_args(argv)
    if args.report:
        print(build_report())
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
