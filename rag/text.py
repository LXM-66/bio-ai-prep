"""文本处理：切分（chunking）与分词（tokenize）。

切分是 RAG 里最容易被忽略、却最影响效果的一步：
- 块太大 → 一段话里混着好几个主题，检索命中后噪声多
- 块太小 → 一句话被切断，上下文不足，答案没法自洽
所以这里按"句子"边界切，并留一段重叠（overlap），避免答案正好落在切口上。
"""

import re

# 按中英文句末标点切句，并保留标点
SENT_SPLIT = re.compile(r"(?<=[。！？；.!?;])\s*")


def split_sentences(text):
    """切成句子列表。"""
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


def chunk_text(text, size=600, overlap=100):
    """把长文本切成带重叠的块（每块尽量不超过 size 字符）。"""
    if len(text) <= size:
        return [text.strip()] if text.strip() else []

    chunks, buf = [], ""
    for sent in split_sentences(text):
        if buf and len(buf) + len(sent) > size:
            chunks.append(buf.strip())
            buf = buf[-overlap:] + sent          # 保留尾部一段做重叠
        else:
            buf += sent
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def tokenize(text):
    """中英混合的极简分词：英文/数字按词，中文按单字。

    BM25 只认"词"，所以这一步决定检索能不能命中。中文没有空格，
    这里用单字做最粗的切分（够用；要更好就上 jieba）。
    """
    text = text.lower()
    tokens = re.findall(r"[a-z0-9][a-z0-9\-\.]*", text)      # 英文/数字
    tokens += re.findall(r"[\u4e00-\u9fff]", text)           # 中文单字
    return tokens
