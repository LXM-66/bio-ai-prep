"""把 rag/data/pubmed.jsonl 切块、建 BM25 索引、存盘。

用法：
    python rag/build_index.py                      # 默认块长 600、重叠 100
    python rag/build_index.py --size 400 --overlap 80

产物：
    rag/index/bm25.json    索引（含切好的块、词频、文档频率）
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import BM25Index   # noqa: E402
from text import chunk_text   # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
INDEX = Path(__file__).resolve().parent / "index" / "bm25.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=600, help="每块最大字符数")
    ap.add_argument("--overlap", type=int, default=100, help="相邻块的重叠字符数")
    args = ap.parse_args()

    src = DATA / "pubmed.jsonl"
    if not src.exists():
        print(f"找不到语料 {src}，先跑：python rag/fetch_pubmed.py")
        return 1

    articles = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines() if line.strip()]
    chunks, meta = [], []
    for art in articles:
        full = f"{art['title']}。{art['abstract']}"          # 标题并进正文，标题往往是信息密度最高的一句
        for n, piece in enumerate(chunk_text(full, args.size, args.overlap)):
            chunks.append(piece)
            meta.append({"pmid": art["pmid"], "title": art["title"],
                         "journal": art["journal"], "year": art["year"], "chunk": n + 1})

    idx = BM25Index().build(chunks, meta)
    idx.save(INDEX, source=f"pubmed:{len(articles)}篇")

    sizes = [len(c) for c in chunks]
    print(f"文档 {len(articles)} 篇 → 切成 {len(chunks)} 块"
          f"（块长 中位 {sorted(sizes)[len(sizes) // 2]} / 最长 {max(sizes)} 字符）")
    print(f"词表 {len(idx.df):,} 个词｜平均块长 {idx.avgdl:.0f} 词")
    print(f"索引写入 {INDEX}（{INDEX.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
