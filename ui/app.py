"""Web 界面：给不写代码的人用（产品化的最后一步）。

    streamlit run ui/app.py

三个页签：
    问答     —— 提问 → 带引用的回答，可展开看每一条引用的原文与链接
    速读报告 —— 输入主题 → 生成 markdown 报告，可预览、可下载
    语料与指标 —— 语料构成、检索评测结果、累计花费

界面只调用 rag/pipeline.py 的引擎层，不重复实现任何逻辑。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("rag", "llm_client"):
    sys.path.insert(0, str(ROOT / sub))

import json                                    # noqa: E402

import streamlit as st                         # noqa: E402

from pipeline import REPORT_DIR, Engine, corpus_overview   # noqa: E402

st.set_page_config(page_title="生物医药文献助手", page_icon="🧬", layout="wide")


@st.cache_resource(show_spinner="加载索引…")
def get_engine():
    return Engine()


def try_engine():
    """索引不存在时给一句人话提示，而不是抛一堆栈 —— 第一次用的人多半没建索引。"""
    try:
        return get_engine()
    except FileNotFoundError:
        st.error("还没建索引。先在项目根目录跑：`python rag/build_index.py`")
        st.stop()


@st.cache_data(ttl=60)
def get_overview():
    return corpus_overview()


def usage_total():
    """累计花费：直接读大模型调用流水，不额外记账。"""
    path = ROOT / "llm_client" / "logs" / "usage.csv"
    if not path.exists():
        return 0.0, 0
    import csv
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    return sum(float(r["cost_cny"]) for r in rows), len(rows)


eng = try_engine()
ov = get_overview()
total_cost, calls = usage_total()

with st.sidebar:
    st.title("🧬 生物医药文献助手")
    st.caption("检索增强问答（BM25 + DeepSeek）")
    st.metric("语料", f"{ov['records']} 条")
    for source, n in ov["by_source"].items():
        st.caption(f"· {source}：{n} 条")
    st.divider()
    k = st.slider("检索块数 k", 1, 10, 5, help="喂给模型的资料块数：太少可能缺信息，太多会分散注意力并增加成本")
    st.divider()
    st.caption(f"本次会话累计 {total_cost:.4f} 元（{calls} 次调用）")
    if eng.bot_error:
        st.warning(f"未配置 API key，只能检索：{eng.bot_error}")

tab_ask, tab_report, tab_about = st.tabs(["问答", "速读报告", "语料与指标"])

with tab_ask:
    st.subheader("问点什么")
    st.caption("中文提问即可 —— 系统会先把它改写成英文检索词，因为语料以英文文献为主。")
    q = st.text_input("问题", placeholder="例如：DNA 错配修复蛋白的功能是什么？")
    if st.button("提问", type="primary") and q.strip():
        with st.spinner("检索并生成…"):
            r = eng.ask(q, k=k)
        if not r["hits"]:
            st.error("检索不到相关内容 —— 换个说法，或先扩充语料。")
        else:
            if r["query"].strip() != q.strip():
                st.caption(f"检索式：`{r['query']}`")
            if r["answer"]:
                st.markdown(r["answer"])
                u = r["usage"]
                st.caption(f"消耗 {u['prompt_tokens']} + {u['completion_tokens']} tokens"
                           f"（缓存命中 {u['cache_hit_tokens']}）｜{u['seconds']:.2f}s｜{r['cost']:.6f} 元")
            else:
                st.info("未配置 API key，以下是检索结果。")
            st.markdown("**引用来源**")
            for i, h in enumerate(r["hits"], 1):
                with st.expander(f"[{i}] {h['source']} {h['sid']}｜{h['title'][:60]}｜相关度 {h['score']}"):
                    st.write(h["text"])
                    st.caption(f"{h['extra']} {h['year']}")
                    if h["url"]:
                        st.markdown(f"[查看原文]({h['url']})")

with tab_report:
    st.subheader("按主题生成中文速读报告")
    st.caption("每条资料一次摘要调用 + 一次综述调用，实测单条约 0.002 元。")
    topic = st.text_input("主题", placeholder="例如：单细胞测序在肿瘤免疫治疗中的应用")
    col1, col2, col3 = st.columns([1, 1, 2])
    limit = col1.number_input("资料条数", 3, 20, 5)
    days = col2.number_input("最近 N 天（0=不限）", 0, 3650, 180, step=30)
    local_only = col3.checkbox("只用本地语料（不联网取新文献）", value=False)
    if st.button("生成报告", type="primary") and topic.strip():
        status = st.status("生成中…", expanded=False)
        with st.spinner("逐条总结…"):
            r = eng.build_report(topic, limit=int(limit), days=int(days) or None,
                                 from_index=local_only, on_progress=lambda m: status.write(m))
        status.update(label=f"完成（{r.get('count', 0)} 条｜{r.get('cost', 0):.4f} 元）", state="complete")
        if r.get("error"):
            st.error(r["error"])
        else:
            st.download_button("下载 markdown", r["markdown"],
                               file_name=f"{topic[:20]}.md", mime="text/markdown")
            st.markdown(r["markdown"])

with tab_about:
    st.subheader("语料与检索质量")
    st.write({"记录数": ov["records"], "按来源": ov["by_source"], "索引块数": len(eng.idx.chunks)})
    result_path = ROOT / "rag" / "eval_result.json"
    if result_path.exists():
        data = json.loads(result_path.read_text(encoding="utf-8"))
        st.caption(f"评测集：{data['题目数']} 道题（由模型从语料反推生成）｜语料 {data['语料块数']} 块")
        st.dataframe(data["结果"], use_container_width=True, hide_index=True)
    else:
        st.info("还没有评测结果，先跑：python rag/eval.py")
    st.caption("检索指标只用于横向比较改动（换分词、换块长、换检索算法），不代表绝对准确率。")
