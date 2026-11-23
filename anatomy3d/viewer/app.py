# -*- coding: utf-8 -*-
"""anatomy3d.viewer.app —— pyglet 解剖查看器（M2 骨架）。

用法::

    python -m anatomy3d.viewer.app --system reference --smoke 3
    python -m anatomy3d.viewer.app --system cardiovascular --max-nodes 32 --names Heart,Left_ventricle

关键设计（问题记录 P12）：
    **不调用 GLTF.build_scene()** —— 它内部构建全部 MeshData（实测 356 万面 21 分钟）。
    只对 lazy.plan 选中的节点调用 ``primitive_meshdata(primitive)``，
    按 budget 分帧/按键增量构建，做到「看得见的才构建」。

3dworld 复用纪律：通过 bridge.resolve_tdworld_src() 注入兄弟仓源码路径，
不 vendor、不 fork；import 全部集中在本文件的 _load_engine()。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from anatomy3d.knowledge.quiz import Quiz
from anatomy3d.knowledge.zh import Knowledge
from anatomy3d.viewer.bridge import resolve_tdworld_src
from anatomy3d.viewer.lazy import LazyAtlas, sanitize_node


def _patch_clip_shader(E):
    """运行时给 3dworld 的 PBR 片元着色器加一个裁剪平面（不改上游仓源码）。

    PBR_VERT 已输出 vWorldPos；在片元 main 开头按平面方程 discard 即可。
    平面禁用时用 w=1e6 哨兵值，永远不满足 dot > w。
    """
    shaders = E["shaders"]
    vert, frag = shaders.SOURCES["pbr"]
    if "uClipPlane" not in frag:
        frag = frag.replace(
            "void main() {",
            "uniform vec4 uClipPlane;\n"
            "void main() {\n"
            "    if (uClipPlane.w < 999.0 && dot(vWorldPos, uClipPlane.xyz) > uClipPlane.w) discard;",
            1,
        )
        shaders.SOURCES["pbr"] = (vert, frag)

KIND_COLORS = {
    "bone": (0.86, 0.82, 0.68),
    "muscle": (0.68, 0.24, 0.22),
    "vessel": (0.72, 0.16, 0.18),
    "nerve": (0.88, 0.78, 0.32),
    "organ": (0.66, 0.36, 0.44),
    "region": (0.48, 0.62, 0.72),
    "other": (0.60, 0.62, 0.66),
}


def _load_engine():
    """注入 3dworld 源码到 sys.path 并导入所需引擎件（跨仓唯一入口）。"""
    src = resolve_tdworld_src()
    if not src:
        raise SystemExit(
            "3dworld source not found: set ANATOMY3D_TDWORLD_SRC to its repo root"
        )
    if src not in sys.path:
        sys.path.insert(0, src)
    from world3d.engine.app import EngineApp, parse_args as engine_parse_args
    from world3d.engine.camera import OrbitCamera
    from world3d.engine.env import LightEnvironment
    from world3d.engine.gltf import GLTF
    from world3d.engine.material import Material
    from world3d.engine.mesh import Mesh
    from world3d.engine.picking import Picker
    from world3d.engine.renderer import Renderer
    from world3d.engine.scene import Node, Scene
    from world3d.engine import shaders as shaders_mod
    return dict(EngineApp=EngineApp, engine_parse_args=engine_parse_args,
                OrbitCamera=OrbitCamera, LightEnvironment=LightEnvironment,
                GLTF=GLTF, Material=Material,
                Mesh=Mesh, Picker=Picker, Renderer=Renderer, Node=Node, Scene=Scene,
                shaders=shaders_mod)


def parse_viewer_args(argv=None):
    """在 EngineApp 参数表上追加本查看器的 --system/--max-nodes/--names。"""
    argv = list(sys.argv[1:] if argv is None else argv)
    own = argparse.ArgumentParser(add_help=False)
    own.add_argument("--system", default="reference", help="系统键（assets/<key>.glb）")
    own.add_argument("--max-nodes", type=int, default=32, help="首批构建节点上限（P12 闸门）")
    own.add_argument("--names", default="", help="逗号分隔的节点名（精确/sanitize 双形态）")
    own.add_argument("--clip", action="store_true", help="启动时启用剖面裁剪")
    own.add_argument("--clip-offset", type=float, default=0.0, help="剖面平面偏移")
    own.add_argument("--quiz", action="store_true", help="启动时进入测验模式")
    ns, rest = own.parse_known_args(argv)
    E = _load_engine()
    ns.engine_args = E["engine_parse_args"](rest)
    ns.names = [n.strip() for n in ns.names.split(",") if n.strip()]
    return ns


def make_app_class(E):
    class AnatomyApp(E["EngineApp"]):
        TITLE = "anatomy3d - open anatomy viewer"
        HELP = ("drag=orbit  wheel=zoom  click=pick/answer  I=isolate  A=show all  "
                "L=load more  H=hide  C=clip  [ ]=rotate clip  - =move clip  "
                "Q=quiz  ESC=quit")
        SHOW_HUD = True
        SHOTS = ((2.0, "docs/viewer_smoke.png"),)

        def __init__(self, ns):
            self.ns = ns
            super().__init__(width=ns.engine_args.width,
                             height=ns.engine_args.height, args=ns.engine_args)

        def setup(self):
            repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            system = self.ns.system
            glb = os.path.join(repo, "assets", f"{system}.glb")
            manifest_path = os.path.join(repo, "assets", f"{system}.manifest.json")
            if not os.path.exists(glb):
                raise SystemExit(f"GLB not found: {glb}")
            _patch_clip_shader(E)        # 必须在 renderer.program('pbr') 首次调用之前
            self.doc = E["GLTF"].load(glb)
            self.manifest = {}
            # 优先全图谱三语富化清单（M3），退回系统清单
            enriched_path = os.path.join(repo, "assets", "anatomy.zh.manifest.json")
            candidates = [enriched_path, manifest_path]
            for path in candidates:
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        loaded = json.load(f)
                    if any(sys["name"] == system for sys in loaded.get("systems", [])):
                        self.manifest = loaded
                        break
            if not self.manifest and os.path.exists(manifest_path):
                with open(manifest_path, encoding="utf-8") as f:
                    self.manifest = json.load(f)
            self.knowledge = Knowledge()
            self.quiz = None
            self.clip_enabled = bool(self.ns.clip)
            self.clip_yaw = 0.0
            self.clip_offset = float(self.ns.clip_offset)
            self.last_quiz_message = ""
            self.lazy = LazyAtlas(self.doc.json, self.manifest, self.ns.max_nodes)
            self.scene = E["Scene"](name=f"anatomy:{system}")
            self.environment = E["LightEnvironment"](sky_intensity=0.55,
                                                     sun_intensity=1.4,
                                                     ibl_intensity=0.6)
            self.environment.bake()              # GL 上下文就绪后烘焙 IBL（setup 阶段）
            self.scene.environment = self.environment
            self.renderer = E["Renderer"](self.window.width, self.window.height,
                                          environment=self.environment)
            self.camera = E["OrbitCamera"](target=(0.0, 0.0, 0.0), yaw=35.0,
                                           pitch=18.0, dist=2.8,
                                           pitch_range=(-80.0, 89.0),
                                           dist_range=(0.15, 60.0))
            self.picker = E["Picker"]()
            self.selected = None              # Node
            self._nodes: dict[str, object] = {}
            self._build(self.ns.names)
            if self.ns.quiz:
                self.quiz = Quiz(self.manifest, seed=7)
                self.quiz.next()

        def _clip_vec4(self):
            import math
            if not self.clip_enabled:
                return (0.0, 0.0, 0.0, 1e6)
            r = math.radians(self.clip_yaw)
            return (math.cos(r), 0.0, math.sin(r), self.clip_offset)

        def _build(self, names=None):
            """只构建选中节点（P12 核心），返回新增数量。"""
            selected, unmatched, skipped = self.lazy.plan(names=names or None)
            added = 0
            for idx, name in selected:
                if self.lazy.is_built(idx):
                    continue
                node_json = self.doc.json["nodes"][idx]
                mesh_index = node_json.get("mesh")
                if mesh_index is None:
                    continue
                prims = self.doc.json["meshes"][mesh_index].get("primitives", [])
                struct = self.lazy.structure_for_node(idx) or {}
                # 未映射节点按所属系统兜底着色（例如心血管未命中的血管也应偏红）
                fallback = {"cardiovascular": "vessel", "skeletal": "bone",
                            "arthrology": "bone", "muscular": "muscle",
                            "nervous": "nerve", "visceral": "organ",
                            "regions": "region"}.get(self.ns.system, "other")
                material = E["Material"](
                    name=name,
                    base_color=KIND_COLORS.get(struct.get("kind", fallback)),
                    roughness=0.72,
                    double_sided=True,
                )
                for p in prims:
                    md = self.doc.primitive_meshdata(p)   # 只构建这个节点
                    mesh = E["Mesh"](md, self.renderer.program("pbr"), material, name=name)
                    t, r, s = self.doc.node_trs(idx)
                    child = E["Node"](name=name, translation=t, rotation=r, scale=s,
                                      drawable=mesh)
                    self.scene.add(child)
                    self._nodes[name] = child
                    added += 1
                self.lazy.mark_built(idx)
            self.scene.invalidate()
            self.scene.update()
            if added:
                self._auto_frame()
            print(f"viewer: built={self.lazy.built_count()} added={added} "
                  f"total_mesh_nodes={len(self.lazy.mesh_nodes)}")
            if unmatched:
                print(f"unmatched names: {len(unmatched)} (first={unmatched[0]})")
            return added

        def dispose(self):
            stats = getattr(self.renderer, "stats", {})
            print(f"viewer: close stats={stats}")

        def _auto_frame(self):
            """按已构建节点的 AABB 自动取景（避免大场景里小结构只占几个像素）。"""
            boxes = [d.world_aabb for d in self.scene.drawables()
                     if getattr(d, "world_aabb", None) is not None]
            if not boxes:
                return
            lo = [min(b.min[i] for b in boxes) for i in range(3)]
            hi = [max(b.max[i] for b in boxes) for i in range(3)]
            center = tuple((lo[i] + hi[i]) * 0.5 for i in range(3))
            radius = max(0.01, 0.5 * max(hi[i] - lo[i] for i in range(3)))
            self.camera.set_target(center)
            self.camera.dist = max(0.25, radius * 2.6)

        def update(self, dt):
            pass    # 解剖观察需要静态视角：不自动环绕（OrbitCamera.advance 默认 8°/s）

        def render(self):
            from pyglet.math import Vec4
            program = self.renderer.program("pbr")
            if "uClipPlane" in program.uniforms:
                program["uClipPlane"] = Vec4(*self._clip_vec4())
            self.renderer.render(self.camera, self.scene, window=self.window)

        def status_text(self):
            sel = f" | picked={self.selected.name}" if self.selected else ""
            clip = " | CLIP on" if self.clip_enabled else ""
            if self.quiz is not None and self.quiz.current:
                quiz = f" | Q: {self.quiz.current['prompt']} [{self.quiz.status()}]"
            else:
                quiz = ""
            msg = f" | {self.last_quiz_message}" if self.last_quiz_message else ""
            return (f"{self.ns.system}: built {self.lazy.built_count()}/"
                    f"{len(self.lazy.mesh_nodes)}{sel}{clip}{quiz}{msg}")

        def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
            self.camera.orbit(dx, dy)

        def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
            self.camera.zoom(scroll_y)

        def on_mouse_press(self, x, y, button, modifiers):
            hit = self.picker.pick(x, y, self.window.width, self.window.height,
                                   self.camera, self.scene)
            if not hit:
                return
            name = getattr(hit.drawable, "name", "")
            node = self._nodes.get(name)
            if node is None:
                return
            if self.selected is not None:
                self.selected.drawable.material.emissive = (0.0, 0.0, 0.0)
            self.selected = node
            node.drawable.material.emissive = (0.18, 0.14, 0.04)
            idx = self._index_for_name(name)
            struct = self.lazy.structure_for_node(idx) if idx is not None else None
            if struct:
                names = struct.get("names", {})
                label = " / ".join(x for x in (names.get("zh"), names.get("en"),
                                               names.get("la")) if x)
                if self.hud:
                    self.hud.set_status(label + (f" — {struct['definition']['zh']}"
                                                 if struct.get("definition", {}).get("zh") else ""))
                if self.quiz is not None and self.quiz.current:
                    result = self.quiz.answer(struct["id"])
                    self.last_quiz_message = result["message"] + f" [{result['score']}]"
                    self.quiz.next()

        def _index_for_name(self, name):
            for i, n in self.lazy.mesh_nodes:
                if n == name or sanitize_node(n) == name:
                    return i
            return None

        def on_key(self, symbol, modifiers):
            from pyglet.window import key
            if symbol == key.L:
                added = self._build()
                if self.hud:
                    self.hud.set_status(f"loaded +{added} nodes")
            elif symbol == key.I and self.selected is not None:
                for name, node in self._nodes.items():
                    node.visible = (node is self.selected)
                self.scene.invalidate()
            elif symbol == key.A:
                for node in self._nodes.values():
                    node.visible = True
                self.scene.invalidate()
            elif symbol == key.H and self.selected is not None:
                self.selected.visible = not self.selected.visible
                self.scene.invalidate()
            elif symbol == key.C:
                self.clip_enabled = not self.clip_enabled
            elif symbol == key.BRACKETLEFT:
                self.clip_yaw -= 15.0
            elif symbol == key.BRACKETRIGHT:
                self.clip_yaw += 15.0
            elif symbol == key.MINUS:
                self.clip_offset -= 0.05
            elif symbol == key.EQUAL:
                self.clip_offset += 0.05
            elif symbol == key.Q:
                if self.quiz is None:
                    self.quiz = Quiz(self.manifest, seed=7)
                self.quiz.next()
                self.last_quiz_message = ""
    return AnatomyApp


def main(argv=None):
    import pyglet
    from pyglet import app as pyglet_app
    ns = parse_viewer_args(argv)
    E = _load_engine()
    app_cls = make_app_class(E)
    instance = app_cls(ns)
    engine_args = ns.engine_args
    if engine_args.bench is not None:
        pyglet.clock.schedule_once(lambda dt: instance.close(), engine_args.bench + 0.5)
        print(f"[bench] running {engine_args.bench}s ...")
    elif engine_args.smoke is not None:
        pyglet.clock.schedule_once(lambda dt: instance.close(), engine_args.smoke)
        print(f"[smoke] auto-close in {engine_args.smoke}s")
    pyglet_app.run(interval=0 if engine_args.bench is not None else 1 / max(1e-3, engine_args.fps))
    if engine_args.bench is not None:
        # 不用 EngineApp.bench_report()：3dworld 上游 perf.cpu.report() 返回 6 值
        # 而 bench_report 解包 7 值（问题记录 P16）；这里直接读渲染器统计。
        print(f"[bench] render_stats={instance.renderer.stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
