# -*- coding: utf-8 -*-
"""Blender 无头导出脚本 —— 在 Blender 内运行（`--background Startup.blend --python ...`）。

用法（Blender 4.2.x，自包含、仅标准库 —— Blender 自带 Python 与本仓包无依赖关系）::

    # 结构摸底：dump collection 树到 JSON（对标先例 Anatria-3D 的 blender_inspect）
    blender --background Startup.blend --python tools/pipeline/blender_export.py -- \\
        --inspect --out inspect.json

    # 导出：按 collection 路径导出该子树的全部几何（MESH + 曲线转网格）
    blender --background Startup.blend --python tools/pipeline/blender_export.py -- \\
        --collection "Bonus collection/Cardiovascular system/Heart" \\
        --out assets/cardiovascular.glb --report report.json

实现要点（对应 tools/pipeline/README.md 坑点清单）：
  ① staging 干净场景：原场景带 driver 网络/依赖环，直导 glTF 会 IndexError ——
     全部几何经 evaluated depsgraph 烘焙为普通 mesh 后链入空场景再导出；
  ② curves 是几何：CURVE/SURFACE/FONT/META 一律经 new_from_object 转网格，
     否则整棵脉管树静默丢失；
  ③ 材质丢弃：viewer 自行着色（PBR），导出只保几何与节点名；
  ④ 节点名保留原样（TA2 英文术语），manifest 侧再做 sanitize 兼容。
"""
from __future__ import annotations

import argparse
import json
import sys

import bpy

GEOMETRY_TYPES = {"MESH", "CURVE", "SURFACE", "META"}   # FONT = 3D 文字标注，非解剖几何，排除


def collection_by_path(root_path: str):
    """按 'A/B/C' 路径找 collection（collection 层级即解剖层级）。"""
    parts = [p.strip() for p in root_path.split("/") if p.strip()]
    current = None
    # 顶层：在全场景 collection children 里按名匹配
    def find_in(children):
        for c in children:
            if c.name == parts_done[-1]:
                return c
        return None

    parts_done = []
    for part in parts:
        parts_done.append(part)
        if current is None:
            # 在所有场景的顶层 children 中找（Z-Anatomy 用多场景/视图层）
            found = None
            for scene in bpy.data.scenes:
                found = find_in(scene.collection.children)
                if found:
                    break
            if not found:
                found = find_in(bpy.data.collections)
            current = found
        else:
            current = find_in(current.children)
        if current is None:
            raise SystemExit(f"[FAIL] collection 路径不存在: {root_path}（止于 {part}）")
    return current


def walk_collections(coll, path=""):
    """递归产出 (path, coll) 与统计。"""
    here = f"{path}/{coll.name}" if path else coll.name
    yield here, coll
    for child in coll.children:
        yield from walk_collections(child, here)


def objects_recursive(coll):
    """collection 子树全部对象（含嵌套）。"""
    seen = set()
    for ob in coll.objects:
        seen.add(ob.name)
        yield ob
    for child in coll.children:
        yield from objects_recursive(child)
    _ = seen


def do_inspect(out_path: str) -> None:
    """dump 全部场景的 collection 树 + 对象类型统计。"""
    doc = {"blender": bpy.app.version_string, "scenes": [], "collections_total": 0}
    seen_paths = set()
    for scene in bpy.data.scenes:
        sdoc = {"name": scene.name, "collections": []}
        for path, coll in walk_collections(scene.collection):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            types: dict[str, int] = {}
            for ob in coll.objects:
                types[ob.type] = types.get(ob.type, 0) + 1
            sdoc["collections"].append(
                {"path": path, "objects": len(coll.objects), "types": types}
            )
        sdoc["collections_total"] = len(sdoc["collections"])
        doc["collections_total"] += sdoc["collections_total"]
    doc["scenes"].append(sdoc)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"[OK] inspect -> {out_path}: {doc['collections_total']} collections")


def build_stage_and_export(coll, out_glb: str, report_path: str) -> None:
    """烘焙子树几何到干净场景并导出 GLB。"""
    deps = bpy.context.evaluated_depsgraph_get()
    stage = bpy.data.scenes.new("anatomy3d_stage")

    converted, skipped = [], []
    for ob in objects_recursive(coll):
        if ob.type not in GEOMETRY_TYPES:
            skipped.append({"name": ob.name, "type": ob.type})
            continue
        try:
            ev = ob.evaluated_get(deps)
            mesh = bpy.data.meshes.new_from_object(ev)
            if mesh is None or len(mesh.polygons) == 0:
                skipped.append({"name": ob.name, "type": ob.type, "reason": "empty-mesh"})
                continue
            mesh.materials.clear()   # 材质节点树带断链 node group，glTF gatherer 会 IndexError（坑点①实体）；viewer 自行着色
            new_ob = bpy.data.objects.new(ob.name, mesh)
            new_ob.matrix_world = ob.matrix_world.copy()
            stage.collection.objects.link(new_ob)
            converted.append(
                {"name": ob.name, "src_type": ob.type, "polys": len(mesh.polygons)}
            )
        except Exception as exc:  # noqa: BLE001 —— 单对象失败不拖垮整树，逐条报告
            skipped.append({"name": ob.name, "type": ob.type, "reason": str(exc)})

    # 激活 stage（后台模式也有 window，实测 4.2）
    wm = bpy.context.window_manager
    if wm.windows:
        wm.windows[0].scene = stage
    print(f"[debug] active scene = {bpy.context.scene.name!r} (stage has {len(stage.collection.objects)} objects)")

    # 确认 glTF 导出器可用
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass  # 4.2 出厂默认已启用

    # 移除原场景：烘焙已完成，stage 是文件里唯一的场景。
    # 不移除的话导出器会把原场景一并导出（实测 17 对象的 stage 导出 3407 个 mesh）。
    for scene in list(bpy.data.scenes):
        if scene != stage:
            bpy.data.scenes.remove(scene)

    kwargs = dict(
        filepath=out_glb,
        export_format="GLB",
        export_yup=True,
        export_materials="NONE",   # 不走材质节点树（Z-Anatomy 的 node group 带断链）
    )
    export_ok, export_err = True, ""
    try:
        with bpy.context.temp_override(scene=stage, collection=stage.collection):
            bpy.ops.export_scene.gltf(**kwargs)
    except Exception as exc:  # noqa: BLE001
        export_ok, export_err = False, str(exc)

    total_polys = sum(c["polys"] for c in converted)
    report = {
        "collection": coll.name,
        "export_ok": export_ok,
        "export_error": export_err,
        "out": out_glb,
        "converted": len(converted),
        "total_polygons": total_polys,
        "objects": converted,
        "skipped": skipped,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(
        f"[{'OK' if export_ok else 'FAIL'}] export {coll.name}: "
        f"{len(converted)} objects / {total_polys} polys -> {out_glb}"
        + (f" | error: {export_err}" if export_err else "")
    )


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="blender_export")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--collection", help="collection 路径 A/B/C")
    parser.add_argument("--out", required=True, help="inspect JSON 或 GLB 输出路径")
    parser.add_argument("--report", help="导出报告 JSON 路径")
    args = parser.parse_args(argv)

    if args.inspect:
        do_inspect(args.out)
        return
    if not args.collection:
        raise SystemExit("[FAIL] 导出模式需要 --collection")
    coll = collection_by_path(args.collection)
    build_stage_and_export(coll, args.out, args.report or (args.out + ".report.json"))


main()
