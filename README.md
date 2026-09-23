# 人类 RefSeq mRNA 的长度与 GC 特征分析

> 从 NCBI 公开库取回 500 条人类 RefSeq mRNA 记录，清洗成可用表，用 4 张图回答一个问题：**这批转录本在长度和碱基组成上有什么规律？**
> 全部代码可复现，三条命令跑通（见下）。

[![Python](https://img.shields.io/badge/Python-3.14-4C8BF5)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-59C3A5)](LICENSE)

![每年记录数](w2/out/fig1_by_year.png)
![长度分布](w2/out/fig2_length.png)
![长度与 GC](w2/out/fig3_gc_length.png)
![top 基因](w2/out/fig4_top_genes.png)

## 关键数字（2026-09-23 实测）

| 指标 | 结果 |
|---|---|
| 记录 / 覆盖基因 | 500 条 / **142 个基因** |
| 序列长度 | 中位 **3040 bp**（478 – 16398 bp），强右偏 |
| GC 含量（60 条有值） | 中位 **55.7%**（35.7% – 62.5%） |
| 对数长度 vs GC 相关系数 | **0.031** —— 基本无关 |
| 2022–2023 两年占全表 | **46%** —— 是 NCBI 批量重注释，不是生物学变化 |

## 这份分析解决什么问题

生信日常拿到的第一份数据，几乎总是"别人导出的表"：列名混乱、日期是字符串、同一样本多个副本、关键列大量缺失。
这个项目把**从公开库取数 → 清洗 → 出图 → 得出结论**这条链路完整走一遍，并留下可复现的代码：

- `w1/` 写序列处理的基础工具（FASTA 解析、密码子翻译、真实序列拉取）
- `w2/` 用 pandas 处理真实记录表，产出上面 4 张图
- `viz.py` 统一出图规范：字体、配色、边框、dpi 一处控制，改一处所有图一起变

## 怎么复现

```bash
# 1. 建环境（uv 或 venv 都行）
uv venv && uv pip install --python .venv/Scripts/python.exe \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 2. 取数据：500 条人类 RefSeq mRNA 记录
python w2/fetch_dataset.py 500

# 3. 给部分记录补真实 GC 含量（练习缺失值处理）
python w2/add_gc.py 60

# 4. 清洗 + 出图：在 VS Code 里打开 notebook 逐格运行
#    w2/分析.ipynb
```

`w1/` 里的四个脚本也可以单独跑：

```bash
python w1/gc_content.py w1/sample.fasta     # 读 FASTA，算长度与 GC
python w1/rev_comp.py                       # 反向互补 + 密码子翻译
python w1/fasta_to_csv.py w1/sample.fasta   # 统计结果写成 CSV
python w1/fetch_ncbi.py NM_000546           # 拉人类 TP53 mRNA 再统计
```

## 项目结构

```
bio-ai-prep/
├── viz.py                 统一出图规范（字体/配色/边框/dpi）
├── requirements.txt
├── .env.example          API key 模板（真的 key 放 .env，不入库）
├── w1/                    Python 地基：序列解析与统计
│   ├── gc_content.py          读 FASTA → 长度 / GC
│   ├── rev_comp.py            反向互补 + 密码子翻译
│   ├── fasta_to_csv.py        统计结果 → CSV（含边界处理）
│   └── fetch_ncbi.py          从 NCBI 拉真实序列（E-utilities，无需 key）
├── w2/                    真实数据表：清洗与可视化
    ├── fetch_dataset.py       esearch + esummary → 500 条记录表
    ├── add_gc.py              复用 w1 的函数，补 GC 含量（默认 60 条，可传 500）
    ├── data/                  原始表 + GC 表（CSV，已入库）
    ├── out/                   4 张图（PNG，已入库）
    └── 分析.ipynb             清洗 + 出图 + 结论（含真实输出）
└── w4/                    大模型 API：流式对话与成本统计
    ├── llm.py                 封装：SSE 流式 / 超时 / 指数退避重试 / 计价
    ├── chat.py                命令行多轮对话（/cost /reset /exit）
    └── logs/usage.csv         每次调用的 token 与花费流水
```

## w4 脚本（接大模型 API：流式 / 重试 / 成本）

```bash
cp .env.example .env        # 填入自己的 DEEPSEEK_API_KEY（.env 不入库）
python w4/chat.py           # 多轮对话：流式输出，每轮显示 token 与花费
```

实测（2026-09-23，`deepseek-flash`，高峰时段）：

| 场景 | 输入 tokens | 缓存命中 | 输出 tokens | 耗时 | 花费 |
|---|---|---|---|---|---|
| 单轮问答（RAG 是什么） | 70 | 0 | 277 | 2.08 s | 0.001178 元 |
| 多轮追问 | 133 | 0 | 190 | 1.40 s | 0.000893 元 |
| 1728 tokens 长前缀 · 首次 | 1728 | 0 | 60 | 0.69 s | 0.001968 元 |
| 同一前缀 · 第二次 | 1728 | **1536** | 97 | 1.11 s | **0.000611 元（↓69%）** |

四个工程要点（都写在 `w4/llm.py` 里）：

1. **只用标准库** `urllib` 手写 SSE 解析 —— 看清"流式"其实就是一行行 `data: {...}`。
2. **重试**：网络错误 / 429 / 5xx 按 1s → 2s → 4s 指数退避，最多 3 次；参数错（4xx）不重试，因为重试没意义。
3. **超时**：默认 60 秒可配，避免调用挂死。
4. **成本**：按[官方价目表](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)自动判断高峰/空闲（空闲时段半价），并区分**缓存命中**与**未命中**分别计价 —— 上面第 3、4 行就是缓存把同一段长前缀变便宜 69% 的实测。

每次调用都会往 `w4/logs/usage.csv` 追加一行（时间、模型、token、是否高峰、花费、耗时），方便回看"这个月花了多少"。

## 数据来源与调用礼节

- 数据：[NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)（`eutils.ncbi.nlm.nih.gov`），公开接口、**无需 API key**
- 礼节：请求带 `User-Agent`，频率 **≤ 3 次/秒**（脚本里内置了 0.4 s 间隔与 3 次重试）
- 原始 FASTA 缓存不入库（`.gitignore`），只提交统计结果与图

## 清洗踩过的坑（都在 `w2/分析.ipynb` 里）

| 坑 | 现象 | 处理 |
|---|---|---|
| 基因名带尾缀 | 12 行是 `ABCC1 blood group` | `str.split().str[0]` |
| 日期是字符串 | `'1999/03/19'` | `pd.to_datetime` → 派生 `year` |
| 同一基因多转录本 | 500 条记录只覆盖 142 个基因 | 先按基因聚合再统计，别当成重复数据 |
| GC 列 88% 缺失 | 只有 60/500 条有 GC | **不能填 0**（0% GC 生物学上不存在），分析时取子集 |

## 局限

- **样本是切片**：按发布日期取的前 500 条，不能说"人类 mRNA 都如此"，只能说"这 500 条里"。
- **GC 只覆盖 60 条**：补全需 500 次请求（`python w2/add_gc.py 500`，约 3 分钟）。
- **年份差异反映注释行为**，不是基因变多变少。

## 进度（12 周计划 · 2026-09-22 → 2026-12-14）

- [x] **W1** Python 地基：解析 FASTA、密码子翻译、CSV 输出、调公开 API 取数
- [x] **W2** pandas + 真实数据表清洗 + 4 张图
- [x] **W3** 整理成可分享的项目页（本 README + notebook + 统一出图规范）
- [x] **W4** 接大模型 API：流式输出、异常重试、超时、Token 与成本统计
- [ ] **W5–W6** RAG 文档问答原型 + 灌入生物医药真实数据
- [ ] **W7–W9** 评测集、成本/延迟实测、PRD 与用户反馈
- [ ] **W10–W12** 双版简历、Demo 视频、投递与模拟面试

## 作者

李林峻 · GitHub [@LXM-66](https://github.com/LXM-66) · MIT License
