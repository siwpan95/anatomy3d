# -*- coding: utf-8 -*-
"""anatomy3d.contracts —— 跨模块契约层（零依赖）。"""
from .manifest import MANIFEST_VERSION, StructureEntry, validate_manifest

__all__ = ["MANIFEST_VERSION", "StructureEntry", "validate_manifest"]
