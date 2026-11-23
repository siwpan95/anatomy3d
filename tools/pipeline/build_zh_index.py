# -*- coding: utf-8 -*-
"""M3 构建器：从大词表/TA2.csv 生成运行时紧凑索引（stdlib 运行期只读 CSV）。

用法::

    python tools/pipeline/build_zh_index.py

输入（均已在 vendor-ref 落地并署名）：
  · zh_en_anatomy.xlsx  中英医学名词（health.net.cn 整理，40231 行）
  · TA2.csv             Z-Anatomy 自带 TA2 术语（含 Latin 列）
  · assets/anatomy.manifest.json  全图谱结构清单
输出（data/，UTF-8 无 BOM）：
  · zh_terms.csv      en,zh     —— 只保留 manifest 命中的英文术语
  · ta2_latin.csv     ta2_id,latin
"""
from __future__ import annotations

import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENDOR = os.path.join(ROOT, "vendor-ref")
DATA = os.path.join(ROOT, "data")


def manifest_en_ids():
    m = json.load(open(os.path.join(ROOT, "assets", "anatomy.manifest.json"), encoding="utf-8"))
    en = {s["names"]["en"] for sys in m["systems"] for s in sys["structures"]}
    ids = {s["ta2_id"] for sys in m["systems"] for s in sys["structures"] if "ta2_id" in s}
    return en, ids


def norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def build_zh(en_names):
    import openpyxl
    wb = openpyxl.load_workbook(os.path.join(VENDOR, "zh_en_anatomy.xlsx"),
                                read_only=True, data_only=True)
    wanted = {norm(e) for e in en_names}
    out = {}
    for cat, zh, en in wb.worksheets[0].iter_rows(values_only=True):
        if not en or not zh or cat != "人体解剖学":
            continue
        k = norm(str(en))
        if k in wanted and k not in out:
            out[k] = str(zh).strip()
    path = os.path.join(DATA, "zh_terms.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["en", "zh"])
        for k, v in sorted(out.items()):
            w.writerow([k, v])
    return len(out)


def build_latin(wanted_ids):
    rows = []
    with open(os.path.join(VENDOR, "TA2.csv"), encoding="utf-8-sig") as f:
        lines = [ln.strip().strip('"').split(";") for ln in f if ln.strip()]
    header = next(r for r in lines if r[0].lower().startswith("ta2id"))
    i_id, i_la = header[0].strip().lower(), next(
        i for i, c in enumerate(header) if c.strip().lower() == "latin")
    idx = header.index("TA2ID")
    la_i = header.index([c for c in header if c.strip().lower() == "latin"][0])
    for row in lines:
        if len(row) <= max(idx, la_i):
            continue
        tid = row[idx].strip()
        if tid in wanted_ids and row[la_i].strip():
            rows.append((tid, row[la_i].strip()))
    seen, uniq = set(), []
    for tid, la in rows:
        if tid not in seen:
            seen.add(tid)
            uniq.append((tid, la))
    with open(os.path.join(DATA, "ta2_latin.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["ta2_id", "latin"])
        w.writerows(sorted(uniq))
    return len(uniq)


if __name__ == "__main__":
    en_names, ids = manifest_en_ids()
    os.makedirs(DATA, exist_ok=True)
    n_zh = build_zh(en_names)
    n_la = build_latin(ids)
    print(f"[OK] zh_terms.csv: {n_zh} entries (from 40231-row xlsx)")
    print(f"[OK] ta2_latin.csv: {n_la} entries (from TA2.csv)")
