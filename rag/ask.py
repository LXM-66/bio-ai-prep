"""命令行问答：中文提问 → 检索 → 带引用的中文回答。

用法：
    python rag/ask.py "单细胞测序怎么用来研究肿瘤内部的细胞异质性？"
    python rag/ask.py "TP53 的功能是什么" --k 8          # 多取几块资料
    python rag/ask.py --search-only "spatial transcriptomics"   # 只看检索结果，不调大模型

逻辑都在 pipeline.Engine 里，这个脚本只负责参数与打印。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import Engine      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", help="要问的问题")
    ap.add_argument("--k", type=int, default=5, help="喂给模型的资料块数")
    ap.add_argument("--search-only", action="store_true", help="只检索，不生成回答")
    args = ap.parse_args()

    eng = Engine(need_bot=not args.search_only)
    if eng.bot_error:
        print(f"（没有可用 API key，只做检索：{eng.bot_error}）")

    r = eng.ask(args.question, k=args.k)
    if r["query"].strip() != args.question.strip():
        print(f"\n检索词（中文问题自动改写为英文关键词）：{r['query']}")
    if not r["hits"]:
        print("检索不到任何内容 —— 换个说法，或先跑 python rag/build_index.py")
        return 1

    print(f"\n检索到 {len(r['hits'])} 块：")
    for n, h in enumerate(r["hits"], 1):
        title = h["title"][:58] + ("…" if len(h["title"]) > 58 else "")
        print(f"  [{n}] {h['score']:>6.2f}  {h['source']} {h['sid']}  {title}")

    if r["answer"]:
        print(f"\n回答> {r['answer']}\n")
        u = r["usage"]
        print(f"消耗 {u['prompt_tokens']} + {u['completion_tokens']} tokens"
              f"（缓存命中 {u['cache_hit_tokens']}）｜{u['seconds']:.2f}s｜{r['cost']:.6f} 元")
    return 0


if __name__ == "__main__":
    sys.exit(main())
