# -*- coding: utf-8 -*-
"""manifest 构建器 —— 导出报告 → structure-manifest v1（仓外运行，stdlib only）。

用法::

    python tools/pipeline/build_manifest.py \\
        --report assets/cardiovascular.report.json \\
        --ta2 vendor-ref/TA2.csv \\
        --system cardiovascular \\
        --out assets/cardiovascular.manifest.json

规则（与 docs/契约/structure-manifest-v1.md 对齐）：
  · TA2 join 键 = TA2.csv 的 English 列 ↔ 导出对象名（先精确匹配，再做后缀清洗）；
  · Z-Anatomy 对象名后缀清洗：尾部 `.xx`（.l/.r/.j/.g/.ol/.or…）与尾部 `'` 逐层剥离，
    逐层尝试匹配（`Muscle.l` → `Muscle`）；
  · **仅收录能映射到 TA2 的结构**（沿用先例 Anatria-3D 的口径：不带术语的几何不上架，
    剔除项保留在报告供人工复核）；
  · id = `TA2:<ta2id>`（稳定、可追溯）；kind 由所属系统映射（封闭枚举）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re

# Z-Anatomy 命名后缀（audit.json 实测：.l/.r 左右、.ol/.or 起止点、.j 关节、.g 组、尾部 ' 变体）
SUFFIX_RE = re.compile(r"\s*[.](?:[a-z]{1,3})\s*$")
PRIME_RE = re.compile(r"\s*'\s*$")

# 系统 → kind（契约封闭枚举）
SYSTEM_KIND = {
    "skeletal": "bone",
    "arthrology": "bone",
    "joints": "bone",
    "muscular": "muscle",
    "cardiovascular": "vessel",
    "lymphoid": "organ",
    "nervous": "nerve",
    "visceral": "organ",
    "regions": "region",
}

# 仓内运行时把包根加入 path（MatchIndex 分层匹配可用）；仓外缺包时 build_ta2_index
# 会 ImportError 退回纯 dict（仅精确+剥后缀），脚本仍可跑（stdlib-only 纪律）。
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..")))


def load_ta2_en_index(path: str) -> dict[str, str]:
    """TA2.csv → {English: TA2ID}。

    实测形态：BOM + 空首行 + 每行整体被双引号包裹 + 分号分隔 —— csv 标准解析
    会把整行当单字段，故手动去引号再切分（P9）。
    """
    idx: dict[str, str] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [ln.strip().strip('"').split(";") for ln in f if ln.strip()]
    header = None
    for row in rows:
        if row and row[0].strip().lower().startswith("ta2id"):
            header = row
            break
    if header is None:
        raise SystemExit(f"[FAIL] TA2.csv 找不到表头: {path}")
    cols = {name.strip().lower(): i for i, name in enumerate(header)}
    i_id, i_en = cols["ta2id"], cols["english"]
    for row in rows:
        if row is header or len(row) <= max(i_id, i_en):
            continue
        en = row[i_en].strip()
        tid = row[i_id].strip()
        if en and tid and en.lower() not in idx:      # 首见优先（TA2 语义唯一）
            idx[en.lower()] = tid
    return idx


def lookup(name: str, ta2) -> tuple[str, str] | None:
    """返回 (matched_term, ta2_id) 或 None。

    P23：ta2 参数升级为 MatchIndex（分层 exact→suffix→normalized→edit1，
    见 anatomy3d/knowledge/ta2_match.py）；传旧式 dict 仍可跑（仅精确+剥后缀）。
    """
    if isinstance(ta2, dict):
        cur = name.strip()
        for _ in range(3):
            hit = ta2.get(cur.lower())
            if hit:
                return cur, hit
            stripped = SUFFIX_RE.sub("", PRIME_RE.sub("", cur))
            if stripped == cur:
                break
            cur = stripped.strip()
        return None
    m = ta2.match(name)
    return (m.term, m.value) if m else None


def build_ta2_index(ta2_path: str):
    """TA2.csv → 分层匹配索引（优先用 MatchIndex；不可导入时退回 dict）。"""
    try:
        from anatomy3d.knowledge.ta2_match import MatchIndex
        return MatchIndex.from_pairs(load_ta2_en_index_pairs(ta2_path))
    except ImportError:
        return load_ta2_en_index(ta2_path)


def load_ta2_en_index_pairs(path: str) -> list[tuple[str, str]]:
    """load_ta2_en_index 的 pairs 形态（供 MatchIndex.from_pairs）。"""
    pairs = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [ln.strip().strip('"').split(";") for ln in f if ln.strip()]
    header = None
    for row in rows:
        if row and row[0].strip().lower().startswith("ta2id"):
            header = row
            break
    if header is None:
        raise SystemExit(f"[FAIL] TA2.csv 找不到表头: {path}")
    cols = {name.strip().lower(): i for i, name in enumerate(header)}
    i_id, i_en = cols["ta2id"], cols["english"]
    for row in rows:
        if row is header or len(row) <= max(i_id, i_en):
            continue
        en = row[i_en].strip()
        tid = row[i_id].strip()
        if en and tid:
            pairs.append((en, tid))
    return pairs


def sanitize_node(name: str) -> str:
    """GLB 节点名 sanitize 形态（空格→下划线；与查看器查找约定一致）。"""
    return re.sub(r"\s+", "_", name.strip())


def build(report_path: str, ta2_path: str, system: str, out_path: str) -> None:
    report = json.load(open(report_path, encoding="utf-8-sig"))
    ta2 = build_ta2_index(ta2_path)

    kind = SYSTEM_KIND.get(system, "other")
    glb_name = (report.get("out") or out_path).replace("\\", "/").split("/")[-1]
    structures, excluded = [], []
    by_id: dict[str, dict] = {}
    for ob in report["objects"]:
        name = ob["name"]
        hit = lookup(name, ta2)
        if not hit:
            excluded.append({"name": name, "reason": "no-ta2-match", "polys": ob.get("polys")})
            continue
        matched, tid = hit
        # id 必须全域唯一：同一 TA2 概念会在多个系统/节点里出现（股骨同时在骨骼与区域系统）。
        # 用「TA2 id + system + node slug」复合键，既能追溯概念又不误删跨系统条目。
        node_slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
        sid = f"TA2:{tid}:{system}:{node_slug}"
        entry = {
            "id": sid,
            "ta2_id": tid,
            "names": {"en": matched},
            "kind": kind,
            "mesh": {"glb": glb_name, "node": name},
            "polys": ob.get("polys", 0),
        }
        # 同一 TA2 概念的多个后缀变体（.l/.r 左右、起止点等）：保留几何量最大的代表
        if sid in by_id:
            if entry["polys"] > by_id[sid]["polys"]:
                excluded.append({"name": by_id[sid]["mesh"]["node"], "reason": f"variant-of-{sid}"})
                by_id[sid] = entry
            else:
                excluded.append({"name": name, "reason": f"variant-of-{sid}"})
            continue
        by_id[sid] = entry
    structures = list(by_id.values())

    manifest = {
        "manifest_version": 1,
        "source": "z-anatomy",
        "systems": [
            {"name": system, "label": {"en": system}, "structures": structures},
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print(f"[OK] manifest -> {out_path}: {len(structures)} structures, {len(excluded)} excluded")
    # 仓内契约校验（如可导入）
    try:
        from anatomy3d.contracts.manifest import validate_manifest
        problems = validate_manifest(manifest)
        for p in problems[:10]:
            print(f"  [contract] {p}")
        print(f"  [contract] {'PASS' if not problems else f'{len(problems)} problems'}")
    except ImportError:
        print("  [contract] SKIP（anatomy3d 包不在 sys.path，稍后用 selfcheck 校验）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--ta2", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    build(args.report, args.ta2, args.system, args.out)
