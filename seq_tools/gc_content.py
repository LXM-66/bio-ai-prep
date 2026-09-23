"""读取 FASTA 文件，输出每条序列的长度与 GC 含量。

用法：
    python seq_tools/gc_content.py seq_tools/sample.fasta

可扩展点：
1. 加一个参数控制是否只输出最长的序列
2. 把结果写进 CSV 文件
3. 处理文件不存在的情况（try/except）
"""

import sys


def read_fasta(path):
    """把 FASTA 文件读成 {序列名: 序列} 的字典。"""
    seqs = {}
    name = None
    chunks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    seqs[name] = "".join(chunks)
                name = line[1:].split()[0]   # 只取第一个空格前的内容当名字
                chunks = []
            else:
                chunks.append(line.upper())
    if name is not None:
        seqs[name] = "".join(chunks)
    return seqs


def gc_content(seq):
    """GC 含量（0~1）。空序列返回 0。"""
    if not seq:
        return 0.0
    gc = sum(1 for base in seq if base in "GC")
    return gc / len(seq)


def main():
    if len(sys.argv) != 2:
        print("用法: python gc_content.py <fasta文件>")
        return 1

    seqs = read_fasta(sys.argv[1])
    if not seqs:
        print("没读到任何序列，检查一下文件格式")
        return 1

    print(f"{'序列名':<20}{'长度':>8}{'GC含量':>10}")
    print("-" * 38)
    for name, seq in seqs.items():
        print(f"{name:<20}{len(seq):>8}{gc_content(seq):>10.1%}")

    total = sum(len(s) for s in seqs.values())
    print("-" * 38)
    print(f"共 {len(seqs)} 条序列，总长 {total} bp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
