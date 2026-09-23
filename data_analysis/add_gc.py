"""给前 N 条记录补上真实 GC 含量（其余记录留空，故意制造缺失值给 pandas 练手）。

用法：
    python data_analysis/add_gc.py            # 默认全量 500 条
    python data_analysis/add_gc.py 60         # 只补前 60 条

产物：
    data_analysis/data/gc_partial.csv      accession,gc（只有 N 行）
    data_analysis/data/gc_seqs.fasta       下载到的序列（缓存）
"""

import csv
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "seq_tools"))          # 复用 seq_tools 里的函数
from gc_content import gc_content, read_fasta  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def fetch(url, timeout=120, retries=3):
    """下载一个 URL；网络抖动（超时/断连）自动重试，避免整批白跑。"""
    req = urllib.request.Request(url, headers={"User-Agent": "w2-learning-script"})
    for attempt in range(1, retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8")
        except Exception as e:
            print(f"    ✗ 第 {attempt}/{retries} 次失败：{type(e).__name__}: {str(e)[:70]}")
            if attempt == retries:
                raise
            time.sleep(3 * attempt)          # 3s → 6s 退避后再试


def fetch_many(accessions, chunk=100):
    """分批拿序列：URL 有长度上限，几百条要拆成几次请求，批次之间停 0.4s 守礼节。"""
    total = -(-len(accessions) // chunk)          # 向上取整
    parts = []
    for i in range(0, len(accessions), chunk):
        batch = accessions[i:i + chunk]
        url = (f"{EFETCH}?db=nuccore&rettype=fasta&retmode=text"
               f"&id={','.join(batch)}")
        parts.append(fetch(url))
        print(f"  批次 {i // chunk + 1}/{total}：{len(batch)} 条")
        if i + chunk < len(accessions):
            time.sleep(0.4)
    return "".join(parts)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
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
