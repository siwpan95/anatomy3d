# CHANGELOG

本仓遵循「用户可见变更逐条记录」；格式参照 Keep a Changelog 精神（简化版）。

## [0.3.0] - 2026-11-23

### Added
- M1 完成：9 系统 GLB 全量导出（约 702MB，gitignore 不入库）
  + 9 份系统 manifest + 全图谱合并清单 `assets/anatomy.manifest.json`（5954 结构、契约 PASS）
- `tools/pipeline/merge_manifests.py`：多系统清单合并（幂等、跳过自身输出）

### Changed
- manifest id 改为复合键 `TA2:<id>:<system>:<node-slug>`（修复跨系统概念重复误删，P13）

### Fixed
- P12-P15 问题流水（M2 build_scene 性能红线 / 复合 id / 合并自引用 / FONT-only 系统）

## [0.2.0] - 2026-11-23

### Added
- M1 资产管线首期落地（心血管系统）：
  - `tools/pipeline/blender_export.py` 实装：inspect 模式（collection 树 dump）+
    导出模式（staging 烘焙 / 曲线转网格 / FONT 排除 / 材质剥离 / 移除原场景防全文件导出）
  - `tools/pipeline/build_manifest.py`：导出报告 → structure-manifest v1（TA2 join、
    后缀清洗、变体去重、剔除项留档）
  - 心血管系统产物：`assets/cardiovascular.glb`（1092 对象 / 356 万三角形，不入库）
    + `assets/cardiovascular.manifest.json`（402 结构、契约校验 PASS）
  - `vendor-ref/`：TA2.csv（Z-Anatomy，CC BY-SA 4.0）、Anatria-3D 先例参考
    （inspect.json / audit 报告），本仓实测 inspect_zanatomy.json 与导出报告

### Fixed
- P8-P11 问题流水（见 docs/问题记录.md）：全文件导出失控、FONT 排除、
  TA2.csv 格式解析、网络获取路径沉淀

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
