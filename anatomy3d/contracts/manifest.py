# -*- coding: utf-8 -*-
"""structure-manifest v1 —— 解剖结构清单契约。

设计对齐组合仓「契约独立版本化」纪律：本契约版本不跟随任何模块发版，
消费方（viewer / knowledge / quiz）按版本区间声明兼容。

形状（详见 docs/契约/structure-manifest-v1.md）::

    {
      "manifest_version": 1,
      "source": "z-anatomy|bodyparts3d|custom",
      "systems": [
        {
          "name": "cardiovascular",
          "label": {"la": "...", "en": "...", "zh": "..."},
          "structures": [
            {
              "id": "FMA7128",
              "ta2_id": "A12.2.01.001",      # TA2 官方编号，可空（待映射）
              "names": {"la": "...", "en": "...", "zh": null},
              "kind": "bone|muscle|vessel|nerve|organ|region|other",
              "mesh": {"glb": "cardiovascular_male.glb", "node": "Right atrium"},
              "parents": ["FMA7088"]          # part-of 链
            }
          ]
        }
      ]
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

MANIFEST_VERSION = 1

# 结构类型封闭枚举：加新类型 = 契约升级（v2），不在 v1 里开放式放宽
KINDS = {"bone", "muscle", "vessel", "nerve", "organ", "region", "other"}

REQUIRED_NAME_LANGS = ("en",)          # en 必备；la 建议有；zh 允许渐进补齐
OPTIONAL_NAME_LANGS = ("la", "zh")


@dataclass
class StructureEntry:
    """单个解剖结构条目（校验后的规范形态）。"""

    id: str
    names: dict[str, str]
    kind: str
    mesh: dict                       # {"glb": ..., "node": ...}
    ta2_id: str | None = None
    parents: list[str] = field(default_factory=list)


def validate_manifest(data: dict) -> list[str]:
    """校验 manifest dict，返回问题清单；空列表 = 通过。

    校验策略：结构层硬失败（版本/必备字段/枚举），引用层软收集
    （parents 悬空、mesh 缺失等逐条报告，便于资产管线增量修复）。
    """
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["manifest 顶层必须是对象"]
    if data.get("manifest_version") != MANIFEST_VERSION:
        problems.append(
            f"manifest_version 必须为 {MANIFEST_VERSION}，实得 {data.get('manifest_version')!r}"
        )
        return problems                      # 版本不对则后续字段语义未定义，直接终止
    if not data.get("source"):
        problems.append("缺少 source（数据源标识）")
    systems = data.get("systems")
    if not isinstance(systems, list) or not systems:
        problems.append("systems 必须为非空数组")
        return problems

    seen_ids: dict[str, int] = {}
    for si, system in enumerate(systems):
        tag = f"systems[{si}]"
        if not isinstance(system, dict) or not system.get("name"):
            problems.append(f"{tag}: 缺少 name")
            continue
        for struct in system.get("structures") or []:
            sid = struct.get("id")
            stag = f"{tag}.structures[{struct.get('id', '?')}]"
            if not sid:
                problems.append(f"{stag}: 缺少 id")
                continue
            seen_ids[sid] = seen_ids.get(sid, 0) + 1
            names = struct.get("names") or {}
            for lang in REQUIRED_NAME_LANGS:
                if not names.get(lang):
                    problems.append(f"{stag}: names.{lang} 必填")
            for lang in names:
                if lang not in REQUIRED_NAME_LANGS + OPTIONAL_NAME_LANGS:
                    problems.append(f"{stag}: names.{lang} 不是受支持语言（{REQUIRED_NAME_LANGS + OPTIONAL_NAME_LANGS}）")
            if struct.get("kind") not in KINDS:
                problems.append(f"{stag}: kind 必须是 {sorted(KINDS)} 之一，实得 {struct.get('kind')!r}")
            mesh = struct.get("mesh")
            if not isinstance(mesh, dict) or not mesh.get("glb") or mesh.get("node") in (None, ""):
                problems.append(f"{stag}: mesh 必须含 glb 与 node")
            if not isinstance(struct.get("parents") or [], list):
                problems.append(f"{stag}: parents 必须是数组")

    for sid, count in seen_ids.items():
        if count > 1:
            problems.append(f"结构 id 重复: {sid}（出现 {count} 次）")

    # parents 引用完整性（软检查：允许跨系统引用）
    all_ids = set(seen_ids)
    for si, system in enumerate(systems):
        for struct in system.get("structures") or []:
            for pid in struct.get("parents") or []:
                if pid not in all_ids:
                    problems.append(f"systems[{si}].{struct.get('id')}: parent {pid} 悬空（清单内无此 id）")
    return problems


def loads(text: str) -> tuple[dict, list[str]]:
    """从 JSON 文本加载并校验，返回 (manifest, problems)。"""
    data = json.loads(text)
    return data, validate_manifest(data)
