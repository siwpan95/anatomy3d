# -*- coding: utf-8 -*-
"""TA2 三语术语索引。

数据形态：CSV，列 = ta2_id,en,la,zh
（zh 渐进补齐：TA2 无官方中文列，中文映射来自全国科学技术名词审定委员会
《人体解剖学名词》，人工校对 —— 这是 M3 的主要工作量，见 docs/项目书.md）。

编码铁律：显式 encoding="utf-8-sig"（GBK 控制台 + 编辑器 BOM 双重防护：
按 utf-8 读带 BOM 文件时首列名会变成 \\ufeffta2_id 导致 KeyError —— 本仓实测踩过，
见 docs/问题记录.md P4）。
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass

_SAMPLE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "ta2_sample.csv")


@dataclass
class Term:
    ta2_id: str
    en: str
    la: str
    zh: str | None


def load_ta2_index(path: str | None = None) -> dict[str, Term]:
    """加载术语索引，按 ta2_id 主键返回 dict；缺省用仓内样例（与 cwd 无关）。"""
    if path is None:
        path = _SAMPLE_PATH
    """加载术语索引，按 ta2_id 主键返回 dict。

    en 名同为 join 键的辅助用途（Z-Anatomy 对象名即 TA2 英文术语），
    由 index_by_en() 提供。
    """
    terms: dict[str, Term] = {}
    if not os.path.exists(path):
        return terms
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            term = Term(
                ta2_id=row["ta2_id"].strip(),
                en=row["en"].strip(),
                la=(row.get("la") or "").strip(),
                zh=(row.get("zh") or "").strip() or None,
            )
            terms[term.ta2_id] = term
    return terms


def index_by_en(terms: dict[str, Term]) -> dict[str, Term]:
    """按英文名建索引（供资产管线 join Z-Anatomy 节点名用）。"""
    return {t.en: t for t in terms.values()}
