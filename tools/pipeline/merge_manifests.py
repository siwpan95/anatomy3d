# -*- coding: utf-8 -*-
"""合并各系统 manifest 为一张全图谱清单（stdlib only）。

用法::

    python tools/pipeline/merge_manifests.py --dir assets --out assets/anatomy.manifest.json

合并时按结构 id 去重；跨系统同名 id 保留首个并记录冲突。合并后跑一次契约校验。
"""
from __future__ import annotations

import argparse
import glob
import json
import os


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="assets")
    ap.add_argument("--out", default="assets/anatomy.manifest.json")
    args = ap.parse_args()

    systems, seen, dup = [], set(), []
    out_abs = os.path.abspath(args.out)
    for path in sorted(glob.glob(os.path.join(args.dir, "*.manifest.json"))):
        if os.path.abspath(path) == out_abs:      # 跳过上次合并产物，避免自引用翻倍
            continue
        manifest = json.load(open(path, encoding="utf-8"))
        for system in manifest.get("systems", []):
            kept = []
            for s in system["structures"]:
                if s["id"] in seen:
                    dup.append({"id": s["id"], "system": system["name"]})
                    continue
                seen.add(s["id"])
                kept.append(s)
            systems.append({"name": system["name"], "label": system.get("label", {}),
                            "structures": kept})

    merged = {"manifest_version": 1, "source": "z-anatomy", "systems": systems}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)

    total = sum(len(s["structures"]) for s in systems)
    print(f"[OK] merged {len(systems)} systems / {total} structures -> {args.out}")
    if dup:
        print(f"  [note] {len(dup)} cross-system duplicate ids dropped (first wins)")

    try:
        from anatomy3d.contracts.manifest import validate_manifest
        problems = validate_manifest(merged)
        print(f"  [contract] {'PASS' if not problems else str(len(problems)) + ' problems'}")
        for p in problems[:8]:
            print(f"    {p}")
    except ImportError:
        print("  [contract] SKIP（包不在 sys.path）")


if __name__ == "__main__":
    main()
