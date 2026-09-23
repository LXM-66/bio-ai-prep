"""检索层的行为测试：能不能把相关的排在前面、能不能存取一致。"""

from store import BM25Index

CORPUS = [
    "TP53 编码 p53 蛋白，是重要的抑癌基因，突变后与多种肿瘤相关。",
    "BRCA1 参与 DNA 双链断裂修复，胚系突变提高乳腺癌风险。",
    "单细胞 RNA 测序可以解析肿瘤内部的细胞异质性。",
]


def test_ranks_relevant_chunk_first():
    idx = BM25Index().build(CORPUS)
    top = idx.search("p53 抑癌基因", k=1)
    assert top and top[0][0] == 0


def test_english_query_hits_english_terms():
    idx = BM25Index().build(CORPUS + ["Single-cell RNA sequencing reveals tumor heterogeneity."])
    top = idx.search("RNA sequencing heterogeneity", k=1)
    assert top and top[0][0] == 3


def test_empty_query_returns_nothing():
    idx = BM25Index().build(CORPUS)
    assert idx.search("", k=3) == []


def test_unknown_terms_return_nothing():
    idx = BM25Index().build(CORPUS)
    assert idx.search("玉米 育种 碱基编辑", k=3) == []


def test_score_ordering_is_descending():
    idx = BM25Index().build(CORPUS)
    scores = [s for _, s in idx.search("肿瘤 细胞 异质性", k=3)]
    assert scores == sorted(scores, reverse=True)


def test_save_and_load_roundtrip(tmp_path):
    idx = BM25Index().build(CORPUS, meta=[{"pmid": str(i)} for i in range(len(CORPUS))])
    path = tmp_path / "idx.json"
    idx.save(path)
    loaded = BM25Index.load(path)
    assert loaded.chunks == idx.chunks
    assert loaded.search("抑癌基因", k=1) == idx.search("抑癌基因", k=1)
    assert loaded.meta[1]["pmid"] == "1"
