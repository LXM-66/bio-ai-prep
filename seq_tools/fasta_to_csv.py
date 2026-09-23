"""读 FASTA，统计每条序列的名字/长度/GC 含量，写成 CSV。

用法：
    python seq_tools/fasta_to_csv.py seq_tools/sample.fasta
输出：
    seq_tools/out/stats.csv
"""

import csv
import sys
from pathlib import Path

from gc_content import gc_content, read_fasta

OUT = Path(__file__).resolve().parent / "out" / "stats.csv"


def main():
    if len(sys.argv) != 2:
        print("用法: python seq_tools/fasta_to_csv.py <fasta文件>")
        return 1

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"文件不存在: {src}")
        return 1

    seqs = read_fasta(src)
    if not seqs:
        print("没读到任何序列，检查一下文件格式")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "length", "gc"])
        for name, seq in seqs.items():
            writer.writerow([name, len(seq), round(gc_content(seq), 4)])

    print(f"已写入 {OUT}（{len(seqs)} 条序列，总长 {sum(len(s) for s in seqs.values())} bp）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
