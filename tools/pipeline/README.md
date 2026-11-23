# Blender 导出管线操作手册（M1 实装依据）

> 本手册把社区先例**已验证**的坑点固化为执行闸门清单。M1 实装时逐条对照，
> 踩到清单外的新坑回填 docs/问题记录.md 并同步本文件。

## 管线总路径（先例：Anatria-3D，实测数字）

```
Z-Anatomy（Blender 应用模板，CC BY-SA 4.0）
   → Blender --background 无头导出（staging 场景烘焙）
   → 按系统拆分 .glb（男性图谱 13 个系统 / 3478 结构 / 8.6M 三角形 / 37MB；
                      女性躯干 7 个文件 / 264 结构 / 5.3MB）
   → manifest join（节点名 = TA2 英文术语 → join TA2.csv 得三语名）
   → gltf-transform：dedup / weld / draco（可选）
```

## 坑点清单（执行前逐条核对）

| # | 坑 | 后果 | 处置 |
|---|---|---|---|
| ① | 原场景带 driver 网络 + 依赖环，直接导出在 glTF gatherer 内 `IndexError` | 导出崩溃 | 必须经**干净 staging 场景**逐对象烘焙为 evaluated mesh（材质丢弃，viewer 自行着色） |
| ② | 整棵脉管树是 **bevelled curves** 不是 mesh | 按 `type=="MESH"` 收集**静默丢掉全部血管**，心腔悬空 | 收集时显式转换曲线几何；导出后按结构数对账 |
| ③ | Windows 260 字符 MAX_PATH | Blender glTF 插件以误导性 `ImportError` 假死 | Blender 与工程路径都放短路径；前置检查覆盖 |
| ④ | 约 9% 导出对象（先例实测 404/4349）不在 TA2（变体命名 + 脚手架几何） | 裸发会产生无术语结构 | 过滤策略：变体对象保留但 `ta2_id` 置空并标记；脚手架几何剔除 |
| ⑤ | 节点名 sanitize（`Right atrium` → `Right_atrium`） | 按原名查找全部落空 | manifest 的 `mesh.node` 写 sanitize 后形态；viewer 双形态查找 |

## 结构选择原则

- **按 collection 选择，不按对象名清单**：Z-Anatomy 的 collection 层级即解剖层级，
  手抄对象名清单必然与源漂移。
- 每系统导出后立即产出该系统 manifest 分片并跑 `validate_manifest`，不等全量。

## 与本仓代码的对接

- 参数形状：`anatomy3d/pipeline/blender_export.py` 的 `ExportJob`
- 前置闸门：`check_pipeline_prereqs()`（Blender 在位 / 源文件在位）
- 契约：`docs/契约/structure-manifest-v1.md`

## 完整命令序列（M1 已实跑）

```bash
# 0. 源文件：Z-Anatomy.zip（86.7MB）内含 Startup.blend（306.8MB），解压到 assets/raw/
#    国内网络：小文件 jsDelivr，大文件 gh-proxy.com + Range 分块并行（见 docs/问题记录.md P11）

# 1. 结构摸底（1945 collections / 4569 几何对象）
blender --background assets/raw/Z-Anatomy/Startup.blend \
  --python tools/pipeline/blender_export.py -- --inspect --out vendor-ref/inspect_zanatomy.json

# 2. 逐系统导出（示例：心血管；系统路径取自 inspect 的 "Bonus collection/..." 子树）
blender --background assets/raw/Z-Anatomy/Startup.blend \
  --python tools/pipeline/blender_export.py -- \
  --collection "Bonus collection/Cardiovascular system" \
  --out assets/cardiovascular.glb --report vendor-ref/cardiovascular_report.json

# 3. 导出报告 → 系统 manifest（TA2 join + 后缀清洗 + 契约校验）
PYTHONPATH=. python tools/pipeline/build_manifest.py \
  --report vendor-ref/cardiovascular_report.json --ta2 vendor-ref/TA2.csv \
  --system cardiovascular --out assets/cardiovascular.manifest.json

# 4. 合并全图谱（幂等，跳过上次输出）
PYTHONPATH=. python tools/pipeline/merge_manifests.py
```

**实装后新增的两个坑**（详见 docs/问题记录.md P8）：
- `new_from_object` 继承材质节点树 → glTF gatherer 断链 IndexError ⇒ `export_materials="NONE"`（枚举名实测）；
- 不删原场景会让导出器把整文件导进去（17 对象导出 3407 mesh）⇒ 烘焙后 `bpy.data.scenes.remove` 原场景。

## 数据署名

导出产物（GLB + manifest）沿上游 CC BY-SA，分发时随包 NOTICE —— 见根 NOTICE。
