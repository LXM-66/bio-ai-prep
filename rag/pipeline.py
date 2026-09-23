"""引擎层：把「检索 + 带引用回答 + 生成报告」的逻辑集中在这里。

命令行（ask.py / report.py）和 Web 界面（ui/app.py）都只调用这一层 —— 逻辑写两遍
迟早会不一致，改一个入口就得记得改另一个。

对外两个方法：
    Engine.ask(question, k)                     → 一次问答（含引用与花费）
    Engine.build_report(topic, limit, days)     → 一份 markdown 速读报告
"""

from __future__ import annotations

import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "llm_client"))

from corpus import Record, load_records, to_record       # noqa: E402
from llm import DeepSeek, DeepSeekError, load_env        # noqa: E402
from query import has_cjk, rewrite_query                 # noqa: E402
from store import BM25Index                              # noqa: E402

INDEX = HERE / "index" / "bm25.json"
DATA = HERE / "data"
REPORT_DIR = HERE / "reports"

ANSWER_SYSTEM = ("你是生物医药文献助手。只依据用户给的【资料】回答；"
                 "每条结论后面用 [编号] 标注来源；资料里没有的内容直接说「资料里没有提到」，不要编。"
                 "用中文回答，专业术语保留英文原词。简洁，不超过 6 句。回答末尾不重复罗列资料原文。")
SUMMARY_SYSTEM = ("你是一名生物医药领域的科研助理。用中文把这段资料总结成 2–3 句，"
                  "只讲做了什么、发现了什么（带上关键数字或结论），不要评价、不要客套、不要罗列方法细节。")
REVIEW_SYSTEM = ("你是生物医药领域的科研助理。下面是一组资料的中文要点，"
                 "请写 3–5 条「这个方向现在到什么程度了」的中文综述，每条后面用 [编号] 标注依据的资料。"
                 "只依据给定材料，不要引入外部知识，材料没提到的不写。")


def build_prompt(question: str, hits: list[tuple[int, float]], idx: BM25Index) -> str:
    """把检索到的块拼成【资料】段落，编号与引用标号一一对应。"""
    blocks = []
    for n, (i, score) in enumerate(hits, 1):
        m = idx.meta[i]
        source = f"{m.get('source', '?')} {m.get('sid', '')}".strip()
        blocks.append(f"[{n}]（{source}｜相关度 {score}）{idx.chunks[i]}")
    return "【资料】\n" + "\n\n".join(blocks) + f"\n\n【问题】{question}"


class Engine:
    """检索问答引擎。need_bot=False 时只检索、不调用大模型（离线也能用）。"""

    def __init__(self, index_path: Path = INDEX, model: str = "deepseek-flash", need_bot: bool = True):
        if not Path(index_path).exists():
            raise FileNotFoundError(f"索引不存在：{index_path}（先跑 python rag/build_index.py）")
        self.idx = BM25Index.load(index_path)
        self.index_path = Path(index_path)
        self.bot = None
        self.bot_error = ""
        if need_bot:
            load_env()
            try:
                self.bot = DeepSeek(model=model)
            except DeepSeekError as exc:                 # 没有 key 就退化成纯检索
                self.bot_error = str(exc)

    # ── 内部工具 ────────────────────────────────────────────────────────
    def _hit(self, i: int, score: float) -> dict:
        m = self.idx.meta[i]
        return {"score": score, "source": m.get("source", ""), "sid": m.get("sid", ""),
                "title": m.get("title", ""), "text": self.idx.chunks[i], "url": m.get("url", ""),
                "extra": m.get("extra", ""), "year": m.get("year", ""), "chunk": m.get("chunk", 1)}

    def _rewrite(self, text: str) -> str:
        if self.bot and has_cjk(text):
            return rewrite_query(self.bot, text)
        return text

    # ── 问答 ────────────────────────────────────────────────────────────
    def ask(self, question: str, k: int = 5) -> dict:
        query = self._rewrite(question)
        hits = self.idx.search(query, k=k)
        result = {"question": question, "query": query, "k": k, "answer": None,
                  "hits": [self._hit(i, s) for i, s in hits], "cost": 0.0, "usage": None,
                  "error": self.bot_error}
        if not self.bot or not hits:
            return result
        answer = self.bot.chat([{"role": "system", "content": ANSWER_SYSTEM},
                                {"role": "user", "content": build_prompt(question, hits, self.idx)}],
                               temperature=0.2)
        result.update(answer=answer, cost=self.bot.last_usage["cost_cny"], usage=self.bot.last_usage)
        return result

    # ── 速读报告 ────────────────────────────────────────────────────────
    def articles_from_index(self, topic: str, limit: int) -> list[Record]:
        """从已有索引里按主题取文章级结果（同一来源同一编号只算一篇）。"""
        hits = self.idx.search(topic, k=limit * 4)
        seen, out = set(), []
        for i, _ in hits:
            m = self.idx.meta[i]
            key = (m.get("source", ""), m.get("sid", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(Record(sid=m.get("sid", ""), source=m.get("source", ""), title=m.get("title", ""),
                              text=self.idx.chunks[i], extra=m.get("extra", ""),
                              year=m.get("year", ""), url=m.get("url", "")))
            if len(out) >= limit:
                break
        return out

    def articles_from_pubmed(self, topic: str, limit: int, days: int | None) -> list[Record]:
        from fetch_pubmed import EFETCH, fetch, parse_articles, search_pmids
        pmids = search_pmids(topic, limit, days=days, sort="pub date")
        if not pmids:
            return []
        url = f"{EFETCH}?" + urllib.parse.urlencode(
            {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"})
        return [to_record("PubMed", d) for d in parse_articles(fetch(url))]

    def build_report(self, topic: str, limit: int = 8, days: int | None = None,
                     from_index: bool = False, on_progress=None) -> dict:
        def say(msg):
            if on_progress:
                on_progress(msg)

        search_term = self._rewrite(topic)
        arts = (self.articles_from_index(search_term, limit) if from_index
                else self.articles_from_pubmed(search_term, limit, days))
        if not arts:
            return {"error": "没取到资料 —— 换个主题，或去掉时间窗限制", "markdown": "", "cost": 0.0}

        header = [f"# 速读报告：{topic}", "",
                  f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M}｜资料数：{len(arts)}"
                  f"｜来源：{'本地索引' if from_index else 'PubMed 最新检索'}"
                  f"｜检索式：`{search_term}`", ""]
        points, details, cost = [], [], 0.0

        for n, art in enumerate(arts, 1):
            user = f"标题：{art.title}\n正文：{art.text}"
            try:
                point = self.bot.chat([{"role": "system", "content": SUMMARY_SYSTEM},
                                       {"role": "user", "content": user}], temperature=0.3).strip()
            except DeepSeekError as exc:
                say(f"  [{n}] 总结失败：{exc}")
                continue
            cost += self.bot.last_usage["cost_cny"]
            points.append(f"[{n}] {point}")
            cite = f"{art.source} {art.sid}"
            if art.extra:
                cite += f"｜{art.extra}"
            if art.year:
                cite += f"（{art.year}）"
            details.append(f"### [{n}] {art.title}\n\n{point}\n\n> {cite}｜[原文]({art.url})\n")
            say(f"  [{n}] {point[:60]}…")
            time.sleep(0.3)                              # 别把接口打急

        review = ""
        if points:
            review = self.bot.chat([{"role": "system", "content": REVIEW_SYSTEM},
                                    {"role": "user", "content": "\n".join(points)}],
                                   temperature=0.3).strip()
            cost += self.bot.last_usage["cost_cny"]

        md = "\n".join(header + ["## 这个方向现在到什么程度了", "", review, "",
                                 "## 逐篇要点", ""] + details +
                       ["---", f"共 {len(details)} 条资料，累计花费 **{cost:.6f} 元**（含综述）。"
                               "由 rag/pipeline.py 生成。"])
        return {"markdown": md, "cost": cost, "count": len(details), "search_term": search_term,
                "articles": arts, "error": ""}


def corpus_overview() -> dict:
    """语料概览：给界面和报告头部用。"""
    records = load_records(DATA)
    by_source: dict[str, int] = {}
    for rec in records:
        by_source[rec.source] = by_source.get(rec.source, 0) + 1
    return {"records": len(records), "by_source": by_source}
