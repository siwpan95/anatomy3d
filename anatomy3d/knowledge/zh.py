# -*- coding: utf-8 -*-
"""M3 三语知识层：中文名 / 拉丁名 / 中文释义，均按英文术语 join。

纯标准库、无 GL 依赖；运行时只读 data/*.csv（由 tools/pipeline/build_zh_index.py 生成）。
"""
from __future__ import annotations

import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")


def _load_csv(name: str, key_col: str, val_col: str) -> dict[str, str]:
    path = os.path.join(DATA, name)
    out: dict[str, str] = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            k, v = row.get(key_col, "").strip(), row.get(val_col, "").strip()
            if k and v:
                out.setdefault(k.lower(), v)
    return out


def normalize_en(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*\([^)]*\)", "", s)       # 去括号注释
    return s.strip()


class Knowledge:
    """三语索引（实例化后一次载入，供 viewer/HUD/测试共享）。"""

    def __init__(self):
        self.zh = _load_csv("zh_terms.csv", "en", "zh")
        # 自撰高频基础词表（标准解剖学名词）覆盖/补齐大词表漏项，如 heart/aorta
        self.zh.update(_load_csv("zh_extra.csv", "en", "zh"))
        self.latin = _load_csv("ta2_latin.csv", "ta2_id", "latin")
        self.definitions = _load_csv("definitions.csv", "en", "zh_def")

    def zh_for(self, en: str) -> str | None:
        for key in (en.strip().lower(), normalize_en(en)):
            hit = self.zh.get(key)
            if hit:
                return hit
        return None

    def latin_for(self, ta2_id: str | None) -> str | None:
        return self.latin.get(str(ta2_id).strip()) if ta2_id else None

    def definition_for(self, en: str) -> str | None:
        for key in (en.strip().lower(), normalize_en(en)):
            hit = self.definitions.get(key)
            if hit:
                return hit
        return None

    def enrich_manifest(self, manifest: dict) -> tuple[dict, dict]:
        """把三语名与释义写入 manifest 结构（不改变既有字段语义）。"""
        stats = {"structures": 0, "zh": 0, "la": 0, "definitions": 0}
        enriched = json.loads(json.dumps(manifest))   # 深拷贝，不动原对象
        for system in enriched.get("systems", []):
            for s in system.get("structures", []):
                stats["structures"] += 1
                names = s.setdefault("names", {})
                en = names.get("en", "")
                zh = self.zh_for(en)
                la = self.latin_for(s.get("ta2_id"))
                definition = self.definition_for(en)
                if zh:
                    names["zh"] = zh
                    stats["zh"] += 1
                if la:
                    names["la"] = la
                    stats["la"] += 1
                if definition:
                    s["definition"] = {"zh": definition}
                    stats["definitions"] += 1
        return enriched, stats

    def summary(self) -> str:
        return (f"Knowledge: zh={len(self.zh)} latin={len(self.latin)} "
                f"definitions={len(self.definitions)}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=os.path.join(ROOT, "assets", "anatomy.manifest.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "assets", "anatomy.zh.manifest.json"))
    args = ap.parse_args()
    k = Knowledge()
    manifest = json.load(open(args.manifest, encoding="utf-8"))
    enriched, stats = k.enrich_manifest(manifest)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=1)
    print(f"[OK] {k.summary()}")
    print(f"[OK] enriched -> {args.out}: {stats}")
    try:
        from anatomy3d.contracts.manifest import validate_manifest
        problems = validate_manifest(enriched)
        print(f"  [contract] {'PASS' if not problems else str(len(problems)) + ' problems'}")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
