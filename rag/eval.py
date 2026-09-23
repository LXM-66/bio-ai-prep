"""检索质量评测：hit@k 与 MRR，并做两组对照实验。

为什么要评测：换块长、换分词、换检索算法时，凭"感觉好像好一点"迟早翻车 ——
这些改动都能让 top1 的分数变高，但分数高不等于把正确的资料排到了前面。

指标：
    hit@k   正确的那块出现在前 k 条里的比例（k=1/3/5/10）
    MRR     正确块排名的倒数均值（排第 1 得 1.0，排第 3 得 0.33），惩罚"排得靠后"
    文档级  同一篇文献/同一条记录里的任意一块命中就算命中（只看块级会低估实际效果）

两组对照：
    ① 查询改写值不值 —— 中文原问题直接检索 vs 改写成英文关键词
    ② 分词方案 —— 中文 bigram vs 改之前的单字切分

改写结果会缓存进 eval_set.jsonl，重复评测不再花第二次钱（--refresh-rewrites 可强制重算）。

用法：
    python rag/eval.py
    python rag/eval.py --refresh-rewrites
    python rag/eval.py --no-ablation       # 只评当前方案
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "llm_client"))
import store                            # noqa: E402
from pipeline import INDEX, Engine      # noqa: E402

EVAL_SET = HERE / "eval_set.jsonl"
KS = (1, 3, 5, 10)


def single_char_tokenize(text: str) -> list[str]:
    """改动之前的方案：中文按单字切。用于对照实验。"""
    text = text.lower()
    return re.findall(r"[a-z0-9][a-z0-9\-\.]*", text) + re.findall(r"[\u4e00-\u9fff]", text)


def evaluate(idx, items: list[dict], query_field: str, topk: int = 10) -> dict:
    chunk_hits = {k: 0 for k in KS}
    doc_hits = {k: 0 for k in KS}
    rr_sum, miss = 0.0, []
    for it in items:
        hits = idx.search(it[query_field], k=topk)
        chunk_rank = next((r for r, (i, _) in enumerate(hits, 1) if i == it["gold_chunk"]), None)
        gold_key = (it["gold_source"], it["gold_sid"])
        doc_rank = next((r for r, (i, _) in enumerate(hits, 1)
                         if (idx.meta[i].get("source", ""), idx.meta[i].get("sid", "")) == gold_key), None)
        if chunk_rank:
            for k in KS:
                chunk_hits[k] += chunk_rank <= k
            rr_sum += 1 / chunk_rank
        else:
            miss.append(it["q"])
        if doc_rank:
            for k in KS:
                doc_hits[k] += doc_rank <= k
    n = max(len(items), 1)
    return {"n": len(items), "chunk": {k: chunk_hits[k] / n for k in KS},
            "doc": {k: doc_hits[k] / n for k in KS}, "mrr": rr_sum / n,
            "miss": len(miss), "miss_examples": miss[:3]}


def row(label: str, m: dict, mrr: float = 0.0) -> str:
    return (f"  {label:26}" + "  ".join(f"{m[k]:6.1%}" for k in KS) + f"   {mrr:.3f}")


def header() -> str:
    return f"  {'方案':26}" + "  ".join(f"hit@{k:<3}" for k in KS) + "   MRR"


def ensure_rewrites(eng, items: list[dict], refresh: bool) -> float:
    todo = [it for it in items if refresh or not it.get("rewritten")]
    if not todo:
        return 0.0
    if eng.bot_error:
        print(f"需要 API key 才能改写：{eng.bot_error}")
        for it in todo:
            it["rewritten"] = it["q"]
        return 0.0
    print(f"改写 {len(todo)} 个问题为英文检索词…")
    cost = 0.0
    for it in todo:
        it["rewritten"] = eng._rewrite(it["q"])
        cost += eng.bot.last_usage["cost_cny"]
    EVAL_SET.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in items) + "\n", encoding="utf-8")
    return cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-rewrites", action="store_true", help="强制重新改写（默认用缓存）")
    ap.add_argument("--no-ablation", action="store_true", help="只评当前方案")
    ap.add_argument("--topk", type=int, default=10)
    args = ap.parse_args()

    if not EVAL_SET.exists():
        print(f"没有评测集 {EVAL_SET}，先跑：python rag/make_eval.py --limit 30")
        return 1
    items = [json.loads(line) for line in EVAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()]

    eng = Engine(need_bot=True)
    idx = eng.idx
    cost = ensure_rewrites(eng, items, args.refresh_rewrites)
    items = [it for it in items if it.get("rewritten") and it.get("gold_chunk") is not None]
    if not items:
        print("评测集里没有可用问题")
        return 1

    print(f"\n语料 {len(idx.chunks)} 块｜索引 {INDEX.name}｜题目 {len(items)} 道"
          + (f"｜改写花费 {cost:.4f} 元" if cost else "（改写用缓存，未花钱）"))
    results = [("当前：改写 + bigram", evaluate(idx, items, "rewritten", args.topk)),
               ("对照：不改写（中文直查）", evaluate(idx, items, "q", args.topk))]

    if not args.no_ablation:
        keep = store.tokenize
        store.tokenize = single_char_tokenize               # 旧分词重建索引
        legacy = store.BM25Index().build(idx.chunks, idx.meta)
        store.tokenize = keep
        results.append(("对照：不改写 + 单字分词", evaluate(legacy, items, "q", args.topk)))
        results.append(("对照：改写 + 单字分词", evaluate(legacy, items, "rewritten", args.topk)))

    print("\n块级命中：")
    print(header())
    for label, r in results:
        print(row(label, r["chunk"], r["mrr"]))
    print("\n文档级命中（同一篇记录里任意一块命中就算命中）：")
    print(header())
    for label, r in results:
        print(row(label, r["doc"], r["mrr"]))

    best = results[0][1]
    if best["miss_examples"]:
        print("\n当前方案完全没召回的样例：" + "；".join(best["miss_examples"]))

    # 落盘一份结果，供 README / Web 界面直接展示（省得为了看数字重新跑一遍评测）
    (HERE / "eval_result.json").write_text(json.dumps(
        {"题目数": len(items), "语料块数": len(idx.chunks),
         "结果": [{"方案": label, **{f"块级 hit@{k}": round(r["chunk"][k], 4) for k in KS},
                   **{f"文档级 hit@{k}": round(r["doc"][k], 4) for k in KS},
                   "MRR": round(r["mrr"], 4)} for label, r in results]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
