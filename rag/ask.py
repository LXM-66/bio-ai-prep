"""问一句 → 检索 → 让大模型带引用回答。这是 RAG 的"用"的那一端。

用法：
    python rag/ask.py "单细胞测序怎么研究肿瘤异质性？"
    python rag/ask.py --k 8 "空间转录组和单细胞测序的区别"
    python rag/ask.py --search-only "TP53 突变"        # 只看检索结果，不调大模型

依赖：llm_client/llm.py（复用其中的 API 封装与成本统计）
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "llm_client"))
from llm import DeepSeek, DeepSeekError, load_env  # noqa: E402
from query import has_cjk, rewrite_query           # noqa: E402
from store import BM25Index                        # noqa: E402

INDEX = HERE / "index" / "bm25.json"
SYSTEM = ("你是生物医药文献助手。只依据用户给的【资料】回答；"
          "每条结论后面用 [编号] 标注来源；资料里没有的内容直接说「资料里没有提到」，不要编。"
          "用中文回答，专业术语保留英文原词。简洁，不超过 6 句。"
          + "回答末尾不重复罗列资料原文。")


def build_prompt(question, hits, idx):
    lines = []
    for n, (i, score) in enumerate(hits, 1):
        m = idx.meta[i]
        lines.append(f"[{n}] (PMID {m['pmid']}, {m['year']}, {m['journal']})\n{idx.chunks[i]}")
    return f"【资料】\n" + "\n\n".join(lines) + f"\n\n【问题】{question}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*", help="问题（不填则交互输入）")
    ap.add_argument("--k", type=int, default=5, help="检索几块")
    ap.add_argument("--search-only", action="store_true", help="只检索，不调用大模型")
    args = ap.parse_args()

    if not INDEX.exists():
        print("索引不存在，先跑：python rag/build_index.py")
        return 1
    idx = BM25Index.load(INDEX)
    print(f"索引：{len(idx.chunks)} 块，来自 {idx.source}（建于 {idx.built_at}）")

    question = " ".join(args.question) or input("问题> ").strip()

    bot = None
    if not args.search_only:
        load_env()
        try:
            bot = DeepSeek(model="deepseek-flash")
        except DeepSeekError as e:
            print(f"（没有可用 key，只做检索：{e}）")

    query = question
    if has_cjk(question):
        if bot:
            query = rewrite_query(bot, question)
            print(f"\n检索词（中文问题自动改写为英文关键词）：{query}")
        else:
            print("\n提示：语料是英文、检索是词面匹配（BM25），中文问题要先改写成英文关键词 ——"
                  "去掉 --search-only 就会自动改写。")

    hits = idx.search(query, k=args.k)
    if not hits:
        print("没有检索到任何相关内容 —— 换种问法，或把 --k 调大")
        return 0

    print(f"\n检索到 {len(hits)} 块（BM25 分数）：")
    for n, (i, score) in enumerate(hits, 1):
        m = idx.meta[i]
        print(f"  [{n}] {score:>6.2f}  PMID {m['pmid']}  {m['title'][:70]}")
    if args.search_only:
        return 0

    if bot is None:
        print("\n（没有可用 key，跳过生成；检索部分已经可用。）")
        return 0

    print("\n回答> ", end="", flush=True)
    try:
        for piece in bot.stream([{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": build_prompt(question, hits, idx)}],
                                temperature=0.2):
            print(piece, end="", flush=True)
    except DeepSeekError as e:
        print(f"\n[调用失败] {e}")
        return 1

    u = bot.last_usage
    print(f"\n\n引用来源：")
    for n, (i, score) in enumerate(hits, 1):
        m = idx.meta[i]
        print(f"  [{n}] PMID {m['pmid']}（{m['year']}）{m['title'][:80]}｜BM25 {score}")
    print(f"消耗 {u['prompt_tokens']} + {u['completion_tokens']} tokens"
          f"（缓存命中 {u['cache_hit_tokens']}）｜{u['seconds']}s｜{u['cost_cny']:.6f} 元")
    return 0


if __name__ == "__main__":
    sys.exit(main())
