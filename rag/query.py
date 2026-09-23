"""查询改写：中文问题/主题 → 英文检索词。

为什么必须要有这一步：PubMed、以及绝大多数生物医学语料都是英文，
而检索（无论 BM25 还是关键词检索）都是"字面匹配"——
用中文去查英文库，命中率接近零（实测：中文主题直接检索 PubMed 会返回
96 万篇"命中"和一堆毫不相关的最近文献）。

所以检索前先把问题改写成英文关键词：这一步便宜（一次短调用，约 0.0002 元），
但直接决定整套系统的可用性。
"""

import re

CJK = re.compile(r"[\u4e00-\u9fff]")
REWRITE_SYSTEM = ("把用户的问题改写成英文文献检索关键词。只输出关键词，用空格分隔，"
                  "不要解释、不要标点、不要换行。")


def has_cjk(text: str) -> bool:
    return bool(CJK.search(text or ""))


def rewrite_query(bot, question: str) -> str:
    """让模型把中文问题压成英文检索关键词（temperature=0，保证可复现）。"""
    return bot.chat([{"role": "system", "content": REWRITE_SYSTEM},
                     {"role": "user", "content": question}], temperature=0.0).strip()
