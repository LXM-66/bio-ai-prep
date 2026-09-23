# seq_tools —— 序列处理基础工具

FASTA 解析、碱基统计、反向互补与密码子翻译，以及从 NCBI 直接取序列的小工具。
依赖只有 Python 标准库。

## 脚本

| 脚本 | 作用 |
|---|---|
| `gc_content.py` | 读 FASTA，输出每条序列的长度与 GC 含量 |
| `rev_comp.py` | 反向互补链 + 按标准密码子表翻译蛋白 |
| `fasta_to_csv.py` | 统计结果写成 CSV（含文件不存在/参数缺失的边界处理） |
| `fetch_ncbi.py` | 从 NCBI E-utilities 按编号取真实序列（无需 API key） |

```bash
python seq_tools/gc_content.py seq_tools/sample.fasta
python seq_tools/rev_comp.py
python seq_tools/fasta_to_csv.py seq_tools/sample.fasta     # 产物 seq_tools/out/stats.csv
python seq_tools/fetch_ncbi.py NM_000546                    # 人类 TP53 mRNA
python seq_tools/fetch_ncbi.py NC_001807 --start 1 --stop 600
```

## 实测

| 编号 | 说明 | 长度 | GC |
|---|---|---|---|
| `NM_000546.6` | 人类 TP53 基因 mRNA | 2512 bp | 53.4% |
| `NC_001807.4:1-600` | 人类线粒体 1–600 位 | 600 bp | 46.7% |

## 约定

- 取数遵守 NCBI 礼节：带 `User-Agent`，频率 ≤ 3 次/秒，失败自动重试
- 下载到的序列缓存进 `out/`（其中 `*.fasta` 不入库），只提交统计结果

## 可扩展点

- `gc_content.py`：支持只输出最长序列、按 GC 排序、处理多行注释行
- `rev_comp.py`：支持按不同遗传密码表（线粒体表）翻译、输出六框翻译
- `fetch_ncbi.py`：支持批量编号、结果直接落 CSV
