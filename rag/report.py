"""按主题生成中文文献速读报告 —— 把检索问答能力变成一个能交付的东西。

用法：
    python rag/report.py "单细胞测序在肿瘤免疫治疗中的应用" --limit 8
    python rag/report.py "spatial transcriptomics" --limit 6 --days 90
    python rag/report.py "TP53 突变" --from-index --limit 5     # 改用已建索引检索（不联网取新文献）

产物：
    rag/reports/<主题>.md      一份可直接发出去的中文报告

成本：每篇文章一次摘要调用，加一次综述调用；实测单篇约 0.002 元。
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "llm_client"))
from fetch_pubmed import EFETCH, fetch, parse_articles, search_pmids  # noqa: E402
from llm import DeepSeek, DeepSeekError, load_env      # noqa: E402
from query import has_cjk, rewrite_query               # noqa: E402
from store import BM25Index                            # noqa: E402

INDEX = HERE / "index" / "bm25.json"
OUT_DIR = HERE / "reports"

SUMMARY_SYSTEM = ("你是一名生物医药领域的科研助理。用中文把这篇文献的摘要总结成 2–3 句，"
                  "只讲做了什么、发现了什么（带上关键数字或结论），不要评价、不要客套、不要罗列方法细节。")
REVIEW_SYSTEM = ("你是生物医药领域的科研助理。下面是一组文献的中文要点，"
                 "请写 3–5 条「这个方向现在到什么程度了」的中文综述，每条后面用 [编号] 标注依据的文献。"
                 "只依据给定材料，不要引入外部知识，材料没提到的不写。")


def slug(text: str) -> str:
    """主题转文件名（去掉不能做文件名的字符）。"""
    return re.sub(r'[\\/:*?"<>|\s]+', "_", text).strip("_")[:50] or "report"


def summarize(bot, art):
    """一篇文献 → 中文要点。"""
    user = f"标题：{art['title']}\n摘要：{art['abstract']}"
    return bot.chat([{"role": "system", "content": SUMMARY_SYSTEM},
                     {"role": "user", "content": user}], temperature=0.3).strip()


def from_index(topic, limit):
    """不联网：从已建索引里按主题检索，返回文章级结果。"""
    idx = BM25Index.load(INDEX)
    hits = idx.search(topic, k=limit * 3)               # 多取一些，后面按 PMID 去重
    seen, arts = set(), []
    for i, _ in hits:
        m = idx.meta[i]
        if m["pmid"] in seen:
            continue
        seen.add(m["pmid"])
        arts.append({"pmid": m["pmid"], "title": m["title"], "abstract": idx.chunks[i],
                     "journal": m["journal"], "year": m["year"]})
        if len(arts) >= limit:
            break
    return arts


def from_pubmed(topic, limit, days):
    """联网：按主题取最新文献。"""
    pmids = search_pmids(topic, limit, days=days, sort="pub date")
    if not pmids:
        return []
    import urllib.parse
    url = f"{EFETCH}?" + urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"})
    return parse_articles(fetch(url))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--limit", type=int, default=8, help="文献数量")
    ap.add_argument("--days", type=int, default=0, help="只看最近 N 天（0 = 不限）")
    ap.add_argument("--from-index", action="store_true", help="从已有索引检索，不联网取新文献")
    ap.add_argument("--out", default="", help="输出路径（默认 rag/reports/<主题>.md）")
    args = ap.parse_args()

    load_env()
    try:
        bot = DeepSeek(model="deepseek-flash")
    except DeepSeekError as e:
        print(f"需要 API key 才能生成报告：{e}")
        return 1

    print(f"主题：{args.topic}")
    search_term = args.topic
    if has_cjk(args.topic):
        search_term = rewrite_query(bot, args.topic)
        print(f"检索式（中文主题自动改写为英文关键词）：{search_term}")

    if args.from_index:
        arts = from_index(search_term, args.limit)
    else:
        arts = from_pubmed(search_term, args.limit, args.days or None)
    if not arts:
        print("没取到文献 —— 换个主题，或去掉 --days 限制")
        return 1
    print(f"拿到 {len(arts)} 篇，开始逐篇总结…")

    lines = [f"# 文献速读：{args.topic}", "",
             f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M}｜文献数：{len(arts)}"
             f"｜来源：{'本地索引' if args.from_index else 'PubMed 最新检索'}"
             f"｜检索式：`{search_term}`", ""]
    points_for_review, details = [], []
    total_cost = 0.0

    for n, art in enumerate(arts, 1):
        try:
            point = summarize(bot, art)
        except DeepSeekError as e:
            print(f"  [{n}] 总结失败：{e}")
            continue
        total_cost += bot.last_usage["cost_cny"]
        points_for_review.append(f"[{n}] {point}")
        details.append(f"### [{n}] {art['title']}\n\n"
                       f"{point}\n\n"
                       f"> {art['journal']}（{art['year']}）｜PMID [{art['pmid']}]"
                       f"(https://pubmed.ncbi.nlm.nih.gov/{art['pmid']}/)\n")
        print(f"  [{n}] {point[:60]}…")
        time.sleep(0.3)

    print("生成主题综述…")
    review = bot.chat([{"role": "system", "content": REVIEW_SYSTEM},
                       {"role": "user", "content": "\n".join(points_for_review)}],
                      temperature=0.3).strip()
    total_cost += bot.last_usage["cost_cny"]

    lines += ["## 这个方向现在到什么程度了", "", review, "", "## 逐篇要点", ""] + details
    lines += ["---", f"本期共 {len(details)} 篇，累计花费 **{total_cost:.6f} 元**"
                     "（含综述）。由 rag/report.py 自动生成。"]

    out = Path(args.out) if args.out else OUT_DIR / f"{slug(args.topic)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已生成：{out}（{len(details)} 篇｜{total_cost:.6f} 元）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
