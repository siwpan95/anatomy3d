# anatomy3d v1.0.0 · 开放数据人体解剖 3D 教育查看器（M0-M4 全通）

首个完整版本。

- M1 资产管线：Z-Anatomy/BodyParts3D 开放数据 → Blender 无头导出 9 系统 GLB + 全图谱 5954 结构三语 manifest（契约 PASS）
- M2 查看器：按节点懒加载（心血管 8/1092 节点 4.8s 启动）、拾取/显隐/隔离/自动取景、1-9 系统切换
- M3 知识层：中文 2547 / 拉丁 5954 / 释义 39（三语 HUD）
- M4 剖面裁剪（C/[ ]/-/=）+ quiz 点选判分（Q）
- 代码 MIT；解剖数据沿 Z-Anatomy/BodyParts3D CC BY-SA（见 NOTICE）
- 自检：python selfcheck.py（exit 0）；单测 19/19
