"""把 rag/data/ 下的全部语料切块、建 BM25 索引、存盘。

数据源在 corpus.py 的登记表里维护（当前：PubMed 摘要 / UniProt 功能注释 / PDB 结构条目），
这里不关心字段差异 —— 每条记录都已经被归一化成 {sid, source, title, text, ...}。

用法：
    python rag/build_index.py                      # 默认块长 600、重叠 100
    python rag/build_index.py --size 400 --overlap 80

产物：
    rag/index/bm25.json    索引（切好的块 + 词频 + 文档频率 + 每块的来源元数据）
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus import load_records, stats      # noqa: E402
from store import BM25Index                 # noqa: E402
from text import chunk_text                 # noqa: E402

INDEX = Path(__file__).resolve().parent / "index" / "bm25.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=600, help="每块最大字符数")
    ap.add_argument("--overlap", type=int, default=100, help="相邻块的重叠字符数")
    args = ap.parse_args()

    records = load_records()
    if not records:
        print("找不到语料。先跑：python rag/fetch_pubmed.py / fetch_uniprot.py / fetch_pdb.py")
        return 1

    chunks, meta = [], []
    for rec in records:
        full = f"{rec.title}。{rec.text}"        # 标题并进正文：标题往往信息密度最高
        for n, piece in enumerate(chunk_text(full, args.size, args.overlap)):
            chunks.append(piece)
            meta.append({"source": rec.source, "sid": rec.sid, "title": rec.title,
                         "extra": rec.extra, "year": rec.year, "url": rec.url, "chunk": n + 1})

    idx = BM25Index().build(chunks, meta)
    by_source = stats(records)["按来源"]
    idx.save(INDEX, source=" / ".join(f"{k} {v} 条" for k, v in by_source.items()))

    sizes = [len(c) for c in chunks]
    print(f"语料 {len(records)} 条（{'、'.join(f'{k} {v}' for k, v in by_source.items())}）")
    print(f"切成 {len(chunks)} 块（块长 中位 {sorted(sizes)[len(sizes) // 2]} / 最长 {max(sizes)} 字符）")
    print(f"词表 {len(idx.df):,} 个词｜平均块长 {idx.avgdl:.0f} 词")
    print(f"索引写入 {INDEX}（{INDEX.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
