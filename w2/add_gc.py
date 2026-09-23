"""给前 N 条记录补上真实 GC 含量（其余记录留空，故意制造缺失值给 pandas 练手）。

用法：
    python w2/add_gc.py500 [N]       

产物：
    w2/data/gc_partial.csv      accession,gc（只有 N 行）
    w2/data/gc_seqs.fasta       下载到的序列（缓存）
"""

import csv
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "w1"))          # 复用 W1 写的函数
from gc_content import gc_content, read_fasta  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def fetch_many(accessions, chunk=100):
    """分批拿序列：URL 有长度上限，几百条要拆成几次请求，批次之间停 0.4s 守礼节。"""
    total = -(-len(accessions) // chunk)          # 向上取整
    parts = []
    for i in range(0, len(accessions), chunk):
        batch = accessions[i:i + chunk]
        url = (f"{EFETCH}?db=nuccore&rettype=fasta&retmode=text"
               f"&id={','.join(batch)}")
        req = urllib.request.Request(url, headers={"User-Agent": "w2-learning-script"})
        parts.append(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))
        print(f"  批次 {i // chunk + 1}/{total}：{len(batch)} 条")
        if i + chunk < len(accessions):
            time.sleep(0.4)
    return "".join(parts)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    rows = list(csv.DictReader((DATA / "ncbi_raw.csv").open(encoding="utf-8")))
    wanted = [r["accession"] for r in rows[:n]]

    fasta_path = DATA / "gc_seqs.fasta"
    fasta_path.write_text(fetch_many(wanted), encoding="utf-8")

    seqs = read_fasta(fasta_path)
    out = DATA / "gc_partial.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["accession", "gc"])
        for name, seq in seqs.items():
            w.writerow([name.split()[0], round(gc_content(seq), 4)])

    print(f"请求 {len(wanted)} 条，拿到 {len(seqs)} 条 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
