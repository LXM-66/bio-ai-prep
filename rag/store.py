"""检索层：BM25 索引（这一层就是"向量库"的位置）。

为什么先用 BM25：DeepSeek 没有 embedding 接口，本地跑向量模型要下几百 MB。
BM25 是纯统计的词面检索，零依赖、快、可解释 —— 先把"检索 + 引用"的整条链路跑通，
以后要换成语义向量检索，只需替换 `search()` 的打分方式，上层代码完全不用动。

BM25 直觉：一个词在当前文档里出现得越多分越高（tf），但这个词在整个语料里越常见分越低（idf），
最后按文档长度做惩罚（长文档不会因为词多就占便宜）。
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

from text import tokenize


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.chunks: list[str] = []
        self.meta: list[dict] = []
        self.tfs: list[Counter] = []
        self.lens: list[int] = []
        self.df: Counter = Counter()
        self.avgdl: float = 0.0

    # ── 建索引 ──────────────────────────────────────────────────────────
    def build(self, chunks: list[str], meta: list[dict] | None = None):
        self.chunks = list(chunks)
        self.meta = list(meta) if meta else [{} for _ in chunks]
        self.tfs = [Counter(tokenize(c)) for c in self.chunks]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())                      # 每个词在几篇文档里出现
        self.df = df
        return self

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (len(self.chunks) - n + 0.5) / (n + 0.5))

    # ── 检索 ────────────────────────────────────────────────────────────
    def search(self, query: str, k: int = 5) -> list[tuple[int, float]]:
        """返回 [(chunk序号, 分数), ...]，按分数从高到低，只留命中的。"""
        scores = [0.0] * len(self.chunks)
        for term in set(tokenize(query)):
            if term not in self.df:
                continue
            idf = self._idf(term)
            for i, tf in enumerate(self.tfs):
                f = tf.get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avgdl)
                scores[i] += idf * f * (self.k1 + 1) / denom
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [(i, round(scores[i], 4)) for i in order if scores[i] > 0]

    # ── 存取 ────────────────────────────────────────────────────────────
    def save(self, path: Path, source: str = ""):
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "params": {"k1": self.k1, "b": self.b},
            "chunks": self.chunks,
            "meta": self.meta,
            "tfs": [dict(tf) for tf in self.tfs],
            "lens": self.lens,
            "df": dict(self.df),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        idx = cls(**d["params"])
        idx.chunks, idx.meta = d["chunks"], d["meta"]
        idx.tfs = [Counter(tf) for tf in d["tfs"]]
        idx.lens, idx.df = d["lens"], Counter(d["df"])
        idx.avgdl = sum(idx.lens) / len(idx.lens) if idx.lens else 0.0
        idx.built_at, idx.source = d.get("built_at", ""), d.get("source", "")
        return idx


if __name__ == "__main__":                            # 自测：内置三条语料
    demo = ["TP53 编码 p53 蛋白，是重要的抑癌基因。",
            "BRCA1 参与 DNA 双链断裂修复。",
            "单细胞 RNA 测序可以解析肿瘤内部的细胞异质性。"]
    idx = BM25Index().build(demo)
    for q in ["抑癌基因 p53", "single-cell 细胞异质性", "今天天气怎么样"]:
        print(q, "→", idx.search(q, k=2) or "（无命中）")
