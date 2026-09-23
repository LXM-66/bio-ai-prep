"""从 NCBI 拉取真实序列（无需 API key），统计后写入 CSV。

用法：
    python seq_tools/fetch_ncbi.py NC_001807
    python seq_tools/fetch_ncbi.py NM_000546 --start 1 --stop 600

产物：
    seq_tools/out/<编号>.fasta     原始序列（缓存，便于复跑）
    seq_tools/out/ncbi_stats.csv   统计结果
"""

import csv
import sys
import urllib.request
from pathlib import Path

from gc_content import gc_content, read_fasta

API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
OUT_DIR = Path(__file__).resolve().parent / "out"


def fetch_fasta(acc, start=None, stop=None):
    """向 NCBI 要 FASTA 文本。返回字符串；拿不到就抛 RuntimeError。"""
    url = f"{API}?db=nuccore&id={acc}&rettype=fasta&retmode=text"
    if start:
        url += f"&seq_start={start}&seq_stop={stop or start}"

    req = urllib.request.Request(url, headers={"User-Agent": "w1-learning-script"})
    text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

    if not text.startswith(">"):
        first = text.strip().splitlines()[0] if text.strip() else "（空响应）"
        raise RuntimeError(f"NCBI 没返回序列，先说：{first[:120]}")
    return text


def main():
    if len(sys.argv) < 2:
        print("用法: python seq_tools/fetch_ncbi.py <NCBI编号> [--start N --stop M]")
        return 1

    acc = sys.argv[1]
    start = stop = None
    if "--start" in sys.argv:
        start = sys.argv[sys.argv.index("--start") + 1]
        stop = sys.argv[sys.argv.index("--stop") + 1] if "--stop" in sys.argv else start

    try:
        fasta = fetch_fasta(acc, start, stop)
    except Exception as e:                      # 网络断了、编号写错了都走这里
        print(f"拉取失败: {type(e).__name__}: {e}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = OUT_DIR / f"{acc}.fasta"
    raw.write_text(fasta, encoding="utf-8")

    seqs = read_fasta(raw)
    rows = [(name, len(seq), round(gc_content(seq), 4)) for name, seq in seqs.items()]

    csv_path = OUT_DIR / "ncbi_stats.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "length", "gc"])
        w.writerows(rows)

    span = "全部" if not start else f"第 {start}-{stop} 位"
    print(f"来源: {acc}（{span}）｜序列 {len(seqs)} 条")
    for name, length, gc in rows:
        print(f"  {name[:60]:<60} {length:>7} bp   GC {gc:.1%}")
    print(f"原始序列 -> {raw}\n统计结果 -> {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
