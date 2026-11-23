# -*- coding: utf-8 -*-
"""anatomy3d 无头自检（registry verify 入口）。

口径：exit 0 = 全部通过；任何异常 exit 1。仅标准库，无 GL 上下文要求。
检查面：
  1. 契约层：合法 manifest 通过 + 各类非法 manifest 全部被抓（能红能绿）
  2. 知识层：样例 TA2 索引可加载、join 键可用
  3. 管线层：ExportJob 参数形状与前置检查路径（无 Blender 时预期报告缺口）
  4. cli：--report 可产出
"""
from __future__ import annotations

import os
import sys

# 与工作目录无关：以本脚本所在目录（仓根）为基准
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anatomy3d import __version__  # noqa: E402
from anatomy3d.cli import build_report  # noqa: E402
from anatomy3d.contracts.manifest import validate_manifest  # noqa: E402
from anatomy3d.knowledge.ta2 import index_by_en, load_ta2_index  # noqa: E402
from anatomy3d.knowledge.quiz import Quiz  # noqa: E402
from anatomy3d.knowledge.zh import Knowledge  # noqa: E402
from anatomy3d.pipeline.blender_export import ExportJob, check_pipeline_prereqs  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def main() -> int:
    print(f"anatomy3d selfcheck v{__version__}")

    # ── 1. 契约层（能红能绿双向） ─────────────────────────────
    good = {
        "manifest_version": 1,
        "source": "z-anatomy",
        "systems": [
            {
                "name": "cardiovascular",
                "label": {"la": "Systema cardiovasculare", "en": "Cardiovascular system", "zh": "心血管系统"},
                "structures": [
                    {
                        "id": "FMA7128",
                        "names": {"en": "Heart", "la": "Cor"},
                        "kind": "organ",
                        "mesh": {"glb": "cardiovascular.glb", "node": "Heart"},
                        "parents": [],
                    }
                ],
            }
        ],
    }
    check("合法 manifest 通过", validate_manifest(good) == [])

    def bad(mutate) -> list[str]:
        import copy

        data = copy.deepcopy(good)
        mutate(data)
        return validate_manifest(data)

    check("版本号错误被抓", len(bad(lambda d: d.update(manifest_version=2))) == 1)
    check("names.en 缺失被抓", len(bad(lambda d: d["systems"][0]["structures"][0].update(names={"la": "Cor"}))) == 1)
    check("kind 非枚举被抓", len(bad(lambda d: d["systems"][0]["structures"][0].update(kind="bone-muscle"))) == 1)
    check("mesh 缺 node 被抓", len(bad(lambda d: d["systems"][0]["structures"][0].update(mesh={"glb": "x.glb"}))) == 1)
    check("id 重复被抓", len(
        bad(lambda d: d["systems"][0]["structures"].append(dict(d["systems"][0]["structures"][0])))
    ) >= 1)
    check("parent 悬空被抓", len(
        bad(lambda d: d["systems"][0]["structures"][0].update(parents=["FMA9999"]))
    ) == 1)

    # ── 2. 知识层 ────────────────────────────────────────────
    idx = load_ta2_index()
    check("样例 TA2 索引可加载", len(idx) >= 6, f"实得 {len(idx)} 条")
    by_en = index_by_en(idx)
    check("英文名 join 键可用", by_en.get("Heart") is not None and by_en["Heart"].zh == "心")

    # ── 3. 管线层 ────────────────────────────────────────────
    job = ExportJob(blend_path="Z-Anatomy/Startup.blend")
    prereqs = check_pipeline_prereqs(job)
    check("无 Blender 时前置检查如实报告", any("blender" in p for p in prereqs), str(prereqs))
    check("命令行预览可生成", isinstance(job.command_preview(), list))

    # ── 4. M3 知识层 ─────────────────────────────────────────
    k = Knowledge()
    check("三语索引可加载", len(k.zh) >= 700 and len(k.latin) >= 1700, k.summary())
    check("高频中文映射命中", k.zh_for("Heart") == "心" and k.zh_for("Femur") == "股骨")
    enriched, stats = k.enrich_manifest({
        "manifest_version": 1, "source": "test", "systems": [
            {"name": "t", "structures": [
                {"id": "TA2:1:t:heart", "ta2_id": "4076", "names": {"en": "Heart"}, "kind": "organ"}]}]})
    check("manifest 三语富化", stats["zh"] == 1 and enriched["systems"][0]["structures"][0]["names"].get("zh") == "心")
    q = Quiz(enriched, seed=1)
    check("quiz 出题可用", q.next() is not None and q.current["answer_id"] == "TA2:1:t:heart")

    # ── 5. cli ───────────────────────────────────────────────
    report = build_report()
    check("装配报告可产出", "anatomy3d" in report and "TA2" in report)

    if FAILURES:
        print(f"selfcheck 未通过：{len(FAILURES)} 项 — {FAILURES}")
        return 1
    print("selfcheck 全部通过")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # GBK 控制台防护（本机既定纪律）
    sys.exit(main())
