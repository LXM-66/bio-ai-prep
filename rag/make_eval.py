"""自动生成评测集：从索引里抽样，让模型为每一块资料写一个"它才能回答"的问题。

思路：如果问题是从某一块资料反推出来的，那么这块资料就是标准答案（gold）。
评测时看检索能不能把这块（或这篇/这条记录）捞回来，就能量化检索质量，
而不必人工标注几百条 —— 人工标注当然是更好的，但成本高得多，先用自动集起步。

注意（要写进报告的局限）：自动生成的问题带有"出题人偏见" —— 用词往往贴着原文，
真实用户的问题会更口语、更绕。所以这套指标主要用来**横向比较改动**
（换分词、换块长、换检索算法），而不是当作绝对准确率。

用法：
    python rag/make_eval.py --limit 30                 # 生成 30 道题 → rag/eval_set.jsonl
    python rag/make_eval.py --limit 10 --per-source 1   # 每个来源各抽几条
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "llm_client"))
from pipeline import INDEX, Engine      # noqa: E402

OUT = HERE / "eval_set.jsonl"
ASK_SYSTEM = ("你会看到一段生物医药资料。请写一个「只有这段资料能回答」的中文问题，"
              "20 字以内，尽量具体（带上关键基因/方法/结论）。只输出问题本身，"
              "不要提及「这段资料」，不要给答案，不要标点以外的任何解释。")


def sample_indices(idx, limit: int, per_source: int, seed: int) -> list[int]:
    """按来源分层抽样：保证每个来源都被考到，而不是全被大来源占满。"""
    rng = random.Random(seed)
    by_source: dict[str, list[int]] = {}
    for i, m in enumerate(idx.meta):
        if i % 3:                      # 同一记录往往切出好几块，抽稀一下避免问题雷同
            continue
        by_source.setdefault(m.get("source", "?"), []).append(i)
    picked: list[int] = []
    for source, idxs in by_source.items():
        rng.shuffle(idxs)
        picked += idxs[:per_source]
    rng.shuffle(picked)
    return picked[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30, help="生成多少道题")
    ap.add_argument("--per-source", type=int, default=4, help="每个来源最多抽多少条")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    eng = Engine(need_bot=True)
    if eng.bot_error:
        print(f"需要 API key 才能生成评测集：{eng.bot_error}")
        return 1

    idx = eng.idx
    picked = sample_indices(idx, args.limit, args.per_source, args.seed)
    print(f"从 {len(idx.chunks)} 块里抽样 {len(picked)} 块出题…")

    rows, cost = [], 0.0
    for n, i in enumerate(picked, 1):
        chunk = idx.chunks[i]
        m = idx.meta[i]
        user = f"资料来源：{m.get('source', '?')} {m.get('sid', '')}\n资料标题：{m.get('title', '')}\n资料正文：{chunk}"
        q = eng.bot.chat([{"role": "system", "content": ASK_SYSTEM},
                          {"role": "user", "content": user}], temperature=0.7).strip()
        cost += eng.bot.last_usage["cost_cny"]
        q = q.strip('"“”「」 ')
        rows.append({"q": q, "gold_chunk": i, "gold_source": m.get("source", ""),
                     "gold_sid": m.get("sid", ""), "gold_title": m.get("title", "")})
        print(f"  [{n}/{len(picked)}] {q}")
        time.sleep(0.2)

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"\n写入 {OUT}（{len(rows)} 道题｜{cost:.4f} 元）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
