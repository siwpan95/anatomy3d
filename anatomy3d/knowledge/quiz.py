# -*- coding: utf-8 -*-
"""M4 测验逻辑（纯 stdlib，无 GL/UI 依赖）。

按结构清单出题：“请指出 <中文名>（<拉丁名>）”，四个选项来自同 kind 的其它结构，
点击模型（或传入结构 id）作答。题序由 seed 决定，可复现。
"""
from __future__ import annotations

import random

from .zh import Knowledge


class Quiz:
    def __init__(self, manifest: dict, seed: int = 7, options: int = 4):
        knowledge = Knowledge()
        self.pool = []
        for system in manifest.get("systems", []):
            for s in system.get("structures", []):
                s = dict(s)                       # 不改调用方的 manifest
                names = dict(s.get("names") or {})
                zh = names.get("zh") or knowledge.zh_for(names.get("en", ""))
                if zh:
                    names["zh"] = zh
                    s["names"] = names
                    if not s.get("definition"):
                        definition = knowledge.definition_for(names.get("en", ""))
                        if definition:
                            s["definition"] = {"zh": definition}
                    self.pool.append(s)
        self.pool.sort(key=lambda s: s["id"])
        self.rng = random.Random(seed)
        self.options = max(2, int(options))
        self.total = 0
        self.correct = 0
        self.current = None

    def next(self):
        if not self.pool:
            return None
        answer = self.rng.choice(self.pool)
        kind = answer.get("kind")
        candidates = [s for s in self.pool if s["id"] != answer["id"] and s.get("kind") == kind]
        if len(candidates) < self.options - 1:
            candidates = [s for s in self.pool if s["id"] != answer["id"]]
        picks = self.rng.sample(candidates, min(self.options - 1, len(candidates)))
        opts = picks + [answer]
        self.rng.shuffle(opts)
        self.current = {
            "answer_id": answer["id"],
            "prompt": f"请指出：{answer['names']['zh']}（{answer['names'].get('la', '')}）",
            "options": [
                {"id": s["id"], "label": s["names"].get("zh") or s["names"]["en"]}
                for s in opts
            ],
        }
        return self.current

    def answer(self, chosen_id: str) -> dict:
        if not self.current:
            raise RuntimeError("quiz.next() must be called first")
        ok = chosen_id == self.current["answer_id"]
        self.total += 1
        self.correct += int(ok)
        answer_struct = next(s for s in self.pool if s["id"] == self.current["answer_id"])
        label = answer_struct["names"].get("zh") or answer_struct["names"]["en"]
        message = ("正确" if ok else f"错误，正确答案：{label}")
        if answer_struct.get("definition", {}).get("zh"):
            message += " — " + answer_struct["definition"]["zh"]
        return {"correct": ok, "message": message,
                "score": f"{self.correct}/{self.total}"}

    def status(self) -> str:
        return f"{self.correct}/{self.total}"
