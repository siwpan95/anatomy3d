# anatomy3d —— 开放数据人体解剖 3D 教育查看器

> **定位**：基于开放解剖数据（Z-Anatomy / BodyParts3D）+ 自研 pyglet 查看器的独立人体解剖教育程序。
> **边界**：教学用途，**非临床**；模型数据来自开放数据源，精度与覆盖以数据源为准。
> **许可**：代码 MIT；解剖模型数据（后续引入）沿上游 **CC BY-SA**，双轨授权见 [NOTICE](NOTICE) 与 [docs/项目书.md](docs/项目书.md) §许可合规。

## 是什么

一个离线可运行的 3D 人体解剖查看器：

- **看**：按系统（骨骼 / 肌肉 / 血管 / 神经 / 内脏…）加载解剖模型，旋转 / 缩放 / 点击选中；
- **剥**：结构级显示 / 隐藏 / 隔离 / 半透明（OIT 顺序无关透明），支持单平面剖面裁剪；
- **学**：结构标注（拉丁 / 英文 / 中文三语术语，源自 TA2），定义与肌肉起止点，quiz 学习模式。

技术底座继承既有三仓流水线经验（世界生成 / 规则内核 / 表现渲染的分工范式）：
本仓对应「资产管线 + 查看器 + 知识内核」的一体化独立应用。

## 怎么跑（当前阶段：框架底座）

```bash
# 依赖以 pyproject.toml 为单一事实来源；当前骨架仅依赖 Python 标准库（≥3.11）
python selfcheck.py          # 无头自检：契约校验 + 模块导入 + 样例术语索引
python -m anatomy3d.cli --report   # 装配报告：各模块就位状态
python -m unittest discover -s tests   # 单元测试

# M2 查看器（需带 pyglet 的 3dworld 仓内 venv；3dworld 源码经 ANATOMY3D_TDWORLD_SRC
# 或并排目录自动注入，不 vendor 不 fork）
python -m anatomy3d.viewer.app --system reference --smoke 3
python -m anatomy3d.viewer.app --system cardiovascular --max-nodes 12 --shot
# 交互：拖拽=旋转 滚轮=缩放 点击=选中/答题 I=隔离 A=全显 L=增量加载 H=隐藏
#       C=剖面开关 [ ]=旋转剖面 - =移动剖面 Q=出题  ESC=退出
# M3 重新生成三语清单：
python -m anatomy3d.knowledge.zh && python tools/pipeline/build_zh_index.py
```

## 依赖

| 阶段 | 依赖 | 说明 |
|---|---|---|
| 框架底座（现在） | 仅 Python 标准库 | selfcheck / cli / 契约校验全部可无头跑 |
| M1 资产管线 | Blender 4.x（外部工具，非 pip） | 无头导出 GLB + manifest |
| M2 查看器 | pyglet==2.1.16 | 沿用既有 3dworld 引擎锁版口径 |

## 门禁怎么跑

```bash
python selfcheck.py          # exit 0 = 通过
python -m unittest discover -s tests

# 场景层级数据导入（旁路，不改 manifest）：inspect.json → hierarchy.json
python tools/pipeline/import_inspect.py --selfcheck   # 导入器能红能绿自检
python tools/pipeline/import_inspect.py               # 生成 data/scene_hierarchy.json
```

### 场景层级数据源

`data/scene_inspect.json` 是 Z-Anatomy `Startup.blend` 的全量**元数据**清单（1944 集合 /
4569 网格对象，含顶点/面数与集合成员），由 Blender 无头 inspect 产出；`data/scene_hierarchy.json`
是导入器产出的层级索引（对象 → 系统 / part-of 父链 / 几何量 / manifest join）。二者是
manifest 的**旁路数据**，不改动冻结的契约 v1；`parents` 字段可作为知识层/结构树的增量来源。
重建命令与统计口径见 `tools/pipeline/import_inspect.py` 文件头。

## 里程碑

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | 框架底座：契约 v1 + 目录骨架 + selfcheck | ✅ 本仓首发 |
| M1 | 资产管线：Blender 无头导出 GLB + manifest（规避已知坑点，见 tools/pipeline/README.md） | ✅ 9 系统全部导出（约 702MB GLB，不入库）+ 全图谱 manifest 5954 结构、契约 PASS；M2 性能红线已实测（P12） |
| M2 | 查看器：加载 / 拾取 / 显隐 / OIT / 标注 / 结构树 | ◐ 骨架已通：pyglet 查看器 + 按节点懒加载（心血管 8/1092 节点 4.8s 启动）+ 轨道相机/自动取景/点选/显隐/隔离/增量加载；bench 20 draw calls、截图可见颅骨与血管树；OIT/中文标注待 M3/M4 |
| M3 | 知识层：定义 + 三语索引 + 中文术语映射 | ✅ 5954 结构富化（中文 2547 / 拉丁 5954 / 释义 39），契约 PASS；中文源为 4 万行医学名词表 + 25 条自撰基础词与释义 |
| M4 | 剖面裁剪 + quiz 学习模式 | ✅ 运行时 PBR shader 裁剪平面（C/[ ]/-/= 交互，截图证明半切）+ quiz 点选判分（Q 键，中文+拉丁题干）；pyglet 2 uniform 写入坑见 P19 |

## 文档

- [docs/项目书.md](docs/项目书.md) —— 完整项目书（背景调研 / 可行性 / 目标范围 / 风险 / 许可合规）
- [docs/契约/structure-manifest-v1.md](docs/契约/structure-manifest-v1.md) —— 结构清单契约 v1
- [docs/问题记录.md](docs/问题记录.md) —— 期间问题与解法流水（完工后反哺治理仓）
- [tools/pipeline/README.md](tools/pipeline/README.md) —— Blender 导出操作手册（含社区先例坑点清单）

## 署名（数据引入后生效）

解剖模型数据的署名与许可声明统一写在 [NOTICE](NOTICE)；在数据真正入库前，该文件仅登记计划引入的数据源与各自许可，避免「先引入后补署名」的合规空窗。

## 许可

代码以 MIT 许可发布（见 [LICENSE](LICENSE)）。解剖模型数据的许可边界与署名要求见 [NOTICE](NOTICE)。
