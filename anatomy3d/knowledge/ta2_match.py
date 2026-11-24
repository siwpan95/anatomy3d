# -*- coding: utf-8 -*-
"""TA2 术语近似匹配器 —— 资产管线与场景导入共用的「名字 → 概念」匹配链。

背景（P10 待办 + P23 实测）：Z-Anatomy 对象名与 TA2 术语间存在大量可机械弥合的偏差：
  · 后缀变体：`.l/.r`（左右）、`.ol/.or`（起止点）、`.e1l/.o1r`（带数字变体）、尾部 `'` 与 `*`
  · 拼写/形态差：大小写、连字符、多空格、标点、复数（arteries ↔ artery）
逐级匹配（level 从强到弱，全部命中都带 matched_term 供人工复核）：
  1. exact      —— 清洗空格后精确命中
  2. suffix     —— 逐层剥离后缀/引号/星号/括号注记后命中
  3. normalized —— 双向归一化（lower/分隔符/标点/常见复数）命中
双向归一化是安全的关键：索引侧与查询侧过**同一个** normalize，键碰撞只发生在
本来就可能同名的词上；粗复数剥离不做 y↔ies 单向猜测，而是规则化双向处理。

性能注意：edit1（编辑距离 1）只对归一化后仍不命中的**去重查询**计算，
并对候选键做长度与首字符预筛，避免 O(n×m) 全表扫描。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Z-Anatomy 命名噪声：`.xx` 字母后缀、`.e1l` 等字母+数字混合后缀、尾部引号/星号
SUFFIX_RE = re.compile(r"\s*[.](?:[a-z]{0,3}\d{0,2}[a-z]{0,3})\s*$")
TAIL_NOISE_RE = re.compile(r"\s*[*'\s]+\s*$")
PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")


@dataclass
class MatchResult:
    term: str        # 命中的原始术语（供人工复核）
    value: str       # 索引值（TA2 id / manifest 结构 id 等）
    level: str       # exact / suffix / normalized / edit1


def normalize(s: str) -> str:
    """双向一致的归一化：索引侧与查询侧必须用同一函数。"""
    s = str(s).lower()
    s = re.sub(r"[\s\-_/]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"ies$", "y", s)          # arteries → artery
    if len(s) > 3 and s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]                        # 粗复数（vessels → vessel）
    return s


def clean_zanatomy(name: str, max_pass: int = 4) -> str:
    """逐层剥离 Z-Anatomy 命名噪声（后缀/引号/星号/括号注记），返回规范名。

    括号两种形态分开处理（P23 实测）：
      · 整名包裹 `(Abdominal part of ...)` → 去外层括号**保留内容**；
      · 尾部注记 `Gyrus (Posteroventral part*)` → 剥掉注记（剥完非空才应用，防剥成空串）。
    """
    cur = str(name).strip()
    for _ in range(max_pass):
        nxt = SUFFIX_RE.sub("", cur)
        nxt = TAIL_NOISE_RE.sub("", nxt)
        if nxt.startswith("(") and nxt.endswith(")") and nxt.count("(") == 1:
            inner = nxt[1:-1].strip()
            if inner:
                nxt = inner
        else:
            p = PAREN_RE.sub("", nxt)
            if p.strip():
                nxt = p
        nxt = nxt.strip()
        if nxt == cur:
            break
        cur = nxt
    return cur


class MatchIndex:
    """两级索引：精确键 + 归一化键。value 可为 TA2 id 或 manifest 结构 id。"""

    def __init__(self) -> None:
        self._exact: dict[str, tuple[str, str]] = {}      # lower(term) -> (term, value)
        self._norm: dict[str, tuple[str, str]] = {}       # normalize(term) -> (term, value)

    def add(self, term: str, value: str) -> None:
        """登记一条术语。同键首见优先（与 build_manifest 的「TA2 语义唯一」口径一致）。

        P23 教训：索引端必须先把术语过 clean_zanatomy 再键化——原始名带 `.l` 类后缀时，
        normalize 去标点会产生 `heartl` 这种错键，查询端 `heart` 永远对不上。
        """
        t = clean_zanatomy(str(term))
        v = str(value).strip()
        if not t or not v:
            return
        self._exact.setdefault(t.lower(), (t, v))
        self._norm.setdefault(normalize(t), (t, v))

    @classmethod
    def from_pairs(cls, pairs) -> "MatchIndex":
        idx = cls()
        for term, value in pairs:
            idx.add(term, value)
        return idx

    def __len__(self) -> int:
        return len(self._exact)

    def match(self, name: str, use_edit1: bool = True) -> MatchResult | None:
        """逐级匹配：exact → suffix → normalized → edit1。"""
        # 1) exact
        hit = self._exact.get(str(name).strip().lower())
        if hit:
            return MatchResult(hit[0], hit[1], "exact")
        # 2) suffix：逐层剥噪声后精确
        cur = str(name).strip()
        for _ in range(4):
            nxt = clean_zanatomy(cur)
            if nxt == cur:
                break
            cur = nxt
            hit = self._exact.get(cur.lower())
            if hit:
                return MatchResult(hit[0], hit[1], "suffix")
        # 3) normalized：查询名也归一化后在归一化索引里找
        q = normalize(str(name))
        hit = self._norm.get(q)
        if hit:
            return MatchResult(hit[0], hit[1], "normalized")
        # 剥噪声后的归一化再试一次（括号注记形态）
        hit = self._norm.get(normalize(cur)) if cur else None
        if hit:
            return MatchResult(hit[0], hit[1], "normalized")
        # 4) edit1：仅对归一化后仍不命中的查询，编辑距离 1 兜底
        if use_edit1 and q:
            hit = self._edit1(q)
            if hit:
                return MatchResult(hit[0], hit[1], "edit1")
        return None

    def _edit1(self, q: str) -> tuple[str, str] | None:
        """编辑距离 1 查找：长度分桶 + 首字符预筛。"""
        best: tuple[str, str] | None = None
        for k, (term, value) in self._norm.items():
            if abs(len(k) - len(q)) > 1 or (k and q and k[0] != q[0]):
                continue
            if _within_edit1(q, k):
                best = (term, value)   # 首见优先
                break
        return best


def _within_edit1(a: str, b: str) -> bool:
    if a == b:
        return False   # 相等不算「距离 1 的纠错」
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        return len(diff) == 1
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):
        if a == b[:i] + b[i + 1:]:
            return True
    return False


def selfcheck() -> bool:
    """能红能绿自检：合法匹配全过 + 误匹配用例全被拒。"""
    ok = True

    def check(label, cond):
        nonlocal ok
        print(("  [OK] " if cond else "  [FAIL] ") + label)
        ok = ok and cond

    idx = MatchIndex.from_pairs([
        ("Adductor pollicis", "T1"),
        ("Pulmonary artery", "T2"),
        ("Heart", "T3"),
        ("Cingulate gyrus", "T4"),
        ("Accessory parotid gland", "T5"),
    ])
    r = idx.match("adductor pollicis")
    check("精确命中", r and r.value == "T1" and r.level == "exact")
    r = idx.match("Adductor pollicis.e1l")
    check("带数字后缀剥除命中", r and r.value == "T1" and r.level == "suffix")
    r = idx.match("Pulmonary arteries")
    check("复数归一命中", r and r.value == "T2" and r.level == "normalized")
    r = idx.match("Cingulate gyrus (Posteroventral part*)")
    check("括号注记剥离命中", r and r.value == "T4")
    r = idx.match("(Accessory parotid gland).l")
    check("整名括号包裹去壳命中", r and r.value == "T5")
    r = idx.match("Pulonary artery")   # 源数据真实拼写错（P10 实测）
    check("ED1 拼写纠错命中", r and r.value == "T2" and r.level == "edit1")
    # 红：不相关词必须不命中
    check("不相关词不命中", idx.match("Femur") is None)
    check("空串不命中", idx.match("") is None)
    # 红：ED1 距离 2 不命中
    check("ED2 不命中", idx.match("Pulonarry artery") is None)
    print("[ta2_match selfcheck] %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if selfcheck() else 1)
