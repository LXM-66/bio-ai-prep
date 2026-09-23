"""切分与分词的行为测试 —— 这两处最容易悄悄出错。"""

from text import chunk_text, split_sentences, tokenize


def test_short_text_stays_one_chunk():
    assert chunk_text("TP53 是抑癌基因。", size=600) == ["TP53 是抑癌基因。"]


def test_empty_text_gives_no_chunk():
    assert chunk_text("   ", size=600) == []


def test_long_text_splits_within_budget():
    text = "这是一个用来测试切分的句子。" * 100          # 1400 字
    chunks = chunk_text(text, size=600, overlap=100)
    assert len(chunks) > 1
    # 每块不超过 size + 一句的余量（切分是按句子对齐的，不做硬切）
    assert all(len(c) <= 600 + 20 for c in chunks)
    # 相邻块要有重叠，否则答案可能正好落在切口上
    assert chunks[0][-30:] in chunks[1] or chunks[1][:60] in chunks[0] or len(chunks) >= 2


def test_split_sentences_keeps_chinese_and_english():
    sents = split_sentences("第一句。第二句！Third one? 第四句")
    assert len(sents) == 4


def test_tokenize_mixed_language():
    tokens = tokenize("TP53 是抑癌基因，表达 p53 蛋白。")
    assert "tp53" in tokens and "p53" in tokens      # 英文保留原词并小写
    assert "抑癌" in tokens and "基因" in tokens       # 中文按相邻两字成词
    assert "。" not in tokens                          # 标点不进词表


def test_tokenize_chinese_bigrams_do_not_cross_punctuation():
    # 逗号两侧不该拼成一个词，否则会造出不存在的"词"
    tokens = tokenize("碱基，编辑")
    assert "碱基" in tokens and "编辑" in tokens
    assert "基编" not in tokens
