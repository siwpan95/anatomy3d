# 契约：structure-manifest v1

> 状态：冻结（v1）· 契约版本独立于任何模块发版 · 实现见 `anatomy3d/contracts/manifest.py`

## 1. 用途

资产管线（M1）产出、查看器（M2）与知识层（M3）消费的**结构清单**对接面：
描述每个解剖结构「叫什么（三语名）· 是什么（类型）· 画在哪（GLB + 节点名）· 归属谁（part-of 链）」。

## 2. 形状

```json
{
  "manifest_version": 1,
  "source": "z-anatomy",
  "systems": [
    {
      "name": "cardiovascular",
      "label": {"la": "Systema cardiovasculare", "en": "Cardiovascular system", "zh": "心血管系统"},
      "structures": [
        {
          "id": "FMA7128",
          "ta2_id": "A12.1.00.001",
          "names": {"en": "Heart", "la": "Cor", "zh": "心"},
          "kind": "organ",
          "mesh": {"glb": "cardiovascular.glb", "node": "Heart"},
          "parents": []
        }
      ]
    }
  ]
}
```

## 3. 字段规则

| 字段 | 必填 | 规则 |
|---|---|---|
| `manifest_version` | ✅ | 恒为 `1`；升级即新契约版本，消费方按区间声明兼容 |
| `source` | ✅ | 数据源标识（`z-anatomy` / `bodyparts3d` / `custom`） |
| `systems[].name` | ✅ | 系统标识（ASCII，GLB 文件名基座） |
| `structures[].id` | ✅ | 全清单唯一（建议 FMA 概念 ID）；重复即校验失败 |
| `names.en` | ✅ | TA2 英文术语（与 Z-Anatomy 节点名 join 的主键） |
| `names.la` / `names.zh` | ⬜ | 渐进补齐；`zh` 来自《人体解剖学名词》人工映射 |
| `kind` | ✅ | 封闭枚举：`bone / muscle / vessel / nerve / organ / region / other`；新增类型 = 契约 v2 |
| `mesh.glb` + `mesh.node` | ✅ | GLB 相对路径 + 节点名（Z-Anatomy 导出后需 sanitize 兼容，如 `Right atrium` → `Right_atrium`，viewer 查找两种形态） |
| `parents[]` | ⬜ | part-of 链；清单内悬空引用会被校验报告（允许，因支持跨文件增量） |

## 4. 校验策略

- **结构层硬失败**：版本不对直接终止（后续字段语义未定义）；`id` 重复、`names.en` 缺失、`kind` 非枚举、`mesh` 缺失。
- **引用层软收集**：`parents` 悬空逐条报告不阻断 —— 支持分系统增量产出（先生成心血管，再生成骨骼，跨文件 join）。

## 5. 兼容性声明方式

消费方声明 `SUPPORTED_MANIFEST_VERSIONS`（如 `(1,)` 或区间），加载时校验；契约升级（v2）只允许**加字段**，禁止改既有字段语义 —— 加字段对 v1 消费方天然向后兼容。
