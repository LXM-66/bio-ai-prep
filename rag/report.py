"""按主题生成中文速读报告 —— 把检索问答能力变成一个能交付的东西。

用法：
    python rag/report.py "单细胞测序在肿瘤免疫治疗中的应用" --limit 8
    python rag/report.py "spatial transcriptomics" --limit 6 --days 90
    python rag/report.py "TP53 突变" --from-index --limit 5     # 用本地语料，不联网取新文献

产物：
    rag/reports/<主题>.md      一份可直接发出去的中文报告

成本：每条资料一次摘要调用，加一次综述调用；实测单条约 0.002 元。
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pipeline import REPORT_DIR, Engine      # noqa: E402


def slug(text: str) -> str:
    """主题 → 文件名（去掉不能做文件名的字符）。"""
    import re
    return re.sub(r'[\\/:*?"<>|\s]+', "_", text).strip("_")[:50] or "report"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--limit", type=int, default=8, help="资料条数")
    ap.add_argument("--days", type=int, default=0, help="只看最近 N 天（0 = 不限）")
    ap.add_argument("--from-index", action="store_true", help="用本地索引检索，不联网取新文献")
    ap.add_argument("--out", default="", help="输出路径（默认 rag/reports/<主题>.md）")
    args = ap.parse_args()

    eng = Engine(index_path=HERE / "index" / "bm25.json")
    if eng.bot_error:
        print(f"需要 API key 才能生成报告：{eng.bot_error}")
        return 1

    print(f"主题：{args.topic}")
    r = eng.build_report(args.topic, limit=args.limit, days=args.days or None,
                         from_index=args.from_index, on_progress=print)
    if r.get("error"):
        print(r["error"])
        return 1
    if r["search_term"].strip() != args.topic.strip():
        print(f"检索式（中文主题自动改写为英文关键词）：{r['search_term']}")

    out = Path(args.out) if args.out else REPORT_DIR / f"{slug(args.topic)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(r["markdown"], encoding="utf-8")
    print(f"\n报告已生成：{out}（{r['count']} 条｜{r['cost']:.6f} 元）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
