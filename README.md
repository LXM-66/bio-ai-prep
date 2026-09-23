# 生物医药文献助手 · bio-ai-prep

面向生物医药场景的检索增强问答系统：**输入一个中文问题 → 从多源真实语料里检索 → 给出带引用的中文回答**；
资料里没有的内容它会直说不确定，不编。附带一套 Streamlit 界面，不写代码的人也能用。

[![Python](https://img.shields.io/badge/Python-3.14-4C8BF5)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-59C3A5)](LICENSE)
![tests](https://img.shields.io/badge/tests-18%20passed-59C3A5)

```
问题：DNA 错配修复蛋白的功能是什么？
检索式（自动改写）：DNA mismatch repair protein function

[1] 19.31  UniProt Q9UHC1  DNA mismatch repair protein Mlh3
[2] 18.11  UniProt P52701  DNA mismatch repair protein Msh6
[3] 17.23  UniProt P40692  DNA mismatch repair protein Mlh1

回答> DNA 错配修复蛋白主要参与复制后 DNA mismatch repair system (MMR) [2][3]。
      MSH6 与 MSH2 形成 MutS alpha，识别单碱基错配与 dinucleotide insertion-deletion loops [2]。
      MLH1 与 PMS2 形成 MutL alpha，被招募后激活 PMS2 的 endonuclease 活性 [3]…

消耗 598 + 797 tokens｜5.33s｜0.003786 元
```

## 跑起来

```bash
uv venv && uv pip install --python .venv/Scripts/python.exe \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

cp .env.example .env && 填入 DEEPSEEK_API_KEY

# ① 建语料（三个公开数据源，都不需要 key）
python rag/fetch_pubmed.py 100 "single-cell RNA sequencing AND cancer"
python rag/fetch_uniprot.py 40
python rag/fetch_pdb.py 20 "tumor suppressor"

# ② 建索引 → ③ 提问 / 生成报告
python rag/build_index.py
python rag/ask.py "DNA 错配修复蛋白的功能是什么？"
python rag/report.py "单细胞测序在肿瘤免疫治疗中的应用" --limit 5

# ④ 评测检索质量（hit@k / MRR + 两组对照实验）
python rag/make_eval.py --limit 24 && python rag/eval.py

# ⑤ Web 界面（不写代码的人也能用）
streamlit run ui/app.py            # → http://localhost:8501

# 其他
python llm_client/chat.py           # 命令行多轮对话（/cost /reset /exit）
python data_analysis/fetch_dataset.py 500 && python data_analysis/add_gc.py
.venv/Scripts/python.exe -m pytest tests -q     # 18 passed
```

## 实测结果

**检索质量**（18 道题，题目由模型从语料反推生成，gold = 出题的那块资料）

| 方案 | 块级 hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|
| **当前：查询改写 + bigram 分词** | **72.2%** | **88.9%** | **88.9%** | **94.4%** | **0.806** |
| 对照：不改写（中文直接检索） | 61.1% | 77.8% | 77.8% | 77.8% | 0.685 |

文档级（同一篇文献/同一条记录命中即算）：**hit@1 88.9%，hit@3 100%**。
→ 查询改写这一环让块级 hit@1 提升 11.1 个百分点、hit@10 提升 16.6 个百分点。

**一个反直觉的实测结论**：把中文分词从「单字」换成「bigram」，在 hit@k / MRR 上**完全没有差别**
（两种方案的指标逐位相同）—— 因为查询被改写成英文后，中文分词根本不参与打分。
bigram 的价值不在排名指标上，而在**避免假匹配**：单字方案下「碱基编辑」会和「基因」共享一个「基」字，
毫不相关的问题也能召回（`tests/test_text.py` 用回归测试锁住了这一点）。
**指标没动不等于改动没价值，但也不能拿它当"提升 XX%"来汇报。**

**多源语料**：PubMed 摘要 100 条 + UniProt 功能注释 40 条 + PDB 结构条目 20 条 → **160 条记录 / 592 块**。

**问答与成本**（`llm_client/logs/usage.csv` 累计实测）

| 指标 | 数值 |
|---|---|
| 单次中文问答（含改写） | 约 0.004 元、5 秒内返回 |
| 同一段 1728 tokens 前缀第二次调用 | 缓存命中 1536，花费 **↓69%**（0.001968 → 0.000611 元） |
| 一份 5 条资料的速读报告 | **0.034 元**（含一篇主题综述） |
| 18 道题的评测集生成 | 0.238 元；改写 18 个问题 0.060 元（结果已缓存，重复评测不再花钱） |
| 网络抖动 | 自动重试 3 次（1s → 2s → 4s 退避），不把失败丢给用户 |

**数据分析**（500 条人类 RefSeq mRNA 记录）

| 指标 | 数值 |
|---|---|
| 记录 / 覆盖基因 | 500 条 / 142 个基因 |
| 序列长度 | 中位 3040 bp（478–16398 bp），强右偏 |
| GC 含量 | 中位 47.2%（32.8%–73.3%） |
| 对数长度 vs GC | r = **−0.197**（弱负相关：转录本越长，GC 略低） |

![每年记录数](data_analysis/out/fig1_by_year.png)
![长度分布](data_analysis/out/fig2_length.png)
![长度与 GC](data_analysis/out/fig3_gc_length.png)
![top 基因](data_analysis/out/fig4_top_genes.png)

## 模块

```
bio-ai-prep/
├── rag/                    检索问答（系统主体）
│   ├── corpus.py               多源语料归一化（PubMed / UniProt / PDB → 统一记录）
│   ├── fetch_pubmed.py         PubMed 摘要（esearch + efetch）
│   ├── fetch_uniprot.py        UniProt 蛋白功能注释
│   ├── fetch_pdb.py            RCSB PDB 结构条目
│   ├── text.py                 切分（句子边界 + 重叠）与中英混合分词
│   ├── store.py                BM25 索引：建索引 / 检索 / 存取
│   ├── query.py                中文问句 → 英文检索关键词
│   ├── pipeline.py             引擎层：问答与报告生成（CLI 与界面共用）
│   ├── ask.py / report.py      两个命令行入口（只做参数与打印）
│   ├── build_index.py          切块建索引 → rag/index/bm25.json
│   ├── make_eval.py / eval.py  自动生成评测集 + hit@k / MRR / 对照实验
│   ├── reports/                生成过的报告样例
│   └── data/*.jsonl            语料（已入库）
├── llm_client/             大模型调用层（可复用于任何下游）
│   ├── llm.py                  流式 SSE / 超时 / 指数退避重试 / 按官方价目表计价
│   ├── chat.py                 命令行多轮对话（/cost /reset /exit）
│   └── logs/usage.csv          每次调用的 token 与花费流水
├── ui/app.py               Streamlit 界面：问答 / 速读报告 / 语料与指标
├── data_analysis/          真实数据清洗与可视化（notebook 含真实输出）
├── seq_tools/              序列处理基础工具（纯标准库）
├── common/viz.py           统一出图规范：字体/配色/边框/dpi
├── tests/                  18 项测试（切分、分词、检索、序列算法、界面冒烟）
└── requirements.txt · .env.example · LICENSE
```

## 设计取舍（都是被实际问题逼出来的）

| 决定 | 为什么 |
|---|---|
| **检索先用 BM25，不硬上向量** | DeepSeek 没有 embedding 接口，本地向量模型要下几百 MB；BM25 零依赖、可解释。检索层独立，换语义检索只需重写 `store.py` 的 `search()`，上层不动 |
| **中文问题必须先改写成英文关键词** | 词面检索下中文词在英文索引里不存在 —— 实测中文主题直接查 PubMed 会得到「命中 96 万篇 + 一堆不相关文献」。评测显示改写让 hit@1 从 61.1% 提到 72.2% |
| **多源语料先归一化再入库** | 三种来源字段名各异，让检索层去认差异会导致"每加一个数据源就改一遍检索代码"。现在加数据源只需在 `corpus.py` 注册一行 |
| **逻辑集中在 pipeline.py，脚本只做参数** | 命令行和 Web 界面共用同一套实现，避免"改了 CLI 忘了改界面" |
| **评测集用模型反推生成** | 人工标注几百条成本太高；自动集能支撑"横向比较改动"这个用途，但要写明它带出题人偏见，不能当绝对准确率 |
| **中文分词用 bigram 而非单字** | 单字会让「碱基编辑」误匹配「基因」；指标上无差异，价值在避免假匹配（有回归测试） |
| **切分按句子边界 + 重叠 100 字符** | 避免答案正好落在切口上；块长 600 与 400 实测对比过：小块分数更高，但同一篇论文会重复占位，多样性变差 |
| **缺失值不填 0** | 0% GC 在生物学上不存在；填了会造出假数据点。分析时取子集，而不是伪造全量 |
| **指数退避重试 + 超时** | NCBI 与各公共接口都会间歇性超时（实测多次 `WinError 10060`），不带重试整批白跑 |
| **出图规范集中在一个文件** | 字体、配色、边框、dpi 一处控制；顺带解决中文字体缺粗体字重的报警 |
| **成本按官方价目表实时计价** | 自动区分高峰/空闲（空闲半价）与缓存命中/未命中，每次调用落一行流水，随时能答"这个月花了多少" |

## 测试

```bash
.venv/Scripts/python.exe -m pytest tests -q     # 18 passed
```

- `test_text.py`：切分预算、句子边界、中英混合分词、bigram 不跨标点
- `test_store.py`：相关性排序、空查询、未知词不误召回、存取一致性
- `test_seq_tools.py`：GC 边界值、反向互补、终止密码子、FASTA 解析
- `test_ui.py`：界面脚本冒烟（Streamlit AppTest，无浏览器也能跑）

## 局限与下一步

- **评测集带偏**：题目由模型从资料反推生成，用词贴着原文，比真实用户提问更容易命中；真实提问的命中率大概率更低。这套指标用于横向比较改动，不等于线上准确率。
- **样本是切片**：语料是各库按主题检索的前若干条，不能外推到整个文献库；报告里也据此措辞。
- **词面检索的天花板**：同义改写（"tumor" vs "neoplasm"）召不回来，需要语义向量或查询扩展。
- **下一步**：语义检索（换掉 `search()` 打分）→ 更大评测集与人工抽检 → 企业内网部署形态（数据不外发的私有化选项、权限与审计）。

## 作者

李林峻 · GitHub [@LXM-66](https://github.com/LXM-66) · MIT License
