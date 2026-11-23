# CHANGELOG

本仓遵循「用户可见变更逐条记录」；格式参照 Keep a Changelog 精神（简化版）。

## [0.1.0] - 2026-11-23

### Added
- M0 框架底座首发：
  - `structure-manifest v1` 契约（零依赖校验器 + 契约文档）
  - `anatomy3d` 包骨架：`contracts` / `pipeline`（Blender 导出参数与前置闸门）/
    `viewer`（3dworld 对接面 Protocol）/ `knowledge`（TA2 三语索引）
  - `selfcheck.py` 无头自检（契约红绿双向 + 知识/管线冒烟 + 装配报告）
  - 单元测试 `tests/test_manifest.py`
  - 项目书（docs/项目书.md）、问题记录（docs/问题记录.md）、管线操作手册（tools/pipeline/README.md）
  - 建仓三件套（README / LICENSE-MIT / .gitignore）+ NOTICE（数据双轨授权声明）
