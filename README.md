# bio-ai-prep

李林峻的求职作品集仓库 —— 生物医药方向的大模型应用（12 周计划，2026-09-22 → 2026-12-14）。

目标：做出 1 个讲得清的 AI 项目，同时投**生物信息/医药数据（技术线）**和 **AI 产品（交叉线）**两方向。

## 目录

| 路径 | 内容 |
|---|---|
| `w1/` | 第 1 周：Python 地基 —— 序列解析、统计、真实数据拉取 |
| `w2/` | 第 2 周：pandas 处理真实生物数据 + 出图（待开始） |

## 环境

- Python 3.14（`D:\Python314\python.exe`）
- 虚拟环境：`uv venv` → `.venv\Scripts\python.exe`

```bash
uv venv
.venv/Scripts/python.exe --version
```

## w1 脚本

```bash
# 1) 读 FASTA，算长度与 GC 含量
python w1/gc_content.py w1/sample.fasta

# 2) DNA 反向互补 + 密码子翻译
python w1/rev_comp.py

# 3) 统计结果写成 CSV（产物 w1/out/stats.csv）
python w1/fasta_to_csv.py w1/sample.fasta

# 4) 从 NCBI 拉真实序列再统计（无需 API key）
python w1/fetch_ncbi.py NM_000546              # 人类 TP53 mRNA
python w1/fetch_ncbi.py NC_001807 --start 1 --stop 600
```

实测输出（2026-09-22）：

| 编号 | 说明 | 长度 | GC |
|---|---|---|---|
| `NM_000546.6` | 人类 TP53 基因 mRNA | 2512 bp | 53.4% |
| `NC_001807.4:1-600` | 人类线粒体 1–600 位 | 600 bp | 46.7% |

## 数据来源与调用礼节

- 数据：NCBI E-utilities（`eutils.ncbi.nlm.nih.gov`），公开接口、无需 key
- 礼节：带 `User-Agent`，请求频率 ≤ 3 次/秒
- 原始序列缓存到 `w1/out/*.fasta`，不入库；只提交统计结果

## w2 脚本（真实数据 → 清洗 → 出图）

```bash
# 1) 从 NCBI 拉 500 条人类 RefSeq mRNA 记录，原样存表（故意不洗）
python w2/fetch_dataset.py 500

# 2) 给前 60 条补真实 GC 含量（其余留空，专门用来练缺失值处理）
python w2/add_gc.py 60

# 3) 清洗 + 三张图：在 VS Code 里打开这个 notebook 逐格跑
w2/分析.ipynb
```

实测结果（2026-09-23，500 条记录）：

| 指标 | 数字 |
|---|---|
| 记录 / 覆盖基因 | 500 条 / 142 个基因 |
| 序列长度 | 中位 **3040 bp**（478 – 16398 bp） |
| GC 含量（60 条有值） | 中位 **55.7%**（35.7% – 62.5%） |
| 长度 vs GC 相关系数 | **0.040**（基本无关） |

![每年记录数](w2/out/fig1_by_year.png)
![长度分布](w2/out/fig2_length.png)
![长度与 GC](w2/out/fig3_gc_length.png)

清洗踩过的坑：`gene` 带尾缀（`ABCC1 blood group`）、日期是字符串、同一基因多个转录本、GC 列 88% 缺失（**不能填 0**）。

## 进度

- [x] W1-0 仓库建好、环境跑通
- [x] W1-1 Python 地基：解析 FASTA、密码子翻译、CSV 输出、调公开 API 取数
- [x] W2 pandas + 真实数据表清洗 + 3 张图
- [ ] W3 把 Week1–2 整理成可分享的项目页（README + notebook）
